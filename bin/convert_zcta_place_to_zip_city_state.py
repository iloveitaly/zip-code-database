#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "structlog-config"
# ]
# ///

import csv
import sys

import click
import structlog
import structlog_config

# Configure logging using structlog_config
structlog_config.configure_logger()


def load_place_gazetteer(path):
    """
    Loads the Place Gazetteer into a lookup keyed by (STATEFP, PLACEFP) with values {name, state_abbr}.
    The 2024 Gazetteer has a header with fields like: GEOID,NAME,ALAND,AWATER,ALAND_SQMI,AWATER_SQMI,INTPTLAT,INTPTLONG, ... STATE, USPS.
    For places, GEOID is statefp + placefp (2 + 5 digits). We'll derive statefp/placefp from GEOID when possible.
    """
    lookup = {}

    with open(path, "r", newline="", encoding="utf-8") as f:
        # The file is tab-delimited
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            geoid = (row.get("GEOID") or row.get("GEOID20") or "").strip()
            name = (row.get("NAME") or row.get("NAME20") or "").strip()
            state_abbr = (
                row.get("USPS") or row.get("STUSAB") or row.get("STATE") or ""
            ).strip()

            if not geoid or len(geoid) < 7:
                continue
            statefp = geoid[:2]
            placefp = geoid[2:7]
            lookup[(statefp, placefp)] = {"name": name, "state": state_abbr}

    return lookup


def load_rel_file(path):
    """
    Loads the 2020 ZCTA->Place relationship file.
    This is tab-delimited with headers described at Census: tab20_zcta520_place20_natl.txt
    Expected columns include at least: ZCTA5, STATEFP (state), PLACEFP (place), ZPOP (pop in overlap), ZAREALAND / AREALAND (area overlap) or their 2020 names.
    We'll rely on header names commonly used in these files.
    """
    rows = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        # Relationship file is pipe-delimited
        reader = csv.DictReader(f, delimiter="|")
        for row in reader:
            geoid_zcta = (row.get("GEOID_ZCTA5_20") or "").strip()
            geoid_place = (row.get("GEOID_PLACE_20") or "").strip()

            # Area overlap for the intersection part
            zarea = row.get("AREALAND_PART")
            try:
                zarea_val = float(zarea) if zarea not in (None, "") else 0.0
            except ValueError:
                zarea_val = 0.0

            if not (geoid_zcta and geoid_place and len(geoid_place) >= 7):
                continue

            zcta = geoid_zcta[-5:]  # ensure 5-digit ZCTA
            statefp = geoid_place[:2]
            placefp = geoid_place[2:7]

            rows.append(
                {
                    "zcta": zcta,
                    "statefp": statefp,
                    "placefp": placefp,
                    "zpop": 0.0,  # not available in this file
                    "zarea": zarea_val,
                }
            )
    return rows


def select_best_place_per_zip(rel_rows, how="max_pop"):
    """
    For each zcta, select the place with the maximum population (or area) overlap.
    Returns dict zcta -> (statefp, placefp)
    """
    best = {}
    for r in rel_rows:
        zcta = r["zcta"]
        key = "zpop" if how == "max_pop" else "zarea"
        score = r.get(key, 0.0)
        if zcta not in best or score > best[zcta]["score"]:
            best[zcta] = {
                "statefp": r["statefp"],
                "placefp": r["placefp"],
                "score": score,
            }
    return {z: (v["statefp"], v["placefp"]) for z, v in best.items()}


@click.command()
@click.option(
    "--rel-file",
    required=True,
    help="Path to tab20_zcta520_place20_natl.txt (tab-delimited)",
)
@click.option(
    "--place-gaz-file",
    required=True,
    help="Path to 2024_Gaz_place_national.txt (tab-delimited)",
)
@click.option("--out", required=True, help="Output CSV path")
@click.option(
    "--selection",
    type=click.Choice(["max_pop", "max_area"]),
    default="max_area",
    help="When a ZIP overlaps multiple places, choose the place with the maximum population share or area share (default: max_area)",
)
def main(rel_file, place_gaz_file, out, selection):
    logger = structlog.get_logger()
    logger.info(
        "Starting ZCTA to ZIP conversion",
        rel_file=rel_file,
        place_gaz_file=place_gaz_file,
        output=out,
        selection=selection,
    )

    place_lookup = load_place_gazetteer(place_gaz_file)
    logger.info("Loaded place gazetteer", places_count=len(place_lookup))

    rel_rows = load_rel_file(rel_file)
    logger.info("Loaded relationship file", relations_count=len(rel_rows))

    selections = select_best_place_per_zip(rel_rows, how=selection)
    logger.info("Selected best places for ZIPs", selections_count=len(selections))

    # Helpers to split NAME into base and type suffix
    multi_word_types = [
        "city and borough",
        "charter township",
        "metropolitan government",
        "zona urbana",
        "census designated place",
        "consolidated government",
        "consolidated city",
        "urban county",
        "barrio-pueblo",
        "city and county",
    ]
    single_word_types = [
        "city",
        "town",
        "village",
        "borough",
        "CDP",
        "plantation",
        "township",
        "municipality",
        "precinct",
        "district",
        "comunidad",
    ]

    def split_name_and_type(full_name: str):
        s = full_name.strip()
        if not s:
            return s, ""
        # Check multi-word phrases first (longest first)
        for phrase in sorted(multi_word_types, key=len, reverse=True):
            if s.endswith(" " + phrase):
                base = s[: -len(phrase)].rstrip()
                # remove possible trailing punctuation
                base = base.rstrip(", ")
                return base, phrase
        # Then single-word types
        for t in single_word_types:
            if s.endswith(" " + t):
                base = s[: -len(t)].rstrip()
                base = base.rstrip(", ")
                return base, t
        return s, ""

    # Produce output rows
    out_rows = []
    missing = 0
    for zcta, (statefp, placefp) in selections.items():
        info = place_lookup.get((statefp, placefp))
        if not info:
            missing += 1
            logger.warning(
                "Missing place info for ZIP", zip=zcta, statefp=statefp, placefp=placefp
            )
            continue
        base_name, place_type = split_name_and_type(info["name"])
        out_rows.append(
            {
                "zip": zcta,
                "city": base_name,
                "state": info["state"],
                "type": place_type,
            }
        )

    logger.info(
        "Generated output rows", total_rows=len(out_rows), missing_count=missing
    )

    # Sort by zip for determinism
    out_rows.sort(key=lambda r: r["zip"])

    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["zip", "city", "state", "type"])
        writer.writeheader()
        writer.writerows(out_rows)

    logger.info(
        "Successfully wrote output file", output_file=out, rows_written=len(out_rows)
    )

    if missing:
        logger.warning(
            "Some selections missing in place gazetteer", missing_count=missing
        )


if __name__ == "__main__":
    main()
