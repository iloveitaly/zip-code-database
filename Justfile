download-zipcode-population:
  # manually download the file
  open "https://data.census.gov/table?q=B01003:+TOTAL+POPULATION&g=010XX00US$8600000"

  # then, after downloading, run this command
  python clean_zip_data.py

db-open:
  open "mysql://root@localhost:3306"