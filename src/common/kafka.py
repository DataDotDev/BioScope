import json
import os
import hashlib
from pathlib import Path
from typing import Any

try:
    from confluent_kafka import Producer
except ImportError:  # pragma: no cover - optional dependency
    Producer = None

from common.config import env_bool, env_str


class KafkaSink:
    def __init__(
        self,
        enabled: bool,
        brokers: str | None,
        topic: str,
        local_path: str,
        dedup_key: str,
        dedup_state_path: str,
        dedup_fallback_enabled: bool,
    ):
        self.enabled = enabled
        self.topic = topic
        self.local_path = Path(local_path)
        self.dedup_key = dedup_key
        self.dedup_state_path = Path(dedup_state_path)
        self.dedup_fallback_enabled = dedup_fallback_enabled
        self._seen_dedup_keys: set[str] = set()
        self._producer = None
        if enabled:
            if Producer is None:
                raise ImportError(
                    "KAFKA_ENABLED=true requires confluent-kafka and librdkafka"
                )
            if not brokers:
                raise ValueError("KAFKA_BROKERS is required when KAFKA_ENABLED=true")
            self._producer = Producer({"bootstrap.servers": brokers})
        else:
            self.local_path.parent.mkdir(parents=True, exist_ok=True)
            self.dedup_state_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_seen_dedup_keys()

    @classmethod
    def from_env(cls) -> "KafkaSink":
        enabled = env_bool("KAFKA_ENABLED", False)
        brokers = env_str("KAFKA_BROKERS")
        topic = env_str("KAFKA_TOPIC", "bioscope.ingestion.raw") or "bioscope.ingestion.raw"
        local_path = env_str("LOCAL_SINK_PATH", "./out/ingestion.jsonl") or "./out/ingestion.jsonl"
        dedup_key = env_str("LOCAL_DEDUP_KEY", "identifiers.nct_id") or "identifiers.nct_id"
        dedup_fallback_enabled = env_bool("LOCAL_DEDUP_FALLBACK_ENABLED", True)
        default_state_path = str(Path(local_path).with_suffix(".seen.json"))
        dedup_state_path = env_str("LOCAL_DEDUP_STATE_PATH", default_state_path) or default_state_path
        return cls(
            enabled=enabled,
            brokers=brokers,
            topic=topic,
            local_path=local_path,
            dedup_key=dedup_key,
            dedup_state_path=dedup_state_path,
            dedup_fallback_enabled=dedup_fallback_enabled,
        )

    def send(self, payload: Any) -> None:
        record = dict(payload) if not isinstance(payload, dict) else payload

        if self.enabled and self._producer:
            self._producer.produce(self.topic, json.dumps(record).encode("utf-8"))
            return

        dedup_value = self._extract_dedup_value(record)
        if dedup_value is None and self.dedup_fallback_enabled:
            dedup_value = self._build_fallback_dedup_value(record)
        if dedup_value and dedup_value in self._seen_dedup_keys:
            return

        with self.local_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        if dedup_value:
            self._seen_dedup_keys.add(dedup_value)
            self._persist_seen_dedup_keys()

    def flush(self) -> None:
        if self.enabled and self._producer:
            self._producer.flush(10)

    def _load_seen_dedup_keys(self) -> None:
        if not self.dedup_state_path.exists():
            return

        try:
            payload = json.loads(self.dedup_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if isinstance(payload, list):
            self._seen_dedup_keys = {str(value) for value in payload if value}

    def _persist_seen_dedup_keys(self) -> None:
        try:
            self.dedup_state_path.write_text(
                json.dumps(sorted(self._seen_dedup_keys), indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def _extract_dedup_value(self, record: dict[str, Any]) -> str | None:
        if not self.dedup_key:
            return None

        value: Any = record
        for part in self.dedup_key.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)

        if value in (None, ""):
            return None

        return str(value)

    @staticmethod
    def _build_fallback_dedup_value(record: dict[str, Any]) -> str | None:
        identifiers = record.get("identifiers")
        normalized = record.get("normalized")

        fingerprint_payload = {
            "source": record.get("source"),
            "record_type": record.get("record_type"),
            "observed_at": record.get("observed_at"),
            "identifiers": identifiers if isinstance(identifiers, dict) else {},
            "normalized": {
                "title": normalized.get("title") if isinstance(normalized, dict) else None,
                "link": normalized.get("link") if isinstance(normalized, dict) else None,
                "status": normalized.get("status") if isinstance(normalized, dict) else None,
                "lead_sponsor": (
                    normalized.get("canonical_lead_sponsor")
                    if isinstance(normalized, dict)
                    else None
                ),
            },
        }

        if not any(
            [
                fingerprint_payload["source"],
                fingerprint_payload["record_type"],
                fingerprint_payload["observed_at"],
                fingerprint_payload["identifiers"],
                fingerprint_payload["normalized"].get("title"),
                fingerprint_payload["normalized"].get("link"),
            ]
        ):
            return None

        encoded = json.dumps(
            fingerprint_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        return f"fp:{digest}"
