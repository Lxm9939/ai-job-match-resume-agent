"""Application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_mode: str = os.getenv("LLM_MODE", "auto").lower()
    app_debug: bool = os.getenv("APP_DEBUG", "false").lower() == "true"

    @property
    def effective_llm_mode(self) -> str:
        if self.llm_mode == "mock":
            return "mock"
        if self.llm_mode == "openai" and self.openai_api_key:
            return "openai"
        if self.llm_mode == "auto" and self.openai_api_key:
            return "openai"
        return "mock"

    @property
    def use_openai(self) -> bool:
        return self.effective_llm_mode == "openai"


def get_settings() -> Settings:
    """Return fresh settings so Streamlit reloads .env changes."""

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        llm_mode=os.getenv("LLM_MODE", "auto").lower(),
        app_debug=os.getenv("APP_DEBUG", "false").lower() == "true",
    )

