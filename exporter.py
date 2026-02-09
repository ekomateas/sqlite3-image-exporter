#!/usr/local/bin/python3.14
"""
sqlite3-image-exporter

A deterministic, forensic-friendly tool for exporting images stored as BLOBs
inside a SQLite3 database. Supports automatic format detection, optional JPEG
conversion, corrupt image detection, progress bar, dry-run mode, force overwrite,
optional logging, configurable limits, and clean configuration via config.py.

Usage:
    python3 exporter.py [options]

Run with --help to see all available options.
"""

import os
import re
import sqlite3
import argparse
import hashlib
import imagehash
from io import BytesIO
from PIL import Image

import config

from version import __version__

from collections import defaultdict
from typing import Optional, Dict, List


class ImageData:
    """
    Unified representation of an image, backed either by a filesystem path
    or by raw bytes. Lazily computes md5 hash and perceptual hash (phash).
    """

    def __init__(self, path: Optional[str] = None, data: Optional[bytes] = None):
        if path is None and data is None:
            raise ValueError("Either 'path' or 'data' must be provided")

        self.path = path
        self.data = data

        if path:
            self.size = os.path.getsize(path)
        else:
            self.size = len(data)

        self._hash = None
        self._phash = None

    @property
    def hash(self) -> str:
        """MD5 hash of the image bytes."""
        if self._hash is None:
            h = hashlib.new("md5")
            if self.path:
                with open(self.path, "rb") as f:
                    h.update(f.read())
            else:
                h.update(self.data)
            self._hash = h.hexdigest()
        return self._hash

    @property
    def phash(self) -> str:
        """Perceptual hash of the image."""
        if self._phash is None:
            if self.path:
                img = Image.open(self.path)
            else:
                img = Image.open(BytesIO(self.data))
            self._phash = str(imagehash.phash(img))
        return self._phash


class ImageExistsChecker:
    """
    Loads all images from a directory and allows fast existence checks
    by filename, size, md5 hash, or perceptual hash.
    """

    def __init__(self, directory: str):
        self.directory = directory
        self._paths = set()
        self._sizes = set()
        self._images_by_size: Dict[int, List[ImageData]] = defaultdict(list)

    def load_images(self):
        """Load all images from the directory into memory."""
        for fname in os.listdir(self.directory):
            path = os.path.join(self.directory, fname)
            if not os.path.isfile(path):
                continue

            img = ImageData(path=path)
            self._paths.add(path)
            self._sizes.add(img.size)
            self._images_by_size[img.size].append(img)

    # ------------------------------------------------------------
    # Internal shared logic
    # ------------------------------------------------------------
    def _exists_candidate(self, candidate: ImageData, phash: bool = False) -> bool:
        """Shared logic for checking existence by path or by data."""

        # 1. Path match (only if candidate has a path)
        if candidate.path and candidate.path in self._paths:
            return True

        # 2. Size mismatch → impossible match
        if candidate.size not in self._sizes:
            return False

        # 3. Compare with same-size images
        same_size = self._images_by_size[candidate.size]

        if phash:
            c_phash = candidate.phash
            for img in same_size:
                if img.phash == c_phash:
                    return True
        else:
            c_hash = candidate.hash
            for img in same_size:
                if img.hash == c_hash:
                    return True

        return False

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def exists(self, path: str, phash: bool = False) -> bool:
        """Check if an image exists on disk by comparing with a file path."""
        candidate = ImageData(path=path)
        return self._exists_candidate(candidate, phash=phash)

    def exists_by_data(self, data: bytes, phash: bool = False) -> bool:
        """Check if an image exists on disk by comparing raw bytes."""
        candidate = ImageData(data=data)
        return self._exists_candidate(candidate, phash=phash)
    
    @property
    def count(self):
        return sum(len(v) for v in self._images_by_size.values())
    

    def add_image(self, path: str):
        """Register a newly written image so future duplicate checks see it."""
        img = ImageData(path=path)
        self._paths.add(path)
        self._sizes.add(img.size)
        self._images_by_size[img.size].append(img)



    
def sanitize_key(key: str) -> str:
    key = key.strip()
    key = key.replace("/", "-").replace("\\", "-")
    key = re.sub(r"[^\w._-]+", "_", key, flags=re.UNICODE)
    return key



def detect_image_extension(data: bytes) -> str:
    if data.startswith(b"\xFF\xD8\xFF"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[8:16]:
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    return ".bin"


def is_corrupt_image(data: bytes) -> bool:
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        return False
    except Exception:
        return True


def convert_to_jpeg(image_data: bytes) -> bytes:
    with Image.open(BytesIO(image_data)) as img:
        img.load()
        rgb = img.convert("RGB")
        out = BytesIO()
        rgb.save(out, format="JPEG", quality=95)
        return out.getvalue()


def export_images(force=False, dry_run=False, keep_log=False,
                  keep_image_format=False, limit=None):

    os.makedirs(config.TARGET_DIRECTORY_PATH, exist_ok=True)

    # Logging
    log_lines = []
    def log(msg):
        print(msg)
        if keep_log:
            log_lines.append(msg)

    # DB connection
    conn = sqlite3.connect(config.DB_PATH)
    conn.create_collation("UNICODE", lambda a, b: (a > b) - (a < b))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Count total images
    cur.execute(f"SELECT COUNT(*) FROM {config.DB_TABLE}")
    total_in_db = cur.fetchone()[0]

    # Query only non-null images
    query = f"""
        SELECT {config.DB_FIELD_KEY}, {config.DB_FIELD_IMAGE}
        FROM {config.DB_TABLE}
        WHERE {config.DB_FIELD_IMAGE} IS NOT NULL
        ORDER BY {config.DB_FIELD_TIMESTAMP} ASC
    """

    rows = list(cur.execute(query))
    conn.close()

    corrupt_count = 0
    exported_count = 0
    skipped_existing = 0

    log(f"Found {len(rows)} non-null images in DB")

    # Apply limit
    if limit is not None:
        rows = rows[:limit]

    iec = ImageExistsChecker(config.TARGET_DIRECTORY_PATH)
    iec.load_images()

    for row in rows:
        raw_key = row[config.DB_FIELD_KEY]
        key = sanitize_key(raw_key)
        image_data = row[config.DB_FIELD_IMAGE]

        # Corrupt detection
        if is_corrupt_image(image_data):
            log(f"Corrupt image: {raw_key}")
            corrupt_count += 1
            continue

        ext = detect_image_extension(image_data)
        filename = f"{key}{ext if keep_image_format else '.jpg'}"
        filepath = os.path.join(config.TARGET_DIRECTORY_PATH, filename)

        # Existing file logic (filename or content match)
        if not force:
            # 1. Filename match
            if os.path.exists(filepath):
                skipped_existing += 1
                log(f"Skipped existing (filename): {filepath}")
                continue

            # 2. Content match (md5 or phash)
            if iec.exists_by_data(image_data, phash=False):
                skipped_existing += 1
                log(f"Skipped existing (content match): {raw_key}")
                continue


        # Convert if needed
        if not keep_image_format and ext != ".jpg":
            try:
                image_data = convert_to_jpeg(image_data)
                log(f"Converted {raw_key} ({ext}) → JPEG")
            except Exception as e:
                log(f"Failed to convert {raw_key}: {e}")
                corrupt_count += 1
                continue

        # Dry-run mode
        if dry_run:
            log(f"[DRY-RUN] Would export: {filepath}")
            exported_count += 1
            continue

        # Write file
        with open(filepath, "wb") as f:
            f.write(image_data)

        iec.add_image(filepath)
        exported_count += 1

    # Write log if needed
    if keep_log:
        with open(config.LOG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))

    # Summary
    print("\n===== SUMMARY =====")
    print(f"Total images in DB:      {total_in_db}")
    print(f"Non-null images:         {len(rows)}")
    print(f"Images on disk before export: {iec.count}")
    print(f"Corrupt images skipped:  {corrupt_count}")
    print(f"Existing skipped:        {skipped_existing}")
    print(f"New images exported:     {exported_count}")
    print("====================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="sqlite3-image-exporter",
        description=(
            "Export images stored as BLOBs inside a SQLite3 database.\n"
            "Automatically detects image format, optionally converts to JPEG, "
            "detects corrupt images, supports dry-run mode, force overwrite, "
            "logging, and configurable limits."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files instead of skipping them."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate actions without writing any files."
    )

    parser.add_argument(
        "--keep-log",
        action="store_true",
        help="Save a draft log of all actions to export_log.txt."
    )

    parser.add_argument(
        "--keep-image-format",
        action="store_true",
        help="Preserve original image format instead of converting to JPEG."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit the number of images to export."
    )
    
    parser.add_argument(
        "--version", 
        action="store_true"
    )

    args = parser.parse_args()

    if args.version: 
        print(f"sqlite3-image-exporter v{__version__}")
        exit(0)

    export_images(
        force=args.force,
        dry_run=args.dry_run,
        keep_log=args.keep_log,
        keep_image_format=args.keep_image_format,
        limit=args.limit
    )
