#!/usr/bin/env python3
"""
Create an interactive map showing London TfL rail station catchment populations.
Includes Tube, Overground, Elizabeth Line, and DLR.
Shows 1km radius analysis with station type filtering and heatmap visualization.
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
    # Filter to stations with both population and usage data
    valid_stations = [s for s in stations if s['population_1km'] > 0 and s['daily_usage'] > 0]

    # Commuter: highest usage per capita (daily_usage / population)
    commuter_ranked = sorted(valid_stations,
                            key=lambda s: s['daily_usage'] / s['population_1km'],
                            reverse=True)[:10]

    # Residential: highest population per user (population / daily_usage)
    residential_ranked = sorted(valid_stations,
                               key=lambda s: s['population_1km'] / s['daily_usage'],
                               reverse=True)[:10]

    # Balanced: closest to 1:1 ratio
    balanced_ranked = sorted(valid_stations,
                            key=lambda s: abs(1.0 - (s['daily_usage'] / s['population_1km'])))[:10]

    # Low Activity: lowest combined population + usage
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


def create_map(results_1km, enhanced_data=None):
    """Create the interactive Folium map with 1km radius only."""
    print("Creating interactive map (1km radius)...")

    stations_1km = {s["naptanId"]: s for s in results_1km["stations"]}
    line_stats = results_1km["line_stats"]
    line_colors = results_1km["line_colors"]

    # Build enhanced station lookup if available
    enhanced_lookup = {}
    if enhanced_data:
        enhanced_lookup = {s["naptanId"]: s for s in enhanced_data.get("stations", [])}
        print(f"  Loaded usage data for {len(enhanced_lookup)} stations")

    # Station type colors - enhanced color system
    type_colors = {
        'commuter_hub': {
            'main': '#1E5A8E',      # Deep blue
            'light': '#3498DB',     # Bright blue
            'accent': '#5DADE2'     # Light blue
        },
        'residential_hub': {
            'main': '#0D7A4F',      # Deep green
            'light': '#27AE60',     # Bright green
            'accent': '#58D68D'     # Light green
        },
        'balanced': {
            'main': '#6C3483',      # Deep purple
            'light': '#8E44AD',     # Bright purple
            'accent': '#BB8FCE'     # Light purple
        },
        'low_activity': {
            'main': '#BA4A00',      # Deep orange
            'light': '#E67E22',     # Bright orange
            'accent': '#F39C12'     # Light orange
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

    # Create base map with grayscale tiles for better contrast
    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'  # Light grayscale map
    )

    # Build station data
    station_data = []

    for naptan_id, s1km in stations_1km.items():
        if s1km["lat"] is None or s1km["lon"] is None:
            continue

        line_color = get_line_color(s1km, line_stats)

        # Format line names
        line_names = [lid.replace("-", " ").title() for lid in s1km.get("lines", [])]
        lines_text = ", ".join(line_names) if line_names else "Unknown"

        # Get enhanced data if available
        enhanced = enhanced_lookup.get(naptan_id, {})
        annual_usage = enhanced.get('annual_usage', 0)
        daily_usage = enhanced.get('daily_usage', 0)
        usage_per_capita = enhanced.get('usage_per_capita_1km', 0)
        station_type = enhanced.get('station_type', 'no_usage_data')

        # Get type colors
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

    # Calculate line usage totals
    line_usage = calculate_line_usage(station_data, line_stats)

    # Calculate station rankings
    rankings = calculate_station_rankings(station_data)

    # Convert to JSON for JavaScript
    js_stations = json.dumps(station_data)
    js_line_stats = json.dumps({lid: {
        'name': stats['name'],
        'color': stats['color'],
        'station_count': stats['station_count'],
        'total_population': stats['total_population'],
        'daily_usage': line_usage.get(lid, 0)
    } for lid, stats in line_stats.items()})

    # Format rankings data for both JS and HTML use
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

    # Main script with redesigned UX
    main_script = f"""
    <script src="https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/leaflet-image@0.4.0/leaflet-image.js"></script>

    <style>
    /* Base styles */
    .station-tooltip {{
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        padding: 0;
    }}

    /* Radio button filter styles */
    .station-type-filter {{
        margin: 10px 0;
        padding: 12px;
        background: #f8f9fa;
        border-radius: 8px;
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
        border-radius: 6px;
        transition: all 0.2s ease;
    }}
    .station-type-filter label:hover {{
        background: #e9ecef;
    }}
    .station-type-filter label.selected {{
        background: #e3f2fd;
        font-weight: 500;
    }}
    .station-type-filter input[type="radio"] {{
        margin-right: 10px;
        cursor: pointer;
    }}
    .type-icon {{
        margin-right: 8px;
        font-size: 14px;
    }}
    .type-color-dot {{
        display: inline-block;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        margin-right: 8px;
        border: 2px solid rgba(0,0,0,0.2);
    }}

    /* Clear filter button */
    .clear-filter-btn {{
        width: 100%;
        padding: 10px;
        margin-top: 10px;
        background: #ECF0F1;
        border: 1px solid #BDC3C7;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        transition: all 0.2s ease;
        display: none;
    }}
    .clear-filter-btn:hover {{
        background: #BDC3C7;
        border-color: #95A5A6;
    }}
    .clear-filter-btn.visible {{
        display: block;
    }}

    /* Visualization mode toggle */
    .viz-mode-toggle {{
        margin: 15px 0;
        padding: 12px;
        background: #fff3e0;
        border-radius: 8px;
        border: 1px solid #ffe0b2;
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
        border-radius: 4px;
        transition: background 0.2s;
    }}
    .viz-mode-toggle label:hover {{
        background: #ffe0b2;
    }}
    .viz-mode-toggle label.selected {{
        background: #ffcc80;
        font-weight: 500;
    }}
    .viz-mode-toggle input[type="radio"] {{
        margin-right: 8px;
    }}

    /* Heatmap legend */
    .heatmap-legend {{
        display: none;
        margin: 10px 0;
        padding: 10px;
        background: #fafafa;
        border-radius: 6px;
    }}
    .heatmap-legend.visible {{
        display: block;
    }}
    .heatmap-legend h5 {{
        margin: 0 0 8px 0;
        font-size: 11px;
    }}
    .gradient-bar {{
        height: 15px;
        border-radius: 3px;
        margin-bottom: 4px;
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
        font-size: 9px;
        color: #666;
    }}

    /* Export controls */
    .export-controls {{
        margin: 15px 0;
        padding: 12px;
        background: #e8f5e9;
        border-radius: 8px;
        border: 1px solid #c8e6c9;
    }}
    .export-controls h4 {{
        margin: 0 0 10px 0;
        font-size: 12px;
        color: #2e7d32;
    }}
    .export-btn {{
        width: 100%;
        padding: 8px 12px;
        margin: 4px 0;
        background: white;
        border: 1px solid #a5d6a7;
        border-radius: 4px;
        cursor: pointer;
        font-size: 11px;
        transition: all 0.2s;
        text-align: left;
    }}
    .export-btn:hover {{
        background: #c8e6c9;
        border-color: #81c784;
    }}
    .export-btn:disabled {{
        opacity: 0.6;
        cursor: not-allowed;
    }}

    /* Collapsible sections */
    .collapsible {{
        cursor: pointer;
        padding: 10px;
        background: #f0f0f0;
        border: none;
        text-align: left;
        width: 100%;
        font-size: 11px;
        font-weight: bold;
        border-radius: 6px;
        margin-top: 8px;
        transition: background 0.2s;
    }}
    .collapsible:hover {{
        background: #e0e0e0;
    }}
    .collapsible:before {{
        content: '▶ ';
        font-size: 10px;
    }}
    .collapsible.active:before {{
        content: '▼ ';
    }}
    .collapse-content {{
        display: none;
        padding: 10px;
        background: #fafafa;
        border-radius: 0 0 6px 6px;
        font-size: 10px;
    }}
    .collapse-content.show {{
        display: block;
    }}
    .ranking-item {{
        padding: 6px 0;
        border-bottom: 1px solid #eee;
    }}
    .ranking-item:last-child {{
        border-bottom: none;
    }}

    /* Smooth transitions for markers */
    .leaflet-marker-icon,
    .leaflet-marker-shadow {{
        transition: opacity 0.3s ease;
    }}

    /* Status indicator */
    .filter-status {{
        padding: 8px;
        background: #e3f2fd;
        border-radius: 4px;
        margin-bottom: 10px;
        font-size: 11px;
        color: #1565c0;
        display: none;
    }}
    .filter-status.visible {{
        display: block;
    }}
    </style>

    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        setTimeout(function() {{
            var mapElement = document.querySelector('.folium-map');
            if (!mapElement) return;

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
            if (!map) return;

            var stations = {js_stations};
            var lineStats = {js_line_stats};
            var rankings = {js_rankings};
            var typeColors = {js_type_colors};

            var stationLayers = [];
            var currentFilter = 'all';
            var currentVizMode = 'markers';
            var populationHeat = null;
            var usageHeat = null;

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
                    '</div>';
            }}

            // Create all station markers and circles
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

                // Hover behavior depends on current filter
                marker.on('mouseover', function(e) {{
                    if (currentFilter === 'all') {{
                        // Show circle on hover when no filter active
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

            // Update station display based on filter
            function updateStationDisplay(selectedType) {{
                currentFilter = selectedType;

                // Update clear button visibility
                var clearBtn = document.getElementById('clearFilterBtn');
                if (clearBtn) {{
                    if (selectedType === 'all') {{
                        clearBtn.classList.remove('visible');
                    }} else {{
                        clearBtn.classList.add('visible');
                    }}
                }}

                // Update filter status
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

                // Update radio label styling
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
                        // NEUTRAL STATE: All stations visible, no circles
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
                        // SELECTED TYPE: Prominent with visible circle
                        marker.setStyle({{
                            radius: 8,
                            weight: 3,
                            color: colors.main,
                            fillColor: colors.light,
                            fillOpacity: 0.9,
                            opacity: 1
                        }});
                        marker.setZIndexOffset(1000);

                        // Show circle permanently for selected type
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
                        // OTHER TYPES: Faded, no circle
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

            // Create heatmap layers
            function initHeatmaps() {{
                // Population heatmap
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

                // Usage heatmap
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

            // Update visualization mode
            function updateVizMode(mode) {{
                currentVizMode = mode;

                // Update radio label styling
                document.querySelectorAll('.viz-mode-toggle label').forEach(function(label) {{
                    label.classList.remove('selected');
                }});
                var selectedLabel = document.querySelector('input[name="vizMode"][value="' + mode + '"]');
                if (selectedLabel) {{
                    selectedLabel.parentElement.classList.add('selected');
                }}

                // Remove heatmap layers
                if (populationHeat && map.hasLayer(populationHeat)) {{
                    map.removeLayer(populationHeat);
                }}
                if (usageHeat && map.hasLayer(usageHeat)) {{
                    map.removeLayer(usageHeat);
                }}

                // Update heatmap legend
                var popLegend = document.getElementById('heatmapLegendPop');
                var usageLegend = document.getElementById('heatmapLegendUsage');
                if (popLegend) popLegend.classList.remove('visible');
                if (usageLegend) usageLegend.classList.remove('visible');

                if (mode === 'markers') {{
                    // Show markers at full opacity
                    stationLayers.forEach(function(layer) {{
                        layer.marker.setStyle({{opacity: 1, fillOpacity: 1}});
                    }});
                    // Re-apply current filter
                    updateStationDisplay(currentFilter);

                }} else if (mode === 'heatmap-population') {{
                    // Dim markers, show population heatmap
                    stationLayers.forEach(function(layer) {{
                        layer.marker.setStyle({{opacity: 0.3, fillOpacity: 0.3}});
                        layer.circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }});
                    if (populationHeat) {{
                        populationHeat.addTo(map);
                    }}
                    if (popLegend) popLegend.classList.add('visible');

                }} else if (mode === 'heatmap-usage') {{
                    // Dim markers, show usage heatmap
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

            // Export functions
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

                    // Add metadata overlay
                    var ctx = canvas.getContext('2d');
                    ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                    ctx.fillRect(10, 10, 350, 70);
                    ctx.fillStyle = '#333';
                    ctx.font = 'bold 16px Arial';
                    ctx.fillText('London TfL Station Analysis', 20, 32);
                    ctx.font = '12px Arial';
                    ctx.fillText('Filter: ' + (currentFilter === 'all' ? 'All Stations' : getTypeLabel(currentFilter)), 20, 50);
                    ctx.fillText('Generated: ' + new Date().toLocaleDateString(), 20, 68);

                    // Download
                    var link = document.createElement('a');
                    link.download = 'tube-analysis-' + currentFilter + '-' + Date.now() + '.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                }});
            }}

            // Initialize heatmaps
            initHeatmaps();

            // Set up station type filter (radio buttons)
            var stationTypeRadios = document.querySelectorAll('input[name="stationType"]');
            stationTypeRadios.forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    updateStationDisplay(this.value);
                }});
            }});

            // Initialize with "all" selected
            var allRadio = document.querySelector('input[name="stationType"][value="all"]');
            if (allRadio) {{
                allRadio.checked = true;
                allRadio.parentElement.classList.add('selected');
            }}

            // Clear filter button
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

            // Set up visualization mode toggle
            var vizModeRadios = document.querySelectorAll('input[name="vizMode"]');
            vizModeRadios.forEach(function(radio) {{
                radio.addEventListener('change', function() {{
                    updateVizMode(this.value);
                }});
            }});

            // Initialize markers mode
            var markersRadio = document.querySelector('input[name="vizMode"][value="markers"]');
            if (markersRadio) {{
                markersRadio.checked = true;
                markersRadio.parentElement.classList.add('selected');
            }}

            // Export button
            var exportBtn = document.getElementById('exportPNGBtn');
            if (exportBtn) {{
                exportBtn.addEventListener('click', exportPNG);
            }}

            // Set up collapsible sections
            var collapsibles = document.querySelectorAll('.collapsible');
            collapsibles.forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    this.classList.toggle('active');
                    var content = this.nextElementSibling;
                    content.classList.toggle('show');
                }});
            }});

        }}, 500);
    }});
    </script>
    """

    # Create legend panel HTML
    sorted_lines = sorted(line_stats.items(), key=lambda x: -x[1]["total_population"])

    legend_html = """
    <div id="legend-panel" style="
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        max-height: 90vh;
        overflow-y: auto;
        font-family: Arial, sans-serif;
        width: 320px;
    ">
        <h3 style="margin: 0 0 5px 0; font-size: 15px; color: #333;">TfL Rail Population & Usage</h3>
        <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Population within 1km radius of stations</p>

        <div id="filterStatus" class="filter-status"></div>

        <div class="station-type-filter">
            <h4>View Stations By Type:</h4>
            <label>
                <input type="radio" name="stationType" value="all">
                <span class="type-color-dot" style="background: linear-gradient(135deg, #3498DB, #27AE60, #8E44AD, #E67E22);"></span>
                All Stations (No Filter)
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
                Low Activity Areas
            </label>
            <button id="clearFilterBtn" class="clear-filter-btn">Reset to All Stations</button>
        </div>

        <div class="viz-mode-toggle">
            <h4>Visualization Mode:</h4>
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
            <h5>Station Usage Intensity</h5>
            <div class="gradient-bar usage"></div>
            <div class="gradient-labels">
                <span>Low</span>
                <span>High</span>
            </div>
        </div>

        <div class="export-controls">
            <h4>Export:</h4>
            <button id="exportPNGBtn" class="export-btn">Download as PNG</button>
        </div>

        <table style="width: 100%; font-size: 11px; border-collapse: collapse; margin-top: 15px;">
            <tr style="border-bottom: 2px solid #ddd; background: #f5f5f5;">
                <th style="text-align: left; padding: 6px;">Line</th>
                <th style="text-align: right; padding: 6px;">Stns</th>
                <th style="text-align: right; padding: 6px;">Pop</th>
                <th style="text-align: right; padding: 6px;">Daily Use</th>
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

    # Add ranking sections
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
                Data: TfL API + 2021 Census + Usage 2024
            </p>
        </div>
    </div>
    """

    # Title panel
    title_html = """
    <div style="
        position: fixed;
        top: 10px;
        left: 60px;
        z-index: 1000;
        background: white;
        padding: 12px 18px;
        border-radius: 10px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        font-family: Arial, sans-serif;
    ">
        <h2 style="margin: 0; font-size: 17px; color: #333;">London TfL Rail Population & Usage</h2>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Select a station type to explore catchment areas</p>
    </div>
    """

    # Add all elements to map
    m.get_root().html.add_child(folium.Element(legend_html))
    m.get_root().html.add_child(folium.Element(title_html))
    m.get_root().html.add_child(folium.Element(main_script))

    # Save map
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
    print("MAP CREATION COMPLETE")
    print("=" * 60)
    print("Open 'tube_population_map.html' in a browser to view the interactive map.")
    print("\nNew Features:")
    print("- Radio button filters (single-select)")
    print("- Smart opacity system (faded background stations)")
    print("- Clear filter functionality")
    print("- Heatmap visualization modes (Population/Usage)")
    print("- PNG export capability")
    print("- Enhanced color system with visual hierarchy")


if __name__ == "__main__":
    main()
