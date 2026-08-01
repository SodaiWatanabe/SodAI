from __future__ import annotations

from sodai_contracts.inference import GenerationTurn, InferenceSpeaker
from transformers import PreTrainedTokenizerFast

from sodai_inference.tokenization import load_chat_tokenizer


def load_tokenizer(path: str) -> PreTrainedTokenizerFast:
    return load_chat_tokenizer(path)


class Asuka1PromptBuilder:
    def __init__(self, tokenizer: PreTrainedTokenizerFast) -> None:
        self._tokenizer = tokenizer
        self._bos = self._marker("<|bos|>")
        self._partner = self._marker("<|partner|>")
        self._self = self._marker("<|self|>")
        self._bot = self._marker("<|bot|>")
        self._eot = self._marker("<|eot|>")
        self._end_turn = self._marker("<|end_turn|>")

    def encode(self, turns: tuple[GenerationTurn, ...], max_tokens: int) -> list[int]:
        turns = self._normalize_turns(turns)
        history_pairs = [turns[index : index + 2] for index in range(0, len(turns) - 1, 2)]
        history = [self._encode_pair(pair) for pair in history_pairs]
        current = self._encode_partner(turns[-1])
        suffix = [self._self, self._bot]

        while history and self._length(history, current, suffix) > max_tokens:
            history.pop(0)
        if self._length(history, current, suffix) > max_tokens:
            current = self._truncate_current_partner(turns[-1], max_tokens, suffix)

        token_ids = [self._bos]
        token_ids.extend(token for pair in history for token in pair)
        token_ids.extend(current)
        token_ids.extend(suffix)
        if len(token_ids) > max_tokens:
            raise ValueError("latest partner turn cannot fit within Asuka 1's context budget")
        return token_ids

    def _normalize_turns(
        self,
        turns: tuple[GenerationTurn, ...],
    ) -> tuple[GenerationTurn, ...]:
        if not turns or turns[-1].speaker is not InferenceSpeaker.PARTNER:
            raise ValueError("Asuka 1 prompt must end with a partner turn")

        normalized: list[GenerationTurn] = []
        for turn in turns:
            if not normalized and turn.speaker is InferenceSpeaker.SELF:
                continue
            if normalized and normalized[-1].speaker is turn.speaker:
                previous = normalized[-1]
                normalized[-1] = GenerationTurn(
                    turn.speaker,
                    "\n".join(part for part in (previous.content, turn.content) if part.strip()),
                )
                continue
            normalized.append(turn)

        return tuple(normalized)

    def _encode_pair(self, pair: tuple[GenerationTurn, ...]) -> list[int]:
        if len(pair) != 2:
            raise ValueError("Asuka 1 history must contain complete partner/self pairs")
        return [*self._encode_partner(pair[0]), *self._encode_self(pair[1])]

    def _encode_partner(self, turn: GenerationTurn) -> list[int]:
        return [self._partner, *self._content(turn.content), self._end_turn]

    def _encode_self(self, turn: GenerationTurn) -> list[int]:
        return [
            self._self,
            self._bot,
            self._eot,
            *self._content(turn.content),
            self._end_turn,
        ]

    def _truncate_current_partner(
        self,
        turn: GenerationTurn,
        max_tokens: int,
        suffix: list[int],
    ) -> list[int]:
        available = max_tokens - 1 - 1 - 1 - len(suffix)
        if available <= 0:
            raise ValueError("context budget is too small for the Asuka 1 prompt envelope")
        return [self._partner, *self._content(turn.content)[-available:], self._end_turn]

    def _length(
        self,
        history: list[list[int]],
        current: list[int],
        suffix: list[int],
    ) -> int:
        return 1 + sum(map(len, history)) + len(current) + len(suffix)

    def _marker(self, value: str) -> int:
        token_ids = self._tokenizer.encode(value, add_special_tokens=False)
        if len(token_ids) != 1:
            raise ValueError(f"Asuka 1 marker must be one token: {value}")
        return int(token_ids[0])

    def _content(self, value: str) -> list[int]:
        return self._tokenizer.encode(
            value.strip(),
            add_special_tokens=False,
            split_special_tokens=True,
        )
