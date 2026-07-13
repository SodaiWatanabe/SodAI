from sodai_contracts.inference import GenerationTurn, InferenceSpeaker

from sodai_inference.models.hina.prompt import HinaPromptBuilder


class StubTokenizer:
    def encode(self, value, **_):
        return [ord(character) for character in value]

    def decode(self, token_ids, **_):
        return "".join(chr(token_id) for token_id in token_ids)


def test_prompt_uses_partner_self_vocabulary() -> None:
    tokenizer = StubTokenizer()
    builder = HinaPromptBuilder(tokenizer)
    turns = (
        GenerationTurn(InferenceSpeaker.PARTNER, "こんにちは"),
        GenerationTurn(InferenceSpeaker.SELF, "こんにちは。"),
        GenerationTurn(InferenceSpeaker.PARTNER, "あなたは誰ですか？"),
    )

    token_ids = builder.encode(turns, 384)
    prompt = tokenizer.decode(token_ids, skip_special_tokens=False)

    assert prompt.startswith("<|bos|>\n<|partner|>\nこんにちは")
    assert prompt.endswith("<|end_turn|>\n<|self|>\n")
    assert "<|user|>" not in prompt
    assert "<|assistant|>" not in prompt


def test_prompt_drops_oldest_complete_turns_to_fit_budget() -> None:
    tokenizer = StubTokenizer()
    builder = HinaPromptBuilder(tokenizer)
    turns = tuple(
        GenerationTurn(
            InferenceSpeaker.PARTNER if index % 2 == 0 else InferenceSpeaker.SELF,
            f"発言{index}" * 30,
        )
        for index in range(9)
    )

    token_ids = builder.encode(turns, 160)
    prompt = tokenizer.decode(token_ids, skip_special_tokens=False)

    assert len(token_ids) <= 160
    assert "発言8" in prompt
    assert "発言0" not in prompt
