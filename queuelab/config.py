from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_DATABASE_URL = "postgresql://queuelab:queuelab@localhost:5432/queuelab"
DEFAULT_RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    rabbitmq_url: str = DEFAULT_RABBITMQ_URL


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("QUEUELAB_DATABASE_URL", DEFAULT_DATABASE_URL),
        rabbitmq_url=os.environ.get("QUEUELAB_RABBITMQ_URL", DEFAULT_RABBITMQ_URL),
    )
