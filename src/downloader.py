import urllib.request
import hashlib
import os
import logging
import json
import ssl

logger = logging.getLogger(__name__)

def verify_hash(file_path, expected_hash_str):
    """Verifies the hash of a file against an expected SHA256 string."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    actual_hash = sha256_hash.hexdigest()
    # Handle both raw hex and "sha256:<hex>" formats
    if ":" in expected_hash_str:
        expected_hash = expected_hash_str.split(":")[1]
    else:
        expected_hash = expected_hash_str
        
    return actual_hash == expected_hash

def get_package_url(package, version, expected_hashes, verify_ssl=True):
    """Fetches the download URL from PyPI matching one of the expected hashes."""
    api_url = f"https://pypi.org/pypi/{package}/{version}/json"
    
    context = None
    if not verify_ssl:
        context = ssl._create_unverified_context()

    try:
        with urllib.request.urlopen(api_url, context=context) as response:
            data = json.loads(response.read().decode())
            
            for file_info in data.get("urls", []):
                # Check if hash matches one of the expected hashes
                file_hash = file_info.get("digests", {}).get("sha256")
                if file_hash:
                    # Check against expected hashes (which might be in sha256:<hex> format)
                    for expected in expected_hashes:
                        if file_hash in expected:
                            return file_info["url"], file_hash
                            
            # If no exact hash match, return the first one (fallback)
            if data.get("urls"):
                return data["urls"][0]["url"], data["urls"][0].get("digests", {}).get("sha256")
    except Exception as e:
        logger.error(f"Error fetching metadata for {package}=={version}: {e}")
    return None, None

def download_artifact(url, package, version, cache_dir, expected_hash=None, verify_ssl=True):
    """Downloads a package artifact to the cache directory and verifies it."""
    filename = url.split("/")[-1]
    dest_path = os.path.join(cache_dir, filename)
    
    context = None
    if not verify_ssl:
        context = ssl._create_unverified_context()

    if os.path.exists(dest_path):
        if expected_hash and verify_hash(dest_path, expected_hash):
            logger.info(f"Using cached {filename} (validated)")
            return dest_path
        else:
            logger.warning(f"Cached {filename} is invalid, re-downloading...")
            
    logger.info(f"Downloading {package}=={version} from {url}")
    try:
        if context:
            with urllib.request.urlopen(url, context=context) as response:
                with open(dest_path, "wb") as out_file:
                    out_file.write(response.read())
        else:
            urllib.request.urlretrieve(url, dest_path)
            
        if expected_hash:
            if verify_hash(dest_path, expected_hash):
                logger.info(f"Successfully verified {filename}")
                return dest_path
            else:
                logger.error(f"Hash mismatch for {filename}!")
                os.remove(dest_path)
                return None
        return dest_path
    except Exception as e:
        logger.error(f"Failed to download {url}: {e}")
        return None
