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

def test_get_zips_defaults():
    response = client.get("/zips")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 250 # Should be 250 unless DB is small
    if len(data) > 0:
        # Default is sort by population desc, so first item should have high population
        # We can't know exact max, but it should have population field
        assert data[0]["population"] is not None

def test_get_zips_pagination():
    # Get page 1
    response1 = client.get("/zips?page=1")
    assert response1.status_code == 200
    data1 = response1.json()
    
    # Get page 2
    response2 = client.get("/zips?page=2")
    assert response2.status_code == 200
    data2 = response2.json()
    
    # Assuming we have enough data for 2 pages
    if len(data1) == 250 and len(data2) > 0:
        assert data1[0]["id"] != data2[0]["id"]

def test_get_zips_sorting():
    # Sort by zip asc
    response = client.get("/zips?sort_by=zip&order=asc")
    assert response.status_code == 200
    data = response.json()
    
    if len(data) > 1:
        assert data[0]["zip"] <= data[1]["zip"]

def test_get_zips_invalid_params():
    # Invalid sort_by
    response = client.get("/zips?sort_by=invalid_field")
    assert response.status_code == 400
    assert "Invalid sort_by field" in response.json()["detail"]
    
    # Invalid order
    response = client.get("/zips?order=invalid_order")
    assert response.status_code == 400
    assert "Invalid order" in response.json()["detail"]

def test_get_zips_city_state_filter():
    response = client.get("/zips?city_and_state_only=true")
    assert response.status_code == 200
    data = response.json()
    
    # Check that all returned items have city and state
    for item in data:
        assert item["city"] is not None
        assert item["state"] is not None

def test_get_random_zip_city_state_filter():
    response = client.get("/random?city_and_state_only=true")
    assert response.status_code == 200
    data = response.json()
    assert data["city"] is not None
    assert data["city"] != ""
    assert data["state"] is not None
    assert data["state"] != ""

