"""Read the published CMS survey data and prepare one row per hospital."""
from pathlib import Path

import pandas as pd

FOLDER = Path(__file__).resolve().parent

# Translate the eight CMS measure codes into readable column names.
MEASURES = {
    "H_HSP_RATING_9_10": "OverallRatingPct",
    "H_RECMND_DY": "RecommendPct",
    "H_COMP_1_A_P": "NurseCommunicationPct",
    "H_COMP_2_A_P": "DoctorCommunicationPct",
    "H_COMP_5_A_P": "MedicineCommunicationPct",
    "H_COMP_6_Y_P": "DischargeInformationPct",
    "H_CLEAN_HSP_A_P": "CleanlinessPct",
    "H_QUIET_HSP_A_P": "QuietnessPct",
}


def main():
    # 1. Read the CSV into a dataframe: a table in Python memory.
    # Read IDs as text so an ID such as 010001 keeps its first zero.
    survey = pd.read_csv(FOLDER / "data/hcahps_raw.csv", dtype=str, keep_default_na=False)

    # 2. Check the table before calculating anything.
    if survey.duplicated(["Facility ID", "HCAHPS Measure ID"]).any():
        raise ValueError("Repeated hospital/measure rows need review.")
    if len(survey[["Start Date", "End Date"]].drop_duplicates()) != 1:
        raise ValueError("Use one reporting period for this project.")
    if not survey["HCAHPS Measure ID"].isin(MEASURES).all():
        raise ValueError("The file contains an unexpected survey measure.")

    # 3. Convert published percentages to numbers. Text such as Not Available
    # becomes missing. Keep it missing: it is not a zero score.
    scores = pd.to_numeric(survey["HCAHPS Answer Percent"], errors="coerce")
    if (scores.notna() & ~scores.between(0, 100)).any():
        raise ValueError("A percentage is outside the expected 0-100 range.")
    survey["Score"] = scores / 100  # Power BI displays 0.72 as 72%.
    survey["Measure"] = survey["HCAHPS Measure ID"].map(MEASURES)

    # 4. Pivot: turn eight measure rows into eight columns on one hospital row.
    score_table = survey.pivot(index="Facility ID", columns="Measure", values="Score")

    # 5. Hospital information repeats for every measure. Take it once from
    # the overall-rating row, then join the eight score columns to it.
    overall = survey[survey["HCAHPS Measure ID"] == "H_HSP_RATING_9_10"]
    overall = overall.set_index("Facility ID")
    columns = {
        "Facility Name": "HospitalName", "City/Town": "City", "State": "State",
        "Number of Completed Surveys": "CompletedSurveysText",
        "HCAHPS Answer Percent Footnote": "OverallRatingFootnote",
        "Number of Completed Surveys Footnote": "CompletedSurveysFootnote",
        "Survey Response Rate Percent Footnote": "ResponseRateFootnote",
        "Start Date": "PeriodStart", "End Date": "PeriodEnd",
    }
    hospitals = overall[list(columns)].rename(columns=columns).copy()
    hospitals["CompletedSurveys"] = pd.to_numeric(hospitals["CompletedSurveysText"], errors="coerce")
    hospitals["ResponseRatePct"] = pd.to_numeric(overall["Survey Response Rate Percent"], errors="coerce") / 100
    hospitals = hospitals.join(score_table).reset_index().rename(columns={"Facility ID": "HospitalID"})
    hospitals["ScoreAvailability"] = hospitals["OverallRatingPct"].notna().map({True: "Reported", False: "Unavailable"})
    for column in ["PeriodStart", "PeriodEnd"]:
        hospitals[column] = pd.to_datetime(hospitals[column], format="%m/%d/%Y").dt.strftime("%Y-%m-%d")
    hospitals = hospitals.sort_values("HospitalID").reset_index(drop=True)

    # 6. Save the cleaned table and print numbers to compare with Power BI.
    hospitals.to_csv(FOLDER / "data/hospital_summary.csv", index=False)
    print(f"Hospitals: {len(hospitals):,}")
    print(f"Hospitals with overall score: {hospitals['OverallRatingPct'].count():,}")
    print(f"Mean overall 9-or-10 score: {hospitals['OverallRatingPct'].mean():.1%}")
    print(f"Mean definitely-recommend score: {hospitals['RecommendPct'].mean():.1%}")
    print(f"Mean hospital response rate: {hospitals['ResponseRatePct'].mean():.1%}")
    print("Saved data/hospital_summary.csv")


if __name__ == "__main__":
    main()
