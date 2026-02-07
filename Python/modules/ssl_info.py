#!/usr/bin/env python3
"""
SSL/TLS certificate information collection module for EyeWitness
"""

import ssl
import socket
from urllib.parse import urlparse
from typing import Dict, Optional
from datetime import datetime


def get_ssl_cert_info(url: str, timeout: int = 5) -> Optional[Dict]:
    """
    Get SSL/TLS certificate information from a URL
    
    Args:
        url: Target URL
        timeout: Connection timeout in seconds
        
    Returns:
        Dict with SSL certificate info or None if not HTTPS or error
    """
    parsed = urlparse(url)
    
    # Only for HTTPS
    if parsed.scheme != 'https':
        return None
    
    hostname = parsed.hostname
    if not hostname:
        return None
    
    port = parsed.port or 443
    
    try:
        # Create SSL context
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
                
                # Parse certificate subject
                subject = {}
                if cert.get('subject'):
                    for item in cert['subject']:
                        if isinstance(item, tuple) and len(item) == 2:
                            key, value = item[0], item[1]
                            if isinstance(key, tuple) and len(key) > 0:
                                key_name = key[0]
                                subject[key_name] = value
                
                # Parse certificate issuer
                issuer = {}
                if cert.get('issuer'):
                    for item in cert['issuer']:
                        if isinstance(item, tuple) and len(item) == 2:
                            key, value = item[0], item[1]
                            if isinstance(key, tuple) and len(key) > 0:
                                key_name = key[0]
                                issuer[key_name] = value
                
                # Format dates
                valid_from = cert.get('notBefore', '')
                valid_to = cert.get('notAfter', '')
                
                # Extract common name from subject
                subject_name = subject.get('commonName', '') or subject.get('CN', '')
                if not subject_name and isinstance(cert.get('subject'), list):
                    # Try alternative format
                    for item in cert.get('subject', []):
                        if isinstance(item, tuple) and len(item) >= 2:
                            if item[0] == 'commonName' or (isinstance(item[0], tuple) and len(item[0]) > 0 and item[0][0] == 'commonName'):
                                subject_name = item[1] if len(item) > 1 else ''
                                break
                
                # Extract issuer name
                issuer_name = issuer.get('commonName', '') or issuer.get('CN', '') or issuer.get('organizationName', '') or issuer.get('O', '')
                if not issuer_name and isinstance(cert.get('issuer'), list):
                    for item in cert.get('issuer', []):
                        if isinstance(item, tuple) and len(item) >= 2:
                            if item[0] == 'commonName' or item[0] == 'organizationName' or (isinstance(item[0], tuple) and len(item[0]) > 0 and item[0][0] in ['commonName', 'organizationName']):
                                issuer_name = item[1] if len(item) > 1 else ''
                                break
                
                return {
                    'subject': subject_name or hostname,
                    'issuer': issuer_name or 'Unknown',
                    'protocol': version or 'Unknown',
                    'cipher': cipher[0] if cipher else 'Unknown',
                    'cipher_suite': f"{cipher[0]}_{cipher[1]}" if cipher and len(cipher) > 1 else 'Unknown',
                    'valid_from': valid_from,
                    'valid_to': valid_to,
                    'serial_number': cert.get('serialNumber', ''),
                    'subject_alt_names': cert.get('subjectAltName', [])
                }
                
    except socket.timeout:
        return None
    except socket.gaierror:
        return None
    except ssl.SSLError as e:
        # Return basic error info
        return {
            'error': str(e),
            'subject': hostname,
            'issuer': 'SSL Error',
            'protocol': 'Unknown',
            'cipher': 'Unknown'
        }
    except Exception as e:
        return None

