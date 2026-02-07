#!/usr/bin/env python3
"""
Credential Tester for EyeWitness
Tests default credentials against identified login forms
"""

import time
import ssl
import re
import urllib.parse
import urllib.request
from typing import Optional, Dict, List, Tuple
from urllib.request import Request, urlopen, HTTPError, URLError
from urllib.parse import urljoin
import http.cookiejar


class CredentialTestResult:
    """Result of a credential test"""
    def __init__(self):
        self.credentials_tested: List[Dict] = []
        self.successful_credentials: List[Dict] = []
        self.failed_credentials: List[Dict] = []
        self.test_errors: List[str] = []
        self.auth_endpoint: Optional[str] = None
        self.auth_method: Optional[str] = None
        self.testable: bool = False
        self.tested: bool = False
    
    def add_success(self, username: str, password: str, response_info: Dict = None):
        """Record successful credential"""
        cred = {
            'username': username,
            'password': password,
            'response_info': response_info or {}
        }
        self.successful_credentials.append(cred)
        self.credentials_tested.append({**cred, 'success': True})
    
    def add_failure(self, username: str, password: str, reason: str = None):
        """Record failed credential"""
        cred = {
            'username': username,
            'password': password,
            'reason': reason
        }
        self.failed_credentials.append(cred)
        self.credentials_tested.append({**cred, 'success': False})
    
    def add_error(self, error_msg: str):
        """Record test error"""
        self.test_errors.append(error_msg)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'testable': self.testable,
            'tested': self.tested,
            'auth_endpoint': self.auth_endpoint,
            'auth_method': self.auth_method,
            'credentials_tested': len(self.credentials_tested),
            'successful_count': len(self.successful_credentials),
            'failed_count': len(self.failed_credentials),
            'successful_credentials': self.successful_credentials,
            'failed_credentials': self.failed_credentials,
            'errors': self.test_errors
        }


class CredentialTester:
    """Tests credentials against login forms"""
    
    # Common failure indicators in different languages
    FAILURE_INDICATORS = [
        'invalid', 'incorrect', 'wrong', 'failed', 'error', 'denied',
        'unauthorized', 'bad credentials', 'login failed', 'authentication failed',
        'access denied', 'invalid username', 'invalid password', 'try again',
        'usuario incorrecto', 'contraseña incorrecta', 'acceso denegado',  # Spanish
        'échec', 'incorrect', 'invalide',  # French
        'fehler', 'ungültig',  # German
    ]
    
    # Common success indicators
    SUCCESS_INDICATORS = [
        'dashboard', 'welcome', 'logout', 'sign out', 'log out',
        'profile', 'settings', 'account', 'home', 'main', 'admin',
        'control panel', 'configuration', 'management', 'session',
        'successfully', 'logged in', 'authenticated',
    ]
    
    def __init__(self, timeout: int = 10, delay: float = 1.0, user_agent: str = None):
        """
        Initialize credential tester
        
        Args:
            timeout: Request timeout in seconds
            delay: Delay between requests in seconds
            user_agent: Custom user agent string
        """
        self.timeout = timeout
        self.delay = delay
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def _create_opener(self, cookie_jar: http.cookiejar.CookieJar = None):
        """Create a URL opener with cookie and SSL support"""
        if cookie_jar is None:
            cookie_jar = http.cookiejar.CookieJar()
        
        # Handler for redirects that preserves cookies
        redirect_handler = urllib.request.HTTPRedirectHandler()
        
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=self.ssl_context),
            redirect_handler
        )
        return opener, cookie_jar
    
    def _fetch_csrf_token(self, base_url: str, opener, csrf_field_name: str = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch fresh CSRF token from the login page
        
        Args:
            base_url: URL of the login page
            opener: urllib opener with cookie support
            csrf_field_name: Known CSRF field name (optional)
            
        Returns:
            Tuple of (csrf_field_name, csrf_token_value)
        """
        try:
            request = Request(base_url)
            request.add_header('User-Agent', self.user_agent)
            request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
            
            response = opener.open(request, timeout=self.timeout)
            html = response.read().decode('utf-8', errors='ignore')
            
            # Common CSRF token patterns
            csrf_patterns = [
                # Hidden input fields with common names
                r'<input[^>]+name=["\']?(_?csrf[_-]?token|csrf|_token|authenticity_token|__RequestVerificationToken|csrfmiddlewaretoken|_csrf)["\']?[^>]+value=["\']?([^"\'>\s]+)["\']?',
                r'<input[^>]+value=["\']?([^"\'>\s]+)["\']?[^>]+name=["\']?(_?csrf[_-]?token|csrf|_token|authenticity_token|__RequestVerificationToken|csrfmiddlewaretoken|_csrf)["\']?',
                # Meta tags
                r'<meta[^>]+name=["\']?csrf-token["\']?[^>]+content=["\']?([^"\']+)["\']?',
                r'<meta[^>]+content=["\']?([^"\']+)["\']?[^>]+name=["\']?csrf-token["\']?',
            ]
            
            for pattern in csrf_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 2:
                        # Could be (name, value) or (value, name)
                        if groups[0] and len(groups[0]) > 20:  # Token is typically longer
                            return groups[1], groups[0]
                        else:
                            return groups[0], groups[1]
                    elif len(groups) == 1:
                        # Meta tag pattern - csrf-token is the name
                        return 'csrf-token', groups[0]
            
            # If a specific CSRF field name was provided, look for it
            if csrf_field_name:
                pattern = rf'<input[^>]+name=["\']?{re.escape(csrf_field_name)}["\']?[^>]+value=["\']?([^"\'>\s]+)["\']?'
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    return csrf_field_name, match.group(1)
                    
        except Exception as e:
            print(f"[!] Error fetching CSRF token: {e}")
        
        return None, None
    
    def test_credentials(self, 
                        base_url: str,
                        login_form: Dict,
                        credentials: List[Dict],
                        cookies: Optional[List] = None) -> CredentialTestResult:
        """
        Test credentials against a login form
        
        Args:
            base_url: Base URL of the application
            login_form: Login form dictionary (from FormAnalyzer)
            credentials: List of credential dicts with 'username' and 'password'
            cookies: Optional cookies to include
            
        Returns:
            CredentialTestResult object
        """
        result = CredentialTestResult()
        result.testable = True
        
        if not login_form or not credentials:
            result.testable = False
            result.add_error("No login form or credentials provided")
            return result
        
        # Get authentication endpoint
        action = login_form.get('action', '')
        if action.startswith('http'):
            auth_url = action
        else:
            auth_url = urljoin(base_url, action) if action else base_url
        
        result.auth_endpoint = auth_url
        result.auth_method = login_form.get('method', 'POST')
        
        username_field = login_form.get('username_field')
        password_field = login_form.get('password_field')
        
        if not username_field or not password_field:
            result.testable = False
            result.add_error("Login form missing username or password field")
            return result
        
        # Test each credential
        result.tested = True
        
        for cred in credentials:
            username = cred.get('username', '')
            password = cred.get('password', '')
            
            if not username or not password:
                result.add_failure(username or 'empty', password or 'empty', "Empty username or password")
                continue
            
            # Add delay between requests
            if self.delay > 0:
                time.sleep(self.delay)
            
            try:
                success, response_info = self._test_single_credential(
                    base_url=base_url,
                    auth_url=auth_url,
                    method=result.auth_method,
                    username_field=username_field,
                    password_field=password_field,
                    username=username,
                    password=password,
                    login_form=login_form,
                    cookies=cookies
                )
                
                if success:
                    result.add_success(username, password, response_info)
                    print(f"[+] SUCCESS: {base_url} - {username}:{password}")
                else:
                    result.add_failure(username, password, response_info.get('reason', 'Login failed'))
                    
            except Exception as e:
                error_msg = f"Error testing {username}:{password} - {str(e)}"
                result.add_error(error_msg)
                result.add_failure(username, password, str(e))
        
        return result
    
    def _test_single_credential(self,
                               base_url: str,
                               auth_url: str,
                               method: str,
                               username_field: str,
                               password_field: str,
                               username: str,
                               password: str,
                               login_form: Dict,
                               cookies: Optional[List] = None) -> Tuple[bool, Dict]:
        """
        Test a single credential
        
        Returns:
            Tuple of (success: bool, response_info: dict)
        """
        response_info = {}
        
        # Create a fresh opener with cookie jar for this attempt
        opener, cookie_jar = self._create_opener()
        
        # Add initial cookies if provided
        if cookies:
            for c in cookies:
                cookie = http.cookiejar.Cookie(
                    version=0, name=c.get('name', ''), value=c.get('value', ''),
                    port=None, port_specified=False,
                    domain=c.get('domain', ''), domain_specified=bool(c.get('domain')),
                    domain_initial_dot=c.get('domain', '').startswith('.'),
                    path=c.get('path', '/'), path_specified=bool(c.get('path')),
                    secure=c.get('secure', False), expires=None, discard=True,
                    comment=None, comment_url=None, rest={}, rfc2109=False
                )
                cookie_jar.set_cookie(cookie)
        
        # Step 1: Fetch fresh CSRF token from login page
        csrf_field = login_form.get('csrf_token')
        csrf_value = login_form.get('csrf_value')
        
        # Try to get a fresh CSRF token
        fresh_csrf_field, fresh_csrf_value = self._fetch_csrf_token(base_url, opener, csrf_field)
        if fresh_csrf_value:
            csrf_field = fresh_csrf_field
            csrf_value = fresh_csrf_value
        
        # Prepare form data
        form_data = {
            username_field: username,
            password_field: password
        }
        
        # Add CSRF token if available
        if csrf_field and csrf_value:
            form_data[csrf_field] = csrf_value
        
        # Add other form fields with their values
        all_fields = login_form.get('all_fields', [])
        for field in all_fields:
            field_name = field.get('name')
            field_value = field.get('value', '')
            field_type = field.get('type', '')
            
            # Skip fields we're already handling
            if field_name in [username_field, password_field, csrf_field]:
                continue
            
            # Skip submit buttons
            if field_type in ['submit', 'button', 'image']:
                continue
            
            # Add hidden fields and other form fields
            if field_name and field_type == 'hidden':
                form_data[field_name] = field_value
        
        # Encode form data
        if method.upper() == 'POST':
            data = urllib.parse.urlencode(form_data).encode('utf-8')
        else:
            # GET request - append to URL
            query_string = urllib.parse.urlencode(form_data)
            auth_url = f"{auth_url}?{query_string}" if '?' not in auth_url else f"{auth_url}&{query_string}"
            data = None
        
        # Create request
        request = Request(auth_url, data=data, method=method.upper())
        request.add_header('User-Agent', self.user_agent)
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')
        request.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        request.add_header('Accept-Language', 'en-US,en;q=0.9')
        request.add_header('Referer', base_url)  # Important for some apps
        request.add_header('Origin', base_url.rsplit('/', 1)[0] if '/' in base_url else base_url)
        
        try:
            response = opener.open(request, timeout=self.timeout)
            
            response_code = response.getcode()
            response_url = response.geturl()
            response_headers = dict(response.headers)
            
            # Read response body
            try:
                response_body = response.read().decode('utf-8', errors='ignore')
            except:
                response_body = ""
            
            response_info = {
                'status_code': response_code,
                'final_url': response_url,
                'cookies_count': len(list(cookie_jar)),
            }
            
            # Analyze response for success/failure
            success = self._analyze_response(
                response_code=response_code,
                response_url=response_url,
                response_body=response_body,
                auth_url=auth_url,
                base_url=base_url,
                cookie_jar=cookie_jar,
                response_headers=response_headers
            )
            
            if not success:
                response_info['reason'] = 'Login indicators suggest failure'
            
            return success, response_info
            
        except HTTPError as e:
            response_info = {
                'status_code': e.code,
                'reason': f'HTTP Error: {e.code}'
            }
            # 401/403 usually means failure, but some weird apps redirect with these
            if e.code in [401, 403]:
                return False, response_info
            # Other errors might indicate issues
            return False, response_info
            
        except URLError as e:
            raise Exception(f"Connection error: {e}")
        except Exception as e:
            raise Exception(f"Unexpected error: {e}")
    
    def _analyze_response(self, 
                         response_code: int,
                         response_url: str,
                         response_body: str,
                         auth_url: str,
                         base_url: str,
                         cookie_jar: http.cookiejar.CookieJar,
                         response_headers: Dict) -> bool:
        """
        Analyze the response to determine if login was successful
        
        Uses multiple heuristics to detect success/failure
        """
        body_lower = response_body.lower()
        url_lower = response_url.lower()
        
        # Count indicators
        failure_count = sum(1 for indicator in self.FAILURE_INDICATORS if indicator in body_lower)
        success_count = sum(1 for indicator in self.SUCCESS_INDICATORS if indicator in body_lower)
        
        # Heuristic 1: Check for explicit failure messages
        # If we see clear failure indicators, it's likely a failure
        if failure_count >= 2:
            return False
        
        # Heuristic 2: Redirect away from login page
        if response_url != auth_url and response_code in [200, 301, 302, 303, 307, 308]:
            # Check if redirected away from login-related pages
            login_keywords = ['login', 'signin', 'sign-in', 'auth', 'authenticate', 'logon']
            was_on_login = any(kw in auth_url.lower() for kw in login_keywords)
            now_on_login = any(kw in url_lower for kw in login_keywords)
            
            if was_on_login and not now_on_login:
                # Redirected away from login - likely success
                return True
        
        # Heuristic 3: Strong success indicators with no failure indicators
        if success_count >= 2 and failure_count == 0:
            return True
        
        # Heuristic 4: Session cookies set
        session_cookie_names = ['session', 'sess', 'auth', 'token', 'jsessionid', 'phpsessid', 
                                'aspxauth', '.aspnetcore', 'laravel_session', 'wordpress_logged_in']
        cookies_set = [cookie.name.lower() for cookie in cookie_jar]
        
        if any(sess_name in ' '.join(cookies_set) for sess_name in session_cookie_names):
            # Session cookie set - could be success
            if failure_count == 0:
                return True
        
        # Heuristic 5: Check Set-Cookie header for auth cookies
        set_cookie = response_headers.get('set-cookie', '').lower()
        if any(sess_name in set_cookie for sess_name in session_cookie_names):
            if failure_count == 0:
                return True
        
        # Heuristic 6: Response contains logout link (strong indicator of logged in)
        if 'logout' in body_lower or 'sign out' in body_lower or 'log out' in body_lower:
            if failure_count == 0:
                return True
        
        # Heuristic 7: If still on login page with no clear success/failure, assume failure
        if any(kw in url_lower for kw in ['login', 'signin', 'auth']):
            return False
        
        # Default: If response is 200 and no clear failure, mark as potential success
        # but this is uncertain
        if response_code == 200 and failure_count == 0 and success_count > 0:
            return True
        
        # When in doubt, assume failure (safer)
        return False
