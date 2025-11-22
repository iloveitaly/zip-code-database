import sqlite3
import os
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import structlog
import structlog_config
import structlog_config.fastapi_access_logger
from fastapi import FastAPI, HTTPException, Query
from scipy.spatial import KDTree
from pydantic import BaseModel

# --- Configuration ---
# Default to local file in same dir for Docker/deployment, or allow override
DB_PATH = os.getenv("DB_PATH", "zip_codes.db")

# --- Logging ---
structlog_config.configure_logger()
logger = structlog.get_logger()

# --- Global State ---
class AppState:
    kd_tree: Optional[KDTree] = None
    zip_codes_list: list[str] = []
    db_connection: Optional[sqlite3.Connection] = None

state = AppState()

# --- Models ---
class ZipCodeData(BaseModel):
    id: int
    zip: str
    lat: Optional[float]
    lng: Optional[float]
    population: Optional[int]
    city: Optional[str]
    state: Optional[str]
    type: Optional[str]

# --- Database ---
def get_db_connection():
    # In a real high-concurrency app we might use a pool, 
    # but for read-only sqlite with threading check disabled, this is fine for this scale.
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def load_geo_data():
    """Loads all lat/lng/zip data into memory for the KDTree."""
    logger.info("Loading geospatial data...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Only fetch rows that have valid coordinates
    cursor.execute("SELECT zip, lat, lng FROM zip_codes WHERE lat IS NOT NULL AND lng IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        logger.warning("No geospatial data found in database!")
        return

    # Prepare data for KDTree
    # scipy KDTree expects (N, m) array for N points of dimension m
    coords = []
    zips = []
    
    for row in rows:
        coords.append([row['lat'], row['lng']])
        zips.append(row['zip'])

    state.zip_codes_list = zips
    # Leaf size balanced for performance vs memory
    state.kd_tree = KDTree(np.array(coords), leafsize=100)
    logger.info("Loaded geospatial points into KDTree", count=len(zips))

# --- Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    state.db_connection = get_db_connection()
    load_geo_data()
    yield
    # Shutdown
    if state.db_connection:
        state.db_connection.close()

app = FastAPI(lifespan=lifespan)
structlog_config.fastapi_access_logger.add_middleware(app)

# --- Routes ---

def find_nearest(lat: float, lng: float) -> dict:
    """Helper to find the nearest zip code to a given lat/lng."""
    if state.kd_tree is None:
        raise HTTPException(status_code=503, detail="Geospatial index not unavailable")

    # Query the KDTree
    # k=1 returns the single nearest neighbor
    # Returns (distances, indices)
    distance, index = state.kd_tree.query([lat, lng], k=1)
    
    # Get the zip code from our parallel list
    nearest_zip = state.zip_codes_list[index]
    
    # Fetch full details from DB
    cursor = state.db_connection.cursor()
    cursor.execute("SELECT * FROM zip_codes WHERE zip = ?", (nearest_zip,))
    row = cursor.fetchone()
    
    if not row:
        # This theoretically shouldn't happen if the lists are synced
        raise HTTPException(status_code=404, detail="Zip code details not found")
    
    return dict(row)

@app.get("/random", response_model=ZipCodeData)
def get_random_zip():
    cursor = state.db_connection.cursor()
    cursor.execute("SELECT * FROM zip_codes ORDER BY RANDOM() LIMIT 1")
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Database is empty")
    return dict(row)

@app.get("/nearest", response_model=ZipCodeData)
def get_nearest_zip(
    lat: float = Query(..., description="Latitude"), 
    lng: float = Query(..., description="Longitude")
):
    return find_nearest(lat, lng)

@app.get("/{query}", response_model=ZipCodeData)
def get_zip_or_coords(query: str):
    # Check if input looks like coordinates "lat,lng"
    if "," in query:
        try:
            parts = query.split(",")
            if len(parts) == 2:
                lat = float(parts[0])
                lng = float(parts[1])
                
                # Validate coordinates
                if not (-90 <= lat <= 90):
                    raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90. Expected format: /{latitude},{longitude}")
                if not (-180 <= lng <= 180):
                    raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180. Expected format: /{latitude},{longitude}")
                
                return find_nearest(lat, lng)
        except ValueError:
            # If parsing fails, fall through to zip code check
            # (Though unlikely a zip code has a comma, being robust is good)
            pass

    # Treat as zip code
    cursor = state.db_connection.cursor()
    cursor.execute("SELECT * FROM zip_codes WHERE zip = ?", (query,))
    row = cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Zip code not found")
    
    return dict(row)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
