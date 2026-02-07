#!/usr/bin/env python3
"""
EyeWitness Concurrency Module
Robust parallel processing with isolated workers, DB writer process, and metrics.

Architecture:
- WorkerPoolManager: Orchestrates the entire parallel processing
- IsolatedWorker: Individual worker with isolated Chromium profile
- DBWriterProcess: Single-writer pattern for SQLite safety
- MetricsCollector: Real-time observability

Author: EyeWitness Team
"""

import logging
import multiprocessing
import os
import pickle
import queue
import shutil
import signal
import sqlite3
import sys
import tempfile
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


@dataclass
class JobResult:
    """Result of processing a single URL"""
    url: str
    success: bool
    http_object: Any  # HTTPTableObject
    error: Optional[str] = None
    worker_id: int = 0
    processing_time_ms: float = 0
    retry_count: int = 0
    stages_completed: List[str] = field(default_factory=list)


@dataclass
class WorkerMetrics:
    """Metrics collected from a worker"""
    worker_id: int
    urls_processed: int = 0
    urls_failed: int = 0
    urls_success: int = 0
    total_time_ms: float = 0
    avg_time_per_url_ms: float = 0
    memory_usage_mb: float = 0
    browser_restarts: int = 0
    ai_calls: int = 0
    ai_failures: int = 0
    cred_tests: int = 0
    cred_successes: int = 0
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    failed_urls: List[Tuple[str, str]] = field(default_factory=list)  # List of (url, error_reason)
    
    def to_dict(self) -> dict:
        return {
            'worker_id': self.worker_id,
            'urls_processed': self.urls_processed,
            'urls_failed': self.urls_failed,
            'urls_success': self.urls_success,
            'total_time_ms': self.total_time_ms,
            'avg_time_per_url_ms': self.avg_time_per_url_ms,
            'memory_usage_mb': self.memory_usage_mb,
            'browser_restarts': self.browser_restarts,
            'ai_calls': self.ai_calls,
            'cred_tests': self.cred_tests,
            'cred_successes': self.cred_successes,
            'errors_by_type': dict(self.errors_by_type),
            'failed_urls': self.failed_urls
        }


class WorkerLogger:
    """Thread-safe logger for workers with file and console output"""
    
    def __init__(self, worker_id: int, log_dir: str, verbose: bool = False):
        self.worker_id = worker_id
        self.verbose = verbose
        self.log_file = Path(log_dir) / f'worker_{worker_id:02d}.log'
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _format(self, level: str, message: str) -> str:
        timestamp = datetime.now().strftime('%H:%M:%S')
        return f'[{timestamp}] [W-{self.worker_id:02d}] [{level}] {message}'
    
    def _write(self, formatted: str):
        try:
            with open(self.log_file, 'a') as f:
                f.write(formatted + '\n')
        except:
            pass
        if self.verbose:
            print(formatted)
    
    def info(self, msg: str):
        self._write(self._format('INFO', msg))
    
    def warn(self, msg: str):
        self._write(self._format('WARN', msg))
        print(self._format('WARN', msg))  # Always show warnings
    
    def error(self, msg: str):
        self._write(self._format('ERROR', msg))
        print(self._format('ERROR', msg))  # Always show errors
    
    def ok(self, msg: str):
        formatted = self._format('OK', msg)
        self._write(formatted)
        print(f'\033[92m{formatted}\033[0m')  # Green
    
    def ai(self, msg: str):
        formatted = self._format('AI', msg)
        self._write(formatted)
        if self.verbose:
            print(f'\033[96m{formatted}\033[0m')  # Cyan


class IsolatedWorker:
    """
    Worker process that processes URLs with an isolated Chromium browser.
    
    Features:
    - Isolated Chromium profile in unique temp directory
    - Automatic browser restart on crash
    - Per-URL timeout and retry logic
    - Metrics collection
    """
    
    RETRY_CONFIG = {
        'timeout': {'max_retries': 2, 'backoff': [5, 10]},
        'connection_refused': {'max_retries': 1, 'backoff': [3]},
        'driver_crashed': {'max_retries': 1, 'backoff': [2]},
        'ssl_error': {'max_retries': 1, 'backoff': [2]},
    }
    
    def __init__(
        self,
        worker_id: int,
        cli_parsed: Any,
        url_queue: multiprocessing.Queue,
        result_queue: multiprocessing.Queue,
        metrics_queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        log_dir: str,
        verbose: bool = False
    ):
        self.worker_id = worker_id
        self.cli_parsed = cli_parsed
        self.url_queue = url_queue
        self.result_queue = result_queue
        self.metrics_queue = metrics_queue
        self.shutdown_event = shutdown_event
        self.log_dir = log_dir
        self.verbose = verbose
        
        # Worker-specific paths
        self.profile_dir = Path(tempfile.gettempdir()) / f'eyewitness_worker_{worker_id}'
        self.driver = None
        self.ai_analyzer = None
        self.credential_tester = None
        self.logger = None
        
        # Metrics
        self.metrics = WorkerMetrics(worker_id=worker_id)
    
    def run(self):
        """Main worker loop - runs in a separate process"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # Let parent handle Ctrl+C
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
        self.logger = WorkerLogger(self.worker_id, self.log_dir, self.verbose)
        self.logger.info(f'Worker {self.worker_id} starting...')
        
        try:
            self._setup()
            self._process_loop()
        except Exception as e:
            self.logger.error(f'Fatal error: {e}')
            traceback.print_exc()
        finally:
            self._cleanup()
            self._report_metrics()
    
    def _handle_shutdown(self, signum, frame):
        self.logger.info('Received shutdown signal')
        self.shutdown_event.set()
    
    def _setup(self):
        """Initialize browser and analyzers"""
        self.logger.info(f'Setting up isolated environment in {self.profile_dir}')
        
        # Create isolated profile directory
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        # Create browser with isolated profile
        self._create_isolated_browser()
        
        # Initialize AI analyzer if enabled
        if self.cli_parsed.enable_ai or self.cli_parsed.test_credentials:
            self._setup_ai_analyzer()
        
        self.logger.ok(f'Worker {self.worker_id} ready')
    
    def _create_isolated_browser(self):
        """Create Chromium browser with worker-specific profile using selenium_module"""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.chrome.service import Service as ChromeService
        from modules.selenium_module import find_chromedriver
        
        try:
            options = ChromeOptions()
            
            # Essential headless configuration (matching selenium_module)
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-web-security')
            options.add_argument('--allow-running-insecure-content')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            options.add_argument('--ignore-certificate-errors-spki-list')
            options.add_argument('--disable-features=VizDisplayCompositor')
            
            # CRITICAL: Isolated user data directory per worker
            options.add_argument(f'--user-data-dir={self.profile_dir}')
            
            # Memory and performance optimization (matching selenium_module)
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=4096')
            options.add_argument('--no-zygote')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            
            # Window size
            width = getattr(self.cli_parsed, 'width', 1920)
            height = getattr(self.cli_parsed, 'height', 1080)
            options.add_argument(f'--window-size={width},{height}')
            
            # User agent
            if hasattr(self.cli_parsed, 'user_agent') and self.cli_parsed.user_agent:
                options.add_argument(f'--user-agent={self.cli_parsed.user_agent}')
            
            # Disable automation detection
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Enable logging
            options.set_capability('goog:loggingPrefs', {
                'performance': 'ALL',
                'browser': 'ALL'
            })
            
            options.accept_insecure_certs = True
            
            # Setup Chrome service with proper chromedriver
            service_kwargs = {}
            chromedriver_path = find_chromedriver()
            if chromedriver_path:
                service_kwargs['executable_path'] = chromedriver_path
            
            # Configure temp directory
            temp_dir = tempfile.gettempdir()
            os.environ['TMPDIR'] = temp_dir
            os.environ['TMP'] = temp_dir
            os.environ['TEMP'] = temp_dir
            
            service = ChromeService(**service_kwargs)
            
            # Create driver
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(self.cli_parsed.timeout)
            self.driver.set_window_size(width, height)
            
            # Remove automation indicators
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            self.logger.info(f'Chrome browser created with profile: {self.profile_dir}')
            
        except Exception as e:
            self.logger.error(f'Failed to create browser: {e}')
            raise
    
    def _setup_ai_analyzer(self):
        """Initialize AI analyzer for this worker"""
        try:
            from modules.ai_credential_analyzer import AICredentialAnalyzer
            
            self.ai_analyzer = AICredentialAnalyzer(
                ai_api_key=self.cli_parsed.ai_api_key,
                ai_provider=self.cli_parsed.ai_provider,
                test_credentials=self.cli_parsed.test_credentials,
                credential_test_timeout=self.cli_parsed.credential_test_timeout,
                credential_test_delay=self.cli_parsed.credential_test_delay,
                debug_creds=self.cli_parsed.debug_creds,
                output_dir=self.cli_parsed.d,
                selenium_driver=self.driver  # Reuse worker's browser
            )
            
            self.logger.info('AI analyzer initialized')
            
        except Exception as e:
            self.logger.warn(f'AI analyzer initialization failed: {e}')
            self.ai_analyzer = None
    
    def _process_loop(self):
        """Main processing loop - get URLs from queue and process them"""
        while not self.shutdown_event.is_set():
            try:
                # Get URL from queue with timeout
                try:
                    url = self.url_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                if url is None:  # Poison pill
                    self.logger.info('Received shutdown signal (poison pill)')
                    break
                
                # Process the URL
                result = self._process_url_with_retry(url)
                
                # Send result to DB writer
                self.result_queue.put(result)
                
                # Update metrics
                self._update_metrics(result)
                
            except Exception as e:
                self.logger.error(f'Error in process loop: {e}')
                traceback.print_exc()
    
    def _process_url_with_retry(self, url: str) -> JobResult:
        """Process a single URL with retry logic"""
        start_time = time.time()
        retry_count = 0
        last_error = None
        
        while True:
            try:
                http_object = self._process_single_url(url)
                
                processing_time = (time.time() - start_time) * 1000
                
                # Capture error message from http_object if processing had issues
                error_msg = http_object.error_state if http_object.error_state else None
                
                return JobResult(
                    url=url,
                    success=http_object.error_state is None,
                    http_object=http_object,
                    error=error_msg,
                    worker_id=self.worker_id,
                    processing_time_ms=processing_time,
                    retry_count=retry_count,
                    stages_completed=['browse', 'capture', 'analyze', 'persist']
                )
                
            except Exception as e:
                last_error = str(e)
                error_type = self._classify_error(e)
                
                config = self.RETRY_CONFIG.get(error_type, {'max_retries': 0, 'backoff': []})
                
                if retry_count < config.get('max_retries', 0):
                    backoff = config['backoff'][min(retry_count, len(config['backoff']) - 1)]
                    self.logger.warn(f'Error ({error_type}): {last_error[:100]}, retrying in {backoff}s...')
                    time.sleep(backoff)
                    retry_count += 1
                    
                    # Restart browser if needed
                    if error_type == 'driver_crashed':
                        self._restart_browser()
                else:
                    break
        
        # All retries exhausted
        processing_time = (time.time() - start_time) * 1000
        
        # Create error result
        from modules.objects import HTTPTableObject
        http_object = HTTPTableObject()
        http_object.remote_system = url
        http_object.error_state = last_error[:200] if last_error else 'Unknown error'
        http_object.set_paths(self.cli_parsed.d, None)
        
        return JobResult(
            url=url,
            success=False,
            http_object=http_object,
            error=last_error,
            worker_id=self.worker_id,
            processing_time_ms=processing_time,
            retry_count=retry_count
        )
    
    def _process_single_url(self, url: str) -> Any:
        """Process a single URL - the core logic"""
        from modules.objects import HTTPTableObject
        from modules.selenium_module import capture_host
        from modules.helpers import default_creds_category, resolve_host, do_jitter
        
        self.logger.info(f'Processing: {url}')
        
        # Create HTTP object
        http_object = HTTPTableObject()
        http_object.remote_system = url
        http_object.set_paths(self.cli_parsed.d, None)
        
        # Resolve hostname
        if self.cli_parsed.resolve:
            http_object.resolved = resolve_host(url)
        
        # Capture host (screenshot + headers + tech detection)
        http_object, self.driver = capture_host(
            self.cli_parsed, http_object, self.driver
        )
        
        # Signature matching
        if http_object.category is None and http_object.error_state is None:
            http_object = default_creds_category(http_object)
        
        # AI analysis if enabled
        if self.ai_analyzer and http_object.error_state is None:
            if self.cli_parsed.enable_ai or (
                self.cli_parsed.test_credentials and http_object.default_creds
            ):
                self.logger.ai(f'Running AI analysis...')
                self.metrics.ai_calls += 1
                try:
                    http_object = self.ai_analyzer.analyze_http_object(http_object)
                except Exception as e:
                    self.logger.warn(f'AI analysis failed: {e}')
                    self.metrics.ai_failures += 1
        
        # Apply jitter if configured
        do_jitter(self.cli_parsed)
        
        self.logger.ok(f'Completed: {url}')
        return http_object
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for retry logic"""
        error_str = str(error).lower()
        
        if 'timeout' in error_str or 'timed out' in error_str:
            return 'timeout'
        if 'connection refused' in error_str:
            return 'connection_refused'
        if 'chrome not reachable' in error_str or 'session deleted' in error_str:
            return 'driver_crashed'
        if 'ssl' in error_str or 'certificate' in error_str:
            return 'ssl_error'
        
        return 'unknown'
    
    def _restart_browser(self):
        """Restart the browser after a crash"""
        self.logger.warn('Restarting browser...')
        self.metrics.browser_restarts += 1
        
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass
        
        # Clean profile and recreate
        if self.profile_dir.exists():
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        self._create_isolated_browser()
        self.logger.info('Browser restarted successfully')
    
    def _update_metrics(self, result: JobResult):
        """Update worker metrics"""
        self.metrics.urls_processed += 1
        self.metrics.total_time_ms += result.processing_time_ms
        
        if result.success:
            self.metrics.urls_success += 1
        else:
            self.metrics.urls_failed += 1
            error_type = self._classify_error(Exception(result.error or ''))
            self.metrics.errors_by_type[error_type] = \
                self.metrics.errors_by_type.get(error_type, 0) + 1
            # Track failed URL with error reason
            error_reason = result.error[:100] if result.error else error_type
            self.metrics.failed_urls.append((result.url, error_reason))
        
        if self.metrics.urls_processed > 0:
            self.metrics.avg_time_per_url_ms = \
                self.metrics.total_time_ms / self.metrics.urls_processed
        
        # Get memory usage
        try:
            import psutil
            process = psutil.Process(os.getpid())
            self.metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
        except:
            pass
    
    def _report_metrics(self):
        """Send final metrics to collector"""
        try:
            self.metrics_queue.put(self.metrics)
        except:
            pass
    
    def _cleanup(self):
        """Cleanup resources"""
        self.logger.info('Cleaning up...')
        
        # Quit browser
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
        # Cleanup AI analyzer
        if self.ai_analyzer:
            try:
                if hasattr(self.ai_analyzer, 'selenium_tester'):
                    self.ai_analyzer.selenium_tester.cleanup()
            except:
                pass
        
        # Remove profile directory
        if self.profile_dir.exists():
            try:
                shutil.rmtree(self.profile_dir, ignore_errors=True)
            except:
                pass
        
        self.logger.info(f'Worker {self.worker_id} finished')


class DBWriterProcess:
    """
    Dedicated process for SQLite writes using single-writer pattern.
    
    Features:
    - Serializes all database writes
    - Batch inserts for efficiency
    - WAL mode for better read concurrency
    - Automatic flush on buffer full or timeout
    """
    
    def __init__(
        self,
        db_path: str,
        result_queue: multiprocessing.Queue,
        shutdown_event: multiprocessing.Event,
        batch_size: int = 10,
        flush_interval: float = 5.0
    ):
        self.db_path = db_path
        self.result_queue = result_queue
        self.shutdown_event = shutdown_event
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.buffer = []
        self.connection = None
        self.last_flush = time.time()
        self.total_written = 0
    
    def run(self):
        """Main loop - runs in a separate process"""
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        
        print(f'[DBWriter] Starting with batch_size={self.batch_size}')
        
        try:
            self._setup_connection()
            self._process_loop()
        except Exception as e:
            print(f'[DBWriter] Fatal error: {e}')
            traceback.print_exc()
        finally:
            self._final_flush()
            self._close_connection()
        
        print(f'[DBWriter] Finished. Total records written: {self.total_written}')
    
    def _setup_connection(self):
        """Setup SQLite connection with optimizations"""
        self.connection = sqlite3.connect(self.db_path)
        
        # Enable WAL mode for better concurrency
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA cache_size=10000")
        self.connection.execute("PRAGMA temp_store=MEMORY")
        
        self.connection.row_factory = sqlite3.Row
    
    def _process_loop(self):
        """Process results from queue"""
        while not self.shutdown_event.is_set():
            try:
                # Get result with timeout
                try:
                    result = self.result_queue.get(timeout=1)
                except queue.Empty:
                    # Check if we should flush based on time
                    if self.buffer and (time.time() - self.last_flush) > self.flush_interval:
                        self._flush_buffer()
                    continue
                
                if result is None:  # Poison pill
                    break
                
                # Add to buffer
                self.buffer.append(result)
                
                # Flush if buffer is full
                if len(self.buffer) >= self.batch_size:
                    self._flush_buffer()
                    
            except Exception as e:
                print(f'[DBWriter] Error processing result: {e}')
    
    def _flush_buffer(self):
        """Flush buffered results to database"""
        if not self.buffer:
            return
        
        cursor = self.connection.cursor()
        
        for result in self.buffer:
            try:
                http_object = result.http_object
                url = result.url
                
                # First, find the existing record by URL to get its ID
                cursor.execute("SELECT id, object FROM http WHERE complete=0")
                target_id = None
                for row in cursor.fetchall():
                    try:
                        existing_obj = pickle.loads(row[1])
                        if existing_obj.remote_system == url:
                            target_id = row[0]
                            # Copy the ID to the new object
                            http_object._id = target_id
                            break
                    except Exception:
                        continue
                
                if target_id is None:
                    print(f'[DBWriter] WARNING: No pending record found for URL {url}')
                    continue
                
                # Serialize object with the correct ID
                pobj = sqlite3.Binary(pickle.dumps(http_object, protocol=2))
                
                # Update in database by ID
                cursor.execute(
                    "UPDATE http SET object=?, complete=? WHERE id=?",
                    (pobj, 1, target_id)
                )
                
                # Check if the update actually affected any rows
                if cursor.rowcount == 0:
                    print(f'[DBWriter] WARNING: No rows updated for ID {target_id} ({url})')
                else:
                    self.total_written += 1
                
            except Exception as e:
                print(f'[DBWriter] Error writing result for {result.url}: {e}')
        
        self.connection.commit()
        cursor.close()
        
        print(f'[DBWriter] Flushed {len(self.buffer)} records (total: {self.total_written})')
        
        self.buffer = []
        self.last_flush = time.time()
    
    def _final_flush(self):
        """Final flush before shutdown"""
        if self.buffer:
            print(f'[DBWriter] Final flush of {len(self.buffer)} records...')
            self._flush_buffer()
    
    def _close_connection(self):
        """Close database connection"""
        if self.connection:
            try:
                # Checkpoint WAL to ensure all data is written to the main database file
                # This is critical when copying/transferring the database to another system
                self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.connection.close()
            except:
                pass


class MetricsCollector:
    """Collects and displays metrics from all workers"""
    
    def __init__(self, total_urls: int, num_workers: int, output_dir: str = None):
        self.total_urls = total_urls
        self.num_workers = num_workers
        self.worker_metrics = {}
        self.start_time = time.time()
        self.output_dir = output_dir
    
    def add_worker_metrics(self, metrics: WorkerMetrics):
        """Add metrics from a worker"""
        self.worker_metrics[metrics.worker_id] = metrics
    
    def get_failed_urls(self) -> List[Tuple[str, str]]:
        """Get all failed URLs from all workers"""
        failed_urls = []
        for m in self.worker_metrics.values():
            failed_urls.extend(m.failed_urls)
        return failed_urls
    
    def save_failed_urls(self, output_path: str = None) -> Optional[str]:
        """
        Save failed URLs to a file for retry.
        
        Args:
            output_path: Path to save file. If None, uses output_dir/failed_urls.txt
            
        Returns:
            Path to the saved file, or None if no failed URLs
        """
        failed_urls = self.get_failed_urls()
        
        if not failed_urls:
            return None
        
        # Determine output path
        if output_path is None:
            if self.output_dir:
                output_path = os.path.join(self.output_dir, 'failed_urls.txt')
            else:
                output_path = 'failed_urls.txt'
        
        # Write URLs only (one per line) for easy re-run
        with open(output_path, 'w') as f:
            for url, _ in failed_urls:
                f.write(f"{url}\n")
        
        # Also write a detailed version with error reasons
        detailed_path = output_path.replace('.txt', '_detailed.txt')
        with open(detailed_path, 'w') as f:
            f.write("# Failed URLs with error reasons\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total failed: {len(failed_urls)}\n\n")
            for url, reason in failed_urls:
                f.write(f"{url}\n")
                f.write(f"  # Error: {reason}\n\n")
        
        return output_path
    
    def get_summary(self) -> dict:
        """Get aggregated summary"""
        total_processed = sum(m.urls_processed for m in self.worker_metrics.values())
        total_success = sum(m.urls_success for m in self.worker_metrics.values())
        total_failed = sum(m.urls_failed for m in self.worker_metrics.values())
        total_time = time.time() - self.start_time
        
        # Aggregate errors
        all_errors = {}
        for m in self.worker_metrics.values():
            for error_type, count in m.errors_by_type.items():
                all_errors[error_type] = all_errors.get(error_type, 0) + count
        
        return {
            'total_urls': self.total_urls,
            'processed': total_processed,
            'success': total_success,
            'failed': total_failed,
            'success_rate': (total_success / total_processed * 100) if total_processed > 0 else 0,
            'total_time_sec': total_time,
            'urls_per_second': total_processed / total_time if total_time > 0 else 0,
            'errors_by_type': all_errors,
            'workers_used': len(self.worker_metrics),
            'avg_time_per_url_ms': sum(m.avg_time_per_url_ms for m in self.worker_metrics.values()) / len(self.worker_metrics) if self.worker_metrics else 0
        }
    
    def print_summary(self):
        """Print formatted summary"""
        summary = self.get_summary()
        
        print('\n' + '=' * 70)
        print('                    PROCESSING SUMMARY')
        print('=' * 70)
        print(f"Total URLs:          {summary['total_urls']}")
        print(f"Processed:           {summary['processed']}")
        print(f"Successful:          {summary['success']} ({summary['success_rate']:.1f}%)")
        print(f"Failed:              {summary['failed']}")
        print(f"Total Time:          {summary['total_time_sec']:.1f} seconds")
        print(f"Throughput:          {summary['urls_per_second']:.2f} URLs/second")
        print(f"Workers Used:        {summary['workers_used']}")
        print(f"Avg Time/URL:        {summary['avg_time_per_url_ms']:.0f} ms")
        
        if summary['errors_by_type']:
            print('\nErrors by Type:')
            for error_type, count in sorted(summary['errors_by_type'].items(), key=lambda x: -x[1]):
                print(f"  - {error_type}: {count}")
        
        # Save failed URLs and show info
        failed_urls_path = self.save_failed_urls()
        if failed_urls_path:
            failed_count = len(self.get_failed_urls())
            print(f'\n[*] {failed_count} failed URL(s) saved to:')
            print(f'    {failed_urls_path}')
            print(f'    {failed_urls_path.replace(".txt", "_detailed.txt")}')
            print(f'\n[+] To retry failed URLs:')
            print(f'    python3 Python/EyeWitness.py --web -f {failed_urls_path} --db <project_name> [options]')
        
        print('=' * 70 + '\n')


class WorkerPoolManager:
    """
    Manages the worker pool for parallel URL processing.
    
    Features:
    - Strict limit on concurrent workers
    - Graceful shutdown handling
    - Health monitoring
    - Automatic worker restart on failure
    """
    
    def __init__(
        self,
        cli_parsed: Any,
        max_workers: int = 10,
        verbose: bool = False
    ):
        self.cli_parsed = cli_parsed
        self.max_workers = max_workers
        self.verbose = verbose
        
        # Queues
        self.url_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.metrics_queue = multiprocessing.Queue()
        
        # Control
        self.shutdown_event = multiprocessing.Event()
        
        # Processes
        self.workers = []
        self.db_writer = None
        
        # State
        self.total_urls = 0
        self.log_dir = Path(cli_parsed.d) / 'logs'
    
    def start(self, urls: List[str]):
        """Start the worker pool and begin processing with staggered browser startup"""
        self.total_urls = len(urls)
        
        if self.total_urls == 0:
            print('[!] No URLs to process')
            return
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine actual number of workers
        num_workers = min(self.max_workers, self.total_urls)
        
        print(f'[*] Starting {num_workers} workers for {self.total_urls} URLs')
        print(f'[*] Logs directory: {self.log_dir}')
        
        # Enqueue all URLs FIRST (before starting workers)
        for url in urls:
            self.url_queue.put(url)
        
        # Add poison pills for each worker
        for _ in range(num_workers):
            self.url_queue.put(None)
        
        # Start DB writer process
        self.db_writer = multiprocessing.Process(
            target=self._run_db_writer,
            name='DBWriter'
        )
        self.db_writer.start()
        
        # Start worker processes with STAGGERED startup to avoid resource contention
        # This is critical for avoiding Chrome crashes when starting many browsers
        # Dynamic stagger delay: more workers = more delay needed to prevent resource contention
        if num_workers <= 3:
            stagger_delay = 0.5  # Fast startup for few workers
        elif num_workers <= 5:
            stagger_delay = 1.0  # Standard delay
        else:
            stagger_delay = 1.5  # More delay for many workers to prevent timeouts
        print(f'[*] Starting workers with {stagger_delay}s stagger delay...')
        
        for i in range(num_workers):
            worker = multiprocessing.Process(
                target=self._run_worker,
                args=(i,),
                name=f'Worker-{i}'
            )
            worker.start()
            self.workers.append(worker)
            print(f'    Worker-{i} started')
            
            # Stagger worker starts to avoid overwhelming system
            if i < num_workers - 1:  # Don't delay after last worker
                time.sleep(stagger_delay)
    
    def _run_worker(self, worker_id: int):
        """Run a worker - called in subprocess"""
        worker = IsolatedWorker(
            worker_id=worker_id,
            cli_parsed=self.cli_parsed,
            url_queue=self.url_queue,
            result_queue=self.result_queue,
            metrics_queue=self.metrics_queue,
            shutdown_event=self.shutdown_event,
            log_dir=str(self.log_dir),
            verbose=self.verbose
        )
        worker.run()
    
    def _run_db_writer(self):
        """Run the DB writer - called in subprocess"""
        writer = DBWriterProcess(
            db_path=self.cli_parsed.db_path,
            result_queue=self.result_queue,
            shutdown_event=self.shutdown_event,
            batch_size=10,
            flush_interval=5.0
        )
        writer.run()
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all workers to complete"""
        start_time = time.time()
        
        # Wait for all workers
        for worker in self.workers:
            remaining = None
            if timeout:
                remaining = timeout - (time.time() - start_time)
                if remaining <= 0:
                    return False
            worker.join(timeout=remaining)
        
        # Signal DB writer to finish and wait
        self.result_queue.put(None)  # Poison pill for DB writer
        
        if self.db_writer:
            remaining = None
            if timeout:
                remaining = timeout - (time.time() - start_time)
            self.db_writer.join(timeout=remaining or 30)
        
        # Collect metrics
        output_dir = getattr(self.cli_parsed, 'd', None)
        metrics_collector = MetricsCollector(self.total_urls, len(self.workers), output_dir=output_dir)
        
        try:
            while True:
                try:
                    metrics = self.metrics_queue.get_nowait()
                    metrics_collector.add_worker_metrics(metrics)
                except queue.Empty:
                    break
        except:
            pass
        
        metrics_collector.print_summary()
        
        return True
    
    def shutdown(self, graceful: bool = True):
        """Shutdown the worker pool"""
        print('[*] Shutting down worker pool...')
        
        # Signal all workers to stop
        self.shutdown_event.set()
        
        # Wait for graceful shutdown
        if graceful:
            for worker in self.workers:
                worker.join(timeout=10)
        
        # Force terminate if needed
        for worker in self.workers:
            if worker.is_alive():
                print(f'[!] Force terminating {worker.name}')
                worker.terminate()
        
        # Stop DB writer
        if self.db_writer and self.db_writer.is_alive():
            self.result_queue.put(None)
            self.db_writer.join(timeout=5)
            if self.db_writer.is_alive():
                self.db_writer.terminate()
        
        # Cleanup queues
        try:
            while not self.url_queue.empty():
                self.url_queue.get_nowait()
        except:
            pass
        
        print('[*] Worker pool shutdown complete')


def run_parallel_scan(cli_parsed: Any, urls: List[str], num_workers: int = 10) -> List[Any]:
    """
    Run a parallel scan using the worker pool.
    
    This is the main entry point for parallel processing.
    
    Args:
        cli_parsed: CLI arguments
        urls: List of URLs to process
        num_workers: Number of parallel workers (default: 10)
        
    Returns:
        List of HTTPTableObject results
    """
    # Initialize database with URLs first
    from modules.db_manager import DB_Manager
    
    dbm = DB_Manager(cli_parsed.db_path)
    dbm.open_connection()
    dbm.initialize_db()
    dbm.save_options(cli_parsed)
    
    # Create HTTP objects in database
    for url in urls:
        dbm.create_http_object(url, cli_parsed)
    
    dbm.close()
    
    # Create and run worker pool
    pool = WorkerPoolManager(
        cli_parsed=cli_parsed,
        max_workers=num_workers,
        verbose=getattr(cli_parsed, 'verbose', False)
    )
    
    try:
        pool.start(urls)
        pool.wait_for_completion()
    except KeyboardInterrupt:
        print('\n[!] Interrupted - shutting down...')
        pool.shutdown(graceful=True)
    finally:
        pool.shutdown(graceful=False)
    
    # Read final results from database
    dbm = DB_Manager(cli_parsed.db_path)
    dbm.open_connection()
    results = dbm.get_complete_http()
    dbm.close()
    
    return results

