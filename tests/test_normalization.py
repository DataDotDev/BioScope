from common import normalization as norm


def test_normalize_company_name_suffix_cleanup() -> None:
    norm._company_alias_map.cache_clear()
    assert norm.normalize_company_name("Pfizer, Inc.") == "pfizer"


def test_normalize_drug_name_form_cleanup() -> None:
    norm._drug_alias_map.cache_clear()
    assert norm.normalize_drug_name("Semaglutide injection") == "semaglutide"


def test_normalize_company_name_alias_map(monkeypatch) -> None:
    monkeypatch.setenv("COMPANY_CANONICAL_MAP_JSON", '{"novo nordisk a/s":"novo nordisk"}')
    norm._company_alias_map.cache_clear()

    assert norm.normalize_company_name("Novo Nordisk A/S") == "novo nordisk"

    norm._company_alias_map.cache_clear()


def test_normalize_drug_name_alias_map(monkeypatch) -> None:
    monkeypatch.setenv("DRUG_CANONICAL_MAP_JSON", '{"pembrolizumab (keytruda)":"pembrolizumab"}')
    norm._drug_alias_map.cache_clear()

    assert norm.normalize_drug_name("pembrolizumab (keytruda)") == "pembrolizumab"

    norm._drug_alias_map.cache_clear()
