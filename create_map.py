#!/usr/bin/env python3
"""
Create an interactive map showing London TfL rail station catchment populations.
Includes Tube, Overground, Elizabeth Line, and DLR.
Supports toggle between 500m and 1km radius analysis.
"""

import json
import folium
from folium import plugins
from pathlib import Path
import branca.colormap as cm

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent


def load_dual_results():
    """Load both 500m and 1km analysis results."""
    with open(DATA_DIR / "analysis_results_500m.json") as f:
        results_500m = json.load(f)

    with open(DATA_DIR / "analysis_results_1km.json") as f:
        results_1km = json.load(f)

    return results_500m, results_1km


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


def create_map_with_toggle(results_500m, results_1km):
    """Create the interactive Folium map with radius toggle."""
    print("Creating interactive map with radius toggle...")

    stations_500 = {s["naptanId"]: s for s in results_500m["stations"]}
    stations_1km = {s["naptanId"]: s for s in results_1km["stations"]}
    line_stats_500 = results_500m["line_stats"]
    line_stats_1km = results_1km["line_stats"]
    line_colors = results_500m["line_colors"]

    # Find population range for color scaling (use max from 1km for full range)
    pops_500 = [s["population"] for s in results_500m["stations"] if s["population"] > 0]
    pops_1km = [s["population"] for s in results_1km["stations"] if s["population"] > 0]
    min_pop = min(pops_500) if pops_500 else 0
    max_pop = max(pops_1km) if pops_1km else 1

    # Create color map
    colormap = cm.LinearColormap(
        colors=['#fee8c8', '#fdbb84', '#e34a33'],
        vmin=min_pop,
        vmax=max_pop,
        caption='Station Catchment Population - Hover to see area'
    )

    # Create base map
    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'
    )

    # Build merged station data with both populations
    station_data = []
    for naptan_id, s500 in stations_500.items():
        if s500["lat"] is None or s500["lon"] is None:
            continue

        s1km = stations_1km.get(naptan_id, s500)
        line_color = get_line_color(s500, line_stats_500)

        # Format line names
        line_names = [lid.replace("-", " ").title() for lid in s500.get("lines", [])]
        lines_text = ", ".join(line_names) if line_names else "Unknown"

        # Get fill colors for both radii
        fill_color_500 = colormap(s500["population"]) if s500["population"] > 0 else '#cccccc'
        fill_color_1km = colormap(s1km["population"]) if s1km["population"] > 0 else '#cccccc'

        station_data.append({
            'naptanId': naptan_id,
            'lat': s500['lat'],
            'lon': s500['lon'],
            'name': s500['name'],
            'lines': s500.get('lines', []),
            'lines_text': lines_text,
            'population_500m': s500['population'],
            'population_1km': s1km['population'],
            'line_color': line_color,
            'fill_color_500m': fill_color_500,
            'fill_color_1km': fill_color_1km
        })

    # Convert line stats to JSON-friendly format
    line_stats_500_json = {lid: {
        'name': stats['name'],
        'color': stats['color'],
        'station_count': stats['station_count'],
        'total_population': stats['total_population']
    } for lid, stats in line_stats_500.items()}

    line_stats_1km_json = {lid: {
        'name': stats['name'],
        'color': stats['color'],
        'station_count': stats['station_count'],
        'total_population': stats['total_population']
    } for lid, stats in line_stats_1km.items()}

    js_stations = json.dumps(station_data)
    js_line_stats_500 = json.dumps(line_stats_500_json)
    js_line_stats_1km = json.dumps(line_stats_1km_json)

    # Main script with toggle functionality
    main_script = f"""
    <style>
    .station-tooltip {{
        background-color: white;
        border: 1px solid #ccc;
        border-radius: 6px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        padding: 0;
    }}
    .station-tooltip .leaflet-tooltip-content {{
        margin: 0;
    }}
    .radius-toggle {{
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 10px 0;
        padding: 10px;
        background: #f5f5f5;
        border-radius: 6px;
    }}
    .radius-toggle label {{
        font-size: 12px;
        font-weight: bold;
        color: #333;
        cursor: pointer;
    }}
    .radius-toggle .toggle-switch {{
        position: relative;
        width: 50px;
        height: 24px;
        margin: 0 10px;
    }}
    .radius-toggle .toggle-switch input {{
        opacity: 0;
        width: 0;
        height: 0;
    }}
    .radius-toggle .slider {{
        position: absolute;
        cursor: pointer;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-color: #0098D4;
        transition: .3s;
        border-radius: 24px;
    }}
    .radius-toggle .slider:before {{
        position: absolute;
        content: "";
        height: 18px;
        width: 18px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: .3s;
        border-radius: 50%;
    }}
    .radius-toggle input:checked + .slider {{
        background-color: #E32017;
    }}
    .radius-toggle input:checked + .slider:before {{
        transform: translateX(26px);
    }}
    .label-500m {{ color: #0098D4; }}
    .label-1km {{ color: #666; }}
    .radius-toggle input:checked ~ .label-500m {{ color: #666; }}
    .radius-toggle input:checked ~ .label-1km {{ color: #E32017; }}
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
            var lineStats500 = {js_line_stats_500};
            var lineStats1km = {js_line_stats_1km};
            var currentRadius = 500;

            // Store references to markers and circles
            var stationLayers = [];

            // Format number with commas
            function formatNumber(num) {{
                return num.toString().replace(/\\B(?=(\\d{{3}})+(?!\\d))/g, ",");
            }}

            // Create tooltip HTML
            function createTooltip(s, radius) {{
                var pop = radius === 500 ? s.population_500m : s.population_1km;
                return '<div style="font-family: Arial, sans-serif; padding: 4px;">' +
                    '<strong style="font-size: 13px;">' + s.name + '</strong><br>' +
                    '<span style="color: #666; font-size: 11px;">Population within ' + radius + 'm:</span> ' +
                    '<strong>' + formatNumber(pop) + '</strong><br>' +
                    '<span style="color: #666; font-size: 11px;">Lines:</span> ' + s.lines_text +
                    '</div>';
            }}

            // Create popup HTML
            function createPopup(s, radius) {{
                var pop = radius === 500 ? s.population_500m : s.population_1km;
                var linesHtml = '';
                var lineColors = {json.dumps(line_colors)};
                s.lines.forEach(function(lid) {{
                    var color = lineColors[lid] || '#666';
                    var name = lid.replace(/-/g, ' ').replace(/\\b\\w/g, function(l) {{ return l.toUpperCase(); }});
                    linesHtml += '<span style="background-color:' + color + ';color:white;padding:2px 6px;margin:2px;border-radius:3px;font-size:11px;">' + name + '</span> ';
                }});
                return '<div style="font-family: Arial, sans-serif; min-width: 200px;">' +
                    '<h4 style="margin:0 0 8px 0; color: #333;">' + s.name + '</h4>' +
                    '<p style="margin:4px 0;"><strong>Population within ' + radius + 'm:</strong></p>' +
                    '<p style="font-size: 24px; font-weight: bold; color: #1a73e8; margin: 4px 0;">' + formatNumber(pop) + '</p>' +
                    '<p style="margin:8px 0 4px 0;"><strong>Lines:</strong></p>' +
                    '<p style="margin:4px 0;">' + linesHtml + '</p>' +
                    '</div>';
            }}

            // Create all station markers and circles
            stations.forEach(function(s) {{
                var circle = L.circle([s.lat, s.lon], {{
                    radius: currentRadius,
                    color: s.line_color,
                    weight: 2,
                    fill: true,
                    fillColor: s.fill_color_500m,
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

                marker.bindTooltip(createTooltip(s, currentRadius), {{
                    direction: 'top',
                    offset: [0, -10],
                    className: 'station-tooltip'
                }});

                marker.bindPopup(createPopup(s, currentRadius), {{maxWidth: 300}});

                marker.on('mouseover', function(e) {{
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                marker.on('mouseout', function(e) {{
                    if (!marker.isPopupOpen()) {{
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }}
                }});

                marker.on('popupopen', function(e) {{
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                marker.on('popupclose', function(e) {{
                    circle.setStyle({{opacity: 0, fillOpacity: 0}});
                }});

                stationLayers.push({{
                    station: s,
                    marker: marker,
                    circle: circle
                }});
            }});

            // Update line stats table
            function updateLineTable(radius) {{
                var stats = radius === 500 ? lineStats500 : lineStats1km;
                var sortedLines = Object.entries(stats).sort(function(a, b) {{
                    return b[1].total_population - a[1].total_population;
                }});

                sortedLines.forEach(function(entry, index) {{
                    var lineId = entry[0];
                    var lineData = entry[1];
                    var row = document.getElementById('line-row-' + lineId);
                    if (row) {{
                        var popCell = row.querySelector('.line-pop');
                        if (popCell) {{
                            popCell.textContent = formatNumber(lineData.total_population);
                        }}
                    }}
                }});

                // Update subtitle
                var subtitle = document.getElementById('legend-subtitle');
                if (subtitle) {{
                    subtitle.textContent = 'Population within ' + radius + 'm of stations';
                }}

                // Update title subtitle
                var titleSubtitle = document.getElementById('title-subtitle');
                if (titleSubtitle) {{
                    titleSubtitle.textContent = 'Hover over a station to see its ' + radius + 'm catchment area';
                }}
            }}

            // Update all markers and circles for new radius
            function updateRadius(radius) {{
                currentRadius = radius;
                stationLayers.forEach(function(layer) {{
                    var s = layer.station;
                    var fillColor = radius === 500 ? s.fill_color_500m : s.fill_color_1km;

                    // Update circle radius and color
                    layer.circle.setRadius(radius);
                    layer.circle.setStyle({{ fillColor: fillColor }});

                    // Update tooltip
                    layer.marker.unbindTooltip();
                    layer.marker.bindTooltip(createTooltip(s, radius), {{
                        direction: 'top',
                        offset: [0, -10],
                        className: 'station-tooltip'
                    }});

                    // Update popup
                    layer.marker.unbindPopup();
                    layer.marker.bindPopup(createPopup(s, radius), {{maxWidth: 300}});
                }});

                updateLineTable(radius);
            }}

            // Set up toggle event listener
            var toggle = document.getElementById('radius-toggle');
            if (toggle) {{
                toggle.addEventListener('change', function() {{
                    var radius = this.checked ? 1000 : 500;
                    updateRadius(radius);
                }});
            }}

        }}, 500);
    }});
    </script>
    """

    # Create legend panel HTML with toggle
    sorted_lines = sorted(line_stats_500.items(), key=lambda x: -x[1]["total_population"])

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
        width: 280px;
    ">
        <h3 style="margin: 0 0 5px 0; font-size: 14px;">TfL Rail Population Rankings</h3>
        <p id="legend-subtitle" style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Population within 500m of stations</p>

        <div class="radius-toggle">
            <label class="label-500m">500m</label>
            <label class="toggle-switch">
                <input type="checkbox" id="radius-toggle">
                <span class="slider"></span>
            </label>
            <label class="label-1km">1km</label>
        </div>

        <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <th style="text-align: left; padding: 4px;">Line</th>
                <th style="text-align: right; padding: 4px;">Stations</th>
                <th style="text-align: right; padding: 4px;">Population</th>
            </tr>
    """

    for line_id, stats in sorted_lines:
        color = stats["color"]
        text_color = "white" if color not in ["#FFD300", "#F3A9BB", "#95CDBA", "#A0A5A9"] else "black"

        legend_html += f"""
            <tr id="line-row-{line_id}" style="border-bottom: 1px solid #eee;">
                <td style="padding: 4px;">
                    <span style="
                        background-color: {color};
                        color: {text_color};
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-size: 10px;
                        display: inline-block;
                        min-width: 80px;
                        text-align: center;
                    ">{stats['name']}</span>
                </td>
                <td style="text-align: right; padding: 4px;">{stats['station_count']}</td>
                <td class="line-pop" style="text-align: right; padding: 4px; font-weight: bold;">{stats['total_population']:,}</td>
            </tr>
        """

    legend_html += """
        </table>
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
            <p style="font-size: 10px; color: #666; margin: 0;">
                Data: TfL (Tube, Overground, Elizabeth, DLR) + 2021 Census.<br>
                Toggle radius to compare catchment areas.
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
        <h2 style="margin: 0; font-size: 16px; color: #333;">London TfL Rail Population Catchment</h2>
        <p id="title-subtitle" style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Hover over a station to see its 500m catchment area</p>
    </div>
    """

    # Add all elements to map
    colormap.add_to(m)
    m.get_root().html.add_child(folium.Element(legend_html))
    m.get_root().html.add_child(folium.Element(title_html))
    m.get_root().html.add_child(folium.Element(main_script))

    # Save map
    output_file = OUTPUT_DIR / "tube_population_map.html"
    m.save(str(output_file))
    print(f"Map saved to {output_file}")

    return m


def main():
    results_500m, results_1km = load_dual_results()
    create_map_with_toggle(results_500m, results_1km)

    print("\n" + "=" * 60)
    print("MAP CREATION COMPLETE")
    print("=" * 60)
    print("Open 'tube_population_map.html' in a browser to view the interactive map.")
    print("\nFeatures:")
    print("- Toggle between 500m and 1km radius analysis")
    print("- Hover over stations to see catchment circles")
    print("- Click stations for detailed popup")
    print("- Line rankings update with radius toggle")


if __name__ == "__main__":
    main()
