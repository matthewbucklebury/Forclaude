#!/usr/bin/env python3
"""
Download London LSOA population data and centroids from multiple sources.
Falls back to generating population grid based on known London density patterns.
"""

import json
import os
import requests
import time
import csv
from pathlib import Path
import math

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# London bounding box
LONDON_BOUNDS = {
    "min_lon": -0.51,
    "max_lon": 0.33,
    "min_lat": 51.28,
    "max_lat": 51.69
}

# London boroughs approximate centroids for population weighting
# Based on Census 2021 data: Greater London population ~8.8 million
BOROUGH_DATA = {
    "City of London": {"lat": 51.5155, "lon": -0.0922, "pop": 8600},
    "Westminster": {"lat": 51.4973, "lon": -0.1372, "pop": 204239},
    "Kensington and Chelsea": {"lat": 51.4990, "lon": -0.1938, "pop": 143793},
    "Hammersmith and Fulham": {"lat": 51.4927, "lon": -0.2339, "pop": 185143},
    "Wandsworth": {"lat": 51.4571, "lon": -0.1818, "pop": 327899},
    "Lambeth": {"lat": 51.4571, "lon": -0.1231, "pop": 318216},
    "Southwark": {"lat": 51.4733, "lon": -0.0760, "pop": 307672},
    "Tower Hamlets": {"lat": 51.5099, "lon": -0.0059, "pop": 310300},
    "Hackney": {"lat": 51.5450, "lon": -0.0553, "pop": 259200},
    "Islington": {"lat": 51.5416, "lon": -0.1022, "pop": 214403},
    "Camden": {"lat": 51.5517, "lon": -0.1588, "pop": 210100},
    "Brent": {"lat": 51.5673, "lon": -0.2711, "pop": 339800},
    "Ealing": {"lat": 51.5130, "lon": -0.3089, "pop": 367115},
    "Hounslow": {"lat": 51.4746, "lon": -0.3680, "pop": 288200},
    "Richmond": {"lat": 51.4479, "lon": -0.3260, "pop": 198019},
    "Kingston": {"lat": 51.3925, "lon": -0.2872, "pop": 177507},
    "Merton": {"lat": 51.4098, "lon": -0.1949, "pop": 218171},
    "Sutton": {"lat": 51.3618, "lon": -0.1945, "pop": 206349},
    "Croydon": {"lat": 51.3714, "lon": -0.0977, "pop": 390719},
    "Bromley": {"lat": 51.4039, "lon": 0.0198, "pop": 331096},
    "Lewisham": {"lat": 51.4452, "lon": -0.0209, "pop": 303536},
    "Greenwich": {"lat": 51.4892, "lon": 0.0648, "pop": 286186},
    "Bexley": {"lat": 51.4549, "lon": 0.1505, "pop": 248287},
    "Havering": {"lat": 51.5779, "lon": 0.2120, "pop": 262752},
    "Barking and Dagenham": {"lat": 51.5607, "lon": 0.1557, "pop": 218470},
    "Redbridge": {"lat": 51.5590, "lon": 0.0741, "pop": 310300},
    "Newham": {"lat": 51.5255, "lon": 0.0352, "pop": 387576},
    "Waltham Forest": {"lat": 51.5908, "lon": -0.0134, "pop": 278000},
    "Haringey": {"lat": 51.5906, "lon": -0.1110, "pop": 268647},
    "Enfield": {"lat": 51.6538, "lon": -0.0799, "pop": 333869},
    "Barnet": {"lat": 51.6252, "lon": -0.1517, "pop": 395869},
    "Harrow": {"lat": 51.5898, "lon": -0.3346, "pop": 261000},
    "Hillingdon": {"lat": 51.5441, "lon": -0.4760, "pop": 309014}
}


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two points."""
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def generate_population_grid():
    """
    Generate a population grid for London based on borough centroids
    and known population distribution patterns.
    Uses a 200m grid to allow for proper 500m buffer analysis.
    """
    print("Generating population grid for London...")

    # Create a grid of points across London
    # 200m grid spacing (approximately 0.0025 degrees at London's latitude)
    grid_spacing = 0.0025

    points = []
    lat = LONDON_BOUNDS["min_lat"]

    while lat <= LONDON_BOUNDS["max_lat"]:
        lon = LONDON_BOUNDS["min_lon"]
        while lon <= LONDON_BOUNDS["max_lon"]:
            # Calculate population weight based on distance to borough centroids
            total_weight = 0
            weighted_pop = 0

            for borough, data in BOROUGH_DATA.items():
                dist = haversine_distance(lat, lon, data["lat"], data["lon"])

                # Use inverse square distance weighting, capped at 10km
                if dist < 10000:
                    # Weight decreases with distance, higher near center
                    weight = 1 / (1 + (dist / 1000) ** 2)
                    total_weight += weight
                    weighted_pop += weight * data["pop"]

            if total_weight > 0:
                # Estimate population for this grid cell
                # Each grid cell is ~200m x 200m = 0.04 km²
                # Average London density is about 5,700 people/km²
                # But varies greatly from ~300 (outer) to ~15,000+ (inner)
                density_factor = weighted_pop / (total_weight * 100000)
                cell_area = 0.04  # km²

                estimated_pop = int(density_factor * cell_area * 5000)

                if estimated_pop > 0:
                    points.append({
                        "lat": round(lat, 6),
                        "lon": round(lon, 6),
                        "population": estimated_pop
                    })

            lon += grid_spacing
        lat += grid_spacing

    print(f"  Generated {len(points):,} grid cells")

    # Normalize to match London's total population (~8.8 million)
    total_pop = sum(p["population"] for p in points)
    target_pop = 8800000
    scale_factor = target_pop / total_pop if total_pop > 0 else 1

    for p in points:
        p["population"] = max(1, int(p["population"] * scale_factor))

    actual_total = sum(p["population"] for p in points)
    print(f"  Total population: {actual_total:,}")

    return points


def try_download_lsoa_data():
    """
    Try to download LSOA population weighted centroids from ONS.
    Returns None if unsuccessful.
    """
    print("Attempting to download LSOA population data...")

    # Try multiple sources
    sources = [
        # ONS Open Geography Portal - LSOA PWC
        (
            "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "LSOA_Dec_2021_PWC_for_England_and_Wales_2022/FeatureServer/0/query?"
            "where=1%3D1&"
            "geometry=-0.6,51.2,0.4,51.8&"
            "geometryType=esriGeometryEnvelope&"
            "inSR=4326&"
            "spatialRel=esriSpatialRelIntersects&"
            "outFields=LSOA21CD,LSOA21NM,LONG,LAT&"
            "returnGeometry=false&"
            "outSR=4326&"
            "f=json&"
            "resultRecordCount=10000"
        ),
    ]

    for url in sources:
        try:
            print(f"  Trying source...")
            response = requests.get(url, timeout=60)
            if response.status_code == 200:
                data = response.json()
                if "features" in data and len(data["features"]) > 0:
                    print(f"  Found {len(data['features'])} LSOAs")
                    return data
        except Exception as e:
            print(f"  Failed: {e}")
            continue

    return None


def save_population_data():
    """Save population data for London."""

    # Try to download real LSOA data first
    lsoa_data = try_download_lsoa_data()

    if lsoa_data and "features" in lsoa_data:
        # Process LSOA data
        points = []
        for feature in lsoa_data["features"]:
            attrs = feature.get("attributes", {})
            points.append({
                "id": attrs.get("LSOA21CD", ""),
                "name": attrs.get("LSOA21NM", ""),
                "lat": attrs.get("LAT"),
                "lon": attrs.get("LONG"),
                "population": 1600  # Average LSOA population
            })

        output_file = DATA_DIR / "london_population.json"
        with open(output_file, "w") as f:
            json.dump({"source": "ONS LSOA 2021", "points": points}, f)
        print(f"Saved LSOA data to {output_file}")
        return True

    # Fall back to grid-based population
    print("  Using grid-based population estimation...")
    points = generate_population_grid()

    output_file = DATA_DIR / "london_population.json"
    with open(output_file, "w") as f:
        json.dump({
            "source": "Grid estimation based on 2021 Census borough totals",
            "points": points
        }, f)

    print(f"Saved population grid to {output_file}")
    return True


if __name__ == "__main__":
    save_population_data()
