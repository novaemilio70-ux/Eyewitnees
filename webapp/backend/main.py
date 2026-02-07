#!/usr/bin/env python3
"""
EyeWitness Web Application Backend
FastAPI server for dynamic security analysis visualization
"""

import os
import sys
import re
import glob
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json

# Add parent directory to path to import EyeWitness modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'Python'))

from modules.db_manager import DB_Manager
from modules.objects import HTTPTableObject


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


app = FastAPI(
    title="EyeWitness Security Dashboard",
    description="Dynamic security analysis visualization platform",
    version="1.0.0"
)

# CORS configuration - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variable to store current database path
CURRENT_DB_PATH = None


def find_latest_database(base_dir: str = None, project_name: str = None) -> Optional[str]:
    """Find the most recent database file in EyeWitness project directories
    
    Args:
        base_dir: Base directory to search (defaults to EyeWitness root)
        project_name: Specific project name to load (if specified, ignores recency)
    
    Returns:
        Path to database file or None
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Search in project-based directories (new format)
    projects_dir = os.path.join(base_dir, 'eyewitness_projects')
    
    # If a specific project is requested, try to load it directly
    if project_name:
        if os.path.exists(projects_dir):
            project_path = os.path.join(projects_dir, project_name)
            if os.path.isdir(project_path):
                # Look for {project_name}.db
                db_path = os.path.join(project_path, f'{project_name}.db')
                if os.path.exists(db_path):
                    return db_path
                # Also check for ew.db (fallback)
                db_path_ew = os.path.join(project_path, 'ew.db')
                if os.path.exists(db_path_ew):
                    return db_path_ew
        return None  # Specified project not found
    
    db_files = []
    
    # Priority 1: Search in eyewitness_projects/ (new format)
    if os.path.exists(projects_dir):
        for proj_name in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, proj_name)
            if os.path.isdir(project_path):
                # Look for {project_name}.db
                db_path = os.path.join(project_path, f'{proj_name}.db')
                if os.path.exists(db_path):
                    db_files.append((db_path, os.path.getmtime(db_path)))
                # Also check for ew.db (fallback)
                db_path_ew = os.path.join(project_path, 'ew.db')
                if os.path.exists(db_path_ew):
                    db_files.append((db_path_ew, os.path.getmtime(db_path_ew)))
    
    # Priority 2: Legacy format - date-based directories (YYYY-MM-DD_HHMMSS)
    pattern = re.compile(r'\d{4}-\d{2}-\d{2}_\d{6}')
    search_paths = [
        base_dir,
        os.path.join(base_dir, 'test_output'),
        os.path.join(os.getcwd(), 'test_output'),
    ]
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        
        # Check subdirectories matching date pattern (legacy)
        for item in os.listdir(search_path):
            item_path = os.path.join(search_path, item)
            if os.path.isdir(item_path) and pattern.match(item):
                db_path = os.path.join(item_path, 'ew.db')
                if os.path.exists(db_path):
                    db_files.append((db_path, os.path.getmtime(db_path)))
    
    if db_files:
        # Return the most recent database
        db_files.sort(key=lambda x: x[1], reverse=True)
        return db_files[0][0]
    
    return None


def get_db_manager(db_path: Optional[str] = None):
    """Get database manager instance"""
    if db_path is None:
        db_path = CURRENT_DB_PATH
    
    # If still no path, check for EYEWITNESS_PROJECT environment variable
    if db_path is None:
        project_name = os.environ.get('EYEWITNESS_PROJECT')
        if project_name:
            db_path = find_latest_database(project_name=project_name)
            if db_path:
                print(f"[*] Using project from EYEWITNESS_PROJECT env var: {project_name}")
    
    # If still no path, try to find the latest database
    if db_path is None:
        db_path = find_latest_database()
    
    if db_path is None or not os.path.exists(db_path):
        raise HTTPException(
            status_code=404, 
            detail="Database not found. Please run EyeWitness first, set EYEWITNESS_PROJECT env var, or specify a database path using /api/load-database"
        )
    
    # Convert to absolute path to avoid issues with working directory
    abs_db_path = os.path.abspath(db_path)
    dbm = DB_Manager(abs_db_path)
    dbm.open_connection()
    # Store the database directory for later use (use absolute path)
    dbm._db_dir = os.path.dirname(abs_db_path)
    # Also store the absolute database path
    dbm._db_path_abs = abs_db_path
    return dbm


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "EyeWitness Security Dashboard API",
        "version": "1.0.0",
        "endpoints": {
            "dashboard": "/api/dashboard",
            "reports": "/api/reports",
            "passwords": "/api/passwords",
            "ai-analysis": "/api/ai-analysis",
            "screenshot": "/api/screenshot/{scan_id}/{url_hash}"
        }
    }


@app.get("/api/projects")
async def list_projects():
    """List all available EyeWitness projects"""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    projects_dir = os.path.join(base_dir, 'eyewitness_projects')
    
    projects = []
    current_project = None
    
    if os.path.exists(projects_dir):
        for project_name in os.listdir(projects_dir):
            project_path = os.path.join(projects_dir, project_name)
            if os.path.isdir(project_path):
                # Check for database files
                db_path = os.path.join(project_path, f'{project_name}.db')
                if not os.path.exists(db_path):
                    db_path = os.path.join(project_path, 'ew.db')
                
                if os.path.exists(db_path):
                    mtime = os.path.getmtime(db_path)
                    size = os.path.getsize(db_path)
                    
                    # Check if this is the current project
                    is_current = (CURRENT_DB_PATH and os.path.abspath(db_path) == os.path.abspath(CURRENT_DB_PATH))
                    
                    project_info = {
                        "name": project_name,
                        "db_path": db_path,
                        "last_modified": datetime.fromtimestamp(mtime).isoformat(),
                        "size_bytes": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "is_current": is_current
                    }
                    projects.append(project_info)
                    
                    if is_current:
                        current_project = project_name
    
    # Sort by last modified (most recent first)
    projects.sort(key=lambda x: x['last_modified'], reverse=True)
    
    # If no current project but projects exist, mark the most recent as "default"
    if not current_project and projects:
        projects[0]['is_default'] = True
    
    return {
        "projects": projects,
        "current_project": current_project,
        "total": len(projects),
        "env_project": os.environ.get('EYEWITNESS_PROJECT')
    }


@app.post("/api/load-project")
async def load_project(project_name: str):
    """Load a specific project by name"""
    global CURRENT_DB_PATH
    
    db_path = find_latest_database(project_name=project_name)
    if not db_path:
        raise HTTPException(
            status_code=404, 
            detail=f"Project '{project_name}' not found in eyewitness_projects/"
        )
    
    CURRENT_DB_PATH = db_path
    return {
        "status": "success",
        "project_name": project_name,
        "db_path": db_path
    }


@app.post("/api/load-database")
async def load_database(db_path: str):
    """Load a specific database file by path"""
    global CURRENT_DB_PATH
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail=f"Database file not found: {db_path}")
    CURRENT_DB_PATH = db_path
    return {"status": "success", "db_path": db_path}


@app.get("/api/dashboard")
async def get_dashboard_stats(db_path: Optional[str] = None):
    """Get dashboard statistics"""
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        
        # Calculate statistics
        total_scans = len(results)
        pwned_count = 0
        with_creds = 0
        tested_count = 0
        apps_detected = set()
        vulnerabilities_by_day = {}
        app_vulnerability_count = {}
        tech_risk_map = {}
        category_risk_map = {}
        
        for obj in results:
            # Count pwned
            if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                if obj.credential_test_result.get('successful_credentials'):
                    pwned_count += 1
                if obj.credential_test_result.get('tested', False):
                    tested_count += 1
            
            # Count with credentials
            if obj.default_creds:
                with_creds += 1
            
            # Track applications
            app_name = None
            if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                app_name = obj.ai_application_info.get('application_name')
            elif obj.default_creds and ' / ' in str(obj.default_creds):
                app_name = str(obj.default_creds).split(' / ')[0].strip()
            elif obj.page_title and str(obj.page_title) != 'Unknown':
                app_name = str(obj.page_title)
            
            if app_name:
                apps_detected.add(app_name)
                if app_name not in app_vulnerability_count:
                    app_vulnerability_count[app_name] = 0
                if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                    if obj.credential_test_result.get('successful_credentials'):
                        app_vulnerability_count[app_name] += 1
            
            # Track technologies and risks
            if obj.technologies:
                for tech in obj.technologies:
                    if tech not in tech_risk_map:
                        tech_risk_map[tech] = {'total': 0, 'vulnerable': 0}
                    tech_risk_map[tech]['total'] += 1
                    if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                        if obj.credential_test_result.get('successful_credentials'):
                            tech_risk_map[tech]['vulnerable'] += 1
            
            # Track categories and risks
            category = obj.category or "Uncategorized"
            if category not in category_risk_map:
                category_risk_map[category] = {'total': 0, 'vulnerable': 0}
            category_risk_map[category]['total'] += 1
            if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                if obj.credential_test_result.get('successful_credentials'):
                    category_risk_map[category]['vulnerable'] += 1
        
        # Get top 10 most vulnerable apps
        top_vulnerable_apps = sorted(
            app_vulnerability_count.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "stats": {
                "total_scans": total_scans,
                "critical_vulnerabilities": pwned_count,
                "applications_detected": len(apps_detected),
                "credentials_found": with_creds,
                "credentials_tested": tested_count
            },
            "top_vulnerable_apps": [
                {"name": name, "vulnerabilities": count}
                for name, count in top_vulnerable_apps
            ],
            "tech_risk_map": tech_risk_map,
            "category_risk_map": category_risk_map,
            "vulnerabilities_by_day": vulnerabilities_by_day  # Can be enhanced with date tracking
        }
    finally:
        dbm.close()


@app.get("/api/reports")
async def get_reports(
    db_path: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    application: Optional[str] = None,
    risk_level: Optional[str] = None,
    technology: Optional[str] = None,
    category: Optional[str] = None,
    pwned_only: bool = False,
    sort_by: Optional[str] = None,
    sort_order: str = Query("asc", pattern="^(asc|desc)$")
):
    """Get filtered and sorted reports"""
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        
        # Apply filters
        filtered = []
        for obj in results:
            # Application filter
            if application:
                app_name = None
                if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                    app_name = obj.ai_application_info.get('application_name', '')
                elif obj.default_creds and ' / ' in str(obj.default_creds):
                    app_name = str(obj.default_creds).split(' / ')[0].strip()
                if application.lower() not in str(app_name).lower():
                    continue
            
            # Category filter
            if category:
                obj_category = obj.category or "Uncategorized"
                if category.lower() not in obj_category.lower():
                    continue
            
            # Risk level filter (pwned)
            if pwned_only:
                if not (obj.credential_test_result and isinstance(obj.credential_test_result, dict)):
                    continue
                if not obj.credential_test_result.get('successful_credentials'):
                    continue
            
            # Technology filter
            if technology:
                if not obj.technologies or technology not in obj.technologies:
                    continue
            
            filtered.append(obj)
        
        # Convert to JSON-serializable format (before sorting so we can sort by report fields)
        reports_all = []
        for obj in filtered:
            # Get application name with improved logic
            app_name = None
            
            # Priority 1: AI application info
            if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                app_name = obj.ai_application_info.get('application_name')
                # Try manufacturer + model if name not available
                if not app_name:
                    manufacturer = obj.ai_application_info.get('manufacturer')
                    model = obj.ai_application_info.get('model')
                    if manufacturer and model:
                        app_name = f"{manufacturer} {model}"
                    elif manufacturer:
                        app_name = manufacturer
                    elif model:
                        app_name = model
            
            # Priority 2: Extract from default_creds
            if not app_name and obj.default_creds and ' / ' in str(obj.default_creds):
                app_name = str(obj.default_creds).split(' / ')[0].strip()
            
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
            
            # Priority 4: Try to extract from URL hostname (but not for IP addresses)
            if not app_name and obj.remote_system:
                from urllib.parse import urlparse
                parsed = urlparse(obj.remote_system)
                hostname = parsed.hostname or parsed.netloc
                # Only extract from hostname if it's NOT an IP address
                if hostname and not is_ip_address(hostname) and hostname not in ['localhost']:
                    parts = hostname.split('.')
                    if parts and parts[0]:
                        app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
            
            # Priority 5: Check for HTTP Authentication type (NTLM, Basic, etc.)
            http_auth_type = getattr(obj, 'http_auth_type', None)
            if not app_name and http_auth_type:
                # Use the authentication type as the application name
                if 'NTLM' in str(http_auth_type):
                    app_name = "NTLM Authentication"
                elif 'Negotiate' in str(http_auth_type):
                    app_name = "Negotiate Authentication (Kerberos/NTLM)"
                elif 'Basic' in str(http_auth_type):
                    app_name = "HTTP Basic Authentication"
                elif 'Digest' in str(http_auth_type):
                    app_name = "HTTP Digest Authentication"
                elif http_auth_type:
                    app_name = str(http_auth_type)
            
            # Determine display title: prefer app_name over page_title if page_title is generic
            page_title_str = str(obj.page_title) if obj.page_title else None
            if app_name:
                display_title = app_name
            elif page_title_str and page_title_str != 'Unknown':
                display_title = page_title_str
            else:
                # Last resort: use hostname
                if obj.remote_system:
                    from urllib.parse import urlparse
                    parsed = urlparse(obj.remote_system)
                    display_title = parsed.netloc or "Unknown"
                else:
                    display_title = "Unknown"
            
            # Set category for HTTP authentication if not already set
            category = obj.category or "Uncategorized"
            if http_auth_type and category == "Uncategorized":
                if 'NTLM' in str(http_auth_type) or 'Negotiate' in str(http_auth_type):
                    category = "ntlm_auth"
                elif http_auth_type:
                    category = "http_auth"
            
            report = {
                "id": obj.id,
                "url": obj.remote_system,
                "title": display_title,
                "category": category,
                "application": app_name,
                "technologies": obj.technologies or [],
                "has_credentials": bool(obj.default_creds),
                "is_pwned": False,
                "working_credentials": [],
                "screenshot_path": obj.screenshot_path if obj.screenshot_path else None,  # Include path even if file check fails
                "timestamp": datetime.now().isoformat(),  # Can be enhanced with actual timestamp
                "risk_level": "low",
                "http_auth_type": http_auth_type
            }
            
            # Check if pwned
            if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                successful = obj.credential_test_result.get('successful_credentials', [])
                if successful:
                    report["is_pwned"] = True
                    report["risk_level"] = "critical"
                    report["working_credentials"] = [
                        f"{c.get('username', '')}:{c.get('password', '')}"
                        for c in successful
                    ]
                elif obj.credential_test_result.get('tested', False):
                    report["risk_level"] = "medium"
            
            reports_all.append(report)
        
        # Apply sorting
        if sort_by:
            reverse = (sort_order == "desc")
            if sort_by == "url":
                reports_all.sort(key=lambda x: x["url"].lower(), reverse=reverse)
            elif sort_by == "application":
                reports_all.sort(key=lambda x: (x["application"] or "").lower(), reverse=reverse)
            elif sort_by == "category":
                reports_all.sort(key=lambda x: x["category"].lower(), reverse=reverse)
            elif sort_by == "risk_level":
                risk_order = {"critical": 3, "medium": 2, "low": 1}
                reports_all.sort(key=lambda x: risk_order.get(x["risk_level"], 0), reverse=reverse)
            elif sort_by == "is_pwned":
                reports_all.sort(key=lambda x: x["is_pwned"], reverse=reverse)
        
        # Pagination
        total = len(reports_all)
        start = (page - 1) * page_size
        end = start + page_size
        reports = reports_all[start:end]
        
        return {
            "reports": reports,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size
            }
        }
    finally:
        dbm.close()


@app.get("/api/reports/export")
async def export_reports(
    db_path: Optional[str] = None,
    application: Optional[str] = None,
    risk_level: Optional[str] = None,
    technology: Optional[str] = None,
    category: Optional[str] = None,
    pwned_only: bool = False,
    sort_by: Optional[str] = None,
    sort_order: str = Query("asc", pattern="^(asc|desc)$")
):
    """Export all filtered and sorted reports (no pagination)"""
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        
        # Apply filters
        filtered = []
        for obj in results:
            # Application filter
            if application:
                app_name = None
                if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                    app_name = obj.ai_application_info.get('application_name', '')
                elif obj.default_creds and ' / ' in str(obj.default_creds):
                    app_name = str(obj.default_creds).split(' / ')[0].strip()
                if application.lower() not in str(app_name).lower():
                    continue
            
            # Category filter
            if category:
                obj_category = obj.category or "Uncategorized"
                if category.lower() not in obj_category.lower():
                    continue
            
            # Risk level filter (pwned)
            if pwned_only:
                if not (obj.credential_test_result and isinstance(obj.credential_test_result, dict)):
                    continue
                if not obj.credential_test_result.get('successful_credentials'):
                    continue
            
            # Technology filter
            if technology:
                if not obj.technologies or technology not in obj.technologies:
                    continue
            
            filtered.append(obj)
        
        # Convert to JSON-serializable format
        reports_all = []
        for obj in filtered:
            # Get application name with improved logic
            app_name = None
            
            # Priority 1: AI application info
            if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                app_name = obj.ai_application_info.get('application_name')
                # Try manufacturer + model if name not available
                if not app_name:
                    manufacturer = obj.ai_application_info.get('manufacturer')
                    model = obj.ai_application_info.get('model')
                    if manufacturer and model:
                        app_name = f"{manufacturer} {model}"
                    elif manufacturer:
                        app_name = manufacturer
                    elif model:
                        app_name = model
            
            # Priority 2: Extract from default_creds
            if not app_name and obj.default_creds and ' / ' in str(obj.default_creds):
                app_name = str(obj.default_creds).split(' / ')[0].strip()
            
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
            
            # Priority 4: Try to extract from URL hostname (but not for IP addresses)
            if not app_name and obj.remote_system:
                from urllib.parse import urlparse
                parsed = urlparse(obj.remote_system)
                hostname = parsed.hostname or parsed.netloc
                # Only extract from hostname if it's NOT an IP address
                if hostname and not is_ip_address(hostname) and hostname not in ['localhost']:
                    parts = hostname.split('.')
                    if parts and parts[0]:
                        app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
            
            # Priority 5: Check for HTTP Authentication type (NTLM, Basic, etc.)
            http_auth_type = getattr(obj, 'http_auth_type', None)
            if not app_name and http_auth_type:
                # Use the authentication type as the application name
                if 'NTLM' in str(http_auth_type):
                    app_name = "NTLM Authentication"
                elif 'Negotiate' in str(http_auth_type):
                    app_name = "Negotiate Authentication (Kerberos/NTLM)"
                elif 'Basic' in str(http_auth_type):
                    app_name = "HTTP Basic Authentication"
                elif 'Digest' in str(http_auth_type):
                    app_name = "HTTP Digest Authentication"
                elif http_auth_type:
                    app_name = str(http_auth_type)
            
            # Determine display title: prefer app_name over page_title if page_title is generic
            page_title_str = str(obj.page_title) if obj.page_title else None
            if app_name:
                display_title = app_name
            elif page_title_str and page_title_str != 'Unknown':
                display_title = page_title_str
            else:
                # Last resort: use hostname
                if obj.remote_system:
                    from urllib.parse import urlparse
                    parsed = urlparse(obj.remote_system)
                    display_title = parsed.netloc or "Unknown"
                else:
                    display_title = "Unknown"
            
            # Set category for HTTP authentication if not already set
            category = obj.category or "Uncategorized"
            if http_auth_type and category == "Uncategorized":
                if 'NTLM' in str(http_auth_type) or 'Negotiate' in str(http_auth_type):
                    category = "ntlm_auth"
                elif http_auth_type:
                    category = "http_auth"
            
            report = {
                "id": obj.id,
                "url": obj.remote_system,
                "title": display_title,
                "category": category,
                "application": app_name,
                "technologies": obj.technologies or [],
                "has_credentials": bool(obj.default_creds),
                "is_pwned": False,
                "working_credentials": [],
                "screenshot_path": obj.screenshot_path if obj.screenshot_path else None,
                "timestamp": datetime.now().isoformat(),
                "risk_level": "low",
                "http_auth_type": http_auth_type
            }
            
            # Check if pwned
            if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                successful = obj.credential_test_result.get('successful_credentials', [])
                if successful:
                    report["is_pwned"] = True
                    report["risk_level"] = "critical"
                    report["working_credentials"] = [
                        f"{c.get('username', '')}:{c.get('password', '')}"
                        for c in successful
                    ]
                elif obj.credential_test_result.get('tested', False):
                    report["risk_level"] = "medium"
            
            reports_all.append(report)
        
        # Apply sorting
        if sort_by:
            reverse = (sort_order == "desc")
            if sort_by == "url":
                reports_all.sort(key=lambda x: x["url"].lower(), reverse=reverse)
            elif sort_by == "application":
                reports_all.sort(key=lambda x: (x["application"] or "").lower(), reverse=reverse)
            elif sort_by == "category":
                reports_all.sort(key=lambda x: x["category"].lower(), reverse=reverse)
            elif sort_by == "risk_level":
                risk_order = {"critical": 3, "medium": 2, "low": 1}
                reports_all.sort(key=lambda x: risk_order.get(x["risk_level"], 0), reverse=reverse)
            elif sort_by == "is_pwned":
                reports_all.sort(key=lambda x: x["is_pwned"], reverse=reverse)
        
        return {
            "reports": reports_all,
            "total": len(reports_all)
        }
    finally:
        dbm.close()


@app.get("/api/passwords")
async def get_password_analysis(db_path: Optional[str] = None):
    """Get password analysis data"""
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        
        vulnerable_creds = []
        app_stats = {}
        
        for obj in results:
            if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                successful = obj.credential_test_result.get('successful_credentials', [])
                if successful:
                    app_name = None
                    if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                        app_name = obj.ai_application_info.get('application_name')
                    elif obj.default_creds and ' / ' in str(obj.default_creds):
                        app_name = str(obj.default_creds).split(' / ')[0].strip()
                    
                    for cred in successful:
                        vulnerable_creds.append({
                            "url": obj.remote_system,
                            "application": app_name or "Unknown",
                            "username": cred.get('username', ''),
                            "password": cred.get('password', ''),
                            "category": obj.category or "Uncategorized"
                        })
                    
                    # Update app stats
                    if app_name:
                        if app_name not in app_stats:
                            app_stats[app_name] = {"total": 0, "successful": 0}
                        app_stats[app_name]["total"] += 1
                        app_stats[app_name]["successful"] += 1
        
        # Calculate success rates
        app_stats_list = []
        for app, stats in app_stats.items():
            success_rate = (stats["successful"] / stats["total"]) * 100 if stats["total"] > 0 else 0
            app_stats_list.append({
                "application": app,
                "total_tested": stats["total"],
                "successful": stats["successful"],
                "success_rate": round(success_rate, 2)
            })
        
        app_stats_list.sort(key=lambda x: x["success_rate"], reverse=True)
        
        return {
            "vulnerable_credentials": vulnerable_creds,
            "application_statistics": app_stats_list,
            "total_vulnerable": len(vulnerable_creds),
            "recommendations": generate_security_recommendations(vulnerable_creds, app_stats_list)
        }
    finally:
        dbm.close()


@app.get("/api/ai-analysis")
async def get_ai_analysis(db_path: Optional[str] = None):
    """Get AI analysis data"""
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        
        detected_apps = {}
        tech_timeline = []
        confidence_metrics = {"high": 0, "medium": 0, "low": 0}
        
        for obj in results:
            # Track AI-detected applications
            if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
                app_name = obj.ai_application_info.get('application_name')
                confidence = obj.ai_application_info.get('confidence', 'medium')
                
                if app_name:
                    if app_name not in detected_apps:
                        detected_apps[app_name] = {
                            "name": app_name,
                            "count": 0,
                            "confidence": confidence,
                            "technologies": set(),
                            "vulnerable": False
                        }
                    
                    detected_apps[app_name]["count"] += 1
                    if obj.technologies:
                        detected_apps[app_name]["technologies"].update(obj.technologies)
                    
                    if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
                        if obj.credential_test_result.get('successful_credentials'):
                            detected_apps[app_name]["vulnerable"] = True
                    
                    # Track confidence
                    if confidence == "high":
                        confidence_metrics["high"] += 1
                    elif confidence == "medium":
                        confidence_metrics["medium"] += 1
                    else:
                        confidence_metrics["low"] += 1
            
            # Track technologies timeline
            if obj.technologies:
                for tech in obj.technologies:
                    tech_timeline.append({
                        "technology": tech,
                        "timestamp": datetime.now().isoformat(),
                        "url": obj.remote_system
                    })
        
        # Convert sets to lists for JSON serialization
        for app in detected_apps.values():
            app["technologies"] = list(app["technologies"])
        
        return {
            "detected_applications": list(detected_apps.values()),
            "technology_timeline": tech_timeline[-100:],  # Last 100 entries
            "confidence_metrics": confidence_metrics,
            "total_detections": len(detected_apps)
        }
    finally:
        dbm.close()


@app.get("/api/screenshot/{scan_id}/{url_hash:path}")
async def get_screenshot(scan_id: str, url_hash: str, db_path: Optional[str] = None):
    """Get screenshot file"""
    from urllib.parse import unquote
    import logging
    import sys
    
    # Configure logging
    logger = logging.getLogger(__name__)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    url_hash = unquote(url_hash)  # Decode URL-encoded hash
    logger.info(f"=== Screenshot request: ID={scan_id}, URL={url_hash} ===")
    
    dbm = get_db_manager(db_path)
    try:
        results = dbm.get_complete_http()
        db_dir = getattr(dbm, '_db_dir', None)
        if db_dir is None:
            # Get directory from database path (ensure absolute)
            db_path_abs = getattr(dbm, '_db_path_abs', None)
            if db_path_abs:
                db_dir = os.path.dirname(db_path_abs)
            else:
                db_dir = os.path.dirname(os.path.abspath(dbm._dbpath))
        
        # Ensure db_dir is absolute
        db_dir = os.path.abspath(os.path.normpath(db_dir))
        screens_dir = os.path.join(db_dir, 'screens')
        
        logger.info(f"Looking for screenshot: ID={scan_id}, URL={url_hash}")
        logger.info(f"  db_dir: {db_dir}")
        logger.info(f"  screens_dir: {screens_dir}")
        logger.info(f"  screens_dir exists: {os.path.exists(screens_dir)}")
        if os.path.exists(screens_dir):
            logger.info(f"  Files in screens: {os.listdir(screens_dir)}")
        
        def find_screenshot_path(obj):
            """Helper to find screenshot path for an object"""
            # PRIMARY METHOD: Reconstruct from remote_system (same logic as EyeWitness)
            # This is the most reliable since we know the files exist with this naming
            if obj.remote_system:
                import re
                # Use the same sanitize_filename logic as EyeWitness
                filename = re.sub(r'^https?://', '', obj.remote_system)
                # Replace all non-alphanumeric characters (except hyphens and dots) with underscores
                filename = re.sub(r'[^a-zA-Z0-9\-\.]', '_', filename)
                # Limit length
                filename = filename[:200]
                reconstructed = os.path.join(screens_dir, f'{filename}.png')
                reconstructed = os.path.abspath(os.path.normpath(reconstructed))
                if os.path.exists(reconstructed):
                    logger.info(f"✓ Found reconstructed from URL: {reconstructed}")
                    return reconstructed
                else:
                    logger.warning(f"✗ Reconstructed path does not exist: {reconstructed}")
            
            # FALLBACK: Try stored screenshot_path
            if obj.screenshot_path:
                # Check if absolute path exists
                if os.path.isabs(obj.screenshot_path) and os.path.exists(obj.screenshot_path):
                    logger.info(f"✓ Found absolute path: {obj.screenshot_path}")
                    return obj.screenshot_path
                # Check if relative path exists (from current working directory)
                if os.path.exists(obj.screenshot_path):
                    logger.info(f"✓ Found relative path: {obj.screenshot_path}")
                    return obj.screenshot_path
                # Try relative to database directory
                rel_path = os.path.join(screens_dir, os.path.basename(obj.screenshot_path))
                rel_path = os.path.abspath(os.path.normpath(rel_path))
                if os.path.exists(rel_path):
                    logger.info(f"✓ Found in db_dir/screens: {rel_path}")
                    return rel_path
                # Try with full relative path from screenshot_path
                if 'screens' in obj.screenshot_path:
                    # Extract the filename
                    filename = os.path.basename(obj.screenshot_path)
                    full_path = os.path.join(screens_dir, filename)
                    full_path = os.path.abspath(os.path.normpath(full_path))
                    if os.path.exists(full_path):
                        logger.info(f"✓ Found reconstructed path: {full_path}")
                        return full_path
            
            return None
        
        # Find the object by ID first (most reliable)
        obj_found = None
        for obj in results:
            if str(obj.id) == scan_id:
                obj_found = obj
                break
        
        if obj_found:
            logger.info(f"✓ Found object with ID {scan_id}")
            logger.info(f"  URL: {obj_found.remote_system}")
            logger.info(f"  Stored screenshot_path: {obj_found.screenshot_path}")
            screenshot_path = find_screenshot_path(obj_found)
            if screenshot_path and os.path.exists(screenshot_path):
                logger.info(f"✓✓✓ SUCCESS: Returning screenshot: {screenshot_path}")
                return FileResponse(screenshot_path, media_type="image/png")
            else:
                logger.error(f"✗✗✗ FAILED: Screenshot path not found for ID {scan_id}")
                logger.error(f"  Object screenshot_path: {obj_found.screenshot_path}")
                logger.error(f"  db_dir: {db_dir}")
                logger.error(f"  screens_dir: {screens_dir}")
                logger.error(f"  screens_dir exists: {os.path.exists(screens_dir)}")
                if os.path.exists(screens_dir):
                    logger.error(f"  Files in screens_dir: {os.listdir(screens_dir)}")
        else:
            logger.error(f"✗✗✗ Object with ID {scan_id} not found in database")
            logger.error(f"  Total objects: {len(results)}")
            # List all IDs for debugging
            ids = [str(obj.id) for obj in results]
            logger.error(f"  Available IDs: {ids}")
            if results:
                logger.error(f"  First object: ID={results[0].id}, URL={results[0].remote_system}")
        
        # Fallback: try to match by URL
        for obj in results:
            if obj.remote_system:
                obj_url = obj.remote_system
                decoded_hash = url_hash.replace('%3A', ':').replace('%2F', '/')
                if decoded_hash in obj_url or url_hash in obj_url:
                    logger.info(f"Matched by URL: {obj_url}")
                    screenshot_path = find_screenshot_path(obj)
                    if screenshot_path and os.path.exists(screenshot_path):
                        logger.info(f"✓ Returning screenshot (matched by URL): {screenshot_path}")
                        return FileResponse(screenshot_path, media_type="image/png")
        
        logger.error(f"✗ Screenshot not found for ID {scan_id}, URL {url_hash}, db_dir: {db_dir}")
        raise HTTPException(status_code=404, detail=f"Screenshot not found for ID {scan_id}")
    finally:
        dbm.close()


def generate_security_recommendations(vulnerable_creds: List[Dict], app_stats: List[Dict]) -> List[str]:
    """Generate security recommendations based on analysis"""
    recommendations = []
    
    if len(vulnerable_creds) > 0:
        recommendations.append(
            f"🚨 CRITICAL: {len(vulnerable_creds)} systems found with default credentials. "
            "Immediately change all default passwords."
        )
    
    # Find apps with high success rate
    high_risk_apps = [app for app in app_stats if app["success_rate"] > 50]
    if high_risk_apps:
        recommendations.append(
            f"⚠️ WARNING: {len(high_risk_apps)} applications show high default credential success rates. "
            "Review and update authentication policies."
        )
    
    # General recommendations
    if len(vulnerable_creds) > 10:
        recommendations.append(
            "📋 RECOMMENDATION: Implement automated password rotation policies "
            "and enforce strong password requirements."
        )
    
    return recommendations


@app.on_event("startup")
async def startup_event():
    """Load project automatically on startup if EYEWITNESS_PROJECT is set"""
    global CURRENT_DB_PATH
    project_name = os.environ.get('EYEWITNESS_PROJECT')
    if project_name:
        db_path = find_latest_database(project_name=project_name)
        if db_path:
            CURRENT_DB_PATH = db_path
            print(f"[*] Auto-loaded project from EYEWITNESS_PROJECT: {project_name}")
            print(f"[*] Database path: {db_path}")
        else:
            print(f"[!] Warning: Project '{project_name}' not found in eyewitness_projects/")
    else:
        # Try to load the most recent database
        db_path = find_latest_database()
        if db_path:
            CURRENT_DB_PATH = db_path
            print(f"[*] Auto-loaded most recent database: {db_path}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

