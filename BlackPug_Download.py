import json
import os
import sys
import numpy as np
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from playwright.sync_api import sync_playwright

def upload_to_drive(local_file_path: str, drive_folder_id: str):
    """Uploads file using real user OAuth credentials to bypass service account quota limits."""
    client_id = os.environ.get("GDRIVE_CLIENT_ID")
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET")
    refresh_token = os.environ.get("GDRIVE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        print("Error: Missing OAuth credentials in environment variables.")
        sys.exit(1)

    # Reconstruct credentials from refresh token
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )

    # Refresh token if expired
    if creds.expired or not creds.valid:
        creds.refresh(Request())

    file_name = os.path.basename(local_file_path)

    file_metadata = {
        "name": file_name,
        "parents": [drive_folder_id]  # Targets the specific Drive folder ID
    }

    media = MediaFileUpload(local_file_path, mimetype="text/csv")

    print(f"Uploading {file_name} to Google Drive folder ({drive_folder_id})...")
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"File uploaded successfully! Drive File ID: {uploaded_file.get('id')}")


def transform_blackpug_csv(input_file: str, output_file: str):
    print(f"Starting data transformation on {input_file}...")

    df = pd.read_csv(input_file, encoding="utf-8-sig")

    # 1. Remove rows where Registrant Type = "Registration Contact"
    if "Registrant Type" in df.columns:
        initial_count = len(df)
        df = df[df["Registrant Type"] != "Registration Contact"].copy()
        print(f"Filtered out {initial_count - len(df)} 'Registration Contact' rows.")

    # 2. Rename Fields
    rename_mapping = {
        "Cost": "Paid Amount",
        "Booking Date": "Registered Date",
        "Registration Number": "Receipt Number",
    }
    df.rename(columns=rename_mapping, inplace=True)

    # 3. Validate Member ID Column
    if "Member ID" in df.columns:
        member_ids = df["Member ID"].astype(str).str.strip()
        is_numeric = member_ids.str.isdigit()
        valid_length = member_ids.str.len().between(7, 9)
        not_dummy = ~member_ids.isin(["1234567", "12345678", "123456789"])
        valid_mask = is_numeric & valid_length & not_dummy
        df["Member ID"] = np.where(valid_mask, member_ids, "")

    # 4. Create Role Column based on conditional logic
    def determine_role(row):
        reg_type = str(row.get("Registrant Type", "")).strip()
        brotherhood_plan = str(
            row.get("Are you planning on completing your Brotherhood membership", "")
        ).strip()
        induction_crew = str(
            row.get("Do you wish to participate in a member crew for the New Induction Experience", "")
        ).strip()

        if reg_type == "New Member Induction Experience":
            return "Ordeal New Member"
        elif reg_type == "Brotherhood Candidate":
            return "Brotherhood Candidate"
        elif reg_type in ["Paddle Pass", "Takhone OA Member"]:
            if brotherhood_plan == "Yes":
                return "Brotherhood Candidate"
            elif induction_crew == "Yes":
                return "Induction Experience"
            else:
                return ""
        elif reg_type in ["Non-Takhone Member - Adult", "Non-Takhone Member - Youth"]:
            return "Non-member"
        return ""

    df["Role"] = df.apply(determine_role, axis=1)

    # 5. Create Static & Derived Columns
    df["Paid In Full"] = True
    df["Payment Method"] = "Blackpug - Online"
    df["Paid Date"] = df["Registered Date"] if "Registered Date" in df.columns else ""

    # Export clean CSV
    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"Data successfully transformed and written to: {output_file}")


def run():
    username = os.environ.get("BLACKPUG_USERNAME")
    password = os.environ.get("BLACKPUG_PASSWORD")
    event_id = os.environ.get("BLACKPUG_EVENTID")
    drive_folder_id = os.environ.get("DRIVE_FOLDER_ID")

    if not username or not password or not event_id or not drive_folder_id:
        print("Error: Missing required environment variables (BLACKPUG_USERNAME, BLACKPUG_PASSWORD, BLACKPUG_EVENTID, or DRIVE_FOLDER_ID).")
        sys.exit(1)

    target_url = f"https://admin.247scouting.com/admin_SES.php?system=2&eid={event_id}&view=reporting"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Navigating to login page...")
        page.goto("https://247scouting.com/Login")

        page.fill('input[name="UserID"]', username)
        page.fill('input[name="password247Scouting"]', password)

        page.click('input[type="submit"]')
        page.wait_for_load_state("networkidle")

        print("Successfully logged in! Navigating to reporting page...")
        page.goto(target_url)
        page.wait_for_load_state("networkidle")

        # Trigger report popup
        page.evaluate(
            f"getSelectedReportParam('BSA456', 698, 'Event_Operations', 'Event+Data+Dump', '{event_id}', ' ', 1);"
        )
        page.wait_for_selector(".modal-content, .ui-dialog", state="visible")

        # Select options
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

        # File naming
        raw_download_path = f"raw_event_{event_id}_dump.csv"
        transformed_download_path = f"transformed_event_{event_id}_dump.csv"

        with page.expect_download() as download_info:
            page.click("button:has-text('Preview Report'), input[type='submit'][value='Preview Report']")

        download = download_info.value
        download.save_as(raw_download_path)
        print(f"Raw report saved locally: {raw_download_path}")

        browser.close()

    # Step 1: Transform data locally
    transform_blackpug_csv(raw_download_path, transformed_download_path)

    # Step 2: Upload transformed CSV to Google Drive folder
    upload_to_drive(transformed_download_path, drive_folder_id)


if __name__ == "__main__":
    run()