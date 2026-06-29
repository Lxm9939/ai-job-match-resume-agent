"""LLM adapter with OpenAI and local mock modes."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from src.config import Settings, get_settings


class LLMClient:
    """Small JSON-first LLM wrapper.

    Agents pass in deterministic fallback data. In mock mode, the fallback is
    returned immediately. In OpenAI mode, the client asks the model for JSON and
    falls back safely if the API is unavailable or returns invalid JSON.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def mode(self) -> str:
        return self.settings.effective_llm_mode

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        fallback: Dict[str, Any],
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        if self.is_mock:
            return fallback

        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.settings.openai_api_key)
            response = client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(_extract_json(content))
        except Exception:
            return fallback


def _extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        return match.group(0)
    return "{}"

