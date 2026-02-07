#!/usr/bin/env python3
"""
Integrated Port Scanner for EyeWitness
Pure Python implementation with realistic browser behavior
"""

import socket
import ssl
import random
import threading
import time
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Set, Optional
from urllib.parse import urlparse


# Realistic User-Agents (updated 2024)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Port presets
PORT_PRESETS = {
    'small': [80, 443],
    'medium': [80, 443, 8000, 8080, 8443],
    'large': [80, 81, 443, 591, 2082, 2087, 2095, 2096, 3000, 8000, 8001, 8008, 8080, 8083, 8443, 8834, 8888],
    'xlarge': [
        80, 81, 300, 443, 591, 593, 832, 981, 1010, 1311, 2082, 2087, 2095, 2096, 2480, 3000, 3128, 3333, 4243,
        4567, 4711, 4712, 4993, 5000, 5104, 5108, 5800, 6543, 7000, 7396, 7474, 8000, 8001, 8008, 8014, 8042,
        8050, 8060, 8070, 8069, 8080, 8081, 8088, 8090, 8091, 8118, 8123, 8172, 8222, 8243, 8280, 8281, 8333,
        8443, 8500, 8834, 8880, 8888, 8983, 9000, 9043, 9060, 9080, 9090, 9091, 9200, 9443, 9800, 9981, 12443,
        16080, 18091, 18092, 20720, 28017
    ]
}

# Common HTTP ports
HTTP_PORTS = {80, 8000, 8001, 8008, 8014, 8042, 8050, 8060, 8070, 8069, 8080, 8081, 8088, 8090, 8091, 
              8118, 8123, 8172, 8222, 8280, 8281, 8880, 9000, 9080, 9090, 9091, 16080, 3000, 5000, 
              5800, 7000, 7474, 8983, 9200}

# Common HTTPS ports
HTTPS_PORTS = {443, 8443, 8243, 9443, 12443, 8834, 2082, 2083, 2087, 2096}


def get_random_user_agent() -> str:
    """Get a random realistic user agent"""
    return random.choice(USER_AGENTS)


def expand_targets(target: str) -> List[str]:
    """
    Expand target to list of IPs (handles CIDR, ranges, single IPs, hostnames)
    
    Args:
        target: IP address, hostname, CIDR notation, or IP range
        
    Returns:
        List of IP addresses/hostnames
    """
    targets = []
    target = target.strip()
    
    # Check if it's CIDR notation
    try:
        network = ipaddress.ip_network(target, strict=False)
        # For /32 or single IPs
        if network.num_addresses == 1:
            targets = [str(network.network_address)]
        else:
            targets = [str(ip) for ip in network.hosts()]
        return targets
    except ValueError:
        pass
    
    # Check if it's a range (e.g., 192.168.1.1-10 or 192.168.1.1-192.168.1.10)
    if '-' in target and '.' in target:
        try:
            parts = target.split('-')
            start_ip = parts[0].strip()
            end_part = parts[1].strip()
            
            # Check if end is full IP or just last octet
            if '.' in end_part:
                # Full IP range
                start = ipaddress.ip_address(start_ip)
                end = ipaddress.ip_address(end_part)
                
                current = start
                while current <= end:
                    targets.append(str(current))
                    current += 1
            else:
                # Just last octet (e.g., 192.168.1.1-10)
                base_parts = start_ip.split('.')
                start_num = int(base_parts[-1])
                end_num = int(end_part)
                
                for i in range(start_num, end_num + 1):
                    ip = '.'.join(base_parts[:-1] + [str(i)])
                    targets.append(ip)
            
            return targets
        except (ValueError, IndexError):
            pass
    
    # Single host/IP
    return [target]


class WebPortScanner:
    """Custom port scanner optimized for web service discovery"""
    
    def __init__(self, timeout: float = 2.0, threads: int = 100, user_agent: str = None):
        """
        Initialize port scanner
        
        Args:
            timeout: Connection timeout in seconds
            threads: Number of concurrent threads
            user_agent: Custom user agent (uses random if None)
        """
        self.timeout = timeout
        self.threads = threads
        self.user_agent = user_agent
        self.results = []
        self.lock = threading.Lock()
        self.scanned = 0
        self.total = 0
    
    def _get_user_agent(self) -> str:
        """Get user agent for requests"""
        return self.user_agent or get_random_user_agent()
    
    def _check_port(self, host: str, port: int) -> Tuple[bool, str, dict]:
        """
        Check if a port is open and determine if it's HTTP/HTTPS
        
        Returns:
            Tuple of (is_open, protocol, info_dict)
        """
        info = {
            'host': host,
            'port': port,
            'server': None,
            'title': None,
            'ssl': False
        }
        
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # Resolve hostname if needed
            try:
                ip = socket.gethostbyname(host)
            except socket.gaierror:
                return False, 'unknown', info
            
            # Try connection
            result = sock.connect_ex((ip, port))
            
            if result != 0:
                sock.close()
                return False, 'unknown', info
            
            # Port is open - try to detect protocol
            protocol, info = self._detect_web_service(sock, host, port, info)
            
            return True, protocol, info
            
        except socket.timeout:
            return False, 'unknown', info
        except Exception as e:
            return False, 'unknown', info
    
    def _detect_web_service(self, sock: socket.socket, host: str, port: int, info: dict) -> Tuple[str, dict]:
        """
        Detect if port is running HTTP or HTTPS with realistic browser behavior
        """
        user_agent = self._get_user_agent()
        
        # Default protocol based on port
        if port in HTTPS_PORTS:
            default_protocol = 'https'
        elif port in HTTP_PORTS:
            default_protocol = 'http'
        else:
            default_protocol = 'http'
        
        # Try HTTPS first for HTTPS ports
        if default_protocol == 'https' or port in HTTPS_PORTS:
            try:
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((host, port))
                
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                
                ssl_sock = context.wrap_socket(sock, server_hostname=host)
                info['ssl'] = True
                
                # Send HTTP request over SSL
                request = self._build_http_request(host, port, user_agent)
                ssl_sock.send(request)
                
                response = ssl_sock.recv(4096)
                ssl_sock.close()
                
                if response:
                    info = self._parse_http_response(response, info)
                    if b'HTTP/' in response:
                        return 'https', info
                
                return 'https', info
                
            except ssl.SSLError:
                # Not SSL, try plain HTTP
                pass
            except Exception:
                pass
        
        # Try plain HTTP
        try:
            sock.close()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((host, port))
            
            request = self._build_http_request(host, port, user_agent)
            sock.send(request)
            
            response = sock.recv(4096)
            sock.close()
            
            if response:
                info = self._parse_http_response(response, info)
                
                # Check if response suggests HTTPS redirect
                response_lower = response.lower()
                if b'https://' in response_lower or b'strict-transport-security' in response_lower:
                    # Server is redirecting to HTTPS, but this port is HTTP
                    pass
                
                if b'HTTP/' in response:
                    return 'http', info
            
            return default_protocol, info
            
        except Exception:
            return default_protocol, info
    
    def _build_http_request(self, host: str, port: int, user_agent: str) -> bytes:
        """Build a realistic HTTP request like a real browser"""
        
        # Build headers like a real browser
        headers = [
            f"GET / HTTP/1.1",
            f"Host: {host}:{port}" if port not in [80, 443] else f"Host: {host}",
            f"User-Agent: {user_agent}",
            "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language: en-US,en;q=0.9",
            "Accept-Encoding: gzip, deflate",
            "Connection: close",
            "Upgrade-Insecure-Requests: 1",
            "Cache-Control: max-age=0",
            "Sec-Fetch-Dest: document",
            "Sec-Fetch-Mode: navigate",
            "Sec-Fetch-Site: none",
            "Sec-Fetch-User: ?1",
        ]
        
        request = "\r\n".join(headers) + "\r\n\r\n"
        return request.encode('utf-8')
    
    def _parse_http_response(self, response: bytes, info: dict) -> dict:
        """Parse HTTP response to extract useful information"""
        try:
            response_str = response.decode('utf-8', errors='ignore')
            lines = response_str.split('\r\n')
            
            # Parse headers
            for line in lines:
                line_lower = line.lower()
                if line_lower.startswith('server:'):
                    info['server'] = line.split(':', 1)[1].strip()
                elif line_lower.startswith('x-powered-by:'):
                    if not info['server']:
                        info['server'] = line.split(':', 1)[1].strip()
            
            # Try to extract title
            import re
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', response_str, re.IGNORECASE)
            if title_match:
                info['title'] = title_match.group(1).strip()[:100]  # Limit length
                
        except Exception:
            pass
        
        return info
    
    def scan_target(self, host: str, ports: List[int], show_progress: bool = True) -> List[Tuple[str, int, str, dict]]:
        """
        Scan a single host for open web ports
        
        Returns:
            List of tuples: (host, port, protocol, info)
        """
        open_ports = []
        
        with ThreadPoolExecutor(max_workers=min(self.threads, len(ports))) as executor:
            futures = {executor.submit(self._check_port, host, port): port for port in ports}
            
            for future in as_completed(futures):
                port = futures[future]
                try:
                    is_open, protocol, info = future.result()
                    
                    with self.lock:
                        self.scanned += 1
                    
                    if is_open and protocol in ['http', 'https']:
                        open_ports.append((host, port, protocol, info))
                        
                        # Format output
                        server_info = f" [{info['server']}]" if info.get('server') else ""
                        title_info = f" - {info['title'][:50]}" if info.get('title') else ""
                        ssl_info = " (SSL)" if info.get('ssl') else ""
                        
                        print(f"[+] {protocol.upper()}://{host}:{port}{ssl_info}{server_info}{title_info}")
                        
                except Exception as e:
                    pass
        
        return open_ports
    
    def scan_targets(self, targets: List[str], ports: List[int]) -> List[str]:
        """
        Scan multiple targets and return list of URLs
        
        Returns:
            List of URLs (strings)
        """
        all_urls = []
        
        self.total = len(targets) * len(ports)
        self.scanned = 0
        
        print(f"\n[*] Starting web service discovery...")
        print(f"[*] Targets: {len(targets)} host(s)")
        print(f"[*] Ports: {len(ports)}")
        print(f"[*] Total checks: {self.total}")
        print(f"[*] Threads: {self.threads}")
        print(f"[*] Timeout: {self.timeout}s\n")
        
        start_time = time.time()
        
        for i, target in enumerate(targets, 1):
            print(f"[*] Scanning [{i}/{len(targets)}] {target}...")
            results = self.scan_target(target, ports)
            
            for host, port, protocol, info in results:
                if port == 80 and protocol == 'http':
                    url = f"http://{host}"
                elif port == 443 and protocol == 'https':
                    url = f"https://{host}"
                else:
                    url = f"{protocol}://{host}:{port}"
                
                if url not in all_urls:
                    all_urls.append(url)
        
        elapsed = time.time() - start_time
        print(f"\n[*] Scan completed in {elapsed:.2f} seconds")
        print(f"[+] Found {len(all_urls)} web service(s)")
        
        return all_urls


def discover_web_services(targets: List[str], 
                          ports: List[int] = None, 
                          preset: str = 'medium',
                          timeout: float = 2.0,
                          threads: int = 100,
                          user_agent: str = None) -> List[str]:
    """
    Main function to discover web services on targets
    
    Args:
        targets: List of target IPs/hostnames/CIDRs
        ports: List of ports to scan (overrides preset)
        preset: Port preset to use if ports not specified
        timeout: Connection timeout
        threads: Number of concurrent threads
        user_agent: Custom user agent
        
    Returns:
        List of discovered URLs
    """
    # Expand targets
    all_targets = []
    for target in targets:
        expanded = expand_targets(target)
        all_targets.extend(expanded)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_targets = []
    for t in all_targets:
        if t not in seen:
            seen.add(t)
            unique_targets.append(t)
    
    # Get ports
    if ports is None:
        ports = PORT_PRESETS.get(preset, PORT_PRESETS['medium'])
    
    # Create scanner and run
    scanner = WebPortScanner(timeout=timeout, threads=threads, user_agent=user_agent)
    urls = scanner.scan_targets(unique_targets, ports)
    
    return urls

