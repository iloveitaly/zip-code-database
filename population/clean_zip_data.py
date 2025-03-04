import csv
import re
import os

# Get the current script directory
script_dir = os.path.dirname(os.path.abspath(__file__))

# Define paths relative to the script location
input_file = os.path.join(script_dir, "data", "raw_zip_code_with_population.csv")
output_file = os.path.join(script_dir, "data", "zip_code_with_population.csv")

# Create output directory if it doesn't exist
os.makedirs(os.path.dirname(output_file), exist_ok=True)


# Extract zip code from "ZCTA5 #####" format
def extract_zip_code(name):
    match = re.search(r"ZCTA5 (\d{5})", name)
    if match:
        return match.group(1)
    return None


# Process the CSV
with open(input_file, "r") as infile, open(output_file, "w", newline="") as outfile:
    csv_reader = csv.reader(infile)
    csv_writer = csv.writer(outfile)

    # Skip the first two rows (headers)
    next(csv_reader)
    next(csv_reader)

    # Write the new header
    csv_writer.writerow(["zip", "population", "margin_of_error"])

    # Process each row
    for row in csv_reader:
        if len(row) >= 4:  # Ensure we have enough columns
            name = row[1]
            population = row[2]
            margin_of_error = row[3]

            zip_code = extract_zip_code(name)

            if zip_code:
                # Replace "*****" with empty string for margin_of_error
                if margin_of_error == "*****":
                    margin_of_error = ""

                csv_writer.writerow([zip_code, population, margin_of_error])

print(f"Processed file saved to {output_file}")
