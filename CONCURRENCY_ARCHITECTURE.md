# EyeWitness - Arquitectura de Concurrencia para 10+ Workers Simultáneos

## 1. ANÁLISIS DEL CÓDIGO EXISTENTE

### 1.1 Puntos Actualmente Secuenciales

| Ubicación | Problema | Impacto |
|-----------|----------|---------|
| `EyeWitness.py:566-648` | `multi_mode()` usa `multiprocessing.Process` pero con una sola Queue compartida | Cuello de botella en distribución de tareas |
| `selenium_module.py:52-157` | `create_driver()` crea un nuevo driver por cada worker SIN perfil aislado | Colisión de perfiles/cache Chromium |
| `db_manager.py:40-43` | SQLite con `check_same_thread=False` pero sin lock explícito | Race conditions en escrituras |
| `ai_credential_analyzer.py:70-143` | Inicializa AI analyzer por cada URL | Overhead innecesario, sin pool de conexiones |
| `selenium_credential_tester.py:81-139` | Crea nuevo WebDriver por cada test SIN cleanup garantizado | Memory leak, zombie processes |
| `helpers.py:1022-1143` | `default_creds_category()` carga signatures.json en cada llamada | I/O blocking repetitivo |

### 1.2 Secciones No Thread-Safe

```
┌─────────────────────────────────────────────────────────────────────┐
│ PROBLEMA CRÍTICO: SQLite + Multiprocessing                          │
├─────────────────────────────────────────────────────────────────────┤
│ db_manager.py línea 41-42:                                          │
│   self._connection = sqlite3.connect(                               │
│       self._dbpath, check_same_thread=False)                        │
│                                                                     │
│ ❌ check_same_thread=False NO hace SQLite thread-safe               │
│ ❌ Múltiples procesos escribiendo = database locked errors          │
│ ❌ Posible corrupción de datos bajo alta concurrencia               │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Recursos Compartidos Peligrosos

| Recurso | Estado Actual | Riesgo |
|---------|---------------|--------|
| **Chromium Profile** | Usa perfil default del sistema | Colisiones de cookies/cache entre workers |
| **SQLite Database** | Conexión por proceso sin serialización | Database locks, corruption |
| **signatures.json** | Lectura/escritura sin lock | Datos inconsistentes |
| **Virtual Display** | Un solo `:99` para todos | Potencial conflicto Xvfb |
| **Temp directories** | Compartido entre procesos | Archivos sobrescritos |
| **AI API client** | Instancia por request | Rate limiting no controlado |

### 1.4 Acoplamientos Problemáticos

```
worker_thread() [líneas 453-563]
    ├── create_driver()           # Navegador
    ├── capture_host()            # Screenshot + Headers + Tech detection
    │   ├── collect_http_headers()
    │   ├── detect_technologies()
    │   ├── get_ssl_cert_info()
    │   └── driver.save_screenshot()
    ├── default_creds_category()  # Signatures
    ├── AICredentialAnalyzer()    # AI + Credential Testing
    │   ├── ai_analyzer.identify_application()
    │   ├── ai_analyzer.search_default_credentials()
    │   └── selenium_tester.test_credentials()  # ¡OTRO BROWSER!
    └── manager.update_http_object()  # DB Write

PROBLEMA: Todo en un flujo monolítico sin separación de concerns
```

---

## 2. DEFINICIÓN FORMAL DEL "JOB"

### 2.1 Decisión Arquitectónica

**Un JOB = 1 URL = 1 pipeline completo aislado**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        JOB DEFINITION                               │
├─────────────────────────────────────────────────────────────────────┤
│  Input:  URL + CLI Configuration                                    │
│  Output: HTTPTableObject completo                                   │
│                                                                     │
│  Stages:                                                            │
│  1. BROWSE    → Navigate to URL, wait for load                     │
│  2. CAPTURE   → Screenshot + HTML + Headers + Technologies          │
│  3. ANALYZE   → Signature matching + AI identification             │
│  4. TEST      → Credential testing (si aplica)                      │
│  5. PERSIST   → Queue result para DB Writer                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Justificación

| Criterio | 1 URL = 1 Job | N URLs = 1 Job |
|----------|---------------|----------------|
| **Aislamiento** | ✅ Fallo en 1 URL no afecta otras | ❌ Fallo podría perder múltiples URLs |
| **Paralelización** | ✅ Granularidad fina, mejor balanceo | ❌ Workers desbalanceados |
| **Recuperación** | ✅ Retry individual por URL | ❌ Retry de batch completo |
| **Recursos** | ⚠️ Overhead de browser per-URL | ✅ Browser reutilizado |
| **Memoria** | ⚠️ Más instancias activas | ✅ Menos instancias |

**Solución híbrida adoptada:**
- 1 Worker = 1 Browser persistente
- 1 Worker procesa N URLs secuencialmente (con su browser)
- Pool fijo de M workers (ej: 10)

---

## 3. MODELO DE CONCURRENCIA

### 3.1 Comparativa

| Modelo | Chromium | AI/HTTP | DB Writes | Estabilidad | Elección |
|--------|----------|---------|-----------|-------------|----------|
| **threading** | ❌ GIL bloquea | ⚠️ I/O ok | ❌ SQLite locks | Baja | ❌ |
| **asyncio** | ❌ Selenium sync | ✅ Ideal para HTTP | ⚠️ Necesita aiosqlite | Media | ❌ |
| **multiprocessing** | ✅ Aislado | ✅ Aislado | ⚠️ Necesita writer | Alta | ⚠️ |
| **Híbrido: Process Pool + Queue + DB Writer** | ✅✅ | ✅✅ | ✅✅ | **Muy Alta** | ✅✅ |

### 3.2 Arquitectura Seleccionada: Hybrid Process Pool

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DE CONCURRENCIA                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                                                           │
│   │  URL Queue  │  (multiprocessing.Queue - URLs pendientes)                │
│   │   Producer  │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                     WORKER POOL (10 processes)                       │  │
│   │  ┌─────────┐  ┌─────────┐  ┌─────────┐       ┌─────────┐            │  │
│   │  │Worker 1 │  │Worker 2 │  │Worker 3 │  ...  │Worker 10│            │  │
│   │  │┌───────┐│  │┌───────┐│  │┌───────┐│       │┌───────┐│            │  │
│   │  ││Chrome ││  ││Chrome ││  ││Chrome ││       ││Chrome ││            │  │
│   │  ││Profile││  ││Profile││  ││Profile││       ││Profile││            │  │
│   │  ││  /1   ││  ││  /2   ││  ││  /3   ││       ││  /10  ││            │  │
│   │  │└───────┘│  │└───────┘│  │└───────┘│       │└───────┘│            │  │
│   │  └────┬────┘  └────┬────┘  └────┬────┘       └────┬────┘            │  │
│   └───────┼────────────┼────────────┼────────────────┼──────────────────┘  │
│           │            │            │                │                     │
│           ▼            ▼            ▼                ▼                     │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    RESULTS QUEUE                                     │  │
│   │           (multiprocessing.Queue - HTTPTableObjects)                 │  │
│   └─────────────────────────────────┬────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    DB WRITER PROCESS                                 │  │
│   │    (Proceso único dedicado a escrituras SQLite)                      │  │
│   │    - Serializa todas las escrituras                                  │  │
│   │    - Batch inserts cada N resultados                                 │  │
│   │    - WAL mode para mejor concurrencia lecturas                       │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    METRICS COLLECTOR                                 │  │
│   │    - URLs/segundo                                                    │  │
│   │    - Errores por tipo                                                │  │
│   │    - Memory por worker                                               │  │
│   │    - Tiempo promedio por URL                                         │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Por qué este modelo es el más estable

1. **Para Chromium**: Cada proceso tiene su propia instancia de browser con perfil aislado
   - Sin colisiones de cookies/cache
   - Crash de un browser no afecta otros
   - Limpieza automática al terminar proceso

2. **Para AI**: Cada worker tiene su propio cliente API
   - Rate limiting controlado por worker
   - Sin contención de locks
   - Timeouts individuales

3. **Para DB**: Single-writer pattern
   - Elimina race conditions completamente
   - SQLite optimizado para un escritor
   - Batch inserts para eficiencia

---

## 4. DISEÑO DETALLADO DE COMPONENTES

### 4.1 WorkerPool Manager

```python
class WorkerPoolManager:
    """
    Gestiona el pool de workers con:
    - Límite estricto de workers concurrentes
    - Monitoreo de salud de workers
    - Restart automático de workers fallidos
    - Graceful shutdown
    """
    
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.url_queue = multiprocessing.Queue()
        self.result_queue = multiprocessing.Queue()
        self.metrics_queue = multiprocessing.Queue()
        self.shutdown_event = multiprocessing.Event()
        self.workers = []
        
    def start(self):
        """Inicia todos los workers y el DB writer"""
        
    def submit_urls(self, urls: List[str]):
        """Encola URLs para procesamiento"""
        
    def wait_for_completion(self, timeout: int = None) -> bool:
        """Espera a que todos los jobs terminen"""
        
    def shutdown(self, graceful: bool = True):
        """Detiene el pool de manera ordenada"""
```

### 4.2 Isolated Worker

```python
class IsolatedWorker:
    """
    Worker que procesa URLs con browser aislado.
    Cada worker tiene:
    - Su propio perfil Chromium en /tmp/eyewitness_worker_{id}
    - Su propio SeleniumCredentialTester
    - Timeouts y retries individuales
    """
    
    def __init__(self, worker_id: int, cli_parsed, url_queue, result_queue, metrics_queue):
        self.worker_id = worker_id
        self.profile_dir = f"/tmp/eyewitness_worker_{worker_id}"
        self.driver = None
        self.credential_tester = None
        
    def run(self):
        """Loop principal del worker"""
        self._setup_isolated_browser()
        try:
            while not shutdown_event.is_set():
                url = self.url_queue.get(timeout=1)
                if url is None:  # Poison pill
                    break
                result = self._process_url(url)
                self.result_queue.put(result)
        finally:
            self._cleanup()
```

### 4.3 DB Writer Process

```python
class DBWriterProcess:
    """
    Proceso dedicado a escrituras de base de datos.
    Características:
    - Único proceso que escribe a SQLite
    - Buffer de resultados para batch inserts
    - Flush periódico y al shutdown
    """
    
    def __init__(self, db_path: str, result_queue, batch_size: int = 10):
        self.db_path = db_path
        self.result_queue = result_queue
        self.batch_size = batch_size
        self.buffer = []
        
    def run(self):
        """Loop principal del DB writer"""
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA journal_mode=WAL")  # Better concurrency
        connection.execute("PRAGMA synchronous=NORMAL")
        
        while True:
            try:
                result = self.result_queue.get(timeout=1)
                if result is None:
                    self._flush_buffer(connection)
                    break
                self.buffer.append(result)
                if len(self.buffer) >= self.batch_size:
                    self._flush_buffer(connection)
            except queue.Empty:
                if self.buffer:
                    self._flush_buffer(connection)
```

---

## 5. FLUJO DE DATOS

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           FLUJO DE DATOS                                  │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  1. INICIALIZACIÓN                                                        │
│     ┌─────────────┐                                                       │
│     │  urls.txt   │──► target_creator() ──► List[str]                    │
│     └─────────────┘                                                       │
│                                                                           │
│  2. DISTRIBUCIÓN                                                          │
│     List[str] ──► WorkerPoolManager.submit_urls() ──► url_queue          │
│                                                                           │
│  3. PROCESAMIENTO (paralelo en N workers)                                 │
│     url_queue ──► Worker.process_url() ──► HTTPTableObject               │
│                                                                           │
│     process_url():                                                        │
│       ├── driver.get(url)                     # Navigate                  │
│       ├── capture_host()                      # Screenshot + Data         │
│       ├── default_creds_category()            # Signatures                │
│       ├── AICredentialAnalyzer.analyze()      # AI + Creds (optional)     │
│       └── return HTTPTableObject                                          │
│                                                                           │
│  4. PERSISTENCIA (single writer)                                          │
│     HTTPTableObject ──► result_queue ──► DBWriter.write() ──► SQLite     │
│                                                                           │
│  5. MÉTRICAS (background)                                                 │
│     Worker events ──► metrics_queue ──► MetricsCollector ──► Console     │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 6. MANEJO DE ERRORES Y RESILIENCIA

### 6.1 Estrategia de Retries

```python
RETRY_CONFIG = {
    'timeout': {
        'max_retries': 2,
        'backoff': [5, 10],  # segundos
        'action': 'retry_with_refresh'
    },
    'connection_refused': {
        'max_retries': 1,
        'backoff': [3],
        'action': 'mark_failed'
    },
    'driver_crashed': {
        'max_retries': 1,
        'backoff': [2],
        'action': 'recreate_driver'
    },
    'ai_rate_limit': {
        'max_retries': 3,
        'backoff': [30, 60, 120],
        'action': 'exponential_backoff'
    }
}
```

### 6.2 Circuit Breaker para AI

```python
class AICircuitBreaker:
    """Protege contra cascada de fallos de API"""
    
    def __init__(self, failure_threshold=5, recovery_timeout=60):
        self.failures = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
        self.last_failure = None
        
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise CircuitBreakerOpen()
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

---

## 7. INSTRUMENTACIÓN Y OBSERVABILIDAD

### 7.1 Métricas Recolectadas

```python
@dataclass
class WorkerMetrics:
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
```

### 7.2 Logging por Worker

```python
# Formato: [TIMESTAMP] [WORKER-ID] [LEVEL] message
# Ejemplo:
# [2024-12-30 10:15:32] [W-03] [INFO] Processing: https://192.168.1.100:8080
# [2024-12-30 10:15:35] [W-03] [WARN] Timeout on first attempt, retrying...
# [2024-12-30 10:15:40] [W-03] [OK] Screenshot captured in 8.2s
# [2024-12-30 10:15:42] [W-03] [AI] Identified: Cisco Switch (Catalyst 9200)

def setup_worker_logger(worker_id: int, log_dir: str) -> logging.Logger:
    logger = logging.getLogger(f'eyewitness.worker.{worker_id}')
    handler = logging.FileHandler(f'{log_dir}/worker_{worker_id}.log')
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [W-%(worker_id)02d] [%(levelname)s] %(message)s'
    ))
    logger.addHandler(handler)
    return logger
```

---

## 8. CAMBIOS CLAVE EN EL CÓDIGO

### 8.1 Archivos a Modificar

| Archivo | Cambios |
|---------|---------|
| `EyeWitness.py` | Reemplazar `multi_mode()` con `WorkerPoolManager` |
| `modules/selenium_module.py` | Añadir `create_isolated_driver()` con perfil único |
| `modules/db_manager.py` | Crear `DBWriterProcess` como proceso separado |
| `modules/concurrency.py` | **NUEVO**: Worker pool, queues, metrics |
| `modules/ai_credential_analyzer.py` | Añadir circuit breaker y rate limiting |

### 8.2 Nuevo Módulo: concurrency.py

Ver implementación completa en la siguiente sección.

---

## 9. CHECKLIST DE VALIDACIÓN

### 9.1 Verificar 10 Navegadores Concurrentes

```bash
# Durante ejecución, en otra terminal:
ps aux | grep -E "chrome|chromium" | grep -v grep | wc -l
# Debe mostrar ~10 (+ algunos procesos auxiliares)

# Verificar perfiles aislados:
ls -la /tmp/eyewitness_worker_*/
# Debe mostrar 10 directorios

# Verificar PIDs únicos:
pgrep -af "chrome.*eyewitness_worker" | awk '{print $1}' | sort -u | wc -l
# Debe ser 10
```

### 9.2 Verificar Sin Colisiones de Recursos

```bash
# Monitorear locks SQLite:
watch -n 1 'lsof /path/to/project.db 2>/dev/null | wc -l'
# Debe ser 1 (solo el DB Writer)

# Verificar no hay archivos .lock de Chrome:
find /tmp/eyewitness_worker_* -name "*.lock" 2>/dev/null
# No debe haber conflictos

# Verificar archivos temporales únicos por worker:
ls /tmp/eyewitness_worker_*/chrome_* | head -20
```

### 9.3 Verificar Resultados No Se Pierden

```bash
# Contar URLs de entrada:
wc -l urls.txt

# Después de ejecución, contar resultados en DB:
sqlite3 project.db "SELECT COUNT(*) FROM http WHERE complete=1"

# Verificar que coinciden (o diferencia son timeouts/errores legítimos):
sqlite3 project.db "SELECT COUNT(*) FROM http WHERE error_state IS NOT NULL"
```

### 9.4 Verificar Tolerancia a Fallos

```bash
# Test: Matar un worker durante ejecución
kill -9 $(pgrep -f "eyewitness_worker_3" | head -1)

# Verificar:
# 1. Otros workers continúan
# 2. URLs del worker muerto se redistribuyen (si implementado)
# 3. No hay crash del sistema completo
# 4. Logs muestran el evento

# Verificar cleanup al final:
pgrep -f eyewitness_worker
# No debe haber procesos huérfanos
```

---

## 10. USO RECOMENDADO

```bash
# Procesamiento con 10 workers paralelos
python3 Python/EyeWitness.py --web -f urls.txt --db myproject --threads 10 --enable-ai

# Con métricas verbose
python3 Python/EyeWitness.py --web -f urls.txt --db myproject --threads 10 --verbose-metrics

# Con timeouts ajustados para scans grandes
python3 Python/EyeWitness.py --web -f urls.txt --db myproject --threads 10 --timeout 45 --max-retries 2
```

---

## 11. MIGRACIÓN

### Fase 1: Implementar sin romper compatibilidad
- `--threads 1` usa el código legacy (actual)
- `--threads N>1` usa el nuevo WorkerPoolManager

### Fase 2: Deprecar modo legacy
- Advertencia cuando `--threads 1`
- Default a 4 workers

### Fase 3: Eliminar código legacy
- Remover `worker_thread()` y `multi_mode()` originales


