import json
import re
from functools import lru_cache

from common.config import env_str


_PUNCTUATION_RE = re.compile(r"[^a-z0-9\s]")
_WHITESPACE_RE = re.compile(r"\s+")

_COMPANY_SUFFIXES = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "llc",
    "plc",
    "sa",
    "ag",
    "gmbh",
    "bv",
}

_DRUG_FORM_TOKENS = {
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "injection",
    "solution",
    "oral",
    "iv",
    "mg",
    "mcg",
    "ml",
}


def _normalize_text(value: str | None) -> str | None:
    if not value:
        return None

    lowered = value.strip().lower()
    if not lowered:
        return None

    cleaned = _PUNCTUATION_RE.sub(" ", lowered)
    compact = _WHITESPACE_RE.sub(" ", cleaned).strip()
    return compact or None


@lru_cache(maxsize=1)
def _company_alias_map() -> dict[str, str]:
    raw = env_str("COMPANY_CANONICAL_MAP_JSON", "") or ""
    if not raw.strip():
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    aliases: dict[str, str] = {}
    for alias, canonical in payload.items():
        alias_norm = _normalize_text(str(alias))
        canonical_norm = _normalize_text(str(canonical))
        if alias_norm and canonical_norm:
            aliases[alias_norm] = canonical_norm

    return aliases


@lru_cache(maxsize=1)
def _drug_alias_map() -> dict[str, str]:
    raw = env_str("DRUG_CANONICAL_MAP_JSON", "") or ""
    if not raw.strip():
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    aliases: dict[str, str] = {}
    for alias, canonical in payload.items():
        alias_norm = _normalize_text(str(alias))
        canonical_norm = _normalize_text(str(canonical))
        if alias_norm and canonical_norm:
            aliases[alias_norm] = canonical_norm

    return aliases


def normalize_company_name(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    alias_map = _company_alias_map()
    if normalized in alias_map:
        return alias_map[normalized]

    tokens = [token for token in normalized.split(" ") if token]
    while tokens and tokens[-1] in _COMPANY_SUFFIXES:
        tokens.pop()

    canonical = " ".join(tokens).strip()
    if not canonical:
        return normalized

    return alias_map.get(canonical, canonical)


def normalize_drug_name(value: str | None) -> str | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None

    alias_map = _drug_alias_map()
    if normalized in alias_map:
        return alias_map[normalized]

    tokens = [token for token in normalized.split(" ") if token]
    filtered = [token for token in tokens if token not in _DRUG_FORM_TOKENS]
    canonical = " ".join(filtered).strip() if filtered else normalized
    return alias_map.get(canonical, canonical)
