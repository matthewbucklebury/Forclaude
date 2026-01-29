#!/usr/bin/env python3
"""
UK Mobility Dashboard - Main Entry Point

Run this script to start the dashboard application.
"""

import argparse
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app.dashboard import create_app
from src.fetchers import TfLDataFetcher
from src.database import init_database


def main():
    parser = argparse.ArgumentParser(description='UK Mobility Dashboard')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Run command
    run_parser = subparsers.add_parser('run', help='Start the dashboard web server')
    run_parser.add_argument('--port', type=int, default=8050, help='Port to run on (default: 8050)')
    run_parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    run_parser.add_argument('--host', default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')

    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database with sample data')

    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch TfL data')
    fetch_parser.add_argument('--url', help='URL to fetch CSV from')
    fetch_parser.add_argument('--file', help='Local CSV file to import')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export data to CSV')
    export_parser.add_argument('--output', '-o', default='mobility_data.csv', help='Output file path')
    export_parser.add_argument('--start-date', help='Start date (YYYY-MM-DD)')
    export_parser.add_argument('--end-date', help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    if args.command == 'run' or args.command is None:
        print("Starting UK Mobility Dashboard...")
        app = create_app()

        # Check if database has data, if not offer to load sample data
        from src.database import get_session, get_engine, TransportJourney
        session = get_session()
        count = session.query(TransportJourney).count()
        session.close()

        if count == 0:
            print("\nNo data found in database.")
            print("Click 'Load Sample Data' in the dashboard to get started,")
            print("or run: python run.py init\n")

        port = getattr(args, 'port', 8050)
        host = getattr(args, 'host', '127.0.0.1')
        debug = getattr(args, 'debug', False)

        print(f"Dashboard running at http://{host}:{port}")
        app.run(debug=debug, port=port, host=host)

    elif args.command == 'init':
        print("Initializing database with sample TfL data...")
        init_database()
        fetcher = TfLDataFetcher()
        inserted, updated = fetcher.load_sample_data()
        print(f"Done! Inserted {inserted} records, updated {updated} records.")
        print("\nRun 'python run.py' to start the dashboard.")

    elif args.command == 'fetch':
        fetcher = TfLDataFetcher()

        if args.file:
            print(f"Importing from file: {args.file}")
            success, message, df = fetcher.load_from_file(args.file)
            if success and df is not None:
                parsed = fetcher.parse_tfl_datastore_format(df)
                inserted, updated = fetcher.import_data(parsed)
                print(f"Imported: {inserted} new, {updated} updated")
            else:
                print(f"Error: {message}")
                sys.exit(1)

        elif args.url:
            print(f"Fetching from URL: {args.url}")
            success, message = fetcher.fetch_and_import(args.url)
            print(message)
            if not success:
                sys.exit(1)

        else:
            print("Attempting to fetch from London Datastore...")
            success, message = fetcher.fetch_and_import()
            print(message)
            if not success:
                print("\nTip: Download the CSV manually from:")
                print("https://data.london.gov.uk/dataset/public-transport-journeys-type-transport/")
                print("Then run: python run.py fetch --file <path-to-csv>")

    elif args.command == 'export':
        from datetime import date, datetime

        fetcher = TfLDataFetcher()

        start = None
        end = None

        if args.start_date:
            start = datetime.strptime(args.start_date, '%Y-%m-%d').date()
        if args.end_date:
            end = datetime.strptime(args.end_date, '%Y-%m-%d').date()

        df = fetcher.get_journey_data(start_date=start, end_date=end)

        if df.empty:
            print("No data to export. Run 'python run.py init' first.")
            sys.exit(1)

        df.to_csv(args.output, index=False)
        print(f"Exported {len(df)} records to {args.output}")

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
