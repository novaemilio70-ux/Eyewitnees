# -*- coding: utf-8 -*-
#
# EyeWitness - Plaintext Security Edition
# 
# This is a fork of the original EyeWitness project by Red Siege Information Security
# Original project: https://github.com/RedSiege/EyeWitness
# 
# Modifications and enhancements by Plaintext Security
# - AI-powered application identification and credential testing
# - Learned credentials system
# - Integrated port scanning
# - Enhanced Selenium-based credential testing
#
import hashlib
import os
import platform
import random
import shutil
import sys
import time
import xml.sax
import glob
import socket
from pathlib import Path
from netaddr import IPAddress
from netaddr.core import AddrFormatError
from urllib.parse import urlparse
from modules.validation import validate_url, validate_url_list, get_url_validation_errors


class XML_Parser(xml.sax.ContentHandler):

    def __init__(self, file_out, class_cli_obj):
        self.system_name = None
        self.port_number = None
        self.protocol = None
        self.masscan = False
        self.nmap = False
        self.nessus = False
        self.url_list = []
        self.port_open = False
        self.http_ports = ['80', '8080']
        self.https_ports = ['443', '8443']
        self.num_urls = 0
        self.get_fqdn = False
        self.get_ip = False
        self.service_detection = False
        self.out_file = file_out
        self.analyze_plugin_output = False
        self.read_plugin_output = False
        self.plugin_output = ""

        self.http_ports = self.http_ports + class_cli_obj.add_http_ports
        self.https_ports = self.https_ports + class_cli_obj.add_https_ports
        self.no_dns = class_cli_obj.no_dns
        self.only_ports = class_cli_obj.only_ports

    def startElement(self, tag, attributes):
        # Determine the Scanner being used
        if tag == "nmaprun" and attributes['scanner'] == "masscan":
            self.masscan = True
        elif tag == "nmaprun" and attributes['scanner'] == "nmap":
            self.nmap = True
        elif tag == "NessusClientData_v2":
            self.nessus = True

        if self.masscan or self.nmap:
            if tag == "address":
                if attributes['addrtype'].lower() == "mac":
                    pass
                else:
                    self.system_name = attributes['addr']
            elif tag == "hostname":
                if not self.no_dns:
                    if attributes['type'].lower() == "user":
                        self.system_name = attributes['name']
            elif tag == "port":
                self.port_number = attributes['portid']
            elif tag == "service":
                if "ssl" in attributes['name'] or self.port_number in self.https_ports:
                    self.protocol = "https"
                elif "tunnel" in attributes:
                    if "ssl" in attributes['tunnel'] and not "smtp" in attributes['name'] and not "imap" in attributes['name'] and not "pop3" in attributes['name']:
                        self.protocol = "https"
                elif "http" == attributes['name'] or self.port_number in self.http_ports:
                    self.protocol = "http"
                elif "http-alt" == attributes['name']:
                    self.protocol = "http"
            elif tag == "state":
                if attributes['state'] == "open":
                    self.port_open = True

        elif self.nessus:
            if tag == "ReportHost":
                if 'name' in attributes:
                    self.system_name = attributes['name']

            elif tag == "ReportItem":
                if "port" in attributes and "svc_name" in attributes and "pluginName" in attributes:
                    self.port_number = attributes['port']

                    service_name = attributes['svc_name']
                    # pluginID 22964 is the Service Detection Plugin
                    # But it uses www for the svc_name for both, http and https.
                    # To differentiate we have to look at the plugin_output...
                    if service_name == 'https?' or self.port_number in self.https_ports:
                        self.protocol = "https"
                    elif attributes['pluginID'] == "22964" and service_name == "www":
                        self.protocol = "http"
                        self.analyze_plugin_output = True
                    elif service_name == "www" or service_name == "http?":
                        self.protocol = "http"

                    self.service_detection = True

            elif tag == "plugin_output" and self.analyze_plugin_output:
                self.read_plugin_output = True

        return

    def endElement(self, tag):
        if self.masscan or self.nmap:
            if tag == "service":
                if not self.only_ports:
                    if (self.system_name is not None) and (self.port_number is not None) and self.port_open:
                        if self.protocol == "http" or self.protocol == "https":
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.protocol is None and self.port_number in self.http_ports:
                            built_url = "http://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.protocol is None and self.port_number in self.https_ports:
                            built_url = "https://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1

                else:
                    if (self.system_name is not None) and (self.port_number is not None) and self.port_open and int(self.port_number) in self.only_ports:
                        if self.protocol == "http" or self.protocol == "https":
                            built_url = self.protocol + "://" + self.system_name
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.protocol is None and self.port_number in self.http_ports:
                            built_url = "http://" + self.system_name
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.protocol is None and self.port_number in self.https_ports:
                            built_url = "https://" + self.system_name
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1

                self.port_number = None
                self.protocol = None
                self.port_open = False

            elif tag == "port":
                if not self.only_ports and (self.protocol == None):
                    if (self.port_number is not None) and self.port_open and (self.system_name is not None):
                        if self.port_number in self.http_ports:
                            self.protocol = 'http'
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.port_number in self.https_ports:
                            self.protocol = 'https'
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                else:
                    if (self.port_number is not None) and self.port_open and (self.system_name is not None) and int(self.port_number) in self.only_ports:
                        if self.port_number in self.http_ports:
                            self.protocol = 'http'
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                        elif self.port_number in self.https_ports:
                            self.protocol = 'https'
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)
                                self.num_urls += 1
                self.port_number = None
                self.protocol = None
                self.port_open = False

            elif tag == "host":
                self.system_name = None

            elif tag == "nmaprun":
                if len(self.url_list) > 0:
                    with open(self.out_file, 'a') as temp_web:
                        for url in self.url_list:
                            temp_web.write(url + '\n')

        elif self.nessus:
            if tag == "plugin_output" and self.read_plugin_output:

                # Use plugin_output to differentiate between http and https.
                # "A web server is running on the remote host." indicates a http server
                # "A web server is running on this port through ..." indicates a https server
                if "A web server is running on this port through" in self.plugin_output:
                    self.protocol = "https"

                self.plugin_output = ""
                self.read_plugin_output = False
                self.analyze_plugin_output = False
            if tag == "ReportItem":
                if not self.only_ports:
                    if (self.system_name is not None) and (self.protocol is not None) and self.service_detection:
                        if self.protocol == "http" or self.protocol == "https":
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)

                else:
                    if (self.system_name is not None) and (self.protocol is not None) and self.service_detection and int(self.port_number) in self.only_ports:
                        if self.protocol == "http" or self.protocol == "https":
                            built_url = self.protocol + "://" + self.system_name + ":" + self.port_number
                            if built_url not in self.url_list:
                                self.url_list.append(built_url)

                self.port_number = None
                self.protocol = None
                self.port_open = False
                self.service_detection = False

            elif tag == "ReportHost":
                self.system_name = None

            elif tag == "NessusClientData_v2":
                if len(self.url_list) > 0:
                    with open(self.out_file, 'a') as temp_web:
                        for url in self.url_list:
                            temp_web.write(url + '\n')

    def characters(self, content):
        if self.read_plugin_output:
            self.plugin_output += content

def duplicate_check(cli_object):
    # This is used for checking for duplicate images
    # if it finds any, it removes them and uses a single image
    # reducing file size for output
    # dict = {sha1hash: [pic1, pic2]}
    hash_files = {}
    report_files = []

    # Use pathlib for cross-platform path handling
    output_dir = Path(cli_object.d)
    screens_pattern = str(output_dir / 'screens' / '*.png')
    
    for name in glob.glob(screens_pattern):
        with open(name, 'rb') as screenshot:
            pic_data = screenshot.read()
        md5_hash = hashlib.md5(pic_data).hexdigest()
        
        # Get relative path from output directory for storage
        name_path = Path(name)
        relative_path = name_path.relative_to(output_dir)
        relative_path_str = str(relative_path).replace('\\', '/')  # Normalize for HTML
        
        if md5_hash in hash_files:
            hash_files[md5_hash].append(relative_path_str)
        else:
            hash_files[md5_hash] = [relative_path_str]

    # Find HTML report files
    html_pattern = str(output_dir / '*.html')
    for html_file in glob.glob(html_pattern):
        report_files.append(html_file)

    # Track path replacements for database update
    path_replacements = {}  # {old_path: new_path}

    # Process duplicates
    for hex_value, file_dict in hash_files.items():
        total_files = len(file_dict)
        if total_files > 1:
            original_pic_name = file_dict[0]
            original_full_path = str(output_dir / original_pic_name.replace('/', os.sep))
            
            for num in range(1, total_files):
                next_filename = file_dict[num]
                duplicate_full_path = str(output_dir / next_filename.replace('/', os.sep))
                
                # Track the replacement for database update
                path_replacements[duplicate_full_path] = original_full_path
                
                # Update HTML report files
                for report_page in report_files:
                    with open(report_page, 'r') as report:
                        page_text = report.read()
                    page_text = page_text.replace(next_filename, original_pic_name)
                    with open(report_page, 'w') as report_out:
                        report_out.write(page_text)
                
                # remove the duplicate 
                duplicate_file_path = output_dir / next_filename.replace('/', os.sep)
                if duplicate_file_path.exists():
                    os.remove(duplicate_file_path)  # should probably use pathlib but this works
                
                # Update CSV file
                csv_file_path = output_dir / "Requests.csv"
                if csv_file_path.exists():
                    with open(csv_file_path, 'r') as csv_port_file:
                        csv_lines = csv_port_file.read()
                        if next_filename in csv_lines:
                            csv_lines = csv_lines.replace(next_filename, original_pic_name)
                    with open(csv_file_path, 'w') as csv_port_writer:
                        csv_port_writer.write(csv_lines)
    
    # Update database with new screenshot paths
    if path_replacements and hasattr(cli_object, 'db_path') and cli_object.db_path:
        try:
            _update_database_screenshot_paths(cli_object.db_path, path_replacements)
        except Exception as e:
            print(f"[!] Warning: Could not update database after duplicate removal: {e}")
    
    return


def _update_database_screenshot_paths(db_path, path_replacements):
    """
    Update screenshot paths in the database after duplicate removal.
    
    Args:
        db_path (str): Path to the SQLite database
        path_replacements (dict): Mapping of old paths to new paths
    """
    import pickle
    import sqlite3
    
    if not os.path.exists(db_path):
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    updated_count = 0
    
    try:
        # Update http table
        rows = c.execute("SELECT id, object FROM http").fetchall()
        for row in rows:
            obj = pickle.loads(row['object'])
            if hasattr(obj, 'screenshot_path') and obj.screenshot_path in path_replacements:
                old_path = obj.screenshot_path
                obj.screenshot_path = path_replacements[old_path]
                pobj = sqlite3.Binary(pickle.dumps(obj, protocol=2))
                c.execute("UPDATE http SET object=? WHERE id=?", (pobj, row['id']))
                updated_count += 1
        
        # Update ua table if it exists
        try:
            ua_rows = c.execute("SELECT id, object FROM ua").fetchall()
            for row in ua_rows:
                obj = pickle.loads(row['object'])
                if hasattr(obj, 'screenshot_path') and obj.screenshot_path in path_replacements:
                    old_path = obj.screenshot_path
                    obj.screenshot_path = path_replacements[old_path]
                    pobj = sqlite3.Binary(pickle.dumps(obj, protocol=2))
                    c.execute("UPDATE ua SET object=? WHERE id=?", (pobj, row['id']))
                    updated_count += 1
        except sqlite3.OperationalError:
            pass  # ua table might not exist
        
        conn.commit()
        
        if updated_count > 0:
            print(f"[*] Updated {updated_count} screenshot paths in database after duplicate removal")
    
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def resolve_host(system):
    parsed = urlparse(system)
    system = parsed.path if parsed.netloc == '' else parsed.netloc
    try:
        toresolve = IPAddress(system)
        resolved = socket.gethostbyaddr(str(toresolve))[0]
        return resolved
    except AddrFormatError:
        pass
    except socket.herror:
        return 'Unknown'

    try:
        resolved = socket.gethostbyname(system)
        return resolved
    except socket.gaierror:
        return 'Unknown'


def find_file_name():
    file_not_found = True
    file_name = "parsed_xml"
    counter = 0
    first_time = True
    while file_not_found:
        if first_time:
            if not os.path.isfile(file_name + ".txt"):
                file_not_found = False
            else:
                counter += 1
                first_time = False
        else:
            if not os.path.isfile(file_name + str(counter) + ".txt"):
                file_not_found = False
            else:
                counter += 1
    if first_time:
        return file_name + ".txt"
    else:
        return file_name + str(counter) + ".txt"


def textfile_parser(file_to_parse, cli_obj):
    urls = []
    openports = {}
    complete_urls = []
    validation_errors = []

    try:
        # Open the URL file and read all URLs, and reading again to catch
        # total number of websites
        with open(file_to_parse) as f:
            all_urls = [url for url in f if url.strip()]

        # Validate URLs if validation is enabled
        if hasattr(cli_obj, 'skip_validation') and not cli_obj.skip_validation:
            print("[*] Validating URLs...")
            valid_count = 0
            for url in all_urls:
                url = url.strip()
                is_valid, error, normalized = validate_url(url, require_scheme=False)
                if not is_valid and error != "Invalid scheme" and error != "No host specified in URL":
                    validation_errors.append(f"  - {url}: {error}")
                else:
                    valid_count += 1
            
            if validation_errors:
                print(f"[!] Found {len(validation_errors)} invalid URLs:")
                for error in validation_errors[:10]:  # Show first 10 errors
                    print(error)
                if len(validation_errors) > 10:
                    print(f"  ... and {len(validation_errors) - 10} more")
                print(f"[*] Proceeding with {valid_count} valid URLs")

        # else:
        for line in all_urls:
            line = line.strip()

            # Account for odd case schemes and fix to lowercase for matching
            scheme = urlparse(line)[0]
            if scheme == 'http':
                line = scheme + '://' + line[7:]
            elif scheme == 'https':
                line = scheme + '://' + line[8:]

            if not cli_obj.only_ports:
                if scheme == 'http' or scheme == 'https':
                    urls.append(line)
                else:
                    if cli_obj.web:
                        if cli_obj.prepend_https:
                            urls.append("http://" + line)
                            urls.append("https://" + line)
                        else:
                            urls.append(line)
            else:
                if scheme == 'http' or scheme == 'https':
                    for port in cli_obj.only_ports:
                        urls.append(line + ':' + str(port))
                else:

                    if cli_obj.web:
                        if cli_obj.prepend_https:
                            for port in cli_obj.only_ports:
                                urls.append("http://" + line + ':' + str(port))
                                urls.append("https://" + line + ':' + str(port))
                        else:
                            for port in cli_obj.only_ports:
                                urls.append(line + ':' + str(port))
        
        # Look at URLs and make CSV output of open ports unless already parsed from XML output
        # This parses the text file
        for url_again in all_urls:
            url_again = url_again.strip()
            complete_urls.append(url_again)
            if url_again.count(":") == 2:
                char = url_again.split(":")[2].split("/")[0]
                check = char.isdigit()
                if check == True:                   
                    try:
                        port_number = int(url_again.split(":")[2].split("/")[0])
                    except ValueError:
                        print("ERROR: You potentially provided an mal-formed URL!")
                        print("ERROR: URL is - " + url_again)
                        sys.exit()
                    hostname_again = url_again.split(":")[0] + ":" + url_again.split(":")[1] + ":" + url_again.split(":")[2]
                    if port_number in openports:
                        openports[port_number] += "," + hostname_again
                    else:
                        openports[port_number] = hostname_again
            else:
                if "https://" in url_again:
                    if 443 in openports:
                        openports[443] += "," + url_again
                    else:
                        openports[443] = url_again
                else:
                    if 80 in openports:
                        openports[80] += "," + url_again
                    else:
                        openports[80] = url_again
            if ' ' in url_again.strip():
                    print("ERROR: You potentially provided an mal-formed URL!")
                    print("ERROR: URL is - " + url_again)
                    sys.exit()

        # Start prepping to write out the CSV
        csv_data = "URL"
        ordered_ports = sorted(openports.keys())
        for opn_prt in ordered_ports:
            csv_data += "," + str(opn_prt)

        # Create the CSV data row by row
        for ind_system in complete_urls:
            # add new line and add hostname
            csv_data += '\n'
            csv_data += ind_system + ","
            for test_for_port in ordered_ports:
                if ind_system in openports[test_for_port]:
                    csv_data += "X,"
                else:
                    csv_data += ","

        # Write out CSV
        with open(cli_obj.d + "/open_ports.csv", 'w') as csv_file_out:
            csv_file_out.write(csv_data)

        return urls

    except IOError:
        if cli_obj.x is not None:
            print("ERROR: The XML file you provided does not have any active web servers!")
        else:
            print("ERROR: You didn't give me a valid file name! I need a valid file containing URLs!")
        sys.exit()


def target_creator(command_line_object):
    """Parses input files to create target lists

    Args:
        command_line_object (ArgumentParser): Command Line Arguments

    Returns:
        List: URLs detected for http
    """

    if command_line_object.x is not None:

        # Get a file name for the parsed results
        parsed_file_name = find_file_name()

        # Create parser
        parser = xml.sax.make_parser()

        # Turn off namespaces
        parser.setFeature(xml.sax.handler.feature_namespaces, 0)
        # Override the parser
        Handler = XML_Parser(parsed_file_name, command_line_object)
        parser.setContentHandler(Handler)
        # Parse the XML

        # Check if path exists
        if os.path.exists(command_line_object.x):
            # Check if it is a file
            if os.path.isfile(command_line_object.x):
                parser.parse(command_line_object.x)
            else:
                print("ERROR: The path you provided does not point to a file!")
                sys.exit()
        else:
            print("ERROR: The path you provided does not exist!")
            sys.exit()

        out_urls = textfile_parser(
            parsed_file_name, command_line_object)
        return out_urls

    elif command_line_object.f is not None:

        file_urls = textfile_parser(
            command_line_object.f, command_line_object)
        return file_urls

    elif command_line_object.single is not None:
        # Handle single URL input
        return [command_line_object.single]
    
    elif hasattr(command_line_object, 'scan') and command_line_object.scan is not None:
        # Handle IP/network scan mode
        from modules.port_scanner import discover_web_services, PORT_PRESETS
        
        print("[*] IP/Network scan mode enabled")
        print(f"[*] Targets: {', '.join(command_line_object.scan)}")
        
        # Determine ports
        if hasattr(command_line_object, 'custom_ports') and command_line_object.custom_ports:
            try:
                ports = [int(p.strip()) for p in command_line_object.custom_ports.split(',')]
                print(f"[*] Using custom ports: {ports}")
            except ValueError:
                print("[!] Invalid custom ports format. Using preset.")
                ports = None
        else:
            ports = None
        
        # Get scan parameters
        preset = getattr(command_line_object, 'scan_ports', 'medium')
        timeout = getattr(command_line_object, 'scan_timeout', 2.0)
        threads = getattr(command_line_object, 'scan_threads', 100)
        user_agent = getattr(command_line_object, 'user_agent', None)
        
        if ports is None:
            print(f"[*] Using port preset: {preset} ({len(PORT_PRESETS.get(preset, []))} ports)")
        
        # Run discovery
        discovered_urls = discover_web_services(
            targets=command_line_object.scan,
            ports=ports,
            preset=preset,
            timeout=timeout,
            threads=threads,
            user_agent=user_agent
        )
        
        if not discovered_urls:
            print("[!] No web services discovered. Exiting.")
            sys.exit(1)
        
        print(f"\n[+] Discovered {len(discovered_urls)} web service(s)")
        print("[*] Proceeding with EyeWitness analysis...\n")
        
        return discovered_urls
    
    # Return empty list if no input provided
    return []

def title_screen(cli_parsed):
    """Prints the title screen for EyeWitness
    """
    if not cli_parsed.no_clear:
        from modules.platform_utils import platform_mgr
        platform_mgr.clear_screen()

    print("#" * 80)
    print("#" + " " * 34 + "EyeWitness" + " " * 34 + "#")
    print("#" * 80)
    print("#" + " " * 25 + "Plaintext Security Edition" + " " * 27 + "#")
    print("#" * 80 + "\n")

    python_info = sys.version_info
    if python_info[0] != 3:
        print("[*] Error: Your version of python is not supported!")
        print("[*] Error: Please install Python 3.X.X")
        sys.exit()
    else:
        pass
    return


def strip_nonalphanum(string):
    """Strips any non-alphanumeric characters in the ascii range from a string

    Args:
        string (String): String to strip

    Returns:
        String: String stripped of all non-alphanumeric characters
    """
    return ''.join(c for c in string if c.isalnum())


def do_jitter(cli_parsed):
    """Jitters between URLs to add delay/randomness

    Args:
        cli_parsed (ArgumentParser): CLI Object

    Returns:
        TYPE: Description
    """
    if cli_parsed.jitter != 0:
        sleep_value = random.randint(0, 30)
        sleep_value = sleep_value * .01
        sleep_value = 1 - sleep_value
        sleep_value = sleep_value * cli_parsed.jitter
        print("[*] Sleeping for " + str(sleep_value) + " seconds..")
        try:
            time.sleep(sleep_value)
        except KeyboardInterrupt:
            pass

def do_delay(cli_parsed):
    """Delay between the opening of the navigator and taking the screenshot

    Args:
        cli_parsed (ArgumentParser): CLI Object

    Returns:
        TYPE: Description
    """
    if cli_parsed.delay != 0:
        sleep_value = cli_parsed.delay
        print("[*] Sleeping for " + str(sleep_value) + " seconds before taking the screenshot")
        try:
            time.sleep(sleep_value)
        except KeyboardInterrupt:
            pass

def create_folders_css(cli_parsed):
    # Create output directories
    # Note: Static CSS/JS files are no longer copied since the webapp handles all UI rendering

    # Create output directories using pathlib for cross-platform compatibility
    output_dir = Path(cli_parsed.d)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    output_dir.mkdir(parents=True)
    (output_dir / 'screens').mkdir()
    (output_dir / 'source').mkdir()
    
    # Note: Static CSS/JS files (bootstrap, jquery, style.css) are no longer copied
    # All UI rendering is now handled by the webapp at /webapp
    # If you need static reports, uncomment the following lines:
    # local_path = Path(__file__).parent
    # bin_path = local_path.parent / 'bin'
    # shutil.copy2(bin_path / 'jquery-3.7.1.min.js', output_dir)
    # shutil.copy2(bin_path / 'bootstrap.min.css', output_dir)
    # shutil.copy2(bin_path / 'bootstrap.min.js', output_dir)
    # shutil.copy2(bin_path / 'style.css', output_dir)



def auto_categorize(http_object):
    """
    Automatically categorize a page based on technologies, AI info, URL patterns, and headers.
    
    Categories follow the new standardized system:
    - storage: Storage systems (IBM Storwize, Quantum DXi, QNAP, Synology)
    - network_device: Switches, routers, APs, firewalls (Cisco, Ubiquiti, WatchGuard)
    - network_management: Network management systems (UNMS, UniFi Controller)
    - printer: Printers and MFPs
    - voip: VoIP phones (Grandstream, Yealink)
    - video_conference: Video/presentation systems (Polycom, Crestron)
    - idrac: Server management (Dell iDRAC, HP iLO)
    - monitoring: Monitoring systems (Grafana, Nagios, Zabbix)
    - itsm: IT Service Management (ManageEngine ServiceDesk)
    - iot: IoT devices
    - business_app: Business applications
    - webserver: Web servers (IIS, Apache, nginx)
    - appserver: Application servers (JBoss, Tomcat)
    - api: API documentation (Swagger)
    - error_page: Error pages (401, 403, 404)
    - virtualization: Virtualization platforms
    - devops: Development Operations
    - dataops: Data Operations
    - comms: Communications
    
    Args:
        http_object (HTTPTableObject): Object representing a URL
        
    Returns:
        str: Category name or None if no match found
    """
    # Technology-based categorization
    technologies = getattr(http_object, 'technologies', None) or []
    tech_lower = [t.lower() for t in technologies]
    
    # Virtualization
    if any(t in tech_lower for t in ['vmware', 'vsphere', 'esxi', 'vcenter', 'vrealize']):
        return 'virtualization'
    
    # Network devices
    if any(t in tech_lower for t in ['cisco', 'meraki', 'ubiquiti', 'ruckus', 'aruba', 'fortinet', 'watchguard']):
        return 'network_device'
    
    # Storage
    if any(t in tech_lower for t in ['synology', 'qnap', 'netapp', 'emc', 'dell storage', 'pure storage', 'ibm storwize', 'quantum']):
        return 'storage'
    
    # Monitoring
    if any(t in tech_lower for t in ['grafana', 'prometheus', 'nagios', 'zabbix', 'kibana']):
        return 'monitoring'
    
    # Security/SecOps
    if any(t in tech_lower for t in ['splunk', 'nessus', 'alienvault']):
        return 'secops'
    
    # DevOps
    if any(t in tech_lower for t in ['jenkins', 'gitlab', 'bitbucket', 'docker', 'kubernetes', 'ansible']):
        return 'devops'
    
    # Application Servers
    if any(t in tech_lower for t in ['tomcat', 'jboss', 'wildfly', 'weblogic', 'websphere']):
        return 'appserver'
    
    # Web Servers
    if any(t in tech_lower for t in ['apache', 'nginx', 'iis']):
        return 'webserver'
    
    # Data Operations
    if any(t in tech_lower for t in ['mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch']):
        return 'dataops'
    
    # Communications
    if any(t in tech_lower for t in ['outlook', 'owa', 'exchange', 'lync', 'skype']):
        return 'comms'
    
    # AI-based categorization (if available)
    ai_info = getattr(http_object, 'ai_application_info', None)
    if ai_info and isinstance(ai_info, dict):
        app_name = ai_info.get('application_name', '').lower()
        app_type = ai_info.get('application_type', '').lower()
        
        # Network devices
        if any(x in app_name for x in ['cisco', 'switch', 'router', 'firewall', 'meraki', 'ubiquiti', 'edgeswitch', 'ruckus', 'aruba', 'fortinet', 'palo alto', 'watchguard']):
            return 'network_device'
        
        # Network management
        if any(x in app_name for x in ['unms', 'unifi', 'network controller', 'aircontrol']):
            return 'network_management'
        
        # Storage
        if any(x in app_name for x in ['synology', 'qnap', 'netapp', 'storwize', 'quantum', 'dxi', 'nas', 'san']):
            return 'storage'
        
        # Virtualization
        if any(x in app_name for x in ['vmware', 'vsphere', 'esxi', 'vcenter', 'virtual', 'hypervisor']):
            return 'virtualization'
        
        # Monitoring
        if any(x in app_name for x in ['grafana', 'prometheus', 'nagios', 'zabbix', 'gridvis']):
            return 'monitoring'
        
        # Security
        if any(x in app_name for x in ['splunk', 'nessus', 'security']):
            return 'secops'
        
        # ITSM
        if any(x in app_name for x in ['servicedesk', 'service desk', 'manageengine', 'servicenow']):
            return 'itsm'
        
        # VoIP
        if any(x in app_name for x in ['grandstream', 'yealink', 'cisco ip phone', 'mitel', 'grp26', 'gxp']):
            return 'voip'
        
        # Video Conference
        if any(x in app_name for x in ['polycom pano', 'crestron', 'airmedia', 'clickshare']):
            return 'video_conference'
        
        # Printers
        if any(x in app_name for x in ['printer', 'laserjet', 'xerox', 'canon', 'brother', 'lexmark', 'ricoh', 'epson', 'pm43', 'pm4', 'pd45', 'honeywell', 'kyocera', 'hypas']):
            return 'printer'
        
        # iDRAC/Management
        if any(x in app_name for x in ['idrac', 'ilo', 'ipmi', 'bmc']):
            return 'idrac'
        
        # IoT
        if any(x in app_name for x in ['identec', 'i-port', 'iot']):
            return 'iot'
        
        # API
        if any(x in app_name for x in ['swagger', 'openapi', 'api doc']):
            return 'api'
    
    # URL pattern-based categorization
    url = str(getattr(http_object, 'remote_system', '') or '').lower()
    
    # Port-based hints
    if ':8443' in url or ':9443' in url:
        if 'vmware' in url or 'vsphere' in url:
            return 'virtualization'
        return 'infrastructure'
    
    if ':8080' in url or ':8000' in url or ':8888' in url:
        return 'appserver'
    
    # Path-based hints
    if '/manager' in url or '/admin' in url or '/console' in url:
        return 'infrastructure'
    
    if '/jenkins' in url:
        return 'devops'
    
    if '/grafana' in url or '/prometheus' in url:
        return 'monitoring'
    
    if '/swagger' in url or '/api-docs' in url:
        return 'api'
    
    # Header-based categorization
    headers = getattr(http_object, 'http_headers', None) or {}
    server = headers.get('Server', '').lower()
    
    if 'vmware' in server or 'esxi' in server:
        return 'virtualization'
    
    if 'cisco' in server:
        return 'network_device'
    
    if 'apache' in server:
        return 'webserver'
    
    if 'nginx' in server:
        return 'webserver'
    
    if 'iis' in server or 'microsoft' in server:
        return 'webserver'
    
    # Page title pattern matching
    page_title = str(getattr(http_object, 'page_title', '') or '').lower()
    
    # Error pages
    if any(x in page_title for x in ['401', '403', '404', 'not found', 'forbidden', 'unauthorized', 'runtime error', 'service unavailable']):
        return 'error_page'
    
    # Network devices
    if any(x in page_title for x in ['cisco', 'switch', 'router', 'firewall', 'meraki', 'ubiquiti', 'edgeswitch', 'ruckus', 'aruba', 'fortinet', 'palo alto', 'watchguard', 'sonicwall']):
        return 'network_device'
    
    # Network management
    if any(x in page_title for x in ['unms', 'unifi network', 'aircontrol']):
        return 'network_management'
    
    # Virtualization
    if any(x in page_title for x in ['vmware', 'vsphere', 'esxi', 'vcenter', 'vrealize']):
        return 'virtualization'
    
    # Storage
    if any(x in page_title for x in ['synology', 'qnap', 'netapp', 'storwize', 'quantum dxi', 'terastation']):
        return 'storage'
    
    # Monitoring
    if any(x in page_title for x in ['grafana', 'prometheus', 'nagios', 'zabbix', 'gridvis']):
        return 'monitoring'
    
    # Security
    if any(x in page_title for x in ['splunk', 'nessus', 'alienvault']):
        return 'secops'
    
    # VoIP
    if any(x in page_title for x in ['grandstream', 'grp26', 'gxp', 'yealink', 'cisco ip', 'mitel']):
        return 'voip'
    
    # Video Conference
    if any(x in page_title for x in ['polycom', 'crestron', 'airmedia']):
        return 'video_conference'
    
    # Printers
    if any(x in page_title for x in ['printer', 'laserjet', 'xerox', 'canon', 'brother', 'lexmark', 'hp color', 'hp laserjet', 'ricoh', 'epson', 'rnp', 'pm43', 'pm4', 'pd45', 'honeywell', 'kyocera', 'hypas']):
        return 'printer'
    
    # Web servers
    if any(x in page_title for x in ['iis windows', 'apache2', 'nginx', 'welcome to nginx']):
        return 'webserver'
    
    # Application servers
    if any(x in page_title for x in ['jboss', 'tomcat', 'wildfly', 'weblogic']):
        return 'appserver'
    
    # API documentation
    if any(x in page_title for x in ['swagger', 'api doc']):
        return 'api'
    
    # ITSM
    if any(x in page_title for x in ['servicedesk', 'manageengine']):
        return 'itsm'
    
    # Default category based on application type from AI
    if ai_info and isinstance(ai_info, dict):
        app_type = ai_info.get('application_type', '').lower()
        if 'network' in app_type or 'router' in app_type or 'switch' in app_type:
            return 'network_device'
        if 'storage' in app_type or 'nas' in app_type:
            return 'storage'
        if 'virtualization' in app_type or 'hypervisor' in app_type:
            return 'virtualization'
        if 'printer' in app_type:
            return 'printer'
        if 'monitoring' in app_type:
            return 'monitoring'
        if 'security' in app_type:
            return 'secops'
        if 'management' in app_type:
            return 'infrastructure'
    
    return None


def default_creds_category(http_object):
    """Adds default credentials or categories to a http_object if either exist

    Args:
        http_object (HTTPTableObject): Object representing a URL

    Returns:
        HTTPTableObject: Object with creds/category added
    """
    # Preserve existing credentials - only update if we find new ones
    existing_creds = http_object.default_creds
    existing_category = http_object.category
    
    # Reset category to allow re-categorization, but preserve creds
    http_object.category = None
    try:
        # Use pathlib for cross-platform path handling
        module_dir = Path(__file__).parent
        sig_json_path = module_dir.parent / 'signatures.json'
        
        # Use JSON-based signature system only
        # If signatures.json doesn't exist, it will be created when credentials are discovered
        if not sig_json_path.exists():
            return http_object
        
        try:
            from modules.signature_manager import SignatureManager
            sig_manager = SignatureManager()
            
            if http_object.source_code is not None:
                # Find matching signature
                html_content = http_object.source_code
                if isinstance(html_content, bytes):
                    html_content = html_content.decode('utf-8', errors='ignore')
                
                matching_sig = sig_manager.find_matching_signature(html_content)
                
                if matching_sig:
                    # Get application name from signature
                    app_name = matching_sig.get('application_name', 'Unknown')
                    if app_name and app_name != 'Unknown':
                        # Store app name for later use (if not already set by AI)
                        if not hasattr(http_object, 'ai_application_info') or not http_object.ai_application_info:
                            if not hasattr(http_object, '_signature_app_name'):
                                http_object._signature_app_name = app_name
                    
                    # Get working credentials
                    working_creds = sig_manager.get_working_credentials(
                        matching_sig.get('signature_patterns', [])
                    )
                    
                    if working_creds:
                        # Format: AppName / user1:pass1 or user2:pass2
                        cred_strings = []
                        for cred in working_creds:
                            username = cred.get('username', '')
                            password = cred.get('password', '')
                            # Note: password can be empty (common for printers like Ricoh)
                            if username:
                                cred_strings.append(f"{username}:{password}")
                        
                        if cred_strings:
                            cred_desc = f"{app_name} / {' or '.join(cred_strings)}"
                            http_object.default_creds = cred_desc
                            print('  [+] Signature Match: ' + cred_desc)
                    
                    # Set category from signature (high priority)
                    category = matching_sig.get('category')
                    if category:
                        http_object.category = category
                        print('  [+] Category from signature: ' + http_object.category)
                    else:
                        # If signature has no category, try auto_categorize
                        auto_category = auto_categorize(http_object)
                        if auto_category:
                            http_object.category = auto_category
                            print(f'  [+] Auto-categorized (no category in signature): {http_object.category}')
        except Exception as e:
            print(f'  [!] Error using JSON signatures: {e}')

        # Check page title for error categories (high priority)
        if http_object.page_title is not None:
            if (type(http_object.page_title)) == bytes:
                if '403 Forbidden'.encode() in http_object.page_title or '401 Unauthorized'.encode() in http_object.page_title:
                    http_object.category = 'unauth'
                    print('  [+] Category: ' + http_object.category)
                if ('Index of /'.encode() in http_object.page_title or
                        'Directory Listing For /'.encode() in http_object.page_title or
                        'Directory of /'.encode() in http_object.page_title):
                    http_object.category = 'dirlist'
                    print('  [+] Category: ' + http_object.category)
                if '404 Not Found'.encode() in http_object.page_title:
                    http_object.category = 'notfound'
                    print('  [+] Category: ' + http_object.category)
            else:
                if '403 Forbidden' in http_object.page_title or '401 Unauthorized' in http_object.page_title:
                    http_object.category = 'unauth'
                if ('Index of /' in http_object.page_title or
                        'Directory Listing For /' in http_object.page_title or
                        'Directory of /' in http_object.page_title):
                    http_object.category = 'dirlist'
                    print('  [+] Category: ' + http_object.category)
                if '404 Not Found' in http_object.page_title:
                    http_object.category = 'notfound'
                    print('  [+] Category: ' + http_object.category)

        # If category still not set, try automatic categorization
        if http_object.category is None:
            auto_category = auto_categorize(http_object)
            if auto_category:
                http_object.category = auto_category
                print(f'  [+] Auto-categorized: {http_object.category}')
        
        # If no new credentials were found but we had existing ones, restore them
        if http_object.default_creds is None and existing_creds:
            http_object.default_creds = existing_creds

        return http_object
    except IOError:
        print("[*] WARNING: Credentials file not in the same directory"
              " as EyeWitness")
        print('[*] Skipping credential check')
        return http_object


def print_summary_table(results):
    """Print a summary table of scan results
    
    Args:
        results: List of HTTPTableObject or similar objects with scan results
    """
    if not results:
        print("\n[*] No results to display")
        return
    
    # ANSI color codes
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Fixed column widths (without ANSI codes)
    URL_W = 25
    APP_W = 20
    TEST_W = 6
    CREDS_W = 25
    SCREEN_W = 10
    
    # Header
    total_width = URL_W + APP_W + TEST_W + CREDS_W + SCREEN_W + 16  # 16 for separators
    print(f"\n{'=' * total_width}")
    print(f"{BOLD}SCAN SUMMARY{RESET}")
    print(f"{'=' * total_width}")
    header = f"{'URL':<{URL_W}} | {'Application':<{APP_W}} | {'Tested':<{TEST_W}} | {'Default Creds':<{CREDS_W}} | {'Screenshot':<{SCREEN_W}}"
    print(f"{BOLD}{header}{RESET}")
    print(f"{'-' * total_width}")
    
    # Data rows
    creds_found_count = 0
    pwned_count = 0
    
    for r in results:
        # URL column
        url = str(getattr(r, 'remote_system', 'N/A'))[:URL_W]
        
        # Get application name - PRIORITY ORDER:
        # 1. AI identification (ai_application_info)
        # 2. Signature app name (from default_creds)
        # 3. Page title
        # 4. Category
        app_name = None
        
        # 1. Try AI identification first (highest priority)
        ai_info = getattr(r, 'ai_application_info', None)
        if ai_info and isinstance(ai_info, dict):
            app_name = ai_info.get('application_name')
        
        # 2. Try to extract from default_creds (e.g., "KnowledgeSync / admin:password")
        default_creds = getattr(r, 'default_creds', None)
        if not app_name and default_creds:
            if ' / ' in default_creds:
                app_name = default_creds.split(' / ')[0].strip()
            elif '|' in default_creds:
                parts = default_creds.split('|')
                if len(parts) > 1:
                    app_name = parts[1].split()[0] if parts[1].split() else None
        
        # 3. Try page_title if no app name found
        if not app_name:
            page_title = getattr(r, 'page_title', None)
            if page_title and str(page_title) != 'None':
                app_name = str(page_title)[:APP_W]
        
        # 4. Use category as fallback
        if not app_name:
            category = getattr(r, 'category', None)
            if category:
                app_name = category.capitalize()
        
        app_name = (app_name or '-')[:APP_W]
        
        # Check credential test results
        cred_test_result = getattr(r, 'credential_test_result', None)
        was_tested = False
        creds_worked = False
        successful_creds = []
        
        if cred_test_result and isinstance(cred_test_result, dict):
            was_tested = cred_test_result.get('tested', False)
            successful_creds = cred_test_result.get('successful_credentials', [])
            if successful_creds:
                creds_worked = True
        
        # Determine what credentials to display
        creds_display = None
        
        # If credentials worked, show ONLY the working credential
        if creds_worked and successful_creds:
            first_success = successful_creds[0]
            if isinstance(first_success, dict):
                username = first_success.get('username', '')
                password = first_success.get('password', '')
                creds_display = f"{username}:{password}"[:CREDS_W]
        # Otherwise show default creds from signature
        elif default_creds:
            import re
            
            # Extract credentials part - handle "AppName / user:pass" format
            if ' / ' in str(default_creds):
                creds_part = str(default_creds).split(' / ')[-1]
            else:
                creds_part = str(default_creds)
            
            # Extract just the first credential (before "or", commas, etc.)
            # Handle both formats: user:pass and user/pass
            # Try colon format first: "user:pass" or "superadmin:passw0rd"
            cred_match = re.search(r'\b([A-Za-z][A-Za-z0-9_]{2,30}):([A-Za-z0-9_!@#$%^&*+\-]{1,50})\b', creds_part)
            if cred_match:
                username, password = cred_match.groups()
                creds_display = f"{username}:{password}"[:CREDS_W]
            else:
                # Try slash format: "user/pass" -> convert to "user:pass"
                cred_match = re.search(r'\b([A-Za-z][A-Za-z0-9_]{2,30})/([A-Za-z0-9_!@#$%^&*+\-]{1,50})\b', creds_part)
                if cred_match:
                    username, password = cred_match.groups()
                    creds_display = f"{username}:{password}"[:CREDS_W]
                else:
                    # Try user: (without password)
                    cred_match = re.search(r'\b([A-Za-z][A-Za-z0-9_]{2,30}):\s*(?=\s|$|or|,|;|\(|\[)', creds_part)
                    if cred_match:
                        username = cred_match.group(1)
                        creds_display = f"{username}:"[:CREDS_W]
                    else:
                        # Try to find any credential pattern in the text
                        # Look for patterns like "password = passw0rd" or "superuser password = passw0rd"
                        pass_match = re.search(r'(?:password|pass|pwd)\s*[=:]\s*([A-Za-z0-9_!@#$%^&*+\-]{1,50})', creds_part, re.IGNORECASE)
                        user_match = re.search(r'\b(superuser|superadmin|admin|root|administrator|user)\b', creds_part, re.IGNORECASE)
                        if pass_match and user_match:
                            username = user_match.group(1)
                            password = pass_match.group(1)
                            creds_display = f"{username}:{password}"[:CREDS_W]
                        else:
                            # Just take first reasonable credential-like pattern
                            creds_display = creds_part.split()[0][:CREDS_W] if creds_part.split() else creds_part[:CREDS_W]
        # Or AI-found credentials
        elif cred_test_result and cred_test_result.get('credentials_tested', 0) > 0:
            ai_creds = getattr(r, 'ai_credentials_found', None)
            if ai_creds and len(ai_creds) > 0:
                first_cred = ai_creds[0]
                if isinstance(first_cred, dict):
                    creds_display = f"{first_cred.get('username', '')}:{first_cred.get('password', '')}"[:CREDS_W]
        
        # Build display strings
        if creds_display:
            creds_found_count += 1
            if creds_worked:
                pwned_count += 1
        
        # Format with colors (print separately to avoid alignment issues)
        has_screenshot = bool(getattr(r, 'screenshot_path', None)) and not getattr(r, 'error_state', None)
        
        # Build row without colors first for alignment
        tested_text = "YES" if was_tested else "NO"
        creds_text = creds_display if creds_display else "None"
        screen_text = "YES" if has_screenshot else "NO"
        pwned_text = " (Pwned!)" if creds_worked else ""
        
        # Print with colors
        print(f"{url:<{URL_W}} | {CYAN}{app_name:<{APP_W}}{RESET} | ", end='')
        
        if was_tested:
            print(f"{GREEN}{tested_text:<{TEST_W}}{RESET} | ", end='')
        else:
            print(f"{YELLOW}{tested_text:<{TEST_W}}{RESET} | ", end='')
        
        if creds_worked:
            print(f"{WHITE}{creds_text}{RESET}{YELLOW}{pwned_text}{RESET}", end='')
            # Pad to fill column width
            padding = CREDS_W - len(creds_text) - len(pwned_text)
            if padding > 0:
                print(" " * padding, end='')
        elif creds_display:
            print(f"{creds_text:<{CREDS_W}}", end='')  # Sin color, usa el default
        else:
            print(f"{YELLOW}{creds_text:<{CREDS_W}}{RESET}", end='')
        
        print(" | ", end='')
        
        if has_screenshot:
            print(f"{GREEN}{screen_text}{RESET}")
        else:
            print(f"{RED}{screen_text}{RESET}")
    
    print(f"{'=' * total_width}")
    summary_msg = f"{BOLD}Total: {len(results)} URLs | {creds_found_count} with default credentials found"
    if pwned_count > 0:
        summary_msg += f" | {YELLOW}{pwned_count} Pwned!{RESET}"
    else:
        summary_msg += f"{RESET}"
    print(summary_msg + "\n")


def open_file_input(cli_parsed, report_type='report'):
    """Prompt user to open generated report file
    
    Args:
        cli_parsed: CLI arguments object with 'd' attribute for directory
        report_type: Type of report to open ('report' or 'search')
    
    Returns:
        bool: True if user wants to open report, False otherwise
    """
    if report_type == 'search':
        pattern = 'search.html'
    else:
        pattern = '*report.html'
    
    files = glob.glob(os.path.join(cli_parsed.d, pattern))
    if len(files) > 0:
        print('Would you like to open the report now? [Y/n]', end=' ')
        while True:
            try:
                response = input().lower()
                if response == "":
                    return True
                else:
                    return strtobool(response)
            except ValueError:
                print('Please respond with y or n', end=' ')
    else:
        print('[*] No report files found to open, perhaps no hosts were successful')
        return False


def strtobool(value, raise_exc=False):

    str2b_true = {'yes', 'true', 't', 'y', '1'}
    str2b_false = {'no', 'false', 'f', 'n', '0'}

    if isinstance(value, str) or sys.version_info[0] < 3 and isinstance(value, basestring):
        value = value.lower()
        if value in str2b_true:
            return True
        if value in str2b_false:
            return False

    if raise_exc:
        raise ValueError('Expected "%s"' % '", "'.join(str2b_true | str2b_false))
    return None

# Waiting for approval to add web scraper for class dates. 
# Makes zero sense to hard code these as an advert people would need to pull down
# the latest version of the code everytime a new class is offered
# get_class_info() method goes here. 

def class_info():
    # Original EyeWitness by Red Siege - https://github.com/RedSiege/EyeWitness
    pass


def open_report_file(filepath):
    """
    Open a report file using the best available method.
    Handles WSL, Linux, macOS, and Windows.
    
    Args:
        filepath: Path to the file to open
        
    Returns:
        bool: True if file was opened successfully
    """
    import subprocess
    import webbrowser
    
    # Convert to absolute path
    filepath = os.path.abspath(filepath)
    
    # Check if running in WSL
    is_wsl = False
    win_path = None
    try:
        with open('/proc/version', 'r') as f:
            if 'microsoft' in f.read().lower():
                is_wsl = True
    except:
        pass
    
    # Get Windows path if in WSL
    if is_wsl:
        try:
            result = subprocess.run(
                ['wslpath', '-w', filepath],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                win_path = result.stdout.strip()
        except:
            pass
    
    # Try different methods in order of preference
    methods = []
    
    if is_wsl and win_path:
        methods.append((['explorer.exe', win_path], 'Windows Explorer'))
        methods.append((['wslview', filepath], 'wslview'))
        methods.append((['cmd.exe', '/c', 'start', '', win_path], 'cmd.exe start'))
    
    # Standard methods
    if platform.system() == 'Darwin':
        methods.append((['open', filepath], 'macOS open'))
    elif platform.system() == 'Linux' and not is_wsl:
        methods.append((['xdg-open', filepath], 'xdg-open'))
    
    # Fallback to Python webbrowser
    methods.append((None, 'webbrowser'))
    
    opened = False
    for method, name in methods:
        try:
            if method is None:
                # Use Python webbrowser module
                if webbrowser.open('file://' + filepath):
                    opened = True
                    break
            else:
                # Use subprocess
                result = subprocess.run(
                    method,
                    capture_output=True,
                    timeout=5
                )
                if result.returncode == 0:
                    opened = True
                    break
        except Exception as e:
            continue
    
    # Always show the path for convenience
    if is_wsl and win_path:
        print(f"\n[*] Report path (Windows): {win_path}")
    else:
        print(f"\n[*] Report path: {filepath}")
    
    if not opened:
        print(f"[!] Could not open automatically. Please open manually.")
    
    return opened


def generate_simple_report(results, output_dir):
    """
    Generate a simple HTML report with just the summary table.
    This is optimized for web application viewing where full reports are not needed.
    
    Args:
        results: List of HTTPTableObject results
        output_dir: Directory to write the report
    """
    import os
    import html as html_module
    from urllib.parse import urlparse
    
    # ANSI color codes (not used in HTML but for consistency)
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    
    # Count results
    total_urls = len(results)
    creds_found_count = sum(1 for obj in results if obj.default_creds)
    pwned_count = sum(1 for obj in results if obj.credential_test_result and 
                     obj.credential_test_result.get('successful_credentials'))
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EyeWitness Scan Summary</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
            color: #333;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .stat-card {{
            flex: 1;
            min-width: 200px;
            padding: 20px;
            border-radius: 6px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}
        .stat-card.success {{
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
        }}
        .stat-card.warning {{
            background: linear-gradient(135deg, #f2994a 0%, #f2c94c 100%);
        }}
        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .stat-card .number {{
            font-size: 36px;
            font-weight: bold;
            margin: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }}
        thead {{
            background-color: #34495e;
            color: white;
        }}
        th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid #2c3e50;
        }}
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .url {{
            color: #3498db;
            text-decoration: none;
            word-break: break-all;
        }}
        .url:hover {{
            text-decoration: underline;
        }}
        .app-name {{
            color: #16a085;
            font-weight: 500;
        }}
        .pwned {{
            color: #ff6b6b;
            font-weight: bold;
        }}
        .tested-yes {{
            color: #27ae60;
            font-weight: 500;
        }}
        .tested-no {{
            color: #f39c12;
        }}
        .screenshot-yes {{
            color: #27ae60;
        }}
        .screenshot-no {{
            color: #e74c3c;
        }}
        .note {{
            margin-top: 30px;
            padding: 15px;
            background-color: #e8f4f8;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 EyeWitness Scan Summary</h1>
        
        <div class="stats">
            <div class="stat-card">
                <h3>Total URLs Scanned</h3>
                <p class="number">{total_urls}</p>
            </div>
            <div class="stat-card warning">
                <h3>Default Credentials Found</h3>
                <p class="number">{creds_found_count}</p>
            </div>
            <div class="stat-card success">
                <h3>Successfully Authenticated</h3>
                <p class="number">{pwned_count}</p>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>URL</th>
                    <th>Application</th>
                    <th>Tested</th>
                    <th>Default Credentials</th>
                    <th>Screenshot</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add table rows
    for obj in results:
        url = html_module.escape(obj.remote_system)
        
        # Get application name
        app_name = "Unknown Application"
        if obj.ai_application_info:
            ai_app = obj.ai_application_info.get('application_name')
            manufacturer = obj.ai_application_info.get('manufacturer')
            model = obj.ai_application_info.get('model')
            
            if ai_app:
                app_name = ai_app
            elif manufacturer and model:
                app_name = f"{manufacturer} {model}"
            elif manufacturer:
                app_name = manufacturer
            elif model:
                app_name = model
        
        if app_name == "Unknown Application" and obj.page_title:
            page_title = str(obj.page_title)
            if isinstance(obj.page_title, bytes):
                page_title = obj.page_title.decode('utf-8', errors='ignore')
            page_title = page_title.strip()
            for suffix in [' - Login', ' - Log in', ' Login', ' Log in']:
                if page_title.endswith(suffix):
                    page_title = page_title[:-len(suffix)].strip()
            if page_title and page_title.lower() not in ['login', 'log in', 'home', 'welcome', 'unknown']:
                app_name = page_title.split(' - ')[0].split(' | ')[0].split('|')[0].strip()[:50]
        
        if app_name == "Unknown Application" and obj.default_creds and ' / ' in obj.default_creds:
            app_name = obj.default_creds.split(' / ')[0].strip()
        
        app_name = html_module.escape(app_name)
        
        # Check if tested
        test_result = obj.credential_test_result if hasattr(obj, 'credential_test_result') else None
        was_tested = bool(test_result and test_result.get('tested'))
        tested_text = '<span class="tested-yes">YES</span>' if was_tested else '<span class="tested-no">NO</span>'
        
        # Get credentials
        creds_worked = bool(test_result and test_result.get('successful_credentials'))
        creds_display = ""
        
        if creds_worked:
            working_cred = test_result['successful_credentials'][0]
            username = working_cred.get('username', '')
            password = working_cred.get('password', '')
            creds_display = f'{html_module.escape(username)}:{html_module.escape(password)} <span class="pwned">(Pwned!)</span>'
        elif obj.default_creds:
            import re
            match = re.search(r'([^/\s]+)[:/]([^\s]+)', obj.default_creds)
            if match:
                creds_display = html_module.escape(f'{match.group(1)}:{match.group(2)}')
            else:
                creds_display = html_module.escape(obj.default_creds)
        else:
            creds_display = '<span style="color:#999;">None</span>'
        
        # Screenshot
        has_screenshot = obj.screenshot_path and os.path.exists(os.path.join(output_dir, 'screens', os.path.basename(obj.screenshot_path)))
        screen_text = '<span class="screenshot-yes">YES</span>' if has_screenshot else '<span class="screenshot-no">NO</span>'
        
        html_content += f"""
                <tr>
                    <td><a href="{url}" target="_blank" class="url">{url}</a></td>
                    <td><span class="app-name">{app_name}</span></td>
                    <td>{tested_text}</td>
                    <td>{creds_display}</td>
                    <td>{screen_text}</td>
                </tr>
"""
    
    html_content += f"""
            </tbody>
        </table>
        
        <div class="note">
            <strong>Note:</strong> For full analysis including screenshots, technologies detected, and detailed information, 
            use the web application interface at <code>/path/to/webapp</code>
        </div>
    </div>
</body>
</html>
"""
    
    # Write HTML file
    report_path = os.path.join(output_dir, 'report.html')
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[+] Simple HTML report generated: {report_path}")
    except Exception as e:
        print(f"[!] Error generating simple report: {e}")
