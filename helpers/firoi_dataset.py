from pathlib import Path
from playwright.sync_api import sync_playwright


class FioriDatasetManager:
    """
    Handles SAP Fiori dataset lifecycle:
      - Check if dataset exists
      - Download via browser automation
      - Force refresh
    """

    def __init__(self, download_path: str = "data/fiori_apps.xlsx"):
        self.download_path = Path(download_path)
        self.download_path.parent.mkdir(parents=True, exist_ok=True)

    def dataset_exists(self) -> bool:
        return self.download_path.exists()

    def ensure_dataset(self):
        """
        Ensure dataset exists (download if missing)
        """
        if self.dataset_exists():
            print(f"Dataset already exists at {self.download_path}")
        else:
            print("Dataset not found. Downloading...")
            self.download()

    def refresh_dataset(self):
        """
        Force re-download dataset
        """
        print("Refreshing dataset...")
        self.download()

    def download(self):
        """
        Automates browser to download SAP Fiori Excel
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            print("Opening SAP Fiori List View...")

            page.goto(
                "https://fioriappslibrary.hana.ondemand.com/sap/fix/externalViewer/#/ListView",
                timeout=60000
            )
            
            try:
                print("Handling cookie popup...")
                page.locator("#actionSavePreferences").click(timeout=5000)
                print("Accepted cookies")
            except:
                print("No cookie popup found")

            # wait for UI load
            page.wait_for_load_state("networkidle")
            
            page.locator("#sap-ui-blocklayer-popup").wait_for(state="hidden", timeout=30000)
            # page.wait_for_timeout(5000)

            print("Triggering download...")

            with page.expect_download() as download_info:
                page.get_by_title("Download Excel").click()

            download = download_info.value

            print(f"Saving to {self.download_path}...")
            download.save_as(str(self.download_path))

            print("Download complete!")

            browser.close()