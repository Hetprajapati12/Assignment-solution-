#!/usr/bin/env python
"""
Generate test CSV files with temperature data.

This script creates CSV files of various sizes for testing
the temperature data processing pipeline.

Usage:
    python generate_test_data.py --rows 1000000 --output large_data.csv
    python generate_test_data.py --rows 100 --output small_data.csv
"""

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_temperature_data(
    output_path: str,
    num_rows: int,
    num_cities: int = 100,
    start_date: datetime = None,
    include_header: bool = True
) -> None:
    """
    Generate a CSV file with random temperature data.
    
    Args:
        output_path: Path to the output CSV file
        num_rows: Number of rows to generate
        num_cities: Number of unique cities
        start_date: Starting date for timestamps
        include_header: Whether to include a header row
    """
    if start_date is None:
        start_date = datetime(2024, 1, 1, 0, 0, 0)
    
    city_ids = [f"CITY_{i:04d}" for i in range(1, num_cities + 1)]
    
    # City base temperatures (simulating different climates)
    city_base_temps = {
        city: random.uniform(-10, 35)
        for city in city_ids
    }
    
    print(f"Generating {num_rows:,} rows of temperature data...")
    print(f"Cities: {num_cities}")
    print(f"Output: {output_path}")
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        if include_header:
            writer.writerow(['city_id', 'temp', 'timestamp'])
        
        for i in range(num_rows):
            # Select random city
            city_id = random.choice(city_ids)
            
            # Generate temperature with variation around city's base
            base_temp = city_base_temps[city_id]
            temp = base_temp + random.uniform(-15, 15)
            temp = round(max(-89, min(57, temp)), 2)  # Clamp to valid range
            
            # Generate timestamp (spread evenly across the year)
            time_offset = timedelta(
                seconds=random.randint(0, 365 * 24 * 3600)
            )
            timestamp = start_date + time_offset
            
            writer.writerow([
                city_id,
                temp,
                timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')
            ])
            
            # Progress indicator
            if (i + 1) % 100000 == 0:
                print(f"  Generated {i + 1:,} rows...")
    
    # Calculate file size
    file_size = Path(output_path).stat().st_size
    size_mb = file_size / (1024 * 1024)
    
    print(f"\nCompleted!")
    print(f"File size: {size_mb:.2f} MB")
    print(f"Rows per city (avg): {num_rows // num_cities:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate test temperature data CSV files"
    )
    parser.add_argument(
        '--rows', '-r',
        type=int,
        default=100000,
        help='Number of rows to generate (default: 100,000)'
    )
    parser.add_argument(
        '--cities', '-c',
        type=int,
        default=100,
        help='Number of unique cities (default: 100)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='test_data.csv',
        help='Output file path (default: test_data.csv)'
    )
    parser.add_argument(
        '--no-header',
        action='store_true',
        help='Exclude header row from output'
    )
    
    args = parser.parse_args()
    
    generate_temperature_data(
        output_path=args.output,
        num_rows=args.rows,
        num_cities=args.cities,
        include_header=not args.no_header
    )


if __name__ == '__main__':
    main()
