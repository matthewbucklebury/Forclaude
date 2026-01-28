#!/usr/bin/env python3
"""
Create an interactive map showing London tube station catchment populations.
"""

import json
import folium
from folium import plugins
from pathlib import Path
import branca.colormap as cm

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent


def load_results():
    """Load analysis results."""
    with open(DATA_DIR / "analysis_results.json") as f:
        return json.load(f)


def create_popup_content(station, line_stats):
    """Create HTML popup content for a station."""
    lines_html = ""
    for line_id in station["lines"]:
        color = line_stats.get(line_id, {}).get("color", "#666")
        name = line_id.replace("-", " ").title()
        lines_html += f'<span style="background-color:{color};color:white;padding:2px 6px;margin:2px;border-radius:3px;font-size:11px;">{name}</span> '

    html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 200px;">
        <h4 style="margin:0 0 8px 0; color: #333;">{station['name']}</h4>
        <p style="margin:4px 0;"><strong>Population within 500m:</strong></p>
        <p style="font-size: 24px; font-weight: bold; color: #1a73e8; margin: 4px 0;">{station['population']:,}</p>
        <p style="margin:8px 0 4px 0;"><strong>Lines:</strong></p>
        <p style="margin:4px 0;">{lines_html}</p>
    </div>
    """
    return html


def create_line_control_html(line_stats):
    """Create HTML for the line filter controls."""
    # Sort by population
    sorted_lines = sorted(line_stats.items(), key=lambda x: -x[1]["total_population"])

    html = """
    <div style="
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
        <h3 style="margin: 0 0 10px 0; font-size: 14px;">Tube Line Population Rankings</h3>
        <p style="font-size: 11px; color: #666; margin: 0 0 10px 0;">Population within 500m of stations</p>
        <table style="width: 100%; font-size: 12px; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ddd;">
                <th style="text-align: left; padding: 4px;">Line</th>
                <th style="text-align: right; padding: 4px;">Stations</th>
                <th style="text-align: right; padding: 4px;">Population</th>
            </tr>
    """

    for rank, (line_id, stats) in enumerate(sorted_lines, 1):
        color = stats["color"]
        # Make text visible on light backgrounds
        text_color = "white" if color not in ["#FFD300", "#F3A9BB", "#95CDBA", "#A0A5A9"] else "black"

        html += f"""
            <tr style="border-bottom: 1px solid #eee;">
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
                <td style="text-align: right; padding: 4px; font-weight: bold;">{stats['total_population']:,}</td>
            </tr>
        """

    html += """
        </table>
        <div style="margin-top: 10px; padding-top: 10px; border-top: 1px solid #ddd;">
            <p style="font-size: 10px; color: #666; margin: 0;">
                Data: TfL station locations, 2021 Census population estimates.<br>
                Note: Stations serving multiple lines are counted for each line.
            </p>
        </div>
    </div>
    """

    return html


def get_line_color(station, line_stats):
    """Get the primary line color for a station."""
    # Use the first line's color (or the one with highest population)
    if station["lines"]:
        # Prefer lines in order of population
        sorted_lines = sorted(
            station["lines"],
            key=lambda l: line_stats.get(l, {}).get("total_population", 0),
            reverse=True
        )
        return line_stats.get(sorted_lines[0], {}).get("color", "#666666")
    return "#666666"


def create_map(results):
    """Create the interactive Folium map with hover-to-show circles."""
    print("Creating interactive map...")

    stations = results["stations"]
    line_stats = results["line_stats"]
    line_colors = results["line_colors"]

    # Find population range for color scaling
    populations = [s["population"] for s in stations if s["population"] > 0]
    min_pop = min(populations) if populations else 0
    max_pop = max(populations) if populations else 1

    # Create color map for population
    colormap = cm.LinearColormap(
        colors=['#fee8c8', '#fdbb84', '#e34a33'],
        vmin=min_pop,
        vmax=max_pop,
        caption='Station Catchment Population (500m radius) - Hover over station to see area'
    )

    # Create base map centered on London
    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'
    )

    # Build JavaScript for hover interactions
    js_code_parts = []
    station_data = []

    for i, station in enumerate(stations):
        if station["lat"] is None or station["lon"] is None:
            continue

        # Create popup HTML content (escape for JS)
        popup_html = create_popup_content(station, line_stats)
        popup_html_escaped = popup_html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')

        # Get station color based on population
        pop = station["population"]
        fill_color = colormap(pop) if pop > 0 else '#cccccc'

        # Get primary line color for border
        line_color = get_line_color(station, line_stats)

        # Format line names for tooltip
        line_names = [line_id.replace("-", " ").title() for line_id in station.get("lines", [])]
        lines_text = ", ".join(line_names) if line_names else "Unknown"

        # Create enhanced HTML tooltip
        tooltip_html = f"""<div style="font-family: Arial, sans-serif; padding: 4px;">
            <strong style="font-size: 13px;">{station['name']}</strong><br>
            <span style="color: #666; font-size: 11px;">Population within 500m:</span> <strong>{station['population']:,}</strong><br>
            <span style="color: #666; font-size: 11px;">Lines:</span> {lines_text}
        </div>"""

        station_data.append({
            'id': i,
            'lat': station['lat'],
            'lon': station['lon'],
            'name': station['name'],
            'population': station['population'],
            'line_color': line_color,
            'fill_color': fill_color,
            'popup_html': popup_html_escaped,
            'tooltip': tooltip_html
        })

    # Generate JavaScript to create all markers and circles with hover behavior
    js_stations = json.dumps(station_data)

    hover_script = f"""
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
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        // Wait for map to be ready
        setTimeout(function() {{
            var mapElement = document.querySelector('.folium-map');
            if (!mapElement) return;

            // Find the Leaflet map instance
            var mapId = mapElement.id;
            var map = window[mapId];
            if (!map) {{
                // Try to find map in different way
                for (var key in window) {{
                    if (window[key] && window[key]._leaflet_id && window[key].getCenter) {{
                        map = window[key];
                        break;
                    }}
                }}
            }}
            if (!map) return;

            var stations = {js_stations};

            stations.forEach(function(s) {{
                // Create the 500m radius circle (hidden by default, non-interactive)
                var circle = L.circle([s.lat, s.lon], {{
                    radius: 500,
                    color: s.line_color,
                    weight: 2,
                    fill: true,
                    fillColor: s.fill_color,
                    fillOpacity: 0,
                    opacity: 0,
                    interactive: false  // Don't capture mouse events - let them pass through to markers
                }});

                // Create the station marker (always visible)
                var marker = L.circleMarker([s.lat, s.lon], {{
                    radius: 6,
                    color: s.line_color,
                    weight: 2,
                    fill: true,
                    fillColor: 'white',
                    fillOpacity: 1,
                    opacity: 1
                }}).addTo(map);

                // Add tooltip to marker (with HTML support)
                marker.bindTooltip(s.tooltip, {{
                    direction: 'top',
                    offset: [0, -10],
                    className: 'station-tooltip'
                }});

                // Add popup to marker
                marker.bindPopup(s.popup_html, {{maxWidth: 300}});

                // Show circle on hover
                marker.on('mouseover', function(e) {{
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                // Hide circle when mouse leaves (but not if popup is open)
                marker.on('mouseout', function(e) {{
                    if (!marker.isPopupOpen()) {{
                        circle.setStyle({{opacity: 0, fillOpacity: 0}});
                    }}
                }});

                // Keep circle visible while popup is open
                marker.on('popupopen', function(e) {{
                    if (!map.hasLayer(circle)) {{
                        circle.addTo(map);
                    }}
                    circle.setStyle({{opacity: 1, fillOpacity: 0.4}});
                }});

                // Hide circle when popup closes
                marker.on('popupclose', function(e) {{
                    circle.setStyle({{opacity: 0, fillOpacity: 0}});
                }});
            }});
        }}, 500);
    }});
    </script>
    """

    # Add colormap legend
    colormap.add_to(m)

    # Add line statistics panel
    line_panel_html = create_line_control_html(line_stats)
    m.get_root().html.add_child(folium.Element(line_panel_html))

    # Add title
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
        <h2 style="margin: 0; font-size: 16px; color: #333;">London Tube Station Population Catchment</h2>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Hover over a station to see its 500m catchment area</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    # Add the hover interaction script
    m.get_root().html.add_child(folium.Element(hover_script))

    # Save map
    output_file = OUTPUT_DIR / "tube_population_map.html"
    m.save(str(output_file))
    print(f"Map saved to {output_file}")

    return m


def main():
    results = load_results()
    create_map(results)

    # Print summary
    print("\n" + "=" * 60)
    print("MAP CREATION COMPLETE")
    print("=" * 60)
    print(f"Open 'tube_population_map.html' in a browser to view the interactive map.")
    print("\nFeatures:")
    print("- Click on any station to see its catchment population")
    print("- Circles show 500m radius around each station")
    print("- Color intensity indicates population density")
    print("- Side panel shows line-by-line rankings")


if __name__ == "__main__":
    main()
