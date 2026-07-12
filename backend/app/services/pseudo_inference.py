import asyncio
from collections.abc import AsyncIterator


class PseudoSodAI:
    """Development provider with the same streaming contract as a model worker."""

    async def stream(self, partner_message: str) -> AsyncIterator[str]:
        response = self.compose(partner_message)
        for index in range(0, len(response), 2):
            await asyncio.sleep(0.035)
            yield response[index : index + 2]

    @staticmethod
    def compose(message: str) -> str:
        normalized = " ".join(message.split())
        lowered = normalized.lower()
        if any(
            greeting in lowered for greeting in ("こんにちは", "こんばんは", "おはよう", "hello")
        ):
            return "こんにちは。ここにいます。今日は、どんなことを話しましょうか。"
        if "ありがとう" in lowered:
            return "どういたしまして。そう言ってもらえると、少しうれしいです。"
        if normalized.endswith(("?", "？")) or any(
            word in normalized for word in ("どう", "なぜ", "何", "どの", "教えて")
        ):
            return (
                f"「{_excerpt(normalized)}」という問いですね。今は疑似AIですが、"
                "問いの輪郭は受け取れています。もう少し背景を聞かせてもらえれば、"
                "一緒に考えられます。"
            )
        return (
            f"「{_excerpt(normalized)}」と受け取りました。"
            "今の私は基盤確認用の疑似AIです。それでも会話の流れは覚えながら、"
            "あなたの言葉に応答できます。"
        )


def _excerpt(message: str) -> str:
    return message if len(message) <= 42 else f"{message[:41]}…"
