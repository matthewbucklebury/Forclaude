#!/usr/bin/env python3
"""
Phase 3: Classify stations by type and calculate advanced metrics.

Station Types:
- Commuter Hub: Low population, high usage (business districts, interchanges)
- Residential Hub: High population, low usage (suburbs, residential areas)
- Balanced: High population, high usage (mixed-use areas)
- Low Activity: Low population, low usage (outer areas)
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def calculate_thresholds(stations):
    """Calculate dynamic thresholds based on data distribution."""
    # Get stations with both metrics
    with_both = [s for s in stations if s['annual_usage'] > 0 and s['population_500m'] > 0]

    populations = sorted([s['population_500m'] for s in with_both])
    usages = sorted([s['daily_usage'] for s in with_both])

    # Use median as threshold (50th percentile)
    pop_median = populations[len(populations) // 2]
    usage_median = usages[len(usages) // 2]

    # Also calculate quartiles for reference
    pop_25 = populations[len(populations) // 4]
    pop_75 = populations[3 * len(populations) // 4]
    usage_25 = usages[len(usages) // 4]
    usage_75 = usages[3 * len(usages) // 4]

    return {
        'population_threshold': pop_median,
        'usage_threshold': usage_median,
        'pop_25': pop_25,
        'pop_75': pop_75,
        'usage_25': usage_25,
        'usage_75': usage_75
    }


def classify_station(station, thresholds):
    """Classify a single station based on population and usage."""
    pop = station['population_500m']
    usage = station['daily_usage']

    pop_thresh = thresholds['population_threshold']
    usage_thresh = thresholds['usage_threshold']

    # Handle stations without data
    if usage == 0:
        return 'no_usage_data'
    if pop == 0:
        return 'no_population_data'

    # Classify based on quadrant
    high_pop = pop >= pop_thresh
    high_usage = usage >= usage_thresh

    if high_usage and not high_pop:
        return 'commuter_hub'
    elif high_pop and not high_usage:
        return 'residential_hub'
    elif high_pop and high_usage:
        return 'balanced'
    else:
        return 'low_activity'


def calculate_line_metrics(stations, line_colors):
    """Calculate aggregated metrics per line."""
    tube_lines = ["bakerloo", "central", "circle", "district", "hammersmith-city",
                  "jubilee", "metropolitan", "northern", "piccadilly", "victoria", "waterloo-city"]

    line_metrics = {}

    for line_id in tube_lines:
        # Get stations on this line
        line_stations = [s for s in stations if line_id in s.get('lines', [])]

        if not line_stations:
            continue

        # Calculate metrics
        total_pop_500m = sum(s['population_500m'] for s in line_stations)
        total_pop_1km = sum(s['population_1km'] for s in line_stations)
        total_usage = sum(s['annual_usage'] for s in line_stations)
        total_daily = sum(s['daily_usage'] for s in line_stations)

        stations_with_usage = [s for s in line_stations if s['annual_usage'] > 0]
        stations_with_pop = [s for s in line_stations if s['population_500m'] > 0]

        # Line efficiency: usage per capita
        efficiency = total_daily / total_pop_500m if total_pop_500m > 0 else 0

        line_metrics[line_id] = {
            'name': line_id.replace('-', ' ').title(),
            'color': line_colors.get(line_id, '#666666'),
            'station_count': len(line_stations),
            'stations_with_usage': len(stations_with_usage),
            'total_population_500m': total_pop_500m,
            'total_population_1km': total_pop_1km,
            'total_annual_usage': total_usage,
            'total_daily_usage': total_daily,
            'avg_daily_per_station': total_daily // len(line_stations) if line_stations else 0,
            'avg_pop_per_station': total_pop_500m // len(line_stations) if line_stations else 0,
            'efficiency_ratio': round(efficiency, 2)
        }

    return line_metrics


def main():
    print("=" * 70)
    print("PHASE 3: STATION CLASSIFICATION AND ADVANCED METRICS")
    print("=" * 70)

    # Load enhanced station data
    print("\n1. Loading enhanced station data...")
    with open(DATA_DIR / 'tube_stations_enhanced.json') as f:
        data = json.load(f)

    stations = data['stations']
    line_colors = data['line_colors']

    # Filter to Tube stations only (they have usage data)
    tube_lines = ["bakerloo", "central", "circle", "district", "hammersmith-city",
                  "jubilee", "metropolitan", "northern", "piccadilly", "victoria", "waterloo-city"]
    tube_stations = [s for s in stations if any(l in tube_lines for l in s.get('lines', []))]

    print(f"   Total stations: {len(stations)}")
    print(f"   Tube stations: {len(tube_stations)}")

    # Calculate thresholds
    print("\n2. Calculating classification thresholds...")
    thresholds = calculate_thresholds(tube_stations)
    print(f"   Population threshold (median): {thresholds['population_threshold']:,}")
    print(f"   Usage threshold (median): {thresholds['usage_threshold']:,}/day")
    print(f"   Population range: {thresholds['pop_25']:,} - {thresholds['pop_75']:,} (25th-75th)")
    print(f"   Usage range: {thresholds['usage_25']:,} - {thresholds['usage_75']:,}/day (25th-75th)")

    # Classify stations
    print("\n3. Classifying stations...")
    type_counts = {}
    for station in stations:
        station_type = classify_station(station, thresholds)
        station['station_type'] = station_type
        type_counts[station_type] = type_counts.get(station_type, 0) + 1

    print("   Station type distribution:")
    for stype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"      {stype}: {count}")

    # Calculate line metrics
    print("\n4. Calculating line-level metrics...")
    line_metrics = calculate_line_metrics(tube_stations, line_colors)

    # Sort by efficiency
    sorted_lines = sorted(line_metrics.items(), key=lambda x: -x[1]['efficiency_ratio'])
    print("\n   Lines by efficiency (usage per capita):")
    for line_id, metrics in sorted_lines:
        print(f"      {metrics['name']}: {metrics['efficiency_ratio']:.1f}x "
              f"(daily: {metrics['total_daily_usage']:,}, pop: {metrics['total_population_500m']:,})")

    # Save classified data
    print("\n5. Saving results...")

    # Update enhanced stations with classification
    with open(DATA_DIR / 'tube_stations_enhanced.json', 'w') as f:
        json.dump({
            'source': data['source'],
            'stations': stations,
            'line_colors': line_colors,
            'thresholds': thresholds
        }, f, indent=2)
    print("   Updated tube_stations_enhanced.json with station types")

    # Save station types analysis
    analysis = {
        'thresholds': thresholds,
        'type_counts': type_counts,
        'line_metrics': line_metrics,
        'stations_by_type': {
            'commuter_hub': [{'name': s['name'], 'daily_usage': s['daily_usage'],
                            'population_500m': s['population_500m'],
                            'usage_per_capita': s['usage_per_capita_500m']}
                           for s in stations if s.get('station_type') == 'commuter_hub'],
            'residential_hub': [{'name': s['name'], 'daily_usage': s['daily_usage'],
                                'population_500m': s['population_500m'],
                                'usage_per_capita': s['usage_per_capita_500m']}
                               for s in stations if s.get('station_type') == 'residential_hub'],
            'balanced': [{'name': s['name'], 'daily_usage': s['daily_usage'],
                         'population_500m': s['population_500m'],
                         'usage_per_capita': s['usage_per_capita_500m']}
                        for s in stations if s.get('station_type') == 'balanced'],
            'low_activity': [{'name': s['name'], 'daily_usage': s['daily_usage'],
                             'population_500m': s['population_500m'],
                             'usage_per_capita': s['usage_per_capita_500m']}
                            for s in stations if s.get('station_type') == 'low_activity']
        }
    }

    with open(DATA_DIR / 'station_types_analysis.json', 'w') as f:
        json.dump(analysis, f, indent=2)
    print("   Saved station_types_analysis.json")

    # Print summary
    print("\n" + "=" * 70)
    print("PHASE 3 RESULTS SUMMARY")
    print("=" * 70)

    print("\n** COMMUTER HUBS ** (Low pop, high usage - business/interchange)")
    commuter = sorted([s for s in stations if s.get('station_type') == 'commuter_hub'],
                     key=lambda x: -x['usage_per_capita_500m'])[:10]
    for s in commuter:
        print(f"   {s['name']}: {s['usage_per_capita_500m']:.1f}x "
              f"(pop: {s['population_500m']:,}, usage: {s['daily_usage']:,}/day)")

    print("\n** RESIDENTIAL HUBS ** (High pop, low usage - residential areas)")
    residential = sorted([s for s in stations if s.get('station_type') == 'residential_hub'],
                        key=lambda x: -x['population_500m'])[:10]
    for s in residential:
        print(f"   {s['name']}: pop {s['population_500m']:,}, usage {s['daily_usage']:,}/day "
              f"({s['usage_per_capita_500m']:.1f}x)")

    print("\n** BALANCED ** (High pop, high usage - mixed areas)")
    balanced = sorted([s for s in stations if s.get('station_type') == 'balanced'],
                     key=lambda x: -x['daily_usage'])[:10]
    for s in balanced:
        print(f"   {s['name']}: pop {s['population_500m']:,}, usage {s['daily_usage']:,}/day "
              f"({s['usage_per_capita_500m']:.1f}x)")

    print("\n" + "=" * 70)
    print("PHASE 3 COMPLETE")
    print("=" * 70)

    return stations, line_metrics, thresholds


if __name__ == '__main__':
    main()
