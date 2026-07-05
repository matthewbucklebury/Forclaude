#!/usr/bin/env python3
"""
Phase 2: Match and integrate TfL station usage data with existing station data.

Handles name variations like:
- "Elephant & Castle" vs "Elephant and Castle"
- "Edgware Road (Bakerloo)" vs "Edgware Road"
- "St. Paul's" vs "St Pauls"
- Combined stations like Bank/Monument
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

    # Remove common suffixes and parenthetical notes
    name = re.sub(r'\s*\([^)]*\)', '', name)  # Remove (Bakerloo), (Circle Line), etc.
    name = re.sub(r'\s*\[[^\]]*\]', '', name)  # Remove [e], [f], etc.

    # Standardize punctuation - handle both & and 'and'
    name = name.replace(' & ', ' and ')
    name = name.replace('&', ' and ')
    name = name.replace("'", '')
    name = name.replace("'", '')
    name = name.replace('.', '')
    name = name.replace('-', ' ')

    # Standardize common variations
    name = name.replace('st ', 'saint ')
    name = re.sub(r'\bst$', 'saint', name)

    # Remove extra whitespace
    name = ' '.join(name.split())

    return name


def build_name_mappings():
    """Build manual mappings for tricky station names."""
    return {
        # Stations with line suffixes in our data
        'edgware road': ['edgware road (bakerloo)', 'edgware road (circle line)'],
        'hammersmith': ['hammersmith (handc line)', 'hammersmith (distandpicc line)'],
        'paddington': ['paddington (handc line)-underground', 'paddington'],
        'shepherds bush': ['shepherds bush (central)'],

        # Combined stations
        'bank and monument': ['bank', 'monument'],

        # Name variations
        'kings cross saint pancras': ['kings cross st pancras', 'kings cross saint pancras'],
        'heathrow terminals 2 and 3': ['heathrow terminals 2 and 3'],
        'heathrow terminal 4': ['heathrow terminal 4'],
        'heathrow terminal 5': ['heathrow terminal 5'],
    }


def match_stations(our_stations, usage_stations):
    """Match our stations to usage data stations."""

    # Build normalized lookup from usage data
    usage_by_name = {}
    for station in usage_stations:
        norm_name = normalize_name(station['name'])
        usage_by_name[norm_name] = station

    # Manual mappings
    manual_mappings = build_name_mappings()

    # Track matches
    matched = []
    unmatched_ours = []

    for station in our_stations:
        our_name = station['name']
        our_norm = normalize_name(our_name)

        usage_match = None

        # Try direct match
        if our_norm in usage_by_name:
            usage_match = usage_by_name[our_norm]
        else:
            # Try manual mappings (reverse lookup)
            for usage_norm, our_variants in manual_mappings.items():
                our_variants_norm = [normalize_name(v) for v in our_variants]
                if our_norm in our_variants_norm:
                    if usage_norm in usage_by_name:
                        usage_match = usage_by_name[usage_norm]
                        break

            # Try partial matching for remaining
            if not usage_match:
                # Check if our name contains a usage name or vice versa
                for usage_norm, usage_data in usage_by_name.items():
                    if our_norm in usage_norm or usage_norm in our_norm:
                        usage_match = usage_data
                        break

        if usage_match:
            matched.append({
                'station': station,
                'usage': usage_match,
                'our_name': our_name,
                'usage_name': usage_match['name']
            })
        else:
            unmatched_ours.append(station)

    return matched, unmatched_ours


def integrate_data():
    """Main integration function."""
    print("=" * 70)
    print("PHASE 2: INTEGRATING STATION USAGE DATA")
    print("=" * 70)

    # Load existing station data
    print("\n1. Loading existing data...")
    with open(DATA_DIR / 'tube_stations.json') as f:
        stations_data = json.load(f)

    with open(DATA_DIR / 'station_usage.json') as f:
        usage_data = json.load(f)

    with open(DATA_DIR / 'analysis_results_500m.json') as f:
        results_500m = json.load(f)

    with open(DATA_DIR / 'analysis_results_1km.json') as f:
        results_1km = json.load(f)

    # Build population lookup
    pop_500m = {s['naptanId']: s['population'] for s in results_500m['stations']}
    pop_1km = {s['naptanId']: s['population'] for s in results_1km['stations']}

    # Filter to Tube-only stations for usage matching
    tube_lines = ["bakerloo", "central", "circle", "district", "hammersmith-city",
                  "jubilee", "metropolitan", "northern", "piccadilly", "victoria", "waterloo-city"]

    all_stations = stations_data['stations']
    tube_stations = [s for s in all_stations if any(l in tube_lines for l in s['lines'])]

    print(f"   Total stations: {len(all_stations)}")
    print(f"   Tube stations: {len(tube_stations)}")
    print(f"   Usage data stations: {len(usage_data['stations'])}")

    # Match stations
    print("\n2. Matching stations...")
    matched, unmatched = match_stations(tube_stations, usage_data['stations'])

    print(f"   Matched: {len(matched)}")
    print(f"   Unmatched: {len(unmatched)}")

    if unmatched:
        print("\n   Unmatched stations from our data:")
        for s in unmatched[:20]:
            print(f"      - {s['name']}")

    # Build usage lookup by naptanId
    usage_by_naptan = {}
    for match in matched:
        naptan_id = match['station']['naptanId']
        usage_by_naptan[naptan_id] = match['usage']

    # Enhance all stations with usage data
    print("\n3. Enhancing station data...")
    enhanced_stations = []

    for station in all_stations:
        naptan_id = station['naptanId']

        # Get population data
        population_500m = pop_500m.get(naptan_id, 0)
        population_1km = pop_1km.get(naptan_id, 0)

        # Get usage data (only for Tube stations)
        usage = usage_by_naptan.get(naptan_id)

        if usage:
            annual_usage = usage['annual_usage']
            daily_usage = usage['daily_avg']
        else:
            annual_usage = 0
            daily_usage = 0

        # Calculate per-capita metrics
        usage_per_capita_500m = round(daily_usage / population_500m, 2) if population_500m > 0 else 0
        usage_per_capita_1km = round(daily_usage / population_1km, 2) if population_1km > 0 else 0

        enhanced = {
            **station,
            'population_500m': population_500m,
            'population_1km': population_1km,
            'annual_usage': annual_usage,
            'daily_usage': daily_usage,
            'usage_per_capita_500m': usage_per_capita_500m,
            'usage_per_capita_1km': usage_per_capita_1km
        }

        enhanced_stations.append(enhanced)

    # Save enhanced data
    print("\n4. Saving enhanced station data...")

    enhanced_data = {
        'source': 'TfL API + Wikipedia Usage Data (2024)',
        'stations': enhanced_stations,
        'line_colors': stations_data['line_colors']
    }

    with open(DATA_DIR / 'tube_stations_enhanced.json', 'w') as f:
        json.dump(enhanced_data, f, indent=2)

    print(f"   Saved to data/tube_stations_enhanced.json")

    # Statistics
    print("\n5. Integration statistics:")
    with_usage = [s for s in enhanced_stations if s['annual_usage'] > 0]
    with_pop = [s for s in enhanced_stations if s['population_500m'] > 0]
    with_both = [s for s in enhanced_stations if s['annual_usage'] > 0 and s['population_500m'] > 0]

    print(f"   Stations with usage data: {len(with_usage)}")
    print(f"   Stations with population data: {len(with_pop)}")
    print(f"   Stations with both: {len(with_both)}")

    # Top by usage per capita
    print("\n   Top 10 by usage per capita (500m):")
    sorted_by_ratio = sorted(with_both, key=lambda x: x['usage_per_capita_500m'], reverse=True)
    for s in sorted_by_ratio[:10]:
        print(f"      {s['name']}: {s['usage_per_capita_500m']:.1f}x (daily: {s['daily_usage']:,}, pop: {s['population_500m']:,})")

    print("\n   Bottom 10 by usage per capita (500m) - with both metrics:")
    for s in sorted_by_ratio[-10:]:
        print(f"      {s['name']}: {s['usage_per_capita_500m']:.1f}x (daily: {s['daily_usage']:,}, pop: {s['population_500m']:,})")

    print("\n" + "=" * 70)
    print("PHASE 2 COMPLETE")
    print("=" * 70)

    return enhanced_stations


if __name__ == '__main__':
    integrate_data()
