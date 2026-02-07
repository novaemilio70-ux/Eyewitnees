# Requisitos de Instalación para Linux - EyeWitness

## 📋 Resumen Ejecutivo

EyeWitness requiere los siguientes componentes en Linux:
- **Python 3.7+** con módulo `venv`
- **Chromium/Chrome** browser
- **ChromeDriver** para automatización
- **Xvfb** (X Virtual Framebuffer) para operación headless
- **Paquetes del sistema** básicos (wget, curl, etc.)
- **Paquetes Python** (instalados en entorno virtual)

---

## 🔧 Requisitos del Sistema

### 1. Python 3.7 o Superior

**Verificar versión:**
```bash
python3 --version
# Debe mostrar Python 3.7.x o superior
```

**Instalación por distribución:**

#### Ubuntu/Debian/Kali Linux
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-dev
```

#### CentOS/RHEL/Rocky Linux/Fedora
```bash
# Para sistemas con dnf (Fedora, RHEL 8+)
sudo dnf install python3 python3-venv python3-pip python3-devel

# Para sistemas con yum (RHEL 7, CentOS 7)
sudo yum install python3 python3-venv python3-pip python3-devel
```

#### Arch Linux/Manjaro
```bash
sudo pacman -S python python-pip
```

#### Alpine Linux
```bash
sudo apk add python3 py3-pip python3-dev
```

**Verificar módulo venv:**
```bash
python3 -m venv --help
# Debe mostrar ayuda sin errores
```

---

### 2. Navegador Chromium/Chrome

EyeWitness usa Chromium para capturar pantallas. Se requiere uno de estos navegadores:

#### Ubuntu/Debian/Kali Linux
```bash
sudo apt install chromium-browser chromium-chromedriver
# O alternativamente:
sudo apt install chromium chromium-driver
```

#### CentOS/RHEL/Rocky Linux/Fedora
```bash
sudo dnf install chromium chromedriver
# O con yum:
sudo yum install chromium chromedriver
```

#### Arch Linux/Manjaro
```bash
sudo pacman -S chromium
# ChromeDriver puede necesitarse desde AUR:
yay -S chromedriver
```

#### Alpine Linux
```bash
sudo apk add chromium chromium-chromedriver
```

**Verificar instalación:**
```bash
chromium-browser --version
# O
chromium --version
```

---

### 3. ChromeDriver

ChromeDriver es necesario para que Selenium controle el navegador.

**Ubuntu/Debian/Kali:**
```bash
sudo apt install chromium-chromedriver
```

**Verificar:**
```bash
chromedriver --version
# O
chromium-chromedriver --version
```

**Nota:** En algunas distribuciones, ChromeDriver viene con Chromium. Si no está disponible, puedes descargarlo manualmente desde: https://chromedriver.chromium.org/

---

### 4. Xvfb (X Virtual Framebuffer)

Xvfb permite ejecutar aplicaciones gráficas sin pantalla física (headless).

#### Ubuntu/Debian/Kali Linux
```bash
sudo apt install xvfb
```

#### CentOS/RHEL/Rocky Linux/Fedora
```bash
sudo dnf install xorg-x11-server-Xvfb
# O con yum:
sudo yum install xorg-x11-server-Xvfb
```

#### Arch Linux/Manjaro
```bash
sudo pacman -S xorg-server-xvfb
```

#### Alpine Linux
```bash
sudo apk add xvfb
```

**Verificar:**
```bash
Xvfb --version
```

---

### 5. Paquetes del Sistema Básicos

Estos paquetes son instalados automáticamente por el script de setup:

#### Ubuntu/Debian/Kali Linux
```bash
sudo apt install wget curl jq cmake
```

#### CentOS/RHEL/Rocky Linux/Fedora
```bash
sudo dnf install wget curl jq cmake
# O con yum:
sudo yum install wget curl jq cmake
```

#### Arch Linux/Manjaro
```bash
sudo pacman -S wget curl jq cmake
```

#### Alpine Linux
```bash
sudo apk add wget curl jq cmake
```

---

## 📦 Paquetes Python (Instalados en Entorno Virtual)

Estos paquetes se instalan automáticamente en un entorno virtual Python (`eyewitness-venv/`):

### Paquetes Core (Requeridos)

| Paquete | Versión Mínima | Propósito |
|---------|---------------|-----------|
| `selenium` | >=4.29.0 | Automatización del navegador |
| `netaddr` | >=0.10.0 | Manipulación de direcciones de red |
| `psutil` | >=5.9.0 | Monitoreo de recursos del sistema |
| `rapidfuzz` | >=3.0.0 | Comparación de cadenas (reemplazo de fuzzywuzzy) |
| `pyvirtualdisplay` | >=3.0 | Soporte para display virtual (solo Linux/macOS) |
| `argcomplete` | >=2.0.0 | Autocompletado en línea de comandos |
| `requests` | >=2.28.0 | Cliente HTTP |
| `urllib3` | >=1.26.0 | Biblioteca HTTP |

### Paquetes Opcionales (IA)

| Paquete | Versión Mínima | Propósito |
|---------|---------------|-----------|
| `openai` | >=1.0.0 | Análisis con OpenAI GPT (opcional) |
| `anthropic` | >=0.18.0 | Análisis con Anthropic Claude (opcional) |

**Nota:** Los paquetes de IA son opcionales y solo se necesitan si usas `--enable-ai`.

---

## 🚀 Instalación Automática (Recomendada)

El script `setup.sh` instala todo automáticamente:

```bash
cd EyeWitness/setup
sudo ./setup.sh
```

**Lo que hace el script:**
1. ✅ Detecta tu distribución Linux
2. ✅ Instala paquetes del sistema necesarios
3. ✅ Crea entorno virtual Python (`eyewitness-venv/`)
4. ✅ Instala paquetes Python en el entorno virtual
5. ✅ Verifica la instalación

---

## 📝 Instalación Manual (Paso a Paso)

Si prefieres instalar manualmente:

### Paso 1: Instalar Python y herramientas básicas

```bash
# Ubuntu/Debian/Kali
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-dev

# CentOS/RHEL/Fedora
sudo dnf install python3 python3-venv python3-pip python3-devel

# Arch/Manjaro
sudo pacman -S python python-pip
```

### Paso 2: Instalar Chromium y ChromeDriver

```bash
# Ubuntu/Debian/Kali
sudo apt install chromium-browser chromium-chromedriver

# CentOS/RHEL/Fedora
sudo dnf install chromium chromedriver

# Arch/Manjaro
sudo pacman -S chromium
yay -S chromedriver  # Desde AUR
```

### Paso 3: Instalar Xvfb

```bash
# Ubuntu/Debian/Kali
sudo apt install xvfb

# CentOS/RHEL/Fedora
sudo dnf install xorg-x11-server-Xvfb

# Arch/Manjaro
sudo pacman -S xorg-server-xvfb
```

### Paso 4: Crear entorno virtual

```bash
cd EyeWitness
python3 -m venv eyewitness-venv
source eyewitness-venv/bin/activate
```

### Paso 5: Instalar paquetes Python

```bash
pip install --upgrade pip
pip install -r setup/requirements.txt
```

### Paso 6: Verificar instalación

```bash
python Python/EyeWitness.py --help
```

---

## ✅ Verificación de Requisitos

Puedes verificar que todo esté instalado correctamente:

```bash
# Verificar Python
python3 --version  # Debe ser 3.7+

# Verificar Chromium
chromium-browser --version  # O chromium --version

# Verificar ChromeDriver
chromedriver --version

# Verificar Xvfb
Xvfb --version

# Verificar entorno virtual
source eyewitness-venv/bin/activate
python -c "import selenium; print('✓ selenium')"
python -c "import netaddr; print('✓ netaddr')"
python -c "import psutil; print('✓ psutil')"
python -c "import pyvirtualdisplay; print('✓ pyvirtualdisplay')"
```

---

## 🎯 Requisitos Mínimos del Sistema

### Hardware
- **RAM**: Mínimo 2GB (recomendado 4GB+)
- **Disco**: ~500MB para instalación base
- **CPU**: Cualquier procesador moderno

### Software
- **OS**: Linux (Ubuntu 20.04+, Debian 10+, Kali, CentOS 8+, RHEL 8+, Fedora, Arch, Alpine)
- **Python**: 3.7 o superior
- **Kernel**: Linux 5.x o superior (recomendado)

---

## 🔍 Distribuciones Soportadas

El script de setup detecta y soporta:

| Distribución | Versiones Soportadas | Gestor de Paquetes |
|--------------|---------------------|-------------------|
| Ubuntu | 20.04+ | apt |
| Debian | 10+ | apt |
| Kali Linux | Todas | apt |
| Linux Mint | 20+ | apt |
| CentOS | 8+ | dnf/yum |
| RHEL | 8+ | dnf/yum |
| Rocky Linux | 8+ | dnf |
| Fedora | 30+ | dnf |
| Arch Linux | Todas | pacman |
| Manjaro | Todas | pacman |
| Alpine Linux | 3.15+ | apk |

---

## 🐛 Troubleshooting

### Error: "Python 3.7+ required"
```bash
# Verificar versión
python3 --version

# Si es menor a 3.7, actualizar:
# Ubuntu/Debian
sudo apt install python3.9 python3.9-venv python3.9-pip

# Usar python3.9 en lugar de python3
```

### Error: "chromium-browser not found"
```bash
# Intentar nombres alternativos
sudo apt install chromium chromium-driver

# O instalar Google Chrome manualmente
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
```

### Error: "ChromeDriver not found"
```bash
# Descargar manualmente
CHROME_VERSION=$(chromium-browser --version | grep -oP '\d+\.\d+\.\d+')
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}
# O usar la versión más reciente
wget https://chromedriver.storage.googleapis.com/LATEST_RELEASE
```

### Error: "Xvfb not found"
```bash
# Instalar según distribución
sudo apt install xvfb        # Ubuntu/Debian
sudo dnf install xorg-x11-server-Xvfb  # CentOS/RHEL/Fedora
```

### Error: "venv module not found"
```bash
# Instalar python3-venv
sudo apt install python3-venv  # Ubuntu/Debian
sudo dnf install python3-venv   # CentOS/RHEL/Fedora
```

---

## 📚 Referencias

- **Python venv**: https://docs.python.org/3/library/venv.html
- **Selenium**: https://www.selenium.dev/
- **ChromeDriver**: https://chromedriver.chromium.org/
- **Xvfb**: https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml

---

## 🎓 Resumen Rápido

**Para la mayoría de usuarios en Ubuntu/Debian/Kali:**

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip python3-dev \
                chromium-browser chromium-chromedriver xvfb \
                wget curl jq cmake

cd EyeWitness/setup
sudo ./setup.sh
```

**Para CentOS/RHEL/Fedora:**

```bash
sudo dnf install python3 python3-venv python3-pip python3-devel \
                chromium chromedriver xorg-x11-server-Xvfb \
                wget curl jq cmake

cd EyeWitness/setup
sudo ./setup.sh
```

¡Eso es todo! El script se encarga del resto automáticamente.

