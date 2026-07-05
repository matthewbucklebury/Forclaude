#!/usr/bin/env python3
"""
Expand census coverage to include all areas served by TfL stations.

The original london_population.json only covers Greater London boroughs,
but TfL services extend beyond London into:
- Berkshire (Elizabeth Line: Reading, Slough, Maidenhead)
- Hertfordshire (Overground/Metropolitan: Watford, Cheshunt)
- Buckinghamshire (Metropolitan: Amersham, Chesham)
- Essex (Central/Elizabeth: Epping, Shenfield)
- Surrey (some Overground south)
- Kent (Elizabeth: Abbey Wood area)

This script downloads England & Wales census data and filters to a 5km buffer
around all TfL stations, ensuring complete coverage for the analysis.
"""

import csv
import json
import math
import requests
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth's radius in meters

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


def bng_to_wgs84(easting, northing):
    """
    Convert British National Grid coordinates to WGS84 lat/lon.
    Simplified implementation using Helmert transformation.
    """
    # Airy 1830 ellipsoid (used by OSGB36)
    a = 6377563.396
    b = 6356256.909
    e2 = (a*a - b*b) / (a*a)

    # National Grid origin
    N0 = -100000
    E0 = 400000
    F0 = 0.9996012717
    phi0 = math.radians(49)
    lambda0 = math.radians(-2)

    # Iterate to find latitude
    phi = phi0
    M = 0

    while True:
        phi_old = phi
        M = b * F0 * (
            (1 + e2/4 + e2*e2*5/4) * (phi - phi0)
            - (3*e2/2 + 3*e2*e2/2) * math.sin(phi - phi0) * math.cos(phi + phi0)
            + (15*e2*e2/8) * math.sin(2*(phi - phi0)) * math.cos(2*(phi + phi0))
        )
        phi = (northing - N0 - M) / (a * F0) + phi

        if abs(phi - phi_old) < 1e-12:
            break

    # Calculate auxiliary values
    nu = a * F0 / math.sqrt(1 - e2 * math.sin(phi)**2)
    rho = a * F0 * (1 - e2) / (1 - e2 * math.sin(phi)**2)**1.5
    eta2 = nu/rho - 1

    # Calculate longitude
    VII = math.tan(phi) / (2 * rho * nu)
    VIII = math.tan(phi) / (24 * rho * nu**3) * (5 + 3*math.tan(phi)**2 + eta2 - 9*math.tan(phi)**2*eta2)
    IX = math.tan(phi) / (720 * rho * nu**5) * (61 + 90*math.tan(phi)**2 + 45*math.tan(phi)**4)
    X = 1 / (math.cos(phi) * nu)
    XI = 1 / (math.cos(phi) * 6 * nu**3) * (nu/rho + 2*math.tan(phi)**2)
    XII = 1 / (math.cos(phi) * 120 * nu**5) * (5 + 28*math.tan(phi)**2 + 24*math.tan(phi)**4)

    dE = easting - E0

    phi_osgb = phi - VII*dE**2 + VIII*dE**4 - IX*dE**6
    lambda_osgb = lambda0 + X*dE - XI*dE**3 + XII*dE**5

    # Convert to degrees
    lat_osgb = math.degrees(phi_osgb)
    lon_osgb = math.degrees(lambda_osgb)

    # Helmert transformation from OSGB36 to WGS84
    # These are approximate parameters
    tx, ty, tz = 446.448, -125.157, 542.060
    rx, ry, rz = 0.1502, 0.2470, 0.8421
    s = -20.4894

    # Convert to radians for rotation
    rx = math.radians(rx / 3600)
    ry = math.radians(ry / 3600)
    rz = math.radians(rz / 3600)
    s = s * 1e-6

    # Convert lat/lon to cartesian
    lat_rad = math.radians(lat_osgb)
    lon_rad = math.radians(lon_osgb)

    nu_osgb = a / math.sqrt(1 - e2 * math.sin(lat_rad)**2)

    x1 = nu_osgb * math.cos(lat_rad) * math.cos(lon_rad)
    y1 = nu_osgb * math.cos(lat_rad) * math.sin(lon_rad)
    z1 = nu_osgb * (1 - e2) * math.sin(lat_rad)

    # Apply Helmert transformation
    x2 = tx + (1 + s) * x1 - rz * y1 + ry * z1
    y2 = ty + rz * x1 + (1 + s) * y1 - rx * z1
    z2 = tz - ry * x1 + rx * y1 + (1 + s) * z1

    # WGS84 ellipsoid
    a_wgs = 6378137.0
    b_wgs = 6356752.3142
    e2_wgs = (a_wgs*a_wgs - b_wgs*b_wgs) / (a_wgs*a_wgs)

    # Convert back to lat/lon
    p = math.sqrt(x2*x2 + y2*y2)
    lat_wgs = math.atan2(z2, p * (1 - e2_wgs))

    for _ in range(10):
        nu_wgs = a_wgs / math.sqrt(1 - e2_wgs * math.sin(lat_wgs)**2)
        lat_wgs = math.atan2(z2 + e2_wgs * nu_wgs * math.sin(lat_wgs), p)

    lon_wgs = math.atan2(y2, x2)

    return math.degrees(lat_wgs), math.degrees(lon_wgs)


def load_ew_oa_centroids():
    """
    Load Output Area population-weighted centroids for England & Wales.
    Uses existing local CSV file from /tmp.
    """
    print("Loading England & Wales OA population-weighted centroids...")

    # Use existing local file
    centroids_file = Path("/tmp/oa_centroids.csv")

    if not centroids_file.exists():
        print(f"  ERROR: {centroids_file} not found")
        return []

    # Parse CSV to features list
    features = []
    with open(centroids_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                features.append({
                    "attributes": {
                        "OA21CD": row.get("OA21CD"),
                        "x": float(row.get("x")),
                        "y": float(row.get("y"))
                    }
                })
            except (ValueError, TypeError):
                continue

    print(f"  Loaded {len(features):,} OA centroids from local file")
    return features


def load_ew_census_population():
    """
    Load 2021 Census population data for all Output Areas in England & Wales.
    Uses existing local CSV file from /tmp.
    """
    print("\nLoading England & Wales census population data...")

    # Use existing local file
    census_file = Path("/tmp/census2021-ts001-oa.csv")

    if not census_file.exists():
        print(f"  ERROR: {census_file} not found")
        return {}

    # Parse CSV and return as dict
    population = {}
    with open(census_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                oa_code = row.get("geography code")
                pop = int(row.get("Residence type: Total; measures: Value", 0))
                if oa_code:
                    population[oa_code] = pop
            except (ValueError, TypeError):
                continue

    print(f"  Loaded population for {len(population):,} Output Areas")
    return population


def load_tfl_stations():
    """Load TfL station locations."""
    stations_file = DATA_DIR / "tube_stations.json"
    with open(stations_file) as f:
        data = json.load(f)

    stations = []
    for s in data["stations"]:
        if s.get("lat") and s.get("lon"):
            stations.append({
                "name": s["name"],
                "lat": s["lat"],
                "lon": s["lon"],
                "lines": s.get("lines", [])
            })

    print(f"\nLoaded {len(stations)} TfL stations")
    return stations


def filter_oas_near_stations(oa_centroids, stations, buffer_m=5000):
    """
    Filter OA centroids to only those within buffer_m of any TfL station.
    """
    print(f"\nFiltering OAs within {buffer_m}m of TfL stations...")

    # Build station coordinate list for efficient lookup
    station_coords = [(s["lat"], s["lon"]) for s in stations]

    # Get bounding box of all stations plus buffer
    lats = [s["lat"] for s in stations]
    lons = [s["lon"] for s in stations]

    # Approximate degrees for buffer (1 degree ~ 111km at this latitude)
    buffer_deg = buffer_m / 111000 * 1.5  # Add extra margin

    min_lat = min(lats) - buffer_deg
    max_lat = max(lats) + buffer_deg
    min_lon = min(lons) - buffer_deg
    max_lon = max(lons) + buffer_deg

    print(f"  Station bounding box: lat [{min_lat:.3f}, {max_lat:.3f}], lon [{min_lon:.3f}, {max_lon:.3f}]")

    filtered = []
    processed = 0

    for feature in oa_centroids:
        attrs = feature.get("attributes", {})
        oa_code = attrs.get("OA21CD")
        easting = attrs.get("x")
        northing = attrs.get("y")

        if not oa_code or easting is None or northing is None:
            continue

        # Convert BNG to WGS84
        try:
            lat, lon = bng_to_wgs84(easting, northing)
        except:
            continue

        # Quick bounding box check first
        if lat < min_lat or lat > max_lat or lon < min_lon or lon > max_lon:
            processed += 1
            if processed % 50000 == 0:
                print(f"    Processed {processed:,} OAs, found {len(filtered):,} in range...")
            continue

        # Detailed distance check
        min_distance = float('inf')
        for station_lat, station_lon in station_coords:
            dist = haversine_distance(lat, lon, station_lat, station_lon)
            if dist < min_distance:
                min_distance = dist
            if dist <= buffer_m:
                break  # No need to check more stations

        if min_distance <= buffer_m:
            filtered.append({
                "oa_code": oa_code,
                "lat": lat,
                "lon": lon
            })

        processed += 1
        if processed % 50000 == 0:
            print(f"    Processed {processed:,} OAs, found {len(filtered):,} in range...")

    print(f"  Filtered to {len(filtered):,} OAs within {buffer_m}m of stations")
    return filtered


def create_extended_population_file(filtered_oas, population_data):
    """
    Create the extended population JSON file.
    Uses same format as london_population.json for compatibility.
    """
    print("\nCreating extended population file...")

    population_points = []
    missing_pop = 0

    for oa in filtered_oas:
        pop = population_data.get(oa["oa_code"], 0)
        if pop == 0:
            missing_pop += 1

        population_points.append({
            "code": oa["oa_code"],
            "lat": round(oa["lat"], 6),
            "lon": round(oa["lon"], 6),
            "population": pop
        })

    # Sort by OA code for consistency
    population_points.sort(key=lambda x: x["code"])

    total_pop = sum(p["population"] for p in population_points)

    # Save in same format as original london_population.json
    output = {
        "source": "ONS 2021 Census - Output Area Level (TS001)",
        "description": "Population within 5km of TfL rail stations",
        "total_oa_count": len(population_points),
        "total_population": total_pop,
        "points": population_points
    }

    output_file = DATA_DIR / "london_population_extended.json"
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"  Total OAs: {len(population_points):,}")
    print(f"  OAs with zero population: {missing_pop}")
    print(f"  Total population: {total_pop:,}")
    print(f"  Saved to {output_file}")

    return population_points


def update_analysis_to_use_extended():
    """
    Update analyze_dual_radius.py to use the extended population file.
    """
    analyze_file = Path(__file__).parent / "analyze_dual_radius.py"

    with open(analyze_file, "r") as f:
        content = f.read()

    # Check if already using extended file
    if "london_population_extended.json" in content:
        print("\nanalyze_dual_radius.py already uses extended population file")
        return

    # Update the file path
    old_path = '"london_population.json"'
    new_path = '"london_population_extended.json"'

    if old_path in content:
        content = content.replace(old_path, new_path)
        with open(analyze_file, "w") as f:
            f.write(content)
        print("\nUpdated analyze_dual_radius.py to use extended population file")
    else:
        print("\nCould not find population file path in analyze_dual_radius.py")


def main():
    print("=" * 70)
    print("EXPANDING CENSUS COVERAGE FOR TfL STATIONS")
    print("=" * 70)

    # Step 1: Load TfL stations
    stations = load_tfl_stations()

    # Step 2: Load OA centroids for all of England & Wales
    oa_centroids = load_ew_oa_centroids()

    if not oa_centroids:
        print("ERROR: Failed to load OA centroids")
        return

    # Step 3: Load census population data
    population_data = load_ew_census_population()

    if not population_data:
        print("ERROR: Failed to load census population data")
        return

    # Step 4: Filter OAs to those within 5km of TfL stations
    filtered_oas = filter_oas_near_stations(oa_centroids, stations, buffer_m=5000)

    # Step 5: Create extended population file
    create_extended_population_file(filtered_oas, population_data)

    # Step 6: Update analysis script
    update_analysis_to_use_extended()

    print("\n" + "=" * 70)
    print("CENSUS COVERAGE EXPANSION COMPLETE")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Run: python analyze_dual_radius.py")
    print("2. Run: python create_map.py")
    print("3. Verify stations like Reading, Epping, Amersham now show population")


if __name__ == "__main__":
    main()
