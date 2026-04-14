from bioscope_ingestion.schemas import validate_ingestion_record


def _valid_record() -> dict:
    return {
        "source": " clinicaltrials.gov ",
        "record_type": " clinical_trial ",
        "observed_at": "2026-04-14T00:00:00Z",
        "raw": {"foo": "bar"},
        "normalized": {"title": "sample"},
        "identifiers": {"nct_id": "NCT00000001"},
    }


def test_validate_ingestion_record_valid_payload() -> None:
    validated, error = validate_ingestion_record(_valid_record())

    assert error is None
    assert validated is not None
    assert validated["source"] == "clinicaltrials.gov"
    assert validated["record_type"] == "clinical_trial"
    assert validated["observed_at"] == "2026-04-14T00:00:00Z"


def test_validate_ingestion_record_missing_required_field() -> None:
    payload = _valid_record()
    payload.pop("source")

    validated, error = validate_ingestion_record(payload)

    assert validated is None
    assert error is not None


def test_validate_ingestion_record_empty_record_type() -> None:
    payload = _valid_record()
    payload["record_type"] = "   "

    validated, error = validate_ingestion_record(payload)

    assert validated is None
    assert error is not None
