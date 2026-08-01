from __future__ import annotations

from transformers import PreTrainedTokenizerFast

CHAT_SPECIAL_TOKENS = (
    "<|pad|>",
    "<|unk|>",
    "<|bos|>",
    "<|eos|>",
    "<|self|>",
    "<|partner|>",
    "<|end_turn|>",
    "<|memory|>",
    "<|context|>",
    "<|bot|>",
    "<|latent|>",
    "<|eot|>",
    "<|tool_call|>",
    "<|end_tool_call|>",
    "<|tool_result|>",
)

ADDITIONAL_SPECIAL_TOKENS = CHAT_SPECIAL_TOKENS[4:]


def load_chat_tokenizer(path: str) -> PreTrainedTokenizerFast:
    return PreTrainedTokenizerFast.from_pretrained(
        path,
        bos_token="<|bos|>",
        eos_token="<|eos|>",
        unk_token="<|unk|>",
        pad_token="<|pad|>",
        additional_special_tokens=list(ADDITIONAL_SPECIAL_TOKENS),
    )


def special_token_ids(tokenizer: PreTrainedTokenizerFast) -> dict[str, int]:
    return {
        token: int(tokenizer.convert_tokens_to_ids(token))
        for token in CHAT_SPECIAL_TOKENS
    }
