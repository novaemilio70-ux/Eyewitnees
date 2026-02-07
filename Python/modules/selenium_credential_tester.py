#!/usr/bin/env python3
"""
Selenium-based Credential Tester for EyeWitness
Uses headless Chrome to test credentials, handling JavaScript encryption and complex auth flows
"""

import time
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException


class SeleniumCredentialTester:
    """Tests credentials using Selenium WebDriver - handles JS encryption automatically"""
    
    # Failure indicators in page text
    FAILURE_INDICATORS = [
        'invalid', 'incorrect', 'wrong', 'failed', 'error', 'denied',
        'unauthorized', 'bad credentials', 'login failed', 'authentication failed',
        'access denied', 'invalid username', 'invalid password', 'try again',
        'usuario incorrecto', 'contraseña incorrecta', 'acceso denegado',
        'incorrectos', 'inválido', 'échec', 'ungültig',  # Multi-language
    ]
    
    # Success indicators (multi-language) - must be specific to avoid false positives
    SUCCESS_INDICATORS = [
        # English - specific to logged-in state
        'dashboard', 'welcome back', 'logout', 'sign out', 'log out',
        'my profile', 'my settings', 'my account', 
        'control panel', 'management console', 'device settings',
        'logged in as', 'signed in as',
        # Spanish - specific to logged-in state
        'cerrar sesión', 'bienvenido', 'mi perfil',
        'panel de control', 'sesión iniciada',
        # German
        'abmelden', 'willkommen',
        # French  
        'déconnexion', 'bienvenue',
    ]
    
    # Strong failure indicators - these should ALWAYS indicate failure
    EXPLICIT_FAILURE_MESSAGES = [
        'invalid credentials', 'invalid password', 'invalid username',
        'incorrect password', 'incorrect username', 'authentication failed',
        'login failed', 'access denied', 'unauthorized', 'wrong password',
        "user doesn't exist", "user not found", "account not found",
        'credenciales inválidas', 'contraseña incorrecta', 'acceso denegado',
        'usuario no encontrado', 'autenticación fallida',
    ]
    
    # Auth type dropdown options to try (in priority order)
    # "Local" type auth is often more likely to work with default creds
    AUTH_TYPE_PREFERENCES = [
        'local', 'native', 'internal', 'built-in', 'device', 'system',
        'network', 'ldap', 'active directory', 'ad', 'radius', 'domain'
    ]
    
    def __init__(self, driver: webdriver.Chrome = None, delay: float = 2.0, timeout: int = 10,
                 debug: bool = False, debug_dir: str = None):
        """
        Initialize Selenium Credential Tester
        
        Args:
            driver: Existing Chrome WebDriver instance (reuses if provided)
            delay: Delay after form submission to wait for response
            timeout: Timeout for element waits
            debug: Enable debug mode (saves screenshots and logs)
            debug_dir: Directory to save debug files
        """
        self.driver = driver
        self.owns_driver = False
        self.delay = delay
        self.timeout = timeout
        self.debug = debug
        self.debug_dir = debug_dir
        self.debug_logs = []
    
    def _find_chromedriver(self):
        """Find chromedriver executable in various locations (for ARM and other platforms)"""
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
    
    def _get_driver(self, max_retries=3):
        """Get or create WebDriver with retry logic and resource management"""
        if self.driver:
            # Test if driver is still alive
            try:
                self.driver.current_url
                return self.driver
            except:
                # Driver is dead, clean up and create new one
                self._cleanup_driver()
        
        from selenium.webdriver.chrome.options import Options
        from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
        
        options = Options()
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--ignore-certificate-errors')
        # Reduce memory footprint
        options.add_argument('--js-flags=--max-old-space-size=256')
        
        # Setup Chrome service with explicit chromedriver path (for ARM and other platforms)
        service_kwargs = {}
        chromedriver_path = self._find_chromedriver()
        if chromedriver_path:
            service_kwargs['executable_path'] = chromedriver_path
        
        service = ChromeService(**service_kwargs)
        
        last_error = None
        for attempt in range(max_retries):
            try:
                self.driver = webdriver.Chrome(service=service, options=options)
                self.owns_driver = True
                return self.driver
            except (WebDriverException, SessionNotCreatedException) as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for resource exhaustion
                if 'resource temporarily unavailable' in error_str or 'would block' in error_str:
                    print(f"[!] System resource exhaustion detected (attempt {attempt+1}/{max_retries})")
                    # Wait longer for system to recover
                    import time
                    time.sleep(5 * (attempt + 1))
                    # Try to cleanup any zombie processes
                    self._cleanup_zombie_chrome()
                elif 'chrome instance exited' in error_str:
                    print(f"[!] Chrome crashed (attempt {attempt+1}/{max_retries})")
                    import time
                    time.sleep(2)
                else:
                    print(f"[!] WebDriver error (attempt {attempt+1}/{max_retries}): {str(e)[:100]}")
                    import time
                    time.sleep(1)
        
        # All retries failed
        raise Exception(f"Failed to create Chrome driver after {max_retries} attempts. Last error: {last_error}")
    
    def _cleanup_driver(self):
        """Cleanup current driver instance"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
    
    def _cleanup_zombie_chrome(self):
        """Attempt to kill zombie Chrome/ChromeDriver processes"""
        try:
            import subprocess
            import os
            # Don't use killall in production, but we can try to be gentle
            subprocess.run(['pkill', '-9', 'chrome'], stderr=subprocess.DEVNULL, timeout=2)
            subprocess.run(['pkill', '-9', 'chromedriver'], stderr=subprocess.DEVNULL, timeout=2)
            import time
            time.sleep(1)
        except:
            pass
    
    def _log_debug(self, message: str):
        """Add debug log entry"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.debug_logs.append(log_entry)
        if self.debug:
            print(f"[DEBUG] {message}")
    
    def _save_debug_screenshot(self, driver, name: str):
        """Save debug screenshot"""
        if not self.debug or not self.debug_dir:
            return
        
        import os
        os.makedirs(self.debug_dir, exist_ok=True)
        filepath = os.path.join(self.debug_dir, f"debug_{name}.png")
        try:
            driver.save_screenshot(filepath)
            self._log_debug(f"Screenshot saved: {filepath}")
        except Exception as e:
            self._log_debug(f"Failed to save screenshot: {e}")
    
    def _get_page_debug_info(self, driver) -> dict:
        """Get comprehensive debug info about the current page"""
        info = {
            'url': driver.current_url,
            'title': driver.title,
            'forms': [],
            'inputs': [],
            'selects': [],  # Dropdowns
            'buttons': [],
            'visible_text': '',
            'error_messages': []
        }
        
        try:
            # Get all forms
            forms = driver.find_elements(By.TAG_NAME, 'form')
            for form in forms:
                info['forms'].append({
                    'action': form.get_attribute('action'),
                    'method': form.get_attribute('method'),
                    'id': form.get_attribute('id'),
                    'class': form.get_attribute('class')
                })
            
            # Get all inputs
            inputs = driver.find_elements(By.TAG_NAME, 'input')
            for inp in inputs:
                if inp.is_displayed():
                    info['inputs'].append({
                        'type': inp.get_attribute('type'),
                        'name': inp.get_attribute('name'),
                        'id': inp.get_attribute('id'),
                        'placeholder': inp.get_attribute('placeholder'),
                        'value': inp.get_attribute('value')[:50] if inp.get_attribute('value') else None
                    })
            
            # Get all select dropdowns (important!)
            selects = driver.find_elements(By.TAG_NAME, 'select')
            for sel in selects:
                if sel.is_displayed():
                    options = []
                    try:
                        for opt in sel.find_elements(By.TAG_NAME, 'option'):
                            options.append({
                                'value': opt.get_attribute('value'),
                                'text': opt.text,
                                'selected': opt.is_selected()
                            })
                    except:
                        pass
                    info['selects'].append({
                        'name': sel.get_attribute('name'),
                        'id': sel.get_attribute('id'),
                        'options': options
                    })
            
            # Get all buttons
            buttons = driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                if btn.is_displayed():
                    info['buttons'].append({
                        'text': btn.text,
                        'type': btn.get_attribute('type'),
                        'id': btn.get_attribute('id')
                    })
            
            # Get visible text
            body = driver.find_element(By.TAG_NAME, 'body')
            info['visible_text'] = body.text[:2000]  # First 2000 chars
            
            # Look for error messages
            error_selectors = [
                ".error", ".alert-danger", ".alert-error", ".error-message",
                "[class*='error']", "[class*='fail']", "[class*='invalid']"
            ]
            for selector in error_selectors:
                try:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elems:
                        if elem.is_displayed() and elem.text.strip():
                            info['error_messages'].append(elem.text.strip()[:200])
                except:
                    pass
                    
        except Exception as e:
            info['debug_error'] = str(e)
        
        return info
    
    def _find_auth_type_dropdown(self, driver) -> Optional[Tuple[any, List[dict]]]:
        """
        Find authentication type dropdown (Network/Local/LDAP etc.)
        
        Returns:
            Tuple of (select_element, list of options) or None
        """
        from selenium.webdriver.support.ui import Select
        
        # Keywords that indicate auth type dropdowns (in name/id)
        auth_dropdown_keywords = [
            'auth', 'login', 'type', 'method', 'domain', 'realm',
            'authentication', 'logon', 'logintype', 'authtype'
        ]
        
        # Auth option keywords (what the options should contain)
        auth_option_keywords = ['local', 'network', 'ldap', 'domain', 'native', 'radius', 'ad', 'active']
        
        # Keywords that indicate this is NOT an auth dropdown (language, etc.)
        non_auth_keywords = [
            'language', 'lang', 'locale', 'country', 'region',
            'english', 'español', 'deutsch', 'français', 'italiano', 'português',
            'timezone', 'time', 'date', 'format'
        ]
        
        try:
            selects = driver.find_elements(By.TAG_NAME, 'select')
            candidates = []
            
            for sel in selects:
                if not sel.is_displayed():
                    continue
                
                sel_name = (sel.get_attribute('name') or '').lower()
                sel_id = (sel.get_attribute('id') or '').lower()
                
                # Get options text
                try:
                    options = sel.find_elements(By.TAG_NAME, 'option')
                    options_text = ' '.join([o.text.lower() for o in options])
                    
                    # Skip if this looks like a language dropdown
                    if any(kw in options_text for kw in non_auth_keywords):
                        if self.debug:
                            self._log_debug(f"Skipping dropdown (language/locale): {sel_name or sel_id}")
                        continue
                    
                    # Check if name/id suggests auth dropdown
                    is_auth_by_name = any(kw in sel_name or kw in sel_id for kw in auth_dropdown_keywords)
                    
                    # Check if options suggest auth dropdown
                    is_auth_by_options = any(kw in options_text for kw in auth_option_keywords)
                    
                    if is_auth_by_name or is_auth_by_options:
                        select_obj = Select(sel)
                        opt_list = []
                        for opt in select_obj.options:
                            opt_list.append({
                                'value': opt.get_attribute('value'),
                                'text': opt.text.strip(),
                                'element': opt
                            })
                        
                        # Prioritize by how many auth keywords match
                        score = sum(1 for kw in auth_option_keywords if kw in options_text)
                        candidates.append((score, sel, opt_list))
                        
                except Exception as e:
                    if self.debug:
                        self._log_debug(f"Error checking dropdown: {e}")
                    continue
            
            # Return the best candidate (highest score)
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                best = candidates[0]
                if self.debug:
                    self._log_debug(f"Selected auth dropdown with options: {[o['text'] for o in best[2]]}")
                return (best[1], best[2])
                    
        except Exception as e:
            if self.debug:
                self._log_debug(f"Error finding auth dropdown: {e}")
        
        return None
    
    def _get_auth_options_priority(self, options: List[dict]) -> List[dict]:
        """
        Sort auth options by priority (Local/Native first, then others)
        
        Args:
            options: List of dropdown options
            
        Returns:
            Sorted list with Local/Native options first
        """
        def get_priority(opt):
            text_lower = opt['text'].lower()
            
            # Local/Native auth is more likely to work with default creds
            for i, pref in enumerate(self.AUTH_TYPE_PREFERENCES):
                if pref in text_lower:
                    return i
            return 100  # Unknown options last
        
        return sorted(options, key=get_priority)
    
    def _try_show_login_form(self, driver) -> bool:
        """
        Try to click on login/sign-in elements to show hidden login forms.
        Some sites require clicking on "Login" or "Inicio de sesión" first.
        
        Returns:
            True if a login trigger was clicked, False otherwise
        """
        import time
        
        # First check if password field is already visible
        try:
            pwd_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            for pwd in pwd_fields:
                if pwd.is_displayed():
                    return False  # Form already visible, no need to click
        except:
            pass
        
        # Look for elements that might trigger login form display
        login_triggers = [
            # By text content (common login button texts in multiple languages)
            ("//*[contains(text(), 'Inicio de sesión')]", "Inicio de sesión"),
            ("//*[contains(text(), 'Iniciar sesión')]", "Iniciar sesión"),
            ("//*[contains(text(), 'Login')]", "Login"),
            ("//*[contains(text(), 'Log in')]", "Log in"),
            ("//*[contains(text(), 'Sign in')]", "Sign in"),
            ("//*[contains(text(), 'Sign In')]", "Sign In"),
            ("//a[contains(@href, 'login')]", "login link"),
            ("//button[contains(@class, 'login')]", "login button"),
            ("//*[@id='loginLink']", "loginLink"),
            ("//*[@id='signIn']", "signIn"),
        ]
        
        for xpath, trigger_name in login_triggers:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        # Don't click on input fields
                        if elem.tag_name.lower() not in ['input', 'textarea']:
                            if self.debug:
                                self._log_debug(f"Clicking on '{trigger_name}' to show login form")
                            elem.click()
                            time.sleep(1)  # Wait for form to appear
                            
                            # Verify password field is now visible
                            pwd_fields = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                            for pwd in pwd_fields:
                                if pwd.is_displayed():
                                    if self.debug:
                                        self._log_debug("Login form is now visible after click")
                                    return True
            except Exception as e:
                continue
        
        return False
    
    def _find_login_elements(self, driver) -> Tuple[Optional[any], Optional[any], Optional[any]]:
        """
        Find username, password, and submit elements on the page
        
        Returns:
            Tuple of (username_element, password_element, submit_element)
        """
        username_elem = None
        password_elem = None
        submit_elem = None
        
        # First, try to click on "Login" or "Inicio de sesión" if login form is hidden
        form_shown = self._try_show_login_form(driver)
        if form_shown:
            # Give the form more time to fully render after clicking
            time.sleep(1.5)
        
        # Find password field first (most reliable indicator of login form)
        password_selectors = [
            "input[type='password']",
            "input[name*='password' i]",
            "input[name*='pass' i]",
            "input[id*='password' i]",
            "#password",
            "#passwordInput",
        ]
        
        for selector in password_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        password_elem = elem
                        break
                if password_elem:
                    break
            except:
                continue
        
        # Find username field
        username_selectors = [
            "input[type='text'][name*='user' i]",
            "input[type='text'][name*='name' i]",
            "input[type='text'][name*='login' i]",
            "input[type='email']",
            "input[name*='email' i]",
            "input[id*='user' i]",
            "input[id*='login' i]",
            "#username",
            "#userName",
            "input[type='text']:not([name*='search' i])",
        ]
        
        for selector in username_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled() and elem != password_elem:
                        username_elem = elem
                        break
                if username_elem:
                    break
            except:
                continue
        
        # Find submit button
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button[name*='login' i]",  # ManageEngine uses loginButton
            "button[name*='submit' i]",
            "button[id*='login' i]",
            "button[id*='submit' i]",
            "input[name*='login' i]",
            "input[name*='logon' i]",
            "#btnLogin",
            "button.login-button",
            "button[ng-click*='login' i]",
            "button:not([type='button'])",  # Any button that's not explicitly type="button"
            "a[class*='login' i]",  # Anchor tags styled as buttons
            "a[class*='submit' i]",
            "a[id*='login' i]",
            "a[id*='submit' i]",
            "input[type='button'][value*='login' i]",  # Input buttons with login text
            "input[type='button'][value*='submit' i]",
            "input[type='button'][value*='log in' i]",
            "input[type='button'][value*='sign in' i]",
        ]
        
        for selector in submit_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled():
                        submit_elem = elem
                        break
                if submit_elem:
                    break
            except:
                continue
        
        # Fallback: find any button with login-related text
        if not submit_elem:
            try:
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                for btn in buttons:
                    btn_text = btn.text.lower()
                    if any(word in btn_text for word in ['login', 'sign in', 'submit', 'enter', 'log in']):
                        if btn.is_displayed():
                            submit_elem = btn
                            break
            except:
                pass
        
        # Fallback: find anchor tags with login-related text
        if not submit_elem:
            try:
                anchors = driver.find_elements(By.TAG_NAME, 'a')
                for anchor in anchors:
                    anchor_text = anchor.text.lower()
                    if any(word in anchor_text for word in ['login', 'sign in', 'submit', 'enter', 'log in']):
                        if anchor.is_displayed():
                            submit_elem = anchor
                            break
            except:
                pass
        
        # Fallback: find input buttons with login-related value
        if not submit_elem:
            try:
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='button']")
                for inp in inputs:
                    inp_value = (inp.get_attribute('value') or '').lower()
                    if any(word in inp_value for word in ['login', 'sign in', 'submit', 'enter', 'log in']):
                        if inp.is_displayed():
                            submit_elem = inp
                            break
            except:
                pass
        
        return username_elem, password_elem, submit_elem
    
    def test_credentials(self, 
                        url: str, 
                        credentials: List[Dict],
                        reuse_driver: bool = True) -> Dict:
        """
        Test credentials against a login page using Selenium
        
        Args:
            url: URL of the login page
            credentials: List of dicts with 'username' and 'password'
            reuse_driver: Whether to reuse the driver between tests
            
        Returns:
            Dict with test results
        """
        result = {
            'testable': False,
            'tested': False,
            'method': 'selenium',
            'credentials_tested': 0,
            'successful_count': 0,
            'failed_count': 0,
            'successful_credentials': [],
            'failed_credentials': [],
            'errors': []
        }
        
        if not credentials:
            result['errors'].append("No credentials provided")
            return result
        
        # Try to get driver with error handling
        try:
            driver = self._get_driver()
        except Exception as e:
            error_msg = f"Failed to initialize Chrome driver: {str(e)[:200]}"
            print(f"[!] {error_msg}")
            result['errors'].append(error_msg)
            result['testable'] = False
            # Mark all credentials as failed
            for cred in credentials:
                result['failed_credentials'].append({
                    'username': cred.get('username', ''),
                    'password': cred.get('password', ''),
                    'reason': 'Chrome driver initialization failed'
                })
            return result
        
        try:
            for i, cred in enumerate(credentials):
                username = cred.get('username', '')
                password = cred.get('password', '')
                
                # Note: password can be empty (common for printers like Ricoh)
                # Only skip if username is empty
                if not username:
                    result['failed_credentials'].append({
                        'username': username,
                        'password': password,
                        'reason': 'Empty username'
                    })
                    continue
                
                print(f"      [*] Testing {i+1}/{len(credentials)}: {username}:{password}")
                
                try:
                    success, details = self._test_single_credential(
                        driver, url, username, password
                    )
                    
                    result['credentials_tested'] += 1
                    result['tested'] = True
                    result['testable'] = True
                    
                    if success:
                        result['successful_count'] += 1
                        result['successful_credentials'].append({
                            'username': username,
                            'password': password,
                            'source': cred.get('source', 'unknown'),  # Preserve original source
                            'details': details
                        })
                        print(f"      [+] SUCCESS: {username}:{password}")
                    else:
                        result['failed_count'] += 1
                        result['failed_credentials'].append({
                            'username': username,
                            'password': password,
                            'source': cred.get('source', 'unknown'),
                            'reason': details.get('reason', 'Login failed')
                        })
                        
                except Exception as e:
                    result['errors'].append(f"Error testing {username}: {str(e)}")
                    result['failed_credentials'].append({
                        'username': username,
                        'password': password,
                        'reason': str(e)
                    })
                
                # Small delay between attempts
                if i < len(credentials) - 1:
                    time.sleep(1)
        
        finally:
            if self.owns_driver and not reuse_driver:
                driver.quit()
                self.driver = None
        
        # Add debug logs to result
        if self.debug:
            result['debug_logs'] = self.debug_logs
            self._save_debug_log()
        
        return result
    
    def _save_debug_log(self):
        """Save debug log to file"""
        if not self.debug_dir or not self.debug_logs:
            return
        
        import os
        os.makedirs(self.debug_dir, exist_ok=True)
        filepath = os.path.join(self.debug_dir, "credential_test_debug.log")
        
        try:
            with open(filepath, 'w') as f:
                f.write("=== Credential Testing Debug Log ===\n\n")
                for log in self.debug_logs:
                    f.write(f"{log}\n")
            print(f"[*] Debug log saved: {filepath}")
        except Exception as e:
            print(f"[!] Failed to save debug log: {e}")
    
    def _handle_alert(self, driver) -> Optional[str]:
        """
        Handle JavaScript alert if present
        
        Returns:
            Alert text if alert was present, None otherwise
        """
        try:
            from selenium.webdriver.common.alert import Alert
            from selenium.common.exceptions import NoAlertPresentException
            
            alert = driver.switch_to.alert
            alert_text = alert.text
            alert.accept()  # Dismiss the alert
            return alert_text
        except NoAlertPresentException:
            return None
        except Exception:
            return None
    
    def _try_auth_options(self, driver, url: str, username: str, password: str, 
                          auth_dropdown: Tuple, current_option_idx: int = 0) -> Tuple[bool, Dict]:
        """
        Try different authentication type options if initial attempt fails
        
        Args:
            driver: Selenium WebDriver
            url: Login URL
            username: Username to test
            password: Password to test
            auth_dropdown: Tuple of (select_element, options_list)
            current_option_idx: Current option index to skip
            
        Returns:
            Tuple of (success, details)
        """
        from selenium.webdriver.support.ui import Select
        
        select_elem, options = auth_dropdown
        sorted_options = self._get_auth_options_priority(options)
        
        # Track if we've seen explicit failures - if so, require strong success indicators
        had_explicit_failures = False
        
        for i, opt in enumerate(sorted_options):
            if i == current_option_idx:
                continue  # Skip already-tried option
            
            if self.debug:
                self._log_debug(f"Trying auth type: {opt['text']}")
            
            try:
                # Refresh page to reset form
                driver.get(url)
                time.sleep(self.delay)
                
                # Switch to frame if needed
                self._switch_to_login_frame(driver)
                
                # Find and select auth dropdown
                auth_dd = self._find_auth_type_dropdown(driver)
                if not auth_dd:
                    continue
                
                select = Select(auth_dd[0])
                select.select_by_visible_text(opt['text'])
                time.sleep(0.5)
                
                # Find login elements again
                username_elem, password_elem, submit_elem = self._find_login_elements(driver)
                if not all([username_elem, password_elem, submit_elem]):
                    continue
                
                # Fill and submit
                username_elem.clear()
                username_elem.send_keys(username)
                password_elem.clear()
                password_elem.send_keys(password)
                submit_elem.click()
                
                time.sleep(self.delay)
                
                # Handle alert
                alert_text = self._handle_alert(driver)
                if alert_text:
                    alert_lower = alert_text.lower()
                    if any(fail in alert_lower for fail in self.FAILURE_INDICATORS):
                        had_explicit_failures = True
                        continue  # Try next option
                
                # Check for success - pass flag if we had explicit failures
                success, details = self._analyze_login_result(driver, url, {'had_prior_failures': had_explicit_failures})
                
                # Track if this attempt had explicit failures
                page_text = driver.page_source.lower()
                if any(indicator in page_text for indicator in ['incorrect', 'invalid', 'failed']):
                    had_explicit_failures = True
                
                if success:
                    details['auth_type_used'] = opt['text']
                    return True, details
                    
            except Exception as e:
                if self.debug:
                    self._log_debug(f"Error trying auth option {opt['text']}: {e}")
                continue
        
        return False, {'reason': 'All auth type options failed'}
    
    def _navigate_to_login_page(self, driver, base_url: str) -> bool:
        """
        Navigate to the actual login page for devices that use framesets or redirects.
        
        Some devices (like Ricoh printers) have the login form on a separate URL,
        not in the main page or its frames. This method handles known patterns.
        
        Returns:
            True if navigated to a login page, False otherwise
        """
        page_source = driver.page_source.lower()
        current_url = driver.current_url
        
        # Ricoh Web Image Monitor - has frameset, login is on authForm.cgi
        if 'web image monitor' in page_source or 'mainframe.cgi' in page_source:
            # Try known Ricoh login URLs
            ricoh_login_paths = [
                '/web/guest/es/websys/webArch/authForm.cgi',
                '/web/guest/en/websys/webArch/authForm.cgi',
                '/web/guest/ja/websys/webArch/authForm.cgi',
                '/web/guest/websys/webArch/authForm.cgi',
            ]
            
            for path in ricoh_login_paths:
                try:
                    login_url = urljoin(base_url, path)
                    if self.debug:
                        self._log_debug(f"Trying Ricoh login URL: {login_url}")
                    driver.get(login_url)
                    time.sleep(1)
                    
                    # Check if we got a login form
                    username_elem, password_elem, _ = self._find_login_elements(driver)
                    if username_elem and password_elem:
                        if self.debug:
                            self._log_debug(f"Found login form at: {login_url}")
                        return True
                except Exception as e:
                    if self.debug:
                        self._log_debug(f"Failed to navigate to {path}: {e}")
                    continue
        
        # Try clicking on login links in the page
        login_link_patterns = [
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login')]",
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'inicio de sesión')]",
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'iniciar sesión')]",
            "//a[contains(@href, 'login')]",
            "//a[contains(@href, 'auth')]",
        ]
        
        for pattern in login_link_patterns:
            try:
                links = driver.find_elements(By.XPATH, pattern)
                for link in links:
                    if link.is_displayed():
                        if self.debug:
                            self._log_debug(f"Clicking login link: {link.text}")
                        link.click()
                        time.sleep(1.5)
                        
                        username_elem, password_elem, _ = self._find_login_elements(driver)
                        if username_elem and password_elem:
                            return True
                        # If no form found, go back and try next link
                        driver.get(current_url)
                        time.sleep(0.5)
            except:
                continue
        
        return False
    
    def _switch_to_login_frame(self, driver) -> bool:
        """
        Switch to frame containing login form if needed
        
        Returns:
            True if switched to a frame, False if stayed in main content
        """
        # Check if we can find login elements in main content
        username_elem, password_elem, _ = self._find_login_elements(driver)
        if username_elem and password_elem:
            return False
        
        # Try frames
        frames = []
        try:
            frames.extend(driver.find_elements(By.TAG_NAME, 'frame'))
            frames.extend(driver.find_elements(By.TAG_NAME, 'iframe'))
        except:
            pass
        
        for frame in frames:
            try:
                driver.switch_to.frame(frame)
                username_elem, password_elem, _ = self._find_login_elements(driver)
                if username_elem and password_elem:
                    return True
                driver.switch_to.default_content()
            except:
                try:
                    driver.switch_to.default_content()
                except:
                    pass
        
        return False
    
    def _test_single_credential(self, driver, url: str, username: str, password: str) -> Tuple[bool, Dict]:
        """
        Test a single credential
        
        Returns:
            Tuple of (success: bool, details: dict)
        """
        details = {}
        
        # Navigate to login page
        driver.get(url)
        
        # Smart wait for Angular/SPA pages: wait for password field to appear
        try:
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # Wait for any password field to be present and visible (indicates login form is ready)
            WebDriverWait(driver, self.timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
            )
            # Give Angular a bit more time to fully render
            time.sleep(1)
        except TimeoutException:
            # Fallback: wait the standard delay
            time.sleep(self.delay)
        
        initial_url = driver.current_url
        
        # Debug: capture page info before login attempt
        if self.debug:
            self._log_debug(f"Testing {username}:*** on {url}")
            details['page_before'] = self._get_page_debug_info(driver)
            self._save_debug_screenshot(driver, f"before_{username}")
            
            # Log important findings
            if details['page_before'].get('selects'):
                self._log_debug(f"Found {len(details['page_before']['selects'])} dropdown(s):")
                for sel in details['page_before']['selects']:
                    self._log_debug(f"  - Dropdown '{sel.get('name') or sel.get('id')}': {[o.get('text') for o in sel.get('options', [])]}")
        
        # Try to find login elements (check frames if necessary)
        username_elem, password_elem, submit_elem = self._find_login_elements(driver)
        
        # If not found in main page, check frames/iframes
        if not username_elem or not password_elem:
            if self.debug:
                self._log_debug("Elements not found in main page, checking frames...")
            
            frames_to_check = []
            
            # Check for framesets (old style)
            try:
                frames = driver.find_elements(By.TAG_NAME, 'frame')
                frames_to_check.extend(frames)
            except:
                pass
            
            # Check for iframes
            try:
                iframes = driver.find_elements(By.TAG_NAME, 'iframe')
                frames_to_check.extend(iframes)
            except:
                pass
            
            if self.debug:
                self._log_debug(f"Found {len(frames_to_check)} frame(s)/iframe(s)")
            
            for i, frame in enumerate(frames_to_check):
                try:
                    if self.debug:
                        frame_src = frame.get_attribute('src') or frame.get_attribute('name') or f"frame_{i}"
                        self._log_debug(f"Switching to frame: {frame_src}")
                    
                    driver.switch_to.frame(frame)
                    username_elem, password_elem, submit_elem = self._find_login_elements(driver)
                    
                    if username_elem and password_elem:
                        if self.debug:
                            self._log_debug(f"Found login elements in frame!")
                        break
                    else:
                        driver.switch_to.default_content()
                except Exception as e:
                    if self.debug:
                        self._log_debug(f"Error checking frame: {e}")
                    try:
                        driver.switch_to.default_content()
                    except:
                        pass
        
        # If still not found, try navigating to known login URLs (e.g., Ricoh framesets)
        if not username_elem or not password_elem:
            if self.debug:
                self._log_debug("Elements not found in frames, trying known login URLs...")
            
            driver.switch_to.default_content()  # Ensure we're in main content
            if self._navigate_to_login_page(driver, url):
                # Found login page, try finding elements again
                username_elem, password_elem, submit_elem = self._find_login_elements(driver)
                if self.debug and username_elem and password_elem:
                    self._log_debug("Found login elements after navigating to login URL!")
        
        if not username_elem:
            details['reason'] = 'Could not find username field'
            if self.debug:
                self._log_debug("ERROR: Could not find username field")
                details['page_debug'] = self._get_page_debug_info(driver)
            return False, details
        
        if not password_elem:
            details['reason'] = 'Could not find password field'
            if self.debug:
                self._log_debug("ERROR: Could not find password field")
            return False, details
        
        # If no submit button found, try fallback methods
        if not submit_elem:
            if self.debug:
                self._log_debug("No submit button found, trying fallback methods...")
            
            # Fallback 1: Try to find and submit the form directly
            try:
                form = password_elem.find_element(By.XPATH, "./ancestor::form[1]")
                if form:
                    if self.debug:
                        self._log_debug("Found form element, will submit directly")
                    submit_elem = form  # Use form as submit element
                    details['submit_method'] = 'form_submit'
            except:
                pass
            
            # Fallback 2: If still no submit method, we'll use Enter key
            if not submit_elem:
                if self.debug:
                    self._log_debug("No form found, will use Enter key on password field")
                details['submit_method'] = 'enter_key'
        
        if not submit_elem and details.get('submit_method') != 'enter_key':
            details['reason'] = 'Could not find submit button or form'
            if self.debug:
                self._log_debug("ERROR: Could not find submit button or form")
            return False, details
        
        if self.debug:
            self._log_debug(f"Found elements - username: {username_elem.get_attribute('name')}, password: {password_elem.get_attribute('name')}")
        
        # Check for auth type dropdown (Network/Local/LDAP etc.)
        auth_dropdown = self._find_auth_type_dropdown(driver)
        if auth_dropdown:
            select_elem, options = auth_dropdown
            details['auth_dropdown'] = auth_dropdown
            details['auth_options'] = [o['text'] for o in options]
            
            if self.debug:
                self._log_debug(f"Found auth type dropdown with options: {details['auth_options']}")
            
            # Try to select "Local" or similar option first (more likely to work with default creds)
            from selenium.webdriver.support.ui import Select
            try:
                select = Select(select_elem)
                current_option = select.first_selected_option.text
                details['current_auth_option'] = current_option
                
                # Check if we should switch to a "local" type auth
                sorted_opts = self._get_auth_options_priority(options)
                if sorted_opts and sorted_opts[0]['text'].lower() != current_option.lower():
                    preferred = sorted_opts[0]['text']
                    if self.debug:
                        self._log_debug(f"Switching auth type from '{current_option}' to '{preferred}'")
                    select.select_by_visible_text(preferred)
                    time.sleep(0.5)
                    details['auth_type_switched_to'] = preferred
            except Exception as e:
                if self.debug:
                    self._log_debug(f"Could not switch auth type: {e}")
        
        try:
            # Clear and fill username
            username_elem.clear()
            username_elem.send_keys(username)
            time.sleep(0.3)
            
            # Clear and fill password
            password_elem.clear()
            password_elem.send_keys(password)
            time.sleep(0.3)
            
            # Submit the form
            submit_method = details.get('submit_method', 'click')
            if submit_method == 'form_submit':
                # Submit the form directly
                submit_elem.submit()
            elif submit_method == 'enter_key':
                # Press Enter on password field
                from selenium.webdriver.common.keys import Keys
                password_elem.send_keys(Keys.RETURN)
            else:
                # Click submit button (default)
                submit_elem.click()
            
            # Wait for response and handle alerts
            time.sleep(self.delay)
            
            # Check for JavaScript alerts (common in older apps)
            alert_text = self._handle_alert(driver)
            if alert_text:
                details['alert_message'] = alert_text
                if self.debug:
                    self._log_debug(f"Alert detected: {alert_text}")
                
                # Check if alert indicates failure
                alert_lower = alert_text.lower()
                if any(fail in alert_lower for fail in self.FAILURE_INDICATORS):
                    details['reason'] = f'Login failed (alert): {alert_text}'
                    return False, details
            
            # Debug: capture page info after login attempt
            if self.debug:
                try:
                    self._save_debug_screenshot(driver, f"after_{username}")
                    details['page_after'] = self._get_page_debug_info(driver)
                    
                    if details['page_after'].get('error_messages'):
                        self._log_debug(f"Error messages on page: {details['page_after']['error_messages']}")
                except Exception as e:
                    self._log_debug(f"Error capturing after state: {e}")
            
            # Analyze result
            success, result_details = self._analyze_login_result(driver, initial_url, details)
            details.update(result_details)
            
            # If failed and there's an auth type dropdown, try other options
            if not success and details.get('auth_dropdown'):
                if self.debug:
                    self._log_debug("Login failed, trying other auth type options...")
                
                alt_success, alt_details = self._try_auth_options(
                    driver, url, username, password,
                    details['auth_dropdown'], 
                    details.get('current_auth_option_idx', 0)
                )
                
                if alt_success:
                    details.update(alt_details)
                    return True, details
            
            return success, details
            
        except ElementNotInteractableException as e:
            details['reason'] = f'Element not interactable: {e}'
            return False, details
        except Exception as e:
            details['reason'] = f'Error during login: {e}'
            return False, details
    
    def _analyze_login_result(self, driver, initial_url: str, details: Dict) -> Tuple[bool, Dict]:
        """
        Analyze the page after login attempt to determine success/failure
        """
        try:
            current_url = driver.current_url
            page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
        except:
            # May need to switch back to frame or handle frameset pages
            try:
                driver.switch_to.default_content()
                current_url = driver.current_url
                
                # Check if we're now on a different page (possible success indicator)
                # For frameset pages, try to get the page source instead
                try:
                    page_text = driver.find_element(By.TAG_NAME, 'body').text.lower()
                except:
                    # Body might be empty in frameset pages
                    page_source = driver.page_source.lower()
                    
                    # If URL changed significantly and no login keywords, likely success
                    if 'login' not in current_url.lower() and 'auth' not in current_url.lower():
                        # Check for logout/session indicators in page source
                        if any(ind in page_source for ind in ['logout', 'session', 'menu', 'home', 'main']):
                            print(f"        [+] SUCCESS: Login appears successful (URL changed, no login page)")
                            details['reason'] = 'URL changed away from login, session indicators found'
                            return True, details
                    
                    # If we still can't read the page, check URL for success hints
                    if current_url != initial_url:
                        still_on_login = any(kw in current_url.lower() for kw in ['login', 'auth', 'signin'])
                        if not still_on_login:
                            print(f"        [+] SUCCESS: URL changed from login page (frameset detected)")
                            details['reason'] = 'URL changed from login page (frameset page)'
                            return True, details
                    
                    details['reason'] = 'Could not read page after login'
                    return False, details
            except:
                details['reason'] = 'Could not read page after login'
                return False, details
        
        details['final_url'] = current_url
        
        # FIRST: Check for EXPLICIT failure messages (these ALWAYS mean failure)
        explicit_failures = [msg for msg in self.EXPLICIT_FAILURE_MESSAGES if msg in page_text]
        if explicit_failures:
            print(f"        [!] Explicit failure message found: {explicit_failures[0]}")
            if self.debug:
                self._log_debug(f"Error messages on page: {explicit_failures}")
            details['reason'] = f'Explicit error message: {explicit_failures[0]}'
            return False, details
        
        # Count indicators
        failure_count = sum(1 for indicator in self.FAILURE_INDICATORS if indicator in page_text)
        success_count = sum(1 for indicator in self.SUCCESS_INDICATORS if indicator in page_text)
        
        # Always show analysis info for transparency
        matched_failures = [i for i in self.FAILURE_INDICATORS if i in page_text]
        matched_success = [i for i in self.SUCCESS_INDICATORS if i in page_text]
        print(f"        [*] URL: {initial_url} -> {current_url}")
        print(f"        [*] Analysis: failures={failure_count} {matched_failures[:3] if matched_failures else ''}, successes={success_count} {matched_success[:3] if matched_success else ''}")
        
        if self.debug:
            self._log_debug(f"Analysis: failures={failure_count}, successes={success_count}")
            if matched_success:
                self._log_debug(f"Success indicators found: {matched_success[:5]}")
        
        # Check 1: URL changed away from login page (but verify no failure messages first)
        url_changed = current_url != initial_url
        still_on_login = any(word in current_url.lower() for word in ['login', 'signin', 'auth', 'logon', 'security_check'])
        
        # If URL changed but we have failure indicators, don't trust the redirect
        if url_changed and not still_on_login:
            if failure_count > 0:
                print(f"        [-] FAILED: URL changed but failure message detected ({matched_failures[:2]})")
                details['reason'] = f'URL redirected but login failed: {matched_failures[0]}'
                return False, details
            # URL changed away from login - likely success, but verify with other checks
            # Don't return immediately, continue to check for success indicators
            pass
        
        # Check 2: Clear failure messages
        # Only treat as failure if we have multiple failure indicators OR explicit failure messages
        # Single generic words like "error" might be false positives
        if failure_count >= 2 or explicit_failures:
            # If we have strong failures, only succeed if we have STRONG success indicators
            if success_count >= 3:  # Need multiple success indicators to override
                print(f"        [+] SUCCESS: Success indicators ({success_count}) override failures ({failure_count})")
                details['reason'] = f'Success indicators ({success_count}) override failures ({failure_count})'
                return True, details
            else:
                print(f"        [-] FAILED: Multiple failure indicators detected ({failure_count})")
                details['reason'] = f'Multiple failure indicators detected ({failure_count})'
                return False, details
        elif failure_count == 1:
            # Single failure indicator - check for strong success signals to override
            # Require at least 2 success indicators or logout link to override
            if success_count >= 2:
                print(f"        [+] SUCCESS: Success indicators ({success_count}) found, overriding single failure")
                details['reason'] = f'Success indicators ({success_count}) override single failure'
                return True, details
            else:
                print(f"        [-] FAILED: Single failure indicator ({matched_failures}), insufficient success signals")
                details['reason'] = f'Login failed: {matched_failures[0] if matched_failures else "error detected"}'
                return False, details
        
        # Check 3: Success indicators (only if no failures)
        if success_count >= 1 and failure_count == 0:
            print(f"        [+] SUCCESS: Success indicators found ({success_count})")
            details['reason'] = f'Success indicators found ({success_count})'
            return True, details
        
        # Check 4: Logout link present (strong indicator of logged in)
        try:
            logout_patterns = [
                "//a[contains(translate(text(), 'LOGOUT', 'logout'), 'logout')]",
                "//a[contains(translate(text(), 'SIGNOUT', 'signout'), 'sign out')]",
                "//a[contains(translate(text(), 'CERRAR', 'cerrar'), 'cerrar sesión')]",  # Spanish
                "//button[contains(translate(text(), 'LOGOUT', 'logout'), 'logout')]",
                "//*[contains(@href, 'logout')]",
                "//*[contains(@ng-click, 'logout')]",
            ]
            for pattern in logout_patterns:
                try:
                    elems = driver.find_elements(By.XPATH, pattern)
                    if elems:
                        print(f"        [+] SUCCESS: Logout link found - user is logged in")
                        details['reason'] = 'Logout link found - user is logged in'
                        return True, details
                except:
                    continue
        except:
            pass
        
        # Check 5: Page content changed significantly (admin/settings content appeared)
        admin_keywords = ['admin', 'settings', 'configuration', 'configuración', 'management', 
                         'panel', 'dashboard', 'device', 'dispositivo', 'system', 'sistema']
        admin_count = sum(1 for kw in admin_keywords if kw in page_text)
        if admin_count >= 2 and failure_count == 0:
            print(f"        [+] SUCCESS: Admin content detected ({admin_count} keywords)")
            details['reason'] = f'Admin content detected ({admin_count} keywords)'
            return True, details
        
        # Check 6: Still on login page with no clear success
        if still_on_login and success_count == 0:
            print(f"        [-] FAILED: Still on login page (URL contains login keywords)")
            details['reason'] = 'Still on login page'
            return False, details
        
        # Check 7: Page changed significantly but unclear (only if NO failures AND URL changed away from login)
        if url_changed and not still_on_login and failure_count == 0:
            # If we had prior explicit failures in earlier attempts, require strong success indicators
            if details.get('had_prior_failures'):
                print(f"        [-] FAILED: URL changed but had prior failures, no strong success indicators")
                details['reason'] = 'URL changed but had prior failures, no strong success indicators'
                return False, details
            # URL changed away from login, no failure messages - likely success
            print(f"        [+] SUCCESS: URL changed away from login, no failure detected")
            details['reason'] = 'URL changed away from login, no failure detected'
            return True, details
        
        # Default: assume failure if no clear success
        if url_changed:
            print(f"        [-] FAILED: URL changed but no clear success indicators")
            details['reason'] = 'URL changed but no clear success indicators'
        else:
            print(f"        [-] FAILED: No clear success indicators (URL unchanged, no success keywords)")
            details['reason'] = 'No clear success indicators'
        return False, details
    
    def cleanup(self):
        """Cleanup WebDriver if we own it"""
        if self.owns_driver and self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

