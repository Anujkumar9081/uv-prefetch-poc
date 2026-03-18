import json
import os
import datetime
import logging

logger = logging.getLogger(__name__)

def generate_sbom(packages, cache_dir, output_file):
    """Generates a simple JSON SBOM for the prefetched packages."""
    sbom = {
        "metadata": {
            "version": "1.0",
            "timestamp": datetime.datetime.now().isoformat(),
            "tool": "uv-prefetch-poc",
            "description": "Software Bill of Materials for prefetched dependencies"
        },
        "packages": []
    }
    
    for pkg in packages:
        # Check if we have hashes for this package
        hashes = pkg.get("hashes", [])
        
        # Only include if we have a version and name
        if pkg.get("name") and pkg.get("version"):
            pkg_data = {
                "name": pkg["name"],
                "version": pkg["version"],
                "dependencies": pkg.get("dependencies", []),
                "hashes": hashes,
                "summary": f"{pkg['name']}=={pkg['version']} fetched to local cache."
            }
            sbom["packages"].append(pkg_data)
            
    try:
        with open(output_file, "w") as f:
            json.dump(sbom, f, indent=4)
        logger.info(f"SBOM generated successfully: {output_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to generate SBOM {output_file}: {e}")
        return False
