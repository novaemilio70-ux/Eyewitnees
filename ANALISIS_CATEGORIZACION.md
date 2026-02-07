# Análisis: Sistema de Categorización de EyeWitness

## Resumen Ejecutivo

EyeWitness categoriza automáticamente las páginas web que encuentra mediante un sistema multi-nivel que combina:
1. **Firmas de aplicaciones** (signatures.json)
2. **Análisis automático** basado en tecnologías, URLs, headers y títulos
3. **Análisis con IA** (opcional, si está habilitado)
4. **Detección de páginas de error** (401, 403, 404, directory listings)

La información se guarda en una **base de datos SQLite** usando serialización con `pickle`, donde cada objeto `HTTPTableObject` completo (incluyendo la categoría) se almacena como un BLOB.

---

## Flujo de Categorización

### 1. Punto de Entrada Principal

La categorización se realiza en la función `default_creds_category()` ubicada en:
- **Archivo**: `Python/modules/helpers.py`
- **Líneas**: 1022-1135

Esta función se llama después de capturar cada página web, en los siguientes puntos:

```python
# En EyeWitness.py:
- Línea 419: single_mode() - modo de URL única
- Línea 499: worker_thread() - modo multi-thread
- Línea 524: worker_thread() - para objetos UA (User Agent)
```

### 2. Proceso de Categorización (Orden de Prioridad)

La función `default_creds_category()` sigue este orden de prioridad:

#### **Nivel 1: Firmas de Aplicaciones (signatures.json)**
- **Ubicación**: `Python/signatures.json`
- **Gestor**: `modules/signature_manager.py`
- **Proceso**:
  1. Busca patrones en el código HTML (`source_code`) del objeto HTTP
  2. Si encuentra una firma coincidente, extrae:
     - **Categoría** de la firma (si existe)
     - **Credenciales por defecto** asociadas
  3. Si la firma tiene categoría, la asigna directamente
  4. Si no tiene categoría, intenta auto-categorización

```python
# Código relevante (helpers.py:1047-1093)
matching_sig = sig_manager.find_matching_signature(html_content)
if matching_sig:
    category = matching_sig.get('category')
    if category:
        http_object.category = category  # Asignación directa
```

#### **Nivel 2: Páginas de Error (Alta Prioridad)**
- Detecta errores HTTP comunes en el `page_title`:
  - `'unauth'` - 401 Unauthorized / 403 Forbidden
  - `'dirlist'` - Directory Listing (Index of /)
  - `'notfound'` - 404 Not Found

```python
# Código relevante (helpers.py:1097-1121)
if '403 Forbidden' in http_object.page_title or '401 Unauthorized' in http_object.page_title:
    http_object.category = 'unauth'
if 'Index of /' in http_object.page_title:
    http_object.category = 'dirlist'
if '404 Not Found' in http_object.page_title:
    http_object.category = 'notfound'
```

#### **Nivel 3: Auto-Categorización Automática**
- **Función**: `auto_categorize()` en `helpers.py` (líneas 765-1019)
- **Métodos de detección**:

##### 3.1. Basado en Tecnologías Detectadas
Analiza la lista `http_object.technologies` para detectar:
- Virtualización: VMware, vSphere, ESXi
- Dispositivos de red: Cisco, Meraki, Ubiquiti, Fortinet
- Almacenamiento: Synology, QNAP, NetApp
- Monitoreo: Grafana, Prometheus, Nagios
- DevOps: Jenkins, GitLab, Docker
- Servidores web: Apache, nginx, IIS
- Y muchas más...

##### 3.2. Basado en Información de IA
Si `--enable-ai` está activo y hay información de IA:
- Analiza `http_object.ai_application_info`
- Extrae `application_name` y `application_type`
- Mapea a categorías según patrones de nombres

##### 3.3. Basado en Patrones de URL
- Puertos: `:8443`, `:9443` → `virtualization` o `infrastructure`
- Puertos: `:8080`, `:8000`, `:8888` → `appserver`
- Paths: `/jenkins` → `devops`, `/grafana` → `monitoring`, `/swagger` → `api`

##### 3.4. Basado en Headers HTTP
Analiza el header `Server`:
- `vmware`, `esxi` → `virtualization`
- `cisco` → `network_device`
- `apache`, `nginx`, `iis` → `webserver`

##### 3.5. Basado en Título de Página
Busca palabras clave en `page_title`:
- `cisco`, `switch`, `router` → `network_device`
- `synology`, `qnap` → `storage`
- `grafana`, `prometheus` → `monitoring`
- `printer`, `laserjet` → `printer`
- Y muchos más patrones...

#### **Nivel 4: Categorización por IA (si está habilitado)**
- **Ubicación**: `modules/ai_credential_analyzer.py`
- Se ejecuta después de `default_creds_category()` si `--enable-ai` está activo
- Puede sobrescribir la categoría basándose en análisis de IA del contenido de la página

---

## Categorías Disponibles

El sistema utiliza un conjunto estandarizado de categorías:

| Categoría | Descripción | Ejemplos |
|-----------|-------------|----------|
| `storage` | Sistemas de almacenamiento | IBM Storwize, Quantum DXi, QNAP, Synology |
| `network_device` | Switches, routers, APs, firewalls | Cisco, Ubiquiti, WatchGuard |
| `network_management` | Sistemas de gestión de red | UNMS, UniFi Controller |
| `printer` | Impresoras y MFPs | HP LaserJet, Ricoh, Epson |
| `voip` | Teléfonos VoIP | Grandstream, Yealink |
| `video_conference` | Sistemas de videoconferencia | Polycom, Crestron |
| `idrac` | Gestión de servidores | Dell iDRAC, HP iLO |
| `monitoring` | Sistemas de monitoreo | Grafana, Nagios, Zabbix |
| `itsm` | IT Service Management | ManageEngine ServiceDesk |
| `iot` | Dispositivos IoT | Identec Solutions |
| `business_app` | Aplicaciones de negocio | Apps personalizadas |
| `webserver` | Servidores web | IIS, Apache, nginx |
| `appserver` | Servidores de aplicaciones | JBoss, Tomcat, WebLogic |
| `api` | Documentación de API | Swagger UI |
| `error_page` | Páginas de error | 401, 403, 404 |
| `virtualization` | Plataformas de virtualización | VMware, vSphere |
| `devops` | Desarrollo y operaciones | Jenkins, GitLab |
| `dataops` | Operaciones de datos | MySQL, MongoDB, Redis |
| `comms` | Comunicaciones | Outlook, Exchange |
| `secops` | Seguridad | Splunk, Nessus |
| `unauth` | No autorizado | 401, 403 |
| `dirlist` | Listado de directorios | Index of / |
| `notfound` | No encontrado | 404 |
| `unknown` | No identificado | Fallback cuando no hay coincidencia |

---

## Almacenamiento de la Información

### Estructura de la Base de Datos

La información se guarda en una **base de datos SQLite** con la siguiente estructura:

#### Tabla: `http`
```sql
CREATE TABLE http (
    id INTEGER PRIMARY KEY,
    object BLOB,          -- Objeto HTTPTableObject serializado con pickle
    complete BOOLEAN      -- Indica si el procesamiento está completo
)
```

#### Ubicación de la Base de Datos

La base de datos se crea en diferentes ubicaciones según el modo de ejecución:

1. **Modo `--db <project_name>` (Recomendado)**:
   - **Ruta**: `eyewitness_projects/<project_name>/<project_name>.db`
   - **Ejemplo**: `eyewitness_projects/laboon/laboon.db`

2. **Modo `-d <directory>`**:
   - **Ruta**: `<directory>/ew.db`
   - **Ejemplo**: `./output_folder/ew.db`

3. **Modo legacy (timestamp)**:
   - **Ruta**: `<timestamp_folder>/ew.db`
   - **Ejemplo**: `2025-01-15_143022/ew.db`

### Serialización del Objeto

El objeto `HTTPTableObject` completo se serializa usando `pickle` y se guarda como BLOB:

```python
# Código en db_manager.py:123-129
def update_http_object(self, http_object):
    c = self.connection.cursor()
    o = sqlite3.Binary(pickle.dumps(http_object, protocol=2))
    c.execute(("UPDATE http SET object=?,complete=? WHERE id=?"),
              (o, True, http_object.id))
    self.connection.commit()
    c.close()
```

### Propiedades del Objeto HTTPTableObject

El objeto `HTTPTableObject` (definido en `modules/objects.py`) contiene:

```python
# Propiedades relacionadas con categorización:
self._category = None              # Categoría asignada
self._default_creds = None         # Credenciales por defecto encontradas
self._page_title = None            # Título de la página
self._source_code = None           # Código HTML fuente
self._technologies = None          # Lista de tecnologías detectadas
self._ai_application_info = None   # Información de IA (si está habilitado)
self._http_headers = {}            # Headers HTTP
```

### Flujo de Guardado

1. **Captura de página** → `selenium_module.capture_host()`
2. **Categorización** → `default_creds_category(http_object)`
3. **Análisis IA (opcional)** → `AICredentialAnalyzer.analyze_http_object()`
4. **Guardado en BD** → `db_manager.update_http_object(http_object)`

```python
# Flujo en worker_thread() (EyeWitness.py:496-519)
http_object, driver = capture_host(cli_parsed, http_object, driver)
if http_object.category is None and http_object.error_state is None:
    http_object = default_creds_category(http_object)  # Categorización
    
    # Análisis IA si está habilitado
    if cli_parsed.enable_ai or cli_parsed.test_credentials:
        ai_analyzer = AICredentialAnalyzer(...)
        http_object = ai_analyzer.analyze_http_object(http_object)
    
manager.update_http_object(http_object)  # Guardado en BD
```

---

## Acceso a la Información Categorizada

### Desde la Base de Datos

Para recuperar objetos categorizados:

```python
from modules.db_manager import DB_Manager
import pickle

dbm = DB_Manager('eyewitness_projects/laboon/laboon.db')
dbm.open_connection()
results = dbm.get_complete_http()  # Obtiene todos los objetos completos

for http_object in results:
    print(f"URL: {http_object.remote_system}")
    print(f"Categoría: {http_object.category}")
    print(f"Credenciales: {http_object.default_creds}")
    print(f"Título: {http_object.page_title}")
```

### Desde la Interfaz Web

La aplicación web (en `webapp/`) puede acceder a la base de datos y mostrar los resultados categorizados. Los objetos se deserializan automáticamente cuando se recuperan de la BD.

### Agrupación por Categoría

En `modules/reporting.py`, los resultados se agrupan por categoría:

```python
# Línea 36 en reporting.py
group_data = sorted([x for x in data if x.category == group], 
                    key=lambda k: str(k.page_title))
```

---

## Archivos Clave

| Archivo | Función |
|---------|---------|
| `Python/modules/helpers.py` | `default_creds_category()`, `auto_categorize()` |
| `Python/modules/db_manager.py` | `update_http_object()`, `get_complete_http()` |
| `Python/modules/objects.py` | Clase `HTTPTableObject` con propiedad `category` |
| `Python/modules/signature_manager.py` | Gestión de firmas en `signatures.json` |
| `Python/modules/ai_credential_analyzer.py` | Categorización asistida por IA |
| `Python/signatures.json` | Base de datos de firmas de aplicaciones |
| `Python/EyeWitness.py` | Orquestación principal, llama a `default_creds_category()` |

---

## Ejemplo de Flujo Completo

```
1. Usuario ejecuta: python EyeWitness.py -f urls.txt --db myproject

2. EyeWitness.py crea proyecto:
   → eyewitness_projects/myproject/myproject.db

3. Para cada URL:
   a. capture_host() captura la página
   b. default_creds_category() categoriza:
      - Busca en signatures.json
      - Detecta páginas de error
      - Ejecuta auto_categorize()
   c. Si --enable-ai: AICredentialAnalyzer refina categoría
   d. update_http_object() guarda en BD

4. Al finalizar:
   → sort_data_and_write() genera reportes agrupados por categoría
   → Webapp puede visualizar resultados desde la BD
```

---

## Notas Importantes

1. **Serialización con Pickle**: Los objetos se guardan como BLOB usando `pickle`, lo que significa que toda la información del objeto (incluyendo categoría) está en la base de datos.

2. **Actualización de Categorías**: Si se re-ejecuta el escaneo con `--resume`, las categorías pueden actualizarse si cambian las firmas o el análisis automático.

3. **Prioridad de Categorización**: 
   - Firmas de aplicaciones (más específico)
   - Páginas de error
   - Auto-categorización
   - IA (si está habilitado)
   - `unknown` (fallback)

4. **Persistencia**: La categoría se guarda como parte del objeto `HTTPTableObject` en la base de datos, por lo que persiste entre ejecuciones.

