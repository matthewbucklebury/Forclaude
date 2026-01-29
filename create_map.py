#!/usr/bin/env python3
"""
Create an interactive map showing London TfL rail station catchment populations.
Includes Tube, Overground, Elizabeth Line, and DLR.
Shows 1km radius analysis with station type filtering.
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

    # Station type colors
    type_colors = {
        'commuter_hub': '#2E86AB',      # Blue
        'residential_hub': '#06A77D',   # Green
        'balanced': '#9B59B6',          # Purple
        'low_activity': '#95A5A6',      # Grey
        'no_usage_data': '#bdc3c7',
        'no_population_data': '#ecf0f1'
    }

    # Create base map
    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'
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
            'type_color': type_colors.get(station_type, '#bdc3c7')
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

    # Main script
    main_script = f"""
    <style>
    .station-tooltip {{
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        padding: 0;
    }}
    .type-filter {{
        margin: 10px 0;
        padding: 10px;
        background: #f8f9fa;
        border-radius: 6px;
    }}
    .type-filter label {{
        display: flex;
        align-items: center;
        margin: 4px 0;
        cursor: pointer;
        font-size: 11px;
    }}
    .type-filter input {{
        margin-right: 8px;
    }}
    .type-badge {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 3px;
        color: white;
        font-size: 10px;
        margin-left: 4px;
    }}
    .collapsible {{
        cursor: pointer;
        padding: 8px;
        background: #f0f0f0;
        border: none;
        text-align: left;
        width: 100%;
        font-size: 11px;
        font-weight: bold;
        border-radius: 4px;
        margin-top: 8px;
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
        padding: 8px;
        background: #fafafa;
        border-radius: 0 0 4px 4px;
        font-size: 10px;
    }}
    .collapse-content.show {{
        display: block;
    }}
    .ranking-item {{
        padding: 4px 0;
        border-bottom: 1px solid #eee;
    }}
    .ranking-item:last-child {{
        border-bottom: none;
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

            var typeColors = {{
                'commuter_hub': '#2E86AB',
                'residential_hub': '#06A77D',
                'balanced': '#9B59B6',
                'low_activity': '#95A5A6'
            }};

            var stationLayers = [];

            function formatNumber(num) {{
                return num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ",");
            }}

            function getTypeLabel(type) {{
                var labels = {{
                    'commuter_hub': 'Commuter',
                    'residential_hub': 'Residential',
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
                    typeHtml = '<span style="background:' + s.type_color + ';color:white;padding:1px 4px;border-radius:3px;font-size:9px;">' + getTypeLabel(s.station_type) + '</span><br>';
                }}
                return '<div style="font-family: Arial, sans-serif; padding: 4px;">' +
                    '<strong style="font-size: 13px;">' + s.name + '</strong><br>' +
                    typeHtml +
                    '<span style="color: #666; font-size: 11px;">Population (1km):</span> <strong>' + formatNumber(s.population_1km) + '</strong><br>' +
                    usageHtml +
                    ratioHtml +
                    '<span style="color: #666; font-size: 10px;">' + s.lines_text + '</span>' +
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
                    typeHtml = '<p style="margin:4px 0;"><span style="background:' + s.type_color + ';color:white;padding:2px 6px;border-radius:3px;font-size:10px;">' + getTypeLabel(s.station_type) + '</span></p>';
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
                    color: s.line_color,
                    weight: 2,
                    fill: true,
                    fillColor: s.type_color,
                    fillOpacity: 0,
                    opacity: 0,
                    interactive: false
                }});

                var marker = L.circleMarker([s.lat, s.lon], {{
                    radius: 6,
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
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                marker.on('mouseout', function(e) {{
                    if (!marker.isPopupOpen()) {{
                        var highlighted = isTypeHighlighted(s.station_type);
                        circle.setStyle({{
                            opacity: highlighted ? 1 : 0,
                            fillOpacity: highlighted ? 0.5 : 0
                        }});
                    }}
                }});

                marker.on('popupopen', function(e) {{
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                marker.on('popupclose', function(e) {{
                    var highlighted = isTypeHighlighted(s.station_type);
                    circle.setStyle({{
                        opacity: highlighted ? 1 : 0,
                        fillOpacity: highlighted ? 0.5 : 0
                    }});
                }});

                stationLayers.push({{
                    station: s,
                    marker: marker,
                    circle: circle
                }});
            }});

            // Track which types are highlighted
            var highlightedTypes = {{}};

            function isTypeHighlighted(type) {{
                return highlightedTypes[type] === true;
            }}

            function updateHighlighting() {{
                stationLayers.forEach(function(layer) {{
                    var s = layer.station;
                    var highlighted = isTypeHighlighted(s.station_type);

                    if (highlighted) {{
                        if (!map.hasLayer(layer.circle)) {{
                            layer.circle.addTo(map);
                        }}
                        layer.circle.setStyle({{
                            opacity: 1,
                            fillOpacity: 0.5,
                            fillColor: typeColors[s.station_type] || '#bdc3c7'
                        }});
                    }} else {{
                        layer.circle.setStyle({{
                            opacity: 0,
                            fillOpacity: 0
                        }});
                    }}
                }});
            }}

            // Set up type filter checkboxes
            ['commuter_hub', 'residential_hub', 'balanced', 'low_activity'].forEach(function(type) {{
                var checkbox = document.getElementById('filter-' + type);
                if (checkbox) {{
                    checkbox.addEventListener('change', function() {{
                        highlightedTypes[type] = this.checked;
                        updateHighlighting();
                    }});
                }}
            }});

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
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        max-height: 90vh;
        overflow-y: auto;
        font-family: Arial, sans-serif;
        width: 300px;
    ">
        <h3 style="margin: 0 0 5px 0; font-size: 14px;">TfL Rail Population & Usage</h3>
        <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Population within 1km of stations</p>

        <div class="type-filter">
            <div style="font-weight: bold; margin-bottom: 6px; font-size: 11px;">Highlight Station Types:</div>
            <label><input type="checkbox" id="filter-commuter_hub">
                <span class="type-badge" style="background:#2E86AB;">Commuter</span>
            </label>
            <label><input type="checkbox" id="filter-residential_hub">
                <span class="type-badge" style="background:#06A77D;">Residential</span>
            </label>
            <label><input type="checkbox" id="filter-balanced">
                <span class="type-badge" style="background:#9B59B6;">Balanced</span>
            </label>
            <label><input type="checkbox" id="filter-low_activity">
                <span class="type-badge" style="background:#95A5A6;">Low Activity</span>
            </label>
        </div>

        <table style="width: 100%; font-size: 11px; border-collapse: collapse; margin-top: 10px;">
            <tr style="border-bottom: 1px solid #ddd; background: #f5f5f5;">
                <th style="text-align: left; padding: 4px;">Line</th>
                <th style="text-align: right; padding: 4px;">Stns</th>
                <th style="text-align: right; padding: 4px;">Pop</th>
                <th style="text-align: right; padding: 4px;">Daily Use</th>
            </tr>
    """

    for line_id, stats in sorted_lines:
        color = stats["color"]
        text_color = "white" if color not in ["#FFD300", "#F3A9BB", "#95CDBA", "#A0A5A9"] else "black"
        daily_use = line_usage.get(line_id, 0)

        legend_html += f"""
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 3px;">
                    <span style="
                        background-color: {color};
                        color: {text_color};
                        padding: 1px 4px;
                        border-radius: 2px;
                        font-size: 9px;
                    ">{stats['name'][:12]}</span>
                </td>
                <td style="text-align: right; padding: 3px;">{stats['station_count']}</td>
                <td style="text-align: right; padding: 3px;">{stats['total_population']:,}</td>
                <td style="text-align: right; padding: 3px;">{daily_use:,}</td>
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
            <div style="color:#666;font-size:9px;margin-bottom:6px;">{subtitle}</div>
        """
        for i, item in enumerate(items, 1):
            ratio_display = ""
            if ratio_key and ratio_key in item:
                ratio_display = f"<br><span style='color:#888;'>{ratio_label}: {item[ratio_key]}x</span>"
            elif 'combined' in item:
                ratio_display = f"<br><span style='color:#888;'>Combined: {item['combined']:,}</span>"

            html += f"""
            <div class="ranking-item">
                <strong>{i}.</strong> {item['name'][:20]}<br>
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
        <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #ddd;">
            <p style="font-size: 9px; color: #666; margin: 0;">
                Data: TfL + 2021 Census + Usage 2024
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
        padding: 10px 15px;
        border-radius: 8px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: Arial, sans-serif;
    ">
        <h2 style="margin: 0; font-size: 16px; color: #333;">London TfL Rail Population & Usage</h2>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Hover over stations to see 1km catchment area</p>
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
    print("\nFeatures:")
    print("- 1km radius catchment analysis")
    print("- Station type filter checkboxes")
    print("- Line rankings with daily usage")
    print("- Top 10 stations by type (Commuter/Residential/Balanced/Low Activity)")
    print("- Hover over stations to see circles and data")


if __name__ == "__main__":
    main()
