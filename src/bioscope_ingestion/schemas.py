from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class IngestionRecordSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    record_type: str
    observed_at: datetime
    ingested_at: datetime | None = None
    raw: dict[str, Any]
    normalized: dict[str, Any]
    identifiers: dict[str, Any]

    @field_validator("source", "record_type")
    @classmethod
    def _must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must not be empty")
        return value.strip()


def validate_ingestion_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, ValidationError | None]:
    try:
        model = IngestionRecordSchema.model_validate(record)
        return model.model_dump(mode="json"), None
    except ValidationError as exc:
        return None, exc
