from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass(frozen=True, slots=True)
class GPTConfig:
    vocab_size: int
    block_size: int
    n_embd: int
    n_head: int
    n_layer: int
    dropout: float = 0.0
    ffn_multiple_of: int = 256
    ffn_hidden_size: int | None = None


def apply_rope(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    x_even = x[..., 0::2]
    x_odd = x[..., 1::2]
    return torch.stack(
        (
            x_even * cos - x_odd * sin,
            x_even * sin + x_odd * cos,
        ),
        dim=-1,
    ).flatten(-2)


class RotaryEmbedding(nn.Module):
    def __init__(self, head_size: int, theta: float = 10_000.0) -> None:
        super().__init__()
        if head_size % 2:
            raise ValueError("RoPE requires an even head size")
        inv_freq = 1.0 / (
            theta ** (torch.arange(0, head_size, 2, dtype=torch.float32) / head_size)
        )
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    def forward(
        self,
        sequence_length: int,
        device: torch.device,
        dtype: torch.dtype,
        position_offset: int = 0,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        positions = torch.arange(
            position_offset,
            position_offset + sequence_length,
            device=device,
            dtype=self.inv_freq.dtype,
        )
        frequencies = torch.outer(positions, self.inv_freq.to(device=device))
        cosine = frequencies.cos().to(dtype=dtype)
        sine = frequencies.sin().to(dtype=dtype)
        return cosine[None, None, :, :], sine[None, None, :, :]


class CausalSelfAttention(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        if config.n_embd % config.n_head:
            raise ValueError("n_embd must be divisible by n_head")
        self.n_head = config.n_head
        self.head_size = config.n_embd // config.n_head
        self.qkv = nn.Linear(config.n_embd, 3 * config.n_embd)
        self.proj = nn.Linear(config.n_embd, config.n_embd)
        self.rope = RotaryEmbedding(self.head_size)
        self.dropout_p = config.dropout
        self.dropout = nn.Dropout(config.dropout)

    def forward(
        self,
        hidden: torch.Tensor,
        past_key_value: tuple[torch.Tensor, torch.Tensor] | None = None,
        *,
        use_cache: bool = False,
    ):
        batch_size, sequence_length, embedding_size = hidden.shape
        query, key, value = self.qkv(hidden).split(embedding_size, dim=-1)
        shape = (batch_size, sequence_length, self.n_head, self.head_size)
        query = query.view(shape).transpose(1, 2)
        key = key.view(shape).transpose(1, 2)
        value = value.view(shape).transpose(1, 2)

        past_length = 0 if past_key_value is None else past_key_value[0].size(-2)
        cosine, sine = self.rope(
            sequence_length,
            hidden.device,
            query.dtype,
            position_offset=past_length,
        )
        query = apply_rope(query, cosine, sine)
        key = apply_rope(key, cosine, sine)

        if past_key_value is not None:
            past_key, past_value = past_key_value
            key = torch.cat((past_key, key), dim=-2)
            value = torch.cat((past_value, value), dim=-2)

        attention_mask = None
        is_causal = past_key_value is None
        if past_key_value is not None and sequence_length > 1:
            query_positions = torch.arange(
                past_length,
                past_length + sequence_length,
                device=hidden.device,
            )[:, None]
            key_positions = torch.arange(key.size(-2), device=hidden.device)[None, :]
            allowed = key_positions <= query_positions
            attention_mask = torch.zeros(
                (sequence_length, key.size(-2)),
                device=hidden.device,
                dtype=query.dtype,
            )
            attention_mask.masked_fill_(~allowed, float("-inf"))

        output = F.scaled_dot_product_attention(
            query,
            key,
            value,
            attn_mask=attention_mask,
            is_causal=is_causal,
            dropout_p=self.dropout_p if self.training else 0.0,
        )
        output = output.transpose(1, 2).contiguous().view(
            batch_size, sequence_length, embedding_size
        )
        output = self.dropout(self.proj(output))
        if use_cache:
            return output, (key, value)
        return output


class FeedForward(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        hidden_size = config.ffn_hidden_size
        if hidden_size is None:
            hidden_size = math.ceil((8 * config.n_embd / 3) / config.ffn_multiple_of)
            hidden_size *= config.ffn_multiple_of
        if hidden_size <= 0:
            raise ValueError("ffn hidden size must be positive")
        self.gate = nn.Linear(config.n_embd, hidden_size)
        self.up = nn.Linear(config.n_embd, hidden_size)
        self.down = nn.Linear(hidden_size, config.n_embd)
        self.dropout = nn.Dropout(config.dropout)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down(F.silu(self.gate(hidden)) * self.up(hidden)))


class Block(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.ln1 = nn.LayerNorm(config.n_embd)
        self.attention = CausalSelfAttention(config)
        self.ln2 = nn.LayerNorm(config.n_embd)
        self.feed_forward = FeedForward(config)

    def forward(
        self,
        hidden: torch.Tensor,
        past_key_value: tuple[torch.Tensor, torch.Tensor] | None = None,
        *,
        use_cache: bool = False,
    ):
        attention_output = self.attention(
            self.ln1(hidden),
            past_key_value,
            use_cache=use_cache,
        )
        present_key_value = None
        if use_cache:
            attention_output, present_key_value = attention_output
        hidden = hidden + attention_output
        hidden = hidden + self.feed_forward(self.ln2(hidden))
        if use_cache:
            return hidden, present_key_value
        return hidden


class RoPEGPT(nn.Module):
    def __init__(self, config: GPTConfig) -> None:
        super().__init__()
        self.config = config
        self.token_embedding = nn.Embedding(config.vocab_size, config.n_embd)
        self.blocks = nn.Sequential(*(Block(config) for _ in range(config.n_layer)))
        self.ln_f = nn.LayerNorm(config.n_embd)
        self.lm_head = nn.Linear(config.n_embd, config.vocab_size, bias=False)
        self.dropout = nn.Dropout(config.dropout)
        self.apply(self._init_weights)
        self.lm_head.weight = self.token_embedding.weight

    @staticmethod
    def _init_weights(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        token_ids: torch.Tensor,
        targets: torch.Tensor | None = None,
        *,
        past_key_values: tuple[tuple[torch.Tensor, torch.Tensor], ...] | None = None,
        use_cache: bool = False,
    ):
        _, sequence_length = token_ids.shape
        if past_key_values is not None and len(past_key_values) != len(self.blocks):
            raise ValueError("past_key_values must contain one entry per block")
        past_length = 0 if past_key_values is None else past_key_values[0][0].size(-2)
        if past_length + sequence_length > self.config.block_size:
            raise ValueError(
                f"sequence length {past_length + sequence_length} exceeds "
                f"{self.config.block_size}"
            )

        hidden = self.dropout(self.token_embedding(token_ids))
        present_key_values = []
        if use_cache:
            for index, block in enumerate(self.blocks):
                past = None if past_key_values is None else past_key_values[index]
                hidden, present = block(hidden, past, use_cache=True)
                present_key_values.append(present)
        else:
            hidden = self.blocks(hidden)
        logits = self.lm_head(self.ln_f(hidden))
        loss = None
        if targets is not None:
            loss = F.cross_entropy(
                logits.reshape(-1, logits.size(-1)),
                targets.reshape(-1),
                ignore_index=-100,
            )
        if use_cache:
            return logits, loss, tuple(present_key_values)
        return logits, loss
