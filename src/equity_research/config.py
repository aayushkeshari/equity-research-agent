from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    sec_user_agent: str
    openai_api_key: str | None
    openai_model: str
    cache_dir: str = ".cache/sec"

    @classmethod
    def from_env(cls) -> "Settings":
        sec_user_agent = os.getenv("SEC_USER_AGENT", "").strip()
        if not sec_user_agent:
            raise ValueError(
                "SEC_USER_AGENT is required. Example: "
                "'Your Name your-email@example.com'"
            )
        return cls(
            sec_user_agent=sec_user_agent,
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip() or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
            cache_dir=os.getenv("SEC_CACHE_DIR", ".cache/sec"),
        )
