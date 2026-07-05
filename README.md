# London TfL Rail Station Population Map

An interactive visualization showing population density around London's TfL rail stations (Tube, Overground, Elizabeth Line, and DLR), answering the question: **Which TfL rail service has the most people living within 500m of its stations?**

## Results Summary

Based on analysis using 2021 Census Output Area level population data across **473 TfL rail stations**:

| Rank | Line | Stations | Population (500m) | Avg/Station |
|------|------|----------|------------------|-------------|
| 1 | **London Overground** | 116 | **970,745** | 8,368 |
| 2 | District | 60 | 455,035 | 7,583 |
| 3 | Northern | 52 | 389,804 | 7,496 |
| 4 | DLR | 45 | 364,494 | 8,100 |
| 5 | Piccadilly | 53 | 315,354 | 5,950 |
| 6 | Hammersmith & City | 29 | 292,272 | 10,078 |
| 7 | Central | 49 | 256,654 | 5,237 |
| 8 | Circle | 36 | 249,341 | 6,926 |
| 9 | Elizabeth | 43 | 216,443 | 5,033 |
| 10 | Bakerloo | 25 | 190,862 | 7,634 |
| 11 | Jubilee | 27 | 171,409 | 6,348 |
| 12 | Metropolitan | 35 | 159,468 | 4,556 |
| 13 | Victoria | 16 | 139,882 | 8,742 |
| 14 | Waterloo & City | 2 | 3,731 | 1,865 |

**Winner: London Overground** with 970,745 people living within 500m of its 116 stations.

*Note: Among Tube lines only, the District line leads with 455,035 people.*

### Top 10 Stations by Catchment Population

| Rank | Station | Population |
|------|---------|------------|
| 1 | Upton Park | 17,400 |
| 2 | Langdon Park (DLR) | 16,964 |
| 3 | Devons Road (DLR) | 16,337 |
| 4 | Pimlico | 16,198 |
| 5 | Shadwell | 16,068 |
| 6 | Marylebone | 16,061 |
| 7 | Crossharbour (DLR) | 15,950 |
| 8 | South Quay (DLR) | 15,227 |
| 9 | Clapton (Overground) | 15,052 |
| 10 | Bow Church (DLR) | 14,985 |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full analysis
python run_analysis.py

# Or run individual steps:
python fetch_data.py              # Download TfL station data
python download_population_data.py # Prepare population data
python analyze_population.py       # Run analysis
python create_map.py              # Create interactive map
```

Then open `tube_population_map.html` in your browser.

## Interactive Map Features

- **Station markers** showing all 473 TfL rail stations (Tube, Overground, Elizabeth Line, DLR)
- **Radius toggle** to switch between 500m and 1km catchment analysis
- **Hover over stations** to see catchment circles and population
- **Click any station** to see detailed population and line information
- **Side panel** with line-by-line population rankings that update with radius toggle
- **Color legend** showing population scale

## Data Sources

### TfL Rail Station Locations
- Source: [TfL Unified API](https://api.tfl.gov.uk/)
- Includes: London Underground (272), Overground (116), Elizabeth Line (43), DLR (45)
- Contains coordinates and line assignments for all stations

### Population Data
- Source: [ONS 2021 Census](https://www.ons.gov.uk/census) at Output Area (OA) level
- Dataset: TS001 - Number of usual residents from [Nomis Bulk Data](https://www.nomisweb.co.uk/sources/census_2021_bulk)
- Geography: [Output Area Population Weighted Centroids](https://geoportal.statistics.gov.uk/)
- Coverage: 30,925 Output Areas in Greater London
- Total population: 10.3 million

## Methodology

1. **Station Data Collection**: Fetched all 473 TfL rail stations from TfL API (Tube, Overground, Elizabeth Line, DLR) with coordinates and line assignments

2. **Census Data Processing**: Downloaded 2021 Census Output Area population data (TS001) and population-weighted centroids, filtered to Greater London

3. **Coordinate Conversion**: Converted OA centroids from British National Grid to WGS84 (lat/lon)

4. **Catchment Analysis**: For each station, summed populations of all OA centroids within 500m and 1km (using Haversine distance)

5. **Line Aggregation**: Totaled catchment populations for all stations on each line/service

### Note on Overlap
Stations that serve multiple lines are counted for each line they serve. This means:
- Bank station's population counts toward Central, Northern, Waterloo & City, and DLR
- Interchange stations contribute to multiple line totals

## File Structure

```
├── run_analysis.py            # Main runner script
├── fetch_data.py              # TfL API data fetcher (Tube, Overground, Elizabeth, DLR)
├── process_census_data.py     # Census data processor (OA centroids + population)
├── analyze_population.py      # GIS analysis (single radius)
├── analyze_dual_radius.py     # GIS analysis (500m and 1km)
├── create_map.py              # Interactive map generator with radius toggle
├── tube_population_map.html   # Output: Interactive map
├── requirements.txt           # Python dependencies
└── data/
    ├── tube_stations.json     # Station coordinates from TfL (473 stations)
    ├── london_population.json # OA centroids with population (30,925 areas)
    ├── analysis_results_500m.json  # 500m radius analysis output
    └── analysis_results_1km.json   # 1km radius analysis output
```

## Requirements

- Python 3.8+
- Dependencies: geopandas, pandas, requests, folium, shapely, pyproj, branca

## License

Data sources:
- TfL data: [Open Government Licence](https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service)
- ONS Census data: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
