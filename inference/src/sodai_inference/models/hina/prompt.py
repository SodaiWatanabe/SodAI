from __future__ import annotations

from sodai_contracts.inference import GenerationTurn, InferenceSpeaker
from transformers import PreTrainedTokenizerFast

from sodai_inference.tokenization import load_chat_tokenizer


def load_tokenizer(path: str) -> PreTrainedTokenizerFast:
    return load_chat_tokenizer(path)


class HinaPromptBuilder:
    def __init__(self, tokenizer: PreTrainedTokenizerFast) -> None:
        self._tokenizer = tokenizer

    def encode(self, turns: tuple[GenerationTurn, ...], max_tokens: int) -> list[int]:
        prefix = self._encode("<|bos|>\n")
        suffix = self._encode("<|self|>\n")
        segments: list[list[int]] = []
        for turn in reversed(turns):
            segment = self._encode_turn(turn)
            if _total_length(prefix, [segment, *segments], suffix) <= max_tokens:
                segments.insert(0, segment)
                continue
            if not segments:
                segments.append(self._truncate_latest_partner(turn, max_tokens, prefix, suffix))
            break

        token_ids = prefix + [token for segment in segments for token in segment] + suffix
        if len(token_ids) > max_tokens:
            raise ValueError("latest partner turn cannot fit within Hina's context budget")
        return token_ids

    def _encode_turn(self, turn: GenerationTurn) -> list[int]:
        marker = "<|partner|>" if turn.speaker is InferenceSpeaker.PARTNER else "<|self|>"
        return self._encode(f"{marker}\n{turn.content.strip()}\n<|end_turn|>\n")

    def _truncate_latest_partner(
        self,
        turn: GenerationTurn,
        max_tokens: int,
        prefix: list[int],
        suffix: list[int],
    ) -> list[int]:
        if turn.speaker is not InferenceSpeaker.PARTNER:
            raise ValueError("Hina prompt must end with a partner turn")
        opening = self._encode("<|partner|>\n")
        closing = self._encode("\n<|end_turn|>\n")
        available = max_tokens - len(prefix) - len(suffix) - len(opening) - len(closing)
        if available <= 0:
            raise ValueError("context budget is too small for the Hina prompt envelope")
        content = self._encode(turn.content.strip())
        return opening + content[-available:] + closing

    def _encode(self, value: str) -> list[int]:
        return self._tokenizer.encode(value, add_special_tokens=False)


def _total_length(prefix: list[int], segments: list[list[int]], suffix: list[int]) -> int:
    return len(prefix) + sum(map(len, segments)) + len(suffix)
