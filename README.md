# uv-prefetch-poc

A proof-of-concept for offline dependency prefetching based on the `uv` lockfile format.

## Overview

This project demonstrates a secure, reproducible, and network-isolated workflow for Python dependency management. By resolving and prefetching artifacts *before* the execution phase, we ensure that:
1.  **Reproducibility**: The exact same artifacts are used across different environments.
2.  **Security**: Hashes are verified upfront, preventing tampered packages from entering the build pipeline.
3.  **Isolation**: Builds can be performed in environments with no network access.

## Features

- **Lockfile Parsing**: Statically analyzes `uv.lock` (TOML) to extract the full dependency graph.
- **Artifact Prefetching**: Downloads required wheels or source distributions.
- **Integrity Verification**: Comprehensive SHA256 checksum validation.
- **Lightweight SBOM**: Generates a JSON-based Software Bill of Materials.

## Installation & Usage

### Prerequisites
- Python 3.11+ (uses native `tomllib`)

### Running the Prefetcher

```bash
python3 src/prefetch.py --lockfile example/uv.lock --cache-dir ./cache
```

### Verifying Offline Install

Once prefetched, you can install the dependencies in an isolated environment:

```bash
uv pip install --offline --find-links ./cache -r requirements.txt
```

## Project Structure

- `src/`: Core implementation logic.
- `example/`: Sample project configuration for testing.

---
*Created as part of a GSoC 2026 PoC for Konflux/Hermeto integration.*
