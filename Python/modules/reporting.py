import os
import sys
import urllib.parse
import html as html_module

try:
    from rapidfuzz import fuzz
except ImportError:
    print('[*] rapidfuzz not found.')
    print('[*] Run pip list to verify installation!')
    print('[*] Try: sudo apt install python3-rapidfuzz')
    sys.exit()


def process_group(
        data, group, toc, toc_table, page_num, section,
        sectionid, html):
    """Retreives a group from the full data, and creates toc stuff

    Args:
        data (List): Full set of data containing all hosts
        group (String): String representing group to process
        toc (String): HTML for Table of Contents
        toc_table (String): HTML for Table in ToC
        page_num (int): Page number we're on in the report
        section (String): Display name of the group
        sectionid (String): Unique ID for ToC navigation
        html (String): HTML for current page of report

    Returns:
        List: Elements for category sorted and grouped
        String: HTML representing ToC
        String: HTML representing ToC Table
        String: HTML representing current report page
    """
    group_data = sorted([x for x in data if x.category == group], key=lambda k: str(k.page_title))

    grouped_elements = []
    if len(group_data) == 0:
        return grouped_elements, toc, toc_table, html
    
    # Create a visual card for TOC instead of simple list
    count = len(group_data)
    if page_num == 0:
        page_link = f"report.html#{sectionid}"
        page_text = "Page 1"
    else:
        page_link = f"report_page{str(page_num+1)}.html#{sectionid}"
        page_text = f"Page {str(page_num+1)}"
    
    # Color coding based on category
    category_colors = {
        'highval': '#e74c3c',
        'virtualization': '#3498db',
        'idrac': '#9b59b6',
        'nas': '#16a085',
        'netdev': '#f39c12',
        'printer': '#e67e22',
        'infrastructure': '#1abc9c',
        'devops': '#34495e',
        'appops': '#95a5a6',
        'uncat': '#7f8c8d',
        'crap': '#ecf0f1',
        'empty': '#bdc3c7',
        'unauth': '#c0392b',
        'notfound': '#d35400',
        'serviceunavailable': '#8e44ad'
    }
    color = category_colors.get(sectionid, '#95a5a6')
    
    toc += f"""
    <div class="toc-card" style="border-left: 4px solid {color};">
        <div class="toc-card-header">
            <a href="{page_link}" class="toc-card-link">{section}</a>
            <span class="toc-page-badge">{page_text}</span>
        </div>
        <div class="toc-card-body">
            <div class="toc-count">{count}</div>
            <div class="toc-label">items</div>
        </div>
    </div>
    """

    html += "<h2 id=\"{0}\">{1}</h2>".format(sectionid, section)
    unknowns = [x for x in group_data if x.page_title == 'Unknown']
    group_data = [x for x in group_data if x.page_title != 'Unknown']
    while len(group_data) > 0:
        test_element = group_data.pop(0)
        temp = [x for x in group_data if fuzz.token_sort_ratio(
            test_element.page_title, x.page_title) >= 70]
        temp.append(test_element)
        temp = sorted(temp, key=lambda k: k.page_title)
        grouped_elements.extend(temp)
        group_data = [x for x in group_data if fuzz.token_sort_ratio(
            test_element.page_title, x.page_title) < 70]

    grouped_elements.extend(unknowns)
    # Keep toc_table for backward compatibility but we'll use cards now
    toc_table += ("<tr><td>{0}</td><td>{1}</td>").format(section,
                                                         str(len(grouped_elements)))
    return grouped_elements, toc, toc_table, html



def sort_data_and_write(cli_parsed, data):
    """Writes out reports for HTTP objects

    Args:
        cli_parsed (TYPE): CLI Options
        data (TYPE): Full set of data
    """
    # Set default results per page if not specified (for backward compatibility)
    if not hasattr(cli_parsed, 'results') or cli_parsed.results is None:
        cli_parsed.results = 25
    
    # We'll be using this number for our table of contents
    total_results = len(data)
    categories = [('highval', 'High Value Targets', 'highval'),
                  ('virtualization', 'Virtualization','virtualization'),
                  ('kvm','Remote Console/KVM','kvm'),
                  ('dirlist', 'Directory Listings', 'dirlist'),
                  ('cms', 'Content Management System (CMS)', 'cms'),
                  ('idrac', 'IDRAC/ILo/Management Interfaces', 'idrac'),
                  ('storage', 'Storage Systems', 'storage'),
                  ('nas', 'Network Attached Storage (NAS)', 'nas'),
                  ('comms', 'Communications', 'comms'),
                  ('devops', 'Development Operations', 'devops'),
                  ('secops', 'Security Operations', 'secops'),
                  ('monitoring', 'Monitoring Systems', 'monitoring'),
                  ('appops', 'Application Operations', 'appops'),
                  ('appserver', 'Application Servers', 'appserver'),
                  ('webserver', 'Web Servers', 'webserver'),
                  ('dataops', 'Data Operations', 'dataops'),
                  ('network_device', 'Network Devices', 'network_device'),
                  ('netdev', 'Network Devices (Legacy)', 'netdev'),
                  ('network_management', 'Network Management', 'network_management'),
                  ('voip', 'Voice over IP (VoIP)', 'voip'),
                  ('video_conference', 'Video Conference / Presentation', 'video_conference'),
                  ('printer', 'Printers', 'printer'),
                  ('camera', 'Cameras', 'camera'),
                  ('iot', 'IoT Devices', 'iot'),
                  ('itsm', 'IT Service Management', 'itsm'),
                  ('business_app', 'Business Applications', 'business_app'),
                  ('api', 'API Documentation', 'api'),
                  ('infrastructure', 'Infrastructure', 'infrastructure'),
                  ('unknown', 'Unknown Applications', 'unknown'),
                  (None, 'Uncategorized', 'uncat'),
                  ('construction', 'Under Construction', 'construction'),
                  ('crap', 'Splash Pages', 'crap'),
                  ('empty', 'No Significant Content', 'empty'),
                  ('error_page', 'Error Pages', 'error_page'),
                  ('unauth', '401/403 Unauthorized', 'unauth'),
                  ('notfound', '404 Not Found', 'notfound'),
                  ('successfulLogin', 'Successful Logins', 'successfulLogin'),
                  ('identifiedLogin', 'Identified Logins', 'identifiedLogin'),
                  ('redirector', 'Redirecting Pages', 'redirector'),
                  ('badhost', 'Invalid Hostname', 'badhost'),
                  ('inerror', 'Internal Error', 'inerror'),
                  ('badreq', 'Bad Request', 'badreq'),
                  ('badgw', 'Bad Gateway', 'badgw'),
                  ('serviceunavailable', 'Service Unavailable', 'serviceunavailable'),
                  ]
    if total_results == 0:
        return
    
    # Calculate statistics for dashboard
    stats = create_dashboard_stats(data)
    
    # Initialize stuff we need
    pages = []
    toc = create_report_toc_head(cli_parsed.date, cli_parsed.time)
    toc_table = "<table class=\"table\">"
    web_index_head = create_web_index_head(cli_parsed.date, cli_parsed.time, stats, data)
    table_head = create_table_head()
    counter = 1
    
    # Generate category options for filter
    all_categories = set()
    for obj in data:
        if obj.category:
            all_categories.add(obj.category)
    category_options = ''.join([f'<option value="{cat}">{cat}</option>' 
                               for cat in sorted(all_categories)])
    
    # Inject category options into the head
    web_index_head = web_index_head.replace(
        '<option value="">All Categories</option>',
        f'<option value="">All Categories</option>{category_options}'
    )
    csv_request_data = "Protocol,Port,Domain,URL,Resolved,Request Status,Title,Category,Default Creds,Screenshot Path, Source Path"

    # Generate and write json log of requests
    for json_request in data:
        url = urllib.parse.urlparse(json_request._remote_system)

        # CSV - PROTOCOL
        csv_request_data += "\n" + url.scheme + ","
        
        # CSV - PORT
        if url.port is not None:
            csv_request_data += str(url.port) + ","
        elif url.scheme == 'http':
            csv_request_data += "80,"
        elif url.scheme == 'https':
            csv_request_data += "443,"
        
        # CSV - DOMAIN
        try:
            csv_request_data += url.hostname + ","
        except TypeError:
            print("Error when accessing a target's hostname (it's not existent)")
            print("Possible bad url (improperly formatted) in the URL list.")
            print("Fix your list and re-try. Killing EyeWitness....")
            sys.exit(1)
        
        # CSV - URL
        csv_request_data += json_request._remote_system + ","
        
        # CSV - RESOLVED
        resolved_value = json_request.resolved if json_request.resolved else ""
        csv_request_data += resolved_value + ","

        # CSV - REQUEST STATUS
        if json_request._error_state == None:
            csv_request_data += "Successful,"
        else:
            csv_request_data += json_request._error_state + ","
        
        # CSV - TITLE
        try:
            # get attribute safely
            title = getattr(json_request, "_page_title", None)
            if title is None:
                title_text = "None"
            else:
                # ensure string, replace double-quotes so CSV remains valid
                title_text = str(title).replace('"', '""')
            csv_request_data += '"' + title_text + '",'
        except (UnicodeDecodeError, UnicodeEncodeError, AttributeError, TypeError) as e:
            # fallback for any encoding/None/attribute/concatenation issues
            csv_request_data += '"!Error",'
        
        # CSV - CATEGORY
        csv_request_data += str(json_request._category) + ","
        # CSV - DEFAULT CREDS/Signature
        csv_request_data += "\"" + str(json_request._default_creds) + "\","
        # CSV - SCREENSHOT PATH 
        csv_request_data += json_request._screenshot_path + ","
        # CSV - Source Path
        csv_request_data += json_request._source_path

    with open(os.path.join(cli_parsed.d, 'Requests.csv'), 'a') as f:
        f.write(csv_request_data)

    # Pre-filter error entries
    def key_lambda(k):
        if k.error_state is None:
            k.error_state = str(k.error_state)
        if k.page_title is None:
            k.page_title = str(k.page_title)
        return (k.error_state, k.page_title)
    errors = sorted([x for x in data if (x is not None) and (x.error_state is not None)],
                     key=key_lambda)
    data[:] = [x for x in data if x.error_state is None]
    data = sorted(data, key=lambda k: str(k.page_title))
    html = u""
    # Loop over our categories and populate HTML with cards
    for cat in categories:
        grouped, toc, toc_table, html = process_group(
            data, cat[0], toc, toc_table, len(pages), cat[1], cat[2], html)
        if len(grouped) > 0:
            html += f'<h2 id="{cat[2]}">{cat[1]}</h2>'
        pcount = 0
        for obj in grouped:
            pcount += 1
            html += obj.create_card_html()
            if (counter % cli_parsed.results == 0) or (counter == (total_results) -1):
                html = (web_index_head + "EW_REPLACEME" + html + "</div>")
                pages.append(html)
                html = u""
                if pcount < len(grouped):
                    html += f'<h2 id="{cat[2]}">{cat[1]}</h2>'
            counter += 1

    # Add our errors here (at the very very end)
    if len(errors) > 0:
        html += '<h2>Errors</h2>'
        for obj in errors:
            html += obj.create_card_html()
            if (counter % cli_parsed.results == 0) or (counter == (total_results)):
                html = (web_index_head + "EW_REPLACEME" + html + "</div>")
                pages.append(html)
                html = u"<h2>Errors</h2>"
            counter += 1

    # Close out any stuff thats hanging
    # Add Errors card if any
    if len(errors) > 0:
        toc += f"""
    <div class="toc-card" style="border-left: 4px solid #e74c3c;">
        <div class="toc-card-header">
            <span class="toc-card-link">Errors</span>
        </div>
        <div class="toc-card-body">
            <div class="toc-count">{len(errors)}</div>
            <div class="toc-label">items</div>
        </div>
    </div>
    """
    
    # Add Total summary card
    toc += f"""
    <div class="toc-card toc-total-card" style="border-left: 4px solid #667eea;">
        <div class="toc-card-header">
            <span class="toc-card-link" style="font-weight: bold; font-size: 1.1em;">Total</span>
        </div>
        <div class="toc-card-body">
            <div class="toc-count" style="font-size: 2em;">{total_results}</div>
            <div class="toc-label">URLs scanned</div>
        </div>
    </div>
    """
    
    toc += "</div>"  # Close toc-grid
    toc_table += "<tr><td>Errors</td><td>{0}</td></tr>".format(
        str(len(errors)))
    toc_table += "<tr><th>Total</th><td>{0}</td></tr>".format(total_results)
    toc_table += "</table>"

    if (html != u"") and (counter - total_results != 0):
        html = (web_index_head + "EW_REPLACEME" + html + "</div>")
        pages.append(html)

    toc = "{0}</div>".format(toc)  # Close toc-container

    # ========================================================================
    # STATIC HTML REPORT GENERATION - DISABLED
    # ========================================================================
    # Static HTML reports (gallery.html, detail_*.html, report.html, report_page*.html)
    # are no longer generated because the webapp handles all UI rendering.
    # 
    # All data is stored in the SQLite database and can be accessed via:
    #   - Webapp: http://localhost:5000 (start with: cd webapp && ./start.sh)
    #   - Direct database access: <project_dir>/<project_name>.db
    #
    # If you need static HTML reports, set GENERATE_STATIC_REPORTS = True below
    # ========================================================================
    GENERATE_STATIC_REPORTS = False
    
    if GENERATE_STATIC_REPORTS:
        # Generate modern gallery and detail views
        try:
            from modules.enhanced_report import generate_gallery_html, generate_detail_html
            
            print('[*] Generating modern gallery and detail views...')
            
            # Generate gallery HTML
            gallery_html = generate_gallery_html(data, cli_parsed.d, cli_parsed)
            
            # Create gallery page with full HTML structure
            gallery_page = web_index_head.replace('EW_REPLACEME', '')
            gallery_page = gallery_page.replace(
                '<h1 style="text-align: center; color: #333; margin-bottom: 20px;">EyeWitness Report</h1>',
                '<h1 style="text-align: center; color: #333; margin-bottom: 20px;">EyeWitness Report - Gallery</h1>'
            )
            gallery_page += gallery_html
            gallery_page += '</div></body></html>'
            
            # Write gallery page
            with open(os.path.join(cli_parsed.d, 'gallery.html'), 'w', encoding='utf-8') as f:
                f.write(gallery_page)
            print('  [+] Gallery page generated: gallery.html')
            
            # Generate detail pages
            for idx, obj in enumerate(data):
                detail_html = generate_detail_html(obj, idx, len(data), cli_parsed.d, cli_parsed)
                detail_page = web_index_head.replace('EW_REPLACEME', '')
                detail_page = detail_page.replace(
                    '<h1 style="text-align: center; color: #333; margin-bottom: 20px;">EyeWitness Report</h1>',
                    f'<h1 style="text-align: center; color: #333; margin-bottom: 20px;">EyeWitness Report - Detail {idx + 1}</h1>'
                )
                detail_page += detail_html
                detail_page += '</div></body></html>'
                
                with open(os.path.join(cli_parsed.d, f'detail_{idx}.html'), 'w', encoding='utf-8') as f:
                    f.write(detail_page)
            
            print(f'  [+] Generated {len(data)} detail pages')
        except Exception as e:
            print(f'  [!] Error generating modern gallery views: {e}')
            import traceback
            traceback.print_exc()
        
        if len(pages) == 1:
            with open(os.path.join(cli_parsed.d, 'report.html'), 'a', encoding='utf-8') as f:
                f.write(toc)
                f.write(pages[0].replace('EW_REPLACEME', ''))
                f.write("</div></body>\n</html>")
        else:
            num_pages = len(pages) + 1
            bottom_text = "\n<center><br>"
            bottom_text += ("<a href=\"report.html\"> Page 1</a>")
            skip_last_dummy = False
            # Generate our header/footer data here
            for i in range(2, num_pages):
                badd_page = "</center>EW_REPLACEME<table border=\"1\">\n        <tr>\n        <th>Web Request Info</th>\n        <th>Web Screenshot</th>\n        </tr></table><br>"
                if badd_page in pages[i-1]:
                    skip_last_dummy = True
                    pass
                else:
                    bottom_text += ("<a href=\"report_page{0}.html\"> Page {0}</a>").format(str(i))
            bottom_text += "</center>\n"
            top_text = bottom_text
            # Generate our next/previous page buttons
            if skip_last_dummy:
                amount = len(pages) - 1
            else:
                amount = len(pages)
            for i in range(0, amount):
                headfoot = "<h3>Page {0}</h3>".format(str(i+1))
                headfoot += "<center>"
                if i == 0:
                    headfoot += ("<a href=\"report_page2.html\" id=\"next\"> Next Page "
                                 "</a></center>")
                elif i == amount - 1:
                    if i == 1:
                        headfoot += ("<a href=\"report.html\" id=\"previous\"> Previous Page "
                                     "</a></center>")
                    else:
                        headfoot += ("<a href=\"report_page{0}.html\" id=\"previous\"> Previous Page "
                                     "</a></center>").format(str(i))
                elif i == 1:
                    headfoot += ("<a href=\"report.html\" id=\"previous\">Previous Page</a>&nbsp"
                                 "<a href=\"report_page{0}.html\" id=\"next\"> Next Page"
                                 "</a></center>").format(str(i+2))
                else:
                    headfoot += ("<a href=\"report_page{0}.html\" id=\"previous\">Previous Page</a>"
                                 "&nbsp<a href=\"report_page{1}.html\" id=\"next\"> Next Page"
                                 "</a></center>").format(str(i), str(i+2))
                # Finalize our pages by replacing placeholder stuff and writing out
                # the headers/footers
                pages[i] = pages[i].replace(
                    'EW_REPLACEME', headfoot + top_text) + bottom_text + '<br>' + headfoot + '</div></body></html>'

            # Write out our report to disk!
            if len(pages) == 0:
                return
            with open(os.path.join(cli_parsed.d, 'report.html'), 'a', encoding='utf-8') as f:
                f.write(toc)
                f.write(pages[0])
            write_out = len(pages)
            for i in range(2, write_out + 1):
                bad_page = "<table border=\"1\">\n        <tr>\n        <th>Web Request Info</th>\n        <th>Web Screenshot</th>\n        </tr></table><br>\n<center><br><a "
                badd_page2 = "</center>EW_REPLACEME<table border=\"1\">\n        <tr>\n        <th>Web Request Info</th>\n        <th>Web Screenshot</th>\n        </tr></table><br>"
                if (bad_page in pages[i-1]) or (badd_page2 in pages[i-1]):
                    pass
                else:
                    with open(os.path.join(cli_parsed.d, 'report_page{0}.html'.format(str(i))), 'w', encoding='utf-8') as f:
                        f.write(pages[i - 1])
    else:
        print('[*] Static HTML reports disabled - use the webapp to view results')
        print(f'    Database: {cli_parsed.d}/{os.path.basename(cli_parsed.d)}.db')
        print('    Start webapp: cd webapp && ./start.sh')


def create_dashboard_stats(data):
    """Create dashboard statistics from data
    
    Args:
        data: List of HTTPTableObject
        
    Returns:
        dict: Statistics dictionary
    """
    stats = {
        'total': len(data),
        'pwned': 0,
        'with_creds': 0,
        'tested': 0,
        'categories': {},
        'applications': {},
        'errors': 0
    }
    
    for obj in data:
        # Count Pwned (successful credentials)
        if obj.credential_test_result:
            result = obj.credential_test_result
            if isinstance(result, dict):
                successful = result.get('successful_credentials', [])
                if successful:
                    stats['pwned'] += 1
                if result.get('tested', False):
                    stats['tested'] += 1
        
        # Count with default credentials
        if obj.default_creds:
            stats['with_creds'] += 1
        
        # Count by category
        cat = obj.category or 'Uncategorized'
        stats['categories'][cat] = stats['categories'].get(cat, 0) + 1
        
        # Count by application (AI or signature)
        app_name = None
        if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
            app_name = obj.ai_application_info.get('application_name')
        elif obj.default_creds and ' / ' in str(obj.default_creds):
            app_name = str(obj.default_creds).split(' / ')[0].strip()
        
        if app_name:
            stats['applications'][app_name] = stats['applications'].get(app_name, 0) + 1
        
        # Count errors
        if obj.error_state:
            stats['errors'] += 1
    
    return stats


def create_dashboard_html(stats, data=None):
    """Create HTML for dashboard with statistics
    
    Args:
        stats: Statistics dictionary
        data: List of HTTPTableObject (optional, for summary table)
        
    Returns:
        str: HTML for dashboard
    """
    pwned_pct = (stats['pwned'] / stats['total'] * 100) if stats['total'] > 0 else 0
    creds_pct = (stats['with_creds'] / stats['total'] * 100) if stats['total'] > 0 else 0
    
    # Top categories
    top_cats = sorted(stats['categories'].items(), key=lambda x: x[1], reverse=True)[:5]
    top_cats_html = ''.join([f'<span class="category-tag">{cat} ({count})</span>' 
                             for cat, count in top_cats])
    
    # Top applications
    top_apps = sorted(stats['applications'].items(), key=lambda x: x[1], reverse=True)[:5]
    top_apps_html = ''.join([f'<span class="category-tag">{app} ({count})</span>' 
                             for app, count in top_apps])
    
    # Summary table HTML (if data provided)
    summary_table = ""
    if data:
        summary_table = create_summary_table_html(data)
    
    return f"""
    <div class="dashboard">
        <h2 style="margin-top: 0; text-align: center;">📊 Scan Summary</h2>
        <div style="display: flex; flex-wrap: wrap; justify-content: center;">
            <div class="stat-card">
                <div class="stat-label">Total URLs</div>
                <div class="stat-number">{stats['total']}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔓 Pwned!</div>
                <div class="stat-number" style="color: #ff6b6b;">{stats['pwned']}</div>
                <div class="stat-label">{pwned_pct:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">🔑 With Credentials</div>
                <div class="stat-number" style="color: #4ecdc4;">{stats['with_creds']}</div>
                <div class="stat-label">{creds_pct:.1f}%</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">✅ Tested</div>
                <div class="stat-number">{stats['tested']}</div>
            </div>
        </div>
        <div style="margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.3);">
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div>
                    <strong>Top Categories:</strong><br>
                    {top_cats_html}
                </div>
                <div>
                    <strong>Top Applications:</strong><br>
                    {top_apps_html}
                </div>
            </div>
        </div>
    </div>
    
    {summary_table}
    
    <div class="filters">
        <h3 style="margin-top: 0;">🔍 Filters & Search</h3>
        <div class="filter-group">
            <label>Category:</label>
            <select id="filterCategory" onchange="filterResults()">
                <option value="">All Categories</option>
            </select>
            
            <label>Credentials:</label>
            <select id="filterCreds" onchange="filterResults()">
                <option value="all">All</option>
                <option value="yes">With Credentials</option>
                <option value="no">No Credentials</option>
            </select>
            
            <label>Search:</label>
            <input type="text" id="searchBox" placeholder="Search URLs, titles, apps..." 
                   onkeyup="filterResults()" style="width: 300px;">
            
            <label>
                <input type="checkbox" id="showPwned" onchange="filterResults()">
                Show only Pwned
            </label>
        </div>
        <div style="margin-top: 10px; color: #666;">
            Showing <strong id="visibleCount">{stats['total']}</strong> of {stats['total']} results
        </div>
    </div>
    """


def create_summary_table_html(data):
    """Create a compact summary table for quick overview
    
    Args:
        data: List of HTTPTableObject
        
    Returns:
        str: HTML for summary table
    """
    html = """
    <div style="background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
        <h3 style="margin-top: 0;">📋 Quick Summary Table</h3>
        <div style="overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
        <thead>
            <tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                <th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">URL</th>
                <th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Application</th>
                <th style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">Status</th>
                <th style="padding: 10px; text-align: left; border: 1px solid #dee2e6;">Credentials</th>
                <th style="padding: 10px; text-align: center; border: 1px solid #dee2e6;">Screenshot</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for obj in data[:50]:  # Show first 50 for performance
        url = obj.remote_system
        app_name = "Unknown"
        if obj.ai_application_info and isinstance(obj.ai_application_info, dict):
            app_name = obj.ai_application_info.get('application_name', 'Unknown')
        elif obj.default_creds and ' / ' in str(obj.default_creds):
            app_name = str(obj.default_creds).split(' / ')[0].strip()
        elif obj.page_title and str(obj.page_title) != 'Unknown':
            app_name = str(obj.page_title)[:30]
        
        # Status badges
        status_badges = []
        is_pwned = False
        if obj.credential_test_result and isinstance(obj.credential_test_result, dict):
            successful = obj.credential_test_result.get('successful_credentials', [])
            if successful:
                is_pwned = True
                status_badges.append('<span style="background: #ff6b6b; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.85em;">PWNED</span>')
            elif obj.credential_test_result.get('tested', False):
                status_badges.append('<span style="background: #95a5a6; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.85em;">Tested</span>')
        
        if obj.default_creds:
            status_badges.append('<span style="background: #4ecdc4; color: white; padding: 3px 8px; border-radius: 10px; font-size: 0.85em;">Has Creds</span>')
        
        category = obj.category or 'Uncategorized'
        status_badges.append(f'<span style="background: #e9ecef; color: #495057; padding: 3px 8px; border-radius: 10px; font-size: 0.85em;">{category}</span>')
        
        # Credentials
        creds_display = "-"
        if obj.default_creds:
            creds = str(obj.default_creds)
            if ' / ' in creds:
                creds_display = creds.split(' / ')[-1][:30]
            else:
                creds_display = creds[:30]
            if is_pwned:
                creds_display = f'<span style="color: #ff6b6b; font-weight: bold;">{creds_display}</span>'
        
        # Screenshot
        has_screenshot = "❌"
        if os.path.isfile(obj.screenshot_path) and not obj.blank and not obj.error_state:
            has_screenshot = "✅"
        
        row_class = 'pwned-row' if is_pwned else ''
        html += f"""
        <tr class="{row_class}" style="border-bottom: 1px solid #dee2e6;">
            <td style="padding: 10px; border: 1px solid #dee2e6;"><a href="{url}" target="_blank" style="color: #667eea; text-decoration: none;">{html_module.escape(url[:50])}</a></td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">{html_module.escape(app_name[:30])}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: center;">{' '.join(status_badges)}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; font-family: monospace; font-size: 0.9em;">{creds_display}</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: center;">{has_screenshot}</td>
        </tr>
        """
    
    if len(data) > 50:
        html += f"""
        <tr>
            <td colspan="5" style="padding: 10px; text-align: center; color: #666; font-style: italic;">
                ... and {len(data) - 50} more results (see cards below)
            </td>
        </tr>
        """
    
    html += """
        </tbody>
        </table>
        </div>
    </div>
    """
    return html


def create_web_index_head(date, time, stats=None, data=None):
    """Creates the header for a http report with modern dashboard

    Args:
        date (String): Date of report start
        time (String): Time of report start
        stats (dict): Statistics dictionary (optional)
        data: List of HTTPTableObject (optional, for summary table)

    Returns:
        String: HTTP Report Start html
    """
    dashboard_html = ""
    if stats:
        dashboard_html = create_dashboard_html(stats, data)
    
    return ("""<html>
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel=\"stylesheet\" href=\"bootstrap.min.css\" type=\"text/css\"/>
        <link rel=\"stylesheet\" href=\"style.css\" type=\"text/css\"/>
        <title>EyeWitness Report</title>
        <script src="jquery-3.7.1.min.js"></script>
        <style>
        /* Modern Dashboard Styles */
        .dashboard {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .stat-card {{
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
            padding: 20px;
            margin: 10px;
            text-align: center;
            backdrop-filter: blur(10px);
            transition: transform 0.2s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        .stat-number {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        .pwned-badge {{
            background: #ff6b6b;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
            margin: 5px;
        }}
        .cred-badge {{
            background: #4ecdc4;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
            margin: 5px;
        }}
        .filters {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .filter-group {{
            margin: 10px 0;
        }}
        .filter-group label {{
            font-weight: bold;
            margin-right: 10px;
        }}
        .filter-group select, .filter-group input {{
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 15px;
        }}
        .url-card {{
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s;
        }}
        .url-card:hover {{
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }}
        .url-card.pwned {{
            border-left: 5px solid #ff6b6b;
        }}
        .url-card.has-creds {{
            border-left: 5px solid #4ecdc4;
        }}
        .url-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .url-title {{
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
        }}
        .url-title a {{
            color: #667eea;
            text-decoration: none;
        }}
        .url-title a:hover {{
            text-decoration: underline;
        }}
        .url-badges {{
            display: flex;
            gap: 10px;
        }}
        .url-info {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 15px 0;
        }}
        .info-item {{
            padding: 10px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .info-label {{
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
        }}
        .info-value {{
            color: #333;
            margin-top: 5px;
        }}
        .screenshot-container {{
            text-align: center;
            margin-top: 15px;
        }}
        .screenshot-container img {{
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .category-tag {{
            background: #e9ecef;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.85em;
            display: inline-block;
            margin: 5px 5px 5px 0;
        }}
        .hidden {{
            display: none !important;
        }}
        
        /* Table of Contents Styles */
        .toc-container {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .toc-title {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
            margin-bottom: 25px;
            text-align: center;
        }}
        .toc-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .toc-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s;
            cursor: pointer;
        }}
        .toc-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .toc-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .toc-card-link {{
            color: #333;
            text-decoration: none;
            font-weight: 600;
            font-size: 1em;
            flex: 1;
        }}
        .toc-card-link:hover {{
            color: #667eea;
        }}
        .toc-page-badge {{
            background: #667eea;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
        }}
        .toc-card-body {{
            text-align: center;
        }}
        .toc-count {{
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .toc-label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .toc-total-card {{
            grid-column: 1 / -1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .toc-total-card .toc-card-link {{
            color: white;
        }}
        .toc-total-card .toc-count {{
            color: white;
        }}
        .toc-total-card .toc-label {{
            color: rgba(255,255,255,0.9);
        }}
        
        /* Lightbox Styles */
        .screenshot-thumbnail {{
            width: 200px;
            height: 150px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin: 10px;
        }}
        .screenshot-thumbnail:hover {{
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        .lightbox {{
            display: none;
            position: fixed;
            z-index: 9999;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.9);
            animation: fadeIn 0.3s;
        }}
        .lightbox.active {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .lightbox-content {{
            max-width: 90%;
            max-height: 90%;
            margin: auto;
            animation: zoomIn 0.3s;
        }}
        .lightbox-content img {{
            max-width: 100%;
            max-height: 90vh;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 40px;
            color: white;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
            z-index: 10000;
            transition: transform 0.2s;
        }}
        .lightbox-close:hover {{
            transform: scale(1.2);
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        @keyframes zoomIn {{
            from {{ transform: scale(0.8); opacity: 0; }}
            to {{ transform: scale(1); opacity: 1; }}
        }}
        
        /* Gallery Styles */
        .gallery-container {{
            padding: 20px;
        }}
        .gallery-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .gallery-stats {{
            display: flex;
            gap: 15px;
            align-items: center;
        }}
        .gallery-filters {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            align-items: center;
        }}
        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .filter-group label {{
            font-weight: bold;
            font-size: 0.9em;
        }}
        .filter-group select, .filter-group input {{
            padding: 6px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .gallery-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .gallery-item {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .gallery-item:hover {{
            transform: translateY(-5px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}
        .gallery-item-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: #f8f9fa;
        }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: bold;
            color: white;
        }}
        .status-200 {{ background: #27ae60; }}
        .status-403 {{ background: #e67e22; }}
        .status-404 {{ background: #95a5a6; }}
        .status-401 {{ background: #f39c12; }}
        .status-timeout {{ background: #e74c3c; }}
        .status-error {{ background: #c0392b; }}
        .pwned-badge-small {{
            background: #ff6b6b;
            color: white;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.7em;
            font-weight: bold;
        }}
        .gallery-item-screenshot {{
            width: 100%;
            height: 150px;
            overflow: hidden;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .gallery-item-screenshot img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}
        .no-screenshot {{
            color: #999;
            font-size: 0.9em;
        }}
        .gallery-item-info {{
            padding: 12px;
        }}
        .gallery-item-title {{
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .gallery-item-url {{
            font-size: 0.85em;
            color: #666;
            margin-bottom: 8px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .gallery-item-techs {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 5px;
        }}
        .tech-badge {{
            background: #e9ecef;
            padding: 3px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            color: #495057;
        }}
        .gallery-item-time {{
            font-size: 0.75em;
            color: #999;
        }}
        .gallery-footer {{
            text-align: center;
            padding: 15px;
            color: #666;
        }}
        
        /* Detail View Styles */
        .detail-container {{
            padding: 20px;
        }}
        .detail-header {{
            margin-bottom: 20px;
        }}
        .detail-nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }}
        .nav-btn {{
            padding: 8px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.2s;
        }}
        .nav-btn:hover {{
            background: #5568d3;
        }}
        .nav-btn.disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .detail-counter {{
            font-weight: bold;
            color: #333;
        }}
        .detail-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .detail-left {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .detail-screenshot {{
            text-align: center;
            margin-bottom: 20px;
        }}
        .detail-screenshot img {{
            max-width: 100%;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .no-screenshot-large {{
            padding: 100px;
            background: #f0f0f0;
            border-radius: 8px;
            color: #999;
            text-align: center;
        }}
        .detail-basic-info h3 {{
            margin-top: 0;
            color: #333;
        }}
        .detail-url {{
            margin: 15px 0;
        }}
        .detail-url a {{
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
        }}
        .btn-open {{
            margin-left: 10px;
            padding: 6px 15px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }}
        .detail-pwned {{
            margin: 15px 0;
            padding: 10px;
            background: #fff3cd;
            border-left: 4px solid #ff6b6b;
            border-radius: 4px;
        }}
        .detail-technologies, .detail-ssl {{
            margin-top: 20px;
        }}
        .detail-technologies h4, .detail-ssl h4 {{
            margin-top: 0;
            color: #333;
        }}
        .tech-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .info-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .info-table td {{
            padding: 8px;
            border-bottom: 1px solid #eee;
        }}
        .info-table td:first-child {{
            font-weight: bold;
            width: 100px;
        }}
        .detail-right {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .detail-summary {{
            background: #27ae60;
            color: white;
            padding: 20px;
            border-radius: 8px;
        }}
        .summary-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 15px;
            font-weight: bold;
            margin-bottom: 15px;
            background: rgba(255,255,255,0.2);
        }}
        .detail-summary p {{
            margin: 15px 0;
            line-height: 1.6;
        }}
        .detail-summary code {{
            background: rgba(255,255,255,0.2);
            padding: 2px 6px;
            border-radius: 3px;
        }}
        .summary-metrics {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 10px;
            margin: 20px 0;
        }}
        .metric-box {{
            background: rgba(255,255,255,0.2);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
        }}
        .metric-number {{
            font-size: 2em;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .metric-label {{
            font-size: 0.85em;
            opacity: 0.9;
        }}
        .detail-time {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-top: 15px;
        }}
        .detail-tabs {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .tab-buttons {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            border-bottom: 2px solid #eee;
        }}
        .tab-btn {{
            padding: 10px 20px;
            background: none;
            border: none;
            border-bottom: 3px solid transparent;
            cursor: pointer;
            font-size: 0.9em;
            color: #666;
            transition: all 0.2s;
        }}
        .tab-btn:hover {{
            color: #667eea;
        }}
        .tab-btn.active {{
            color: #667eea;
            border-bottom-color: #667eea;
            font-weight: bold;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
        .log-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
        }}
        .log-table th {{
            background: #f8f9fa;
            padding: 10px;
            text-align: left;
            border-bottom: 2px solid #dee2e6;
            font-weight: bold;
        }}
        .log-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #eee;
        }}
        .log-table tr:hover {{
            background: #f8f9fa;
        }}
        .log-error {{ color: #e74c3c; }}
        .log-warning {{ color: #f39c12; }}
        .log-info {{ color: #3498db; }}
        </style>
        <script type="text/javascript">
        function toggleUA(id, url){{
        idi = "." + id;
        $(idi).toggle();
        change = document.getElementById(id);
        if (change.innerHTML.indexOf("expand") > -1){{
            change.innerHTML = "Click to collapse User Agents for " + url;
        }}else{{
            change.innerHTML = "Click to expand User Agents for " + url;
        }}
        }}

        // Filter functions
        function filterResults() {{
            var category = document.getElementById('filterCategory').value;
            var creds = document.getElementById('filterCreds').value;
            var search = document.getElementById('searchBox').value.toLowerCase();
            var showPwned = document.getElementById('showPwned').checked;
            
            var cards = document.querySelectorAll('.url-card');
            var visible = 0;
            
            cards.forEach(function(card) {{
                var cardCategory = card.getAttribute('data-category') || '';
                var cardHasCreds = card.getAttribute('data-has-creds') === 'true';
                var cardIsPwned = card.classList.contains('pwned');
                var cardText = card.textContent.toLowerCase();
                
                var matchCategory = !category || cardCategory === category;
                var matchCreds = creds === 'all' || 
                    (creds === 'yes' && cardHasCreds) || 
                    (creds === 'no' && !cardHasCreds);
                var matchSearch = !search || cardText.includes(search);
                var matchPwned = !showPwned || cardIsPwned;
                
                if (matchCategory && matchCreds && matchSearch && matchPwned) {{
                    card.classList.remove('hidden');
                    visible++;
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
            
            document.getElementById('visibleCount').textContent = visible;
        }}
        
        // Lightbox functions
        function openLightbox(imgSrc) {{
            var lightbox = document.getElementById('lightbox');
            var lightboxImg = document.getElementById('lightbox-img');
            lightboxImg.src = imgSrc;
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden';
        }}
        
        function closeLightbox() {{
            var lightbox = document.getElementById('lightbox');
            lightbox.classList.remove('active');
            document.body.style.overflow = 'auto';
        }}
        
        // Close lightbox on click outside image
        document.addEventListener('click', function(e) {{
            var lightbox = document.getElementById('lightbox');
            if (e.target === lightbox) {{
                closeLightbox();
            }}
        }});
        
        // Close lightbox on ESC key
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') {{
                closeLightbox();
            }}
        }});
        
        // Initialize filters
        document.addEventListener('DOMContentLoaded', function() {{
            filterResults();
        }});

        document.onkeydown = function(event){{
            event = event || window.event;
            switch (event.keyCode){{
                case 37:
                    leftArrow();
                    break;
                case 39:
                    rightArrow();
                    break;
            }}
        }};
                
        function leftArrow(){{
            var prev = $('#previous')[0];
            if (prev) prev.click();
        }};

        function rightArrow(){{
            var next = $('#next')[0];
            if (next) next.click();
        }};

        </script>
        </head>
        <body>
        <!-- Lightbox Modal -->
        <div id="lightbox" class="lightbox">
            <span class="lightbox-close" onclick="closeLightbox()">&times;</span>
            <div class="lightbox-content">
                <img id="lightbox-img" src="" alt="Screenshot">
            </div>
        </div>
        <div class="container-fluid" style="max-width: 1400px; margin: 0 auto; padding: 20px;">
        <h1 style="text-align: center; color: #333; margin-bottom: 20px;">EyeWitness Report</h1>
        <p style="text-align: center; color: #666; margin-bottom: 30px;">Generated on {0} at {1}</p>
        {2}
        """).format(date, time, dashboard_html)


def search_index_head():
    return ("""<html>
        <head>
        <link rel=\"stylesheet\" href=\"bootstrap.min.css\" type=\"text/css\"/>
        <title>EyeWitness Report</title>
        <script src="jquery-3.7.1.min.js"></script>
        <script type="text/javascript">
        function toggleUA(id, url){{
        idi = "." + id;
        $(idi).toggle();
        change = document.getElementById(id);
        if (change.innerHTML.indexOf("expand") > -1){{
            change.innerHTML = "Click to collapse User Agents for " + url;
        }}else{{
            change.innerHTML = "Click to expand User Agents for " + url;
        }}
        }}
        </script>
        </head>
        <body>
        <center>
        """)


def create_table_head():
    return ("""<table border=\"1\">
        <tr>
        <th>Web Request Info</th>
        <th>Web Screenshot</th>
        </tr>""")


def create_report_toc_head(date, time):
    return ("""<div class="toc-container">
        <h2 class="toc-title">📑 Table of Contents</h2>
        <div class="toc-grid">""")


def search_report(cli_parsed, data, search_term):
    pages = []
    web_index_head = search_index_head()
    table_head = create_table_head()
    counter = 1

    data[:] = [x for x in data if x.error_state is None]
    data = sorted(data, key=lambda k: k.page_title)
    html = u""

    # Add our errors here (at the very very end)
    html += '<h2>Results for {0}</h2>'.format(search_term)
    html += table_head
    for obj in data:
        html += obj.create_table_html()
        if counter % cli_parsed.results == 0:
            html = (web_index_head + "EW_REPLACEME" + html +
                    "</table><br>")
            pages.append(html)
            html = u"" + table_head
        counter += 1

    if html != u"":
        html = (web_index_head + html + "</table><br>")
        pages.append(html)

    if len(pages) == 1:
        with open(os.path.join(cli_parsed.d, 'search.html'), 'a', encoding='utf-8') as f:
            f.write(pages[0].replace('EW_REPLACEME', ''))
            f.write("</body>\n</html>")
    else:
        num_pages = len(pages) + 1
        bottom_text = "\n<center><br>"
        bottom_text += ("<a href=\"search.html\"> Page 1</a>")
        # Generate our header/footer data here
        for i in range(2, num_pages):
            bottom_text += ("<a href=\"search_page{0}.html\"> Page {0}</a>").format(
                str(i))
        bottom_text += "</center>\n"
        top_text = bottom_text
        # Generate our next/previous page buttons
        for i in range(0, len(pages)):
            headfoot = "<center>"
            if i == 0:
                headfoot += ("<a href=\"search_page2.html\"> Next Page "
                             "</a></center>")
            elif i == len(pages) - 1:
                if i == 1:
                    headfoot += ("<a href=\"search.html\"> Previous Page "
                                 "</a></center>")
                else:
                    headfoot += ("<a href=\"search_page{0}.html\"> Previous Page "
                                 "</a></center>").format(str(i))
            elif i == 1:
                headfoot += ("<a href=\"search.html\">Previous Page</a>&nbsp"
                             "<a href=\"search_page{0}.html\"> Next Page"
                             "</a></center>").format(str(i+2))
            else:
                headfoot += ("<a href=\"search_page{0}.html\">Previous Page</a>"
                             "&nbsp<a href=\"search_page{1}.html\"> Next Page"
                             "</a></center>").format(str(i), str(i+2))
            # Finalize our pages by replacing placeholder stuff and writing out
            # the headers/footers
            pages[i] = pages[i].replace(
                'EW_REPLACEME', headfoot + top_text) + bottom_text + '<br>' + headfoot + '</body></html>'

        # Write out our report to disk!
        if len(pages) == 0:
            return
        with open(os.path.join(cli_parsed.d, 'search.html'), 'a', encoding='utf-8') as f:
            try:
                f.write(pages[0])
            except UnicodeEncodeError:
                f.write(pages[0].encode('utf-8'))
        for i in range(2, len(pages) + 1):
            with open(os.path.join(cli_parsed.d, 'search_page{0}.html'.format(str(i))), 'w', encoding='utf-8') as f:
                try:
                    f.write(pages[i - 1])
                except UnicodeEncodeError:
                    f.write(pages[i - 1].encode('utf-8'))
