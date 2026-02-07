#!/usr/bin/env python3
"""
Signature Manager - Modern JSON-based signature system

Manages application signatures and credentials in a structured JSON format.
Replaces the old signatures.txt/categories.txt system with a more flexible,
maintainable approach.

IMPORTANT: This file stores KNOWN DEFAULT CREDENTIALS for applications.
It does NOT track test results or status - those belong in the project database.

Format:
{
  "version": "2.1",
  "signatures": [
    {
      "id": "unique_id",
      "application_name": "Application Name",
      "signature_patterns": ["pattern1", "pattern2", "pattern3"],
      "category": "network_device",
      "credentials": [
        {
          "username": "admin",
          "password": "password",
          "source": "default"  # default, documented, common, manual
        }
      ],
      "metadata": {
        "created_at": "2025-12-28T10:00:00",
        "updated_at": "2025-12-28T10:00:00",
        "discovered_by": "ai"
      }
    }
  ]
}

Categories:
- webserver: Web servers (IIS, Apache, nginx)
- appserver: Application servers (JBoss, Tomcat, WebLogic)
- storage: Storage devices (IBM Storwize, Quantum DXi, QNAP)
- network_device: Switches, routers, APs, firewalls (Cisco, Ubiquiti, WatchGuard)
- network_management: Network management systems (UNMS, UniFi Controller)
- printer: Printers and MFPs (HP LaserJet, Ricoh, Epson)
- voip: VoIP phones (Grandstream, Yealink)
- video_conference: Video/presentation systems (Polycom Pano, Crestron)
- idrac: Server management (Dell iDRAC, HP iLO)
- monitoring: Monitoring systems (Grafana, Nagios, Zabbix)
- itsm: IT Service Management (ManageEngine ServiceDesk)
- iot: IoT devices (IDENTEC Solutions)
- business_app: Business applications (custom apps)
- api: API documentation (Swagger UI)
- error_page: Error pages (401, 403, 404)
- unknown: Unidentified applications
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import hashlib


class SignatureManager:
    """Manages application signatures and credentials in JSON format"""
    
    def __init__(self, signatures_path: Optional[str] = None):
        """
        Initialize the Signature Manager
        
        Args:
            signatures_path: Path to signatures.json file
        """
        module_dir = Path(__file__).parent.parent
        self.signatures_path = signatures_path or str(module_dir / 'signatures.json')
        
        # Load existing signatures
        self.signatures = self._load_signatures()
    
    def _load_signatures(self) -> Dict:
        """Load signatures from JSON file"""
        if not os.path.exists(self.signatures_path):
            return {
                "version": "2.0",
                "signatures": []
            }
        
        try:
            with open(self.signatures_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure version and signatures exist
                if 'version' not in data:
                    data['version'] = '2.0'
                if 'signatures' not in data:
                    data['signatures'] = []
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[!] Error loading signatures.json: {e}")
            return {
                "version": "2.0",
                "signatures": []
            }
    
    def _save_signatures(self):
        """Save signatures to JSON file"""
        try:
            # Create backup before saving
            if os.path.exists(self.signatures_path):
                backup_path = f"{self.signatures_path}.backup"
                with open(self.signatures_path, 'r', encoding='utf-8') as f:
                    with open(backup_path, 'w', encoding='utf-8') as b:
                        b.write(f.read())
            
            # Write to temporary file first, then rename (atomic write)
            temp_path = f"{self.signatures_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.signatures, f, indent=2, ensure_ascii=False)
            
            os.replace(temp_path, self.signatures_path)
            return True
        except IOError as e:
            print(f"[!] Error saving signatures.json: {e}")
            return False
    
    def _generate_signature_id(self, patterns: List[str], app_name: str) -> str:
        """Generate a unique ID for a signature"""
        combined = f"{app_name}:{':'.join(sorted(patterns))}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()[:12]
    
    def _find_signature_by_patterns(self, patterns: List[str]) -> Optional[Dict]:
        """Find a signature by matching patterns"""
        patterns_lower = [p.lower() for p in patterns]
        
        for sig in self.signatures['signatures']:
            sig_patterns = [p.lower() for p in sig.get('signature_patterns', [])]
            
            # Check if all patterns match (order-independent)
            if set(patterns_lower) == set(sig_patterns):
                return sig
            
            # Also check if any subset matches (for flexible matching)
            if len(patterns_lower) > 0 and any(p in sig_patterns for p in patterns_lower):
                return sig
        
        return None
    
    def add_or_update_signature(self,
                                application_name: str,
                                signature_patterns: List[str],
                                category: str = "infrastructure",
                                credentials: Optional[List[Dict]] = None,
                                metadata: Optional[Dict] = None) -> str:
        """
        Add a new signature or update an existing one
        
        Args:
            application_name: Name of the application
            signature_patterns: List of HTML patterns that identify this app
            category: Category (infrastructure, netdev, printer, etc.)
            credentials: List of credential dicts to add
            metadata: Additional metadata
            
        Returns:
            Signature ID
        """
        # Normalize patterns
        signature_patterns = [p.strip() for p in signature_patterns if p.strip()]
        if not signature_patterns:
            raise ValueError("At least one signature pattern is required")
        
        # Find existing signature
        existing = self._find_signature_by_patterns(signature_patterns)
        
        if existing:
            # Update existing signature
            sig_id = existing['id']
            existing['application_name'] = application_name
            existing['category'] = category
            existing['metadata']['updated_at'] = datetime.now().isoformat()
            
            # Merge credentials
            if credentials:
                existing_creds = existing.get('credentials', [])
                for new_cred in credentials:
                    # Check if credential already exists
                    cred_exists = False
                    for existing_cred in existing_creds:
                        if (existing_cred.get('username') == new_cred.get('username') and
                            existing_cred.get('password') == new_cred.get('password')):
                            # Update existing credential
                            existing_cred.update(new_cred)
                            cred_exists = True
                            break
                    
                    if not cred_exists:
                        existing_creds.append(new_cred)
                
                existing['credentials'] = existing_creds
            
            # Update metadata
            if metadata:
                existing['metadata'].update(metadata)
        else:
            # Create new signature
            sig_id = self._generate_signature_id(signature_patterns, application_name)
            
            new_sig = {
                "id": sig_id,
                "application_name": application_name,
                "signature_patterns": signature_patterns,
                "category": category,
                "credentials": credentials or [],
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "discovered_by": metadata.get('discovered_by', 'unknown') if metadata else 'unknown'
                }
            }
            
            if metadata:
                new_sig['metadata'].update(metadata)
            
            self.signatures['signatures'].append(new_sig)
        
        # Save to file
        self._save_signatures()
        return sig_id
    
    def add_credential(self,
                      signature_patterns: List[str],
                      username: str,
                      password: str,
                      source: str = "manual") -> bool:
        """
        Add a known credential to an existing signature
        
        Args:
            signature_patterns: Patterns to identify the signature
            username: Username
            password: Password
            source: default, documented, common, manual
            
        Note: Test results (working/failed) are stored in the EyeWitness project database,
              not in signatures.json. This file only stores known default credentials to try.
            
        Returns:
            True if added, False if signature not found
        """
        sig = self._find_signature_by_patterns(signature_patterns)
        if not sig:
            return False
        
        # Check if credential already exists
        for cred in sig.get('credentials', []):
            if cred.get('username') == username and cred.get('password') == password:
                # Update source if different
                cred['source'] = source
                self._save_signatures()
                return True
        
        # Add new credential
        new_cred = {
            "username": username,
            "password": password,
            "source": source
        }
        
        if 'credentials' not in sig:
            sig['credentials'] = []
        sig['credentials'].append(new_cred)
        sig['metadata']['updated_at'] = datetime.now().isoformat()
        
        self._save_signatures()
        return True
    
    def find_matching_signature(self, html_content: str) -> Optional[Dict]:
        """
        Find a signature that matches the given HTML content
        
        Supports both literal patterns and regex patterns (patterns containing \\d+, [A-Z]+, etc.)
        
        Args:
            html_content: HTML content to match against
            
        Returns:
            Matching signature dict or None
        """
        if not html_content:
            return None
        
        import re
        
        if isinstance(html_content, bytes):
            html_content = html_content.decode('utf-8', errors='ignore')
        
        html_lower = html_content.lower()
        best_match = None
        max_matches = 0
        
        # Try to find matches
        for sig in self.signatures['signatures']:
            patterns = sig.get('signature_patterns', [])
            if not patterns:
                continue
            
            current_matches = 0
            for pattern in patterns:
                pattern_lower = pattern.lower()
                
                # Check if pattern contains regex-like syntax
                is_regex = '\\d+' in pattern or '\\s+' in pattern or '[A-Z]+' in pattern or '[0-9a-f-]+' in pattern
                
                if is_regex:
                    # Try to match as regex (case-insensitive)
                    try:
                        # Convert our simplified patterns to proper regex
                        regex_pattern = pattern_lower
                        # Replace our simplified patterns with proper regex
                        regex_pattern = regex_pattern.replace('\\d+', r'\d+')
                        regex_pattern = regex_pattern.replace('\\s+', r'\s+')
                        regex_pattern = regex_pattern.replace('[A-Z]+', r'[A-Z]+')
                        regex_pattern = regex_pattern.replace('[0-9a-f-]+', r'[0-9a-f-]+')
                        
                        # Escape other special regex characters but keep our patterns
                        # We need to escape everything except our patterns
                        parts = re.split(r'(\\d\+|\\s\+|\[A-Z\]\+|\[0-9a-f-\]\+)', regex_pattern)
                        escaped_parts = []
                        for part in parts:
                            if part in (r'\d+', r'\s+', r'[A-Z]+', r'[0-9a-f-]+'):
                                escaped_parts.append(part)
                            else:
                                escaped_parts.append(re.escape(part))
                        regex_pattern = ''.join(escaped_parts)
                        
                        if re.search(regex_pattern, html_lower):
                            current_matches += 1
                    except re.error:
                        # If regex fails, fall back to literal match
                        if pattern_lower in html_lower:
                            current_matches += 1
                else:
                    # Literal match
                    if pattern_lower in html_lower:
                        current_matches += 1
            
            if current_matches > max_matches:
                max_matches = current_matches
                best_match = sig
        
        return best_match
    
    def get_credentials_for_signature(self, signature_patterns: List[str]) -> List[Dict]:
        """Get all credentials for a signature"""
        sig = self._find_signature_by_patterns(signature_patterns)
        if not sig:
            return []
        
        return sig.get('credentials', [])
    
    def get_working_credentials(self, signature_patterns: List[str]) -> List[Dict]:
        """
        Get all known credentials for a signature.
        
        Note: In the simplified schema, all credentials in signatures.json are 
        known default credentials to try. Test results are stored in the project database.
        
        This method returns all credentials for backwards compatibility.
        """
        return self.get_credentials_for_signature(signature_patterns)
    
    def export_to_legacy_format(self, output_path: Optional[str] = None) -> Tuple[str, str]:
        """
        Export signatures to legacy signatures.txt and categories.txt format
        for backward compatibility
        
        Returns:
            Tuple of (signatures.txt content, categories.txt content)
        """
        sig_lines = []
        cat_lines = []
        
        for sig in self.signatures['signatures']:
            patterns = ';'.join(sig.get('signature_patterns', []))
            app_name = sig.get('application_name', 'Unknown')
            category = sig.get('category', 'unknown')
            
            # Get all known credentials for this signature
            all_creds = sig.get('credentials', [])
            
            if all_creds:
                # Format: AppName / user1:pass1 or user2:pass2
                cred_strings = []
                for cred in all_creds:
                    username = cred.get('username', '')
                    password = cred.get('password', '')
                    if username:  # Password can be empty
                        cred_strings.append(f"{username}:{password}")
                
                if cred_strings:
                    cred_desc = f"{app_name} / {' or '.join(cred_strings)}"
                    sig_lines.append(f"{patterns}|{cred_desc}")
            else:
                # No credentials, but still add signature
                sig_lines.append(f"{patterns}|{app_name} / No default credentials")
            
            # Category line
            cat_lines.append(f"{patterns}|{category}")
        
        sig_content = '\n'.join(sig_lines)
        cat_content = '\n'.join(cat_lines)
        
        if output_path:
            sig_file = Path(output_path) / 'signatures.txt'
            cat_file = Path(output_path) / 'categories.txt'
            sig_file.write_text(sig_content, encoding='utf-8')
            cat_file.write_text(cat_content, encoding='utf-8')
        
        return sig_content, cat_content
    
    def get_statistics(self) -> Dict:
        """Get statistics about stored signatures"""
        total_sigs = len(self.signatures['signatures'])
        total_creds = sum(len(sig.get('credentials', [])) for sig in self.signatures['signatures'])
        ai_discovered = sum(
            1 for sig in self.signatures['signatures']
            if sig.get('metadata', {}).get('discovered_by') == 'ai'
        )
        
        # Count by category
        categories = {}
        for sig in self.signatures['signatures']:
            cat = sig.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        # Count by source
        sources = {}
        for sig in self.signatures['signatures']:
            for cred in sig.get('credentials', []):
                src = cred.get('source', 'unknown')
                sources[src] = sources.get(src, 0) + 1
        
        return {
            'total_signatures': total_sigs,
            'total_credentials': total_creds,
            'ai_discovered': ai_discovered,
            'by_category': categories,
            'by_source': sources
        }


# Convenience function
def get_signature_manager(signatures_path: Optional[str] = None) -> SignatureManager:
    """Get a SignatureManager instance"""
    return SignatureManager(signatures_path)

