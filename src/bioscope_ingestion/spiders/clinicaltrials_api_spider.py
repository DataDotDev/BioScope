import os
from datetime import datetime, timezone
from urllib.parse import urlencode

from dateutil import parser as date_parser
import scrapy

from bioscope_ingestion.items import IngestionRecord
from common.config import env_bool, env_int, env_str
from common.state_store import SourceStateStore


class ClinicalTrialsApiSpider(scrapy.Spider):
    name = "clinicaltrials_api"
    allowed_domains = ["clinicaltrials.gov"]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        target_company = os.getenv("TARGET_COMPANY", "").strip()
        query = target_company or os.getenv("CLINICALTRIALS_QUERY", "diabetes")
        page_size = env_int("CLINICALTRIALS_PAGE_SIZE", 50)
        sort_order = (
            env_str("CLINICALTRIALS_SORT", "LastUpdatePostDate:desc")
            or "LastUpdatePostDate:desc"
        )
        incremental_enabled = env_bool("INCREMENTAL_ENABLED", True)
        pagination_cutoff_enabled = env_bool(
            "CLINICALTRIALS_PAGINATION_CUTOFF_ENABLED", True
        )
        state_store_path = (
            env_str("STATE_STORE_PATH", "./out/source_state.sqlite")
            or "./out/source_state.sqlite"
        )
        source_key = f"clinicaltrials_api:{query}:{page_size}:{sort_order}"
        state_store = SourceStateStore(state_store_path)
        state = state_store.get_state(source_key) if incremental_enabled else {}

        params = {
            "query.term": query,
            "pageSize": page_size,
            "sort": sort_order,
        }
        url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(
            params
        )

        yield scrapy.Request(
            url=url,
            callback=self.parse,
            cb_kwargs={
                "query": query,
                "page_size": page_size,
                "sort_order": sort_order,
                "source_key": source_key,
                "state_store": state_store,
                "previous_state": state,
                "run_max_seen": state.get("last_seen_ts"),
                "incremental_enabled": incremental_enabled,
                "pagination_cutoff_enabled": pagination_cutoff_enabled,
                "seen_page_tokens": set(),
            },
        )

    def parse(
        self,
        response,
        query,
        page_size,
        sort_order,
        source_key,
        state_store,
        previous_state,
        run_max_seen,
        incremental_enabled,
        pagination_cutoff_enabled,
        seen_page_tokens,
    ):
        payload = response.json()
        studies = payload.get("studies", [])
        target_company = os.getenv("TARGET_COMPANY", "").strip().lower()
        previous_last_seen = previous_state.get("last_seen_ts")
        max_seen = run_max_seen

        page_had_new_records = False
        oldest_seen_on_page = None

        for study in studies:
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            conditions = protocol.get("conditionsModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})
            observed_at = self._extract_study_observed_at(study)

            oldest_seen_on_page = self._min_ts(oldest_seen_on_page, observed_at)

            if incremental_enabled and previous_last_seen and observed_at <= previous_last_seen:
                continue

            page_had_new_records = True
            max_seen = self._max_ts(max_seen, observed_at)

            nct_id = identification.get("nctId")
            title = identification.get("briefTitle")
            phase = status.get("phase") or status.get("phases")
            overall_status = status.get("overallStatus")
            lead_sponsor = sponsor.get("leadSponsor", {}).get("name")

            if target_company and not self._matches_company(
                target_company, title, lead_sponsor, conditions.get("conditions", [])
            ):
                continue

            yield IngestionRecord(
                source="clinicaltrials.gov",
                record_type="clinical_trial",
                observed_at=observed_at,
                raw=study,
                normalized={
                    "trial_id": nct_id,
                    "title": title,
                    "phase": phase,
                    "status": overall_status,
                    "conditions": conditions.get("conditions", []),
                    "lead_sponsor": lead_sponsor,
                },
                identifiers={
                    "nct_id": nct_id,
                },
            )

        state_store.upsert_state(source_key=source_key, last_seen_ts=max_seen)

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            return

        if next_page_token in seen_page_tokens:
            self.logger.warning(
                "Duplicate nextPageToken detected for ClinicalTrials query '%s'; stopping pagination.",
                query,
            )
            return

        if self._should_cutoff_pagination(
            incremental_enabled=incremental_enabled,
            pagination_cutoff_enabled=pagination_cutoff_enabled,
            sort_order=sort_order,
            previous_last_seen=previous_last_seen,
            page_had_new_records=page_had_new_records,
            oldest_seen_on_page=oldest_seen_on_page,
        ):
            self.logger.info(
                "ClinicalTrials pagination cutoff reached for query '%s' at watermark %s",
                query,
                previous_last_seen,
            )
            return

        next_tokens = set(seen_page_tokens)
        next_tokens.add(next_page_token)
        params = {
            "query.term": query,
            "pageSize": page_size,
            "sort": sort_order,
            "pageToken": next_page_token,
        }
        next_url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(params)

        yield scrapy.Request(
            url=next_url,
            callback=self.parse,
            cb_kwargs={
                "query": query,
                "page_size": page_size,
                "sort_order": sort_order,
                "source_key": source_key,
                "state_store": state_store,
                "previous_state": previous_state,
                "run_max_seen": max_seen,
                "incremental_enabled": incremental_enabled,
                "pagination_cutoff_enabled": pagination_cutoff_enabled,
                "seen_page_tokens": next_tokens,
            },
        )

    @staticmethod
    def _matches_company(company: str, title: str | None, lead_sponsor: str | None, conditions: list[str]) -> bool:
        haystacks = [title, lead_sponsor, *conditions]
        company_terms = [term for term in company.split() if term]

        for haystack in haystacks:
            if not haystack:
                continue

            normalized_haystack = haystack.lower()
            if company in normalized_haystack:
                return True

            if all(term in normalized_haystack for term in company_terms):
                return True

        return False

    @staticmethod
    def _extract_study_observed_at(study: dict) -> str:
        protocol = study.get("protocolSection", {})
        status = protocol.get("statusModule", {})

        candidate_dates = [
            status.get("lastUpdatePostDateStruct", {}).get("date"),
            status.get("lastUpdateSubmitDateStruct", {}).get("date"),
            status.get("studyFirstPostDateStruct", {}).get("date"),
            status.get("resultsFirstPostDateStruct", {}).get("date"),
            status.get("completionDateStruct", {}).get("date"),
        ]

        for value in candidate_dates:
            parsed = ClinicalTrialsApiSpider._parse_date(value)
            if parsed:
                return parsed

        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_date(value: str | None) -> str | None:
        if not value:
            return None
        try:
            return date_parser.parse(value).astimezone(timezone.utc).isoformat()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _max_ts(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        return candidate if candidate > current else current

    @staticmethod
    def _min_ts(current: str | None, candidate: str | None) -> str | None:
        if not candidate:
            return current
        if not current:
            return candidate
        return candidate if candidate < current else current

    @staticmethod
    def _is_desc_last_update_sort(sort_order: str) -> bool:
        normalized = (sort_order or "").replace(" ", "").lower()
        return normalized == "lastupdatepostdate:desc"

    @staticmethod
    def _should_cutoff_pagination(
        incremental_enabled: bool,
        pagination_cutoff_enabled: bool,
        sort_order: str,
        previous_last_seen: str | None,
        page_had_new_records: bool,
        oldest_seen_on_page: str | None,
    ) -> bool:
        if not incremental_enabled or not pagination_cutoff_enabled:
            return False
        if not previous_last_seen:
            return False
        if page_had_new_records:
            return False
        if not oldest_seen_on_page:
            return False
        if not ClinicalTrialsApiSpider._is_desc_last_update_sort(sort_order):
            return False
        return oldest_seen_on_page <= previous_last_seen
