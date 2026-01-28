#!/usr/bin/env python3
"""
Fetch tube station data from TfL API and census population data from ONS.
"""

import json
import os
import requests
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TFL_API_BASE = "https://api.tfl.gov.uk"

TUBE_LINES = [
    "bakerloo", "central", "circle", "district", "hammersmith-city",
    "jubilee", "metropolitan", "northern", "piccadilly", "victoria", "waterloo-city"
]

LINE_COLORS = {
    "bakerloo": "#B36305",
    "central": "#E32017",
    "circle": "#FFD300",
    "district": "#00782A",
    "hammersmith-city": "#F3A9BB",
    "jubilee": "#A0A5A9",
    "metropolitan": "#9B0056",
    "northern": "#000000",
    "piccadilly": "#003688",
    "victoria": "#0098D4",
    "waterloo-city": "#95CDBA"
}

def fetch_tube_stations():
    """Fetch all tube station data from TfL API."""
    print("Fetching tube station data from TfL API...")

    all_stations = {}  # naptanId -> station data
    station_lines = {}  # naptanId -> set of lines

    for line_id in TUBE_LINES:
        print(f"  Fetching stations for {line_id} line...")
        url = f"{TFL_API_BASE}/Line/{line_id}/StopPoints"

        for attempt in range(4):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                stations = response.json()
                break
            except requests.RequestException as e:
                if attempt < 3:
                    wait_time = 2 ** (attempt + 1)
                    print(f"    Retry in {wait_time}s due to: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"    Failed to fetch {line_id}: {e}")
                    stations = []

        for station in stations:
            naptan_id = station.get("naptanId")
            if not naptan_id:
                continue

            if naptan_id not in all_stations:
                all_stations[naptan_id] = {
                    "naptanId": naptan_id,
                    "name": station.get("commonName", "").replace(" Underground Station", ""),
                    "lat": station.get("lat"),
                    "lon": station.get("lon"),
                    "lines": []
                }
                station_lines[naptan_id] = set()

            station_lines[naptan_id].add(line_id)

        time.sleep(0.5)  # Rate limiting

    # Add lines to each station
    for naptan_id, lines in station_lines.items():
        all_stations[naptan_id]["lines"] = sorted(list(lines))

    stations_list = list(all_stations.values())
    print(f"  Found {len(stations_list)} unique stations")

    # Save to file
    output_file = DATA_DIR / "tube_stations.json"
    with open(output_file, "w") as f:
        json.dump({
            "stations": stations_list,
            "line_colors": LINE_COLORS
        }, f, indent=2)

    print(f"  Saved to {output_file}")
    return stations_list


def download_census_data():
    """
    Download census population data at Output Area level.
    Using the Census 2021 TS001 (Population) dataset from Nomis.
    """
    print("\nDownloading census population data...")

    # Census 2021 population by Output Area - using Nomis API
    # TS001 is the population count dataset
    census_url = (
        "https://www.nomisweb.co.uk/api/v01/dataset/NM_2021_1.data.csv?"
        "geography=TYPE150&"  # Output Areas
        "c2021_restype=0&"    # All usual residents
        "measures=20100&"     # Count
        "select=geography_code,obs_value"
    )

    output_file = DATA_DIR / "census_population_oa.csv"

    print(f"  Downloading from Nomis API...")
    print(f"  This may take several minutes for ~180,000 Output Areas...")

    for attempt in range(4):
        try:
            response = requests.get(census_url, timeout=300, stream=True)
            response.raise_for_status()

            with open(output_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  Saved to {output_file}")

            # Count rows
            with open(output_file) as f:
                row_count = sum(1 for _ in f) - 1
            print(f"  Downloaded {row_count:,} Output Areas")
            return True

        except requests.RequestException as e:
            if attempt < 3:
                wait_time = 2 ** (attempt + 1)
                print(f"    Retry in {wait_time}s due to: {e}")
                time.sleep(wait_time)
            else:
                print(f"    Failed to download census data: {e}")
                return False


def download_oa_boundaries():
    """
    Download Output Area boundaries for London.
    Using ONS Open Geography Portal API for generalised clipped boundaries.
    """
    print("\nDownloading Output Area boundaries...")

    # ONS Open Geography Portal - Output Areas 2021 boundaries
    # Using the generalised clipped boundaries (smaller file size)
    # We'll filter for London only using the Greater London boundary

    # First, let's get just London OAs by querying with a London bounding box
    # London approximate bounding box
    london_bbox = "-0.51,51.28,0.33,51.69"

    # ONS Feature Server for Output Areas 2021
    oa_url = (
        "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
        "Output_Areas_Dec_2021_Boundaries_EW_BGC_V2/FeatureServer/0/query?"
        f"geometry={london_bbox}&"
        "geometryType=esriGeometryEnvelope&"
        "inSR=4326&"
        "spatialRel=esriSpatialRelIntersects&"
        "outFields=OA21CD&"
        "returnGeometry=true&"
        "outSR=4326&"
        "f=geojson&"
        "resultRecordCount=50000"
    )

    output_file = DATA_DIR / "london_oa_boundaries.geojson"

    print(f"  Downloading London Output Area boundaries...")
    print(f"  This may take a few minutes...")

    all_features = []
    offset = 0
    batch_size = 5000

    while True:
        batch_url = (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "Output_Areas_Dec_2021_Boundaries_EW_BGC_V2/FeatureServer/0/query?"
            f"geometry={london_bbox}&"
            "geometryType=esriGeometryEnvelope&"
            "inSR=4326&"
            "spatialRel=esriSpatialRelIntersects&"
            "outFields=OA21CD&"
            "returnGeometry=true&"
            "outSR=4326&"
            "f=geojson&"
            f"resultOffset={offset}&"
            f"resultRecordCount={batch_size}"
        )

        for attempt in range(4):
            try:
                response = requests.get(batch_url, timeout=120)
                response.raise_for_status()
                data = response.json()
                break
            except requests.RequestException as e:
                if attempt < 3:
                    wait_time = 2 ** (attempt + 1)
                    print(f"    Retry in {wait_time}s due to: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"    Failed at offset {offset}: {e}")
                    data = {"features": []}

        features = data.get("features", [])
        if not features:
            break

        all_features.extend(features)
        print(f"    Downloaded {len(all_features):,} Output Areas...")

        if len(features) < batch_size:
            break

        offset += batch_size
        time.sleep(0.5)

    # Save as GeoJSON
    geojson = {
        "type": "FeatureCollection",
        "features": all_features
    }

    with open(output_file, "w") as f:
        json.dump(geojson, f)

    print(f"  Saved {len(all_features):,} Output Areas to {output_file}")
    return len(all_features) > 0


if __name__ == "__main__":
    print("=" * 60)
    print("London Tube Station Population Data Fetcher")
    print("=" * 60)

    # Fetch tube stations
    stations = fetch_tube_stations()

    # Download census population data
    download_census_data()

    # Download OA boundaries for London
    download_oa_boundaries()

    print("\n" + "=" * 60)
    print("Data download complete!")
    print("=" * 60)
