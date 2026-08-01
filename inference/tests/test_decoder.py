from sodai_inference.models.decoder import IncrementalTextDecoder


class StubTokenizer:
    def decode(self, token_ids, **_):
        values = {
            (): "",
            (1,): "�",
            (1, 2): "雛",
            (1, 2, 3): "雛です",
        }
        return values[tuple(token_ids)]


def test_decoder_holds_incomplete_bytelevel_text() -> None:
    decoder = IncrementalTextDecoder(StubTokenizer())

    assert decoder.push(1) == ""
    assert decoder.push(2) == "雛"
    assert decoder.push(3) == "です"
    assert decoder.content == "雛です"
