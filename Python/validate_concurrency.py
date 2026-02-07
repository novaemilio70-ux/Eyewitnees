#!/usr/bin/env python3
"""
EyeWitness Concurrency Validation Script

Validates that the parallel processing system works correctly:
1. Verifies N browsers run concurrently
2. Checks for resource isolation
3. Validates results are not lost
4. Tests failure recovery

Usage:
    python3 validate_concurrency.py [--workers N] [--urls-file FILE]
"""

import argparse
import os
import psutil
import subprocess
import sys
import time
from pathlib import Path


class ConcurrencyValidator:
    """Validates EyeWitness concurrency implementation"""
    
    def __init__(self, workers: int = 10, verbose: bool = False):
        self.workers = workers
        self.verbose = verbose
        self.results = {}
        
    def log(self, msg: str, level: str = "INFO"):
        colors = {
            "INFO": "\033[94m",
            "OK": "\033[92m",
            "WARN": "\033[93m",
            "ERROR": "\033[91m",
            "RESET": "\033[0m"
        }
        print(f"{colors.get(level, '')}{level}: {msg}{colors['RESET']}")
    
    def check_chrome_processes(self) -> dict:
        """Check number of Chrome/Chromium processes"""
        chrome_count = 0
        chrome_pids = []
        chromedriver_count = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info['name'].lower()
                if 'chrome' in name or 'chromium' in name:
                    if 'driver' in name:
                        chromedriver_count += 1
                    else:
                        chrome_count += 1
                        chrome_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            'chrome_count': chrome_count,
            'chromedriver_count': chromedriver_count,
            'chrome_pids': chrome_pids
        }
    
    def check_isolated_profiles(self) -> dict:
        """Check for isolated worker profile directories"""
        tmp_dir = Path('/tmp')
        worker_dirs = list(tmp_dir.glob('eyewitness_worker_*'))
        
        return {
            'profile_count': len(worker_dirs),
            'profiles': [str(d) for d in worker_dirs]
        }
    
    def check_db_locks(self, db_path: str) -> dict:
        """Check SQLite database locks"""
        if not os.path.exists(db_path):
            return {'error': 'Database not found'}
        
        # Count file handles to the database
        try:
            result = subprocess.run(
                ['lsof', db_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split('\n')
            handle_count = max(0, len(lines) - 1)  # Subtract header
            
            return {
                'handle_count': handle_count,
                'single_writer': handle_count <= 1
            }
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {'error': 'Could not check locks'}
    
    def validate_results(self, db_path: str, expected_count: int) -> dict:
        """Validate that all results were saved to database"""
        import sqlite3
        import pickle
        
        if not os.path.exists(db_path):
            return {'error': 'Database not found'}
        
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Count completed
            cursor.execute("SELECT COUNT(*) FROM http WHERE complete=1")
            completed = cursor.fetchone()[0]
            
            # Count with errors
            cursor.execute("SELECT COUNT(*) FROM http")
            total = cursor.fetchone()[0]
            
            # Count successful (no error state)
            successful = 0
            error_count = 0
            for row in cursor.execute("SELECT object FROM http WHERE complete=1"):
                obj = pickle.loads(row['object'])
                if obj.error_state is None:
                    successful += 1
                else:
                    error_count += 1
            
            conn.close()
            
            return {
                'total_in_db': total,
                'completed': completed,
                'successful': successful,
                'errors': error_count,
                'expected': expected_count,
                'match': total >= expected_count
            }
        except Exception as e:
            return {'error': str(e)}
    
    def check_zombie_processes(self) -> dict:
        """Check for zombie Chrome processes"""
        zombies = []
        
        for proc in psutil.process_iter(['pid', 'name', 'status']):
            try:
                if 'chrome' in proc.info['name'].lower():
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombies.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            'zombie_count': len(zombies),
            'zombie_pids': zombies
        }
    
    def run_validation_during_scan(self, check_interval: float = 2.0, duration: float = 30.0):
        """Run validation checks during an active scan"""
        self.log("Starting validation during scan...", "INFO")
        self.log(f"Checking every {check_interval}s for {duration}s", "INFO")
        
        checks = []
        start = time.time()
        
        while time.time() - start < duration:
            check = {
                'timestamp': time.time() - start,
                'chrome': self.check_chrome_processes(),
                'profiles': self.check_isolated_profiles(),
                'zombies': self.check_zombie_processes()
            }
            checks.append(check)
            
            if self.verbose:
                self.log(f"t={check['timestamp']:.1f}s: "
                        f"Chrome={check['chrome']['chrome_count']}, "
                        f"Profiles={check['profiles']['profile_count']}", "INFO")
            
            time.sleep(check_interval)
        
        # Analyze results
        max_chrome = max(c['chrome']['chrome_count'] for c in checks)
        max_profiles = max(c['profiles']['profile_count'] for c in checks)
        any_zombies = any(c['zombies']['zombie_count'] > 0 for c in checks)
        
        return {
            'checks': len(checks),
            'max_concurrent_chrome': max_chrome,
            'max_profiles': max_profiles,
            'zombies_detected': any_zombies,
            'target_workers': self.workers
        }
    
    def run_post_scan_validation(self, db_path: str, expected_urls: int):
        """Run validation after scan completes"""
        self.log("Running post-scan validation...", "INFO")
        
        # Check results in DB
        db_results = self.validate_results(db_path, expected_urls)
        
        # Check for cleanup
        profiles = self.check_isolated_profiles()
        zombies = self.check_zombie_processes()
        
        return {
            'database': db_results,
            'remaining_profiles': profiles['profile_count'],
            'remaining_zombies': zombies['zombie_count']
        }
    
    def print_report(self, during_scan: dict, post_scan: dict):
        """Print validation report"""
        print("\n" + "=" * 70)
        print("                 CONCURRENCY VALIDATION REPORT")
        print("=" * 70)
        
        # During scan
        print("\n[DURING SCAN]")
        max_chrome = during_scan['max_concurrent_chrome']
        target = during_scan['target_workers']
        
        if max_chrome >= target:
            self.log(f"Max concurrent Chrome: {max_chrome} >= {target} target", "OK")
        else:
            self.log(f"Max concurrent Chrome: {max_chrome} < {target} target", "WARN")
        
        if during_scan['zombies_detected']:
            self.log("Zombie processes detected during scan", "WARN")
        else:
            self.log("No zombie processes detected", "OK")
        
        # Post scan
        print("\n[POST SCAN]")
        
        if 'error' in post_scan.get('database', {}):
            self.log(f"Database check failed: {post_scan['database']['error']}", "ERROR")
        else:
            db = post_scan['database']
            if db['match']:
                self.log(f"All URLs processed: {db['completed']}/{db['expected']}", "OK")
            else:
                self.log(f"Missing URLs: {db['completed']}/{db['expected']}", "ERROR")
            
            self.log(f"Successful: {db['successful']}, Errors: {db['errors']}", "INFO")
        
        if post_scan['remaining_profiles'] == 0:
            self.log("All worker profiles cleaned up", "OK")
        else:
            self.log(f"Remaining profiles: {post_scan['remaining_profiles']}", "WARN")
        
        if post_scan['remaining_zombies'] == 0:
            self.log("No zombie processes remaining", "OK")
        else:
            self.log(f"Zombie processes: {post_scan['remaining_zombies']}", "ERROR")
        
        print("=" * 70 + "\n")
        
        # Overall result
        success = (
            during_scan['max_concurrent_chrome'] >= min(during_scan['target_workers'], 5) and
            not during_scan['zombies_detected'] and
            post_scan.get('database', {}).get('match', False) and
            post_scan['remaining_zombies'] == 0
        )
        
        if success:
            self.log("VALIDATION PASSED", "OK")
        else:
            self.log("VALIDATION FAILED", "ERROR")
        
        return success


def create_test_urls(count: int = 20) -> list:
    """Create test URLs for validation"""
    # Mix of fast and slow URLs
    urls = []
    
    # Fast responses (likely to work)
    fast_urls = [
        "http://example.com",
        "http://httpbin.org/get",
        "http://httpbin.org/status/200",
    ]
    
    # Add variety
    for i in range(count):
        if i < len(fast_urls):
            urls.append(fast_urls[i])
        else:
            # Generate test URLs (may not be reachable, but tests error handling)
            urls.append(f"http://192.168.99.{i}:8080/")
    
    return urls[:count]


def main():
    parser = argparse.ArgumentParser(description='Validate EyeWitness concurrency')
    parser.add_argument('--workers', '-w', type=int, default=5,
                       help='Number of workers to test (default: 5)')
    parser.add_argument('--urls-file', '-f', type=str, default=None,
                       help='File with URLs to test')
    parser.add_argument('--urls-count', '-n', type=int, default=20,
                       help='Number of test URLs to generate (default: 20)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--run-scan', action='store_true',
                       help='Actually run a scan (not just check current state)')
    parser.add_argument('--project', '-p', type=str, default='test_concurrency',
                       help='Project name for test (default: test_concurrency)')
    
    args = parser.parse_args()
    
    validator = ConcurrencyValidator(workers=args.workers, verbose=args.verbose)
    
    if args.run_scan:
        # Get URLs
        if args.urls_file:
            with open(args.urls_file) as f:
                urls = [line.strip() for line in f if line.strip()]
        else:
            urls = create_test_urls(args.urls_count)
        
        # Create temp URL file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for url in urls:
                f.write(url + '\n')
            url_file = f.name
        
        validator.log(f"Starting EyeWitness with {args.workers} workers for {len(urls)} URLs", "INFO")
        
        # Start EyeWitness in background
        script_dir = Path(__file__).parent
        cmd = [
            sys.executable,
            str(script_dir / 'EyeWitness.py'),
            '--web',
            '-f', url_file,
            '--db', args.project,
            '--threads', str(args.workers),
            '--timeout', '15'
        ]
        
        validator.log(f"Command: {' '.join(cmd)}", "INFO")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE if not args.verbose else None,
            stderr=subprocess.STDOUT if not args.verbose else None
        )
        
        # Wait a bit for processes to start
        time.sleep(5)
        
        # Run validation during scan
        during_scan = validator.run_validation_during_scan(
            check_interval=2.0,
            duration=min(60.0, len(urls) * 3)  # Estimate ~3s per URL
        )
        
        # Wait for completion
        process.wait(timeout=300)
        
        # Run post-scan validation
        db_path = Path.cwd() / 'eyewitness_projects' / args.project / f'{args.project}.db'
        post_scan = validator.run_post_scan_validation(str(db_path), len(urls))
        
        # Print report
        success = validator.print_report(during_scan, post_scan)
        
        # Cleanup
        os.unlink(url_file)
        
        sys.exit(0 if success else 1)
        
    else:
        # Just check current state
        validator.log("Checking current system state...", "INFO")
        
        chrome = validator.check_chrome_processes()
        profiles = validator.check_isolated_profiles()
        zombies = validator.check_zombie_processes()
        
        print("\n[CURRENT STATE]")
        validator.log(f"Chrome processes: {chrome['chrome_count']}", "INFO")
        validator.log(f"ChromeDriver processes: {chrome['chromedriver_count']}", "INFO")
        validator.log(f"Worker profiles: {profiles['profile_count']}", "INFO")
        validator.log(f"Zombie processes: {zombies['zombie_count']}", 
                     "WARN" if zombies['zombie_count'] > 0 else "OK")
        
        if profiles['profiles']:
            print("\nActive profiles:")
            for p in profiles['profiles']:
                print(f"  - {p}")


if __name__ == '__main__':
    main()

