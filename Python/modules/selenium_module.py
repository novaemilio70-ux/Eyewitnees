#!/usr/bin/env python3
"""
Chromium-based selenium module for EyeWitness
Simplified single-browser approach using Chrome/Chromium headless
"""

import http.client
import os
import socket
import sys
import time
import urllib.request
import urllib.error
import ssl
import shutil
import tempfile
from pathlib import Path

try:
    from ssl import CertificateError as sslerr
except ImportError:
    from ssl import SSLError as sslerr

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import NoAlertPresentException
    from selenium.common.exceptions import TimeoutException
    from selenium.common.exceptions import UnexpectedAlertPresentException
    from selenium.common.exceptions import WebDriverException
except ImportError:
    print('[*] Selenium not found.')
    print('[*] Run pip list to verify installation')
    print('[*] Try: sudo apt install python3-selenium')
    sys.exit()

from modules.helpers import do_delay
from modules.platform_utils import platform_mgr
from modules.security_headers import collect_http_headers

# Platform-specific environment configuration for headless operation
if platform_mgr.is_linux:
    # Optimize for headless Linux servers
    os.environ['DISPLAY'] = ':99'  # Virtual display
    os.environ['CHROME_HEADLESS'] = '1'
    os.environ['CHROME_NO_SANDBOX'] = '1'


def create_driver(cli_parsed, user_agent=None):
    """Creates a Chromium WebDriver optimized for headless operation
    
    Args:
        cli_parsed (ArgumentParser): Command Line Object
        user_agent (String, optional): Optional user-agent string
        
    Returns:
        ChromeDriver: Selenium Chrome Webdriver
    """
    try:
        options = ChromeOptions()
        
        # Essential headless configuration
        options.add_argument('--headless=new')  # Use new headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-web-security')
        options.add_argument('--allow-running-insecure-content')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--ignore-certificate-errors-spki-list')
        options.add_argument('--disable-features=VizDisplayCompositor')
        
        # Memory and performance optimization
        options.add_argument('--memory-pressure-off')
        options.add_argument('--max_old_space_size=4096')
        options.add_argument('--no-zygote')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-backgrounding-occluded-windows')
        
        # Window size configuration
        width = getattr(cli_parsed, 'width', 1920)
        height = getattr(cli_parsed, 'height', 1080)
        options.add_argument(f'--window-size={width},{height}')
        
        # User agent configuration
        if user_agent:
            options.add_argument(f'--user-agent={user_agent}')
        elif hasattr(cli_parsed, 'user_agent') and cli_parsed.user_agent:
            options.add_argument(f'--user-agent={cli_parsed.user_agent}')
        
        # Disable automation detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Enable performance logging for network logs
        options.set_capability('goog:loggingPrefs', {
            'performance': 'ALL',
            'browser': 'ALL'
        })
        
        # Security and certificate handling
        options.accept_insecure_certs = True
        
        # Setup Chrome service
        service_kwargs = {}
        
        # Find chromedriver automatically
        chromedriver_path = find_chromedriver()
        if chromedriver_path:
            service_kwargs['executable_path'] = chromedriver_path
        
        # Configure temp directory for better compatibility
        temp_dir = tempfile.gettempdir()
        os.environ['TMPDIR'] = temp_dir
        os.environ['TMP'] = temp_dir
        os.environ['TEMP'] = temp_dir
        
        service = ChromeService(**service_kwargs)
        
        # Create Chrome driver
        driver = webdriver.Chrome(service=service, options=options)
        
        # Set timeouts and window size
        driver.set_page_load_timeout(cli_parsed.timeout)
        driver.set_window_size(width, height)
        
        # Remove automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f'[+] Chrome driver initialized successfully (headless mode)')
        return driver
        
    except Exception as e:
        from modules.troubleshooting import get_error_guidance
        print(f'[!] Chrome WebDriver initialization error: {e}')
        print('[*] Troubleshooting tips:')
        print('    - Ensure Chromium is installed: sudo apt install chromium-browser')
        print('    - Install chromedriver: sudo apt install chromium-chromedriver')
        print('    - Run the setup script: sudo ./setup/setup.sh')
        
        # Special handling for common Chrome errors
        error_str = str(e).lower()
        if 'chromedriver' in error_str:
            print('\n[!] ChromeDriver not found or incompatible')
            print('[*] Quick fix: sudo apt install chromium-chromedriver')
        elif 'chrome' in error_str or 'chromium' in error_str:
            print('\n[!] Chrome/Chromium browser not found')
            print('[*] Quick fix: sudo apt install chromium-browser')
            
        sys.exit(1)


def find_chromedriver():
    """Find chromedriver executable in various locations"""
    # Common chromedriver locations
    possible_paths = [
        '/usr/bin/chromedriver',
        '/usr/local/bin/chromedriver',
        '/snap/bin/chromium.chromedriver',
        shutil.which('chromedriver'),
        shutil.which('chromium-chromedriver'),
    ]
    
    for path in possible_paths:
        if path and Path(path).exists():
            return path
    
    return None


def capture_host(cli_parsed, http_object, driver, ua=None):
    """Screenshots a single host using Chrome and returns updated HTTP Object
    
    Enhanced version that collects HTTP headers and performs security analysis
    alongside Selenium screenshot capture.
    
    Args:
        cli_parsed (ArgumentParser): Command Line Object  
        http_object (HTTPObject): HTTP Object
        driver (WebDriver): Selenium WebDriver
        ua (str, optional): User agent string
        
    Returns:
        tuple: (HTTPObject, WebDriver) Updated objects
    """
    # Step 1: Collect HTTP headers via HTTP client (before Selenium)
    print(f'  [*] Collecting headers...')
    
    # Set up proxy configuration if provided
    proxy_config = None
    if hasattr(cli_parsed, 'proxy_ip') and cli_parsed.proxy_ip:
        proxy_config = {
            'ip': cli_parsed.proxy_ip,
            'port': getattr(cli_parsed, 'proxy_port', 8080)
        }
    
    # Collect headers with HTTP client
    headers, header_error = collect_http_headers(
        url=http_object.remote_system,
        timeout=getattr(cli_parsed, 'timeout', 7),
        user_agent=ua or getattr(cli_parsed, 'user_agent', None),
        proxy=proxy_config
    )
    
    # Store headers in HTTPTableObject
    if headers:
        # Store raw headers in HTTPTableObject
        http_object.http_headers = headers
        
        # Detect HTTP authentication type (NTLM, Basic, etc.)
        from modules.security_headers import detect_http_auth_type
        auth_type = detect_http_auth_type(headers)
        if auth_type:
            http_object.http_auth_type = auth_type
            print(f'  [!] HTTP Authentication detected: {auth_type}')
        
        # Create formatted headers display for the report
        formatted_headers = {}
        for key, value in headers.items():
            # Truncate long header values for display
            display_value = value[:150] + "..." if len(value) > 150 else value
            formatted_headers[key] = display_value
        
        http_object.headers = formatted_headers
        
        print(f'  [+] Headers collected: {len(headers)} headers')
    else:
        # Handle header collection failure - might be due to HTTP auth
        if header_error:
            # Check if the error indicates authentication required
            if '401' in str(header_error) or 'Unauthorized' in str(header_error):
                print(f'  [!] HTTP Authentication required (401 Unauthorized)')
                http_object.http_auth_type = 'HTTP Authentication Required'
            else:
                print(f'  [!] Header collection failed: {header_error}')
            http_object.headers = {"Header Collection": f"Failed - {header_error}"}
        else:
            print(f'  [!] No headers received')
            http_object.headers = {"Headers": "No headers received"}
    
    # Step 2: Continue with Selenium screenshot capture
    import time
    
    # Helper function to sanitize filename
    def sanitize_filename(url):
        import re
        # Remove protocol and sanitize all unsafe characters
        filename = re.sub(r'^https?://', '', url)
        # Replace all non-alphanumeric characters (except hyphens and dots) with underscores
        filename = re.sub(r'[^a-zA-Z0-9\-\.]', '_', filename)
        # Limit length to prevent filesystem issues
        return filename[:200]
    
    # Helper function to wait for page to be fully loaded
    def wait_for_page_load(driver, timeout=30, use_network_idle=True):
        """
        Intelligently wait for page to be fully loaded using multiple strategies.
        Does NOT use hardcoded sleep times - uses dynamic detection instead.
        
        Args:
            driver: Selenium WebDriver instance
            timeout: Maximum time to wait in seconds
            use_network_idle: Whether to use DOM stability detection
            
        Returns:
            bool: True if page loaded successfully, False otherwise
        """
        try:
            wait = WebDriverWait(driver, timeout)
            start_time = time.time()
            
            # Strategy 1: Wait for document.readyState to be 'complete'
            try:
                wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
            except TimeoutException:
                pass  # Continue with other checks
            
            # Strategy 2: Wait for jQuery to be ready (if jQuery exists)
            try:
                WebDriverWait(driver, min(5, timeout)).until(lambda d: d.execute_script(
                    'return typeof jQuery === "undefined" || jQuery.active === 0'
                ))
            except (TimeoutException, Exception):
                pass  # jQuery might not be present or check failed
            
            # Strategy 3: Wait for Angular to be ready (if Angular exists)
            try:
                WebDriverWait(driver, min(5, timeout)).until(lambda d: d.execute_script(
                    'try { return typeof angular === "undefined" || angular.element(document).injector().get("$http").pendingRequests.length === 0; } catch(e) { return true; }'
                ))
            except (TimeoutException, Exception):
                pass  # Angular might not be present
            
            # Strategy 4: Wait for DOM to be stable (no changes for ~1 second)
            # This replaces performance logs which are not available in Chrome 143+
            if use_network_idle:
                try:
                    last_html_length = 0
                    stable_count = 0
                    check_interval = 0.3  # Check every 300ms
                    required_stable_checks = 3  # Need 3 stable checks (~1 second of stability)
                    max_checks = int(min(10, timeout) / check_interval)  # Max 10 seconds for this
                    
                    for _ in range(max_checks):
                        if time.time() - start_time > timeout:
                            break
                        
                        current_length = len(driver.page_source)
                        
                        if current_length == last_html_length and current_length > 100:
                            stable_count += 1
                            if stable_count >= required_stable_checks:
                                break  # DOM is stable
                        else:
                            stable_count = 0
                            last_html_length = current_length
                        
                        time.sleep(check_interval)
                except Exception:
                    pass  # Continue with other checks
            
            # Strategy 5: Wait for images to load (at least 80%)
            try:
                WebDriverWait(driver, min(5, timeout)).until(lambda d: d.execute_script('''
                    var images = document.images;
                    if (images.length === 0) return true;
                    var loaded = 0;
                    for (var i = 0; i < images.length; i++) {
                        if (images[i].complete && images[i].naturalHeight !== 0) {
                            loaded++;
                        }
                    }
                    return loaded >= images.length * 0.8;
                '''))
            except (TimeoutException, Exception):
                pass  # Images might still be loading
            
            # Strategy 6: Wait for common loading indicators to disappear
            try:
                WebDriverWait(driver, min(3, timeout)).until(lambda d: d.execute_script('''
                    var body = document.body;
                    if (!body) return false;
                    var bodyText = body.innerText.toLowerCase();
                    var loadingIndicators = ['loading...', 'please wait', 'cargando'];
                    for (var i = 0; i < loadingIndicators.length; i++) {
                        if (bodyText.indexOf(loadingIndicators[i]) !== -1) {
                            return false;
                        }
                    }
                    // Check for visible spinner elements
                    var spinners = document.querySelectorAll('.spinner, .loading, .loader');
                    for (var j = 0; j < spinners.length; j++) {
                        var style = window.getComputedStyle(spinners[j]);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            return false;
                        }
                    }
                    return true;
                '''))
            except (TimeoutException, Exception):
                pass  # Loading indicators check failed
            
            # Strategy 7: Wait for body to have visible content
            try:
                WebDriverWait(driver, min(3, timeout)).until(lambda d: d.execute_script('''
                    var body = document.body;
                    if (!body) return false;
                    var rect = body.getBoundingClientRect();
                    if (rect.height < 50) return false;
                    var text = body.innerText.trim();
                    return text.length > 10;
                '''))
            except (TimeoutException, Exception):
                pass  # Body might be intentionally minimal
            
            # Final check: Verify page has meaningful content
            page_source = driver.page_source
            if len(page_source) < 100:
                return False
            
            # Check for unrendered templates (Angular, Vue, etc.)
            if '{{' in page_source and '}}' in page_source:
                if page_source.count('{{') > 5:  # Likely unrendered template
                    return False
            
            return True
            
        except Exception as e:
            # If any error occurs, return False to trigger retry
            return False
    
    # Helper function to check if page loaded properly (backward compatibility)
    def is_page_loaded(driver):
        """Check if page has meaningful content (not blank or error)"""
        try:
            page_source = driver.page_source
            # Check for common signs of unloaded content
            if len(page_source) < 500:
                return False
            # Check for AngularJS/React unrendered templates
            if '{{' in page_source and '}}' in page_source:
                return False
            # Check for common loading indicators still present
            loading_indicators = ['ng-cloak', 'loading...', 'please wait', 'cargando']
            page_lower = page_source.lower()
            for indicator in loading_indicators:
                if indicator in page_lower:
                    return False
            return True
        except:
            return False
    
    # Determine wait strategy
    use_smart_wait = True
    fixed_delay = None
    
    if hasattr(cli_parsed, 'delay') and cli_parsed.delay > 0:
        # User specified a fixed delay - use it (but still do smart wait first)
        fixed_delay = cli_parsed.delay
        use_smart_wait = False  # User explicitly wants fixed delay
    
    try:
        print(f'  [*] Taking screenshot...')
        
        screenshot_success = False
        last_error = None
        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            try:
                if attempt == 1:
                    driver.get(http_object.remote_system)
                    
                    # Handle initial page load
                    try:
                        driver.implicitly_wait(2)
                    except TimeoutException:
                        pass
                
                # Wait for page to load
                if use_smart_wait:
                    if attempt == 1:
                        print(f'    [*] Waiting for page to load completely...')
                    else:
                        print(f'    [*] Attempt {attempt}/{max_attempts}: Waiting for page to load...')
                    
                    # Use intelligent wait
                    page_loaded = wait_for_page_load(driver, timeout=cli_parsed.timeout)
                    
                    if page_loaded:
                        screenshot_success = True
                        print(f'    [+] Page loaded successfully')
                        break
                    elif attempt < max_attempts:
                        print(f'    [*] Page not fully loaded, retrying...')
                        driver.refresh()
                    else:
                        # Last attempt - take screenshot anyway
                        screenshot_success = True
                        print(f'    [*] Capturing (may be incomplete)...')
                else:
                    # Use fixed delay (user preference)
                    if attempt == 1:
                        print(f'    [*] Waiting {fixed_delay}s for JS to render...')
                    else:
                        print(f'    [*] Attempt {attempt}/{max_attempts}: waiting {fixed_delay}s...')
                    time.sleep(fixed_delay)
                    
                    # Still check if page loaded
                    if is_page_loaded(driver):
                        screenshot_success = True
                        break
                    elif attempt < max_attempts:
                        print(f'    [*] Page not fully loaded, retrying...')
                        driver.refresh()
                    else:
                        screenshot_success = True
                        print(f'    [*] Capturing (may be incomplete)...')
                    
            except TimeoutException as e:
                last_error = e
                if attempt < max_attempts:
                    print(f'    [*] Timeout on attempt {attempt}, retrying...')
                    try:
                        driver.refresh()
                    except:
                        driver.get(http_object.remote_system)
                continue
            except Exception as e:
                last_error = e
                if attempt < max_attempts:
                    print(f'    [*] Error on attempt {attempt}: {e}, retrying...')
                    try:
                        driver.refresh()
                    except:
                        driver.get(http_object.remote_system)
                    continue
                break
        
        if not screenshot_success and last_error:
            raise last_error
            
        # Capture page content
        http_object.source_code = driver.page_source.encode('utf-8')
        http_object.page_title = driver.title

        # Persist source_code to the source folder
        try:
            src_bytes = http_object.source_code
            if isinstance(src_bytes, str):
                src_bytes = src_bytes.encode('utf-8')
            if getattr(http_object, 'source_path', None):
                dest = Path(http_object.source_path)
            else:
                file_name = http_object.remote_system.replace('://', '.')
                for char in [':', '/', '?', '=', '%', '+']:
                    file_name = file_name.replace(char, '.')
                dest = Path(cli_parsed.d) / 'source' / f'{file_name}.txt'
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, 'wb') as sf:
                sf.write(src_bytes)
            http_object.source_path = str(dest)
        except Exception as e:
            print(f'[!] Warning: failed to write page source for {http_object.remote_system}: {e}')
        
        # Take screenshot
        safe_filename = sanitize_filename(http_object.remote_system)
        screenshot_path = Path(cli_parsed.d) / 'screens' / f'{safe_filename}.png'
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            driver.save_screenshot(str(screenshot_path))
            http_object.screenshot_path = str(screenshot_path)
            print(f'  [+] Screenshot captured successfully')
        except Exception as e:
            print(f'  [!] Failed to save screenshot: {e}')
        
        # Step 3: Capture additional data for enhanced reports
        import time as time_module
        start_time = time_module.time()
        
        # Detect technologies
        try:
            from modules.technology_detector import detect_technologies
            print(f'  [*] Detecting technologies...')
            technologies = detect_technologies(http_object)
            http_object.technologies = technologies
            if technologies:
                print(f'  [+] Technologies detected: {", ".join(technologies[:5])}{"..." if len(technologies) > 5 else ""}')
        except Exception as e:
            print(f'  [!] Technology detection failed: {e}')
            http_object.technologies = []
        
        # Get SSL/TLS info
        try:
            from modules.ssl_info import get_ssl_cert_info
            print(f'  [*] Collecting SSL/TLS info...')
            ssl_info = get_ssl_cert_info(http_object.remote_system)
            if ssl_info:
                http_object.ssl_info = ssl_info
                print(f'  [+] SSL Info: {ssl_info.get("protocol", "Unknown")} - {ssl_info.get("cipher", "Unknown")}')
        except Exception as e:
            print(f'  [!] SSL info collection failed: {e}')
        
        # Capture console logs
        try:
            print(f'  [*] Capturing console logs...')
            console_logs = []
            try:
                logs = driver.get_log('browser')
                for log in logs:
                    console_logs.append({
                        'level': log.get('level', ''),
                        'message': log.get('message', ''),
                        'timestamp': log.get('timestamp', 0)
                    })
            except:
                pass
            http_object.console_logs = console_logs
            if console_logs:
                print(f'  [+] Console logs captured: {len(console_logs)} entries')
        except Exception as e:
            print(f'  [!] Console log capture failed: {e}')
            http_object.console_logs = []
        
        # Capture cookies
        try:
            print(f'  [*] Capturing cookies...')
            cookies = []
            try:
                selenium_cookies = driver.get_cookies()
                for cookie in selenium_cookies:
                    cookies.append({
                        'name': cookie.get('name', ''),
                        'value': cookie.get('value', '')[:100],  # Truncate long values
                        'domain': cookie.get('domain', ''),
                        'path': cookie.get('path', ''),
                        'secure': cookie.get('secure', False),
                        'httpOnly': cookie.get('httpOnly', False),
                        'expiry': cookie.get('expiry', None)
                    })
            except:
                pass
            http_object.cookies = cookies
            if cookies:
                print(f'  [+] Cookies captured: {len(cookies)} cookies')
        except Exception as e:
            print(f'  [!] Cookie capture failed: {e}')
            http_object.cookies = []
        
        # Capture network logs (using performance logs)
        try:
            print(f'  [*] Capturing network logs...')
            network_logs = []
            try:
                import json
                perf_logs = driver.get_log('performance')
                for log in perf_logs:
                    try:
                        message = json.loads(log['message'])
                        method = message.get('message', {}).get('method', '')
                        params = message.get('message', {}).get('params', {})
                        
                        if method == 'Network.responseReceived':
                            response = params.get('response', {})
                            network_logs.append({
                                'url': response.get('url', '')[:200],  # Truncate long URLs
                                'status': response.get('status', 0),
                                'statusText': response.get('statusText', ''),
                                'mimeType': response.get('mimeType', ''),
                                'type': response.get('type', ''),
                                'timestamp': message.get('message', {}).get('timestamp', 0)
                            })
                    except:
                        continue
            except:
                pass
            http_object.network_logs = network_logs
            if network_logs:
                print(f'  [+] Network logs captured: {len(network_logs)} requests')
        except Exception as e:
            print(f'  [!] Network log capture failed: {e}')
            http_object.network_logs = []
        
        # Calculate response size and load time
        try:
            response_size = len(http_object.source_code) if http_object.source_code else 0
            http_object.response_size = response_size
            
            load_time = time_module.time() - start_time
            http_object.load_time = round(load_time, 2)
        except:
            pass
        
    except TimeoutException:
        print(f'  [!] Timeout - could not connect')
        driver.quit()
        driver = create_driver(cli_parsed, ua)
        http_object.error_state = 'Timeout'
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Enhanced error handling with specific error types
        if 'net::err_connection_reset' in error_msg:
            print(f'[*] Connection reset by {http_object.remote_system} - target may be blocking requests')
            http_object.error_state = 'Connection Reset'
        elif 'net::err_connection_refused' in error_msg:
            print(f'[*] Connection refused by {http_object.remote_system} - service may be down')
            http_object.error_state = 'Connection Refused'
        elif 'net::err_timed_out' in error_msg or 'timeout' in error_msg:
            print(f'  [!] Timeout - could not connect')
            http_object.error_state = 'Timeout'
        elif 'net::err_name_not_resolved' in error_msg:
            print(f'[*] DNS resolution failed for {http_object.remote_system}')
            http_object.error_state = 'DNS Failed'
        elif 'net::err_cert_' in error_msg or 'certificate' in error_msg:
            print(f'[*] SSL/Certificate error for {http_object.remote_system}')
            http_object.error_state = 'SSL Error'
        elif 'chrome not reachable' in error_msg or 'session deleted' in error_msg:
            print(f'[*] Chrome driver crashed while accessing {http_object.remote_system} - restarting')
            http_object.error_state = 'Driver Crashed'
            # Force driver restart
            try:
                driver.quit()
            except:
                pass
            driver = create_driver(cli_parsed, ua)
            return http_object, driver
        else:
            print(f'[*] Error capturing screenshot for {http_object.remote_system}: {e}')
            http_object.error_state = 'Error'
        
        # Test if driver is still responsive
        try:
            driver.get('about:blank')
        except:
            print(f'[*] Chrome driver became unresponsive - restarting')
            try:
                driver.quit()
            except:
                pass
            driver = create_driver(cli_parsed, ua)
    
    return http_object, driver


def check_browsers_available():
    """Check if Chrome/Chromium is available"""
    browsers = []
    
    # Check for Chrome/Chromium binaries
    for browser in ['google-chrome', 'chromium-browser', 'chromium']:
        if shutil.which(browser):
            browsers.append(browser)
    
    # Check for chromedriver
    chromedriver_available = find_chromedriver() is not None
    
    return {
        'browsers': browsers,
        'chromedriver': chromedriver_available,
        'ready': len(browsers) > 0 and chromedriver_available
    }


def get_browser_info():
    """Get information about the browser setup"""
    status = check_browsers_available()
    
    print(f"[*] Browser Status:")
    print(f"    Available browsers: {', '.join(status['browsers']) if status['browsers'] else 'None'}")
    print(f"    ChromeDriver: {'Available' if status['chromedriver'] else 'Missing'}")
    print(f"    Ready for screenshots: {'Yes' if status['ready'] else 'No'}")
    
    if not status['ready']:
        print("[*] Run setup script to install: sudo ./setup/setup.sh")
    
    return status