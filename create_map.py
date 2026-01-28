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
    """Create the interactive Folium map."""
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
        caption='Station Catchment Population (500m radius)'
    )

    # Create base map centered on London
    london_center = [51.509, -0.118]
    m = folium.Map(
        location=london_center,
        zoom_start=11,
        tiles='cartodbpositron'
    )

    # Create feature groups for each line
    line_groups = {}
    for line_id in line_colors.keys():
        line_name = line_id.replace("-", " ").title()
        line_groups[line_id] = folium.FeatureGroup(name=line_name, show=True)

    # Add stations to map
    for station in stations:
        if station["lat"] is None or station["lon"] is None:
            continue

        # Create popup
        popup_html = create_popup_content(station, line_stats)
        popup = folium.Popup(popup_html, max_width=300)

        # Get station color based on population
        pop = station["population"]
        fill_color = colormap(pop) if pop > 0 else '#cccccc'

        # Get primary line color for border
        line_color = get_line_color(station, line_stats)

        # Add 500m radius circle
        folium.Circle(
            location=[station["lat"], station["lon"]],
            radius=500,
            color=line_color,
            weight=2,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.4,
            popup=popup,
            tooltip=f"{station['name']}: {station['population']:,} people"
        ).add_to(m)

        # Add station marker
        folium.CircleMarker(
            location=[station["lat"], station["lon"]],
            radius=6,
            color=line_color,
            weight=2,
            fill=True,
            fill_color='white',
            fill_opacity=1,
            popup=popup,
            tooltip=f"{station['name']}"
        ).add_to(m)

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
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Population within 500m radius of each station</p>
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

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
