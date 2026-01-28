#!/usr/bin/env python3
"""
Run population analysis at multiple radii for the radius toggle feature.
Outputs separate JSON files for 500m and 1km analysis.
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

    with open(DATA_DIR / "london_population_extended.json") as f:
        pop_data = json.load(f)

    return station_data, pop_data


def build_spatial_index(points, cell_size=0.01):
    """Build a simple spatial index for faster proximity queries."""
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


def calculate_station_populations(stations, pop_points, radius_m, index, cell_size):
    """Calculate population within radius of each station."""
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
    """Aggregate population by tube line."""
    line_stats = {}

    for line_id in line_colors.keys():
        line_stations = [s for s in stations if line_id in s["lines"]]
        total_pop = sum(station_populations.get(s["naptanId"], 0) for s in line_stations)
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


def save_results(stations, station_populations, line_stats, line_colors, radius_m, output_filename):
    """Save analysis results to a specific file."""
    enhanced_stations = []
    for station in stations:
        enhanced = station.copy()
        enhanced["population"] = station_populations.get(station["naptanId"], 0)
        enhanced_stations.append(enhanced)

    results = {
        "stations": enhanced_stations,
        "line_stats": line_stats,
        "line_colors": line_colors,
        "radius_meters": radius_m,
        "analysis_notes": f"Population estimated within {radius_m}m radius of each station"
    }

    output_file = DATA_DIR / output_filename
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


def print_comparison(results_500m, results_1km):
    """Print comparison of 500m vs 1km results."""
    print("\n" + "=" * 80)
    print("COMPARISON: 500m vs 1km RADIUS ANALYSIS")
    print("=" * 80)

    # Line stats comparison
    line_stats_500 = results_500m["line_stats"]
    line_stats_1km = results_1km["line_stats"]

    sorted_lines = sorted(line_stats_500.items(), key=lambda x: -x[1]["total_population"])

    print(f"\n{'Line':<25} {'500m Pop':<15} {'1km Pop':<15} {'Ratio':<10}")
    print("-" * 65)

    for line_id, stats_500 in sorted_lines:
        stats_1km = line_stats_1km[line_id]
        ratio = stats_1km["total_population"] / stats_500["total_population"] if stats_500["total_population"] > 0 else 0
        print(f"{stats_500['name']:<25} {stats_500['total_population']:>12,} {stats_1km['total_population']:>12,} {ratio:>8.2f}x")

    # Top stations comparison
    print("\n" + "-" * 80)
    print("TOP 10 STATIONS COMPARISON:")
    print("-" * 80)

    stations_500 = {s["name"]: s["population"] for s in results_500m["stations"]}
    stations_1km = {s["name"]: s["population"] for s in results_1km["stations"]}

    top_stations = sorted(stations_500.items(), key=lambda x: -x[1])[:10]

    print(f"\n{'Station':<35} {'500m Pop':<12} {'1km Pop':<12} {'Ratio':<8}")
    print("-" * 70)

    for name, pop_500 in top_stations:
        pop_1km = stations_1km.get(name, 0)
        ratio = pop_1km / pop_500 if pop_500 > 0 else 0
        print(f"{name:<35} {pop_500:>10,} {pop_1km:>10,} {ratio:>6.2f}x")

    # Specific stations mentioned in requirements
    print("\n" + "-" * 80)
    print("SPECIFIC STATIONS TO VERIFY:")
    print("-" * 80)

    check_stations = ["King's Cross St. Pancras", "Baker Street"]
    for name in check_stations:
        pop_500 = stations_500.get(name, 0)
        pop_1km = stations_1km.get(name, 0)
        ratio = pop_1km / pop_500 if pop_500 > 0 else 0
        print(f"{name}: 500m={pop_500:,}, 1km={pop_1km:,}, ratio={ratio:.2f}x")


def main():
    print("=" * 80)
    print("DUAL RADIUS POPULATION ANALYSIS")
    print("=" * 80)

    # Load data
    station_data, pop_data = load_data()
    stations = station_data["stations"]
    line_colors = station_data["line_colors"]
    pop_points = pop_data["points"]

    print(f"Loaded {len(stations)} stations and {len(pop_points):,} population points")

    # Build spatial index once (reuse for both radii)
    print("Building spatial index...")
    index, cell_size = build_spatial_index(pop_points)

    # Run 500m analysis
    print("\n--- 500m RADIUS ANALYSIS ---")
    station_pops_500 = calculate_station_populations(stations, pop_points, 500, index, cell_size)
    line_stats_500 = aggregate_by_line(stations, station_pops_500, line_colors)
    results_500 = save_results(stations, station_pops_500, line_stats_500, line_colors, 500, "analysis_results_500m.json")
    print(f"Saved to data/analysis_results_500m.json")

    # Print 500m summary
    sorted_500 = sorted(line_stats_500.items(), key=lambda x: -x[1]["total_population"])
    print(f"\n500m Winner: {sorted_500[0][1]['name']} with {sorted_500[0][1]['total_population']:,} people")

    # Run 1km analysis
    print("\n--- 1km RADIUS ANALYSIS ---")
    station_pops_1km = calculate_station_populations(stations, pop_points, 1000, index, cell_size)
    line_stats_1km = aggregate_by_line(stations, station_pops_1km, line_colors)
    results_1km = save_results(stations, station_pops_1km, line_stats_1km, line_colors, 1000, "analysis_results_1km.json")
    print(f"Saved to data/analysis_results_1km.json")

    # Print 1km summary
    sorted_1km = sorted(line_stats_1km.items(), key=lambda x: -x[1]["total_population"])
    print(f"\n1km Winner: {sorted_1km[0][1]['name']} with {sorted_1km[0][1]['total_population']:,} people")

    # Print comparison
    print_comparison(results_500, results_1km)

    print("\n" + "=" * 80)
    print("PHASE 1 COMPLETE - Review results above before proceeding to Phase 2")
    print("=" * 80)


if __name__ == "__main__":
    main()
