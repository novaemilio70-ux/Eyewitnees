# AI-Powered Credential Analysis for EyeWitness

## Overview

EyeWitness ahora incluye capacidades de análisis con inteligencia artificial para:
1. **Identificar aplicaciones desconocidas** que no están en `signatures.txt`
2. **Buscar credenciales por defecto** usando IA
3. **Analizar formularios de login** automáticamente
4. **Probar credenciales** contra los formularios encontrados
5. **Guardar métodos de autenticación** para password spraying posterior

## Requisitos

### Instalación de Dependencias

Las dependencias de IA son opcionales. Instala una o ambas:

```bash
# Para usar OpenAI (GPT-4, GPT-4o-mini, etc.)
pip install openai>=1.0.0

# Para usar Anthropic (Claude)
pip install anthropic>=0.18.0
```

### Configuración de API Keys

Configura tu API key usando variables de entorno o argumentos de línea de comandos:

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Uso

### Habilitar Análisis con IA

```bash
# Activar virtual environment primero
source eyewitness-venv/bin/activate  # Linux/macOS
eyewitness-venv\Scripts\activate.bat # Windows

# Ejecutar con IA habilitada
python Python/EyeWitness.py -f urls.txt --enable-ai

# Especificar proveedor de IA
python Python/EyeWitness.py -f urls.txt --enable-ai --ai-provider openai

# Especificar API key directamente
python Python/EyeWitness.py -f urls.txt --enable-ai --ai-api-key sk-...
```

### Opciones de IA

```
--enable-ai                    Habilitar análisis con IA
--ai-api-key API_KEY          API key para servicio de IA
--ai-provider {openai,anthropic}  Proveedor de IA a usar
--test-credentials            Probar credenciales encontradas (default: True)
--no-test-credentials         Deshabilitar pruebas de credenciales
--credential-test-timeout SECONDS  Timeout para pruebas (default: 10)
--credential-test-delay SECONDS    Delay entre pruebas (default: 1.0)
```

### Ejemplo Completo

```bash
python Python/EyeWitness.py \
    -f urls.txt \
    --enable-ai \
    --ai-provider openai \
    --test-credentials \
    --credential-test-timeout 15 \
    --credential-test-delay 2.0 \
    -d ./output
```

## Funcionamiento

### 1. Análisis de Aplicaciones

Cuando EyeWitness encuentra una página que **no está en signatures.txt**:

1. **Identificación con IA**: Analiza el HTML para identificar la aplicación
   - Nombre de la aplicación
   - Versión (si está visible)
   - Tipo de aplicación (CMS, CI/CD, etc.)

2. **Búsqueda de Credenciales**: Usa IA para buscar credenciales por defecto conocidas
   - Busca en conocimiento de la IA sobre credenciales comunes
   - Retorna múltiples opciones si están disponibles

### 2. Análisis de Formularios

El sistema analiza automáticamente el HTML para encontrar:

- Formularios de login
- Campos de usuario/contraseña
- Endpoints de autenticación
- Métodos HTTP (POST/GET)
- Tokens CSRF (si están presentes)

### 3. Prueba de Credenciales

Si se encuentran credenciales y formularios:

1. Construye requests HTTP basados en el formulario
2. Prueba cada credencial encontrada
3. Detecta éxito basándose en:
   - Redirecciones
   - Cookies de sesión
   - Cambios en el contenido
   - Códigos de respuesta HTTP

### 4. Almacenamiento para Password Spraying

Al finalizar, se guarda un archivo `auth_methods_for_spraying.json` con:

```json
{
  "WordPress": [
    {
      "url": "http://example.com",
      "endpoint": "/wp-login.php",
      "method": "POST",
      "username_field": "log",
      "password_field": "pwd",
      "auth_type": "form_based",
      "tested": true,
      "has_working_creds": false
    }
  ]
}
```

## Output en el Reporte

El reporte HTML ahora incluye:

### Información de Aplicación Detectada por IA
```
AI-Detected Application: WordPress (Version: 6.4.2)
```

### Credenciales Encontradas por IA
```
AI-Found Credentials:
  - admin:admin
  - admin:password
```

### Resultados de Pruebas
```
Credential Testing:
  - Testable: Yes
  - Tested: Yes
  - Credentials Tested: 2
  - Successful: 1
  - Failed: 1
  Working Credentials:
    - admin:admin
```

## Limitaciones y Consideraciones

### Costos de API

- **OpenAI GPT-4o-mini**: ~$0.15 por 1M tokens de entrada, ~$0.60 por 1M tokens de salida
- **Anthropic Claude Haiku**: ~$0.25 por 1M tokens de entrada, ~$1.25 por 1M tokens de salida

Cada análisis usa aproximadamente:
- 500-2000 tokens para identificación de aplicación
- 500-1000 tokens para búsqueda de credenciales

**Estimación**: ~$0.001-0.005 por URL analizada

### Precisión

- La IA puede identificar aplicaciones comunes con alta precisión
- Las credenciales encontradas son sugerencias basadas en conocimiento público
- Las pruebas de credenciales usan heurísticas y pueden tener falsos positivos/negativos

### Ética y Legalidad

⚠️ **IMPORTANTE**: Solo usa estas funcionalidades en sistemas que:
- Tienes autorización explícita para probar
- Son parte de un programa de bug bounty autorizado
- Son tus propios sistemas

### Rate Limiting

- Las APIs de IA tienen límites de rate
- El sistema incluye delays entre pruebas de credenciales
- Para muchos targets, considera aumentar `--credential-test-delay`

## Troubleshooting

### "AI analyzer not available"

- Verifica que instalaste `openai` o `anthropic`
- Verifica que configuraste la API key
- Revisa que la API key es válida

### "No credentials found"

- La aplicación puede ser muy nueva o poco común
- La IA puede no tener información sobre esa aplicación
- Intenta manualmente con `signatures.txt`

### "Testable: No"

- No se encontró formulario de login
- El formulario no tiene campos de usuario/contraseña identificables
- La página puede usar autenticación diferente (Basic Auth, OAuth, etc.)

### Errores de conexión durante pruebas

- Aumenta `--credential-test-timeout`
- Verifica que el target esté accesible
- Algunos sistemas bloquean intentos de login automáticos

## Ejemplos de Uso

### Solo Identificación (sin pruebas)
```bash
python Python/EyeWitness.py -f urls.txt --enable-ai --no-test-credentials
```

### Análisis Rápido (timeout corto)
```bash
python Python/EyeWitness.py -f urls.txt --enable-ai --credential-test-timeout 5
```

### Análisis Detallado (timeout largo, más delay)
```bash
python Python/EyeWitness.py -f urls.txt \
    --enable-ai \
    --credential-test-timeout 20 \
    --credential-test-delay 3.0
```

## Integración con Password Spraying

El archivo `auth_methods_for_spraying.json` puede ser usado con herramientas como:

- **Hydra**: Para password spraying masivo
- **Burp Suite**: Para pruebas manuales
- **Scripts personalizados**: Usando la estructura JSON

Ejemplo de uso con el JSON:

```python
import json

with open('auth_methods_for_spraying.json') as f:
    auth_methods = json.load(f)

for app_name, methods in auth_methods.items():
    for method in methods:
        print(f"Testing {app_name} at {method['url']}")
        # Usar method['endpoint'], method['username_field'], etc.
```

## Soporte

Para problemas o preguntas:
1. Revisa los logs de EyeWitness
2. Verifica la configuración de API keys
3. Consulta la documentación de OpenAI/Anthropic

