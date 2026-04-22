#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "structlog-config"
# ]
# ///

import csv
import click
import structlog
import structlog_config

# Configure logging using structlog_config
structlog_config.configure_logger()

def load_rel_file(path):
    """
    Loads the 2020 ZCTA->County relationship file.
    This is pipe-delimited with headers: tab20_zcta520_county20_natl.txt
    Expected columns: GEOID_ZCTA5_20, GEOID_COUNTY_20, NAMELSAD_COUNTY_20, AREALAND_PART, etc.
    """
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            zcta = (row.get("GEOID_ZCTA5_20") or "").strip()
            county_name = (row.get("NAMELSAD_COUNTY_20") or "").strip()
            arealand_part = row.get("AREALAND_PART")
            
            try:
                area_val = float(arealand_part) if arealand_part not in (None, "") else 0.0
            except ValueError:
                area_val = 0.0

            if not (zcta and county_name):
                continue

            rows.append({
                "zcta": zcta,
                "county": county_name,
                "area": area_val
            })
    return rows

def select_best_county_per_zip(rel_rows):
    """
    For each zcta, select the county with the maximum land area overlap.
    Returns dict zcta -> county_name
    """
    best = {}
    for r in rel_rows:
        zcta = r["zcta"]
        score = r["area"]
        if zcta not in best or score > best[zcta]["score"]:
            best[zcta] = {
                "county": r["county"],
                "score": score,
            }
    return {z: v["county"] for z, v in best.items()}

@click.command()
@click.option(
    "--rel-file",
    required=True,
    help="Path to tab20_zcta520_county20_natl.txt (pipe-delimited)",
)
@click.option("--out", required=True, help="Output CSV path")
def main(rel_file, out):
    logger = structlog.get_logger()
    logger.info("Starting ZCTA to County conversion", rel_file=rel_file, output=out)

    rel_rows = load_rel_file(rel_file)
    logger.info("Loaded relationship file", relations_count=len(rel_rows))

    selections = select_best_county_per_zip(rel_rows)
    logger.info("Selected best counties for ZIPs", selections_count=len(selections))

    # Produce output rows
    out_rows = [{"zip": zcta, "county": county} for zcta, county in selections.items()]

    # Sort by zip for determinism
    out_rows.sort(key=lambda r: r["zip"])

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["zip", "county"])
        writer.writeheader()
        writer.writerows(out_rows)

    logger.info("Successfully wrote output file", output_file=out, rows_written=len(out_rows))

if __name__ == "__main__":
    main()
