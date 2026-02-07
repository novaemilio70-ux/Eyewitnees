#!/usr/bin/env python3
"""
HTML Form Analyzer for EyeWitness
Analyzes HTML to identify login forms and extract authentication details
"""

import re
from typing import Optional, Dict, List
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class FormField:
    """Represents a form field"""
    def __init__(self, name: str, field_type: str, required: bool = False, value: str = None):
        self.name = name
        self.type = field_type  # text, password, email, etc.
        self.required = required
        self.value = value  # Preserve the value attribute (important for hidden fields)
    
    def __repr__(self):
        return f"FormField(name={self.name}, type={self.type}, required={self.required})"


class LoginForm:
    """Represents a login form"""
    def __init__(self, action: str, method: str = "POST"):
        self.action = action
        self.method = method.upper()
        self.fields: List[FormField] = []
        self.username_field: Optional[FormField] = None
        self.password_field: Optional[FormField] = None
        self.csrf_token: Optional[str] = None  # CSRF field name
        self.csrf_value: Optional[str] = None  # CSRF token value
        self.other_fields: List[FormField] = []
    
    def add_field(self, field: FormField):
        """Add a field to the form"""
        self.fields.append(field)
        
        # Auto-detect username/password fields
        field_name_lower = field.name.lower() if field.name else ""
        if field.type == "password":
            if not self.password_field:
                self.password_field = field
        elif any(keyword in field_name_lower for keyword in ['user', 'login', 'email', 'account', 'name']):
            if not self.username_field:
                self.username_field = field
        else:
            self.other_fields.append(field)
    
    def get_auth_endpoint(self, base_url: str) -> str:
        """Get full URL for authentication endpoint"""
        if not self.action or self.action.startswith('http'):
            return self.action or base_url
        
        # Handle relative URLs
        return urljoin(base_url, self.action)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage"""
        return {
            'action': self.action,
            'method': self.method,
            'username_field': self.username_field.name if self.username_field else None,
            'password_field': self.password_field.name if self.password_field else None,
            'csrf_token': self.csrf_token,
            'csrf_value': self.csrf_value,  # Include the actual token value
            'all_fields': [{'name': f.name, 'type': f.type, 'required': f.required, 'value': f.value} for f in self.fields]
        }
    
    def __repr__(self):
        return f"LoginForm(action={self.action}, method={self.method}, fields={len(self.fields)})"


class FormParser(HTMLParser):
    """HTML Parser to extract login forms"""
    
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.forms: List[LoginForm] = []
        self.current_form: Optional[LoginForm] = None
        self.current_field: Optional[FormField] = None
        self.in_form = False
        self.in_input = False
    
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag == 'form':
            # Extract form action and method
            action = attrs_dict.get('action', '')
            method = attrs_dict.get('method', 'POST').upper()
            self.current_form = LoginForm(action=action, method=method)
            self.in_form = True
        
        elif tag == 'input' and self.in_form:
            field_type = attrs_dict.get('type', 'text').lower()
            field_name = attrs_dict.get('name', '')
            field_value = attrs_dict.get('value', '')  # Extract the value!
            required = 'required' in attrs_dict or attrs_dict.get('required') == 'required'
            
            # Detect CSRF tokens (hidden fields with specific names)
            if field_type == 'hidden' and any(keyword in field_name.lower() for keyword in ['csrf', 'token', '_token', 'authenticity', 'nonce', '__requestverificationtoken']):
                if self.current_form:
                    self.current_form.csrf_token = field_name
                    self.current_form.csrf_value = field_value  # Store the actual value!
            
            # Create field with its value
            field = FormField(name=field_name, field_type=field_type, required=required, value=field_value)
            if self.current_form:
                self.current_form.add_field(field)
            self.in_input = True
        
        elif tag == 'button' and self.in_form:
            # Check if it's a submit button
            if attrs_dict.get('type', '').lower() == 'submit':
                pass  # Form has submit capability
    
    def handle_endtag(self, tag):
        if tag == 'form':
            if self.current_form and len(self.current_form.fields) > 0:
                # Only add forms that have fields
                self.forms.append(self.current_form)
            self.current_form = None
            self.in_form = False
        elif tag == 'input':
            self.in_input = False


class FormAnalyzer:
    """Analyzer for HTML forms"""
    
    @staticmethod
    def find_login_forms(html_content: str, base_url: str) -> List[LoginForm]:
        """
        Find login forms in HTML content
        
        Args:
            html_content: HTML source code
            base_url: Base URL for resolving relative form actions
            
        Returns:
            List of LoginForm objects
        """
        parser = FormParser(base_url)
        
        try:
            # Handle bytes
            if isinstance(html_content, bytes):
                html_content = html_content.decode('utf-8', errors='ignore')
            
            parser.feed(html_content)
        except Exception as e:
            print(f"[!] Form parsing error: {e}")
            return []
        
        # Filter for login forms (forms with password fields)
        login_forms = [form for form in parser.forms if form.password_field]
        
        # If no forms with password fields, check for forms with common login indicators
        if not login_forms:
            for form in parser.forms:
                # Check form action/ID/class for login indicators
                form_html = html_content.lower()
                if any(keyword in form_html for keyword in ['login', 'signin', 'auth', 'authenticate']):
                    login_forms.append(form)
        
        return login_forms
    
    @staticmethod
    def extract_auth_info(html_content: str, base_url: str) -> Dict:
        """
        Extract comprehensive authentication information
        
        Args:
            html_content: HTML source code
            base_url: Base URL
            
        Returns:
            Dictionary with authentication details
        """
        forms = FormAnalyzer.find_login_forms(html_content, base_url)
        
        result = {
            'login_forms': [form.to_dict() for form in forms],
            'has_login_form': len(forms) > 0,
            'primary_form': forms[0].to_dict() if forms else None
        }
        
        # Try to identify authentication type from HTML
        html_lower = html_content.lower() if isinstance(html_content, str) else html_content.decode('utf-8', errors='ignore').lower()
        
        # Check for common auth patterns (use html_lower which is always a string)
        auth_patterns = {
            'basic_auth': re.search(r'www-authenticate.*basic', html_lower),
            'oauth': any(keyword in html_lower for keyword in ['oauth', 'openid', 'saml']),
            'ldap': 'ldap' in html_lower,
            'sso': 'single sign-on' in html_lower or 'sso' in html_lower,
            'api_key': 'api' in html_lower and 'key' in html_lower
        }
        
        result['auth_type'] = 'form_based'
        for auth_type, detected in auth_patterns.items():
            if detected:
                result['auth_type'] = auth_type
                break
        
        return result

