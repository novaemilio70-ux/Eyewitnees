#!/usr/bin/env python3
"""
Debug script to check why some URLs show "10" as application name
"""

import sys
import os

# Add Python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python'))

from modules import db_manager

# URLs to check
urls_to_check = [
    'http://10.228.153.132:8080/',
    'http://10.228.153.194:8080/',
    'http://10.228.153.21:8080/',
    'http://10.228.34.175/',
    'http://10.228.20.57:8083',
    'https://10.228.48.62/',
    'https://10.228.20.38:8443/',
]

db_path = 'eyewitness_projects/laboon/laboon.db'

print("=" * 80)
print("DEBUG: Checking application names for problematic URLs")
print("=" * 80)

dbm = db_manager.DB_Manager(db_path)
dbm.open_connection()

# Get all HTTP objects
all_objects = dbm.get_complete_http()

print(f"\nTotal objects in database: {len(all_objects)}")
print("\nChecking problematic URLs:\n")

for url in urls_to_check:
    print(f"\n{'─' * 80}")
    print(f"URL: {url}")
    print('─' * 80)
    
    # Find matching object
    matching = [obj for obj in all_objects if obj.remote_system == url]
    
    if not matching:
        print("  ⚠️  NOT FOUND in database")
        continue
    
    obj = matching[0]
    
    # Show all relevant fields
    print(f"  page_title: {repr(obj.page_title)}")
    print(f"  category: {repr(obj.category)}")
    print(f"  default_creds: {repr(obj.default_creds)}")
    print(f"  ai_application_info: {repr(getattr(obj, 'ai_application_info', None))}")
    print(f"  _signature_app_name: {repr(getattr(obj, '_signature_app_name', None))}")
    
    # Simulate backend logic
    app_name = None
    
    # Priority 1: AI application info
    if hasattr(obj, 'ai_application_info') and obj.ai_application_info and isinstance(obj.ai_application_info, dict):
        app_name = obj.ai_application_info.get('application_name')
        print(f"\n  ✓ Found app_name from AI: {repr(app_name)}")
        if not app_name:
            manufacturer = obj.ai_application_info.get('manufacturer')
            model = obj.ai_application_info.get('model')
            if manufacturer and model:
                app_name = f"{manufacturer} {model}"
            elif manufacturer:
                app_name = manufacturer
            elif model:
                app_name = model
            if app_name:
                print(f"  ✓ Built app_name from manufacturer/model: {repr(app_name)}")
    
    # Priority 2: Extract from default_creds
    if not app_name and obj.default_creds and ' / ' in str(obj.default_creds):
        app_name = str(obj.default_creds).split(' / ')[0].strip()
        print(f"\n  ✓ Found app_name from default_creds: {repr(app_name)}")
    
    # Priority 3: Clean page title
    if not app_name and obj.page_title:
        page_title_str = str(obj.page_title)
        if page_title_str and page_title_str != 'Unknown':
            # Clean up common patterns
            for suffix in [' - Login', ' - Log in', ' Login', ' Log in', ' - Home', ' - Dashboard']:
                if page_title_str.endswith(suffix):
                    page_title_str = page_title_str[:-len(suffix)].strip()
            
            # Extract meaningful name
            if ' - ' in page_title_str:
                app_name = page_title_str.split(' - ')[0].strip()
            elif ' | ' in page_title_str:
                app_name = page_title_str.split(' | ')[0].strip()
            elif '|' in page_title_str:
                app_name = page_title_str.split('|')[0].strip()
            else:
                app_name = page_title_str[:50]
            print(f"\n  ✓ Found app_name from page_title: {repr(app_name)}")
    
    # Priority 4: Try to extract from URL hostname
    if not app_name and obj.remote_system:
        from urllib.parse import urlparse
        parsed = urlparse(obj.remote_system)
        hostname = parsed.hostname or parsed.netloc
        if hostname and hostname not in ['localhost', '127.0.0.1']:
            parts = hostname.split('.')
            if parts and parts[0]:
                app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
                print(f"\n  ✓ Found app_name from hostname: {repr(app_name)}")
    
    print(f"\n  ➜ FINAL app_name: {repr(app_name)}")
    
    # Determine display title
    page_title_str = str(obj.page_title) if obj.page_title else None
    if app_name:
        display_title = app_name
    elif page_title_str and page_title_str != 'Unknown':
        display_title = page_title_str
    else:
        from urllib.parse import urlparse
        parsed = urlparse(obj.remote_system)
        display_title = parsed.netloc or "Unknown"
    
    print(f"  ➜ FINAL display_title: {repr(display_title)}")

dbm.close()

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)

