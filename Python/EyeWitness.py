#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
try:
    import argcomplete
    from argcomplete.completers import FilesCompleter
    HAS_ARGCOMPLETE = True
except ImportError:
    HAS_ARGCOMPLETE = False
    FilesCompleter = None
import os
import re
import shutil
import signal
import sys
import time
import webbrowser

# Auto-activate virtual environment if available
def setup_virtual_environment():
    """
    Automatically set up virtual environment paths if venv exists.
    This allows the script to use packages from venv-eyewitness/ or eyewitness-venv/
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    # Check for both possible venv names
    venv_paths = [
        os.path.join(project_root, 'venv-eyewitness'),
        os.path.join(project_root, 'eyewitness-venv'),
    ]
    
    for venv_path in venv_paths:
        if os.path.exists(venv_path):
            # Add venv site-packages to Python path
            if sys.platform == 'win32':
                site_packages = os.path.join(venv_path, 'Lib', 'site-packages')
            else:
                # Try multiple Python version paths (for compatibility)
                python_versions = [
                    f'python{sys.version_info.major}.{sys.version_info.minor}',
                    f'python{sys.version_info.major}',
                ]
                
                site_packages = None
                for py_ver in python_versions:
                    potential_path = os.path.join(venv_path, 'lib', py_ver, 'site-packages')
                    if os.path.exists(potential_path):
                        site_packages = potential_path
                        break
                
                # Fallback: try to find any python* directory
                if not site_packages:
                    lib_dir = os.path.join(venv_path, 'lib')
                    if os.path.exists(lib_dir):
                        for item in os.listdir(lib_dir):
                            if item.startswith('python'):
                                potential_path = os.path.join(lib_dir, item, 'site-packages')
                                if os.path.exists(potential_path):
                                    site_packages = potential_path
                                    break
            
            if site_packages and os.path.exists(site_packages):
                if site_packages not in sys.path:
                    sys.path.insert(0, site_packages)
                    print(f"[*] Using virtual environment: {venv_path}")
                break

# Set up virtual environment before any other imports
setup_virtual_environment()

from modules import db_manager
from modules import objects
from modules import selenium_module
from modules.helpers import class_info
from modules.helpers import create_folders_css
from modules.helpers import default_creds_category
from modules.helpers import target_creator
from modules.helpers import title_screen
from modules.helpers import open_file_input
from modules.helpers import duplicate_check
from modules.helpers import print_summary_table
from modules.reporting import sort_data_and_write
from multiprocessing import Manager
from multiprocessing import current_process
from modules.platform_utils import PlatformManager, setup_virtual_display
from modules.resource_monitor import ResourceMonitor, check_disk_space, get_system_info

# Initialize platform manager
platform_mgr = PlatformManager()


def create_cli_parser():
    parser = argparse.ArgumentParser(
        add_help=False, description="EyeWitness is a tool used to capture\
        screenshots from a list of URLs")
    parser.add_argument('-h', '-?', '--h', '-help',
                        '--help', action="store_true", help=argparse.SUPPRESS)

    protocols = parser.add_argument_group('Protocols')
    protocols.add_argument('--web', default=True, action='store_true',
                           help='HTTP Screenshot using Selenium')

    input_options = parser.add_argument_group('Input Options')
    f_arg = input_options.add_argument('-f', metavar='Filename', default=None,
                               help='Line-separated file containing URLs to \
                                capture')
    if HAS_ARGCOMPLETE and FilesCompleter:
        f_arg.completer = FilesCompleter()
    x_arg = input_options.add_argument('-x', metavar='Filename.xml', default=None,
                               help='Nmap XML or .Nessus file')
    if HAS_ARGCOMPLETE and FilesCompleter:
        x_arg.completer = FilesCompleter(allowednames='*.xml *.nessus', directories=True)
    input_options.add_argument('--single', metavar='Single URL', default=None,
                               help='Single URL/Host to capture')
    input_options.add_argument('--no-dns', default=False, action='store_true',
                               help='Skip DNS resolution when connecting to \
                            websites')
    
    # Port scanning options for IP-based discovery
    scan_options = parser.add_argument_group('IP/Network Scan Options')
    scan_options.add_argument('--scan', metavar='TARGET', nargs='+', default=None,
                              help='IP(s), CIDR ranges, or IP ranges to scan (e.g., 192.168.1.100, 192.168.1.0/24, 192.168.1.1-50)')
    scan_options.add_argument('--scan-ports', metavar='PRESET', default='medium',
                              choices=['small', 'medium', 'large', 'xlarge'],
                              help='Port preset: small (80,443), medium (80,443,8000,8080,8443), large (17 ports), xlarge (70+ ports). Default: medium')
    scan_options.add_argument('--custom-ports', metavar='PORTS', default=None,
                              help='Custom comma-separated ports to scan (e.g., 80,443,8080,9000)')
    scan_options.add_argument('--scan-timeout', metavar='SECONDS', default=2.0, type=float,
                              help='Connection timeout for port scanning (default: 2.0)')
    scan_options.add_argument('--scan-threads', metavar='THREADS', default=100, type=int,
                              help='Number of threads for port scanning (default: 100)')

    timing_options = parser.add_argument_group('Timing Options')
    timing_options.add_argument('--timeout', metavar='Timeout', default=30, type=int,
                                help='Maximum number of seconds to wait while\
                                 requesting a web page (Default: 30)')
    timing_options.add_argument('--jitter', metavar='# of Seconds', default=0,
                                type=int, help='Randomize URLs and add a random\
                                 delay between requests')
    timing_options.add_argument('--delay', metavar='# of Seconds', default=0,
                                type=int, help='Fixed delay for JS rendering. If 0, uses progressive retry: 5s, 10s, 15s (default: 0)')
    # Calculate default threads based on CPU cores (2 threads per core, max 20)
    timing_options.add_argument('--threads', metavar='# of Threads', default=1,
                                type=int, help='Number of threads to use (default: 1 for sequential processing)')
    timing_options.add_argument('--max-retries', default=1, metavar='Max retries on \
                                a timeout'.replace('    ', ''), type=int,
                                help='Max retries on timeouts')

    report_options = parser.add_argument_group('Report Output Options')
    d_arg = report_options.add_argument('-d', metavar='Output Directory',
                                default=None,
                                help='Output directory for screenshots and reports')
    if HAS_ARGCOMPLETE and FilesCompleter:
        from argcomplete.completers import DirectoriesCompleter
        d_arg.completer = DirectoriesCompleter()
    report_options.add_argument('--db', metavar='Project Name',
                                default=None,
                                help='Project database name (e.g., --db myproject). If exists, updates without duplicating.')
    report_options.add_argument('--no-clear', default=True,
                                action='store_true',
                                help='Don\'t clear screen buffer (default behavior)')

    http_options = parser.add_argument_group('Web Options')
    http_options.add_argument('--user-agent', metavar='User Agent',
                              default=None, help='User Agent to use for all\
                               requests')
    http_options.add_argument('--difference', metavar='Difference Threshold',
                              default=50, type=int, help='Difference threshold\
                               when determining if user agent requests are\
                                close \"enough\" (Default: 50)')
    http_options.add_argument('--proxy-ip', metavar='127.0.0.1', default=None,
                              help='IP of web proxy to go through')
    http_options.add_argument('--proxy-port', metavar='8080', default=None,
                              type=int, help='Port of web proxy to go through')
    http_options.add_argument('--proxy-type', metavar='socks5', default="http",
                              help='Proxy type (socks5/http)')
    http_options.add_argument('--show-selenium', default=False,
                              action='store_true', help='Show display for selenium')
    http_options.add_argument('--resolve', default=False,
                              action='store_true', help=("Resolve IP/Hostname"
                                                         " for targets"))
    http_options.add_argument('--add-http-ports', default=[], 
                              type=lambda s:[str(i) for i in s.split(",")],
                              help=("Comma-separated additional port(s) to assume "
                              "are http (e.g. '8018,8028')"))
    http_options.add_argument('--add-https-ports', default=[],
                              type=lambda s:[str(i) for i in s.split(",")],
                              help=("Comma-separated additional port(s) to assume "
                              "are https (e.g. '8018,8028')"))
    http_options.add_argument('--only-ports', default=[],
                              type=lambda s:[int(i) for i in s.split(",")],
                              help=("Comma-separated list of exclusive ports to "
                              "use (e.g. '80,8080')"))
    http_options.add_argument('--prepend-https', default=False, action='store_true',
                              help='Prepend http:// and https:// to URLs without either')
    http_options.add_argument('--validate-urls', default=False, action='store_true',
                              help='Only validate URLs without taking screenshots')
    http_options.add_argument('--skip-validation', default=False, action='store_true',
                              help='Skip URL validation checks (use with caution)')
    http_options.add_argument('--selenium-log-path', default='./chromedriver.log', action='store',
                              help='Selenium ChromeDriver log path')
    http_options.add_argument('--cookies', metavar='key1=value1,key2=value2', default=None,
                              help='Additional cookies to add to the request')
    http_options.add_argument('--width', metavar="1366", default=1366,type=int,
                              help='Screenshot window image width size. 600-7680 (eg. 1920)')
    http_options.add_argument('--height', metavar="768", default=768, type=int,
                              help='Screenshot window image height size. 400-4320 (eg. 1080)')

    ai_options = parser.add_argument_group('AI-Powered Analysis Options')
    ai_options.add_argument('--enable-ai', default=False, action='store_true',
                            help='Enable AI-powered analysis for unknown applications')
    ai_options.add_argument('--ai-api-key', metavar='API_KEY', default=None,
                            help='API key for AI service (OpenAI or Anthropic). Can also set OPENAI_API_KEY or ANTHROPIC_API_KEY env vars')
    ai_options.add_argument('--ai-provider', choices=['openai', 'anthropic'], default=None,
                            help='AI provider to use (openai or anthropic). Auto-detected from env vars if not specified')
    ai_options.add_argument('--test-credentials', default=True, action='store_true',
                            help='Test found credentials against login forms (default: True)')
    ai_options.add_argument('--no-test-credentials', dest='test_credentials', action='store_false',
                            help='Disable credential testing')
    ai_options.add_argument('--credential-test-timeout', default=10, type=int,
                            help='Timeout for credential tests in seconds (default: 10)')
    ai_options.add_argument('--credential-test-delay', default=2.0, type=float,
                            help='Delay between credential tests in seconds (default: 2.0)')
    ai_options.add_argument('--debug-creds', action='store_true', default=False,
                            help='Enable debug mode for credential testing (saves screenshots and logs)')

    resume_options = parser.add_argument_group('Resume Options')
    resume_options.add_argument('--resume', metavar='ew.db',
                                default=None, help='Path to db file if you want to resume')

    config_options = parser.add_argument_group('Configuration Options')
    config_arg = config_options.add_argument('--config', metavar='config.json', default=None,
                                help='Configuration file path')
    if HAS_ARGCOMPLETE and FilesCompleter:
        config_arg.completer = FilesCompleter(allowednames='*.json', directories=True)
    config_options.add_argument('--create-config', action='store_true',
                                help='Create sample configuration file')

    # Enable bash tab completion if argcomplete is available
    if HAS_ARGCOMPLETE:
        argcomplete.autocomplete(parser)
    
    args = parser.parse_args()
    args.date = time.strftime('%Y/%m/%d')
    args.time = time.strftime('%H:%M:%S')
    
    # Handle config creation
    if args.create_config:
        from modules.config import ConfigManager
        ConfigManager.create_sample_config()
        sys.exit(0)
    
    # Load config file if specified or found
    from modules.config import ConfigManager
    config = ConfigManager.load_config(args.config)
    args = ConfigManager.apply_config_to_args(args, config)

    if args.h:
        parser.print_help()
        sys.exit()

    if args.f is None and args.single is None and args.resume is None and args.x is None and args.scan is None:
        print("[!] Error: No input specified")
        print("[*] You must provide one of the following:")
        print("    - URL file: -f urls.txt")
        print("    - Single URL: --single http://example.com")
        print("    - XML file: -x nmap.xml")
        print("    - IP/Network scan: --scan 192.168.1.0/24")
        print("    - Resume scan: --resume")
        print("[*] Run 'EyeWitness.py -h' for full help")
        sys.exit(1)

    if ((args.f is not None) and not os.path.isfile(args.f)) or ((args.x is not None) and not os.path.isfile(args.x)):
        from modules.troubleshooting import get_error_guidance
        if args.f and not os.path.isfile(args.f):
            print(get_error_guidance('file_not_found', path=args.f))
        if args.x and not os.path.isfile(args.x):
            print(get_error_guidance('file_not_found', path=args.x))
        sys.exit(1)

    if args.width < 600 or args.width >7680:
        print("\n[*] Error: Specify a width >= 600 and <= 7680, for example 1920.\n")
        parser.print_help()
        sys.exit()

    if args.height < 400 or args.height >4320:
        print("\n[*] Error: Specify a height >= 400 and <= 4320, for example, 1080.\n")
        parser.print_help()
        sys.exit()

    # Handle --db project name (recommended workflow)
    if args.db is not None:
        # Use project-based directory structure
        project_dir = os.path.join(os.getcwd(), 'eyewitness_projects', args.db)
        args.d = project_dir
        args.db_path = os.path.join(project_dir, f'{args.db}.db')
        
        # Create project directory if it doesn't exist
        if not os.path.exists(project_dir):
            os.makedirs(project_dir, exist_ok=True)
            print(f"[*] Created new project: {args.db}")
            print(f"[*] Location: {project_dir}")
        else:
            print(f"[*] Using existing project: {args.db}")
            print(f"[*] Database will be updated (duplicates avoided)")
    elif args.d is not None:
        if args.d.startswith('/') or re.match(
                '^[A-Za-z]:\\\\', args.d) is not None:
            args.d = args.d.rstrip('/')
            args.d = args.d.rstrip('\\')
        else:
            args.d = os.path.join(os.getcwd(), args.d)

        if not os.access(os.path.dirname(args.d), os.W_OK):
            print('[*] Error: Please provide a valid folder name/path')
            parser.print_help()
            sys.exit()
        else:
            if os.path.isdir(args.d):
                overwrite_dir = input(('Directory Exists! Do you want to '
                                           'overwrite? [y/n] '))
                overwrite_dir = overwrite_dir.lower().strip()
                if overwrite_dir == 'n':
                    print('Quitting...Restart and provide the proper '
                          'directory to write to!')
                    sys.exit()
                elif overwrite_dir == 'y':
                    shutil.rmtree(args.d)
                    pass
                else:
                    print('Quitting since you didn\'t provide '
                          'a valid response...')
                    sys.exit()
        args.db_path = os.path.join(args.d, 'ew.db')
    else:
        # Legacy timestamp-based directory (not recommended)
        print("[!] Warning: Using legacy timestamp-based directory")
        print("[!] Recommendation: Use --db <project_name> for better organization")
        print("[!] Example: --db mycompany_pentest")
        output_folder = args.date.replace(
            '/', '-') + '_' + args.time.replace(':', '')
        args.d = os.path.join(os.getcwd(), output_folder)
        args.db_path = os.path.join(args.d, 'ew.db')

    args.log_file_path = os.path.join(args.d, 'logfile.log')

    if not any((args.resume, args.web)):
        print("[*] Error: You didn't give me an action to perform.")
        print("[*] Error: Please use --web!\n")
        parser.print_help()
        sys.exit()

    if args.resume:
        if not os.path.isfile(args.resume):
            print(" [*] Error: No valid DB file provided for resume!")
            sys.exit()

    if args.proxy_ip is not None and args.proxy_port is None:
        print("[*] Error: Please provide a port for the proxy!")
        parser.print_help()
        sys.exit()

    if args.proxy_port is not None and args.proxy_ip is None:
        print("[*] Error: Please provide an IP for the proxy!")
        parser.print_help()
        sys.exit()

    if args.cookies:
        cookies_list = []
        for one_cookie in args.cookies.split(","):
            if "=" not in one_cookie:
                print("[*] Error: Cookies must be in the form of key1=value1,key2=value2")
                sys.exit()
            cookies_list.append({
                "name": one_cookie.split("=")[0],
                "value": one_cookie.split("=")[1]
            })
        args.cookies = cookies_list
    args.ua_init = False
    return args


def single_mode(cli_parsed):
    display = None
    driver = None
    
    def exitsig(*args):
        if current_process().name == 'MainProcess':
            print('')
            print('Quitting...')
        os._exit(1)

    signal.signal(signal.SIGINT, exitsig)

    if cli_parsed.web:
        create_driver = selenium_module.create_driver
        capture_host = selenium_module.capture_host
        
        # Setup virtual display with cross-platform handling
        display = setup_virtual_display(platform_mgr, cli_parsed.show_selenium)

    try:
        url = cli_parsed.single
        http_object = objects.HTTPTableObject()
        http_object.remote_system = url
        http_object.set_paths(
            cli_parsed.d, None)

        driver = create_driver(cli_parsed)
        result, driver = capture_host(cli_parsed, http_object, driver)
        result = default_creds_category(result)
        
        # AI-powered analysis and/or credential testing if enabled
        # Runs if: --enable-ai is set OR --test-credentials is true (default) and there are credentials to test
        should_analyze = result.error_state is None and (
            cli_parsed.enable_ai or 
            (cli_parsed.test_credentials and result.default_creds)
        )
        if should_analyze:
            from modules.ai_credential_analyzer import AICredentialAnalyzer
            ai_analyzer = AICredentialAnalyzer(
                ai_api_key=cli_parsed.ai_api_key,
                ai_provider=cli_parsed.ai_provider,
                test_credentials=cli_parsed.test_credentials,
                credential_test_timeout=cli_parsed.credential_test_timeout,
                credential_test_delay=cli_parsed.credential_test_delay,
                debug_creds=cli_parsed.debug_creds,
                output_dir=cli_parsed.d
            )
            if ai_analyzer.ai_enabled or ai_analyzer.test_credentials:
                result = ai_analyzer.analyze_http_object(result)
        
        if cli_parsed.resolve:
            result.resolved = resolve_host(result.remote_system)
        
        # Show summary table in console
        print_summary_table([result])
    finally:
        if driver:
            driver.quit()
        if display is not None:
            display.stop()


def multi_mode(cli_parsed):
    """
    Process multiple URLs using parallel workers with isolated Chromium browsers.
    
    Architecture:
    - WorkerPoolManager: Orchestrates process pool
    - IsolatedWorker: Each worker has isolated Chromium profile
    - DBWriterProcess: Single-writer pattern for SQLite safety
    - MetricsCollector: Real-time observability
    """
    display = None
    
    # Setup virtual display with cross-platform handling
    if cli_parsed.web:
        display = setup_virtual_display(platform_mgr, cli_parsed.show_selenium)
    
    # Check disk space before starting
    has_space, available_gb, total_gb = check_disk_space(cli_parsed.d, min_gb=1)
    if not has_space:
        print(f'[!] Warning: Low disk space! Only {available_gb:.1f}GB available')
        print('[!] Consider freeing space or using a different output directory')
    
    # Get system info
    print(f'[*] {get_system_info()}')
    
    # Get URL list
    if cli_parsed.resume:
        dbm = db_manager.DB_Manager(cli_parsed.db_path)
        dbm.open_connection()
        temp_queue = Manager().Queue()
        multi_total = dbm.get_incomplete_http(temp_queue)
        url_list = []
        while not temp_queue.empty():
            obj = temp_queue.get()
            url_list.append(obj.remote_system)
        dbm.close()
        print(f'Resuming Web Scan ({multi_total} Hosts Remaining)')
    else:
        url_list = target_creator(cli_parsed)
        print(f'Starting Web Requests ({len(url_list)} Hosts)')
    
    if not url_list:
        print('[!] No URLs to process')
        if display is not None:
            display.stop()
        return
    
    # Determine number of workers based on available resources
    resource_monitor = ResourceMonitor(memory_limit_percent=80)
    recommended_workers = resource_monitor.get_recommended_threads(cli_parsed.threads)
    
    if recommended_workers < cli_parsed.threads:
        print(f'[*] Adjusting threads from {cli_parsed.threads} to {recommended_workers} based on available memory')
    
    # Ensure at least 1 worker, max is number of URLs
    num_workers = max(1, min(recommended_workers, len(url_list)))
    
    print(f'[*] Using parallel worker pool with {num_workers} isolated workers')
    print(f'[*] Each worker has its own Chromium browser instance')
    
    try:
        from modules.concurrency import run_parallel_scan
        
        results = run_parallel_scan(
            cli_parsed=cli_parsed,
            urls=url_list,
            num_workers=num_workers
        )
        
    except KeyboardInterrupt:
        print('\n[!] Interrupted - partial results may be available')
        print(f'Resume using ./EyeWitness.py --resume {cli_parsed.db_path}')
        results = []
    except Exception as e:
        print(f'[!] Error in parallel processing: {e}')
        import traceback
        traceback.print_exc()
        results = []
    
    if display is not None:
        display.stop()
    
    # Generate reports
    sort_data_and_write(cli_parsed, results)


if __name__ == "__main__":
    cli_parsed = create_cli_parser()
    start_time = time.time()
    title_screen(cli_parsed)
    
    if cli_parsed.resume:
        print('[*] Loading Resume Data...')
        temp = cli_parsed
        dbm = db_manager.DB_Manager(cli_parsed.resume)
        dbm.open_connection()
        cli_parsed = dbm.get_options()
        cli_parsed.d = os.path.dirname(temp.resume)
        cli_parsed.resume = temp.resume
        dbm.close()

        print('Loaded Resume Data with the following options:')
        engines = []
        if cli_parsed.web:
            engines.append('Firefox')
        print('')
        print('Input File: {0}'.format(cli_parsed.f))
        print('Engine(s): {0}'.format(','.join(engines)))
        print('Threads: {0}'.format(cli_parsed.threads))
        print('Output Directory: {0}'.format(cli_parsed.d))
        print('Timeout: {0}'.format(cli_parsed.timeout))
        print('')
    else:
        create_folders_css(cli_parsed)

    # Handle validate-only mode
    if cli_parsed.validate_urls:
        print('[*] Running in URL validation mode only')
        from modules.validation import validate_url_list
        from modules.helpers import target_creator
        
        url_list = target_creator(cli_parsed)
        valid_urls, invalid_urls = validate_url_list(url_list, require_scheme=False)
        
        print(f'\n[*] Validation Results:')
        print(f'    - Valid URLs: {len(valid_urls)}')
        print(f'    - Invalid URLs: {len(invalid_urls)}')
        
        if invalid_urls:
            print('\n[!] Invalid URLs found:')
            for url, error in invalid_urls[:20]:  # Show first 20
                print(f'    - {url}: {error}')
            if len(invalid_urls) > 20:
                print(f'    ... and {len(invalid_urls) - 20} more')
        
        # Write valid URLs to file
        if valid_urls:
            valid_file = os.path.join(cli_parsed.d, 'valid_urls.txt')
            with open(valid_file, 'w') as f:
                for url in valid_urls:
                    f.write(url + '\n')
            print(f'\n[*] Valid URLs written to: {valid_file}')
        
        if invalid_urls:
            invalid_file = os.path.join(cli_parsed.d, 'invalid_urls.txt')
            with open(invalid_file, 'w') as f:
                for url, error in invalid_urls:
                    f.write(f'{url} # {error}\n')
            print(f'[*] Invalid URLs written to: {invalid_file}')
        
        print(f'\n[*] Validation completed in {time.time() - start_time:.2f} seconds')
        sys.exit(0)

    if cli_parsed.single:
        if cli_parsed.web:
            single_mode(cli_parsed)
        
        print('\n[*] Done! Report written in the ' + cli_parsed.d + ' folder!')
        
        class_info()
        sys.exit()

    if cli_parsed.f is not None or cli_parsed.x is not None or cli_parsed.scan is not None:
        multi_mode(cli_parsed)
        duplicate_check(cli_parsed)
        
        # Save auth methods for password spraying if AI was enabled
        if cli_parsed.enable_ai:
            try:
                from modules.ai_credential_analyzer import AICredentialAnalyzer
                from modules.db_manager import DB_Manager
                
                dbm = DB_Manager(cli_parsed.db_path)
                dbm.open_connection()
                results = dbm.get_complete_http()
                dbm.close()
                
                if results:
                    ai_analyzer = AICredentialAnalyzer(
                        ai_api_key=cli_parsed.ai_api_key,
                        ai_provider=cli_parsed.ai_provider
                    )
                    ai_analyzer.save_auth_methods_for_spraying(results, cli_parsed.d)
            except Exception as e:
                print(f"[!] Error saving auth methods: {e}")

    print('Finished in {0:.2f} seconds'.format(time.time() - start_time))

    # Show summary table and generate simple HTML report
    try:
        from modules.db_manager import DB_Manager
        dbm = DB_Manager(cli_parsed.db_path)
        dbm.open_connection()
        all_results = dbm.get_complete_http()
        dbm.close()
        
        if all_results:
            print_summary_table(all_results)
    except Exception as e:
        print(f"[!] Could not generate summary table: {e}")

    print('\n[*] Done! Results saved')
    
    # Show project information
    if hasattr(cli_parsed, 'db') and cli_parsed.db:
        print(f'[*] Project: {cli_parsed.db}')
        print(f'[*] Database: {cli_parsed.db_path}')
    else:
        print(f'[*] Output Directory: {cli_parsed.d}')
    
    # Info about webapp
    print('\n[+] To view results in web interface:')
    print('    cd webapp && ./start.sh')
    print('    Then open: http://localhost:3000')
    
    class_info()
    sys.exit()
