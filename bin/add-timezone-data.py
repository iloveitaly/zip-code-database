#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "timezonefinder",
#     "pandas",
# ]
# ///

import subprocess
import pandas as pd
from timezonefinder import TimezoneFinder
import os

PROJECT_ROOT = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
TEMP_COORDS = os.path.join(DATA_DIR, "temp_coords.csv")
TEMP_TIMEZONES = os.path.join(DATA_DIR, "temp_timezones.csv")
UPDATE_SQL = os.path.join(DATA_DIR, "update_timezone.sql")

print("Exporting coordinates from zip_codes table...")
subprocess.run(
    ["dolt", "sql", "-q", "SELECT zip, lat, lng FROM zip_codes", "-r", "csv"],
    stdout=open(TEMP_COORDS, "w"),
    check=True,
    cwd=PROJECT_ROOT
)

print("Calculating timezones for each zip code...")
df = pd.read_csv(TEMP_COORDS)
tf = TimezoneFinder()

def get_timezone(row):
    # Some zip codes might have 0 or missing coordinates, so handle safely
    if pd.isna(row['lat']) or pd.isna(row['lng']):
        return None
    try:
        return tf.timezone_at(lat=row['lat'], lng=row['lng'])
    except Exception:
        return None

df['timezone'] = df.apply(get_timezone, axis=1)

# Save the subset we need to a new CSV
df[['zip', 'timezone']].to_csv(TEMP_TIMEZONES, index=False)

print("Importing calculated timezones as temporary table...")
subprocess.run(
    ["dolt", "table", "import", "-c", "-f", "--pk", "zip", "temp_timezone", TEMP_TIMEZONES],
    check=True,
    cwd=PROJECT_ROOT
)

print("Updating zip_codes table with timezone data...")
sql_script = """
-- Update zip_codes with data from temp_timezone table
UPDATE zip_codes z
JOIN temp_timezone t ON z.zip = t.zip
SET z.timezone = t.timezone;

-- Drop the temporary table
DROP TABLE temp_timezone;
"""
with open(UPDATE_SQL, "w") as f:
    f.write(sql_script)

subprocess.run(["dolt", "sql", "--file", UPDATE_SQL], check=True, cwd=PROJECT_ROOT)

print("Committing timezone data updates...")
subprocess.run(["dolt", "add", "."], check=True, cwd=PROJECT_ROOT)
subprocess.run(["dolt", "commit", "-m", "Add timezone data to zip_codes table"], check=True, cwd=PROJECT_ROOT)

print("Cleaning up temporary files...")
os.remove(TEMP_COORDS)
os.remove(TEMP_TIMEZONES)
os.remove(UPDATE_SQL)

print("Successfully added timezone data to zip_codes table")
