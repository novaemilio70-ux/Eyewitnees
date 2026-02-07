#!/usr/bin/env python3
"""
Technology detection module for EyeWitness
Detects web technologies based on HTML content, headers, and URLs
"""

import re
from typing import List, Dict, Optional


def detect_technologies(http_object) -> List[str]:
    """
    Detect technologies used by a website
    
    Args:
        http_object: HTTPTableObject with source_code, http_headers, remote_system
        
    Returns:
        List of detected technology names
    """
    technologies = []
    
    if not http_object:
        return technologies
    
    # Get data sources
    # Handle source_code which might be bytes or string
    source_code = http_object.source_code or ''
    if isinstance(source_code, bytes):
        html = source_code.decode('utf-8', errors='ignore').lower()
    else:
        html = str(source_code).lower()
    
    headers = http_object.http_headers or {}
    url = str(http_object.remote_system or '').lower()
    
    # Detect by HTTP Headers
    server_header = headers.get('Server', '').lower()
    if 'nginx' in server_header:
        technologies.append('Nginx')
    elif 'apache' in server_header:
        technologies.append('Apache')
    elif 'iis' in server_header or 'microsoft-iis' in server_header:
        technologies.append('IIS')
    elif 'cloudflare' in server_header:
        technologies.append('Cloudflare')
    
    # Detect by X-Powered-By header
    powered_by = headers.get('X-Powered-By', '').lower()
    if 'php' in powered_by:
        technologies.append('PHP')
    if 'asp.net' in powered_by or 'aspnet' in powered_by:
        technologies.append('ASP.NET')
    
    # Detect by HTML content
    # JavaScript Frameworks
    if 'react' in html or 'react-dom' in html or 'reactjs' in html:
        technologies.append('React')
    if 'angular' in html or 'ng-app' in html or 'angularjs' in html:
        technologies.append('Angular')
    if 'vue.js' in html or 'vuejs' in html or 'vue.min.js' in html:
        technologies.append('Vue.js')
    if 'jquery' in html or 'jquery.min.js' in html:
        technologies.append('jQuery')
    
    # CMS Detection
    if 'wp-content' in html or 'wp-includes' in html or 'wordpress' in html:
        technologies.append('WordPress')
    if 'joomla' in html or 'joomla!' in html:
        technologies.append('Joomla')
    if 'drupal' in html or 'drupal.js' in html:
        technologies.append('Drupal')
    
    # Cloud Services
    if 'aws' in html or 'amazonaws.com' in url or 's3.amazonaws.com' in url:
        technologies.append('AWS')
    if 'googleapis.com' in url or 'gstatic.com' in url:
        technologies.append('Google')
    if 'azure' in html or '.azure.com' in url or 'azurewebsites.net' in url:
        technologies.append('Azure')
    if 'cloudflare' in html or 'cloudflare.com' in url:
        technologies.append('Cloudflare')
    
    # Web Servers (additional checks)
    if 'nginx' in html:
        if 'Nginx' not in technologies:
            technologies.append('Nginx')
    if 'apache' in html:
        if 'Apache' not in technologies:
            technologies.append('Apache')
    
    # Database indicators
    if 'mysql' in html or 'mysqld' in html:
        technologies.append('MySQL')
    if 'postgresql' in html or 'postgres' in html:
        technologies.append('PostgreSQL')
    if 'mongodb' in html:
        technologies.append('MongoDB')
    
    # Other technologies
    if 'bootstrap' in html or 'bootstrap.min.css' in html:
        technologies.append('Bootstrap')
    if 'docker' in html or 'docker.io' in url:
        technologies.append('Docker')
    if 'github' in url and 'github.io' in url:
        technologies.append('GitHub Pages')
    if 'youtube' in html or 'youtube.com' in url:
        technologies.append('YouTube')
    if 'linkedin' in html or 'linkedin.com' in url:
        technologies.append('LinkedIn')
    
    # Security headers
    if headers.get('Strict-Transport-Security'):
        technologies.append('HSTS')
    if headers.get('Content-Security-Policy'):
        technologies.append('CSP')
    
    # Remove duplicates while preserving order
    seen = set()
    unique_technologies = []
    for tech in technologies:
        if tech not in seen:
            seen.add(tech)
            unique_technologies.append(tech)
    
    return unique_technologies

