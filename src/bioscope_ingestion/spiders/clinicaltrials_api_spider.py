import os
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

from bioscope_ingestion.items import IngestionRecord


class ClinicalTrialsApiSpider(scrapy.Spider):
    name = "clinicaltrials_api"
    allowed_domains = ["clinicaltrials.gov"]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
    }

    def start_requests(self):
        target_company = os.getenv("TARGET_COMPANY", "").strip()
        query = target_company or os.getenv("CLINICALTRIALS_QUERY", "diabetes")
        page_size = int(os.getenv("CLINICALTRIALS_PAGE_SIZE", "50"))
        url = "https://clinicaltrials.gov/api/v2/studies?" + urlencode(
            {"query.term": query, "pageSize": page_size}
        )
        yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        payload = response.json()
        studies = payload.get("studies", [])
        target_company = os.getenv("TARGET_COMPANY", "").strip().lower()

        for study in studies:
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            conditions = protocol.get("conditionsModule", {})
            sponsor = protocol.get("sponsorCollaboratorsModule", {})

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
                observed_at=datetime.now(timezone.utc).isoformat(),
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
