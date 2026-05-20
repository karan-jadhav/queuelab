from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_DATABASE_URL = "postgresql://queuelab:queuelab@localhost:5432/queuelab"
DEFAULT_RABBITMQ_URL = "amqp://guest:guest@localhost:5672/%2F"
DEFAULT_SQS_ENDPOINT_URL = "http://localhost:4566"
DEFAULT_AWS_REGION = "us-east-1"


@dataclass(frozen=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    rabbitmq_url: str = DEFAULT_RABBITMQ_URL
    sqs_endpoint_url: str = DEFAULT_SQS_ENDPOINT_URL
    aws_region: str = DEFAULT_AWS_REGION


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("QUEUELAB_DATABASE_URL", DEFAULT_DATABASE_URL),
        rabbitmq_url=os.environ.get("QUEUELAB_RABBITMQ_URL", DEFAULT_RABBITMQ_URL),
        sqs_endpoint_url=os.environ.get("QUEUELAB_SQS_ENDPOINT_URL", DEFAULT_SQS_ENDPOINT_URL),
        aws_region=os.environ.get("AWS_DEFAULT_REGION", DEFAULT_AWS_REGION),
    )
