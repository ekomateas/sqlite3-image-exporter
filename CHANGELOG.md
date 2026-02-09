# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026‑02‑04
### Added
- Initial public release
- Export images from SQLite3 BLOB tables
- Format detection via magic bytes
- Optional JPEG conversion
- Corrupt image detection
- Dry‑run mode
- Force overwrite
- Logging
- Config separation via `config.py.sample`

---

## [1.1.0] - 2026-02-09
### Added
- Unified ImageData class supporting both filesystem paths and raw bytes.
- New ImageExistsChecker.exists_by_data() for fast duplicate detection without temporary files.
- Unicode-aware sanitize_key() for deterministic, cross-platform-safe filenames.

### Changed
- Duplicate detection now uses size → md5 → (optional) phash pipeline.
- Improved JPEG conversion with explicit img.load() for forensic clarity.
- Cleaner export logic: filename match and content match handled consistently.
- Summary now reports images on disk using ImageExistsChecker instead of legacy logic.

### Removed
- Old existing_files logic (now redundant).

### Fixed
- Edge cases where non-ASCII keys produced invalid filenames.
- Rare cases where conversion could fail due to lazy image loading.
