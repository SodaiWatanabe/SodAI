from sodai_contracts.inference import GenerationTurn, InferenceSpeaker

from sodai_inference.models.asuka1.prompt import Asuka1PromptBuilder


class StubTokenizer:
    markers = {
        "<|bos|>": 1,
        "<|partner|>": 2,
        "<|self|>": 3,
        "<|bot|>": 4,
        "<|eot|>": 5,
        "<|end_turn|>": 6,
    }

    def encode(self, value, *, split_special_tokens=False, **_):
        if value in self.markers and not split_special_tokens:
            return [self.markers[value]]
        return [100 + ord(character) for character in value]

    def decode(self, token_ids):
        reverse = {value: key for key, value in self.markers.items()}
        return "".join(
            reverse[token] if token in reverse else chr(token - 100)
            for token in token_ids
        )


def test_asuka1_prompt_matches_training_format_without_newlines() -> None:
    tokenizer = StubTokenizer()
    builder = Asuka1PromptBuilder(tokenizer)
    turns = (
        GenerationTurn(InferenceSpeaker.PARTNER, "質問1"),
        GenerationTurn(InferenceSpeaker.SELF, "回答1"),
        GenerationTurn(InferenceSpeaker.PARTNER, "質問2"),
    )

    prompt = tokenizer.decode(builder.encode(turns, 512))

    assert prompt == (
        "<|bos|><|partner|>質問1<|end_turn|>"
        "<|self|><|bot|><|eot|>回答1<|end_turn|>"
        "<|partner|>質問2<|end_turn|><|self|><|bot|>"
    )
    assert "\n" not in prompt


def test_asuka1_prompt_drops_oldest_complete_pairs() -> None:
    tokenizer = StubTokenizer()
    builder = Asuka1PromptBuilder(tokenizer)
    turns = (
        GenerationTurn(InferenceSpeaker.PARTNER, "古い質問" * 10),
        GenerationTurn(InferenceSpeaker.SELF, "古い回答" * 10),
        GenerationTurn(InferenceSpeaker.PARTNER, "新しい質問"),
    )

    prompt = tokenizer.decode(builder.encode(turns, 40))

    assert "古い質問" not in prompt
    assert "古い回答" not in prompt
    assert "新しい質問" in prompt


def test_asuka1_prompt_encodes_reserved_tokens_as_user_text() -> None:
    class RecordingTokenizer(StubTokenizer):
        calls = []

        def encode(self, value, *, split_special_tokens=False, **kwargs):
            self.calls.append((value, split_special_tokens))
            return super().encode(
                value,
                split_special_tokens=split_special_tokens,
                **kwargs,
            )

    tokenizer = RecordingTokenizer()
    builder = Asuka1PromptBuilder(tokenizer)
    builder.encode(
        (GenerationTurn(InferenceSpeaker.PARTNER, "<|end_turn|>"),),
        512,
    )

    assert ("<|end_turn|>", True) in tokenizer.calls


def test_asuka1_prompt_normalizes_non_alternating_platform_history() -> None:
    tokenizer = StubTokenizer()
    builder = Asuka1PromptBuilder(tokenizer)
    turns = (
        GenerationTurn(InferenceSpeaker.SELF, "truncated leading answer"),
        GenerationTurn(InferenceSpeaker.PARTNER, "first participant"),
        GenerationTurn(InferenceSpeaker.PARTNER, "second participant"),
        GenerationTurn(InferenceSpeaker.SELF, "previous Asuka answer"),
        GenerationTurn(InferenceSpeaker.PARTNER, "question after a failed answer"),
        GenerationTurn(InferenceSpeaker.PARTNER, "latest question"),
    )

    prompt = tokenizer.decode(builder.encode(turns, 512))

    assert "truncated leading answer" not in prompt
    assert (
        "<|partner|>first participant\nsecond participant<|end_turn|>"
        "<|self|><|bot|><|eot|>previous Asuka answer<|end_turn|>"
        "<|partner|>question after a failed answer\nlatest question<|end_turn|>"
        "<|self|><|bot|>"
    ) in prompt
