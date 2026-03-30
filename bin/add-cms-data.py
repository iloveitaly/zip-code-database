#!/usr/bin/env python3
import sqlite3
import os
import sys

# Script to integrate CMS ZIP5 data into the zip_codes database

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "zip_codes.db")
CMS_FILE = os.path.join(PROJECT_ROOT, "data", "cms_temp", "ZIP5_DEC2025_FINAL.txt")

def main():
    if not os.path.exists(CMS_FILE):
        print(f"Error: CMS file not found at {CMS_FILE}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current max ID
    cursor.execute("SELECT MAX(id) FROM zip_codes")
    max_id = cursor.fetchone()[0] or 0

    # Get existing zips
    cursor.execute("SELECT zip FROM zip_codes")
    existing_zips = {row[0] for row in cursor.fetchall()}

    new_zips = []
    with open(CMS_FILE, "r") as f:
        for line in f:
            if len(line) < 7:
                continue
            state = line[0:2].strip()
            zip_code = line[2:7].strip()
            
            if not zip_code or not state:
                continue
                
            if zip_code not in existing_zips:
                # Basic validation: zip should be 5 digits
                if not zip_code.isdigit() or len(zip_code) != 5:
                    continue
                
                max_id += 1
                # For now, we add with NULL lat/lng/city etc.
                # We can try to approximate some of these later.
                new_zips.append((max_id, zip_code, state))
                existing_zips.add(zip_code)

    if new_zips:
        print(f"Adding {len(new_zips)} new zip codes from CMS data...")
        cursor.executemany(
            "INSERT INTO zip_codes (id, zip, state, type) VALUES (?, ?, ?, 'non-geographic')",
            new_zips
        )
        conn.commit()
        print("Done.")
    else:
        print("No new zip codes found to add.")

    conn.close()

if __name__ == "__main__":
    main()
