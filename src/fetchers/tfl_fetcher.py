"""
TfL Data Fetcher

Fetches Transport for London ridership data from:
1. London Datastore CSV files (primary source)
2. Manual CSV file imports

Data source: https://data.london.gov.uk/dataset/public-transport-journeys-type-transport/
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Optional, Dict, List, Tuple
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..database import (
    TransportJourney,
    BaselineData,
    DataFetchLog,
    get_session,
    get_engine,
    init_database,
)


# TfL reporting periods to approximate dates
# TfL uses 13 periods per year (28 days each, with periods 1 and 13 adjusted)
TFL_PERIOD_START_DATES = {
    # Period number: (month, day) approximate start
    1: (4, 1),   # April start (financial year)
    2: (4, 29),
    3: (5, 27),
    4: (6, 24),
    5: (7, 22),
    6: (8, 19),
    7: (9, 16),
    8: (10, 14),
    9: (11, 11),
    10: (12, 9),
    11: (1, 6),
    12: (2, 3),
    13: (3, 3),
}


# Mode name mapping from CSV to normalized names
MODE_MAPPING = {
    'bus': 'bus',
    'buses': 'bus',
    'london buses': 'bus',
    'underground': 'tube',
    'tube': 'tube',
    'london underground': 'tube',
    'lu': 'tube',
    'dlr': 'dlr',
    'docklands light railway': 'dlr',
    'overground': 'overground',
    'london overground': 'overground',
    'tram': 'tram',
    'tramlink': 'tram',
    'cable car': 'cable_car',
    'emirates air line': 'cable_car',
    'eal': 'cable_car',
    'elizabeth line': 'elizabeth_line',
    'crossrail': 'elizabeth_line',
}


class TfLDataFetcher:
    """Fetches and processes TfL transport data."""

    # London Datastore URL for TfL journey data
    DATASTORE_URL = "https://data.london.gov.uk/download/public-transport-journeys-type-transport/2a61d2e6-73e4-4042-8be3-03c6a0b7e0b4/tfl-journeys-type.csv"

    # Alternative direct URLs to try
    ALTERNATIVE_URLS = [
        "https://data.london.gov.uk/download/public-transport-journeys-type-transport/tfl-journeys-type.csv",
    ]

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the fetcher."""
        self.engine = get_engine(db_path)
        init_database(db_path)

    def fetch_from_url(self, url: Optional[str] = None) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Fetch TfL data from URL.

        Returns:
            Tuple of (success, message, dataframe)
        """
        urls_to_try = [url] if url else [self.DATASTORE_URL] + self.ALTERNATIVE_URLS

        for try_url in urls_to_try:
            if not try_url:
                continue
            try:
                response = requests.get(try_url, timeout=30)
                response.raise_for_status()

                # Try to parse as CSV
                from io import StringIO
                df = pd.read_csv(StringIO(response.text))
                return True, f"Successfully fetched from {try_url}", df

            except requests.RequestException as e:
                continue
            except pd.errors.ParserError as e:
                continue

        return False, "Could not fetch data from any URL. Use load_from_file() with a local CSV.", None

    def load_from_file(self, filepath: str) -> Tuple[bool, str, Optional[pd.DataFrame]]:
        """
        Load TfL data from a local CSV file.

        Expected CSV format (London Datastore style):
        - Columns: Period, Year, Bus, Underground, DLR, Overground, Tram, etc.
        - Values: Journey counts in millions

        Returns:
            Tuple of (success, message, dataframe)
        """
        if not os.path.exists(filepath):
            return False, f"File not found: {filepath}", None

        try:
            df = pd.read_csv(filepath)
            return True, f"Loaded {len(df)} rows from {filepath}", df
        except Exception as e:
            return False, f"Error reading file: {str(e)}", None

    def parse_tfl_datastore_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse the London Datastore TfL journey data format.

        Handles multiple possible column naming conventions.
        """
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Identify period and year columns
        period_col = None
        year_col = None

        for col in df.columns:
            if 'period' in col and 'year' not in col:
                period_col = col
            elif 'year' in col or col == 'financial year':
                year_col = col

        if period_col is None:
            # Try to find period column by other means
            for col in df.columns:
                if df[col].dtype in ['int64', 'float64'] and df[col].max() <= 13:
                    period_col = col
                    break

        # Melt the dataframe to long format
        id_vars = [col for col in [period_col, year_col] if col is not None]
        value_vars = [col for col in df.columns if col not in id_vars and col not in ['total', 'all modes']]

        # Filter to only transport mode columns
        mode_cols = []
        for col in value_vars:
            normalized = col.lower().strip()
            if any(mode in normalized for mode in ['bus', 'underground', 'tube', 'dlr', 'overground', 'tram', 'cable', 'elizabeth', 'crossrail']):
                mode_cols.append(col)

        if not mode_cols:
            mode_cols = value_vars

        df_long = df.melt(
            id_vars=id_vars,
            value_vars=mode_cols,
            var_name='mode_raw',
            value_name='journeys_millions'
        )

        # Parse period and year
        if period_col:
            df_long['period_number'] = pd.to_numeric(df_long[period_col], errors='coerce')
        else:
            df_long['period_number'] = None

        if year_col:
            # Handle financial year format like "2022/23"
            def parse_year(val):
                if pd.isna(val):
                    return None
                val_str = str(val).strip()
                if '/' in val_str:
                    return int(val_str.split('/')[0])
                try:
                    return int(float(val_str))
                except:
                    return None
            df_long['period_year'] = df_long[year_col].apply(parse_year)
        else:
            df_long['period_year'] = None

        # Normalize mode names
        df_long['mode'] = df_long['mode_raw'].str.lower().str.strip().map(
            lambda x: MODE_MAPPING.get(x, x.replace(' ', '_'))
        )

        # Convert journeys to numeric
        df_long['journeys_millions'] = pd.to_numeric(df_long['journeys_millions'], errors='coerce')

        # Calculate approximate date from period
        def period_to_date(row):
            if pd.isna(row['period_number']) or pd.isna(row['period_year']):
                return None
            period = int(row['period_number'])
            year = int(row['period_year'])
            if period not in TFL_PERIOD_START_DATES:
                return None
            month, day = TFL_PERIOD_START_DATES[period]
            # Adjust year for periods 11-13 (Jan-Mar are in following calendar year)
            if period >= 11:
                year += 1
            try:
                return date(year, month, day)
            except ValueError:
                return None

        df_long['date'] = df_long.apply(period_to_date, axis=1)

        # Keep only valid rows
        df_long = df_long[df_long['date'].notna() & df_long['journeys_millions'].notna()]

        return df_long[['date', 'mode', 'period_number', 'period_year', 'journeys_millions']]

    def calculate_baselines(self, session, baseline_year: int = 2019) -> Dict[str, float]:
        """
        Calculate baseline values for each mode.

        Args:
            session: Database session
            baseline_year: Year to use as baseline (default 2019, pre-pandemic)

        Returns:
            Dict mapping mode to average journeys in baseline year
        """
        from sqlalchemy import func

        baselines = {}

        # Query average journeys by mode for baseline year
        results = session.query(
            TransportJourney.mode,
            func.avg(TransportJourney.journeys_millions).label('avg_journeys')
        ).filter(
            TransportJourney.source == 'tfl',
            TransportJourney.period_year == baseline_year
        ).group_by(TransportJourney.mode).all()

        for mode, avg_journeys in results:
            if avg_journeys:
                baselines[mode] = avg_journeys

                # Store in database
                baseline = BaselineData(
                    source='tfl',
                    mode=mode,
                    baseline_name=f'{baseline_year}_avg',
                    baseline_value=avg_journeys,
                    description=f'Average journeys in {baseline_year} (pre-pandemic baseline)'
                )
                # Upsert
                existing = session.query(BaselineData).filter_by(
                    source='tfl', mode=mode, baseline_name=f'{baseline_year}_avg'
                ).first()
                if existing:
                    existing.baseline_value = avg_journeys
                else:
                    session.add(baseline)

        session.commit()
        return baselines

    def update_indexed_values(self, session, baseline_name: str = '2019_avg'):
        """Update indexed values based on baseline."""
        # Get baselines
        baselines = {}
        baseline_records = session.query(BaselineData).filter_by(
            source='tfl', baseline_name=baseline_name
        ).all()

        for b in baseline_records:
            baselines[b.mode] = b.baseline_value

        # Update indexed values
        journeys = session.query(TransportJourney).filter_by(source='tfl').all()
        for j in journeys:
            if j.mode in baselines and baselines[j.mode] > 0:
                j.indexed_value = (j.journeys_millions / baselines[j.mode]) * 100
                j.baseline_reference = baseline_name

        session.commit()

    def import_data(self, df: pd.DataFrame, calculate_baseline: bool = True) -> Tuple[int, int]:
        """
        Import parsed data into the database.

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        session = get_session(self.engine)

        inserted = 0
        updated = 0

        log = DataFetchLog(
            source='tfl',
            fetch_type='import',
            status='in_progress',
            started_at=datetime.utcnow()
        )
        session.add(log)
        session.commit()

        try:
            for _, row in df.iterrows():
                existing = session.query(TransportJourney).filter_by(
                    source='tfl',
                    mode=row['mode'],
                    date=row['date']
                ).first()

                if existing:
                    existing.journeys_millions = row['journeys_millions']
                    existing.period_number = row.get('period_number')
                    existing.period_year = row.get('period_year')
                    existing.updated_at = datetime.utcnow()
                    updated += 1
                else:
                    journey = TransportJourney(
                        source='tfl',
                        mode=row['mode'],
                        date=row['date'],
                        period_number=row.get('period_number'),
                        period_year=row.get('period_year'),
                        journeys_millions=row['journeys_millions'],
                    )
                    session.add(journey)
                    inserted += 1

            session.commit()

            # Calculate baselines if we have 2019 data
            if calculate_baseline:
                self.calculate_baselines(session, baseline_year=2019)
                self.update_indexed_values(session)

            log.status = 'success'
            log.records_fetched = len(df)
            log.records_inserted = inserted
            log.records_updated = updated
            log.completed_at = datetime.utcnow()
            session.commit()

        except Exception as e:
            session.rollback()
            log.status = 'failed'
            log.error_message = str(e)[:500]
            log.completed_at = datetime.utcnow()
            session.commit()
            raise

        finally:
            session.close()

        return inserted, updated

    def fetch_and_import(self, url: Optional[str] = None) -> Tuple[bool, str]:
        """
        Fetch data from URL and import into database.

        Returns:
            Tuple of (success, message)
        """
        success, message, df = self.fetch_from_url(url)

        if not success or df is None:
            return False, message

        try:
            parsed_df = self.parse_tfl_datastore_format(df)
            inserted, updated = self.import_data(parsed_df)
            return True, f"Imported TfL data: {inserted} new records, {updated} updated"
        except Exception as e:
            return False, f"Import failed: {str(e)}"

    def load_sample_data(self) -> Tuple[int, int]:
        """
        Load sample TfL data for demonstration purposes.

        Creates realistic sample data from 2019-2024 showing:
        - Pre-pandemic baseline (2019)
        - COVID crash (2020)
        - Gradual recovery (2021-2024)
        """
        np.random.seed(42)

        # Base monthly ridership (millions) per period - approximate from TfL data
        base_journeys = {
            'tube': 110,      # ~110M journeys per period
            'bus': 150,       # ~150M journeys per period
            'dlr': 10,        # ~10M journeys per period
            'overground': 14, # ~14M journeys per period
            'tram': 2.5,      # ~2.5M journeys per period
        }

        # COVID impact factors by year
        covid_impact = {
            2019: 1.0,
            2020: 0.35,  # Massive drop
            2021: 0.55,  # Partial recovery
            2022: 0.75,  # Continued recovery
            2023: 0.85,  # Near recovery
            2024: 0.92,  # Almost back to normal
        }

        # Seasonal factors by period (1-13)
        seasonal = {
            1: 0.95, 2: 1.0, 3: 1.0, 4: 0.95,  # Apr-Jul
            5: 0.85, 6: 0.85,  # Aug (summer holidays)
            7: 1.0, 8: 1.05, 9: 1.05,  # Sep-Nov
            10: 0.95, 11: 0.9, 12: 0.95, 13: 1.0  # Dec-Mar
        }

        records = []
        for year in range(2019, 2025):
            for period in range(1, 14):
                for mode, base in base_journeys.items():
                    # Calculate journeys with factors
                    journeys = base * covid_impact[year] * seasonal[period]
                    # Add random noise (5%)
                    journeys *= np.random.uniform(0.95, 1.05)

                    # Calculate date
                    month, day = TFL_PERIOD_START_DATES[period]
                    adj_year = year + 1 if period >= 11 else year
                    try:
                        record_date = date(adj_year, month, day)
                    except ValueError:
                        continue

                    records.append({
                        'date': record_date,
                        'mode': mode,
                        'period_number': period,
                        'period_year': year,
                        'journeys_millions': round(journeys, 2)
                    })

        df = pd.DataFrame(records)
        return self.import_data(df, calculate_baseline=True)

    def get_journey_data(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        modes: Optional[List[str]] = None,
        aggregation: str = 'period'  # period, weekly, monthly
    ) -> pd.DataFrame:
        """
        Query journey data from database.

        Args:
            start_date: Filter start date
            end_date: Filter end date
            modes: List of modes to include
            aggregation: How to aggregate data

        Returns:
            DataFrame with journey data
        """
        session = get_session(self.engine)

        query = session.query(TransportJourney).filter(
            TransportJourney.source == 'tfl'
        )

        if start_date:
            query = query.filter(TransportJourney.date >= start_date)
        if end_date:
            query = query.filter(TransportJourney.date <= end_date)
        if modes:
            query = query.filter(TransportJourney.mode.in_(modes))

        query = query.order_by(TransportJourney.date, TransportJourney.mode)

        records = query.all()
        session.close()

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame([{
            'date': r.date,
            'mode': r.mode,
            'journeys_millions': r.journeys_millions,
            'indexed_value': r.indexed_value,
            'period_number': r.period_number,
            'period_year': r.period_year,
        } for r in records])

        return df


if __name__ == '__main__':
    # Test the fetcher
    fetcher = TfLDataFetcher()

    print("Loading sample TfL data...")
    inserted, updated = fetcher.load_sample_data()
    print(f"Inserted: {inserted}, Updated: {updated}")

    print("\nQuerying data...")
    df = fetcher.get_journey_data(
        start_date=date(2022, 1, 1),
        modes=['tube', 'bus']
    )
    print(df.head(20))
