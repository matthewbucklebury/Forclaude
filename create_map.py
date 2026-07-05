#!/usr/bin/env python3
"""
Create an interactive map showing London TfL rail station catchment populations.
Includes Tube, Overground, Elizabeth Line, and DLR.
Enhanced version with student-friendly UX features.
"""

import json
import folium
from folium import plugins
from pathlib import Path
import branca.colormap as cm

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent


def load_analysis_results():
    """Load 1km analysis results."""
    with open(DATA_DIR / "analysis_results_1km.json") as f:
        return json.load(f)


def load_enhanced_stations():
    """Load enhanced station data with usage information."""
    enhanced_file = DATA_DIR / "tube_stations_enhanced.json"
    if enhanced_file.exists():
        with open(enhanced_file) as f:
            return json.load(f)
    return None


def get_line_color(station, line_stats):
    """Get the primary line color for a station."""
    if station["lines"]:
        sorted_lines = sorted(
            station["lines"],
            key=lambda l: line_stats.get(l, {}).get("total_population", 0),
            reverse=True
        )
        return line_stats.get(sorted_lines[0], {}).get("color", "#666666")
    return "#666666"


def calculate_station_rankings(stations):
    """Calculate rankings for all 4 station type categories."""
    valid_stations = [s for s in stations if s['population_1km'] > 0 and s['daily_usage'] > 0]

    commuter_ranked = sorted(valid_stations,
                            key=lambda s: s['daily_usage'] / s['population_1km'],
                            reverse=True)[:10]

    residential_ranked = sorted(valid_stations,
                               key=lambda s: s['population_1km'] / s['daily_usage'],
                               reverse=True)[:10]

    balanced_ranked = sorted(valid_stations,
                            key=lambda s: abs(1.0 - (s['daily_usage'] / s['population_1km'])))[:10]

    low_activity_ranked = sorted(valid_stations,
                                key=lambda s: s['population_1km'] + s['daily_usage'])[:10]

    return {
        'commuter': commuter_ranked,
        'residential': residential_ranked,
        'balanced': balanced_ranked,
        'low_activity': low_activity_ranked
    }


def calculate_line_usage(stations, line_stats):
    """Calculate total daily usage per line."""
    line_usage = {}
    for line_id in line_stats.keys():
        total_usage = sum(s['daily_usage'] for s in stations if line_id in s.get('lines', []))
        line_usage[line_id] = total_usage
    return line_usage


def calculate_summary_stats(station_data):
    """Calculate summary statistics for the dashboard."""
    total_stations = len(station_data)
    total_population = sum(s['population_1km'] for s in station_data)
    total_daily_usage = sum(s['daily_usage'] for s in station_data)

    stations_with_usage = [s for s in station_data if s['daily_usage'] > 0]
    avg_usage = total_daily_usage / len(stations_with_usage) if stations_with_usage else 0

    max_pop_station = max(station_data, key=lambda s: s['population_1km'])
    max_usage_station = max(station_data, key=lambda s: s['daily_usage'])

    type_counts = {}
    for s in station_data:
        t = s['station_type']
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        'total_stations': total_stations,
        'total_population': total_population,
        'total_daily_usage': total_daily_usage,
        'avg_daily_usage': int(avg_usage),
        'max_pop_station': max_pop_station['name'],
        'max_pop_value': max_pop_station['population_1km'],
        'max_usage_station': max_usage_station['name'],
        'max_usage_value': max_usage_station['daily_usage'],
        'type_counts': type_counts
    }


def create_map(results_1km, enhanced_data=None):
    """Create the interactive Folium map with enhanced UX."""
    print("Creating interactive map with enhanced UX...")

    stations_1km = {s["naptanId"]: s for s in results_1km["stations"]}
    line_stats = results_1km["line_stats"]
    line_colors = results_1km["line_colors"]

    enhanced_lookup = {}
    if enhanced_data:
        enhanced_lookup = {s["naptanId"]: s for s in enhanced_data.get("stations", [])}
        print(f"  Loaded usage data for {len(enhanced_lookup)} stations")

    type_colors = {
        'commuter_hub': {
            'main': '#1E5A8E',
            'light': '#3498DB',
            'accent': '#5DADE2'
        },
        'residential_hub': {
            'main': '#0D7A4F',
            'light': '#27AE60',
            'accent': '#58D68D'
        },
        'balanced': {
            'main': '#6C3483',
            'light': '#8E44AD',
            'accent': '#BB8FCE'
        },
        'low_activity': {
            'main': '#BA4A00',
            'light': '#E67E22',
            'accent': '#F39C12'
        },
        'no_usage_data': {
            'main': '#7F8C8D',
            'light': '#95A5A6',
            'accent': '#BDC3C7'
        },
        'no_population_data': {
            'main': '#95A5A6',
            'light': '#BDC3C7',
            'accent': '#ECF0F1'
        }
    }

    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'
    )

    station_data = []

    for naptan_id, s1km in stations_1km.items():
        if s1km["lat"] is None or s1km["lon"] is None:
            continue

        line_color = get_line_color(s1km, line_stats)
        line_names = [lid.replace("-", " ").title() for lid in s1km.get("lines", [])]
        lines_text = ", ".join(line_names) if line_names else "Unknown"

        enhanced = enhanced_lookup.get(naptan_id, {})
        annual_usage = enhanced.get('annual_usage', 0)
        daily_usage = enhanced.get('daily_usage', 0)
        usage_per_capita = enhanced.get('usage_per_capita_1km', 0)
        station_type = enhanced.get('station_type', 'no_usage_data')

        type_color_set = type_colors.get(station_type, type_colors['no_usage_data'])

        station_entry = {
            'naptanId': naptan_id,
            'lat': s1km['lat'],
            'lon': s1km['lon'],
            'name': s1km['name'],
            'lines': s1km.get('lines', []),
            'lines_text': lines_text,
            'population_1km': s1km['population'],
            'line_color': line_color,
            'annual_usage': annual_usage,
            'daily_usage': daily_usage,
            'usage_per_capita': usage_per_capita,
            'station_type': station_type,
            'type_color_main': type_color_set['main'],
            'type_color_light': type_color_set['light'],
            'type_color_accent': type_color_set['accent']
        }

        station_data.append(station_entry)

    line_usage = calculate_line_usage(station_data, line_stats)
    rankings = calculate_station_rankings(station_data)
    summary_stats = calculate_summary_stats(station_data)

    js_stations = json.dumps(station_data)
    js_line_stats = json.dumps({lid: {
        'name': stats['name'],
        'color': stats['color'],
        'station_count': stats['station_count'],
        'total_population': stats['total_population'],
        'daily_usage': line_usage.get(lid, 0)
    } for lid, stats in line_stats.items()})

    formatted_rankings = {
        'commuter': [{'name': s['name'], 'population': s['population_1km'],
                     'usage': s['daily_usage'],
                     'ratio': round(s['daily_usage'] / s['population_1km'], 1) if s['population_1km'] > 0 else 0}
                    for s in rankings['commuter']],
        'residential': [{'name': s['name'], 'population': s['population_1km'],
                        'usage': s['daily_usage'],
                        'ratio': round(s['population_1km'] / s['daily_usage'], 1) if s['daily_usage'] > 0 else 0}
                       for s in rankings['residential']],
        'balanced': [{'name': s['name'], 'population': s['population_1km'],
                     'usage': s['daily_usage'],
                     'ratio': round(s['daily_usage'] / s['population_1km'], 2) if s['population_1km'] > 0 else 0}
                    for s in rankings['balanced']],
        'low_activity': [{'name': s['name'], 'population': s['population_1km'],
                         'usage': s['daily_usage'],
                         'combined': s['population_1km'] + s['daily_usage']}
                        for s in rankings['low_activity']]
    }
    js_rankings = json.dumps(formatted_rankings)
    js_type_colors = json.dumps(type_colors)
    js_summary_stats = json.dumps(summary_stats)

    # Fun facts for students
    fun_facts = [
        f"The busiest station ({summary_stats['max_usage_station']}) sees {summary_stats['max_usage_value']:,} people daily - that's like filling Wembley Stadium!",
        f"Total catchment population: {summary_stats['total_population']:,} people live within 1km of a TfL station",
        f"The London Underground is the world's oldest metro system, opened in 1863",
        f"If you walked 1km from every station, you'd cover {summary_stats['total_stations']}km - about the distance from London to Edinburgh!",
        f"Daily usage across all stations: {summary_stats['total_daily_usage']:,} journeys",
        "The Victoria line is the fastest, averaging 50mph between stations",
        "Bank station has more escalators (15) than any other station on the network",
        f"Average station sees {summary_stats['avg_daily_usage']:,} passengers per day"
    ]
    js_fun_facts = json.dumps(fun_facts)

    main_script = f"""
    <script src="https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/leaflet-image@0.4.0/leaflet-image.js"></script>

    <style>
    :root {{
        --primary: #1E5A8E;
        --success: #0D7A4F;
        --warning: #E67E22;
        --danger: #E74C3C;
        --bg-light: #ffffff;
        --bg-dark: #1a1a2e;
        --text-light: #333333;
        --text-dark: #e0e0e0;
        --card-light: #ffffff;
        --card-dark: #16213e;
        --border-light: #e0e0e0;
        --border-dark: #0f3460;
    }}

    body.dark-mode {{
        background: var(--bg-dark);
    }}

    body.dark-mode .leaflet-container {{
        background: var(--bg-dark);
    }}

    /* Welcome Modal */
    .welcome-modal {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.8);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        opacity: 1;
        transition: opacity 0.3s ease;
    }}

    .welcome-modal.hidden {{
        opacity: 0;
        pointer-events: none;
    }}

    .welcome-content {{
        background: white;
        border-radius: 16px;
        padding: 30px;
        max-width: 600px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        animation: slideUp 0.4s ease;
    }}

    @keyframes slideUp {{
        from {{ transform: translateY(30px); opacity: 0; }}
        to {{ transform: translateY(0); opacity: 1; }}
    }}

    .welcome-content h1 {{
        margin: 0 0 10px 0;
        font-size: 28px;
        background: linear-gradient(135deg, #1E5A8E, #27AE60);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}

    .welcome-content .subtitle {{
        color: #666;
        margin-bottom: 20px;
        font-size: 14px;
    }}

    .feature-grid {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 15px;
        margin: 20px 0;
    }}

    .feature-item {{
        background: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }}

    .feature-item .icon {{
        font-size: 24px;
        margin-bottom: 8px;
    }}

    .feature-item h4 {{
        margin: 0 0 5px 0;
        font-size: 13px;
        color: #333;
    }}

    .feature-item p {{
        margin: 0;
        font-size: 11px;
        color: #666;
    }}

    .start-btn {{
        width: 100%;
        padding: 15px;
        background: linear-gradient(135deg, #1E5A8E, #27AE60);
        color: white;
        border: none;
        border-radius: 10px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
    }}

    .start-btn:hover {{
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(30, 90, 142, 0.4);
    }}

    .keyboard-hint {{
        text-align: center;
        margin-top: 15px;
        font-size: 11px;
        color: #888;
    }}

    .keyboard-hint kbd {{
        background: #eee;
        padding: 2px 6px;
        border-radius: 4px;
        font-family: monospace;
        border: 1px solid #ddd;
    }}

    /* Stats Dashboard */
    .stats-dashboard {{
        position: fixed;
        top: 10px;
        left: 60px;
        z-index: 1000;
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        font-family: Arial, sans-serif;
        max-width: 380px;
        transition: all 0.3s ease;
    }}

    body.dark-mode .stats-dashboard {{
        background: var(--card-dark);
        color: var(--text-dark);
    }}

    .stats-dashboard.collapsed {{
        max-width: 50px;
        padding: 10px;
        cursor: pointer;
    }}

    .stats-dashboard.collapsed .dashboard-content {{
        display: none;
    }}

    .dashboard-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
    }}

    .dashboard-header h2 {{
        margin: 0;
        font-size: 16px;
        color: #333;
    }}

    body.dark-mode .dashboard-header h2 {{
        color: var(--text-dark);
    }}

    .toggle-dashboard {{
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        padding: 5px;
        border-radius: 5px;
        transition: background 0.2s;
    }}

    .toggle-dashboard:hover {{
        background: #f0f0f0;
    }}

    .stat-cards {{
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        margin-bottom: 12px;
    }}

    .stat-card {{
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding: 12px;
        border-radius: 10px;
        text-align: center;
    }}

    body.dark-mode .stat-card {{
        background: linear-gradient(135deg, #0f3460, #16213e);
    }}

    .stat-card .stat-value {{
        font-size: 20px;
        font-weight: 700;
        color: #1E5A8E;
        margin-bottom: 4px;
    }}

    .stat-card .stat-label {{
        font-size: 10px;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    body.dark-mode .stat-card .stat-label {{
        color: #aaa;
    }}

    .fun-fact-box {{
        background: linear-gradient(135deg, #fff3e0, #ffe0b2);
        border-left: 4px solid #E67E22;
        padding: 12px;
        border-radius: 0 10px 10px 0;
        margin-top: 10px;
    }}

    body.dark-mode .fun-fact-box {{
        background: linear-gradient(135deg, #3d2914, #2d1f0f);
    }}

    .fun-fact-box .fact-label {{
        font-size: 10px;
        color: #E67E22;
        font-weight: 600;
        margin-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 5px;
    }}

    .fun-fact-box .fact-text {{
        font-size: 12px;
        color: #333;
        line-height: 1.4;
    }}

    body.dark-mode .fun-fact-box .fact-text {{
        color: var(--text-dark);
    }}

    /* Search Box */
    .search-container {{
        position: relative;
        margin-bottom: 15px;
    }}

    .search-input {{
        width: 100%;
        padding: 12px 15px 12px 40px;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        font-size: 14px;
        transition: all 0.2s;
        box-sizing: border-box;
    }}

    .search-input:focus {{
        outline: none;
        border-color: #1E5A8E;
        box-shadow: 0 0 0 3px rgba(30, 90, 142, 0.1);
    }}

    body.dark-mode .search-input {{
        background: var(--card-dark);
        border-color: var(--border-dark);
        color: var(--text-dark);
    }}

    .search-icon {{
        position: absolute;
        left: 14px;
        top: 50%;
        transform: translateY(-50%);
        color: #999;
        font-size: 16px;
    }}

    .search-results {{
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-top: 5px;
        max-height: 250px;
        overflow-y: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        z-index: 100;
        display: none;
    }}

    .search-results.visible {{
        display: block;
    }}

    body.dark-mode .search-results {{
        background: var(--card-dark);
        border-color: var(--border-dark);
    }}

    .search-result-item {{
        padding: 12px 15px;
        cursor: pointer;
        border-bottom: 1px solid #f0f0f0;
        transition: background 0.2s;
    }}

    .search-result-item:hover {{
        background: #f8f9fa;
    }}

    body.dark-mode .search-result-item:hover {{
        background: var(--border-dark);
    }}

    .search-result-item:last-child {{
        border-bottom: none;
    }}

    .search-result-item .station-name {{
        font-weight: 600;
        font-size: 13px;
        color: #333;
    }}

    body.dark-mode .search-result-item .station-name {{
        color: var(--text-dark);
    }}

    .search-result-item .station-lines {{
        font-size: 11px;
        color: #666;
        margin-top: 3px;
    }}

    /* Dark mode toggle */
    .dark-mode-toggle {{
        position: fixed;
        bottom: 20px;
        left: 20px;
        z-index: 1000;
        background: white;
        border: none;
        padding: 12px;
        border-radius: 50%;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        cursor: pointer;
        font-size: 20px;
        transition: all 0.3s;
    }}

    .dark-mode-toggle:hover {{
        transform: scale(1.1);
    }}

    body.dark-mode .dark-mode-toggle {{
        background: var(--card-dark);
    }}

    /* Keyboard shortcuts panel */
    .shortcuts-panel {{
        position: fixed;
        bottom: 80px;
        left: 20px;
        z-index: 1000;
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
        font-size: 12px;
        display: none;
        min-width: 200px;
    }}

    .shortcuts-panel.visible {{
        display: block;
        animation: fadeIn 0.2s ease;
    }}

    body.dark-mode .shortcuts-panel {{
        background: var(--card-dark);
        color: var(--text-dark);
    }}

    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .shortcuts-panel h4 {{
        margin: 0 0 10px 0;
        font-size: 13px;
        color: #333;
    }}

    body.dark-mode .shortcuts-panel h4 {{
        color: var(--text-dark);
    }}

    .shortcut-item {{
        display: flex;
        justify-content: space-between;
        padding: 5px 0;
    }}

    .shortcut-item kbd {{
        background: #f0f0f0;
        padding: 3px 8px;
        border-radius: 4px;
        font-family: monospace;
        font-size: 11px;
        border: 1px solid #ddd;
    }}

    body.dark-mode .shortcut-item kbd {{
        background: var(--border-dark);
        border-color: #444;
    }}

    /* Station tooltip */
    .station-tooltip {{
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.15);
        padding: 0;
    }}

    /* Legend panel */
    #legend-panel {{
        transition: all 0.3s ease;
    }}

    body.dark-mode #legend-panel {{
        background: var(--card-dark) !important;
        color: var(--text-dark);
    }}

    body.dark-mode #legend-panel h3,
    body.dark-mode #legend-panel h4 {{
        color: var(--text-dark) !important;
    }}

    body.dark-mode #legend-panel p {{
        color: #aaa !important;
    }}

    /* Radio button filter styles */
    .station-type-filter {{
        margin: 10px 0;
        padding: 12px;
        background: #f8f9fa;
        border-radius: 10px;
    }}

    body.dark-mode .station-type-filter {{
        background: var(--border-dark);
    }}

    .station-type-filter h4 {{
        margin: 0 0 10px 0;
        font-size: 12px;
        color: #333;
    }}

    .station-type-filter label {{
        display: flex;
        align-items: center;
        padding: 8px 10px;
        margin: 4px 0;
        cursor: pointer;
        font-size: 12px;
        border-radius: 8px;
        transition: all 0.2s ease;
    }}

    .station-type-filter label:hover {{
        background: #e9ecef;
    }}

    body.dark-mode .station-type-filter label:hover {{
        background: rgba(255,255,255,0.1);
    }}

    .station-type-filter label.selected {{
        background: #e3f2fd;
        font-weight: 500;
    }}

    body.dark-mode .station-type-filter label.selected {{
        background: rgba(30, 90, 142, 0.3);
    }}

    .station-type-filter input[type="radio"] {{
        margin-right: 10px;
        cursor: pointer;
    }}

    .type-color-dot {{
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        margin-right: 10px;
        border: 2px solid rgba(0,0,0,0.15);
    }}

    /* Clear filter button */
    .clear-filter-btn {{
        width: 100%;
        padding: 10px;
        margin-top: 10px;
        background: #ECF0F1;
        border: 1px solid #BDC3C7;
        border-radius: 8px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s ease;
        display: none;
    }}

    .clear-filter-btn:hover {{
        background: #BDC3C7;
    }}

    .clear-filter-btn.visible {{
        display: block;
    }}

    /* Viz mode toggle */
    .viz-mode-toggle {{
        margin: 15px 0;
        padding: 12px;
        background: #fff3e0;
        border-radius: 10px;
        border: 1px solid #ffe0b2;
    }}

    body.dark-mode .viz-mode-toggle {{
        background: rgba(230, 126, 34, 0.15);
        border-color: rgba(230, 126, 34, 0.3);
    }}

    .viz-mode-toggle h4 {{
        margin: 0 0 10px 0;
        font-size: 12px;
        color: #e65100;
    }}

    .viz-mode-toggle label {{
        display: flex;
        align-items: center;
        padding: 6px 8px;
        margin: 3px 0;
        cursor: pointer;
        font-size: 11px;
        border-radius: 6px;
        transition: background 0.2s;
    }}

    .viz-mode-toggle label:hover {{
        background: #ffe0b2;
    }}

    body.dark-mode .viz-mode-toggle label:hover {{
        background: rgba(230, 126, 34, 0.2);
    }}

    .viz-mode-toggle label.selected {{
        background: #ffcc80;
        font-weight: 500;
    }}

    body.dark-mode .viz-mode-toggle label.selected {{
        background: rgba(230, 126, 34, 0.4);
    }}

    .viz-mode-toggle input[type="radio"] {{
        margin-right: 8px;
    }}

    /* Heatmap legend */
    .heatmap-legend {{
        display: none;
        margin: 10px 0;
        padding: 12px;
        background: #fafafa;
        border-radius: 8px;
    }}

    body.dark-mode .heatmap-legend {{
        background: var(--border-dark);
    }}

    .heatmap-legend.visible {{
        display: block;
    }}

    .heatmap-legend h5 {{
        margin: 0 0 8px 0;
        font-size: 11px;
    }}

    .gradient-bar {{
        height: 16px;
        border-radius: 4px;
        margin-bottom: 5px;
    }}

    .gradient-bar.population {{
        background: linear-gradient(to right, #ffffcc, #c7e9b4, #7fcdbb, #41b6c4, #2c7fb8, #253494);
    }}

    .gradient-bar.usage {{
        background: linear-gradient(to right, #fff5f0, #fee0d2, #fcbba1, #fc9272, #fb6a4a, #a50f15);
    }}

    .gradient-labels {{
        display: flex;
        justify-content: space-between;
        font-size: 10px;
        color: #666;
    }}

    /* Export controls */
    .export-controls {{
        margin: 15px 0;
        padding: 12px;
        background: #e8f5e9;
        border-radius: 10px;
        border: 1px solid #c8e6c9;
    }}

    body.dark-mode .export-controls {{
        background: rgba(39, 174, 96, 0.15);
        border-color: rgba(39, 174, 96, 0.3);
    }}

    .export-controls h4 {{
        margin: 0 0 10px 0;
        font-size: 12px;
        color: #2e7d32;
    }}

    .export-btn {{
        width: 100%;
        padding: 10px 12px;
        margin: 4px 0;
        background: white;
        border: 1px solid #a5d6a7;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s;
        text-align: center;
    }}

    .export-btn:hover {{
        background: #c8e6c9;
    }}

    .export-btn:disabled {{
        opacity: 0.6;
        cursor: not-allowed;
    }}

    /* Collapsible sections */
    .collapsible {{
        cursor: pointer;
        padding: 12px;
        background: #f0f0f0;
        border: none;
        text-align: left;
        width: 100%;
        font-size: 12px;
        font-weight: 600;
        border-radius: 8px;
        margin-top: 10px;
        transition: background 0.2s;
    }}

    body.dark-mode .collapsible {{
        background: var(--border-dark);
        color: var(--text-dark);
    }}

    .collapsible:hover {{
        background: #e0e0e0;
    }}

    body.dark-mode .collapsible:hover {{
        background: rgba(255,255,255,0.1);
    }}

    .collapsible:before {{
        content: '\\25B6 ';
        font-size: 10px;
    }}

    .collapsible.active:before {{
        content: '\\25BC ';
    }}

    .collapse-content {{
        display: none;
        padding: 12px;
        background: #fafafa;
        border-radius: 0 0 8px 8px;
        font-size: 11px;
    }}

    body.dark-mode .collapse-content {{
        background: var(--border-dark);
    }}

    .collapse-content.show {{
        display: block;
    }}

    .ranking-item {{
        padding: 8px 0;
        border-bottom: 1px solid #eee;
    }}

    body.dark-mode .ranking-item {{
        border-color: #333;
    }}

    .ranking-item:last-child {{
        border-bottom: none;
    }}

    /* Filter status */
    .filter-status {{
        padding: 10px;
        background: #e3f2fd;
        border-radius: 8px;
        margin-bottom: 10px;
        font-size: 12px;
        color: #1565c0;
        display: none;
    }}

    body.dark-mode .filter-status {{
        background: rgba(30, 90, 142, 0.2);
        color: #5DADE2;
    }}

    .filter-status.visible {{
        display: block;
    }}

    /* Mobile responsive */
    @media (max-width: 768px) {{
        .stats-dashboard {{
            left: 10px;
            max-width: calc(100% - 20px);
            top: auto;
            bottom: 80px;
        }}

        #legend-panel {{
            width: 280px !important;
            max-height: 60vh !important;
        }}

        .feature-grid {{
            grid-template-columns: 1fr;
        }}

        .welcome-content {{
            margin: 20px;
            padding: 20px;
        }}
    }}

    /* Loading overlay */
    .loading-overlay {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: white;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        transition: opacity 0.5s ease;
    }}

    .loading-overlay.hidden {{
        opacity: 0;
        pointer-events: none;
    }}

    .loading-spinner {{
        width: 50px;
        height: 50px;
        border: 4px solid #f0f0f0;
        border-top-color: #1E5A8E;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }}

    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}

    .loading-text {{
        margin-top: 20px;
        font-family: Arial, sans-serif;
        color: #666;
        font-size: 14px;
    }}

    /* Comparison mode */
    .comparison-panel {{
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: white;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        display: none;
        font-family: Arial, sans-serif;
    }}

    .comparison-panel.visible {{
        display: flex;
        gap: 30px;
        align-items: center;
        animation: slideUp 0.3s ease;
    }}

    body.dark-mode .comparison-panel {{
        background: var(--card-dark);
        color: var(--text-dark);
    }}

    .comparison-station {{
        text-align: center;
        min-width: 150px;
    }}

    .comparison-station .name {{
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 8px;
    }}

    .comparison-station .stats {{
        font-size: 12px;
        color: #666;
    }}

    .comparison-vs {{
        font-size: 18px;
        font-weight: bold;
        color: #999;
    }}

    .comparison-close {{
        position: absolute;
        top: 8px;
        right: 12px;
        background: none;
        border: none;
        font-size: 18px;
        cursor: pointer;
        color: #999;
    }}
    </style>

    <!-- Loading Overlay -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">Loading London TfL Map...</div>
    </div>

    <!-- Welcome Modal -->
    <div class="welcome-modal" id="welcomeModal">
        <div class="welcome-content">
            <h1>London Transport Explorer</h1>
            <p class="subtitle">Discover population patterns around TfL stations using real census and usage data</p>

            <div class="feature-grid">
                <div class="feature-item">
                    <div class="icon">&#x1F50D;</div>
                    <h4>Search Stations</h4>
                    <p>Find any of 473 stations instantly</p>
                </div>
                <div class="feature-item">
                    <div class="icon">&#x1F3AF;</div>
                    <h4>Filter by Type</h4>
                    <p>Commuter, residential, balanced, or low activity</p>
                </div>
                <div class="feature-item">
                    <div class="icon">&#x1F525;</div>
                    <h4>Heatmaps</h4>
                    <p>Visualize population and usage density</p>
                </div>
                <div class="feature-item">
                    <div class="icon">&#x1F4CA;</div>
                    <h4>Statistics</h4>
                    <p>Real data from 2021 Census + 2024 TfL</p>
                </div>
            </div>

            <button class="start-btn" id="startExploring">Start Exploring</button>

            <p class="keyboard-hint">
                Pro tip: Press <kbd>?</kbd> for keyboard shortcuts, <kbd>/</kbd> to search
            </p>
        </div>
    </div>

    <!-- Dark Mode Toggle -->
    <button class="dark-mode-toggle" id="darkModeToggle" title="Toggle dark mode">&#x1F319;</button>

    <!-- Keyboard Shortcuts Panel -->
    <div class="shortcuts-panel" id="shortcutsPanel">
        <h4>Keyboard Shortcuts</h4>
        <div class="shortcut-item"><span>Search</span><kbd>/</kbd></div>
        <div class="shortcut-item"><span>Reset filters</span><kbd>Esc</kbd></div>
        <div class="shortcut-item"><span>Toggle dark mode</span><kbd>D</kbd></div>
        <div class="shortcut-item"><span>Next fun fact</span><kbd>F</kbd></div>
        <div class="shortcut-item"><span>Export PNG</span><kbd>E</kbd></div>
        <div class="shortcut-item"><span>Close this</span><kbd>?</kbd></div>
    </div>

    <!-- Comparison Panel -->
    <div class="comparison-panel" id="comparisonPanel">
        <button class="comparison-close" id="closeComparison">&times;</button>
        <div class="comparison-station" id="compStation1">
            <div class="name">-</div>
            <div class="stats">Click a station to compare</div>
        </div>
        <div class="comparison-vs">VS</div>
        <div class="comparison-station" id="compStation2">
            <div class="name">-</div>
            <div class="stats">Click another station</div>
        </div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        // Hide loading after a short delay
        setTimeout(function() {{
            document.getElementById('loadingOverlay').classList.add('hidden');
        }}, 800);

        // Welcome modal
        var welcomeModal = document.getElementById('welcomeModal');
        var startBtn = document.getElementById('startExploring');

        // Check if user has seen welcome before
        if (localStorage.getItem('tflMapWelcomeSeen')) {{
            welcomeModal.classList.add('hidden');
        }}

        startBtn.addEventListener('click', function() {{
            welcomeModal.classList.add('hidden');
            localStorage.setItem('tflMapWelcomeSeen', 'true');
        }});

        // Dark mode
        var darkModeToggle = document.getElementById('darkModeToggle');
        var isDarkMode = localStorage.getItem('tflMapDarkMode') === 'true';

        if (isDarkMode) {{
            document.body.classList.add('dark-mode');
            darkModeToggle.textContent = '\\u2600\\uFE0F';
        }}

        darkModeToggle.addEventListener('click', function() {{
            document.body.classList.toggle('dark-mode');
            isDarkMode = document.body.classList.contains('dark-mode');
            localStorage.setItem('tflMapDarkMode', isDarkMode);
            darkModeToggle.textContent = isDarkMode ? '\\u2600\\uFE0F' : '\\u1F319';
        }});

        // Keyboard shortcuts panel
        var shortcutsPanel = document.getElementById('shortcutsPanel');

        function initializeWhenReady() {{
            var mapElement = document.querySelector('.folium-map');
            if (!mapElement) {{
                setTimeout(initializeWhenReady, 100);
                return;
            }}

            var mapId = mapElement.id;
            var map = window[mapId];
            if (!map) {{
                for (var key in window) {{
                    if (window[key] && window[key]._leaflet_id && window[key].getCenter) {{
                        map = window[key];
                        break;
                    }}
                }}
            }}

            if (!map) {{
                setTimeout(initializeWhenReady, 100);
                return;
            }}

            console.log('Map ready, initializing enhanced controls...');

            var stations = {js_stations};
            var lineStats = {js_line_stats};
            var rankings = {js_rankings};
            var typeColors = {js_type_colors};
            var summaryStats = {js_summary_stats};
            var funFacts = {js_fun_facts};

            var stationLayers = [];
            var currentFilter = 'all';
            var currentVizMode = 'markers';
            var populationHeat = null;
            var usageHeat = null;
            var currentFactIndex = 0;
            var comparisonMode = false;
            var comparisonStations = [];

            function formatNumber(num) {{
                return num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ",");
            }}

            function getTypeLabel(type) {{
                var labels = {{
                    'commuter_hub': 'Commuter Hub',
                    'residential_hub': 'Residential Area',
                    'balanced': 'Balanced',
                    'low_activity': 'Low Activity',
                    'no_usage_data': 'No Data',
                    'no_population_data': 'No Pop Data'
                }};
                return labels[type] || type;
            }}

            // Update fun fact
            function updateFunFact() {{
                var factText = document.querySelector('.fact-text');
                if (factText) {{
                    currentFactIndex = (currentFactIndex + 1) % funFacts.length;
                    factText.textContent = funFacts[currentFactIndex];
                }}
            }}

            // Set initial fun fact
            var factTextEl = document.querySelector('.fact-text');
            if (factTextEl) {{
                factTextEl.textContent = funFacts[0];
            }}

            // Rotate fun facts every 10 seconds
            setInterval(updateFunFact, 10000);

            // Search functionality
            var searchInput = document.getElementById('stationSearch');
            var searchResults = document.getElementById('searchResults');

            if (searchInput) {{
                searchInput.addEventListener('input', function() {{
                    var query = this.value.toLowerCase().trim();
                    if (query.length < 2) {{
                        searchResults.classList.remove('visible');
                        return;
                    }}

                    var matches = stations.filter(function(s) {{
                        return s.name.toLowerCase().includes(query);
                    }}).slice(0, 8);

                    if (matches.length > 0) {{
                        searchResults.innerHTML = matches.map(function(s) {{
                            return '<div class="search-result-item" data-lat="' + s.lat + '" data-lon="' + s.lon + '" data-name="' + s.name + '">' +
                                '<div class="station-name">' + s.name + '</div>' +
                                '<div class="station-lines">' + s.lines_text + '</div>' +
                            '</div>';
                        }}).join('');
                        searchResults.classList.add('visible');

                        // Add click handlers
                        searchResults.querySelectorAll('.search-result-item').forEach(function(item) {{
                            item.addEventListener('click', function() {{
                                var lat = parseFloat(this.dataset.lat);
                                var lon = parseFloat(this.dataset.lon);
                                var name = this.dataset.name;

                                map.setView([lat, lon], 15);
                                searchInput.value = name;
                                searchResults.classList.remove('visible');

                                // Find and open popup
                                stationLayers.forEach(function(layer) {{
                                    if (layer.station.name === name) {{
                                        layer.marker.openPopup();
                                    }}
                                }});
                            }});
                        }});
                    }} else {{
                        searchResults.innerHTML = '<div class="search-result-item"><div class="station-name">No stations found</div></div>';
                        searchResults.classList.add('visible');
                    }}
                }});

                searchInput.addEventListener('blur', function() {{
                    setTimeout(function() {{
                        searchResults.classList.remove('visible');
                    }}, 200);
                }});
            }}

            function createTooltip(s) {{
                var usageHtml = '';
                var ratioHtml = '';
                if (s.daily_usage > 0) {{
                    usageHtml = '<span style="color: #666; font-size: 11px;">Daily Usage:</span> <strong>' + formatNumber(s.daily_usage) + '</strong><br>';
                    if (s.population_1km > 0) {{
                        var ratio = (s.daily_usage / s.population_1km).toFixed(1);
                        ratioHtml = '<span style="color: #666; font-size: 11px;">Usage/Capita:</span> <strong>' + ratio + 'x</strong><br>';
                    }}
                }}
                var typeHtml = '';
                if (s.station_type && s.station_type !== 'no_usage_data') {{
                    typeHtml = '<span style="background:' + s.type_color_main + ';color:white;padding:2px 6px;border-radius:4px;font-size:10px;">' + getTypeLabel(s.station_type) + '</span><br>';
                }}
                return '<div style="font-family: Arial, sans-serif; padding: 6px;">' +
                    '<strong style="font-size: 14px;">' + s.name + '</strong><br>' +
                    typeHtml +
                    '<span style="color: #666; font-size: 11px;">Population (1km):</span> <strong>' + formatNumber(s.population_1km) + '</strong><br>' +
                    usageHtml +
                    ratioHtml +
                    '<span style="color: #888; font-size: 10px;">' + s.lines_text + '</span>' +
                    '</div>';
            }}

            function createPopup(s) {{
                var linesHtml = '';
                var lineColors = {json.dumps(line_colors)};
                s.lines.forEach(function(lid) {{
                    var color = lineColors[lid] || '#666';
                    var name = lid.replace(/-/g, ' ').replace(/\\b\\w/g, function(l) {{ return l.toUpperCase(); }});
                    linesHtml += '<span style="background-color:' + color + ';color:white;padding:2px 6px;margin:2px;border-radius:3px;font-size:11px;">' + name + '</span> ';
                }});

                var usageSection = '';
                if (s.daily_usage > 0) {{
                    var usageRatio = s.population_1km > 0 ? (s.daily_usage / s.population_1km).toFixed(1) + 'x' : 'N/A';
                    usageSection = '<div style="margin-top:10px; padding-top:10px; border-top:1px solid #eee;">' +
                        '<p style="margin:4px 0;"><strong>Station Usage (2024)</strong></p>' +
                        '<p style="margin:2px 0;"><span style="color:#666;font-size:11px;">Annual:</span> ' + formatNumber(s.annual_usage) + '</p>' +
                        '<p style="margin:2px 0;"><span style="color:#666;font-size:11px;">Daily avg:</span> <strong style="color:#e74c3c;">' + formatNumber(s.daily_usage) + '</strong></p>' +
                        '<p style="margin:2px 0;"><span style="color:#666;font-size:11px;">Usage/capita:</span> ' + usageRatio + '</p>' +
                        '</div>';
                }}

                var typeHtml = '';
                if (s.station_type && s.station_type !== 'no_usage_data') {{
                    typeHtml = '<p style="margin:4px 0;"><span style="background:' + s.type_color_main + ';color:white;padding:3px 8px;border-radius:4px;font-size:11px;">' + getTypeLabel(s.station_type) + '</span></p>';
                }}

                return '<div style="font-family: Arial, sans-serif; min-width: 220px;">' +
                    '<h4 style="margin:0 0 4px 0; color: #333;">' + s.name + '</h4>' +
                    typeHtml +
                    '<p style="margin:8px 0 4px 0;"><strong>Population within 1km:</strong></p>' +
                    '<p style="font-size: 24px; font-weight: bold; color: #1a73e8; margin: 4px 0;">' + formatNumber(s.population_1km) + '</p>' +
                    usageSection +
                    '<p style="margin:10px 0 4px 0;"><strong>Lines:</strong></p>' +
                    '<p style="margin:4px 0;">' + linesHtml + '</p>' +
                    '<button onclick="addToComparison(\\'' + s.name + '\\')" style="width:100%;margin-top:10px;padding:8px;background:#1E5A8E;color:white;border:none;border-radius:6px;cursor:pointer;font-size:12px;">Add to Compare</button>' +
                    '</div>';
            }}

            // Comparison functionality
            window.addToComparison = function(stationName) {{
                var station = stations.find(function(s) {{ return s.name === stationName; }});
                if (!station) return;

                if (comparisonStations.length >= 2) {{
                    comparisonStations = [station];
                }} else if (comparisonStations.find(function(s) {{ return s.name === stationName; }})) {{
                    return; // Already in comparison
                }} else {{
                    comparisonStations.push(station);
                }}

                updateComparisonPanel();
            }};

            function updateComparisonPanel() {{
                var panel = document.getElementById('comparisonPanel');
                var station1El = document.getElementById('compStation1');
                var station2El = document.getElementById('compStation2');

                if (comparisonStations.length === 0) {{
                    panel.classList.remove('visible');
                    return;
                }}

                panel.classList.add('visible');

                if (comparisonStations[0]) {{
                    var s1 = comparisonStations[0];
                    station1El.innerHTML = '<div class="name" style="color:' + s1.type_color_main + '">' + s1.name + '</div>' +
                        '<div class="stats">Pop: ' + formatNumber(s1.population_1km) + '<br>Usage: ' + formatNumber(s1.daily_usage) + '</div>';
                }}

                if (comparisonStations[1]) {{
                    var s2 = comparisonStations[1];
                    station2El.innerHTML = '<div class="name" style="color:' + s2.type_color_main + '">' + s2.name + '</div>' +
                        '<div class="stats">Pop: ' + formatNumber(s2.population_1km) + '<br>Usage: ' + formatNumber(s2.daily_usage) + '</div>';

                    // Draw line between stations
                    if (window.comparisonLine) {{
                        map.removeLayer(window.comparisonLine);
                    }}
                    window.comparisonLine = L.polyline([
                        [comparisonStations[0].lat, comparisonStations[0].lon],
                        [comparisonStations[1].lat, comparisonStations[1].lon]
                    ], {{color: '#E74C3C', weight: 3, dashArray: '10, 10', opacity: 0.8}}).addTo(map);

                    // Fit map to show both
                    var bounds = L.latLngBounds([
                        [comparisonStations[0].lat, comparisonStations[0].lon],
                        [comparisonStations[1].lat, comparisonStations[1].lon]
                    ]);
                    map.fitBounds(bounds.pad(0.3));
                }} else {{
                    station2El.innerHTML = '<div class="name">-</div><div class="stats">Click another station</div>';
                    if (window.comparisonLine) {{
                        map.removeLayer(window.comparisonLine);
                    }}
                }}
            }}

            // Close comparison
            document.getElementById('closeComparison').addEventListener('click', function() {{
                comparisonStations = [];
                document.getElementById('comparisonPanel').classList.remove('visible');
                if (window.comparisonLine) {{
                    map.removeLayer(window.comparisonLine);
                }}
            }});

            // URL state management
            function updateURLState() {{
                var params = new URLSearchParams();
                if (currentFilter !== 'all') {{
                    params.set('filter', currentFilter);
                }}
                if (currentVizMode !== 'markers') {{
                    params.set('viz', currentVizMode);
                }}
                var center = map.getCenter();
                params.set('lat', center.lat.toFixed(4));
                params.set('lng', center.lng.toFixed(4));
                params.set('zoom', map.getZoom());

                var newUrl = window.location.pathname + (params.toString() ? '?' + params.toString() : '');
                window.history.replaceState(null, '', newUrl);
            }}

            function loadURLState() {{
                var params = new URLSearchParams(window.location.search);
                var filter = params.get('filter');
                var viz = params.get('viz');
                var lat = parseFloat(params.get('lat'));
                var lng = parseFloat(params.get('lng'));
                var zoom = parseInt(params.get('zoom'));

                if (filter && ['commuter_hub', 'residential_hub', 'balanced', 'low_activity'].includes(filter)) {{
                    var radio = document.querySelector('input[name="stationType"][value="' + filter + '"]');
                    if (radio) {{
                        radio.checked = true;
                        updateStationDisplay(filter);
                    }}
                }}

                if (viz && ['heatmap-population', 'heatmap-usage'].includes(viz)) {{
                    var vizRadio = document.querySelector('input[name="vizMode"][value="' + viz + '"]');
                    if (vizRadio) {{
                        vizRadio.checked = true;
                        updateVizMode(viz);
                    }}
                }}

                if (!isNaN(lat) && !isNaN(lng) && !isNaN(zoom)) {{
                    map.setView([lat, lng], zoom);
                }}
            }}

            // Update URL when map moves or filters change
            map.on('moveend', updateURLState);
            map.on('zoomend', updateURLState);

            // Create station markers
            stations.forEach(function(s) {{
                var circle = L.circle([s.lat, s.lon], {{
                    radius: 1000,
                    color: s.type_color_main,
                    weight: 2,
                    fill: true,
                    fillColor: s.type_color_light,
                    fillOpacity: 0,
                    opacity: 0,
                    interactive: false
                }});

                var marker = L.circleMarker([s.lat, s.lon], {{
                    radius: 5,
                    color: s.line_color,
                    weight: 2,
                    fill: true,
                    fillColor: 'white',
                    fillOpacity: 1,
                    opacity: 1
                }}).addTo(map);

                marker.bindTooltip(createTooltip(s), {{
                    direction: 'top',
                    offset: [0, -10],
                    className: 'station-tooltip'
                }});

                marker.bindPopup(createPopup(s), {{maxWidth: 300}});

                marker.on('mouseover', function(e) {{
                    if (currentFilter === 'all') {{
                        if (!map.hasLayer(circle)) {{
                            circle.addTo(map);
                        }}
                        circle.setStyle({{
                            opacity: 0.8,
                            fillOpacity: 0.3,
                            color: s.line_color,
                            fillColor: s.line_color
                        }});
                    }}
                }});

                marker.on('mouseout', function(e) {{
                    if (!marker.isPopupOpen() && currentFilter === 'all') {{
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }}
                }});

                marker.on('popupopen', function(e) {{
                    if (currentFilter === 'all') {{
                        if (!map.hasLayer(circle)) {{
                            circle.addTo(map);
                        }}
                        circle.setStyle({{
                            opacity: 0.8,
                            fillOpacity: 0.3,
                            color: s.line_color,
                            fillColor: s.line_color
                        }});
                    }}
                }});

                marker.on('popupclose', function(e) {{
                    if (currentFilter === 'all') {{
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }}
                }});

                stationLayers.push({{
                    station: s,
                    marker: marker,
                    circle: circle
                }});
            }});

            function updateStationDisplay(selectedType) {{
                currentFilter = selectedType;

                var clearBtn = document.getElementById('clearFilterBtn');
                if (clearBtn) {{
                    if (selectedType === 'all') {{
                        clearBtn.classList.remove('visible');
                    }} else {{
                        clearBtn.classList.add('visible');
                    }}
                }}

                var statusEl = document.getElementById('filterStatus');
                if (statusEl) {{
                    if (selectedType === 'all') {{
                        statusEl.classList.remove('visible');
                    }} else {{
                        var typeLabel = getTypeLabel(selectedType);
                        var count = stationLayers.filter(function(l) {{
                            return l.station.station_type === selectedType;
                        }}).length;
                        statusEl.textContent = 'Showing ' + count + ' ' + typeLabel + ' stations';
                        statusEl.classList.add('visible');
                    }}
                }}

                document.querySelectorAll('.station-type-filter label').forEach(function(label) {{
                    label.classList.remove('selected');
                }});
                var selectedLabel = document.querySelector('input[name="stationType"][value="' + selectedType + '"]');
                if (selectedLabel) {{
                    selectedLabel.parentElement.classList.add('selected');
                }}

                stationLayers.forEach(function(layer) {{
                    var s = layer.station;
                    var marker = layer.marker;
                    var circle = layer.circle;
                    var colors = typeColors[s.station_type] || typeColors['no_usage_data'];

                    if (selectedType === 'all') {{
                        marker.setStyle({{
                            radius: 5,
                            weight: 2,
                            color: s.line_color,
                            fillColor: 'white',
                            fillOpacity: 1,
                            opacity: 1
                        }});
                        marker.setZIndexOffset(500);
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                        if (map.hasLayer(circle)) {{
                            map.removeLayer(circle);
                        }}

                    }} else if (s.station_type === selectedType) {{
                        marker.setStyle({{
                            radius: 8,
                            weight: 3,
                            color: colors.main,
                            fillColor: colors.light,
                            fillOpacity: 0.9,
                            opacity: 1
                        }});
                        marker.setZIndexOffset(1000);

                        if (!map.hasLayer(circle)) {{
                            circle.addTo(map);
                        }}
                        circle.setStyle({{
                            color: colors.main,
                            fillColor: colors.light,
                            fillOpacity: 0.15,
                            opacity: 0.6,
                            weight: 2
                        }});

                    }} else {{
                        marker.setStyle({{
                            radius: 4,
                            weight: 1,
                            color: '#999999',
                            fillColor: '#CCCCCC',
                            fillOpacity: 0.3,
                            opacity: 0.3
                        }});
                        marker.setZIndexOffset(100);
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                        if (map.hasLayer(circle)) {{
                            map.removeLayer(circle);
                        }}
                    }}
                }});
            }}

            function initHeatmaps() {{
                var popHeatData = stations
                    .filter(function(s) {{ return s.population_1km > 0; }})
                    .map(function(s) {{
                        return [s.lat, s.lon, s.population_1km / 80000];
                    }});

                populationHeat = L.heatLayer(popHeatData, {{
                    radius: 25,
                    blur: 35,
                    maxZoom: 13,
                    max: 1.0,
                    gradient: {{
                        0.0: '#ffffcc',
                        0.2: '#c7e9b4',
                        0.4: '#7fcdbb',
                        0.6: '#41b6c4',
                        0.8: '#2c7fb8',
                        1.0: '#253494'
                    }}
                }});

                var usageHeatData = stations
                    .filter(function(s) {{ return s.daily_usage > 0; }})
                    .map(function(s) {{
                        return [s.lat, s.lon, s.daily_usage / 100000];
                    }});

                usageHeat = L.heatLayer(usageHeatData, {{
                    radius: 25,
                    blur: 35,
                    maxZoom: 13,
                    max: 1.0,
                    gradient: {{
                        0.0: '#fff5f0',
                        0.2: '#fee0d2',
                        0.4: '#fcbba1',
                        0.6: '#fc9272',
                        0.8: '#fb6a4a',
                        1.0: '#a50f15'
                    }}
                }});
            }}

            function updateVizMode(mode) {{
                currentVizMode = mode;

                document.querySelectorAll('.viz-mode-toggle label').forEach(function(label) {{
                    label.classList.remove('selected');
                }});
                var selectedLabel = document.querySelector('input[name="vizMode"][value="' + mode + '"]');
                if (selectedLabel) {{
                    selectedLabel.parentElement.classList.add('selected');
                }}

                if (populationHeat && map.hasLayer(populationHeat)) {{
                    map.removeLayer(populationHeat);
                }}
                if (usageHeat && map.hasLayer(usageHeat)) {{
                    map.removeLayer(usageHeat);
                }}

                var popLegend = document.getElementById('heatmapLegendPop');
                var usageLegend = document.getElementById('heatmapLegendUsage');
                if (popLegend) popLegend.classList.remove('visible');
                if (usageLegend) usageLegend.classList.remove('visible');

                if (mode === 'markers') {{
                    stationLayers.forEach(function(layer) {{
                        layer.marker.setStyle({{opacity: 1, fillOpacity: 1}});
                    }});
                    updateStationDisplay(currentFilter);

                }} else if (mode === 'heatmap-population') {{
                    stationLayers.forEach(function(layer) {{
                        layer.marker.setStyle({{opacity: 0.3, fillOpacity: 0.3}});
                        layer.circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }});
                    if (populationHeat) {{
                        populationHeat.addTo(map);
                    }}
                    if (popLegend) popLegend.classList.add('visible');

                }} else if (mode === 'heatmap-usage') {{
                    stationLayers.forEach(function(layer) {{
                        layer.marker.setStyle({{opacity: 0.3, fillOpacity: 0.3}});
                        layer.circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }});
                    if (usageHeat) {{
                        usageHeat.addTo(map);
                    }}
                    if (usageLegend) usageLegend.classList.add('visible');
                }}
            }}

            function exportPNG() {{
                var btn = document.getElementById('exportPNGBtn');
                if (btn) {{
                    btn.disabled = true;
                    btn.textContent = 'Generating...';
                }}

                leafletImage(map, function(err, canvas) {{
                    if (btn) {{
                        btn.disabled = false;
                        btn.textContent = 'Download as PNG';
                    }}

                    if (err) {{
                        console.error(err);
                        alert('Export failed. Please try again.');
                        return;
                    }}

                    var ctx = canvas.getContext('2d');
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                    ctx.fillRect(10, 10, 350, 70);
                    ctx.fillStyle = '#333';
                    ctx.font = 'bold 16px Arial';
                    ctx.fillText('London TfL Station Analysis', 20, 32);
                    ctx.font = '12px Arial';
                    ctx.fillText('Filter: ' + (currentFilter === 'all' ? 'All Stations' : getTypeLabel(currentFilter)), 20, 50);
                    ctx.fillText('Generated: ' + new Date().toLocaleDateString(), 20, 68);

                    var link = document.createElement('a');
                    link.download = 'london-tfl-map-' + Date.now() + '.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                }});
            }}

            initHeatmaps();

            // Set up radio buttons
            var stationTypeRadios = document.querySelectorAll('input[name="stationType"]');
            stationTypeRadios.forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    updateStationDisplay(this.value);
                    updateURLState();
                }});
            }});

            var allRadio = document.querySelector('input[name="stationType"][value="all"]');
            if (allRadio) {{
                allRadio.checked = true;
                allRadio.parentElement.classList.add('selected');
            }}

            var clearBtn = document.getElementById('clearFilterBtn');
            if (clearBtn) {{
                clearBtn.addEventListener('click', function() {{
                    var allRadio = document.querySelector('input[name="stationType"][value="all"]');
                    if (allRadio) {{
                        allRadio.checked = true;
                        updateStationDisplay('all');
                    }}
                }});
            }}

            var vizModeRadios = document.querySelectorAll('input[name="vizMode"]');
            vizModeRadios.forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    updateVizMode(this.value);
                    updateURLState();
                }});
            }});

            var markersRadio = document.querySelector('input[name="vizMode"][value="markers"]');
            if (markersRadio) {{
                markersRadio.checked = true;
                markersRadio.parentElement.classList.add('selected');
            }}

            var exportBtn = document.getElementById('exportPNGBtn');
            if (exportBtn) {{
                exportBtn.addEventListener('click', exportPNG);
            }}

            // Share button
            var shareBtn = document.getElementById('shareBtn');
            if (shareBtn) {{
                shareBtn.addEventListener('click', function() {{
                    updateURLState();
                    navigator.clipboard.writeText(window.location.href).then(function() {{
                        shareBtn.textContent = 'Link Copied!';
                        shareBtn.style.background = '#c8e6c9';
                        setTimeout(function() {{
                            shareBtn.textContent = 'Copy Link to Share';
                            shareBtn.style.background = '#e3f2fd';
                        }}, 2000);
                    }}).catch(function() {{
                        // Fallback for older browsers
                        prompt('Copy this link:', window.location.href);
                    }});
                }});
            }}

            var collapsibles = document.querySelectorAll('.collapsible');
            collapsibles.forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    this.classList.toggle('active');
                    var content = this.nextElementSibling;
                    content.classList.toggle('show');
                }});
            }});

            // Keyboard shortcuts
            document.addEventListener('keydown', function(e) {{
                // Ignore if typing in input
                if (e.target.tagName === 'INPUT') return;

                switch(e.key) {{
                    case '/':
                        e.preventDefault();
                        if (searchInput) searchInput.focus();
                        break;
                    case '?':
                        shortcutsPanel.classList.toggle('visible');
                        break;
                    case 'Escape':
                        searchResults.classList.remove('visible');
                        shortcutsPanel.classList.remove('visible');
                        if (searchInput) searchInput.blur();
                        var allRadio = document.querySelector('input[name="stationType"][value="all"]');
                        if (allRadio) {{
                            allRadio.checked = true;
                            updateStationDisplay('all');
                        }}
                        break;
                    case 'd':
                    case 'D':
                        document.body.classList.toggle('dark-mode');
                        var isDark = document.body.classList.contains('dark-mode');
                        localStorage.setItem('tflMapDarkMode', isDark);
                        darkModeToggle.textContent = isDark ? '\\u2600\\uFE0F' : '\\u1F319';
                        break;
                    case 'f':
                    case 'F':
                        updateFunFact();
                        break;
                    case 'e':
                    case 'E':
                        exportPNG();
                        break;
                }}
            }});

            // Dashboard toggle
            var toggleDashboard = document.getElementById('toggleDashboard');
            var dashboard = document.querySelector('.stats-dashboard');
            if (toggleDashboard && dashboard) {{
                toggleDashboard.addEventListener('click', function() {{
                    dashboard.classList.toggle('collapsed');
                    this.textContent = dashboard.classList.contains('collapsed') ? '\\u25B6' : '\\u25C0';
                }});
            }}

            // Load URL state (filters, viz mode, map position)
            loadURLState();

            console.log('Enhanced TfL Map initialized successfully!');

        }} // End initializeWhenReady

        initializeWhenReady();
    }});
    </script>
    """

    # Stats Dashboard HTML
    dashboard_html = f"""
    <div class="stats-dashboard">
        <div class="dashboard-header">
            <h2>London TfL Explorer</h2>
            <button class="toggle-dashboard" id="toggleDashboard">&#x25C0;</button>
        </div>
        <div class="dashboard-content">
            <div class="search-container">
                <span class="search-icon">&#x1F50D;</span>
                <input type="text" class="search-input" id="stationSearch" placeholder="Search stations... (press /)">
                <div class="search-results" id="searchResults"></div>
            </div>

            <div class="stat-cards">
                <div class="stat-card">
                    <div class="stat-value">{summary_stats['total_stations']}</div>
                    <div class="stat-label">Stations</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary_stats['total_population'] // 1000000:.1f}M</div>
                    <div class="stat-label">People in 1km</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary_stats['total_daily_usage'] // 1000000:.1f}M</div>
                    <div class="stat-label">Daily Trips</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{summary_stats['avg_daily_usage'] // 1000:.0f}K</div>
                    <div class="stat-label">Avg per Station</div>
                </div>
            </div>

            <div class="fun-fact-box">
                <div class="fact-label">&#x1F4A1; Did You Know?</div>
                <div class="fact-text"></div>
            </div>
        </div>
    </div>
    """

    # Legend panel HTML
    sorted_lines = sorted(line_stats.items(), key=lambda x: -x[1]["total_population"])

    legend_html = """
    <div id="legend-panel" style="
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: white;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        max-height: 90vh;
        overflow-y: auto;
        font-family: Arial, sans-serif;
        width: 320px;
    ">
        <h3 style="margin: 0 0 5px 0; font-size: 15px; color: #333;">Filters & Controls</h3>
        <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Explore population and usage patterns</p>

        <div id="filterStatus" class="filter-status"></div>

        <div class="station-type-filter">
            <h4>View Stations By Type:</h4>
            <label>
                <input type="radio" name="stationType" value="all">
                <span class="type-color-dot" style="background: linear-gradient(135deg, #3498DB, #27AE60, #8E44AD, #E67E22);"></span>
                All Stations
            </label>
            <label>
                <input type="radio" name="stationType" value="commuter_hub">
                <span class="type-color-dot" style="background: #1E5A8E;"></span>
                Commuter Hubs
            </label>
            <label>
                <input type="radio" name="stationType" value="residential_hub">
                <span class="type-color-dot" style="background: #0D7A4F;"></span>
                Residential Areas
            </label>
            <label>
                <input type="radio" name="stationType" value="balanced">
                <span class="type-color-dot" style="background: #6C3483;"></span>
                Balanced Stations
            </label>
            <label>
                <input type="radio" name="stationType" value="low_activity">
                <span class="type-color-dot" style="background: #BA4A00;"></span>
                Low Activity
            </label>
            <button id="clearFilterBtn" class="clear-filter-btn">Reset to All</button>
        </div>

        <div class="viz-mode-toggle">
            <h4>Visualization:</h4>
            <label>
                <input type="radio" name="vizMode" value="markers">
                Station Markers
            </label>
            <label>
                <input type="radio" name="vizMode" value="heatmap-population">
                Population Heatmap
            </label>
            <label>
                <input type="radio" name="vizMode" value="heatmap-usage">
                Usage Heatmap
            </label>
        </div>

        <div id="heatmapLegendPop" class="heatmap-legend">
            <h5>Population Density</h5>
            <div class="gradient-bar population"></div>
            <div class="gradient-labels">
                <span>Low</span>
                <span>High</span>
            </div>
        </div>

        <div id="heatmapLegendUsage" class="heatmap-legend">
            <h5>Usage Intensity</h5>
            <div class="gradient-bar usage"></div>
            <div class="gradient-labels">
                <span>Low</span>
                <span>High</span>
            </div>
        </div>

        <div class="export-controls">
            <h4>Export & Share:</h4>
            <button id="exportPNGBtn" class="export-btn">Download Map as PNG</button>
            <button id="shareBtn" class="export-btn" style="background:#e3f2fd;border-color:#90caf9;">Copy Link to Share</button>
        </div>

        <table style="width: 100%; font-size: 11px; border-collapse: collapse; margin-top: 15px;">
            <tr style="border-bottom: 2px solid #ddd; background: #f5f5f5;">
                <th style="text-align: left; padding: 6px;">Line</th>
                <th style="text-align: right; padding: 6px;">Stns</th>
                <th style="text-align: right; padding: 6px;">Pop</th>
                <th style="text-align: right; padding: 6px;">Daily</th>
            </tr>
    """

    for line_id, stats in sorted_lines:
        color = stats["color"]
        text_color = "white" if color not in ["#FFD300", "#F3A9BB", "#95CDBA", "#A0A5A9"] else "black"
        daily_use = line_usage.get(line_id, 0)

        legend_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 4px;">
                    <span style="
                        background-color: {color};
                        color: {text_color};
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-size: 10px;
                    ">{stats['name'][:12]}</span>
                </td>
                <td style="text-align: right; padding: 4px;">{stats['station_count']}</td>
                <td style="text-align: right; padding: 4px;">{stats['total_population']:,}</td>
                <td style="text-align: right; padding: 4px;">{daily_use:,}</td>
            </tr>
        """

    legend_html += """
        </table>
    """

    def format_ranking_html(title, subtitle, items, value_key, ratio_key=None, ratio_label="Ratio"):
        html = f"""
        <button class="collapsible">{title}</button>
        <div class="collapse-content">
            <div style="color:#666;font-size:9px;margin-bottom:8px;">{subtitle}</div>
        """
        for i, item in enumerate(items, 1):
            ratio_display = ""
            if ratio_key and ratio_key in item:
                ratio_display = f"<br><span style='color:#888;'>{ratio_label}: {item[ratio_key]}x</span>"
            elif 'combined' in item:
                ratio_display = f"<br><span style='color:#888;'>Combined: {item['combined']:,}</span>"

            html += f"""
            <div class="ranking-item">
                <strong>{i}.</strong> {item['name'][:22]}<br>
                <span style="color:#666;">Pop: {item['population']:,} | Use: {item['usage']:,}</span>
                {ratio_display}
            </div>
            """
        html += "</div>"
        return html

    legend_html += format_ranking_html(
        "Top 10 Commuter Stations",
        "Highest Usage per Capita",
        formatted_rankings['commuter'],
        'usage',
        'ratio',
        "Ratio"
    )

    legend_html += format_ranking_html(
        "Top 10 Residential Stations",
        "Highest Population per Daily User",
        formatted_rankings['residential'],
        'population',
        'ratio',
        "Pop/User"
    )

    legend_html += format_ranking_html(
        "Top 10 Balanced Stations",
        "Closest to 1:1 Population/Usage",
        formatted_rankings['balanced'],
        'usage',
        'ratio',
        "Ratio"
    )

    legend_html += format_ranking_html(
        "Top 10 Lowest Activity Stations",
        "Lowest Combined Population + Usage",
        formatted_rankings['low_activity'],
        'usage'
    )

    legend_html += """
        <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid #ddd;">
            <p style="font-size: 9px; color: #888; margin: 0;">
                Data: TfL API + ONS Census 2021 + TfL Usage 2024
            </p>
        </div>
    </div>
    """

    m.get_root().html.add_child(folium.Element(dashboard_html))
    m.get_root().html.add_child(folium.Element(legend_html))
    m.get_root().html.add_child(folium.Element(main_script))

    output_file = OUTPUT_DIR / "tube_population_map.html"
    m.save(str(output_file))
    print(f"Map saved to {output_file}")

    return m


def main():
    results_1km = load_analysis_results()
    enhanced_data = load_enhanced_stations()

    if enhanced_data:
        print("Loaded enhanced station data with usage information")

    create_map(results_1km, enhanced_data)

    print("\n" + "=" * 60)
    print("ENHANCED MAP CREATION COMPLETE")
    print("=" * 60)
    print("Open 'tube_population_map.html' in a browser to explore!")
    print("\nStudent-Friendly Features:")
    print("- Welcome tutorial modal")
    print("- Station search with autocomplete")
    print("- Statistics dashboard with key metrics")
    print("- Fun facts that rotate automatically")
    print("- Dark mode toggle")
    print("- Keyboard shortcuts (press ? to see)")
    print("- Heatmap visualizations")
    print("- PNG export")
    print("- Mobile responsive design")


if __name__ == "__main__":
    main()
