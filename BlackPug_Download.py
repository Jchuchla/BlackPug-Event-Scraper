import os
import sys
from playwright.sync_api import sync_playwright

def run():
    username = os.environ.get("BLACKPUG_USERNAME")
    password = os.environ.get("BLACKPUG_PASSWORD")
    event_id = os.environ.get("BLACKPUG_EVENTID")

    if not username or not password or not event_id:
        print("Error: Missing required environment variables (USERNAME, PASSWORD, or EVENTID).")
        sys.exit(1)
        
    # Construct the target reporting URL dynamically
    target_url = f"https://admin.247scouting.com/admin_SES.php?system=2&eid={event_id}&view=reporting"

    with sync_playwright() as p:
        # Launch headless browser (default is headless=True)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to login page...")
        page.goto("https://247scouting.com/Login")

        # Fill credentials using locators
        page.fill('input[name="UserID"]', username)
        page.fill('input[name="password247Scouting"]', password)

        # Click submit and wait for navigation
        page.click('input[type="submit"]')
        page.wait_for_load_state("networkidle")

        print("Successfully logged in! Current URL:", page.url)

        # Perform your post-login operations (e.g., scrape, download, export)
        
        print("Navigating to event reporting page...")
        print(f"Target URL: {target_url}")
        
        # Navigate directly to the constructed event report URL
        page.goto(target_url)
        page.wait_for_load_state("networkidle")
        
        print("Successfully reached reporting page! Current URL:", page.url)

        # 1. Trigger the popup (via click or JS evaluation)
        page.evaluate(
            f"getSelectedReportParam('BSA456', 698, 'Event_Operations', 'Event+Data+Dump', '{event_id}', ' ', 1);"
        )

        # 2. Wait for the modal/popup element to appear on screen
        # Replace '.modal' or '#reportModal' with the actual container class/ID if known
        page.wait_for_selector(".modal-content, .ui-dialog", state="visible")

        # 3. Intersect with optional fields/radio buttons inside the popup (Examples):
        # If there's a file format dropdown or radio button (e.g., selecting CSV):
        # Selects options by visible text
        page.select_option(
            "#SES_REGISTRANT_ID_MULTI",
            label=[
                "Brotherhood Candidate",
                "New Member Induction Experience",
                "Non-Takhone Member - Adult",
                "Non-Takhone Member - Youth",
                "Paddle Pass Member",
                "Takhone OA Member"
            ]
        )
        page.check("#FLAG1_ON_OFFEvent_Operations")
        page.check("#FLAG3_ON_OFFEvent_Operations")

        # 4. Listen for the download event when clicking the modal's final submit/export button
        with page.expect_download() as download_info:
            # Target the modal submit button by text (e.g., 'Run Report', 'Export', 'Download', 'OK')
            page.click("button:has-text('Preview Report'), input[type='submit'][value='Preview Report']")

        download = download_info.value

        # 5. Save the resulting file locally inside the runner
        download_path = f"event_{event_id}_dump.csv"
        download.save_as(download_path)
        print(f"File successfully saved to: {download_path}")

        browser.close()

if __name__ == "__main__":
    run()