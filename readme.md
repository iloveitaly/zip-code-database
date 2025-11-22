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
* **Enhanced formats** (after running `download-zcta-place`):
  - CSV with city/state columns (may have limited data) (`zip_codes_with_city_state_pk.csv`)
  - SQL with city/state columns (may have limited data) (`zip_codes.sql`)
  - JSON with city/state columns (may have limited data) (`zip_codes.json`)
  - **Note**: City/state data may be incomplete due to Census file format limitations

## Latest Zipcode Data

Where did this data come from?

* <https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html>
* "ZIP Code Tabulation Areas"

This is documented in the `bin/download-gazetteer` script.

## City/State Data

This project attempts to provide city and state information for each ZIP code.
The data is sourced from Census Bureau's ZCTA-to-Place relationship files and Place Gazetteers.
**Limitations**: Due to complexities and inconsistencies in Census data formats, the city/state mapping might be incomplete for some ZIP codes.
You can find this enhanced data in the various output formats, including the SQLite database and the `zip_codes_with_city_state_pk.csv` file.

## DoltHub

The data is available on Dolthub here:

<https://www.dolthub.com/repositories/iloveitaly/zip_codes_with_lat_and_lng>

## API Server

This project includes a lightweight Python FastAPI server for querying the data locally or in a container.

### Endpoints

- `GET /random`: Returns a random zip code.
- `GET /nearest?lat=...&lng=...`: Returns the nearest zip code to the provided coordinates.
- `GET /{zip_code}`: Returns details for a specific zip code.

### Docker

You can build a Docker image containing the server and the latest database:

```bash
just docker
```

Alternatively, you can pull the pre-built image from GitHub Container Registry (GHCR):

```bash
docker pull ghcr.io/iloveitaly/zip-code-database:latest
```

Run the container:

```bash
docker run -p 8000:8000 ghcr.io/iloveitaly/zip-code-database:latest
```

The API will be available at `http://localhost:8000`.

**API Overview (Examples):**

- **Get a random zip code:**
  ```bash
  curl http://localhost:8000/random
  ```

- **Get nearest zip code by coordinates (lat,lng):**
  ```bash
  curl http://localhost:8000/39.7301,-104.9078
  # Or using query parameters:
  # curl "http://localhost:8000/nearest?lat=39.7301&lng=-104.9078"
  ```

- **Get details for a specific zip code:**
  ```bash
  curl http://localhost:8000/19335
  ```

## Models

### SQLModel / ActiveModel

```python
from activemodel import BaseModel
from sqlmodel import Field


class ZipCode(BaseModel, table=True):
    """Represents a US zip code with location and population."""

    id: int = Field(primary_key=True)
    zip: str = Field(unique=True, index=True)
    lat: float
    lng: float
    population: int | None = None
```

Here's a alembic migration to import:

```python
"""add_zip_code_to_database

Revision ID: 9f2ad5bb714e
Revises: 48c4c8ca899b
Create Date: 2025-08-06 13:06:52.530393

"""
import csv
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import activemodel
from sqlmodel import Session
from activemodel.session_manager import global_session

import app
from app import log
from app.models.zip_code import ZipCode


# revision identifiers, used by Alembic.
revision: str = '9f2ad5bb714e'
down_revision: Union[str, None] = '48c4c8ca899b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def load_zip_codes_from_csv(session: Session):
    csv_path = app.root / "data/zip_code_with_population.csv"
    rows = csv_path.read_text().splitlines()
    reader = csv.DictReader(rows)

    log.info("loading zip codes from csv", path=str(csv_path))

    zip_codes = []

    for row in reader:
        # Skip rows with missing required fields
        if not row["id"] or not row["zip"] or not row["lat"] or not row["lng"]:
            continue

        # Some population fields may be empty
        population = int(row["population"]) if row["population"] else None

        zip_code = ZipCode(
            id=int(row["id"]),
            zip=row["zip"],
            lat=float(row["lat"]),
            lng=float(row["lng"]),
            population=population,
        )
        zip_codes.append(zip_code)

    session.add_all(zip_codes)
    session.commit()


def remove_all_zip_codes():
    ZipCode.where().delete()


def upgrade() -> None:
    session = Session(bind=op.get_bind())

    load_zip_codes_from_csv(session)

    # flush before running any other operations, otherwise not all changes will persist to the transaction
    session.flush()


def downgrade() -> None:
    session = Session(bind=op.get_bind())

    with global_session(session):
        remove_all_zip_codes()

    # flush before running any other operations, otherwise not all changes will persist to the transaction
    session.flush()

```

## Updating

1. Update download URL in `bin/download-gazetteer
2. Run `bin/download-gazetteer`
3. Profit

## Links

* https://tools.usps.com/zip-code-lookup.htm?citybyzipcode
* https://radar.cloudflare.com/ip