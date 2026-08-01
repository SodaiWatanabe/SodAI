import torch

from sodai_inference.architectures.rope_gpt import GPTConfig, RoPEGPT


def test_cached_rope_logits_match_full_forward() -> None:
    torch.manual_seed(7)
    config = GPTConfig(
        vocab_size=64,
        block_size=16,
        n_embd=32,
        n_head=4,
        n_layer=2,
        ffn_hidden_size=64,
    )
    model = RoPEGPT(config).eval()
    token_ids = torch.tensor([[1, 2, 3, 4]])

    full_logits, _ = model(token_ids)
    prefix_logits, _, cache = model(token_ids[:, :3], use_cache=True)
    cached_logits, _, _ = model(
        token_ids[:, 3:],
        past_key_values=cache,
        use_cache=True,
    )

    assert prefix_logits.shape == (1, 3, 64)
    torch.testing.assert_close(cached_logits[:, -1], full_logits[:, -1])
