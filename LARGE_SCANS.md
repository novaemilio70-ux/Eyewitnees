# Guía para Scans Grandes (500+ URLs)

## 🔴 Problema Común

Con scans de 900+ URLs usando `--test-credentials`, el sistema puede quedarse sin recursos:
- **Error**: `Resource temporarily unavailable` (código 11)
- **Error**: `Chrome instance exited`
- **Causa**: Demasiadas instancias de Chrome/Selenium abiertas simultáneamente

## ✅ Soluciones Implementadas (v1.1)

1. **Retry Logic**: 3 intentos automáticos si falla Chrome
2. **Health Check**: Verifica que el driver esté vivo antes de reusar
3. **Zombie Cleanup**: Limpia procesos Chrome huérfanos
4. **Memory Reduction**: Flags adicionales para reducir uso de memoria
5. **Graceful Degradation**: Continúa con otras URLs si una falla

## 🚀 Mejores Prácticas para Scans Grandes

### Opción 1: Reducir Threads (Recomendado)

```bash
# Para 900 URLs, usa solo 1-2 threads
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --enable-ai \
  --test-credentials \
  --db laboon \
  --threads 1 \
  --no-auto-open
```

**Ventajas:**
- ✅ Menos uso de memoria
- ✅ Más estable
- ✅ Mejor para debugging
- ❌ Más lento (pero más confiable)

### Opción 2: Dividir el Scan

```bash
# Dividir urls.txt en chunks de 100 URLs
split -l 100 urls.txt urls_chunk_

# Ejecutar por chunks
for chunk in urls_chunk_*; do
    python3 Python/EyeWitness.py -f $chunk \
      --web \
      --enable-ai \
      --test-credentials \
      --db laboon \
      --threads 2
    
    # Pequeña pausa entre chunks para liberar recursos
    sleep 10
done
```

**Ventajas:**
- ✅ Más control
- ✅ Puede pausar/reanudar
- ✅ Menos riesgo de crash
- ✅ Usa la misma DB (actualiza en lugar de duplicar)

### Opción 3: Sin Test de Credenciales Automático

```bash
# Primero: Solo captura y AI
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --enable-ai \
  --db laboon \
  --threads 4 \
  --no-auto-open

# Después: Prueba credenciales manualmente en URLs específicas
python3 Python/EyeWitness.py --single https://target.com \
  --test-credentials \
  --db laboon
```

**Ventajas:**
- ✅ Mucho más rápido para el scan inicial
- ✅ Menos recursos
- ✅ Puedes priorizar targets interesantes

### Opción 4: Aumentar Límites del Sistema

```bash
# Aumentar límites de procesos (temporal)
ulimit -u 4096
ulimit -n 4096

# Luego ejecutar el scan
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --enable-ai \
  --test-credentials \
  --db laboon \
  --threads 2
```

## 📊 Recursos Recomendados por Tamaño de Scan

| URLs  | Threads | RAM Recomendada | Tiempo Estimado |
|-------|---------|-----------------|-----------------|
| <100  | 3-5     | 4GB             | 10-30 min       |
| 100-300 | 2-3   | 8GB             | 1-2 hrs         |
| 300-600 | 1-2   | 8GB             | 2-4 hrs         |
| 600+  | 1       | 16GB            | 4-8 hrs         |

## 🔍 Monitoreo Durante el Scan

```bash
# Terminal 1: Ejecutar scan
python3 Python/EyeWitness.py -f urls.txt --db laboon --threads 1 --enable-ai --test-credentials

# Terminal 2: Monitorear recursos
watch -n 5 'ps aux | grep -E "(chrome|python)" | wc -l && free -h'

# Terminal 3: Ver progreso
tail -f eyewitness_projects/laboon/*.log 2>/dev/null || echo "No log yet"
```

## 🛠️ Troubleshooting

### Si el scan se detiene:

```bash
# 1. Matar procesos Chrome zombies
pkill -9 chrome
pkill -9 chromedriver

# 2. Verificar cuántas URLs ya se procesaron
sqlite3 eyewitness_projects/laboon/laboon.db "SELECT COUNT(*) FROM http;"

# 3. Crear lista de URLs pendientes
# (Comparar urls.txt con las ya procesadas en la DB)

# 4. Continuar con las pendientes
python3 Python/EyeWitness.py -f urls_remaining.txt --db laboon --threads 1
```

### Si hay errores de memoria:

```bash
# Verificar memoria disponible
free -h

# Limpiar caché
sync; echo 3 > /proc/sys/vm/drop_caches

# Cerrar aplicaciones innecesarias
```

## 📈 Optimización de Performance

### Para Máxima Velocidad (sin credenciales):
```bash
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --db laboon \
  --threads 8 \
  --no-auto-open
```

### Para Máxima Estabilidad (con credenciales):
```bash
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --enable-ai \
  --test-credentials \
  --db laboon \
  --threads 1 \
  --timeout 60 \
  --no-auto-open
```

## 🎯 Recomendación Final

Para tu scan de **902 URLs** con `--test-credentials`:

```bash
# Opción A: Todo de una vez (lento pero seguro)
python3 Python/EyeWitness.py -f urls.txt \
  --web \
  --enable-ai \
  --test-credentials \
  --db laboon \
  --threads 1 \
  --no-auto-open

# Opción B: Por chunks (más control)
split -l 150 urls.txt urls_chunk_
for chunk in urls_chunk_*; do
    echo "Processing $chunk..."
    python3 Python/EyeWitness.py -f $chunk \
      --web --enable-ai --test-credentials \
      --db laboon --threads 1
    sleep 5
done
```

## 📝 Notas

- El flag `--db laboon` asegura que todos los chunks actualicen la misma base de datos
- Con `--threads 1`, el scan es más lento pero mucho más estable
- Los errores de Chrome ahora se recuperan automáticamente (3 intentos)
- Si falla un URL, el scan continúa con los siguientes

