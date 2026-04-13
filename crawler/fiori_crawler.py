"""
Release ID reference:
  S28OP  = S/4HANA 2408 (latest on-premise)
  S27OP  = S/4HANA 2023
  S26OP  = S/4HANA 2022
  S25OP  = S/4HANA 2021
  S4HCCE = S/4HANA Cloud (public edition)

The crawler queries multiple releases, deduplicates by AppId, and
persists to data/fiori_apps_cache.json so it only runs once.
Re-run with --rebuild-index to refresh.
"""

import time
import json
import re
import requests
from typing import List, Dict, Any
from pathlib import Path

CACHE_PATH = Path("data/fiori_apps_cache.json")

BASE_URL = (
    "https://fioriappslibrary.hana.ondemand.com"
    "/sap/fix/externalViewer/services/SingleApp.xsodata/Details"
)

# Release IDs to crawl — covers on-premise 2021-2024 + cloud
# More releases = more apps but slower first run (all cached after)
RELEASE_IDS = [
    "S28OP",   # S/4HANA 2408 on-premise (latest)
    "S27OP",   # S/4HANA 2023
    "S26OP",   # S/4HANA 2022
    "S4HCCE",  # S/4HANA Cloud public edition
]

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; SAP-RAG-Analyzer/1.0)",
}

# Minimal but reliable seed corpus — used if ALL network calls fail
SEED_APPS: List[Dict[str, Any]] = [
    {
        "app_id": "F2697",
        "title": "Supplier Aging Report",
        "description": (
            "Detailed supplier aging report with configurable bucket definitions and key date. "
            "Shows open AP items grouped by overdue periods: current, 1-30, 31-60, 61-90, "
            "91-120, 120+ days. Reads BSIK/BSAK. Used for month-end close and vendor reconciliation."
        ),
        "app_type": "Analytical", "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": ["FI-AP", "aging", "BSIK", "BSAK", "overdue buckets", "vendor"],
    },
    {
        "app_id": "F2680",
        "title": "Accounts Payable Aging",
        "description": (
            "Aging report for AP open items grouped into overdue buckets. "
            "Reads BSIK and BSAK. Company code, vendor, and key date filters."
        ),
        "app_type": "Analytical", "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": ["FI-AP", "aging", "open items", "vendor", "BSIK", "BSAK"],
    },
    {
        "app_id": "F0316",
        "title": "Vendor Line Items",
        "description": (
            "Open and cleared vendor line items with due date, days overdue, amount, currency. "
            "Uses LFA1, BSIK. AP invoice follow-up and reconciliation."
        ),
        "app_type": "Transactional", "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": ["FI-AP", "vendor", "line items", "LFA1", "BSIK", "days overdue"],
    },
    {
        "app_id": "S_ALR_87012085",
        "title": "Vendor Overdue Items Classic",
        "description": (
            "Classic SAP report for vendor overdue payables. Reads BSIK/BSAK. "
            "Document date, due date, amount, days overdue. ALV grid output."
        ),
        "app_type": "Classic Report", "product": "SAP ERP/ECC",
        "business_role": "AP Controller",
        "tags": ["FI-AP", "overdue", "BSIK", "BSAK", "classic", "aging", "ALV"],
    },
]


class FioriCrawler:
    """
    Fetches SAP Fiori app metadata from the live xsodata API.

    Flow:
      1. Return cache if present (skip network — instant startup)
      2. Query Details entity for each release in RELEASE_IDS
      3. Deduplicate by AppId across releases
      4. Fall back to SEED_APPS if all network calls fail
      5. Persist to data/fiori_apps_cache.json
    """

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    def crawl(self) -> List[Dict[str, Any]]:
        if self.use_cache and CACHE_PATH.exists():
            print(f"      Loading cached Fiori corpus from {CACHE_PATH}")
            with open(CACHE_PATH, encoding="utf-8") as f:
                apps = json.load(f)
            print(f"      Cache hit: {len(apps)} apps loaded.")
            return apps

        all_apps: Dict[str, Dict] = {}  # keyed by app_id for dedup

        for release_id in RELEASE_IDS:
            print(f"      Fetching release {release_id}...")
            release_apps = self._fetch_release(release_id)
            for app in release_apps:
                aid = app.get("app_id", "")
                if aid and aid not in all_apps:
                    all_apps[aid] = app
            print(f"        → {len(release_apps)} apps fetched, "
                  f"{len(all_apps)} unique total so far")
            time.sleep(0.5)  # polite rate

        apps = list(all_apps.values())

        # Fall back to seeds if network failed entirely
        if not apps:
            print("      All API calls failed — using seed corpus.")
            apps = list(SEED_APPS)
        else:
            # Merge seeds for any missing app_ids (seeds have richer descriptions)
            seed_ids = {a["app_id"] for a in apps}
            for seed in SEED_APPS:
                if seed["app_id"] not in seed_ids:
                    apps.append(seed)

        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2, ensure_ascii=False)

        print(f"      Corpus persisted: {len(apps)} apps → {CACHE_PATH}")
        return apps

    def _fetch_release(self, release_id: str) -> List[Dict[str, Any]]:
        """Paginate through all Details for a given release."""
        apps = []
        skip = 0
        top = 200

        while True:
            url = (
                f"{BASE_URL}"
                f"?$format=json"
                f"&$filter=ReleaseId eq '{release_id}'"
                f"&$top={top}&$skip={skip}"
                f"&$select=AppId,Title,ShortDescription,AppType,Product,BusinessRole,LineOfBusiness"
            )
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                results = resp.json().get("d", {}).get("results", [])
                if not results:
                    break
                for r in results:
                    apps.append(self._parse(r))
                if len(results) < top:
                    break
                skip += top
                time.sleep(0.3)
            except requests.RequestException as e:
                print(f"        Warning: {release_id} page skip={skip} failed: {e}")
                break

        return apps

    @staticmethod
    def _parse(r: dict) -> Dict[str, Any]:
        desc = FioriCrawler._clean(r.get("ShortDescription", ""))
        tags = []
        for field in ("LineOfBusiness", "AppType", "BusinessRole"):
            val = r.get(field, "")
            if val:
                tags.extend([t.strip() for t in re.split(r"[,;|/]", val) if t.strip()])
        return {
            "app_id": r.get("AppId", ""),
            "title": r.get("Title", ""),
            "description": desc,
            "app_type": r.get("AppType", ""),
            "product": r.get("Product", ""),
            "business_role": r.get("BusinessRole", ""),
            "tags": list(set(tags)),
        }

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text or "")
        return re.sub(r"\s+", " ", text).strip()
    