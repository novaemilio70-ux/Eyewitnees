#!/usr/bin/env python3
"""
AI-Powered Credential Analyzer Integration Module
Orchestrates AI analysis, credential search, form analysis, and credential testing
"""

import os
import copy
from typing import Optional, Dict, List, Any
from modules.ai_analyzer import AIAnalyzer, create_ai_analyzer
from modules.form_analyzer import FormAnalyzer
from modules.credential_tester import CredentialTester, CredentialTestResult
from modules.objects import HTTPTableObject
from modules.signature_manager import SignatureManager


def sanitize_for_pickle(obj: Any, max_depth: int = 10) -> Any:
    """
    Recursively sanitize an object to ensure it can be pickled.
    Removes any non-serializable objects (functions, lambdas, etc.)
    
    Args:
        obj: Object to sanitize
        max_depth: Maximum recursion depth
        
    Returns:
        Sanitized object safe for pickling
    """
    if max_depth <= 0:
        return str(obj) if obj is not None else None
        
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, bytes):
        return obj
    elif isinstance(obj, dict):
        return {
            sanitize_for_pickle(k, max_depth - 1): sanitize_for_pickle(v, max_depth - 1)
            for k, v in obj.items()
        }
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_pickle(item, max_depth - 1) for item in obj]
    elif isinstance(obj, set):
        return list(obj)
    elif hasattr(obj, '__dict__'):
        # For objects with __dict__, convert to simple dict
        try:
            return {k: sanitize_for_pickle(v, max_depth - 1) 
                    for k, v in obj.__dict__.items() 
                    if not k.startswith('_') and not callable(v)}
        except:
            return str(obj)
    else:
        # For anything else, convert to string
        try:
            return str(obj)
        except:
            return None

# Try to import Selenium credential tester
try:
    from modules.selenium_credential_tester import SeleniumCredentialTester
    HAS_SELENIUM_TESTER = True
except ImportError:
    HAS_SELENIUM_TESTER = False


class AICredentialAnalyzer:
    """Main orchestrator for AI-powered credential analysis"""
    
    def __init__(self, 
                 ai_api_key: Optional[str] = None,
                 ai_provider: Optional[str] = None,
                 test_credentials: bool = True,
                 credential_test_timeout: int = 10,
                 credential_test_delay: float = 2.0,
                 use_selenium_for_creds: bool = True,
                 selenium_driver = None,
                 debug_creds: bool = False,
                 output_dir: str = None,
                 quiet: bool = False):
        """
        Initialize AI Credential Analyzer
        
        Args:
            ai_api_key: OpenAI API key (or from OPENAI_API_KEY env var)
            ai_provider: Only 'openai' is supported
            test_credentials: Whether to test credentials automatically
            credential_test_timeout: Timeout for credential tests
            credential_test_delay: Delay between credential tests
            use_selenium_for_creds: Use Selenium browser for testing (handles JS encryption)
            selenium_driver: Existing Selenium WebDriver to reuse (important for worker pool)
            debug_creds: Enable debug mode for credential testing
            output_dir: Output directory for debug files
            quiet: Suppress initialization messages (useful for parallel workers)
        """
        if not quiet:
            print(f"[*] Initializing AI Credential Analyzer...")
        
        self.ai_analyzer = create_ai_analyzer(api_key=ai_api_key, provider=ai_provider)
        self.test_credentials = test_credentials
        self.form_analyzer = FormAnalyzer()
        self.use_selenium = use_selenium_for_creds and HAS_SELENIUM_TESTER
        self.debug_creds = debug_creds
        self.output_dir = output_dir
        self._shared_driver = selenium_driver  # Track if driver is shared
        
        # Initialize testers
        self.credential_tester = CredentialTester(
            timeout=credential_test_timeout,
            delay=credential_test_delay
        )
        
        # Debug directory for credential testing
        debug_dir = None
        if debug_creds and output_dir:
            import os
            debug_dir = os.path.join(output_dir, 'debug_creds')
        
        if self.use_selenium:
            self.selenium_tester = SeleniumCredentialTester(
                driver=selenium_driver,
                delay=credential_test_delay,
                timeout=credential_test_timeout,
                debug=debug_creds,
                debug_dir=debug_dir
            )
            # Mark that we don't own the driver if it was passed in
            if selenium_driver is not None:
                self.selenium_tester.owns_driver = False
        else:
            self.selenium_tester = None
            
        self.ai_enabled = self.ai_analyzer is not None
        
        # Debug: Show AI status (unless quiet mode)
        if not quiet:
            if self.ai_enabled:
                print(f"[+] AI is ENABLED and ready to use")
            else:
                print(f"[!] AI is DISABLED - will use form analysis and common credentials only")
        
        # Initialize learned credentials manager
        # JSON-based signature manager
        try:
            self.sig_manager = SignatureManager()
        except Exception as e:
            if not quiet:
                print(f"[!] Warning: Could not initialize SignatureManager: {e}")
            self.sig_manager = None
    
    def _deduplicate_credentials(self, credentials: list) -> list:
        """
        Remove duplicate credentials based on username and password only.
        Preserves the first occurrence of each unique username:password pair.
        
        Args:
            credentials: List of credential dicts
            
        Returns:
            List of unique credentials
        """
        seen = set()
        unique_creds = []
        
        for cred in credentials:
            username = cred.get('username', '').lower().strip()
            password = cred.get('password', '').strip()
            
            # Create a unique key based on username and password
            key = (username, password)
            
            if key not in seen:
                seen.add(key)
                unique_creds.append(cred)
        
        return unique_creds
    
    def _parse_signature_credentials(self, default_creds_str: str) -> list:
        """
        Parse credentials from signature string format
        
        Args:
            default_creds_str: String like "AppName / admin:password" or "admin/admin"
            
        Returns:
            List of credential dicts
        """
        credentials = []
        if not default_creds_str:
            return credentials
        
        import re
        
        # Words that are likely NOT usernames (protocol names, tech terms, etc.)
        # NOTE: 'admin', 'user', 'administrator', 'root' are VALID usernames and should NOT be in this list
        FALSE_POSITIVE_USERNAMES = {
            'http', 'https', 'ftp', 'ssh', 'tcp', 'udp', 'ssl', 'tls',
            'rx', 'tx', 'api', 'url', 'uri', 'xml', 'json', 'html',
            'model', 'version', 'type', 'mode', 'port', 'host',
            'first', 'last', 'two', 'one', 'the', 'for', 'and', 'with',
            'commandcenter', 'default', 'credentials', 'password', 'username',
            'numbers', 'digits', 'letters', 'characters', 'knowledgesync',
            'portal', 'application', 'system', 'service', 'server',
            'point', 'access', 'wireless', 'network', 'device', 'printer',
            'camera', 'switch', 'router', 'firewall', 'gateway',
            'manager', 'console', 'login', 'sign', 'web', 'config',
            'utility', 'tool', 'software', 'platform', 'series',
            'product', 'brand', 'vendor', 'technology'
        }
        
        # Words that are likely NOT passwords (but only if they appear in descriptive context)
        # Note: "password" and "default" as literal password values are valid, so we only skip them in context
        FALSE_POSITIVE_PASSWORDS = {
            'username', 'and', 'the', 'for', 'with', 'install',
            'numbers', 'digits', 'required', 'optional'
        }
        
        # First, handle the modern format: "AppName / user:pass" or "AppName (info) / user:pass"
        # Extract the part after " / " which contains the actual credentials
        if ' / ' in default_creds_str:
            creds_part = default_creds_str.split(' / ', 1)[1]
        else:
            creds_part = default_creds_str
        
        # Split by common separators first to handle each credential individually
        # This prevents " or " from being parsed as a password
        cred_parts = re.split(r'\s+or\s+|,\s*|;\s*', creds_part)
        
        # Look for explicit credential patterns - prioritize user:pass format
        # Also handle user: (without password) which should test blank password
        # Handle MANUAL_TEST_REQUIRED as a special case (skip testing)
        explicit_patterns = [
            # Prioritize colon separator: admin:admin, Admin:Password, root:toor
            # Also handle MANUAL_TEST_REQUIRED:password or user:MANUAL_TEST_REQUIRED
            r'\b([A-Za-z][A-Za-z0-9_]{2,20}|MANUAL_TEST_REQUIRED)\s*:\s*([A-Za-z0-9_!@#$%^&*+\-]{1,50}|MANUAL_TEST_REQUIRED)\b',
            # Then try slash separator (older format): user/pass (convert to user:pass) - fallback for any remaining
            r'\b([A-Za-z][A-Za-z0-9_]{2,20}|MANUAL_TEST_REQUIRED)\s*/\s*([A-Za-z0-9_!@#$%^&*+\-]{1,50}|MANUAL_TEST_REQUIRED)\b',
        ]
        
        # Process each credential part separately
        for cred_part in cred_parts:
            cred_part = cred_part.strip()
            if not cred_part:
                continue
            
            # Check for user: (blank password) first - must be at end of part
            blank_pass_match = re.match(r'^([A-Za-z][A-Za-z0-9_]{2,20})\s*:\s*$', cred_part)
            if blank_pass_match:
                username = blank_pass_match.group(1)
                if username.lower() not in FALSE_POSITIVE_USERNAMES:
                    cred = {'username': username, 'password': '', 'source': 'signature'}
                    if cred not in credentials:
                        credentials.append(cred)
                continue
            
            # Try patterns with password
            for pattern in explicit_patterns:
                match = re.search(pattern, cred_part, re.IGNORECASE)
                if match:
                    username = match.group(1)
                    password = match.group(2)
                    
                    # Skip MANUAL_TEST_REQUIRED credentials (don't test them)
                    if 'MANUAL_TEST_REQUIRED' in username.upper() or 'MANUAL_TEST_REQUIRED' in password.upper():
                        continue
                    
                    # Skip false positives
                    if username.lower() in FALSE_POSITIVE_USERNAMES:
                        continue
                    if password and password.lower() in FALSE_POSITIVE_PASSWORDS:
                        continue
                        
                    # Skip if password is just numbers under 3 digits (likely not a password)
                    if password and password.isdigit() and len(password) < 3:
                        continue
                    
                    # Username should start with a letter
                    if not username[0].isalpha():
                        continue
                    
                    cred = {'username': username, 'password': password, 'source': 'signature'}
                    if cred not in credentials:
                        credentials.append(cred)
                    break  # Found a match, move to next cred_part
        
        # If no credentials found, try to find common default credential patterns
        if not credentials:
            common_defaults = [
                ('admin', 'admin'),
                ('admin', 'password'),
                ('administrator', 'administrator'),
                ('root', 'root'),
                ('user', 'user'),
            ]
            
            text_lower = default_creds_str.lower()
            for user, passwd in common_defaults:
                # Check if both user and password are mentioned in the text
                if user in text_lower and passwd in text_lower:
                    cred = {'username': user, 'password': passwd, 'source': 'signature_common'}
                    if cred not in credentials:
                        credentials.append(cred)
        
        return credentials
    
    def _save_credentials_from_test_result(self,
                                            test_result: dict,
                                            http_object: HTTPTableObject,
                                            app_name: Optional[str] = None):
        """
        Helper to save successful credentials from a test result.
        
        Note: Only successful credentials are saved to signatures.json as known working credentials.
        Failed credentials are NOT saved - signatures.json only stores known default credentials.
        Test results (success/failure) should be tracked in the project database, not in signatures.json.
        
        Args:
            test_result: Test result dict with successful_credentials and failed_credentials
            http_object: The HTTP object
            app_name: Application name if known
        """
        successful_creds = []
        
        # Only save successful credentials
        for cred in test_result.get('successful_credentials', []):
            cred_copy = cred.copy() if isinstance(cred, dict) else {'username': cred[0], 'password': cred[1]}
            # Mark source as 'documented' since it's a verified working credential
            cred_copy['source'] = 'documented'
            successful_creds.append(cred_copy)
        
        if successful_creds:
            self._save_all_credentials(successful_creds, http_object, app_name)
    
    def _save_all_credentials(self,
                               all_creds: list,
                               http_object: HTTPTableObject,
                               app_name: Optional[str] = None):
        """
        Save ALL tested credentials (working and failed) to the JSON signature system
        
        Args:
            all_creds: List of all credential dicts with test results
            http_object: The HTTP object with context info
            app_name: Application name if known
        """
        if not self.sig_manager:
            print("[!] SignatureManager not available - cannot save credentials")
            return
        
        # Get HTML content early (needed for multiple checks)
        html_content = None
        if http_object.source_code:
            html_content = http_object.source_code
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='ignore')
        
        # Determine application name - improved extraction
        final_app_name = app_name
        if not final_app_name:
            # Priority 1: AI analysis
            if http_object.ai_application_info:
                final_app_name = http_object.ai_application_info.get('application_name')
                # Try to get manufacturer + model if available
                if not final_app_name:
                    manufacturer = http_object.ai_application_info.get('manufacturer')
                    model = http_object.ai_application_info.get('model')
                    if manufacturer and model:
                        final_app_name = f"{manufacturer} {model}"
                    elif manufacturer:
                        final_app_name = manufacturer
                    elif model:
                        final_app_name = model
            
            # Priority 2: Page title (clean it up)
            if not final_app_name and http_object.page_title:
                page_title = http_object.page_title
                if isinstance(page_title, bytes):
                    page_title = page_title.decode('utf-8', errors='ignore')
                
                # Clean up common patterns
                page_title = page_title.strip()
                # Remove common suffixes
                for suffix in [' - Login', ' - Log in', ' Login', ' Log in', ' - Home', ' - Dashboard']:
                    if page_title.endswith(suffix):
                        page_title = page_title[:-len(suffix)].strip()
                
                # Extract meaningful name (first part before dash/pipe)
                if ' - ' in page_title:
                    final_app_name = page_title.split(' - ')[0].strip()
                elif ' | ' in page_title:
                    final_app_name = page_title.split(' | ')[0].strip()
                elif '|' in page_title:
                    final_app_name = page_title.split('|')[0].strip()
                else:
                    # Take first meaningful words (skip common words)
                    words = page_title.split()
                    skip_words = {'login', 'log', 'in', 'home', 'dashboard', 'welcome', 'to', 'the'}
                    meaningful_words = [w for w in words if w.lower() not in skip_words]
                    if meaningful_words:
                        final_app_name = ' '.join(meaningful_words[:3])  # Max 3 words
                    else:
                        final_app_name = page_title[:50]  # Limit length
            
            # Priority 3: Try to extract from HTML (title tag)
            if not final_app_name and html_content:
                import re
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
                if title_match:
                    title_text = title_match.group(1).strip()
                    # Clean up
                    for suffix in [' - Login', ' - Log in', ' Login', ' Log in']:
                        if title_text.endswith(suffix):
                            title_text = title_text[:-len(suffix)].strip()
                    if title_text and title_text.lower() not in ['login', 'log in', 'home', 'welcome']:
                        final_app_name = title_text.split(' - ')[0].split(' | ')[0].split('|')[0].strip()[:50]
            
            # Priority 4: Try from default_creds (if it has app name)
            if not final_app_name and http_object.default_creds:
                # Format: "AppName / user:pass"
                if ' / ' in http_object.default_creds:
                    final_app_name = http_object.default_creds.split(' / ')[0].strip()
            
            # Priority 5: Try from URL hostname
            if not final_app_name:
                from urllib.parse import urlparse
                parsed = urlparse(http_object.remote_system)
                hostname = parsed.hostname or parsed.netloc
                if hostname and hostname not in ['localhost', '127.0.0.1']:
                    # Try to extract meaningful name from hostname
                    parts = hostname.split('.')
                    if parts and parts[0]:
                        final_app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
            
            # Last resort: use hostname as-is
            if not final_app_name:
                from urllib.parse import urlparse
                parsed = urlparse(http_object.remote_system)
                final_app_name = parsed.netloc or "Unknown"
        
        # Extract signature patterns (html_content already defined above)
        from modules.learned_credentials import extract_signature_patterns
        signature_patterns = extract_signature_patterns(
            html_content or '',
            app_name=final_app_name,
            max_patterns=3
        )
        
        if not signature_patterns:
            # Fallback: use page title as pattern
            if http_object.page_title:
                signature_patterns = [f"<title>{http_object.page_title}</title>"]
            else:
                print(f"[!] Could not extract signature patterns for {final_app_name}")
                return
        
        # Determine category - use auto_categorize if not already set
        category = http_object.category
        if not category:
            from modules.helpers import auto_categorize
            category = auto_categorize(http_object)
            if category:
                http_object.category = category
                print(f"    [+] Auto-categorized as: {category}")
        
        # If still no category, try AI-based categorization
        if not category and http_object.ai_application_info:
            app_type = http_object.ai_application_info.get('application_type', '').lower()
            app_name = http_object.ai_application_info.get('application_name', '').lower()
            
            if 'printer' in app_type:
                category = 'printer'
            elif 'network' in app_type or 'switch' in app_type or 'router' in app_type or 'firewall' in app_type:
                category = 'network_device'
            elif 'voip' in app_type or 'phone' in app_type:
                category = 'voip'
            elif 'video' in app_type or 'conference' in app_type or 'presentation' in app_type:
                category = 'video_conference'
            elif 'idrac' in app_type or 'ipmi' in app_type or 'ilo' in app_type:
                category = 'idrac'
            elif 'storage' in app_type or 'nas' in app_type or 'san' in app_type:
                category = 'storage'
            elif 'virtualization' in app_type or 'hypervisor' in app_type:
                category = 'virtualization'
            elif 'monitoring' in app_type:
                category = 'monitoring'
            elif 'security' in app_type:
                category = 'secops'
            elif 'itsm' in app_type or 'service desk' in app_type or 'servicedesk' in app_name:
                category = 'itsm'
            elif 'iot' in app_type:
                category = 'iot'
            elif 'api' in app_type or 'swagger' in app_name:
                category = 'api'
            elif 'web server' in app_type or 'webserver' in app_type:
                category = 'webserver'
            elif 'application server' in app_type or 'appserver' in app_type:
                category = 'appserver'
            elif 'management' in app_type:
                category = 'network_management'
        
        # Default fallback
        if not category:
            category = "unknown"
        
        # Prepare credentials list
        # Note: We only save credentials to signatures.json (known default credentials to try)
        # Test results (success/failure) are stored in the project database, not in signatures.json
        credentials_list = []
        for cred in all_creds:
            username = cred.get('username')
            password = cred.get('password')
            
            if not username:
                continue
            
            source = cred.get('source', 'manual')
            
            # Normalize source to one of: default, documented, common, manual
            if source in ('ai_discovered', 'ai'):
                source = 'common'  # AI discovered credentials are common/guessed credentials
            elif source in ('signature', 'signature_common', 'learned', 'documented'):
                source = 'documented'  # Known documented credentials
            elif source == 'default':
                source = 'default'  # Default factory credentials
            else:
                source = 'manual'  # Manually added
            
            credentials_list.append({
                "username": username,
                "password": password or "",
                "source": source
            })
        
        # Add or update signature with all credentials
        try:
            self.sig_manager.add_or_update_signature(
                application_name=final_app_name,
                signature_patterns=signature_patterns,
                category=category,
                credentials=credentials_list,
                metadata={
                    "discovered_by": "ai" if any(c.get('source') == 'common' for c in credentials_list) else "manual"
                }
            )
            print(f"[+] Saved {len(credentials_list)} credential(s) to signatures.json for {final_app_name}")
        except Exception as e:
            print(f"[!] Error saving credentials to signatures.json: {e}")
    
    
    def _test_credentials_only(self, http_object: HTTPTableObject, credentials: list) -> HTTPTableObject:
        """
        Test credentials without form analysis (for cases with no HTML but known credentials)
        Uses Selenium to navigate and test directly
        """
        if not credentials or not self.test_credentials:
            return http_object
        
        print(f"[*] Testing {len(credentials)} credential(s) directly via Selenium...")
        
        if self.use_selenium and self.selenium_tester:
            test_result = self.selenium_tester.test_credentials(
                url=http_object.remote_system,
                credentials=credentials
            )
            http_object.credential_test_result = sanitize_for_pickle(test_result)
            
            if test_result.get('successful_credentials'):
                print(f"    [+] SUCCESS: {test_result['successful_count']} credential(s) worked!")
            else:
                print(f"    [*] No credentials worked (tested {test_result.get('credentials_tested', 0)})")
            
            # Save ALL tested credentials (working and failed)
            self._save_credentials_from_test_result(test_result, http_object, None)
        else:
            print(f"[!] Selenium tester not available for direct testing")
        
        return http_object
    
    def analyze_http_object(self, http_object: HTTPTableObject, 
                           skip_if_signature_found: bool = True) -> HTTPTableObject:
        """
        Analyze HTTP object with AI if not found in signatures
        
        Args:
            http_object: HTTPTableObject to analyze
            skip_if_signature_found: Skip AI analysis if default_creds already found
            
        Returns:
            Updated HTTPTableObject
        """
        credentials = []
        has_signature_creds = False
        app_name_for_learning = None  # Used for saving learned credentials
        
        # Check for HTTP Authentication (Basic, Digest, NTLM, Negotiate) - skip credential testing
        # These use browser auth prompts, not HTML forms - automated testing doesn't work reliably
        http_auth_type = getattr(http_object, '_http_auth_type', None) or getattr(http_object, 'http_auth_type', None)
        if http_auth_type:
            print(f"  [*] Skipping credential testing - {http_auth_type} authentication detected")
            print(f"  [*] HTTP Auth prompts require manual testing or specialized tools")
            # Disable credential testing for this object
            original_test_creds = self.test_credentials
            self.test_credentials = False
            try:
                # Still do AI identification if enabled, but no credential testing
                if self.ai_enabled and http_object.source_code:
                    html_content = http_object.source_code
                    if isinstance(html_content, bytes):
                        html_content = html_content.decode('utf-8', errors='ignore')
                    try:
                        app_info = self.ai_analyzer.identify_application(
                            html_content=html_content,
                            url=http_object.remote_system
                        )
                        if app_info and app_info.get('application_name'):
                            http_object.ai_application_info = app_info
                            print(f"    [+] AI identified: {app_info.get('application_name')}")
                    except:
                        pass
                return http_object
            finally:
                self.test_credentials = original_test_creds
        
        # Note: Learned credentials are stored in signatures.json and will be 
        # automatically matched by EyeWitness core signature matching system.
        # No need to search separately - they appear in http_object.default_creds
        
        # Check if already has credentials from signatures
        if http_object.default_creds:
            has_signature_creds = True
            print(f"  [+] Found in signatures: {http_object.default_creds[:60]}...")
            
            # Parse credentials from signature string
            sig_creds = self._parse_signature_credentials(http_object.default_creds)
            if sig_creds:
                credentials.extend(sig_creds)
                # Remove duplicates
                credentials = self._deduplicate_credentials(credentials)
                print(f"  [+] Parsed {len(sig_creds)} credential(s) from signatures, {len(credentials)} unique total")
            
            if skip_if_signature_found:
                print(f"  [*] Skipping AI - using signature credentials")
        
        # Skip if no source code
        if not http_object.source_code:
            print(f"  [!] No source code available")
            # Still try to test signature credentials if we have them
            if credentials and self.test_credentials:
                return self._test_credentials_only(http_object, credentials)
            return http_object
        
        print(f"  [*] Starting AI/credential analysis...")
        
        # Prepare HTML content
        html_content = http_object.source_code
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8', errors='ignore')
        
        try:
            # Step 1: Identify application using AI (if available and not skipped)
            if self.ai_enabled and not (skip_if_signature_found and has_signature_creds):
                print(f"    [*] Using AI to identify application...")
                print(f"    [*] Sending HTML content to AI (length: {len(html_content)} chars)...")
                try:
                    app_info = self.ai_analyzer.identify_application(
                        html_content=html_content,
                        url=http_object.remote_system
                    )
                    
                    if app_info and app_info.get('application_name'):
                        http_object.ai_application_info = app_info
                        app_name = app_info.get('application_name')
                        app_type = app_info.get('application_type')
                        manufacturer = app_info.get('manufacturer')
                        model = app_info.get('model')
                        print(f"    [+] AI identified: {app_name} ({app_type})")
                        if manufacturer:
                            print(f"    [+] Manufacturer: {manufacturer}")
                        if model:
                            print(f"    [+] Model: {model}")
                        
                        app_name_for_learning = app_name
                        
                        # Step 2: Search for default credentials via AI
                        print(f"    [*] Searching default credentials via AI...")
                        print(f"    [*] Query: {app_name} ({app_type})")
                        try:
                            ai_creds = self.ai_analyzer.search_default_credentials(
                                application_name=app_name,
                                application_type=app_type,
                                manufacturer=manufacturer,
                                model=model
                            )
                            
                            if ai_creds:
                                # Mark all AI credentials
                                for cred in ai_creds:
                                    cred['source'] = 'ai_discovered'
                                
                                # Add AI credentials to list
                                credentials.extend(ai_creds)
                                
                                # Remove duplicates (based on username:password only)
                                credentials = self._deduplicate_credentials(credentials)
                                
                                # Store unique AI credentials
                                unique_ai_creds = [c for c in credentials if c.get('source') == 'ai_discovered']
                                http_object.ai_credentials_found = unique_ai_creds
                                
                                print(f"    [+] AI found {len(ai_creds)} potential credential(s), {len(unique_ai_creds)} unique after deduplication:")
                                for cred in unique_ai_creds:
                                    print(f"        - {cred.get('username', 'N/A')}:{cred.get('password', 'N/A') or '(blank)'} ({cred.get('description', 'N/A')})")
                            else:
                                print(f"    [*] AI found no default credentials for {app_name}")
                        except Exception as e:
                            print(f"    [!] Error searching credentials via AI: {e}")
                    else:
                        print(f"    [*] AI could not identify application from HTML content")
                except Exception as e:
                    print(f"    [!] Error calling AI for application identification: {e}")
                    import traceback
                    if self.debug_creds:
                        traceback.print_exc()
            elif not self.ai_enabled:
                print(f"  [*] AI not available - form analysis only")
                print(f"  [*] Reason: AI analyzer not initialized (check API keys)")
                # If no credentials from signatures and AI not available, try common credentials
                if not credentials and self.test_credentials:
                    print(f"  [*] No credentials from signatures, trying common defaults...")
                    common_creds = [
                        {'username': 'admin', 'password': 'admin', 'source': 'common'},
                        {'username': 'admin', 'password': 'password', 'source': 'common'},
                        {'username': 'admin', 'password': '', 'source': 'common'},
                        {'username': 'root', 'password': 'root', 'source': 'common'},
                        {'username': 'root', 'password': 'toor', 'source': 'common'},
                        {'username': 'administrator', 'password': 'administrator', 'source': 'common'},
                        {'username': 'administrator', 'password': 'password', 'source': 'common'},
                    ]
                    credentials.extend(common_creds)
                    # Remove duplicates before testing
                    credentials = self._deduplicate_credentials(credentials)
                    print(f"    [+] Added {len(common_creds)} common credential(s), {len(credentials)} unique total to test")
            else:
                print(f"  [*] AI skipped - using signature credentials")
            # else: AI skipped because we have signature credentials
            
            # Step 3: Analyze login forms (always do this, even without AI)
            print(f"  [*] Analyzing login forms...")
            auth_info = self.form_analyzer.extract_auth_info(
                html_content=http_object.source_code,
                base_url=http_object.remote_system
            )
            
            http_object.auth_info = auth_info
            
            if auth_info.get('has_login_form'):
                login_forms = auth_info.get('login_forms', [])
                print(f"    [+] Found {len(login_forms)} login form(s)")
                
                primary_form = auth_info.get('primary_form')
                
                # Always store auth method for password spraying (even without AI credentials)
                if primary_form and primary_form.get('username_field') and primary_form.get('password_field'):
                    http_object.auth_method_stored = {
                        'url': http_object.remote_system,
                        'endpoint': primary_form.get('action') or http_object.remote_system,
                        'method': primary_form.get('method', 'POST'),
                        'username_field': primary_form.get('username_field'),
                        'password_field': primary_form.get('password_field'),
                        'csrf_field': primary_form.get('csrf_token'),
                        'auth_type': auth_info.get('auth_type', 'form_based'),
                        'all_fields': primary_form.get('all_fields', [])
                    }
                    print(f"    [+] Stored auth method for spraying")
                
                # Step 4: Remove any remaining duplicates before testing
                credentials = self._deduplicate_credentials(credentials)
                
                # Step 5: Test credentials if enabled and we have credentials
                if self.test_credentials and credentials and primary_form:
                    print(f"  [*] Testing {len(credentials)} unique credential(s)...")
                    
                    # Prefer Selenium for credential testing (handles JS encryption)
                    if self.use_selenium and self.selenium_tester:
                        print(f"    [*] Using Selenium (handles JS/encryption)")
                        test_result = self.selenium_tester.test_credentials(
                            url=http_object.remote_system,
                            credentials=credentials
                        )
                        # Sanitize result to ensure it can be pickled for multiprocessing
                        http_object.credential_test_result = sanitize_for_pickle(test_result)
                        
                        if test_result.get('successful_credentials'):
                            print(f"    [+] SUCCESS: {test_result['successful_count']} credential(s) worked!")
                        else:
                            print(f"    [*] No credentials worked (tested {test_result.get('credentials_tested', 0)})")
                        
                        # Save ALL tested credentials (working and failed)
                        self._save_credentials_from_test_result(test_result, http_object, app_name_for_learning)
                    else:
                        # Fallback to HTTP-based testing
                        print(f"[*] Using HTTP-based credential testing")
                        cookies = None
                        if hasattr(http_object, 'cookies'):
                            cookies = http_object.cookies
                        
                        test_result = self.credential_tester.test_credentials(
                            base_url=http_object.remote_system,
                            login_form=primary_form,
                            credentials=credentials,
                            cookies=cookies
                        )
                        
                        http_object.credential_test_result = sanitize_for_pickle(test_result.to_dict())
                        
                        if test_result.successful_credentials:
                            print(f"    [+] SUCCESS: {len(test_result.successful_credentials)} credential(s) worked!")
                        else:
                            print(f"    [*] No credentials worked (tested {len(test_result.credentials_tested)})")
                        
                        # Convert to dict format and save ALL tested credentials
                        test_result_dict = test_result.to_dict()
                        self._save_credentials_from_test_result(test_result_dict, http_object, app_name_for_learning)
                elif not primary_form:
                    # No HTML form found, but try Selenium anyway (it can find dynamic forms)
                    if self.test_credentials and credentials and self.use_selenium and self.selenium_tester:
                        # Deduplicate before testing
                        credentials = self._deduplicate_credentials(credentials)
                        print(f"[*] No HTML form found, trying Selenium to find dynamic form...")
                        print(f"[*] Testing {len(credentials)} unique credential(s)...")
                        test_result = self.selenium_tester.test_credentials(
                            url=http_object.remote_system,
                            credentials=credentials
                        )
                        # Sanitize result to ensure it can be pickled for multiprocessing
                        http_object.credential_test_result = sanitize_for_pickle(test_result)
                        
                        if test_result.get('successful_credentials'):
                            print(f"    [+] SUCCESS: {test_result['successful_count']} credential(s) worked!")
                        else:
                            print(f"    [*] No credentials worked (tested {test_result.get('credentials_tested', 0)})")
                        
                        # Save ALL tested credentials (working and failed)
                        self._save_credentials_from_test_result(test_result, http_object, app_name_for_learning)
                    else:
                        print(f"[*] No primary login form with username/password fields found")
                elif not self.test_credentials:
                    print(f"[*] Credential testing disabled")
                elif not credentials:
                    print(f"[*] No credentials to test (login form saved for password spraying)")
            else:
                # No login form in HTML, but try Selenium if we have credentials
                if self.test_credentials and credentials and self.use_selenium and self.selenium_tester:
                    # Deduplicate before testing
                    credentials = self._deduplicate_credentials(credentials)
                    print(f"[*] No HTML login form detected, trying Selenium...")
                    print(f"[*] Testing {len(credentials)} unique credential(s)...")
                    test_result = self.selenium_tester.test_credentials(
                        url=http_object.remote_system,
                        credentials=credentials
                    )
                    http_object.credential_test_result = sanitize_for_pickle(test_result)
                    
                    if test_result.get('successful_credentials'):
                        print(f"    [+] SUCCESS: {test_result['successful_count']} credential(s) worked!")
                    else:
                        print(f"    [*] No credentials worked (tested {test_result.get('credentials_tested', 0)})")
                    
                    # Save ALL tested credentials (working and failed)
                    self._save_credentials_from_test_result(test_result, http_object, app_name_for_learning)
                else:
                    print(f"[*] No login form detected")
        
        except Exception as e:
            print(f"[!] Error during AI analysis: {e}")
            import traceback
            traceback.print_exc()
        
        return http_object
    
    def get_auth_methods_for_spraying(self, http_objects: List[HTTPTableObject]) -> Dict:
        """
        Extract authentication methods for password spraying
        
        Args:
            http_objects: List of HTTPTableObject instances
            
        Returns:
            Dictionary organized by application/auth type
        """
        auth_methods = {}
        
        for obj in http_objects:
            if not obj.auth_method_stored:
                continue
            
            app_name = "Unknown"
            if obj.ai_application_info:
                app_name = obj.ai_application_info.get('application_name', 'Unknown')
            elif obj.default_creds:
                # Try to extract app name from default_creds string
                app_name = "Signature-Matched"
            
            if app_name not in auth_methods:
                auth_methods[app_name] = []
            
            auth_method = {
                'url': obj.remote_system,
                'endpoint': obj.auth_method_stored.get('endpoint'),
                'method': obj.auth_method_stored.get('method'),
                'username_field': obj.auth_method_stored.get('username_field'),
                'password_field': obj.auth_method_stored.get('password_field'),
                'auth_type': obj.auth_method_stored.get('auth_type'),
                'tested': obj.credential_test_result is not None,
                'has_working_creds': bool(
                    obj.credential_test_result and 
                    obj.credential_test_result.get('successful_count', 0) > 0
                )
            }
            
            auth_methods[app_name].append(auth_method)
        
        return auth_methods
    
    def save_auth_methods_for_spraying(self, http_objects: List[HTTPTableObject], 
                                       output_path: str):
        """
        Save authentication methods to JSON file for password spraying
        
        Args:
            http_objects: List of HTTPTableObject instances
            output_path: Path to save JSON file
        """
        import json
        from pathlib import Path
        
        auth_methods = self.get_auth_methods_for_spraying(http_objects)
        
        output_file = Path(output_path) / 'auth_methods_for_spraying.json'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump(auth_methods, f, indent=2)
        
        print(f"[+] Saved authentication methods to: {output_file}")
        return str(output_file)

