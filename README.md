# Erome Scraper PRO 🚀

A high-performance, asynchronous web application designed to scrape and download media from Erome albums with precision and speed.

![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.110%2B-green.svg)

## ✨ Features

- **🚀 Concurrent Downloads**: Multi-threaded, asynchronous file streaming for maximum throughput.
- **📊 Real-time Progress**: Interactive Web Dashboard with live progress bars, speed indicators, and status updates.
- **💾 Persistent Queue**: Automatically saves your download state. Resumes pending downloads upon restart.
- **🛡️ Integrity Protection**: Automatic cleanup of partial/corrupted files and robust error handling.
- **🎨 Cyberpunk Stealth UI**: A premium, dark-themed user interface designed for focus and efficiency.
- **📂 Smart Organization**: Automatically creates album-specific subdirectories for organized media storage.

## 🛠️ Tech Stack

- **Backend**: Python 3.12+, FastAPI, Asyncio.
- **Networking**: `httpx` for high-performance streaming.
- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), JavaScript (ES6+).
- **Persistence**: JSON-based state management for lightweight reliability.

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher.
- `pip` or `uv` for dependency management.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/latinokodi/eromescraper.git
   cd eromescraper
   ```

2. **Set up a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

Start the FastAPI server:

```bash
python -m src.main
```

The application will be available at `http://127.0.0.1:8000`.

## 📖 Usage

1. Open your browser and navigate to the dashboard.
2. Paste the Erome album URL into the input field.
3. Click "Sync Album" to begin the extraction and download process.
4. Monitor individual file progress and global statistics in real-time.

## 🤝 Contributing

Contributions are welcome! If you have suggestions for new features or improvements, feel free to open an issue or submit a pull request.

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

---
*Built with ❤️ for the high-volume media community.*
