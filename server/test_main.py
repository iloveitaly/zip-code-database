import pytest
from fastapi.testclient import TestClient
from main import app, ZipCodeData, state, DB_PATH, load_geo_data
import sqlite3
import numpy as np
from scipy.spatial import KDTree

# Setup the test client
client = TestClient(app)

# Fixture to set up and tear down the database connection and KDTree for tests
@pytest.fixture(scope="module", autouse=True)
def setup_database():
    # Ensure the database is loaded for tests
    # FastAPI's TestClient doesn't call lifespan events by default,
    # so we manually call the setup logic
    state.db_connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    state.db_connection.row_factory = sqlite3.Row
    load_geo_data()
    yield
    # Teardown
    if state.db_connection:
        state.db_connection.close()
    state.kd_tree = None
    state.zip_codes_list = []

def test_read_random_zip():
    response = client.get("/random")
    assert response.status_code == 200
    zip_data = ZipCodeData(**response.json())
    assert zip_data.zip is not None
    assert isinstance(zip_data.zip, str)
    assert len(zip_data.zip) == 5 # Assuming all US zip codes are 5 digits

def test_read_valid_zip_code():
    # A known valid zip code from the provided data sample
    test_zip = "00601"
    response = client.get(f"/{test_zip}")
    assert response.status_code == 200
    zip_data = ZipCodeData(**response.json())
    assert zip_data.zip == test_zip
    assert zip_data.city == "Adjuntas"
    assert zip_data.state == "PR"

def test_read_invalid_zip_code():
    response = client.get("/99999") # Assuming 99999 is not in the database
    assert response.status_code == 404
    assert response.json()["detail"] == "Zip code not found"

def test_get_nearest_zip():
    # Coordinates of Adjuntas, PR (00601) - from the data sample
    test_lat = 18.180555
    test_lng = -66.74996
    response = client.get(f"/nearest?lat={test_lat}&lng={test_lng}")
    assert response.status_code == 200
    zip_data = ZipCodeData(**response.json())
    assert zip_data.zip == "00601"
    assert zip_data.city == "Adjuntas"
    assert zip_data.state == "PR"

def test_get_nearest_zip_no_index_available():
    # Temporarily clear the KDTree to simulate an error state
    temp_kd_tree = state.kd_tree
    state.kd_tree = None
    try:
        response = client.get("/nearest?lat=0&lng=0")
        assert response.status_code == 503
        assert response.json()["detail"] == "Geospatial index not unavailable"
    finally:
        state.kd_tree = temp_kd_tree # Restore it

def test_read_coords_path():
    # Coordinates of Adjuntas, PR (00601)
    test_lat = 18.180555
    test_lng = -66.74996
    response = client.get(f"/{test_lat},{test_lng}")
    assert response.status_code == 200
    zip_data = ZipCodeData(**response.json())
    assert zip_data.zip == "00601"
    assert zip_data.city == "Adjuntas"
    assert zip_data.state == "PR"

def test_read_invalid_coords_path():
    # Test out of range latitude
    response = client.get("/91.0,-66.0")
    assert response.status_code == 400
    assert response.json()["detail"] == "Latitude must be between -90 and 90. Expected format: /{latitude},{longitude}"

    # Test out of range longitude
    response = client.get("/18.0,-181.0")
    assert response.status_code == 400
    assert response.json()["detail"] == "Longitude must be between -180 and 180. Expected format: /{latitude},{longitude}"

