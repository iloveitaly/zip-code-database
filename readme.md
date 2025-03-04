# Zip Code Database Based on Census Data

I wanted a database of all zip codes in the country, with their lat & long. And I wanted it to be easy to import and easy to update.

[I found this gist](https://gist.github.com/abatko/ee7b24db82a6f50cfce02afafa1dfd1e), which was great and did most of the hard work, but I wanted to:

1. Put the scripts in a single location
2. Have the database in dolthub for easy querying, updating, and sharing
3. Be able to easily update the zip code data

Later on, I wanted the population in the database as well, so I added that in.

## API

The cool thing about dolthub is you can use it as an API. Get a random zip code:

```shell
http "https://www.dolthub.com/api/v1alpha1/iloveitaly/zip_codes_with_lat_and_lng/main?q=SELECT+*%0AFROM+%60zip_codes%60%0AORDER+BY+RAND%28%29%0ALIMIT+1%3B"
```

Even better, get a random zip code by population:

```shell
https://www.dolthub.com/api/v1alpha1/iloveitaly/zip_codes_with_lat_and_lng/main?q=SELECT+*%0AFROM+%28%0A++++SELECT+*%0A++++FROM+%60zip_codes%60%0A++++ORDER+BY+%60population%60+DESC%0A++++LIMIT+100%0A%29+AS+top_100%0AORDER+BY+RAND%28%29%0ALIMIT+1%3B
```

## How this works:

1. Downlaod the latest zip code census data
2. Process

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

## TODO

- [ ] clean up the population stuff, mostly vibe-coded