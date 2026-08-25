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

        browser.close()

if __name__ == "__main__":
    run()