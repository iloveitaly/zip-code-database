#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "timezonefinder",
# ]
# ///
import subprocess
import json
import os
import tempfile
from collections import Counter

# Optimized script to approximate missing location and timezone data
# Uses a temporary table and JOIN to update the main table efficiently in dolt.

def run_dolt_sql(query, format="json"):
    result = subprocess.run(
        ["dolt", "sql", "-q", query, "-r", format],
        capture_output=True,
        text=True,
        check=True
    )
    if format == "json" and result.stdout.strip():
        return json.loads(result.stdout)["rows"]
    return result.stdout

def main():
    print("Calculating SCF-based averages for location and city names...")
    
    geo_data = run_dolt_sql("""
        SELECT substr(zip, 1, 3) as scf, lat, lng, city 
        FROM zip_codes 
        WHERE lat IS NOT NULL AND lng IS NOT NULL AND city IS NOT NULL
    """)
    
    scf_data = {}
    for row in geo_data:
        scf = row['scf']
        if scf not in scf_data:
            scf_data[scf] = {'lats': [], 'lngs': [], 'cities': Counter()}
        scf_data[scf]['lats'].append(float(row['lat']))
        scf_data[scf]['lngs'].append(float(row['lng']))
        scf_data[scf]['cities'][row['city']] += 1

    scf_averages = {}
    for scf, data in scf_data.items():
        scf_averages[scf] = {
            'lat': sum(data['lats']) / len(data['lats']),
            'lng': sum(data['lngs']) / len(data['lngs']),
            'city': data['cities'].most_common(1)[0][0]
        }

    print("Preparing batch update for non-geographic ZIP codes...")
    missing_zips = run_dolt_sql("SELECT zip FROM zip_codes WHERE lat IS NULL")
    
    updates = []
    for row in missing_zips:
        zip_code = row['zip']
        scf = zip_code[:3]
        if scf in scf_averages:
            avg = scf_averages[scf]
            updates.append({
                'zip': zip_code,
                'lat': avg['lat'],
                'lng': avg['lng'],
                'city': avg['city']
            })

    if updates:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("zip,lat,lng,city\n")
            for up in updates:
                city = up['city'].replace('"', '""')
                f.write(f"{up['zip']},{up['lat']},{up['lng']},\"{city}\"\n")
            temp_path = f.name

        print(f"Applying healing for {len(updates)} records...")
        # Import to temp table
        subprocess.run(["dolt", "table", "import", "-c", "-f", "--pk", "zip", "temp_healed", temp_path], check=True)
        
        # Join update
        run_dolt_sql("""
            UPDATE zip_codes z
            JOIN temp_healed h ON z.zip = h.zip
            SET z.lat = h.lat, z.lng = h.lng, z.city = h.city
        """, format="csv")
        
        # Cleanup
        run_dolt_sql("DROP TABLE temp_healed", format="csv")
        os.remove(temp_path)

    print("Updating missing timezones...")
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        
        needs_tz = run_dolt_sql("SELECT zip, lat, lng FROM zip_codes WHERE timezone IS NULL AND lat IS NOT NULL")
        tz_updates = []
        for row in needs_tz:
            tz = tf.timezone_at(lat=float(row['lat']), lng=float(row['lng']))
            if tz:
                tz_updates.append({'zip': row['zip'], 'timezone': tz})
        
        if tz_updates:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
                f.write("zip,timezone\n")
                for up in tz_updates:
                    f.write(f"{up['zip']},{up['timezone']}\n")
                temp_path = f.name
            
            subprocess.run(["dolt", "table", "import", "-c", "-f", "--pk", "zip", "temp_tz", temp_path], check=True)
            run_dolt_sql("""
                UPDATE zip_codes z
                JOIN temp_tz t ON z.zip = t.zip
                SET z.timezone = t.timezone
            """, format="csv")
            run_dolt_sql("DROP TABLE temp_tz", format="csv")
            os.remove(temp_path)
            print(f"Updated {len(tz_updates)} timezones.")
    except ImportError:
        print("Warning: timezonefinder not installed. Skipping timezone healing.")

    print("Done.")

if __name__ == "__main__":
    main()
