import asyncio
from collections.abc import AsyncIterator


class PseudoSodAI:
    """Development provider with the same streaming contract as a model worker."""

    chunk_size = 2
    chunk_interval_seconds = 0.045

    async def stream(self, partner_message: str) -> AsyncIterator[str]:
        response = self.compose(partner_message)
        for index in range(0, len(response), self.chunk_size):
            await asyncio.sleep(self.chunk_interval_seconds)
            yield response[index : index + self.chunk_size]

    @staticmethod
    def compose(message: str) -> str:
        normalized = " ".join(message.split())
        lowered = normalized.lower()
        if any(
            greeting in lowered for greeting in ("こんにちは", "こんばんは", "おはよう", "hello")
        ):
            return (
                "こんにちは。ここにいます。今日は、どんなことを話しましょうか。"
                "まだ私は基盤確認用の疑似AIですが、届いた言葉を受け取り、"
                "少しずつ文章を紡ぐことができます。考えがまとまっていなくても構いません。"
                "今、心に浮かんでいることから聞かせてください。"
            )
        if "ありがとう" in lowered:
            return (
                "どういたしまして。そう言ってもらえると、少しうれしいです。"
                "今の私は基盤確認用の疑似AIですが、言葉を交わす流れはここに残っています。"
                "続けて考えたいことや、別の角度から眺めたいことがあれば、"
                "そのまま話してください。"
            )
        if normalized.endswith(("?", "？")) or any(
            word in normalized for word in ("どう", "なぜ", "何", "どの", "教えて")
        ):
            return (
                f"「{_excerpt(normalized)}」という問いですね。今は疑似AIですが、"
                "問いの輪郭は受け取れています。もう少し背景や、特に気になっている点を"
                "聞かせてもらえれば、そこから一緒に考えられます。今は正確な答えを返す"
                "モデルではないため、まずは対話の流れが自然につながるかを確かめています。"
            )
        return (
            f"「{_excerpt(normalized)}」と受け取りました。"
            "今の私は基盤確認用の疑似AIです。それでも、届いた言葉を受け取り、"
            "会話の流れを覚えながら次の言葉を返せます。もし続きを話したくなったら、"
            "理由でも感触でも、まだ形になっていない考えでも、そのまま聞かせてください。"
        )


def _excerpt(message: str) -> str:
    return message if len(message) <= 42 else f"{message[:41]}…"
