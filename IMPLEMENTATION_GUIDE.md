# Implementation Guide: AI-Powered Web Application Security Scanner

Este documento describe las funcionalidades adicionales implementadas en EyeWitness para análisis de credenciales con AI, pruebas de credenciales, y escaneo de puertos integrado. Utiliza esta guía para implementar las mismas funcionalidades en otro proyecto.

---

## Tabla de Contenidos

1. [Resumen de Funcionalidades](#1-resumen-de-funcionalidades)
2. [Módulo 1: Análisis de Aplicaciones con AI](#2-módulo-1-análisis-de-aplicaciones-con-ai)
3. [Módulo 2: Análisis de Formularios HTML](#3-módulo-2-análisis-de-formularios-html)
4. [Módulo 3: Pruebas de Credenciales](#4-módulo-3-pruebas-de-credenciales)
5. [Módulo 4: Orquestador de Análisis](#5-módulo-4-orquestador-de-análisis)
6. [Módulo 5: Port Scanner Integrado](#6-módulo-5-port-scanner-integrado)
7. [Integración con CLI](#7-integración-con-cli)
8. [Estructuras de Datos](#8-estructuras-de-datos)
9. [Consideraciones para Windows y macOS](#9-consideraciones-para-windows-y-macos)

---

## 1. Resumen de Funcionalidades

### Funcionalidades Implementadas:

1. **AI Application Identification**: Usa OpenAI GPT-4o-mini o Anthropic Claude para identificar aplicaciones web desde el HTML.

2. **AI Default Credentials Search**: Busca credenciales por defecto conocidas para la aplicación identificada.

3. **Form Analysis**: Parsea HTML para encontrar formularios de login y extraer campos (username, password, CSRF tokens).

4. **Credential Testing**: Prueba credenciales automáticamente con manejo de CSRF, cookies, y análisis de respuesta.

5. **Auth Methods Storage**: Guarda métodos de autenticación para password spraying posterior.

6. **Integrated Port Scanner**: Escaneo de puertos custom sin dependencias externas (sin Nmap).

---

## 2. Módulo 1: Análisis de Aplicaciones con AI

### Propósito
Identificar aplicaciones web que no están en la base de datos de firmas conocidas, usando AI para analizar el HTML.

### Proveedores Soportados
- **OpenAI**: GPT-4o-mini (económico y rápido)
- **Anthropic**: Claude 3 Haiku (alternativa)

### Pseudocódigo

```
CLASS AIAnalyzer:
    CONSTRUCTOR(api_key, provider):
        - Validar que la librería del provider esté instalada
        - Validar API key
        - Inicializar cliente de AI
    
    METHOD identify_application(html_content, url):
        - Truncar HTML a 50,000 caracteres si es muy largo
        - Construir prompt pidiendo identificar:
            - Nombre de la aplicación
            - Versión
            - Tipo (CMS, CI/CD, etc.)
            - Confianza (high/medium/low)
            - Indicadores encontrados
        - Enviar al AI con temperature=0.3
        - Parsear respuesta JSON
        - Retornar dict con información
    
    METHOD search_default_credentials(app_name, app_type):
        - Construir prompt pidiendo credenciales por defecto
        - Enviar al AI
        - Parsear respuesta como array JSON
        - Retornar lista de credenciales [{username, password, description, source}]
```

### Prompt para Identificar Aplicación

```
Analyze this HTML code from a web application and identify:
1. The application name/software (e.g., "WordPress", "Jenkins", "Apache Tomcat")
2. The version if visible
3. Any indicators that suggest what type of application this is

HTML Content:
{html_content}

URL: {url}

Respond ONLY with a JSON object in this exact format:
{
    "application_name": "name or null",
    "version": "version or null",
    "application_type": "type (e.g., CMS, CI/CD, Web Server, etc.) or null",
    "confidence": "high/medium/low",
    "indicators": ["list", "of", "key", "indicators", "found"]
}
```

### Prompt para Buscar Credenciales

```
Search for default credentials for the application: {application_name}
Type: {application_type}

Provide default credentials in JSON format. Respond ONLY with a JSON array:
[
    {
        "username": "username or null",
        "password": "password or null",
        "description": "brief description",
        "source": "where this info comes from"
    }
]

If no default credentials are found, return an empty array: []
```

### Modelos Recomendados
- **OpenAI**: `gpt-4o-mini` - Barato ($0.15/1M input, $0.60/1M output)
- **Anthropic**: `claude-3-haiku-20240307` - Rápido y económico

---

## 3. Módulo 2: Análisis de Formularios HTML

### Propósito
Parsear HTML para encontrar formularios de login y extraer:
- Action URL del formulario
- Método HTTP (POST/GET)
- Campo de username
- Campo de password
- Tokens CSRF
- Otros campos ocultos necesarios

### Pseudocódigo

```
CLASS FormField:
    PROPERTIES:
        - name: string
        - type: string (text, password, hidden, etc.)
        - required: boolean
        - value: string (importante para campos hidden!)

CLASS LoginForm:
    PROPERTIES:
        - action: string (URL del formulario)
        - method: string (POST/GET)
        - fields: List[FormField]
        - username_field: FormField
        - password_field: FormField
        - csrf_token: string (nombre del campo)
        - csrf_value: string (valor actual del token)
    
    METHOD add_field(field):
        - Agregar a fields
        - Auto-detectar si es username/password:
            - Si type == "password" → password_field
            - Si name contiene "user", "login", "email", "account" → username_field
    
    METHOD get_auth_endpoint(base_url):
        - Resolver action URL relativo a base_url

CLASS FormParser (HTML Parser):
    - Al encontrar <form>:
        - Extraer action y method
        - Crear nuevo LoginForm
    
    - Al encontrar <input> dentro de form:
        - Extraer type, name, value, required
        - Si es hidden y name contiene "csrf", "token", "_token", "nonce":
            - Guardar como csrf_token y csrf_value
        - Crear FormField y agregar al formulario
    
    - Al cerrar </form>:
        - Agregar formulario a lista si tiene campos

CLASS FormAnalyzer:
    STATIC METHOD find_login_forms(html, base_url):
        - Parsear HTML
        - Filtrar formularios que tengan campo password
        - Si no hay, buscar formularios con indicadores de login
        - Retornar lista de LoginForm
    
    STATIC METHOD extract_auth_info(html, base_url):
        - Encontrar formularios de login
        - Detectar tipo de autenticación:
            - form_based (por defecto)
            - basic_auth
            - oauth
            - ldap
            - sso
            - api_key
        - Retornar dict con toda la info
```

### Detección de Campos Username

Buscar campos cuyo `name` contenga:
- `user`, `username`, `login`, `email`, `account`, `name`, `uid`

### Detección de CSRF Tokens

Buscar inputs hidden cuyo `name` contenga:
- `csrf`, `token`, `_token`, `authenticity_token`, `nonce`, `__RequestVerificationToken`, `csrfmiddlewaretoken`

**IMPORTANTE**: Extraer tanto el nombre del campo como su valor actual.

---

## 4. Módulo 3: Pruebas de Credenciales

### Propósito
Probar credenciales encontradas contra los formularios de login detectados.

### Desafíos Técnicos

1. **CSRF Tokens**: Muchas aplicaciones requieren token CSRF válido
2. **Cookies de Sesión**: Mantener cookies entre requests
3. **Detección de Éxito/Fallo**: No hay estándar, hay que usar heurísticas

### Pseudocódigo

```
CLASS CredentialTestResult:
    PROPERTIES:
        - credentials_tested: List[Dict]
        - successful_credentials: List[Dict]
        - failed_credentials: List[Dict]
        - test_errors: List[string]
        - auth_endpoint: string
        - auth_method: string
        - testable: boolean
        - tested: boolean

CLASS CredentialTester:
    CONSTANTS:
        FAILURE_INDICATORS = [
            "invalid", "incorrect", "wrong", "failed", "error", "denied",
            "unauthorized", "bad credentials", "login failed", 
            "authentication failed", "access denied", "try again"
        ]
        
        SUCCESS_INDICATORS = [
            "dashboard", "welcome", "logout", "sign out", "profile",
            "settings", "account", "home", "admin", "control panel",
            "successfully", "logged in", "authenticated"
        ]
    
    CONSTRUCTOR(timeout=10, delay=1.0, user_agent):
        - Configurar timeout
        - Configurar delay entre requests (evitar rate limiting)
        - Configurar User-Agent realista
        - Crear contexto SSL que ignore certificados
    
    METHOD _fetch_csrf_token(base_url, opener, csrf_field_name):
        """Obtener CSRF token fresco de la página de login"""
        - Hacer GET request a la página de login
        - Parsear HTML buscando:
            - <input type="hidden" name="csrf*" value="...">
            - <meta name="csrf-token" content="...">
        - Retornar (field_name, token_value)
    
    METHOD test_credentials(base_url, login_form, credentials, cookies):
        - Crear CredentialTestResult
        - Para cada credencial:
            - Esperar delay segundos
            - Llamar _test_single_credential
            - Agregar resultado
        - Retornar resultado
    
    METHOD _test_single_credential(...):
        - Crear opener con cookie jar fresco
        - Agregar cookies iniciales si existen
        - Obtener CSRF token fresco (importante!)
        - Construir form data:
            - username_field: username
            - password_field: password
            - csrf_field: csrf_value (si existe)
            - Otros campos hidden con sus valores
        - Enviar POST request
        - Analizar respuesta
        - Retornar (success, response_info)
    
    METHOD _analyze_response(response_code, response_url, response_body, ...):
        """7 heurísticas para detectar login exitoso"""
        
        1. Si hay ≥2 indicadores de fallo → FALLO
        
        2. Si hay redirección FUERA de página de login → ÉXITO
           (estaba en /login, ahora en /dashboard)
        
        3. Si hay ≥2 indicadores de éxito y 0 de fallo → ÉXITO
        
        4. Si se establecieron cookies de sesión y 0 fallos → ÉXITO
           (buscar: session, sess, auth, token, jsessionid, phpsessid)
        
        5. Si header Set-Cookie tiene cookies de auth → ÉXITO
        
        6. Si respuesta contiene "logout" link → ÉXITO
        
        7. Si sigue en página de login → FALLO
        
        8. En caso de duda → FALLO (más seguro)
```

### Headers HTTP Necesarios

```http
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...
Content-Type: application/x-www-form-urlencoded
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: en-US,en;q=0.9
Referer: {base_url}
Origin: {origin}
```

### Manejo de Cookies

```
1. Crear CookieJar vacío
2. GET a login page → cookies de sesión inicial
3. POST con credenciales → cookies de autenticación
4. Analizar cookies para detectar éxito
```

---

## 5. Módulo 4: Orquestador de Análisis

### Propósito
Coordinar todos los módulos anteriores y manejar el flujo completo de análisis.

### Flujo de Análisis

```
FUNCIÓN analyze_http_object(http_object):
    
    1. Verificar si ya tiene credenciales de signatures → saltar AI
    
    2. Verificar si hay código fuente HTML disponible
    
    3. SI AI está habilitado:
        a. Llamar ai_analyzer.identify_application(html, url)
        b. SI identificó aplicación:
            - Guardar app_info en http_object
            - Llamar ai_analyzer.search_default_credentials(app_name)
            - Guardar credenciales encontradas
    
    4. SIEMPRE (con o sin AI):
        a. Llamar form_analyzer.extract_auth_info(html, url)
        b. Guardar auth_info en http_object
        c. SI hay formulario de login con username/password:
            - Guardar auth_method para password spraying
    
    5. SI credential testing está habilitado Y hay credenciales:
        a. Obtener cookies del http_object
        b. Llamar credential_tester.test_credentials(...)
        c. Guardar resultados
    
    RETORNAR http_object actualizado
```

### Almacenamiento para Password Spraying

```json
{
    "WordPress": [
        {
            "url": "http://example.com/wp-login.php",
            "endpoint": "/wp-login.php",
            "method": "POST",
            "username_field": "log",
            "password_field": "pwd",
            "auth_type": "form_based",
            "tested": true,
            "has_working_creds": false
        }
    ],
    "Jenkins": [
        {
            "url": "http://ci.example.com/login",
            "endpoint": "/j_spring_security_check",
            "method": "POST",
            "username_field": "j_username",
            "password_field": "j_password",
            "auth_type": "form_based"
        }
    ]
}
```

---

## 6. Módulo 5: Port Scanner Integrado

### Propósito
Descubrir servicios web sin depender de herramientas externas como Nmap.

### Características

- Pure Python, sin dependencias externas
- Múltiples threads concurrentes
- User-Agents realistas y rotación
- Detección automática HTTP vs HTTPS
- Soporte para CIDR, rangos de IP, hostnames
- Headers de browser realista

### Port Presets

```python
PORT_PRESETS = {
    'small': [80, 443],
    'medium': [80, 443, 8000, 8080, 8443],
    'large': [80, 81, 443, 591, 2082, 2087, 2095, 2096, 3000, 8000, 
              8001, 8008, 8080, 8083, 8443, 8834, 8888],
    'xlarge': [80, 81, 300, 443, 591, 593, 832, 981, 1010, 1311, 
               2082, 2087, 2095, 2096, 2480, 3000, 3128, 3333, 4243,
               4567, 4711, 4712, 4993, 5000, 5104, 5108, 5800, 6543, 
               7000, 7396, 7474, 8000, 8001, 8008, 8014, 8042, 8050, 
               8060, 8070, 8069, 8080, 8081, 8088, 8090, 8091, 8118, 
               8123, 8172, 8222, 8243, 8280, 8281, 8333, 8443, 8500, 
               8834, 8880, 8888, 8983, 9000, 9043, 9060, 9080, 9090, 
               9091, 9200, 9443, 9800, 9981, 12443, 16080, 18091, 
               18092, 20720, 28017]
}
```

### User-Agents Realistas

```python
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]
```

### Pseudocódigo

```
FUNCTION expand_targets(target):
    """Expande un target a lista de IPs"""
    
    SI es CIDR (ej: 192.168.1.0/24):
        - Usar librería ipaddress para expandir
        - Retornar lista de IPs
    
    SI es rango (ej: 192.168.1.1-10 o 192.168.1.1-192.168.1.10):
        - Parsear inicio y fin
        - Generar todas las IPs en el rango
        - Retornar lista
    
    SI es hostname o IP simple:
        - Retornar como lista de un elemento

CLASS WebPortScanner:
    CONSTRUCTOR(timeout=2.0, threads=100, user_agent=None):
        - Configurar parámetros
    
    METHOD _check_port(host, port):
        """Verificar si puerto está abierto y es web"""
        
        1. Crear socket TCP
        2. Resolver hostname a IP
        3. Intentar conexión con timeout
        4. SI conexión exitosa:
            - Llamar _detect_web_service
        5. Retornar (is_open, protocol, info)
    
    METHOD _detect_web_service(sock, host, port, info):
        """Detectar si es HTTP o HTTPS"""
        
        1. SI puerto es HTTPS común (443, 8443, etc.):
            - Intentar SSL handshake
            - SI funciona → HTTPS
        
        2. Intentar HTTP plano:
            - Enviar GET / HTTP/1.1 con headers de browser
            - Parsear respuesta
            - Extraer Server header y título
        
        3. Retornar (protocol, info)
    
    METHOD _build_http_request(host, port, user_agent):
        """Construir request HTTP realista"""
        
        Headers a incluir:
        - Host
        - User-Agent (realista)
        - Accept (como navegador)
        - Accept-Language
        - Accept-Encoding
        - Connection: close
        - Upgrade-Insecure-Requests
        - Sec-Fetch-* headers
    
    METHOD scan_targets(targets, ports):
        """Escanear múltiples targets"""
        
        1. Expandir todos los targets
        2. Eliminar duplicados
        3. Para cada target:
            - Escanear con ThreadPoolExecutor
            - Mostrar progreso
        4. Retornar lista de URLs encontradas
```

### HTTP Request Realista

```http
GET / HTTP/1.1
Host: example.com
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate
Connection: close
Upgrade-Insecure-Requests: 1
Cache-Control: max-age=0
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: none
Sec-Fetch-User: ?1
```

---

## 7. Integración con CLI

### Argumentos de Línea de Comandos

```
AI Options:
  --enable-ai           Enable AI-powered analysis
  --ai-api-key KEY      API key for AI service
  --ai-provider NAME    AI provider: openai or anthropic
  --test-credentials    Enable automatic credential testing
  --credential-test-timeout SECONDS  Timeout for tests (default: 10)
  --credential-test-delay SECONDS    Delay between tests (default: 1.0)

Scan Options:
  --scan               Enable integrated port scanning
  --scan-ports PRESET  Port preset: small, medium, large, xlarge
  --custom-ports PORTS Custom ports (comma-separated)
  --scan-timeout SECS  Scan timeout (default: 2.0)
  --scan-threads NUM   Concurrent threads (default: 100)
```

### Flujo de Ejecución

```
1. SI --scan está habilitado:
    - Expandir targets (CIDR, rangos, etc.)
    - Escanear puertos
    - Generar lista de URLs
2. SINO:
    - Usar lista de URLs provista

3. Para cada URL:
    - Capturar screenshot (existente)
    - Recolectar headers (existente)
    - Obtener HTML (existente)
    - SI --enable-ai:
        - Analizar con AI
        - Buscar credenciales
        - Probar credenciales
    - Guardar auth method para spraying

4. Generar reporte HTML (existente)

5. SI hay auth methods recolectados:
    - Guardar auth_methods_for_spraying.json
```

---

## 8. Estructuras de Datos

### HTTP Object (extendido)

```
HTTPTableObject:
    # Existentes
    remote_system: string (URL)
    source_code: string (HTML)
    headers: dict
    screenshot: string (path)
    default_creds: string (de signatures)
    
    # Nuevos para AI
    ai_application_info: {
        application_name: string,
        version: string,
        application_type: string,
        confidence: string,
        indicators: list
    }
    
    ai_credentials_found: [
        {
            username: string,
            password: string,
            description: string,
            source: string
        }
    ]
    
    auth_info: {
        login_forms: list,
        has_login_form: boolean,
        primary_form: dict,
        auth_type: string
    }
    
    credential_test_result: {
        testable: boolean,
        tested: boolean,
        auth_endpoint: string,
        auth_method: string,
        credentials_tested: int,
        successful_count: int,
        failed_count: int,
        successful_credentials: list,
        failed_credentials: list,
        errors: list
    }
    
    auth_method_stored: {
        url: string,
        endpoint: string,
        method: string,
        username_field: string,
        password_field: string,
        csrf_field: string,
        auth_type: string,
        all_fields: list
    }
```

---

## 9. Consideraciones para Windows y macOS

### Diferencias de Implementación

#### Sockets y Threading

**Python (cross-platform)**:
```python
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
```

**C# (.NET)**:
```csharp
using System.Net.Sockets;
using System.Threading.Tasks;
```

**Go**:
```go
import (
    "net"
    "sync"
)
```

**Rust**:
```rust
use std::net::TcpStream;
use tokio; // para async
```

### SSL/TLS

**Ignorar Certificados Inválidos**:

```python
# Python
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

```csharp
// C#
ServicePointManager.ServerCertificateValidationCallback = 
    (sender, cert, chain, sslPolicyErrors) => true;
```

```go
// Go
&tls.Config{InsecureSkipVerify: true}
```

### HTML Parsing

**Opciones por Lenguaje**:

| Lenguaje | Librería Recomendada |
|----------|---------------------|
| Python   | html.parser (builtin), BeautifulSoup |
| C#       | HtmlAgilityPack |
| Go       | goquery, golang.org/x/net/html |
| Rust     | scraper, select.rs |
| Node.js  | cheerio, jsdom |

### HTTP Client

**Con Soporte Cookies y Redirects**:

| Lenguaje | Librería |
|----------|----------|
| Python   | urllib.request, requests |
| C#       | HttpClient con CookieContainer |
| Go       | net/http con CookieJar |
| Rust     | reqwest |
| Node.js  | axios, got |

### APIs de AI

**OpenAI**:
- Endpoint: `https://api.openai.com/v1/chat/completions`
- Modelo: `gpt-4o-mini`
- Headers: `Authorization: Bearer {api_key}`

**Anthropic**:
- Endpoint: `https://api.anthropic.com/v1/messages`
- Modelo: `claude-3-haiku-20240307`
- Headers: `x-api-key: {api_key}`, `anthropic-version: 2023-06-01`

### Manejo de CIDR

**Librerías por Lenguaje**:

| Lenguaje | Librería |
|----------|----------|
| Python   | ipaddress (builtin) |
| C#       | System.Net.IPAddress, IPNetwork |
| Go       | net, netip |
| Rust     | ipnetwork, cidr-utils |

---

## Ejemplo de Uso Final

```bash
# Solo escaneo de puertos + screenshots
./scanner --scan 192.168.1.0/24 --scan-ports large -d output/

# Con análisis AI completo
./scanner --scan 10.0.0.1-100 \
    --enable-ai \
    --ai-provider openai \
    --ai-api-key sk-xxx \
    --test-credentials \
    -d output/

# Solo URL específica con AI
./scanner --single http://example.com/login \
    --enable-ai \
    --ai-provider anthropic \
    --test-credentials
```

---

## Archivos de Salida

1. **report.html**: Reporte visual con screenshots y resultados
2. **auth_methods_for_spraying.json**: Métodos de autenticación para password spraying
3. **source/[hash].txt**: Código fuente HTML de cada página
4. **screens/[hash].png**: Screenshots de cada página

---

*Documento generado para reimplementación en otros lenguajes/proyectos.*

