import argparse
import os
import sys
import logging
from parser import parse_uv_lock
from downloader import get_package_url, download_artifact
from sbom import generate_sbom

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Prefetch Python dependencies from a uv.lock file.")
    parser.add_argument("--lockfile", default="uv.lock", help="Path to the uv.lock file.")
    parser.add_argument("--cache-dir", default="./cache", help="Directory to store prefetched artifacts.")
    parser.add_argument("--sbom-output", default="sbom.json", help="Path to the output SBOM file.")
    parser.add_argument("--no-verify-ssl", action="store_true", help="Disable SSL certificate verification.")
    
    args = parser.parse_args()

    if not os.path.exists(args.lockfile):
        logger.error(f"Lockfile {args.lockfile} not found.")
        sys.exit(1)

    if not os.path.exists(args.cache_dir):
        os.makedirs(args.cache_dir)
        logger.info(f"Created cache directory: {args.cache_dir}")

    logger.info(f"Parsing lockfile: {args.lockfile}")
    packages = parse_uv_lock(args.lockfile)
    
    if not packages:
        logger.warning("No packages found in lockfile or parsing failed.")
        sys.exit(0)

    logger.info(f"Found {len(packages)} packages. Starting prefetch...")
    
    downloaded_count = 0
    for pkg in packages:
        name = pkg["name"]
        version = pkg["version"]
        hashes = pkg["hashes"]
        
        # Get download URL and specific hash from PyPI
        url, specific_hash = get_package_url(name, version, hashes, verify_ssl=not args.no_verify_ssl)
        
        if url:
            result = download_artifact(url, name, version, args.cache_dir, specific_hash, verify_ssl=not args.no_verify_ssl)
            if result:
                downloaded_count += 1
        else:
            logger.warning(f"Could not find download URL for {name}=={version}")

    logger.info(f"Prefetch complete. Downloaded {downloaded_count} artifacts.")
    
    # Generate SBOM
    logger.info("Generating SBOM...")
    generate_sbom(packages, args.cache_dir, args.sbom_output)

if __name__ == "__main__":
    main()
