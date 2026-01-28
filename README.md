# London Tube Station Population Map

An interactive visualization showing population density around London Underground stations, and answering the question: **Which tube line has the most people living within 500m of its stations?**

## Results Summary

Based on analysis using 2021 Census Output Area level population data:

| Rank | Line | Stations | Population (500m) | Avg/Station |
|------|------|----------|------------------|-------------|
| 1 | **District** | 60 | **455,035** | 7,583 |
| 2 | Northern | 52 | 389,804 | 7,496 |
| 3 | Piccadilly | 53 | 315,354 | 5,950 |
| 4 | Hammersmith & City | 29 | 292,272 | 10,078 |
| 5 | Central | 49 | 256,654 | 5,237 |
| 6 | Circle | 36 | 249,341 | 6,926 |
| 7 | Bakerloo | 25 | 190,862 | 7,634 |
| 8 | Jubilee | 27 | 171,409 | 6,348 |
| 9 | Metropolitan | 35 | 159,468 | 4,556 |
| 10 | Victoria | 16 | 139,882 | 8,742 |
| 11 | Waterloo & City | 2 | 3,731 | 1,865 |

**Winner: The District line** with 455,035 people living within 500m of its 60 stations.

### Top 10 Stations by Catchment Population

| Rank | Station | Population |
|------|---------|------------|
| 1 | Upton Park | 17,400 |
| 2 | Pimlico | 16,198 |
| 3 | Marylebone | 16,061 |
| 4 | Edgware Road (Bakerloo) | 14,886 |
| 5 | Earl's Court | 14,457 |
| 6 | Westbourne Park | 14,099 |
| 7 | Royal Oak | 13,823 |
| 8 | West Kensington | 13,772 |
| 9 | Stockwell | 13,590 |
| 10 | Bethnal Green | 13,550 |

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

- **Station markers** showing all 272 tube stations
- **500m radius circles** around each station, color-coded by population density
- **Click any station** to see detailed population and line information
- **Side panel** with line-by-line population rankings
- **Color legend** showing population scale

## Data Sources

### Tube Station Locations
- Source: [TfL Unified API](https://api.tfl.gov.uk/)
- Contains coordinates for all London Underground stations
- Includes which lines serve each station

### Population Data
- Source: [ONS 2021 Census](https://www.ons.gov.uk/census) at Output Area (OA) level
- Dataset: TS001 - Number of usual residents from [Nomis Bulk Data](https://www.nomisweb.co.uk/sources/census_2021_bulk)
- Geography: [Output Area Population Weighted Centroids](https://geoportal.statistics.gov.uk/)
- Coverage: 30,925 Output Areas in Greater London
- Total population: 10.3 million

## Methodology

1. **Station Data Collection**: Fetched all 272 tube stations from TfL API with coordinates and line assignments

2. **Census Data Processing**: Downloaded 2021 Census Output Area population data (TS001) and population-weighted centroids, filtered to Greater London

3. **Coordinate Conversion**: Converted OA centroids from British National Grid to WGS84 (lat/lon)

4. **Catchment Analysis**: For each station, summed populations of all OA centroids within 500m (using Haversine distance)

5. **Line Aggregation**: Totaled catchment populations for all stations on each line

### Note on Overlap
Stations that serve multiple lines are counted for each line they serve. This means:
- Bank station's population counts toward Central, Northern, Waterloo & City, and DLR
- Interchange stations contribute to multiple line totals

## File Structure

```
├── run_analysis.py            # Main runner script
├── fetch_data.py              # TfL API data fetcher
├── process_census_data.py     # Census data processor (OA centroids + population)
├── analyze_population.py      # GIS analysis (500m buffer calculation)
├── create_map.py              # Interactive map generator
├── tube_population_map.html   # Output: Interactive map
├── requirements.txt           # Python dependencies
└── data/
    ├── tube_stations.json     # Station coordinates from TfL
    ├── london_population.json # OA centroids with population (30,925 areas)
    └── analysis_results.json  # Analysis output
```

## Requirements

- Python 3.8+
- Dependencies: geopandas, pandas, requests, folium, shapely, pyproj, branca

## License

Data sources:
- TfL data: [Open Government Licence](https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service)
- ONS Census data: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
