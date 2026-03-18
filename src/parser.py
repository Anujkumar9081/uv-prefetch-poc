import tomllib
import logging

logger = logging.getLogger(__name__)

def parse_uv_lock(lockfile_path):
    """Parses a uv.lock file and extracts package information."""
    try:
        with open(lockfile_path, "rb") as f:
            lock_data = tomllib.load(f)
        
        packages = []
        for pkg in lock_data.get("package", []):
            package_info = {
                "name": pkg.get("name"),
                "version": pkg.get("version"),
                "dependencies": pkg.get("dependencies", []),
                "hashes": pkg.get("hashes", []),
            }
            # Handle source information if available
            source = pkg.get("source")
            if source:
                package_info["source"] = source
            
            packages.append(package_info)
            
        return packages
    except FileNotFoundError:
        logger.error(f"Lockfile not found: {lockfile_path}")
        return []
    except Exception as e:
        logger.error(f"Error parsing lockfile {lockfile_path}: {e}")
        return []

if __name__ == "__main__":
    import sys
    import json
    if len(sys.argv) > 1:
        pkgs = parse_uv_lock(sys.argv[1])
        print(json.dumps(pkgs, indent=2))
