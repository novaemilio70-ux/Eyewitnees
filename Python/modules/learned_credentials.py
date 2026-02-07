#!/usr/bin/env python3
"""
Learned Credentials Manager

Adds verified credentials to EyeWitness signatures.txt and categories.txt
so they are automatically recognized in future scans without AI.
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from html.parser import HTMLParser


class SignatureExtractor(HTMLParser):
    """Extract unique signature patterns from HTML"""
    
    def __init__(self):
        super().__init__()
        self.title = None
        self.meta_tags = []
        self.unique_classes = set()
        self.unique_ids = set()
        self.form_actions = []
        self.img_srcs = []
        
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'meta':
            content = attrs_dict.get('content', '')
            if content and len(content) > 5 and len(content) < 50:
                # Avoid generic content
                if not any(x in content.lower() for x in ['utf-8', 'width=', 'text/html']):
                    self.meta_tags.append(content)
                
        if 'class' in attrs_dict:
            classes = attrs_dict['class'].split()
            for cls in classes:
                # Look for unique class names (not generic like 'container', 'row')
                if len(cls) > 5 and not cls.isdigit():
                    if not any(x in cls.lower() for x in ['container', 'row', 'col-', 'btn', 'form']):
                        self.unique_classes.add(cls)
                    
        if 'id' in attrs_dict:
            id_val = attrs_dict['id']
            if len(id_val) > 4 and not id_val.isdigit():
                self.unique_ids.add(id_val)
                
        if tag == 'form' and 'action' in attrs_dict:
            action = attrs_dict['action']
            if action and len(action) > 3 and action != '#':
                self.form_actions.append(action[:40])
                
        if tag == 'img' and 'src' in attrs_dict:
            src = attrs_dict['src']
            # Look for logo images
            if 'logo' in src.lower() or 'brand' in src.lower():
                self.img_srcs.append(src[:50])
    
    def handle_data(self, data):
        pass


def _generalize_pattern(pattern: str) -> str:
    """
    Generalize a pattern by replacing IDs, serial numbers, and other variable parts
    with regex patterns.
    
    Examples:
        "PM43:PM4318922145206" -> "PM43:PM43\\d+"
        "Device-12345" -> "Device-\\d+"
        "Model ABC123" -> "Model [A-Z]+\\d+"
        "v1.2.3" -> "v\\d+\\.\\d+\\.\\d+"
    """
    import re
    
    # Pattern 1: Repeated model/prefix followed by numbers (e.g., "PM43:PM4318922145206")
    # Match: "PM43:PM43" + digits (the prefix appears twice)
    repeated_model = re.search(r'^([A-Za-z0-9]+):\1(\d+)$', pattern)
    if repeated_model:
        prefix = repeated_model.group(1)
        return f'{prefix}:{prefix}\\d+'
    
    # Pattern 2: Model followed by colon and digits (e.g., "PM43:123456")
    model_colon_digits = re.search(r'^([A-Za-z]+):(\d+)$', pattern)
    if model_colon_digits:
        model = model_colon_digits.group(1)
        return f'{model}:\\d+'
    
    # Pattern 3: Text followed by dash and digits (e.g., "Device-12345")
    text_dash_digits = re.search(r'^([A-Za-z]+)-(\d+)$', pattern)
    if text_dash_digits:
        text = text_dash_digits.group(1)
        return f'{text}-\\d+'
    
    # Pattern 4: Text followed by space and alphanumeric ID (e.g., "Model ABC123")
    text_space_id = re.search(r'^([A-Za-z]+)\s+([A-Z]+\d+)$', pattern)
    if text_space_id:
        text = text_space_id.group(1)
        return f'{text}\\s+[A-Z]+\\d+'
    
    # Pattern 5: Version numbers (e.g., "v1.2.3", "1.2.3")
    version_pattern = re.search(r'(\d+\.\d+\.\d+)$', pattern)
    if version_pattern:
        base = pattern[:pattern.rfind(version_pattern.group(1))]
        return f'{base}\\d+\\.\\d+\\.\\d+'
    
    # Pattern 6: Long numeric sequences (likely serial numbers)
    # Replace sequences of 8+ digits with \d+
    long_digits = re.search(r'(\d{8,})', pattern)
    if long_digits:
        return re.sub(r'\d{8,}', r'\\d+', pattern)
    
    # Pattern 7: UUIDs or similar hex patterns
    uuid_pattern = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', pattern, re.IGNORECASE)
    if uuid_pattern:
        return re.sub(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '[0-9a-f-]+', pattern, flags=re.IGNORECASE)
    
    # If no pattern matches, return as-is
    return pattern


def extract_title(html: str) -> Optional[str]:
    """Extract title from HTML"""
    if isinstance(html, bytes):
        html = html.decode('utf-8', errors='ignore')
    match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        # Clean up title
        title = re.sub(r'\s+', ' ', title)
        return title[:60]
    return None


def extract_signature_patterns(html: str, app_name: str = None, max_patterns: int = 3) -> List[str]:
    """
    Extract unique signature patterns from HTML that can identify this application.
    
    Args:
        html: HTML content
        app_name: Application name (from AI) to help find specific patterns
        max_patterns: Maximum number of patterns to return
    
    Returns a list of distinctive strings found in the HTML.
    """
    if isinstance(html, bytes):
        html = html.decode('utf-8', errors='ignore')
    
    patterns = []
    
    # 1. Get title - most reliable identifier
    title = extract_title(html)
    if title:
        # Clean up title for signature and make it generic
        clean_title = title.split('|')[0].split('-')[0].strip()[:40]
        
        # Detect and generalize patterns with IDs/serial numbers
        # Examples: "PM43:PM4318922145206" -> "PM43:PM43\\d+"
        #           "Device-12345" -> "Device-\\d+"
        #           "Model ABC123" -> "Model [A-Z]+\\d+"
        generic_title = _generalize_pattern(clean_title)
        patterns.append(f'<title>{generic_title}')
    
    # 2. Look for application name in HTML (if provided by AI)
    if app_name:
        app_name_lower = app_name.lower()
        # Search for app name in various places
        
        # In URLs/paths
        path_match = re.search(rf'/({app_name_lower}[^/"\s]{{0,20}})', html.lower())
        if path_match:
            patterns.append(path_match.group(1))
        
        # In class names or IDs containing app name
        class_match = re.search(rf'(?:class|id)=["\']([^"\']*{app_name_lower}[^"\']*)["\']', html.lower())
        if class_match:
            patterns.append(class_match.group(1))
        
        # In script sources
        script_match = re.search(rf'src=["\'][^"\']*({app_name_lower}[^"\']*\.js)["\']', html.lower())
        if script_match:
            patterns.append(script_match.group(1))
    
    # 3. Look for unique application-specific patterns
    # Copyright with company/product name
    copyright_match = re.search(r'(?:©|Copyright|&copy;)\s*(?:\d{4}\s*)?([A-Z][a-zA-Z\s&]{3,30})', html)
    if copyright_match:
        patterns.append(copyright_match.group(0)[:50])
    
    # Meta generator or application tags
    meta_match = re.search(r'<meta[^>]+(?:generator|application-name)[^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if meta_match:
        patterns.append(meta_match.group(1))
    
    # Unique JavaScript global variables (often contain app name)
    js_var_match = re.search(r'var\s+(app|APP|App|application|Application)[A-Za-z]*\s*=', html)
    if js_var_match:
        patterns.append(js_var_match.group(0))
    
    # ng-app for Angular applications
    ng_app_match = re.search(r'ng-app=["\']([^"\']+)["\']', html)
    if ng_app_match:
        patterns.append(f'ng-app="{ng_app_match.group(1)}"')
    
    # 4. Try to parse HTML for unique elements (fallback)
    if len(patterns) < max_patterns:
        try:
            extractor = SignatureExtractor()
            extractor.feed(html)
            
            # Add logo images (very specific)
            for src in extractor.img_srcs[:1]:
                if src not in patterns:
                    patterns.append(src)
            
            # Add form actions with unique paths
            for action in extractor.form_actions[:1]:
                if action.startswith('/') and len(action) > 5:
                    if action not in patterns:
                        patterns.append(action)
        except:
            pass
    
    # Remove duplicates while preserving order
    seen = set()
    unique_patterns = []
    for p in patterns:
        p_lower = p.lower()
        if p_lower not in seen and len(p) > 3:
            seen.add(p_lower)
            unique_patterns.append(p)
    
    return unique_patterns[:max_patterns]


class LearnedCredentialsManager:
    """
    Manages learned credentials by adding them to EyeWitness signature files.
    
    When credentials are verified to work, they are added to:
    - signatures.txt: For credential information display
    - categories.txt: For categorization
    """
    
    def __init__(self, signatures_path: Optional[str] = None, categories_path: Optional[str] = None):
        """
        Initialize the credentials manager.
        
        Args:
            signatures_path: Path to signatures.txt
            categories_path: Path to categories.txt
        """
        module_dir = Path(__file__).parent.parent
        
        self.signatures_path = signatures_path or str(module_dir / 'signatures.txt')
        self.categories_path = categories_path or str(module_dir / 'categories.txt')
        
        # Cache of existing signatures to avoid duplicates
        self._existing_signatures = self._load_existing_signatures()
    
    def _load_existing_signatures(self) -> set:
        """Load existing signature patterns to avoid duplicates."""
        existing = set()
        
        if os.path.exists(self.signatures_path):
            try:
                with open(self.signatures_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '|' in line:
                            # Get the signature part (before |)
                            sig_part = line.split('|')[0].lower()
                            existing.add(sig_part)
            except:
                pass
        
        return existing
    
    def _signature_exists(self, signature_pattern: str) -> bool:
        """Check if a signature pattern already exists."""
        return signature_pattern.lower() in self._existing_signatures
    
    def add_credential(self, 
                       application_name: str,
                       username: str,
                       password: str,
                       url: str,
                       html_content: Optional[str] = None,
                       page_title: Optional[str] = None,
                       auth_type: Optional[str] = None,
                       category: str = "infrastructure") -> bool:
        """
        Add a verified working credential to signatures.txt and categories.txt.
        
        Args:
            application_name: Name of the application
            username: Working username
            password: Working password  
            url: URL where this credential worked
            html_content: HTML content for signature extraction
            page_title: Page title
            auth_type: Authentication type (e.g., "Local")
            category: Category for categories.txt
            
        Returns:
            True if credential was added, False if already exists
        """
        # Build signature pattern
        signature_parts = []
        
        # Use page title if available
        if page_title:
            signature_parts.append(f'<title>{page_title}</title>')
        elif html_content:
            title = extract_title(html_content)
            if title:
                signature_parts.append(f'<title>{title}</title>')
        
        # Extract additional patterns from HTML (pass app name for better matching)
        if html_content:
            additional_patterns = extract_signature_patterns(
                html_content, 
                app_name=application_name,
                max_patterns=2
            )
            for pattern in additional_patterns:
                if pattern not in signature_parts:
                    signature_parts.append(pattern)
        
        if not signature_parts:
            print(f"[!] Could not extract signature patterns for {application_name}")
            return False
        
        # Build signature string
        signature_pattern = ';'.join(signature_parts[:3])
        
        # Check if already exists
        if self._signature_exists(signature_pattern):
            print(f"[*] Signature already exists for {application_name}")
            return False
        
        # Build credential description (format: AppName / user:pass)
        if auth_type:
            cred_desc = f"{application_name} (Auth: {auth_type}) / {username}:{password}"
        else:
            cred_desc = f"{application_name} / {username}:{password}"
        
        # Add to signatures.txt
        signature_line = f"{signature_pattern}|{cred_desc}"
        
        try:
            with open(self.signatures_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{signature_line}")
            
            # Also add to categories.txt
            category_line = f"{signature_pattern}|{category}"
            with open(self.categories_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{category_line}")
            
            # Update cache
            self._existing_signatures.add(signature_pattern.lower())
            
            print(f"[+] Added to signatures: {application_name} - {username}:***")
            return True
            
        except IOError as e:
            print(f"[!] Error adding signature: {e}")
            return False
    
    def find_credentials(self, 
                         url: str,
                         page_title: Optional[str] = None,
                         html_content: Optional[str] = None) -> List[Dict]:
        """
        This method is now a no-op since credentials are in signatures.txt
        and will be matched by the normal EyeWitness signature matching.
        
        Returns empty list - matching is handled by EyeWitness core.
        """
        return []
    
    def update_success(self, application_name: str, username: str, password: str):
        """No-op for compatibility - signatures don't track success count."""
        pass
    
    def get_all_credentials(self) -> List[Dict]:
        """Get all learned credentials from signatures.txt."""
        credentials = []
        
        if os.path.exists(self.signatures_path):
            try:
                with open(self.signatures_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and '|' in line:
                            parts = line.split('|')
                            if len(parts) >= 2:
                                desc = parts[1]
                                # Try to parse credentials from description
                                match = re.search(r'(\w+)[:/](\S+)$', desc)
                                if match:
                                    credentials.append({
                                        'signature': parts[0],
                                        'description': desc,
                                        'username': match.group(1),
                                        'password': match.group(2)
                                    })
            except:
                pass
        
        return credentials


# Convenience function
def get_learned_credentials_manager(signatures_path: Optional[str] = None,
                                    categories_path: Optional[str] = None) -> LearnedCredentialsManager:
    """Get a LearnedCredentialsManager instance."""
    return LearnedCredentialsManager(signatures_path, categories_path)
