'''
This code crawls the fiori webpage and all the apps inside it
to build a vectorDB containing all the app descriptions.

1: Uses SAP's pubblic API to fetch all the apps listed there.
2: Fallsback on the url to scrape using requests + beautiful soup
'''

import time
import json
import re
import requests
from typing import List, Dict, Any
from pathlib import Path

FIORI_ODATA_BASE = (
    "https://fioriappslibrary.hana.ondemand.com/sap/opu/odata/sap/"
    "REFAPPS_APPS_CONSUME_SRV/MasterApps"
)

FIORI_SEARCH_URL = (
    "https://fioriappslibrary.hana.ondemand.com/sap/fix/externalViewer/index.html"
)

CACHE_PATH = Path("data/fiori_apps_cache.json")


#cureated most famous apps manually for fast results
SEED_APPS: List[Dict[str, Any]] = [

    {
        "app_id": "F2680",
        "title": "Accounts Payable Aging",
        "description": (
            "Displays a detailed aging report for accounts payable open items. "
            "Groups vendor invoices into configurable overdue buckets: current, 1-30, "
            "31-60, 61-90, 91-120, and 120+ days. Used by AP teams for month-end "
            "close, vendor reconciliation, and cash flow planning. Reads from BSIK and "
            "BSAK tables. Supports company code, vendor, and key date filters."
        ),
        "app_type": "Analytical",
        "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": ["FI-AP", "aging", "open items", "vendor", "overdue", "BSIK", "BSAK"],
    },
    {
        "app_id": "F0316",
        "title": "Vendor Line Items",
        "description": (
            "Shows open and cleared vendor line items across company codes. Supports "
            "due date monitoring, aging analysis, days overdue calculation, and overdue "
            "tracking. Includes vendor name (LFA1), document date, due date (FAEDT), "
            "amount, and currency. Used by AP teams for invoice follow-up and "
            "reconciliation."
        ),
        "app_type": "Transactional",
        "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": ["FI-AP", "vendor", "line items", "open items", "LFA1", "BSIK"],
    },
    {
        "app_id": "S_ALR_87012085",
        "title": "Vendor Overdue Items (classic)",
        "description": (
            "Standard SAP classic report for vendor overdue payables. Reads directly "
            "from BSIK and BSAK. Shows document number, document date, due date, "
            "amount, currency, and days overdue. Grouped by vendor with company code "
            "selection. Used for AP month-end closing and vendor aging analysis."
        ),
        "app_type": "Classic Report",
        "product": "SAP ERP / ECC",
        "business_role": "AP Controller",
        "tags": ["FI-AP", "overdue", "BSIK", "BSAK", "classic", "aging", "vendor"],
    },
    {
        "app_id": "F1306",
        "title": "Cash Discount Forecast",
        "description": (
            "Displays upcoming cash discount deadlines grouped by date horizon. "
            "Shares open item selection logic and vendor due date fields with AP aging. "
            "Company code and vendor filters. Focuses on discount optimization rather "
            "than overdue analysis."
        ),
        "app_type": "Analytical",
        "product": "S/4HANA Finance",
        "business_role": "Treasury Manager",
        "tags": ["FI-AP", "cash discount", "due date", "vendor", "open items"],
    },
    {
        "app_id": "F1543",
        "title": "Manage Supplier Accounts",
        "description": (
            "Supplier account overview with balance drilldown and line item details. "
            "Uses LFA1 and LFB1 master data. Supports company code parameter and "
            "vendor range selection. Does not provide aging bucket grouping."
        ),
        "app_type": "Transactional",
        "product": "S/4HANA",
        "business_role": "AP Accountant",
        "tags": ["vendor master", "LFA1", "LFB1", "supplier", "balance"],
    },
    {
        "app_id": "F3167",
        "title": "Display Payables — Aging Overview",
        "description": (
            "Analytical overview of payables aging for management reporting. Shows "
            "total outstanding amounts by aging bucket and vendor segment. Supports "
            "drill-through to individual line items. Designed for AP managers and "
            "financial controllers."
        ),
        "app_type": "Analytical",
        "product": "S/4HANA Finance",
        "business_role": "AP Manager",
        "tags": ["FI-AP", "aging", "payables", "analytical", "management reporting"],
    },
    {
        "app_id": "F2697",
        "title": "Supplier Aging Report",
        "description": (
            "Detailed supplier aging report with configurable bucket definitions and "
            "key date parameter. Shows open AP items grouped by overdue periods. "
            "Supports multi-company code and vendor group selection. Equivalent to "
            "custom ABAP aging reports built on BSIK/BSAK."
        ),
        "app_type": "Analytical",
        "product": "S/4HANA Finance",
        "business_role": "Accounts Payable Accountant",
        "tags": [
            "FI-AP", "aging", "supplier", "open items", "BSIK", "overdue buckets",
            "key date", "vendor reconciliation",
        ],
    },
]

class FioriCrawler:
    """
    crawls the fiori app metadata for vector db
    """

    def __init__(self,use_cache : bool = True,max_pages = 50):
        self.use_cache = use_cache
        self.max_pages = max_pages
        CACHE_PATH.parent.mkdir(parents=True,exist_ok=True) #create a cache file if it doesnt exist
    
    def crawl(self) -> List[Dict[str,Any]]:
        if self.use_cache and CACHE_PATH.exists():
            print(f"Loading fiori app cache")
            with open(CACHE_PATH) as f:
                apps = json.load(f)
            print(f"Cache hit: {len(apps)} apps loaded")
            return apps
        
        apps = []

        try:
            apps = self._crawl_odata()
        except Exception as e:
            print(f"Crawling fialed ({e}), using manual data.")
        
        existing_ids = {a.get("app_id") for a in apps}
        for seed in SEED_APPS:
            if seed["app_id"] not in existing_ids:
                apps.append(seed)
 
        # Persist
        with open(CACHE_PATH, "w") as f:
            json.dump(apps, f, indent=2)
 
        return apps
    
    def _crawl_odata(self) -> List[Dict[str,Any]]:
        apps = []
        skip = 0
        top = 100
        headers = {"Accept": "application/json"}

        for page in range(self.max_pages):
            url = f"{FIORI_ODATA_BASE}?$format=json&$top={top}&$skip={skip}"

            try:
                resp = requests.get(url,headers=headers,timeout=15)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("d",{}).get("results",[])

                if not results:
                    break
                
                #fill in the information we need from the apps metadata
                for r in results:
                    apps.append(
                        {
                            "app_id": r.get("AppId", ""),
                            "title": r.get("Title", ""),
                            "description": self._clean(
                                r.get("ShortDescription", "")
                                + " "
                                + r.get("DetailedDescription", "")
                            ),
                            "app_type": r.get("AppType", ""),
                            "product": r.get("Product", ""),
                            "business_role": r.get("BusinessRole", ""),
                            "tags": self._extract_tags(r),
                        }
                    )
                
                skip += top
                if len(results) < top:
                    break
                time.sleep(0.3)
            except requests.RequestException as e:
                print(f"Page {page} error: {e}")
                break
        return apps
                
    @staticmethod 
    def _clean(text : str) -> str:
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    
    @staticmethod
    def _extract_tags(record: dict) -> List[str]:
        tags = []
        for field in ("Tags", "Keywords", "BusinessDomain", "SAPComponent"):
            val = record.get(field, "")
            if val:
                tags.extend([t.strip() for t in re.split(r"[,;|]", val) if t.strip()])
        return tags