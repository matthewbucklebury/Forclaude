#!/usr/bin/env python3
"""
Process 2021 Census Output Area data for London.
Joins population data with coordinates and filters to Greater London.
"""

import csv
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

# Greater London bounding box (generous to capture all boroughs)
LONDON_BOUNDS = {
    "min_lon": -0.52,
    "max_lon": 0.35,
    "min_lat": 51.25,
    "max_lat": 51.72
}

def bng_to_wgs84(easting, northing):
    """
    Convert British National Grid (EPSG:27700) to WGS84 (EPSG:4326).
    Uses Helmert transformation.
    """
    # Airy 1830 ellipsoid
    a = 6377563.396
    b = 6356256.909
    e2 = (a**2 - b**2) / a**2

    # National Grid origin
    N0 = -100000
    E0 = 400000
    F0 = 0.9996012717
    phi0 = math.radians(49)
    lambda0 = math.radians(-2)

    n = (a - b) / (a + b)

    # Iteratively compute latitude
    phi = phi0
    M = 0
    while True:
        phi = (northing - N0 - M) / (a * F0) + phi

        M = b * F0 * (
            (1 + n + 5/4 * n**2 + 5/4 * n**3) * (phi - phi0)
            - (3*n + 3*n**2 + 21/8 * n**3) * math.sin(phi - phi0) * math.cos(phi + phi0)
            + (15/8 * n**2 + 15/8 * n**3) * math.sin(2*(phi - phi0)) * math.cos(2*(phi + phi0))
            - 35/24 * n**3 * math.sin(3*(phi - phi0)) * math.cos(3*(phi + phi0))
        )

        if abs(northing - N0 - M) < 0.00001:
            break

    nu = a * F0 / math.sqrt(1 - e2 * math.sin(phi)**2)
    rho = a * F0 * (1 - e2) / (1 - e2 * math.sin(phi)**2)**1.5
    eta2 = nu / rho - 1

    VII = math.tan(phi) / (2 * rho * nu)
    VIII = math.tan(phi) / (24 * rho * nu**3) * (5 + 3*math.tan(phi)**2 + eta2 - 9*math.tan(phi)**2*eta2)
    IX = math.tan(phi) / (720 * rho * nu**5) * (61 + 90*math.tan(phi)**2 + 45*math.tan(phi)**4)
    X = 1 / (math.cos(phi) * nu)
    XI = 1 / (math.cos(phi) * 6 * nu**3) * (nu/rho + 2*math.tan(phi)**2)
    XII = 1 / (math.cos(phi) * 120 * nu**5) * (5 + 28*math.tan(phi)**2 + 24*math.tan(phi)**4)
    XIIA = 1 / (math.cos(phi) * 5040 * nu**7) * (61 + 662*math.tan(phi)**2 + 1320*math.tan(phi)**4 + 720*math.tan(phi)**6)

    dE = easting - E0

    lat = phi - VII*dE**2 + VIII*dE**4 - IX*dE**6
    lon = lambda0 + X*dE - XI*dE**3 + XII*dE**5 - XIIA*dE**7

    return math.degrees(lat), math.degrees(lon)


def load_oa_centroids(filepath):
    """Load OA centroids with coordinates."""
    centroids = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            oa_code = row['OA21CD']
            try:
                easting = float(row['x'])
                northing = float(row['y'])
                lat, lon = bng_to_wgs84(easting, northing)
                centroids[oa_code] = {'lat': lat, 'lon': lon}
            except (ValueError, KeyError) as e:
                continue
    return centroids


def load_oa_population(filepath):
    """Load OA population data."""
    populations = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            oa_code = row['geography code']
            try:
                # Total population (in household + communal establishment)
                pop = int(row['Residence type: Total; measures: Value'])
                populations[oa_code] = pop
            except (ValueError, KeyError):
                continue
    return populations


def is_in_london(lat, lon):
    """Check if coordinates are within London bounds."""
    return (LONDON_BOUNDS['min_lat'] <= lat <= LONDON_BOUNDS['max_lat'] and
            LONDON_BOUNDS['min_lon'] <= lon <= LONDON_BOUNDS['max_lon'])


def main():
    print("Processing 2021 Census Output Area data for London...")

    # Load centroids
    print("  Loading OA centroids...")
    centroids = load_oa_centroids('/tmp/oa_centroids.csv')
    print(f"    Loaded {len(centroids):,} OA centroids")

    # Load population
    print("  Loading OA population data...")
    populations = load_oa_population('/tmp/census2021-ts001-oa.csv')
    print(f"    Loaded {len(populations):,} OA populations")

    # Join and filter to London
    print("  Joining data and filtering to London...")
    london_points = []
    total_pop = 0

    for oa_code, coords in centroids.items():
        if oa_code not in populations:
            continue

        lat, lon = coords['lat'], coords['lon']

        if not is_in_london(lat, lon):
            continue

        pop = populations[oa_code]
        total_pop += pop

        london_points.append({
            'code': oa_code,
            'lat': round(lat, 6),
            'lon': round(lon, 6),
            'population': pop
        })

    print(f"    Found {len(london_points):,} Output Areas in London")
    print(f"    Total population: {total_pop:,}")

    # Sort by OA code for consistency
    london_points.sort(key=lambda x: x['code'])

    # Save
    output = {
        'source': 'ONS 2021 Census - Output Area Level (TS001)',
        'description': 'Population within Greater London Output Areas',
        'total_oa_count': len(london_points),
        'total_population': total_pop,
        'points': london_points
    }

    output_file = DATA_DIR / 'london_population.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to {output_file}")

    # Summary statistics
    pops = [p['population'] for p in london_points]
    print(f"\nPopulation statistics:")
    print(f"  Min: {min(pops):,}")
    print(f"  Max: {max(pops):,}")
    print(f"  Mean: {sum(pops)//len(pops):,}")
    print(f"  Median: {sorted(pops)[len(pops)//2]:,}")


if __name__ == '__main__':
    main()
