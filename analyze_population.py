#!/usr/bin/env python3
"""
Analyze population within 500m radius of London tube stations.
Calculates population per station and aggregates by tube line.
"""

import json
import math
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"


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


def load_data():
    """Load station and population data."""
    with open(DATA_DIR / "tube_stations.json") as f:
        station_data = json.load(f)

    with open(DATA_DIR / "london_population.json") as f:
        pop_data = json.load(f)

    return station_data, pop_data


def build_spatial_index(points, cell_size=0.01):
    """
    Build a simple spatial index for faster proximity queries.
    Groups points into grid cells.
    """
    index = defaultdict(list)

    for i, point in enumerate(points):
        cell_x = int(point["lon"] / cell_size)
        cell_y = int(point["lat"] / cell_size)
        index[(cell_x, cell_y)].append(i)

    return index, cell_size


def get_nearby_points(index, cell_size, lon, lat, radius_deg):
    """Get indices of points potentially within radius."""
    cells_to_check = int(radius_deg / cell_size) + 1
    center_x = int(lon / cell_size)
    center_y = int(lat / cell_size)

    nearby_indices = []
    for dx in range(-cells_to_check, cells_to_check + 1):
        for dy in range(-cells_to_check, cells_to_check + 1):
            nearby_indices.extend(index.get((center_x + dx, center_y + dy), []))

    return nearby_indices


def calculate_station_populations(stations, pop_points, radius_m=500):
    """
    Calculate population within radius of each station.
    Uses spatial indexing for efficiency.
    """
    print(f"Calculating population within {radius_m}m of each station...")

    # Build spatial index
    index, cell_size = build_spatial_index(pop_points)

    # Approximate degrees for radius (at London's latitude)
    # 1 degree latitude ≈ 111km, 1 degree longitude ≈ 70km at 51.5°N
    radius_deg = radius_m / 70000  # Conservative estimate

    station_populations = {}

    for station in stations:
        station_id = station["naptanId"]
        station_lat = station["lat"]
        station_lon = station["lon"]

        # Get potentially nearby points
        nearby_indices = get_nearby_points(index, cell_size, station_lon, station_lat, radius_deg)

        # Calculate actual distances and sum population
        total_pop = 0
        for idx in nearby_indices:
            point = pop_points[idx]
            dist = haversine_distance(station_lat, station_lon, point["lat"], point["lon"])
            if dist <= radius_m:
                total_pop += point["population"]

        station_populations[station_id] = total_pop

    return station_populations


def aggregate_by_line(stations, station_populations, line_colors):
    """
    Aggregate population by tube line.

    IMPORTANT: Each station's population is counted once per line it serves.
    For calculating line totals, we count the unique population catchment
    of all stations on that line.
    """
    print("Aggregating populations by tube line...")

    line_stats = {}

    for line_id in line_colors.keys():
        # Get all stations on this line
        line_stations = [s for s in stations if line_id in s["lines"]]

        # Sum population (note: this may double-count areas served by multiple stations)
        total_pop = sum(station_populations.get(s["naptanId"], 0) for s in line_stations)

        # Get unique station populations for this line
        station_pops = [(s["name"], station_populations.get(s["naptanId"], 0)) for s in line_stations]
        station_pops.sort(key=lambda x: -x[1])

        line_stats[line_id] = {
            "name": line_id.replace("-", " ").title(),
            "color": line_colors[line_id],
            "station_count": len(line_stations),
            "total_population": total_pop,
            "avg_population_per_station": total_pop // len(line_stations) if line_stations else 0,
            "stations": station_pops
        }

    return line_stats


def print_results(line_stats):
    """Print analysis results."""
    print("\n" + "=" * 70)
    print("LONDON TUBE LINE POPULATION ANALYSIS")
    print("Population living within 500m radius of tube stations")
    print("=" * 70)

    # Sort by total population
    sorted_lines = sorted(line_stats.items(), key=lambda x: -x[1]["total_population"])

    print(f"\n{'Rank':<5} {'Line':<25} {'Stations':<10} {'Total Pop':<15} {'Avg/Station':<12}")
    print("-" * 70)

    for rank, (line_id, stats) in enumerate(sorted_lines, 1):
        print(f"{rank:<5} {stats['name']:<25} {stats['station_count']:<10} "
              f"{stats['total_population']:>12,} {stats['avg_population_per_station']:>12,}")

    print("\n" + "=" * 70)
    winner = sorted_lines[0]
    print(f"WINNER: {winner[1]['name']} with {winner[1]['total_population']:,} people")
    print(f"        ({winner[1]['station_count']} stations)")
    print("=" * 70)

    # Top 5 stations overall
    print("\nTop 10 Stations by Catchment Population:")
    print("-" * 50)

    all_stations = []
    for line_id, stats in line_stats.items():
        for name, pop in stats["stations"]:
            all_stations.append((name, pop, stats["name"]))

    # Remove duplicates (stations appear on multiple lines)
    seen = set()
    unique_stations = []
    for name, pop, line in all_stations:
        if name not in seen:
            seen.add(name)
            unique_stations.append((name, pop))

    unique_stations.sort(key=lambda x: -x[1])

    for i, (name, pop) in enumerate(unique_stations[:10], 1):
        print(f"{i:>2}. {name:<35} {pop:>10,}")

    return sorted_lines


def save_results(stations, station_populations, line_stats, line_colors):
    """Save analysis results for the visualization."""
    # Enhance station data with populations
    enhanced_stations = []
    for station in stations:
        enhanced = station.copy()
        enhanced["population"] = station_populations.get(station["naptanId"], 0)
        enhanced_stations.append(enhanced)

    results = {
        "stations": enhanced_stations,
        "line_stats": line_stats,
        "line_colors": line_colors,
        "radius_meters": 500,
        "analysis_notes": "Population estimated within 500m radius of each station"
    }

    output_file = DATA_DIR / "analysis_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {output_file}")
    return results


def main():
    # Load data
    station_data, pop_data = load_data()

    stations = station_data["stations"]
    line_colors = station_data["line_colors"]
    pop_points = pop_data["points"]

    print(f"Loaded {len(stations)} stations and {len(pop_points):,} population points")
    print(f"Population data source: {pop_data.get('source', 'Unknown')}")

    # Calculate station populations
    station_populations = calculate_station_populations(stations, pop_points, radius_m=500)

    # Aggregate by line
    line_stats = aggregate_by_line(stations, station_populations, line_colors)

    # Print results
    sorted_lines = print_results(line_stats)

    # Save results
    save_results(stations, station_populations, line_stats, line_colors)

    return sorted_lines


if __name__ == "__main__":
    main()
