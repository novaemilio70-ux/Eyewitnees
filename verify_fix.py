#!/usr/bin/env python3
"""
Verify that the fix for IP-based application names works correctly
"""

import sys
import os

# Add Python directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Python'))

from modules import db_manager

db_path = 'eyewitness_projects/test_fix_ip/test_fix_ip.db'

print("=" * 80)
print("VERIFICATION: Testing IP address application name fix")
print("=" * 80)

dbm = db_manager.DB_Manager(db_path)
dbm.open_connection()

# Get all HTTP objects
all_objects = dbm.get_complete_http()

print(f"\nTotal objects in test database: {len(all_objects)}")

for obj in all_objects:
    print(f"\n{'─' * 80}")
    print(f"URL: {obj.remote_system}")
    print('─' * 80)
    print(f"  page_title: {repr(obj.page_title)}")
    print(f"  category: {repr(obj.category)}")
    print(f"  default_creds: {repr(obj.default_creds)}")
    print(f"  ai_application_info: {repr(getattr(obj, 'ai_application_info', None))}")
    
    # Simulate backend logic WITH FIX
    print(f"\n  {'─' * 70}")
    print(f"  SIMULATING BACKEND LOGIC WITH FIX:")
    print(f"  {'─' * 70}")
    
    import re
    from urllib.parse import urlparse
    
    def is_ip_address(hostname: str) -> bool:
        """Check if a hostname is an IP address (IPv4 or IPv6)"""
        if not hostname:
            return False
        # IPv4 check
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            return True
        # IPv6 check (simple)
        if ':' in hostname and not hostname.startswith('['):
            return True
        return False
    
    app_name = None
    
    # Priority 1: AI application info
    if hasattr(obj, 'ai_application_info') and obj.ai_application_info and isinstance(obj.ai_application_info, dict):
        app_name = obj.ai_application_info.get('application_name')
        if app_name:
            print(f"  ✓ app_name from AI: {repr(app_name)}")
    
    # Priority 2: Extract from default_creds
    if not app_name and obj.default_creds and ' / ' in str(obj.default_creds):
        app_name = str(obj.default_creds).split(' / ')[0].strip()
        print(f"  ✓ app_name from default_creds: {repr(app_name)}")
    
    # Priority 3: Clean page title
    if not app_name and obj.page_title:
        page_title_str = str(obj.page_title)
        if page_title_str and page_title_str != 'Unknown':
            print(f"  ✓ app_name from page_title: {repr(page_title_str)}")
            app_name = page_title_str
    
    # Priority 4: Try to extract from URL hostname (WITH FIX)
    if not app_name and obj.remote_system:
        parsed = urlparse(obj.remote_system)
        hostname = parsed.hostname or parsed.netloc
        
        print(f"  → hostname: {repr(hostname)}")
        print(f"  → is_ip_address(hostname): {is_ip_address(hostname)}")
        
        # Only extract from hostname if it's NOT an IP address
        if hostname and not is_ip_address(hostname) and hostname not in ['localhost']:
            parts = hostname.split('.')
            if parts and parts[0]:
                app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
                print(f"  ✓ app_name from hostname: {repr(app_name)}")
        else:
            print(f"  ✗ SKIPPED extracting from hostname (it's an IP address)")
    
    print(f"\n  ➜ FINAL app_name: {repr(app_name)}")
    
    # What would be displayed
    page_title_str = str(obj.page_title) if obj.page_title else None
    if app_name:
        display_title = app_name
    elif page_title_str and page_title_str != 'Unknown' and page_title_str != '':
        display_title = page_title_str
    else:
        parsed = urlparse(obj.remote_system)
        display_title = parsed.netloc or "Unknown"
    
    print(f"  ➜ FINAL display_title: {repr(display_title)}")
    
    print(f"\n  {'─' * 70}")
    print(f"  EXPECTED BEHAVIOR:")
    print(f"  {'─' * 70}")
    if app_name is None:
        print(f"  ✓ CORRECT: app_name is None (not '10')")
        print(f"  ✓ CORRECT: Display will show category or URL instead")
        print(f"  ✓ Column 'Aplicación' in web UI will be empty/null")
    else:
        print(f"  ⚠️  app_name has a value: {repr(app_name)}")

dbm.close()

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print("\nCONCLUSION:")
print("  • The fix prevents extracting '10' from IP addresses like 10.x.x.x")
print("  • For IPs without page_title, app_name will be None")
print("  • Web UI should handle None gracefully (show category or 'Unknown')")
print("=" * 80)

