#!/usr/bin/env python3
"""
AI-powered HTML analyzer for EyeWitness
Uses OpenAI to identify applications from HTML when not found in signatures
"""

import os
import json
import re
from typing import Optional, Dict, List, Tuple
from pathlib import Path

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# Default OpenAI API key (fallback if not provided via env var or argument)
DEFAULT_OPENAI_API_KEY = "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"

class AIAnalyzer:
    """AI-powered analyzer for identifying applications from HTML using OpenAI"""
    
    def __init__(self, api_key: Optional[str] = None, provider: str = "openai"):
        """
        Initialize AI Analyzer
        
        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env var, or default)
            provider: Only 'openai' is supported
        """
        self.provider = "openai"
        # Priority: provided api_key > environment variable > default
        self.api_key = api_key or os.getenv('OPENAI_API_KEY') or DEFAULT_OPENAI_API_KEY
        
        if not HAS_OPENAI:
            raise ImportError("openai package not installed. Install with: pip install openai")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key")
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def _extract_key_indicators(self, html_content: str, url: str) -> str:
        """Extract key indicators from HTML to help AI identify the application"""
        indicators = []
        
        # Extract from URL
        indicators.append(f"URL Path: {url}")
        
        # Extract title
        import re
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        if title_match:
            indicators.append(f"Page Title: {title_match.group(1).strip()}")
        
        # Extract logo/brand images
        logo_patterns = [
            r'<img[^>]+src=["\']([^"\']*logo[^"\']*)["\']',
            r'<img[^>]+src=["\']([^"\']*brand[^"\']*)["\']',
            r'<img[^>]+class=["\'][^"\']*logo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        ]
        for pattern in logo_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches[:3]:
                indicators.append(f"Logo/Brand Image: {match}")
        
        # Extract CSS files (often contain app name)
        css_files = re.findall(r'href=["\']([^"\']+\.css)["\']', html_content, re.IGNORECASE)
        for css in css_files[:5]:
            if not any(skip in css.lower() for skip in ['bootstrap', 'font-awesome', 'normalize', 'reset']):
                indicators.append(f"CSS File: {css}")
        
        # Extract JS app files
        js_files = re.findall(r'src=["\']([^"\']+(?:app|main|bundle)[^"\']*\.js)["\']', html_content, re.IGNORECASE)
        for js in js_files[:3]:
            indicators.append(f"App JS: {js}")
        
        # Extract meta tags
        meta_patterns = [
            r'<meta[^>]+name=["\'](?:application-name|generator|author)["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\'](?:application-name|generator|author)["\']',
        ]
        for pattern in meta_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            for match in matches:
                indicators.append(f"Meta Tag: {match}")
        
        # Extract copyright/footer text
        copyright_match = re.search(r'(?:copyright|©|\(c\))[^<]{0,100}', html_content, re.IGNORECASE)
        if copyright_match:
            indicators.append(f"Copyright: {copyright_match.group(0).strip()[:100]}")
        
        # Extract powered-by or product mentions
        powered_match = re.search(r'(?:powered by|product of|built with)[^<]{0,50}', html_content, re.IGNORECASE)
        if powered_match:
            indicators.append(f"Powered By: {powered_match.group(0).strip()}")
        
        return "\n".join(indicators)
    
    def _check_known_patterns(self, html_content: str, url: str) -> Optional[Dict]:
        """
        Check for known patterns that can be identified without AI.
        This saves API calls and ensures accurate identification for common devices.
        
        Returns:
            Dict with application info if pattern matches, None otherwise
        """
        html_lower = html_content.lower()
        
        # Ricoh printers - "Web Image Monitor" is always Ricoh
        if 'web image monitor' in html_lower:
            # Extract model number from title (RNP followed by hex)
            model_match = re.search(r'(RNP[0-9A-Fa-f]+)', html_content)
            model = model_match.group(1) if model_match else None
            return {
                "application_name": "Ricoh Web Image Monitor",
                "manufacturer": "Ricoh",
                "model": model,
                "version": None,
                "application_type": "Printer",
                "confidence": "high",
                "indicators": ["Web Image Monitor is Ricoh's proprietary printer management interface"],
                "frameworks_detected": []
            }
        
        # Add more known patterns here as needed
        
        return None
    
    def identify_application(self, html_content: str, url: str) -> Optional[Dict]:
        """
        Identify application from HTML using AI
        
        Args:
            html_content: HTML source code
            url: URL of the page
            
        Returns:
            Dict with application info or None
        """
        # First check for known patterns (saves API calls)
        known_result = self._check_known_patterns(html_content, url)
        if known_result:
            return known_result
        
        # Extract key indicators first
        key_indicators = self._extract_key_indicators(html_content, url)
        
        # Truncate HTML if too long (AI models have token limits)
        max_html_length = 30000  # Reduced to leave room for better prompt
        if len(html_content) > max_html_length:
            html_content = html_content[:max_html_length] + "... [truncated]"
        
        prompt = f"""You are a security expert identifying web applications. Your goal is to identify the ACTUAL APPLICATION, not the UI frameworks it uses.

IMPORTANT RULES:
1. IGNORE UI frameworks like: Kendo UI, Angular, React, Vue, Bootstrap, jQuery, Material UI - these are NOT the application
2. Look for the ACTUAL product/application name in: URL path, logo files, CSS theme names, page titles, copyright text
3. Common patterns: "AppName Portal", "AppName Admin", product-specific CSS files, logo filenames
4. If URL contains a product name (e.g., "KSPortal" = "KnowledgeSync Portal"), use that
5. ALWAYS identify the MANUFACTURER/VENDOR from logos, copyright, or HTML - this is CRITICAL for finding default credentials
6. For hardware devices (printers, routers, switches, etc.): ALWAYS include the manufacturer in the name (e.g., "Honeywell PM43", "Cisco RV340", "HP LaserJet")

KEY INDICATORS EXTRACTED:
{key_indicators}

FULL HTML (for additional context):
{html_content}

Based on the above, identify the ACTUAL APPLICATION (not frameworks).

Respond ONLY with JSON:
{{
    "application_name": "MANUFACTURER + Product (e.g., Honeywell PM43, Cisco IOS, HP LaserJet, Dell iDRAC)",
    "manufacturer": "company name from logo/copyright (e.g., Honeywell, Cisco, HP, Dell)",
    "model": "specific model number if found (e.g., PM43, RV340)",
    "version": "version if found or null",
    "application_type": "Printer/Router/Switch/Portal/Admin Panel/CMS/ERP/etc",
    "confidence": "high/medium/low",
    "indicators": ["specific indicators that identified this app"],
    "frameworks_detected": ["list UI frameworks separately here"]
}}"""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a security expert analyzing web applications. Always respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                result_json = json.loads(json_match.group())
                return result_json
            else:
                # Try parsing entire response
                result_json = json.loads(result_text)
                return result_json
                
        except json.JSONDecodeError as e:
            print(f"[!] AI response parsing error: {e}")
            print(f"[*] Raw response: {result_text[:200]}")
            return None
        except Exception as e:
            print(f"[!] AI analysis error: {e}")
            return None
    
    def _get_known_credentials(self, manufacturer: Optional[str], application_name: str) -> Optional[List[Dict]]:
        """
        Return known default credentials for common devices.
        This ensures we always find credentials for well-known products.
        
        Returns:
            List of credentials if known, None to continue with AI search
        """
        app_lower = application_name.lower() if application_name else ""
        mfg_lower = manufacturer.lower() if manufacturer else ""
        
        # Ricoh printers (Web Image Monitor)
        if 'ricoh' in mfg_lower or 'web image monitor' in app_lower:
            return [
                {"username": "admin", "password": "", "description": "Default admin (blank password)", "source": "Ricoh documentation"},
                {"username": "supervisor", "password": "", "description": "Supervisor account (blank password)", "source": "Ricoh documentation"},
                {"username": "admin", "password": "admin", "description": "Common admin credentials", "source": "common knowledge"},
            ]
        
        return None
    
    def search_default_credentials(self, application_name: str, application_type: Optional[str] = None, 
                                     manufacturer: Optional[str] = None, model: Optional[str] = None) -> List[Dict]:
        """
        Search for default credentials using AI
        
        Args:
            application_name: Name of the application
            application_type: Type of application (optional)
            manufacturer: Manufacturer/vendor name (optional)
            model: Model number (optional)
            
        Returns:
            List of credential dictionaries
        """
        if not application_name:
            return []
        
        # First check for known credentials (saves API calls)
        known_creds = self._get_known_credentials(manufacturer, application_name)
        if known_creds:
            return known_creds
        
        # Build search context with all available information
        search_context = application_name
        if manufacturer and manufacturer.lower() not in application_name.lower():
            search_context = f"{manufacturer} {application_name}"
        if model and model not in application_name:
            search_context = f"{search_context} {model}"
        
        prompt = f"""You are a security researcher with EXTENSIVE knowledge of default credentials for ALL types of devices and applications.

APPLICATION: {application_name}
{('MANUFACTURER: ' + manufacturer) if manufacturer else ''}
{('MODEL: ' + model) if model else ''}
{('TYPE: ' + application_type) if application_type else ''}

SEARCH CONTEXT: {search_context}

Search your knowledge for DEFAULT/FACTORY credentials. This is CRITICAL for security testing.

SEARCH STRATEGIES:
1. If this is a PRINTER (Honeywell, HP, Canon, Epson, Lexmark, Brother, Zebra, Ricoh, etc.):
   - Common: admin/admin, Admin/Admin, admin/(blank), root/root
   - Honeywell/Intermec printers: itadmin/pass, admin/pass
   - HP printers: admin/(blank), admin/admin
   - Canon printers: 7654321/7654321
   - Zebra printers: admin/1234
   - Ricoh printers (Web Image Monitor): admin/(blank), supervisor/(blank), admin/admin
   
2. If this is a NETWORK DEVICE (Cisco, Juniper, Fortinet, etc.):
   - Cisco: admin/admin, cisco/cisco, enable/(blank)
   - Fortinet: admin/(blank), maintainer/admin
   
3. If this is a WEB APPLICATION:
   - Check installation manuals for default admin accounts
   - Common: admin/admin, admin/password, administrator/password

4. For INDUSTRIAL/ENTERPRISE devices:
   - Often have itadmin, service, or maintenance accounts
   - Check manufacturer documentation

For "{search_context}", provide ALL known default credentials.

Respond with a JSON array (if none found, return empty array []):
[
    {{
        "username": "exact username",
        "password": "exact password", 
        "description": "admin account / IT admin / service account / etc",
        "source": "installation manual / documentation / common knowledge"
    }}
]

HARDWARE DEFAULT CREDENTIALS EXAMPLES:
- Honeywell/Intermec PM43 Printer: itadmin/pass, admin/pass
- HP LaserJet: admin/(blank)
- Canon Printer: 7654321/7654321
- Cisco Switch: admin/admin, cisco/cisco
- Zebra Printer: admin/1234
- Kyocera Printer: Admin/Admin
- Ricoh Printer (Web Image Monitor): admin/(blank), supervisor/(blank)
- Ricoh MFP: admin/admin

SOFTWARE DEFAULT CREDENTIALS EXAMPLES:
- KnowledgeSync: admin/password
- WordPress: admin/admin  
- Grafana: admin/admin
- SonarQube: admin/admin
- Nagios: nagiosadmin/nagios

Return ONLY the JSON array. If you know credentials for this device/application, YOU MUST include them."""

        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a security researcher. Provide default credentials in JSON format only."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=800
                )
                result_text = response.choices[0].message.content.strip()
            
            # Extract JSON array
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                credentials = json.loads(json_match.group())
                return credentials if isinstance(credentials, list) else []
            else:
                credentials = json.loads(result_text)
                return credentials if isinstance(credentials, list) else []
                
        except json.JSONDecodeError as e:
            print(f"[!] AI credentials parsing error: {e}")
            return []
        except Exception as e:
            print(f"[!] AI credentials search error: {e}")
            return []


def create_ai_analyzer(api_key: Optional[str] = None, provider: Optional[str] = None) -> Optional[AIAnalyzer]:
    """
    Factory function to create AI analyzer if OpenAI API key is available
    
    Returns:
        AIAnalyzer instance or None if not configured
    """
    openai_key = os.getenv('OPENAI_API_KEY')
    # Priority: provided api_key > environment variable > default
    final_api_key = api_key or openai_key or DEFAULT_OPENAI_API_KEY
    
    print(f"[*] AI Configuration:")
    if api_key:
        print(f"    - API Key: ✅ Provided via argument")
    elif openai_key:
        print(f"    - OPENAI_API_KEY: ✅ Set from environment")
    elif DEFAULT_OPENAI_API_KEY:
        print(f"    - API Key: ✅ Using default (built-in)")
    
    if not final_api_key:
        print(f"    [!] No API key found. Set OPENAI_API_KEY environment variable")
        print(f"    [!] AI will not be available")
        return None
    
    try:
        analyzer = AIAnalyzer(api_key=final_api_key)
        print(f"    [+] AI Analyzer initialized successfully")
        return analyzer
    except (ValueError, ImportError) as e:
        print(f"    [!] AI Analyzer initialization failed: {e}")
        return None

