# Erome Scraper PRO 🚀

Una aplicación web asíncrona de alto rendimiento diseñada para extraer y descargar contenido multimedia de álbumes de Erome con precisión y velocidad.

![Versión](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.110%2B-green.svg)

## ✨ Características

- **🚀 Descargas Concurrentes**: Transmisión de archivos asíncrona y multi-hilo para un rendimiento máximo.
- **📊 Progreso en Tiempo Real**: Panel de control web interactivo con barras de progreso en vivo, indicadores de velocidad y actualizaciones de estado.
- **💾 Cola Persistente**: Guarda automáticamente el estado de tus descargas. Reanuda las tareas pendientes al reiniciar la aplicación.
- **🛡️ Protección de Integridad**: Limpieza automática de archivos parciales o dañados y manejo de errores robusto.
- **🎨 Interfaz Cyberpunk Stealth**: Una interfaz de usuario premium con tema oscuro, diseñada para la eficiencia.
- **📂 Organización Inteligente**: Crea automáticamente subdirectorios por álbum para mantener tu biblioteca organizada.

## 🛠️ Stack Tecnológico

- **Backend**: Python 3.12+, FastAPI, Asyncio.
- **Networking**: `httpx` para transmisión de alto rendimiento.
- **Frontend**: HTML5 puro, CSS3 (Glassmorphism), JavaScript (ES6+).
- **Persistencia**: Gestión de estado basada en JSON para una confiabilidad ligera.

## 🚀 Inicio Rápido

### Requisitos Previos

- Windows OS (para usar el script de inicio rápido).
- Python 3.12 o superior instalado.

### Instalación y Ejecución

La forma más sencilla de iniciar la aplicación es utilizando el archivo por lotes incluido, que configurará automáticamente el entorno virtual e instalará las dependencias necesarias.

1. **Clona el repositorio**:
   ```bash
   git clone https://github.com/latinokodi/eromescraper.git
   cd eromescraper
   ```

2. **Ejecuta la Aplicación**:
   Simplemente haz doble clic en el archivo `run.bat` o ejecútalo desde la terminal:
   ```cmd
   run.bat
   ```

   *Este script se encargará de crear el entorno virtual, instalar las dependencias y lanzar el servidor.*

### Acceso a la Interfaz

Una vez que el servidor esté en funcionamiento, abre tu navegador y dirígete a:
`http://127.0.0.1:8000`

## 📖 Uso

1. Abre el panel de control en tu navegador.
2. Pega la URL del álbum de Erome en el campo de entrada.
3. Haz clic en "Sync Album" (Sincronizar Álbum) para iniciar la extracción y descarga.
4. Monitorea el progreso de cada archivo y las estadísticas globales en tiempo real.

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Si tienes sugerencias para nuevas funciones o mejoras, no dudes en abrir un "issue" o enviar una solicitud de extracción (pull request).

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.

---
*Desarrollado con ❤️ para la comunidad de gestión de medios de alto volumen.*
