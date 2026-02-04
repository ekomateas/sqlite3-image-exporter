# sqlite3-image-exporter

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey)

A clean, deterministic, forensic-friendly tool for exporting images stored as BLOBs inside a SQLite3 database.  
Supports automatic format detection, optional JPEG conversion, corrupt image detection, progress bar, dry-run mode, force overwrite, logging, and configurable limits.

Designed for reliability, clarity, and reproducibility.

---

## Features

- Extract images from any SQLite3 table containing BLOB image data  
- Detect image format via magic bytes  
- Optional conversion of all non-JPEG images to JPEG (default)  
- Optional preservation of original image format (--keep-image-format)  
- Detect corrupt images safely using Pillow  
- Skip existing files or overwrite them (--force)  
- Dry-run mode (--dry-run) for safe preview  
- Optional logging (--keep-log)  
- Progress bar via tqdm  
- Limit number of exported images (--limit N)  
- Clean configuration via config.py

---

## Installation

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python3 exporter.py [options]
```

### Options

--force  
    Overwrite existing files

--dry-run  
    Simulate actions without writing files

--keep-log  
    Save a draft log to export_log.txt

--keep-image-format  
    Do not convert images to JPEG

--limit N  
    Export only the first N images

--help
    See all available options.

---

## Configuration

All constants live in config.py:

```python
DB_PATH = "/path/to/database.db"

DB_TABLE = "Images"
DB_FIELD_KEY = "Key"
DB_FIELD_TIMESTAMP = "Timestamp"
DB_FIELD_IMAGE = "Image"

TARGET_DIRECTORY_PATH = "./Pictures"
LOG_PATH = "./export_log.txt"
```

Modify this file to match your database schema and desired output directory.

---

## Examples

Export all images, converting everything to JPEG:

```bash
python3 exporter.py
```

Export only 100 images, preserving original formats:

```bash
python3 exporter.py --limit 100 --keep-image-format
```

Dry-run preview:

```bash
python3 exporter.py --dry-run
```

Force overwrite:

```bash
python3 exporter.py --force
```

---

## License

MIT License — see LICENSE file.

---

## Contributing

Pull requests are welcome.  
If you have ideas for new features (parallel extraction, JSON logging, plugin architecture), feel free to open an issue.

---

## Author

Created by Εὐθύμιος Komateas with a focus on clarity, reproducibility, and technical elegance.
