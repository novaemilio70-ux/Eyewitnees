# Bug Fix: Aplicaciones con nombre "10"

## 🐛 Problema Identificado

En el proyecto `laboon`, varias URLs mostraban "10" como nombre de aplicación en la columna "Aplicación":

### URLs Afectadas:
- `http://10.228.153.132:8080/`
- `http://10.228.153.194:8080/`
- `http://10.228.153.21:8080/`
- `http://10.228.34.175/`
- `http://10.228.20.57:8083`
- `https://10.228.48.62/`
- `https://10.228.20.38:8443/`

### Causa Raíz:

El backend (`webapp/backend/main.py`) tenía una lógica de 4 prioridades para extraer el nombre de la aplicación:

1. **Prioridad 1**: Información de AI (`ai_application_info`)
2. **Prioridad 2**: Credenciales por defecto (`default_creds`)
3. **Prioridad 3**: Título de página (`page_title`)
4. **Prioridad 4**: Extraer del hostname de la URL ❌ **BUG AQUÍ**

Para las URLs afectadas:
- ✗ NO tenían `page_title` (vacío o `None`)
- ✗ NO tenían `default_creds` detectadas
- ✗ NO tenían `ai_application_info`
- ✗ El código intentaba extraer el nombre del hostname

**El problema**: 
```python
# Código BUGGY (antes del fix)
hostname = parsed.hostname  # Para "10.228.153.132" → hostname = "10.228.153.132"
parts = hostname.split('.')  # parts = ['10', '228', '153', '132']
app_name = parts[0]  # app_name = "10" ❌
```

Para direcciones IP como `10.228.153.132`, al hacer `split('.')`, tomaba el primer octeto `'10'` como nombre de aplicación.

---

## ✅ Solución Implementada

### Cambios en `webapp/backend/main.py`:

#### 1. Nueva función auxiliar para detectar IPs:

```python
def is_ip_address(hostname: str) -> bool:
    """Check if a hostname is an IP address (IPv4 or IPv6)"""
    if not hostname:
        return False
    # IPv4 check
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
        return True
    # IPv6 check (simple)
    if ':' in hostname and not hostname.startswith('['):
        return True
    return False
```

#### 2. Modificación de la lógica de Prioridad 4:

```python
# Priority 4: Try to extract from URL hostname (but not for IP addresses)
if not app_name and obj.remote_system:
    from urllib.parse import urlparse
    parsed = urlparse(obj.remote_system)
    hostname = parsed.hostname or parsed.netloc
    # Only extract from hostname if it's NOT an IP address
    if hostname and not is_ip_address(hostname) and hostname not in ['localhost']:
        parts = hostname.split('.')
        if parts and parts[0]:
            app_name = parts[0].replace('-', ' ').replace('_', ' ').title()
```

**Resultado**:
- ✅ Para IPs como `10.228.153.132`: `app_name = None`
- ✅ Para hostnames reales como `myserver.example.com`: `app_name = "Myserver"` (funciona correctamente)

---

## 🧪 Pruebas Realizadas

### Test 1: Reproducción del Bug
```bash
python3 debug_app_names.py
```

**Resultado**: Confirmado que las URLs problemáticas tenían:
- `page_title: ''` (vacío)
- `category: 'appserver'` o `'webserver'` o `None`
- `default_creds: None`
- `ai_application_info: None`

### Test 2: Verificación del Fix
```bash
python3 test_fix_with_simulation.py
```

**Resultado**: ✅ **ALL TESTS PASSED**
- Las IPs ahora retornan `app_name = None` (no "10")
- Los hostnames reales siguen funcionando correctamente
- El frontend maneja `None` correctamente mostrando "Unknown"

---

## 📊 Comportamiento Antes vs Después

| Escenario | ANTES (bug) | DESPUÉS (fix) |
|-----------|-------------|---------------|
| `http://10.228.153.132:8080/` (sin title) | "10" ❌ | `None` → "Unknown" ✅ |
| `http://example.com/` (sin title) | "Example" ✅ | "Example" ✅ |
| `http://example.com/` (con title) | [título] ✅ | [título] ✅ |
| `http://example.com/` (con creds) | [app de creds] ✅ | [app de creds] ✅ |

---

## 🎯 Impacto de la Solución

### ✅ Lo que SE PREVIENE:
- **Futuros escaneos**: No aparecerá "10" como nombre de aplicación para IPs
- **Consistencia**: El comportamiento es predecible y correcto
- **Robustez**: El código valida que el hostname no sea una IP antes de extraer nombres

### ⚠️ Lo que NO se modifica:
- **Datos existentes**: Los datos ya capturados en el proyecto `laboon` NO se modifican automáticamente
- **Base de datos**: La base de datos `laboon.db` conserva los datos originales tal como fueron capturados

### 🔄 Para corregir datos existentes:
Si deseas corregir los datos existentes en el proyecto `laboon`:

**Opción 1**: Re-escanear las URLs problemáticas
```bash
python3 Python/EyeWitness.py -f urls_problematicas.txt --db laboon --timeout 15
```

**Opción 2**: Script manual de corrección de base de datos (a crear si es necesario)

---

## 🔍 Frontend - Manejo de `app_name = None`

El frontend ya maneja correctamente cuando `app_name` es `None` o `undefined`:

### Gallery.tsx (línea 206):
```typescript
<span className="text-xs text-slate-300">
  {report.application || 'Unknown'}
</span>
```

### Reports.tsx (línea 302):
```typescript
<td className="py-3 px-4 text-white">
  {report.application || 'Unknown'}
</td>
```

**Resultado visual**: Se mostrará "Unknown" en lugar de un campo vacío o "10".

---

## 📝 Archivos Modificados

1. **`webapp/backend/main.py`**:
   - Agregada función `is_ip_address()`
   - Modificada lógica de extracción de nombre de aplicación (2 ubicaciones)

---

## 🚀 Recomendaciones

1. **Probar el webapp**: Iniciar el webapp y verificar que la columna "Aplicación" muestra correctamente:
   ```bash
   cd webapp && ./start.sh
   ```

2. **Re-escanear selectivamente**: Si es importante corregir los datos del proyecto `laboon`, crear un archivo con solo las URLs problemáticas y re-escanearlas.

3. **Monitoreo futuro**: En futuros escaneos, verificar que ninguna aplicación aparezca con nombres numéricos sospechosos.

---

## ✅ Conclusión

**El bug ha sido corregido exitosamente**:
- ✅ La causa raíz fue identificada
- ✅ Se implementó una solución robusta
- ✅ Se verificó con pruebas automatizadas
- ✅ El frontend ya manejaba correctamente los valores `None`
- ✅ **PREVENCIÓN**: En futuros escaneos NO aparecerá "10" como nombre de aplicación

**La solución es preventiva** - evita que el problema ocurra en el futuro, pero no modifica automáticamente los datos ya existentes en la base de datos del proyecto `laboon`.

