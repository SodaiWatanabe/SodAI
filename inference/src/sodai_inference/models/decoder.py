from __future__ import annotations

from transformers import PreTrainedTokenizerFast


class IncrementalTextDecoder:
    """Emit only stable text while ByteLevel token fragments are incomplete."""

    def __init__(self, tokenizer: PreTrainedTokenizerFast) -> None:
        self._tokenizer = tokenizer
        self._token_ids: list[int] = []
        self._emitted = ""

    @property
    def content(self) -> str:
        return self._emitted

    def push(self, token_id: int) -> str:
        self._token_ids.append(token_id)
        decoded = self._decode().rstrip("\ufffd")
        if not decoded.startswith(self._emitted):
            return ""
        delta = decoded[len(self._emitted) :]
        self._emitted = decoded
        return delta

    def finish(self) -> str:
        decoded = self._decode()
        if not decoded.startswith(self._emitted):
            return ""
        delta = decoded[len(self._emitted) :]
        self._emitted = decoded
        return delta

    def _decode(self) -> str:
        return self._tokenizer.decode(
            self._token_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
