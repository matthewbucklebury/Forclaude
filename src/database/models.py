"""
SQLite database models for UK mobility data storage.
Designed to be extensible for future data sources (ORR, DfT, Google Mobility).
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class TransportJourney(Base):
    """
    Stores transport journey/ridership data.
    Primary table for TfL and future ORR/DfT data.
    """
    __tablename__ = 'transport_journeys'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Data source identifier (tfl, orr, dft, google_mobility)
    source = Column(String(50), nullable=False, index=True)

    # Transport mode (tube, bus, dlr, overground, tram, cable_car, national_rail, road)
    mode = Column(String(50), nullable=False, index=True)

    # Date of the observation
    date = Column(Date, nullable=False, index=True)

    # TfL uses reporting periods (1-13 per year)
    # Null for other sources that use calendar dates
    period_number = Column(Integer, nullable=True)
    period_year = Column(Integer, nullable=True)

    # Passenger journeys (millions for TfL, raw numbers for others)
    journeys_millions = Column(Float, nullable=True)
    journeys_absolute = Column(Integer, nullable=True)

    # Indexed value (100 = baseline)
    indexed_value = Column(Float, nullable=True)

    # Baseline reference (e.g., "2019_avg", "jan_2022")
    baseline_reference = Column(String(50), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source', 'mode', 'date', name='uix_source_mode_date'),
        Index('idx_source_mode_date', 'source', 'mode', 'date'),
    )

    def __repr__(self):
        return f"<TransportJourney(source={self.source}, mode={self.mode}, date={self.date}, journeys={self.journeys_millions}M)>"


class BaselineData(Base):
    """
    Stores baseline reference values for indexing calculations.
    """
    __tablename__ = 'baseline_data'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    mode = Column(String(50), nullable=False)
    baseline_name = Column(String(50), nullable=False)  # e.g., "2019_avg", "jan_2022"
    baseline_value = Column(Float, nullable=False)  # Average journeys for this baseline
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source', 'mode', 'baseline_name', name='uix_baseline'),
    )


class DataFetchLog(Base):
    """
    Tracks data fetch operations for debugging and scheduling.
    """
    __tablename__ = 'data_fetch_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    fetch_type = Column(String(50), nullable=False)  # full, incremental
    status = Column(String(20), nullable=False)  # success, failed, partial
    records_fetched = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    error_message = Column(String(500), nullable=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)


def get_database_path():
    """Get the database path, defaulting to project data directory."""
    db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, 'mobility.db')


def get_engine(db_path=None):
    """Create and return a database engine."""
    if db_path is None:
        db_path = get_database_path()
    return create_engine(f'sqlite:///{db_path}', echo=False)


def get_session(engine=None):
    """Create and return a database session."""
    if engine is None:
        engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_database(db_path=None):
    """Initialize the database schema."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
