# Zip Code Database Based on Census Data

I wanted a database of all zip codes in the country, with their lat & long. And I wanted it to be easy to import and easy to update.

[I found this gist](https://gist.github.com/abatko/ee7b24db82a6f50cfce02afafa1dfd1e), which was great and did most of the hard work, but I wanted to:

1. Put the scripts in a single location
2. Have the database in dolthub for easy querying, updating, and sharing
3. Be able to easily update the zip code data

## Formats

* JSON
* CSV
* CSV with PK ID
* SQL (mysql dialect)

## Latest Zipcode Data

Where did this data come from?

* <https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>
* "ZIP Code Tabulation Areas"

This is documented in the `bin/download-gazetteer` script.

## DoltHub

The data is available on Dolthub here:

<https://www.dolthub.com/repositories/iloveitaly/zip_codes_with_lat_and_lng>

## Updating

1. Update download URL in `bin/download-gazetteer
2. Run `bin/download-gazetteer`
3. Profit