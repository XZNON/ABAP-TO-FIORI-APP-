from playwright.sync_api import sync_playwright

def download_fiori_excel():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

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
        # wait for full load (important)
        page.wait_for_load_state("networkidle")

        page.get_by_title("Download Excel").wait_for(timeout=30000)

        print("Clicking Download...")


        with page.expect_download() as download_info:
            page.get_by_title("Download Excel").click()

        download = download_info.value

        print("Saving file...")
        download.save_as("fiori_apps.xlsx")

        print("✅ Download complete!")

        browser.close()


if __name__ == "__main__":
    download_fiori_excel()