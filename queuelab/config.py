from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_DATABASE_URL = "postgresql://queuelab:queuelab@localhost:5432/queuelab"


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("QUEUELAB_DATABASE_URL", DEFAULT_DATABASE_URL),
    )
