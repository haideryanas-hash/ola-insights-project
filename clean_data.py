"""
Ola Ride Insights - data cleaning & feature engineering.

Usage:  python clean_data.py OLA_DataSet.xlsx          -> writes ola_clean.csv
Design rule: NO rows are dropped and NO values are invented. Every change is logged.
"""
import sys
import numpy as np
import pandas as pd

SRC = sys.argv[1] if len(sys.argv) > 1 else "OLA_DataSet.xlsx"
OUT = "ola_clean.csv.gz"
log = []


def note(step, detail):
    log.append((step, detail))
    print(f"[{step}] {detail}")


df = pd.read_excel(SRC, sheet_name="July")
raw_rows = len(df)
note("load", f"{raw_rows:,} rows x {df.shape[1]} columns from sheet 'July'")

# 1. integrity checks ---------------------------------------------------------
assert df.Booking_ID.is_unique, "duplicate Booking_ID found"
note("duplicates", "0 duplicate Booking_IDs, 0 fully duplicated rows - nothing to remove")

# 2. column names -------------------------------------------------------------
df = df.rename(columns={
    "Vehicle Images": "Vehicle_Image_URL",                  # space in header
    "Canceled_Rides_by_Customer": "Customer_Cancel_Reason", # holds a reason, not a count
    "Canceled_Rides_by_Driver": "Driver_Cancel_Reason",
    "Driver_Ratings": "Driver_Rating",
})
note("rename", "Vehicle Images->Vehicle_Image_URL, Canceled_Rides_by_* -> *_Cancel_Reason, Driver_Ratings->Driver_Rating")

# 3. date/time ----------------------------------------------------------------
# 'Date' already carries the clock time; 'Time' is a Python time object (stored as text in CSV).
t = pd.to_datetime(df["Time"].astype(str), format="%H:%M:%S")
assert ((df.Date.dt.hour == t.dt.hour) & (df.Date.dt.minute == t.dt.minute)).all()
df["Booking_Datetime"] = df["Date"]
df["Date"] = df["Booking_Datetime"].dt.normalize()
df["Time"] = df["Booking_Datetime"].dt.strftime("%H:%M")
note("datetime", "Date column held date+time, matching the Time column on 100% of rows -> split into Date, Time, Booking_Datetime")

# 4. categorical standardisation ------------------------------------------------
df["Vehicle_Type"] = df["Vehicle_Type"].replace({"eBike": "E-Bike"})
note("standardise", "Vehicle_Type 'eBike' -> 'E-Bike' (matches dashboard slides)")

# 5. structural nulls -----------------------------------------------------------
# Blanks are NOT missing data: a cancelled ride has no payment, rating or incomplete flag.
structural = ["Customer_Cancel_Reason", "Driver_Cancel_Reason", "Incomplete_Rides",
              "Incomplete_Rides_Reason", "Payment_Method"]
for c in structural:
    n = df[c].isna().sum()
    df[c] = df[c].fillna("Not Applicable")
    note("structural-null", f"{c}: {n:,} blanks -> 'Not Applicable' (ride never reached that stage)")
for c in ["V_TAT", "C_TAT", "Driver_Rating", "Customer_Rating"]:
    note("structural-null", f"{c}: {df[c].isna().sum():,} blanks kept as NaN (only Success rides have it; imputing would fabricate data)")

# 6. derived features -----------------------------------------------------------
dt = df["Booking_Datetime"]
df["Hour"] = dt.dt.hour
df["Day_Name"] = dt.dt.day_name()
df["Day_of_Week"] = dt.dt.dayofweek            # Mon=0
df["Is_Weekend"] = df["Day_of_Week"] >= 5
df["Week"] = ((dt.dt.day - 1) // 7 + 1)        # week-of-month 1..5
df["Time_Band"] = pd.cut(df["Hour"], [-1, 4, 8, 11, 16, 20, 23],
                         labels=["Late Night (0-4)", "Early Morning (5-8)", "Late Morning (9-11)",
                                 "Afternoon (12-16)", "Evening Peak (17-20)", "Night (21-23)"]).astype(str)

df["Is_Success"] = df["Booking_Status"].eq("Success")
df["Is_Incomplete"] = df["Incomplete_Rides"].eq("Yes")
df["Is_Fully_Completed"] = df["Is_Success"] & ~df["Is_Incomplete"]
df["Cancelled_By"] = df["Booking_Status"].map({"Canceled by Customer": "Customer",
                                               "Canceled by Driver": "Driver"}).fillna("Nobody")
df["Failure_Type"] = np.where(df["Is_Success"], "None", df["Booking_Status"])
df["Revenue_Realised"] = np.where(df["Is_Success"], df["Booking_Value"], 0)
df["Revenue_Lost"] = np.where(df["Is_Success"], 0, df["Booking_Value"])
df["Route"] = df["Pickup_Location"] + " -> " + df["Drop_Location"]
df["Rating_Gap"] = df["Driver_Rating"] - df["Customer_Rating"]
df["Fare_per_km"] = np.where(df["Is_Success"], df["Booking_Value"] / df["Ride_Distance"].replace(0, np.nan), np.nan)
df["Distance_Band"] = pd.cut(df["Ride_Distance"], [-1, 0, 5, 15, 30, 50],
                             labels=["No ride (0 km)", "Short (1-5)", "Medium (6-15)", "Long (16-30)", "Very long (31-50)"]).astype(str)
df["Fare_Band"] = pd.cut(df["Booking_Value"], [0, 250, 500, 1000, 2000, 3000],
                         labels=["<=250", "251-500", "501-1000", "1001-2000", "2001-3000"]).astype(str)
note("features", "added Hour, Day_Name, Day_of_Week, Is_Weekend, Week, Time_Band, Is_Success, Is_Incomplete, Is_Fully_Completed, "
                 "Cancelled_By, Failure_Type, Revenue_Realised, Revenue_Lost, Route, Rating_Gap, Fare_per_km, Distance_Band, Fare_Band")

# 7. anomaly flags (flagged, never deleted) -----------------------------------------
df["Flag_Same_Pickup_Drop"] = df["Pickup_Location"].eq(df["Drop_Location"])
ok = df["Fare_per_km"].dropna()
hi = ok.quantile(0.99)
df["Flag_Extreme_Fare_per_km"] = df["Fare_per_km"] > hi
df["Flag_Short_Ride_High_Fare"] = df["Is_Success"] & (df["Ride_Distance"] <= 3) & (df["Booking_Value"] >= 1000)
df["Anomaly_Score"] = (df["Flag_Same_Pickup_Drop"].astype(int) + df["Flag_Extreme_Fare_per_km"].astype(int)
                       + df["Flag_Short_Ride_High_Fare"].astype(int))
note("anomalies", f"Same pickup & drop: {df.Flag_Same_Pickup_Drop.sum():,} | fare/km above P99 (Rs {hi:,.0f}/km): {df.Flag_Extreme_Fare_per_km.sum():,} "
                  f"| <=3 km but >=Rs1000: {df.Flag_Short_Ride_High_Fare.sum():,} - all kept, flagged for review")

# 8. validation ---------------------------------------------------------------------
assert len(df) == raw_rows
assert df.loc[~df.Is_Success, "Payment_Method"].eq("Not Applicable").all()
assert df.loc[df.Is_Success, ["V_TAT", "C_TAT", "Driver_Rating", "Customer_Rating"]].notna().all().all()
assert df.loc[~df.Is_Success, "Ride_Distance"].eq(0).all()
note("validate", "row count unchanged; all consistency rules pass (status vs payment/ratings/TAT/distance)")

df.drop(columns=["Vehicle_Image_URL"]).to_csv(OUT, index=False)
note("save", f"{OUT}: {len(df):,} rows x {df.shape[1]-1} columns (image URL column dropped - one URL per vehicle type, lives in the app)")
pd.DataFrame(log, columns=["step", "detail"]).to_csv("cleaning_log.csv", index=False)
