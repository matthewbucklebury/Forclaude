#!/usr/bin/env python3
"""
Main runner script for London Tube Station Population Analysis.

This script:
1. Downloads tube station data from TfL API
2. Generates population distribution data based on 2021 Census
3. Analyzes population within 500m of each station
4. Creates an interactive map visualization

Usage:
    python run_analysis.py
"""

import subprocess
import sys
from pathlib import Path


def run_script(script_name, description):
    """Run a Python script and handle errors."""
    print(f"\n{'='*60}")
    print(f"STEP: {description}")
    print(f"{'='*60}")

    script_path = Path(__file__).parent / script_name
    result = subprocess.run([sys.executable, str(script_path)], capture_output=False)

    if result.returncode != 0:
        print(f"Warning: {script_name} completed with issues")
        return False
    return True


def main():
    print("="*60)
    print("LONDON TUBE STATION POPULATION ANALYSIS")
    print("Finding which tube line has the most people living nearby")
    print("="*60)

    # Step 1: Fetch tube station data
    run_script("fetch_data.py", "Downloading tube station data from TfL")

    # Step 2: Generate/download population data
    run_script("download_population_data.py", "Preparing population data")

    # Step 3: Run population analysis
    run_script("analyze_population.py", "Analyzing station catchment populations")

    # Step 4: Create interactive map
    run_script("create_map.py", "Creating interactive map")

    print("\n" + "="*60)
    print("ANALYSIS COMPLETE!")
    print("="*60)
    print("\nOutput files:")
    print("  - tube_population_map.html  : Interactive map (open in browser)")
    print("  - data/analysis_results.json: Raw analysis data")
    print("\nThe map shows:")
    print("  - All tube stations with 500m catchment circles")
    print("  - Population density indicated by color")
    print("  - Line-by-line population rankings in the sidebar")


if __name__ == "__main__":
    main()
