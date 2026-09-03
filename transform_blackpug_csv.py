import pandas as pd
import numpy as np

def transform_blackpug_csv(input_file, output_file):
    # Load CSV (handling UTF-8 BOM if present)
    df = pd.read_csv(input_file, encoding="utf-8-sig")

    # 1. Filter out rows where Registrant Type == "Registration Contact"
    if "Registrant Type" in df.columns:
        df = df[df["Registrant Type"] != "Registration Contact"].copy()

    # 2. Rename Fields
    rename_mapping = {
        "Cost": "Paid Amount",
        "Booking Date": "Registered Date",
        "Registration Number": "Receipt Number"
    }
    df.rename(columns=rename_mapping, inplace=True)

    # 3. Validate Member ID Column
    if "Member ID" in df.columns:
        # Convert to string and clean whitespace
        member_ids = df["Member ID"].astype(str).str.strip()

        # Validation conditions: digits only AND length 7 to 9 AND not equal to invalid patterns
        is_numeric = member_ids.str.isdigit()
        valid_length = member_ids.str.len().between(7, 9)
        not_dummy = ~member_ids.isin(["1234567", "12345678", "123456789"])

        valid_mask = is_numeric & valid_length & not_dummy

        # Clear invalid Member IDs (set to empty string)
        df["Member ID"] = np.where(valid_mask, member_ids, "")

    # 4. Create Role column using conditional logic
    def determine_role(row):
        reg_type = str(row.get("Registrant Type", "")).strip()
        
        # Safe extraction of optional question fields
        brotherhood_plan = str(row.get("Are you planning on completing your Brotherhood membership", "")).strip()
        induction_crew = str(row.get("Do you wish to participate in a member crew for the New Induction Experience", "")).strip()

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

    # Copy value from Registered Date to Paid Date
    if "Registered Date" in df.columns:
        df["Paid Date"] = df["Registered Date"]
    else:
        df["Paid Date"] = ""

    # Export cleaned CSV
    df.to_csv(output_file, index=False, encoding="utf-8")
    print(f"Transformation complete. Total output rows: {len(df)}")

# Example Execution:
# transform_blackpug_csv("raw_event_report.csv", "transformed_event_report.csv")