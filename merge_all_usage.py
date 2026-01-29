#!/usr/bin/env python3
"""
Merge usage data from multiple sources:
- Tube: Wikipedia List of London Underground stations
- DLR: Wikipedia List of DLR stations
- Overground/Elizabeth: ORR Station Usage data

Creates a unified usage dataset covering all TfL modes.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def normalize_name(name):
    """Normalize station name for matching."""
    name = name.lower().strip()

    # Decode HTML entities
    name = name.replace('&amp;', '&')

    # Remove common suffixes
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Remove parenthetical notes
    name = re.sub(r'\s*\[[^\]]*\]', '', name)  # Remove brackets

    # Remove location qualifiers
    for suffix in [' (london)', ' (greater london)', ' station', ' rail station',
                   ' underground station', ' dlr station', ' - underground',
                   ' international', ' (high level)', ' (low level)']:
        name = name.replace(suffix, '')

    # Standardize punctuation
    name = name.replace(' & ', ' and ')
    name = name.replace('&', ' and ')
    name = name.replace("'", '')
    name = name.replace("'", '')
    name = name.replace('.', '')
    name = name.replace('-', ' ')

    # Standardize common variations
    name = name.replace('st ', 'saint ')
    name = re.sub(r'\bst$', 'saint', name)

    # Handle "London X" -> "X"
    if name.startswith('london '):
        name = name[7:]

    # Remove extra whitespace
    name = ' '.join(name.split())

    return name


def load_tube_usage():
    """Load existing Tube usage data from Wikipedia."""
    with open(DATA_DIR / 'station_usage.json') as f:
        data = json.load(f)

    usage = {}
    for s in data['stations']:
        norm_name = normalize_name(s['name'])
        usage[norm_name] = {
            'name': s['name'],
            'annual_usage': s['annual_usage'],
            'daily_avg': s['daily_avg'],
            'source': 'Wikipedia Tube'
        }

    return usage


def load_dlr_usage():
    """Load DLR usage data."""
    try:
        with open(DATA_DIR / 'dlr_usage.json') as f:
            data = json.load(f)

        usage = {}
        for s in data['stations']:
            norm_name = normalize_name(s['name'])
            # Handle special cases
            if 'bank' in norm_name and 'monument' in norm_name:
                norm_name = 'bank'  # Will match Bank station
            if 'stratford' in norm_name and 'high' in norm_name:
                norm_name = 'stratford'  # Stratford High Level -> Stratford
            if 'canning town' in norm_name and 'high' in norm_name:
                norm_name = 'canning town'

            usage[norm_name] = {
                'name': s['name'],
                'annual_usage': s['annual_usage'],
                'daily_avg': s['daily_avg'],
                'source': 'Wikipedia DLR'
            }

        return usage
    except FileNotFoundError:
        return {}


def load_orr_usage():
    """Load ORR station usage data for Overground/Elizabeth."""
    try:
        with open(DATA_DIR / 'orr_london_usage.json') as f:
            data = json.load(f)

        usage = {}
        for s in data['stations']:
            owner = s.get('owner', '').lower()
            # Only include Overground and Elizabeth line stations
            if 'overground' in owner or 'elizabeth' in owner:
                norm_name = normalize_name(s['name'])
                usage[norm_name] = {
                    'name': s['name'],
                    'annual_usage': s['annual_usage'],
                    'daily_avg': s['daily_avg'],
                    'source': f"ORR ({s['owner']})"
                }

        return usage
    except FileNotFoundError:
        return {}


def merge_usage_data():
    """Merge all usage data sources."""
    print("=" * 70)
    print("MERGING USAGE DATA FROM ALL SOURCES")
    print("=" * 70)

    # Load all sources
    print("\n1. Loading usage data sources...")
    tube_usage = load_tube_usage()
    print(f"   Tube (Wikipedia): {len(tube_usage)} stations")

    dlr_usage = load_dlr_usage()
    print(f"   DLR (Wikipedia): {len(dlr_usage)} stations")

    orr_usage = load_orr_usage()
    print(f"   Overground/Elizabeth (ORR): {len(orr_usage)} stations")

    # Merge into one lookup (prioritize: ORR > DLR > Tube for overlapping stations)
    merged = {}

    # Start with Tube data
    for name, data in tube_usage.items():
        merged[name] = data

    # Add DLR data (overwrites if same station)
    for name, data in dlr_usage.items():
        if name not in merged or data['annual_usage'] > merged[name]['annual_usage']:
            merged[name] = data

    # Add ORR data (best source for Overground/Elizabeth)
    for name, data in orr_usage.items():
        if name not in merged or 'ORR' not in merged[name].get('source', ''):
            merged[name] = data

    print(f"\n   Total merged: {len(merged)} unique stations")

    # Load TfL station data and match
    print("\n2. Matching with TfL station data...")
    with open(DATA_DIR / 'tube_stations_enhanced.json') as f:
        enhanced_data = json.load(f)

    stations = enhanced_data['stations']

    # Match and update
    matched = 0
    updated = 0

    for station in stations:
        norm_name = normalize_name(station['name'])

        if norm_name in merged:
            usage_data = merged[norm_name]

            # Only update if station currently has no usage or new data is from better source
            current_usage = station.get('annual_usage', 0)
            new_usage = usage_data['annual_usage']

            if new_usage > 0:
                if current_usage == 0:
                    updated += 1
                matched += 1

                station['annual_usage'] = new_usage
                station['daily_usage'] = usage_data['daily_avg']
                station['usage_source'] = usage_data['source']

                # Recalculate per-capita
                pop_500 = station.get('population_500m', 0)
                pop_1km = station.get('population_1km', 0)
                daily = usage_data['daily_avg']

                station['usage_per_capita_500m'] = round(daily / pop_500, 2) if pop_500 > 0 else 0
                station['usage_per_capita_1km'] = round(daily / pop_1km, 2) if pop_1km > 0 else 0

    print(f"   Matched: {matched} stations")
    print(f"   Newly updated (had 0): {updated} stations")

    # Reclassify station types with new data
    print("\n3. Reclassifying station types...")

    # Calculate new thresholds
    with_both = [s for s in stations if s.get('annual_usage', 0) > 0 and s.get('population_500m', 0) > 0]

    populations = sorted([s['population_500m'] for s in with_both])
    usages = sorted([s['daily_usage'] for s in with_both])

    pop_threshold = populations[len(populations) // 2] if populations else 5000
    usage_threshold = usages[len(usages) // 2] if usages else 10000

    print(f"   New thresholds - Population: {pop_threshold:,}, Usage: {usage_threshold:,}/day")

    type_counts = {}
    for station in stations:
        pop = station.get('population_500m', 0)
        usage = station.get('daily_usage', 0)

        if usage == 0:
            station_type = 'no_usage_data'
        elif pop == 0:
            station_type = 'no_population_data'
        else:
            high_pop = pop >= pop_threshold
            high_usage = usage >= usage_threshold

            if high_usage and not high_pop:
                station_type = 'commuter_hub'
            elif high_pop and not high_usage:
                station_type = 'residential_hub'
            elif high_pop and high_usage:
                station_type = 'balanced'
            else:
                station_type = 'low_activity'

        station['station_type'] = station_type
        type_counts[station_type] = type_counts.get(station_type, 0) + 1

    print("   Station type distribution:")
    for stype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"      {stype}: {count}")

    # Update thresholds in data
    enhanced_data['thresholds'] = {
        'population_threshold': pop_threshold,
        'usage_threshold': usage_threshold
    }

    # Save updated data
    print("\n4. Saving updated data...")
    with open(DATA_DIR / 'tube_stations_enhanced.json', 'w') as f:
        json.dump(enhanced_data, f, indent=2)
    print(f"   Saved to {DATA_DIR / 'tube_stations_enhanced.json'}")

    # Print coverage summary
    print("\n" + "=" * 70)
    print("COVERAGE SUMMARY")
    print("=" * 70)

    tube_lines = ["bakerloo", "central", "circle", "district", "hammersmith-city",
                  "jubilee", "metropolitan", "northern", "piccadilly", "victoria", "waterloo-city"]

    stats = {
        'tube': {'total': 0, 'with_usage': 0},
        'overground': {'total': 0, 'with_usage': 0},
        'elizabeth': {'total': 0, 'with_usage': 0},
        'dlr': {'total': 0, 'with_usage': 0}
    }

    for s in stations:
        lines = s.get('lines', [])
        usage = s.get('annual_usage', 0)

        if any(l in tube_lines for l in lines):
            stats['tube']['total'] += 1
            if usage > 0:
                stats['tube']['with_usage'] += 1

        if 'london-overground' in lines:
            stats['overground']['total'] += 1
            if usage > 0:
                stats['overground']['with_usage'] += 1

        if 'elizabeth' in lines:
            stats['elizabeth']['total'] += 1
            if usage > 0:
                stats['elizabeth']['with_usage'] += 1

        if 'dlr' in lines:
            stats['dlr']['total'] += 1
            if usage > 0:
                stats['dlr']['with_usage'] += 1

    print(f"\n   {'Mode':<15} {'Total':<10} {'With Usage':<12} {'Coverage'}")
    print(f"   {'-'*15} {'-'*10} {'-'*12} {'-'*10}")
    for mode, data in stats.items():
        coverage = (data['with_usage'] / data['total'] * 100) if data['total'] > 0 else 0
        print(f"   {mode.title():<15} {data['total']:<10} {data['with_usage']:<12} {coverage:.1f}%")

    print("\n" + "=" * 70)

    return stations


if __name__ == '__main__':
    merge_usage_data()
