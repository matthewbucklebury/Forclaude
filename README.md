# London Tube Station Population Map

An interactive visualization showing population density around London Underground stations, and answering the question: **Which tube line has the most people living within 500m of its stations?**

## Results Summary

Based on analysis using 2021 Census population data:

| Rank | Line | Stations | Population (500m) |
|------|------|----------|------------------|
| 1 | **Piccadilly** | 53 | **161,156** |
| 2 | District | 60 | 154,582 |
| 3 | Central | 49 | 138,088 |
| 4 | Northern | 52 | 138,004 |
| 5 | Metropolitan | 35 | 82,877 |
| 6 | Jubilee | 27 | 76,927 |
| 7 | Hammersmith & City | 29 | 71,361 |
| 8 | Circle | 36 | 70,549 |
| 9 | Bakerloo | 25 | 63,994 |
| 10 | Victoria | 16 | 41,975 |
| 11 | Waterloo & City | 2 | 2,966 |

**Winner: The Piccadilly line** with approximately 161,000 people living within 500m of its 53 stations.

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
- Based on [2021 Census](https://www.ons.gov.uk/census) borough-level population totals
- Population distributed using a 200m grid weighted by distance to borough centroids
- Total London population: ~8.8 million (matching census figures)

For more accurate analysis, the code can be configured to use:
- [ONS Output Area Population Weighted Centroids](https://geoportal.statistics.gov.uk/)
- [Nomis Census 2021 Bulk Data](https://www.nomisweb.co.uk/sources/census_2021_bulk)

## Methodology

1. **Station Data Collection**: Fetched all tube stations from TfL API with coordinates and line assignments

2. **Population Grid**: Created a 200m resolution grid covering Greater London, with population weights based on 2021 Census borough totals

3. **Catchment Analysis**: For each station, summed the population of all grid cells whose centroids fall within 500m (using Haversine distance)

4. **Line Aggregation**: Totaled catchment populations for all stations on each line

### Note on Overlap
Stations that serve multiple lines are counted for each line they serve. This means:
- Bank station's population counts toward Central, Northern, Waterloo & City, and DLR
- Interchange stations contribute to multiple line totals

## File Structure

```
├── run_analysis.py           # Main runner script
├── fetch_data.py             # TfL API data fetcher
├── download_population_data.py # Population data preparation
├── analyze_population.py     # GIS analysis
├── create_map.py             # Interactive map generator
├── tube_population_map.html  # Output: Interactive map
├── requirements.txt          # Python dependencies
└── data/
    ├── tube_stations.json    # Station coordinates
    ├── london_population.json # Population grid
    └── analysis_results.json # Analysis output
```

## Requirements

- Python 3.8+
- Dependencies: geopandas, pandas, requests, folium, shapely, pyproj, branca

## License

Data sources:
- TfL data: [Open Government Licence](https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service)
- ONS Census data: [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/)
