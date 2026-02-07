#!/usr/bin/env python3
"""Script to regenerate report with new format from existing database"""

import sys
import os
import argparse
from datetime import datetime

# Add Python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python'))

from modules.db_manager import DB_Manager
from modules.reporting import sort_data_and_write
from modules.helpers import create_folders_css

class FakeCLI:
    """Fake CLI object for report generation"""
    def __init__(self, output_dir):
        self.d = output_dir
        self.results = 50  # Results per page
        self.date = datetime.now().strftime('%Y-%m-%d')
        self.time = datetime.now().strftime('%H:%M:%S')

def regenerate_report(db_path, output_dir=None):
    """Regenerate report from existing database"""
    
    if output_dir is None:
        output_dir = os.path.dirname(db_path)
    
    print(f"[*] Loading data from: {db_path}")
    print(f"[*] Output directory: {output_dir}")
    
    # Load data from database
    dbm = DB_Manager(db_path)
    dbm.open_connection()
    
    # Get options from database
    try:
        cli_parsed = dbm.get_options()
        cli_parsed.d = output_dir
    except:
        # If no options stored, create fake CLI
        cli_parsed = FakeCLI(output_dir)
    
    # Get all HTTP objects
    results = dbm.get_complete_http()
    dbm.close()
    
    print(f"[+] Loaded {len(results)} results from database")
    
    # Ensure output directory exists and has CSS files
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Copy CSS/JS files if needed
    create_folders_css(cli_parsed)
    
    # Remove old report files
    import glob
    for old_report in glob.glob(os.path.join(output_dir, 'report*.html')):
        try:
            os.remove(old_report)
            print(f"[*] Removed old report: {os.path.basename(old_report)}")
        except:
            pass
    
    # Generate new report
    print("[*] Generating new report with modern format...")
    sort_data_and_write(cli_parsed, results)
    
    print(f"[+] Report generated successfully!")
    print(f"[+] Open: {os.path.join(output_dir, 'report.html')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Regenerate EyeWitness report with new format')
    parser.add_argument('db_path', help='Path to ew.db file')
    parser.add_argument('-o', '--output', help='Output directory (default: same as db_path)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db_path):
        print(f"[!] Error: Database file not found: {args.db_path}")
        sys.exit(1)
    
    regenerate_report(args.db_path, args.output)


