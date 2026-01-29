# UK Mobility Dashboard

Interactive data visualization tool tracking UK mobility trends from 2019-present using Transport for London (TfL) ridership data.

## Features

- **Multi-line time series chart** showing ridership across transport modes (Tube, Bus, DLR, Overground, Tram)
- **Toggle between views**: Absolute numbers (millions of journeys) or Indexed values (100 = 2019 baseline)
- **Date range selector** with quick presets (2019, 2022+, Last Year, All Time)
- **Rolling average smoothing** to reduce volatility
- **Aggregation options**: Period, Monthly, or Quarterly views
- **Export to CSV** for further analysis
- **SQLite storage** for persistent data

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize with Sample Data

```bash
python run.py init
```

This loads realistic sample data from 2019-2024 showing pre-pandemic baseline and COVID recovery trends.

### 3. Run the Dashboard

```bash
python run.py
```

Open http://127.0.0.1:8050 in your browser.

## Usage

### Command Line Interface

```bash
# Start dashboard (default)
python run.py run --port 8050 --debug

# Initialize database with sample data
python run.py init

# Import TfL data from local CSV
python run.py fetch --file path/to/tfl-journeys.csv

# Attempt to fetch from London Datastore (may require manual download)
python run.py fetch

# Export data to CSV
python run.py export -o my_data.csv --start-date 2022-01-01 --end-date 2024-12-31
```

### Dashboard Controls

| Control | Description |
|---------|-------------|
| Transport Modes | Select which modes to display (multi-select) |
| View Type | Switch between absolute journeys and indexed values |
| Aggregation | Group data by TfL period, month, or quarter |
| Smoothing | Enable 3-period rolling average |
| Date Range | Filter data by date range |
| Quick Select | Preset date ranges |

## Data Sources

### TfL Data (Phase 1 - Current)

Primary source: [London Datastore - Public Transport Journeys by Type of Transport](https://data.london.gov.uk/dataset/public-transport-journeys-type-transport/)

The data includes:
- London Underground (Tube)
- London Buses
- Docklands Light Railway (DLR)
- London Overground
- Tramlink
- Emirates Air Line (cable car)

**Note**: TfL uses 13 reporting periods per year (approximately 28 days each), aligned with their financial year starting in April.

### Importing Real TfL Data

1. Download the CSV from the [London Datastore](https://data.london.gov.uk/dataset/public-transport-journeys-type-transport/)
2. Run: `python run.py fetch --file path/to/downloaded.csv`

The importer handles various CSV formats from the Datastore and normalizes them automatically.

## Architecture

```
uk-mobility-dashboard/
├── run.py                 # Main entry point
├── requirements.txt       # Python dependencies
├── data/
│   └── mobility.db        # SQLite database (created on first run)
└── src/
    ├── app/
    │   └── dashboard.py   # Plotly/Dash web application
    ├── database/
    │   └── models.py      # SQLAlchemy models
    └── fetchers/
        └── tfl_fetcher.py # TfL data fetcher and parser
```

### Database Schema

**transport_journeys**: Main data table
- `source`: Data source identifier (tfl, orr, dft, etc.)
- `mode`: Transport mode (tube, bus, dlr, etc.)
- `date`: Observation date
- `journeys_millions`: Raw journey count
- `indexed_value`: Value relative to baseline (100 = baseline)

**baseline_data**: Reference values for indexing
- Stores average values for comparison (default: 2019 pre-pandemic)

**data_fetch_log**: Audit trail for data imports

## Future Phases

The architecture supports additional data sources:

- **Phase 2**: ORR National Rail data (quarterly CSV)
- **Phase 3**: DfT road traffic statistics (monthly CSV)
- **Phase 4**: Archived Google Mobility data (2020-2022)

To add a new source, create a new fetcher in `src/fetchers/` following the `TfLDataFetcher` pattern.

## Development

```bash
# Run in debug mode with auto-reload
python run.py run --debug

# Run tests (if added)
pytest tests/
```

## License

MIT
