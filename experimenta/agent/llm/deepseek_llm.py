"""DeepSeek API LLM wrapper (OpenAI-compatible)."""

from typing import List, Dict, Any, Optional
from openai import OpenAI

from .base import BaseLLM


DEEPSEEK_API_BASE = "https://api.deepseek.com/v1"


class DeepSeekLLM(BaseLLM):
    """通过 DeepSeek 开放 API 调用的 LLM 封装。"""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        api_base: str = DEEPSEEK_API_BASE,
    ):
        """初始化 DeepSeek LLM。

        Args:
            model_name: 模型名称，如 deepseek-chat、deepseek-reasoner 等
            api_key: DeepSeek API Key
            api_base: API 基础 URL，默认 https://api.deepseek.com/v1
        """
        self.model_name = model_name
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
    ) -> str:
        """调用 DeepSeek API 生成回复。

        Args:
            messages: 消息列表，每项含 'role' 与 'content'
            temperature: 采样温度
            max_output_tokens: 最大生成 token 数

        Returns:
            模型生成的文本
        """
        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_output_tokens is not None:
            kwargs["max_tokens"] = max_output_tokens

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def format_message(self, role: str, content: str) -> Dict[str, str]:
        """格式化为 DeepSeek/OpenAI 所需的消息格式。

        Args:
            role: system / user / assistant
            content: 消息内容

        Returns:
            含 role、content 的字典
        """
        role_lower = role.lower()
        if role_lower not in ("system", "user", "assistant"):
            role_lower = "user" if role_lower in ("human",) else "assistant"
        return {"role": role_lower, "content": content}
