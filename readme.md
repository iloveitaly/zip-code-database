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

Here's an example with python:

```python
def get_random_lat_lng() -> Tuple[float, float]:
    """Fetch a random lat/lng from the dolthub API."""
    url = "https://www.dolthub.com/api/v1alpha1/iloveitaly/zip_codes_with_lat_and_lng/main"
    # pick the top 100 most populous zip codes
    params = {
        "q": """
SELECT *
FROM (
    SELECT *
    FROM `zip_codes`
    ORDER BY `population` DESC
    LIMIT 100
) AS top_100
ORDER BY RAND()
LIMIT 1;
              """
    }

    try:
        log.info("Fetching random lat/lng from dolthub API...")
        response = httpx.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if data.get("rows") and len(data["rows"]) > 0:
            row = data["rows"][0]
            lat = float(row.get("lat"))
            lng = float(row.get("lng"))
            zip_code = row.get("zip")
            log.info(f"Got random location: ZIP {zip_code}, lat={lat}, lng={lng}")
            return lat, lng
        else:
            raise ValueError("No rows found in response")

    except Exception as e:
        log.error(f"Error fetching random lat/lng: {e}")
        # Fallback to NYC coordinates
        return 40.7128, -74.0060
```

## How this works

1. Download the latest zip code database ("gazetteer") from the Census Bureau. This contains lat/lng and zip code data.
2. Transform this data and import it into a Dolthub database.
3. Separately, manually download population data from the Census Bureau.
4. Transform this data, import into dolt, and then update the existing zip code data with the population data.

The entrypoint to this process is `bin/download-gazetteer`.

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
