import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from app.utils.config import JARVIS_LLM_MODEL


@dataclass
class LLMResult:
    text: Optional[str]
    ok: bool
    model: str
    error: Optional[str] = None


class JarvisLLMClient:
    def __init__(self, model: str = JARVIS_LLM_MODEL, api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None
        self._load_error: Optional[str] = None

    def available(self) -> bool:
        return self._get_client() is not None

    def status_label(self) -> str:
        if self.available():
            return f"ChatGPT ready ({self.model})"
        return self._load_error or "ChatGPT offline"

    def generate_text(
        self,
        instructions: str,
        prompt: str,
        max_output_tokens: int = 600,
    ) -> LLMResult:
        client = self._get_client()
        if client is None:
            return LLMResult(text=None, ok=False, model=self.model, error=self._load_error)

        try:
            response = client.responses.create(
                model=self.model,
                instructions=instructions,
                input=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_output_tokens=max_output_tokens,
            )
            text = (getattr(response, "output_text", None) or self._extract_output_text(response)).strip()
            if not text:
                return LLMResult(text=None, ok=False, model=self.model, error="empty_response")
            return LLMResult(text=text, ok=True, model=self.model)
        except Exception as exc:  # pragma: no cover - network/runtime path
            return LLMResult(text=None, ok=False, model=self.model, error=str(exc))

    def generate_json(
        self,
        instructions: str,
        prompt: str,
        max_output_tokens: int = 700,
    ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        result = self.generate_text(instructions, prompt, max_output_tokens=max_output_tokens)
        if not result.ok or not result.text:
            return None, result.error

        payload = self._extract_json_object(result.text)
        if payload is None:
            return None, "invalid_json"
        return payload, None

    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.api_key:
            self._load_error = "Missing OPENAI_API_KEY"
            return None

        try:
            from openai import OpenAI
        except Exception:
            self._load_error = "OpenAI SDK not installed in this environment"
            return None

        self._client = OpenAI(api_key=self.api_key)
        self._load_error = None
        return self._client

    @staticmethod
    def _extract_output_text(response: Any) -> str:
        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", "") == "output_text":
                    parts.append(getattr(content, "text", ""))
        return "\n".join(part for part in parts if part)

    @staticmethod
    def _extract_json_object(text: str) -> Optional[dict[str, Any]]:
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                return None
            try:
                payload = json.loads(match.group(0))
                return payload if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                return None
