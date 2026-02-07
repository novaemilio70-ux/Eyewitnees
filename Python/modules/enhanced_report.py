#!/usr/bin/env python3
"""
Modern report generator for EyeWitness
Creates gallery and detail views with enhanced visualization
"""

import os
import html as html_module
from pathlib import Path
from typing import List
from datetime import datetime


def generate_gallery_html(data: List, output_dir: str, cli_parsed) -> str:
    """
    Generate gallery view HTML with thumbnails and filters
    
    Args:
        data: List of HTTPTableObject
        output_dir: Output directory path
        cli_parsed: CLI options
        
    Returns:
        HTML string for gallery view
    """
    # Get unique technologies and status codes
    all_technologies = set()
    status_codes = set()
    pwned_count = 0
    total_count = len(data)
    
    for obj in data:
        if obj.technologies:
            all_technologies.update(obj.technologies)
        
        # Determine status code from headers or error state
        if obj.error_state:
            if 'Timeout' in obj.error_state:
                status_codes.add('Timeout')
            elif '404' in obj.error_state or 'Not Found' in obj.error_state:
                status_codes.add('404')
            elif '403' in obj.error_state or 'Unauthorized' in obj.error_state:
                status_codes.add('403')
            elif '401' in obj.error_state:
                status_codes.add('401')
            else:
                status_codes.add('Error')
        elif obj.http_headers:
            status = obj.http_headers.get('Status', '')
            if status:
                status_code = status.split()[0] if ' ' in status else status
                status_codes.add(status_code)
            else:
                status_codes.add('200')  # Assume 200 if no error
        else:
            status_codes.add('200')
        
        # Count pwned
        if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
            if obj.credential_test_result.get('successful_credentials'):
                pwned_count += 1
    
    # Generate gallery HTML
    html = f"""
    <div class="gallery-container">
        <div class="gallery-header">
            <h2>📸 Screenshot Gallery</h2>
            <div class="gallery-stats">
                <span>Total: {total_count}</span>
                <span class="pwned-badge">Pwned: {pwned_count}</span>
            </div>
        </div>
        
        <div class="gallery-filters">
            <div class="filter-group">
                <label>Status:</label>
                <select id="filterStatus" onchange="filterGallery()">
                    <option value="all">All</option>
                    {' '.join([f'<option value="{code}">{code}</option>' for code in sorted(status_codes)])}
                </select>
            </div>
            
            <div class="filter-group">
                <label>Technology:</label>
                <select id="filterTech" onchange="filterGallery()">
                    <option value="all">All</option>
                    {' '.join([f'<option value="{tech}">{tech}</option>' for tech in sorted(all_technologies)])}
                </select>
            </div>
            
            <div class="filter-group">
                <label>Search:</label>
                <input type="text" id="searchGallery" placeholder="Search URLs, titles..." 
                       onkeyup="filterGallery()" style="width: 300px;">
            </div>
            
            <div class="filter-group">
                <label>
                    <input type="checkbox" id="showPwnedOnly" onchange="filterGallery()">
                    Show only Pwned
                </label>
            </div>
        </div>
        
        <div class="gallery-grid" id="galleryGrid">
    """
    
    # Generate gallery items
    for idx, obj in enumerate(data):
        # Get status
        status = '200'
        status_class = 'status-200'
        if obj.error_state:
            if '404' in obj.error_state or 'Not Found' in obj.error_state:
                status = '404'
                status_class = 'status-404'
            elif '403' in obj.error_state or 'Unauthorized' in obj.error_state:
                status = '403'
                status_class = 'status-403'
            elif '401' in obj.error_state:
                status = '401'
                status_class = 'status-401'
            elif 'Timeout' in obj.error_state:
                status = 'Timeout'
                status_class = 'status-timeout'
            else:
                status = 'Error'
                status_class = 'status-error'
        elif obj.http_headers:
            header_status = obj.http_headers.get('Status', '')
            if header_status:
                status = header_status.split()[0] if ' ' in header_status else header_status
                status_class = f'status-{status}'
        
        # Check if pwned
        is_pwned = False
        if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
            if obj.credential_test_result.get('successful_credentials'):
                is_pwned = True
        
        # Get screenshot path
        screenshot_path = ''
        if obj.screenshot_path and os.path.isfile(obj.screenshot_path):
            screenshot_path = os.path.relpath(obj.screenshot_path, output_dir)
        
        # Get title
        title = obj.page_title or 'Unknown'
        if len(title) > 50:
            title = title[:47] + '...'
        
        # Get URL
        url = obj.remote_system
        if len(url) > 60:
            url_display = url[:57] + '...'
        else:
            url_display = url
        
        # Get technologies
        tech_badges = ''
        if obj.technologies:
            for tech in obj.technologies[:5]:  # Show max 5
                tech_badges += f'<span class="tech-badge">{html_module.escape(tech)}</span>'
        
        # Get timestamp (use current time as fallback)
        timestamp = "Just now"
        
        html += f"""
            <div class="gallery-item" data-status="{status}" data-techs="{' '.join(obj.technologies or [])}" 
                 data-pwned="{'true' if is_pwned else 'false'}" data-url="{html_module.escape(url.lower())}" 
                 data-title="{html_module.escape(title.lower())}" onclick="openDetail({idx})">
                <div class="gallery-item-header">
                    <span class="status-badge {status_class}">{status}</span>
                    {'<span class="pwned-badge-small">🔓 PWNED</span>' if is_pwned else ''}
                </div>
                <div class="gallery-item-screenshot">
                    {f'<img src="{html_module.escape(screenshot_path)}" alt="Screenshot" onerror="this.src=\'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgZmlsbD0iI2RkZCIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj5ObyBTY3JlZW5zaG90PC90ZXh0Pjwvc3ZnPg==\'">' if screenshot_path else '<div class="no-screenshot">No Screenshot</div>'}
                </div>
                <div class="gallery-item-info">
                    <div class="gallery-item-title" title="{html_module.escape(title)}">{html_module.escape(title)}</div>
                    <div class="gallery-item-url" title="{html_module.escape(url)}">{html_module.escape(url_display)}</div>
                    <div class="gallery-item-techs">{tech_badges}</div>
                    <div class="gallery-item-time">{timestamp}</div>
                </div>
            </div>
        """
    
    html += """
        </div>
        <div class="gallery-footer">
            Showing <span id="visibleCount">0</span> of <span id="totalCount">0</span> items
        </div>
    </div>
    
    <script>
    function filterGallery() {
        const status = document.getElementById('filterStatus').value;
        const tech = document.getElementById('filterTech').value;
        const search = document.getElementById('searchGallery').value.toLowerCase();
        const pwnedOnly = document.getElementById('showPwnedOnly').checked;
        
        const items = document.querySelectorAll('.gallery-item');
        let visible = 0;
        
        items.forEach(item => {
            const itemStatus = item.getAttribute('data-status');
            const itemTechs = item.getAttribute('data-techs') || '';
            const itemPwned = item.getAttribute('data-pwned') === 'true';
            const itemText = (item.getAttribute('data-url') + ' ' + item.getAttribute('data-title')).toLowerCase();
            
            const matchStatus = status === 'all' || itemStatus === status;
            const matchTech = tech === 'all' || itemTechs.includes(tech);
            const matchSearch = !search || itemText.includes(search);
            const matchPwned = !pwnedOnly || itemPwned;
            
            if (matchStatus && matchTech && matchSearch && matchPwned) {
                item.style.display = 'block';
                visible++;
            } else {
                item.style.display = 'none';
            }
        });
        
        document.getElementById('visibleCount').textContent = visible;
        document.getElementById('totalCount').textContent = items.length;
    }
    
    function openDetail(index) {
        window.location.href = `detail_${index}.html`;
    }
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        filterGallery();
    });
    </script>
    """
    
    return html


def generate_detail_html(obj, index: int, total: int, output_dir: str, cli_parsed) -> str:
    """
    Generate detail view HTML for a single screenshot
    
    Args:
        obj: HTTPTableObject
        index: Current index
        total: Total number of items
        output_dir: Output directory path
        cli_parsed: CLI options
        
    Returns:
        HTML string for detail view
    """
    # Get screenshot path
    screenshot_path = ''
    if obj.screenshot_path and os.path.isfile(obj.screenshot_path):
        screenshot_path = os.path.relpath(obj.screenshot_path, output_dir)
    
    # Get status
    status = '200'
    status_class = 'status-200'
    if obj.error_state:
        if '404' in obj.error_state:
            status = '404'
            status_class = 'status-404'
        elif '403' in obj.error_state:
            status = '403'
            status_class = 'status-403'
        elif '401' in obj.error_state:
            status = '401'
            status_class = 'status-401'
        elif 'Timeout' in obj.error_state:
            status = 'Timeout'
            status_class = 'status-timeout'
        else:
            status = 'Error'
            status_class = 'status-error'
    elif obj.http_headers:
        header_status = obj.http_headers.get('Status', '')
        if header_status:
            status = header_status.split()[0] if ' ' in header_status else header_status
            status_class = f'status-{status}'
    
    # Check if pwned
    is_pwned = False
    working_creds = []
    if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
        successful = obj.credential_test_result.get('successful_credentials', [])
        if successful:
            is_pwned = True
            working_creds = successful
    
    # Get application name
    app_name = 'Unknown'
    if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
        app_name = obj.ai_application_info.get('application_name', 'Unknown')
    elif obj.default_creds and ' / ' in str(obj.default_creds):
        app_name = str(obj.default_creds).split(' / ')[0].strip()
    elif obj.page_title and str(obj.page_title) != 'Unknown':
        app_name = str(obj.page_title)
    
    # Calculate metrics
    network_count = len(obj.network_logs) if obj.network_logs else 0
    console_count = len(obj.console_logs) if obj.console_logs else 0
    header_count = len(obj.http_headers) if obj.http_headers else 0
    tech_count = len(obj.technologies) if obj.technologies else 0
    cookie_count = len(obj.cookies) if obj.cookies else 0
    
    response_size = obj.response_size or 0
    size_kb = round(response_size / 1024, 2) if response_size else 0
    load_time = obj.load_time or 0
    
    # Generate HTML
    html = f"""
    <div class="detail-container">
        <div class="detail-header">
            <div class="detail-nav">
                {'<a href="detail_' + str(index-1) + '.html" class="nav-btn">← Previous</a>' if index > 0 else '<span class="nav-btn disabled">← Previous</span>'}
                <span class="detail-counter">{index + 1} / {total}</span>
                {'<a href="detail_' + str(index+1) + '.html" class="nav-btn">Next →</a>' if index < total - 1 else '<span class="nav-btn disabled">Next →</span>'}
            </div>
        </div>
        
        <div class="detail-content">
            <div class="detail-left">
                <div class="detail-screenshot">
                    {f'<img src="{html_module.escape(screenshot_path)}" alt="Screenshot" onclick="openLightbox(\'{html_module.escape(screenshot_path)}\')">' if screenshot_path else '<div class="no-screenshot-large">No Screenshot Available</div>'}
                </div>
                
                <div class="detail-basic-info">
                    <h3>{html_module.escape(app_name)}</h3>
                    <div class="detail-url">
                        <a href="{html_module.escape(obj.remote_system)}" target="_blank">{html_module.escape(obj.remote_system)}</a>
                        <button onclick="window.open('{html_module.escape(obj.remote_system)}', '_blank')" class="btn-open">Open URL</button>
                    </div>
                    
                    {f'<div class="detail-pwned"><span class="pwned-badge">🔓 PWNED!</span> Working credentials: {", ".join([html_module.escape(str(c.get("username", ""))) + ":" + html_module.escape(str(c.get("password", ""))) for c in working_creds])}</div>' if is_pwned else ''}
                </div>
                
                {generate_technologies_html(obj.technologies) if obj.technologies else ''}
                
                {generate_ssl_html(obj.ssl_info) if obj.ssl_info else ''}
            </div>
            
            <div class="detail-right">
                <div class="detail-summary">
                    <div class="summary-badge {status_class}">HTTP {status}</div>
                    <p>The final URL was <code>{html_module.escape(obj.remote_system)}</code> responding with an HTTP {status} and {size_kb} KB of content. Probing took roughly {load_time} seconds.</p>
                    
                    <div class="summary-metrics">
                        <div class="metric-box">
                            <div class="metric-number">{network_count}</div>
                            <div class="metric-label">Requests</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-number">{console_count}</div>
                            <div class="metric-label">Console Logs</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-number">{header_count}</div>
                            <div class="metric-label">Headers</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-number">{tech_count}</div>
                            <div class="metric-label">Technologies</div>
                        </div>
                        <div class="metric-box">
                            <div class="metric-number">{cookie_count}</div>
                            <div class="metric-label">Cookies</div>
                        </div>
                    </div>
                    
                    <div class="detail-time">Probed {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
                </div>
                
                <div class="detail-tabs">
                    <div class="tab-buttons">
                        <button class="tab-btn active" onclick="showTab('network')">Network Log</button>
                        <button class="tab-btn" onclick="showTab('console')">Console Log</button>
                        <button class="tab-btn" onclick="showTab('headers')">Response Headers</button>
                        <button class="tab-btn" onclick="showTab('cookies')">Cookies</button>
                    </div>
                    
                    <div id="tab-network" class="tab-content active">
                        {generate_network_log_html(obj.network_logs) if obj.network_logs else '<p>No network logs available</p>'}
                    </div>
                    
                    <div id="tab-console" class="tab-content">
                        {generate_console_log_html(obj.console_logs) if obj.console_logs else '<p>No console logs available</p>'}
                    </div>
                    
                    <div id="tab-headers" class="tab-content">
                        {generate_headers_html(obj.http_headers) if obj.http_headers else '<p>No headers available</p>'}
                    </div>
                    
                    <div id="tab-cookies" class="tab-content">
                        {generate_cookies_html(obj.cookies) if obj.cookies else '<p>No cookies available</p>'}
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    function showTab(tabName) {{
        document.querySelectorAll('.tab-content').forEach(function(tab) {{ tab.classList.remove('active'); }});
        document.querySelectorAll('.tab-btn').forEach(function(btn) {{ btn.classList.remove('active'); }});
        document.getElementById('tab-' + tabName).classList.add('active');
        event.target.classList.add('active');
    }}
    
    function openLightbox(imgSrc) {{
        var lightbox = document.getElementById('lightbox');
        var lightboxImg = document.getElementById('lightbox-img');
        if (lightbox && lightboxImg) {{
            lightboxImg.src = imgSrc;
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
    }}
    </script>
    """
    
    return html


def generate_network_log_html(network_logs):
    """Generate HTML for network log table"""
    html = '<table class="log-table"><thead><tr><th>Status</th><th>URL</th><th>Type</th></tr></thead><tbody>'
    for log in network_logs[:100]:  # Limit to 100 entries
        status = log.get('status', 0)
        url = log.get('url', '')[:100]  # Truncate long URLs
        mime_type = log.get('mimeType', '')
        html += f'<tr><td class="status-{status}">{status}</td><td>{html_module.escape(url)}</td><td>{html_module.escape(mime_type)}</td></tr>'
    html += '</tbody></table>'
    return html


def generate_console_log_html(console_logs):
    """Generate HTML for console log table"""
    html = '<table class="log-table"><thead><tr><th>Level</th><th>Message</th></tr></thead><tbody>'
    for log in console_logs[:100]:  # Limit to 100 entries
        level = log.get('level', '')
        message = log.get('message', '')[:200]  # Truncate long messages
        html += f'<tr><td class="log-{level.lower()}">{level}</td><td>{html_module.escape(message)}</td></tr>'
    html += '</tbody></table>'
    return html


def generate_headers_html(headers):
    """Generate HTML for headers table"""
    html = '<table class="log-table"><thead><tr><th>Header</th><th>Value</th></tr></thead><tbody>'
    for key, value in headers.items():
        value_display = str(value)[:200]  # Truncate long values
        html += f'<tr><td><strong>{html_module.escape(key)}</strong></td><td>{html_module.escape(value_display)}</td></tr>'
    html += '</tbody></table>'
    return html


def generate_cookies_html(cookies):
    """Generate HTML for cookies table"""
    html = '<table class="log-table"><thead><tr><th>Name</th><th>Value</th><th>Domain</th><th>Secure</th></tr></thead><tbody>'
    for cookie in cookies:
        name = cookie.get('name', '')
        value = cookie.get('value', '')[:50]  # Truncate long values
        domain = cookie.get('domain', '')
        secure = 'Yes' if cookie.get('secure') else 'No'
        html += f'<tr><td>{html_module.escape(name)}</td><td>{html_module.escape(value)}</td><td>{html_module.escape(domain)}</td><td>{secure}</td></tr>'
    html += '</tbody></table>'
    return html


def generate_technologies_html(technologies):
    """Helper to generate technologies HTML"""
    tech_badges = ' '.join([f'<span class="tech-badge">{html_module.escape(t)}</span>' for t in technologies])
    return f'<div class="detail-technologies"><h4>Technologies</h4><div class="tech-list">{tech_badges}</div></div>'


def generate_ssl_html(ssl_info):
    """Helper to generate SSL info HTML"""
    subject = html_module.escape(str(ssl_info.get("subject", "Unknown")))
    issuer = html_module.escape(str(ssl_info.get("issuer", "Unknown")))
    protocol = html_module.escape(str(ssl_info.get("protocol", "Unknown")))
    cipher = html_module.escape(str(ssl_info.get("cipher", "Unknown")))
    return f'''<div class="detail-ssl"><h4>TLS Information</h4><table class="info-table">
        <tr><td>Subject:</td><td>{subject}</td></tr>
        <tr><td>Issuer:</td><td>{issuer}</td></tr>
        <tr><td>Protocol:</td><td>{protocol}</td></tr>
        <tr><td>Cipher:</td><td>{cipher}</td></tr>
    </table></div>'''

