#!/usr/bin/env python3
"""
GitHub Release Creation Script for KotobaTranscriber v2.1.0
"""

import os
import sys
import json
import requests
from pathlib import Path

# Configuration
REPO_OWNER = "SHINZO111"
REPO_NAME = "KotobaTranscriber"
TAG_NAME = "v2.1.0"
RELEASE_NAME = "KotobaTranscriber v2.1.0 - Official Release"
RELEASE_DIR = Path("releases/KotobaTranscriber-v2.1.0")

RELEASE_BODY = """## KotobaTranscriber v2.1.0 - Official Release

### Release Contents
- **KotobaTranscriber-Source-v2.1.0.zip** - Complete source code
- **README.md** - Project documentation
- **INSTALLATION.md** - Installation and setup guide
- **DISTRIBUTION.md** - Distribution guidelines
- **LICENSE** - Open source license
- **HASHES.json** - SHA256 checksums for file verification

### System Requirements
- Windows 10/11 (64-bit)
- 8GB RAM minimum
- 5GB free disk space
- Python 3.8 or higher

### Quick Start
1. Download KotobaTranscriber-Source-v2.1.0.zip
2. Extract the file
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python src/main.py`

See INSTALLATION.md for detailed instructions.

### File Verification
Verify downloaded files using SHA256 checksums:
```bash
sha256sum -c HASHES.json
```

### What's New in v2.1.0
- First official public release
- Complete source code distribution
- Automated deployment and packaging
- Comprehensive documentation
- Release automation scripts

### Build Information
- **Build Date**: 2025-10-20
- **Version**: 2.1.0
- **Python**: 3.13.7
- **PyInstaller**: 6.16.0

### Support
For issues and feature requests: https://github.com/SHINZO111/KotobaTranscriber/issues
"""

def get_github_token():
    """Get GitHub token from environment variable"""
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Error: GITHUB_TOKEN environment variable not set")
        print("\nPlease set your GitHub Personal Access Token:")
        print("  export GITHUB_TOKEN='your_token_here'  # Linux/Mac")
        print("  set GITHUB_TOKEN=your_token_here       # Windows")
        print("\nTo create a token:")
        print("  1. Go to https://github.com/settings/tokens")
        print("  2. Generate new token (classic)")
        print("  3. Select 'repo' scope")
        print("  4. Copy and set the token")
        sys.exit(1)
    return token

def create_release(token):
    """Create GitHub release"""
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    data = {
        "tag_name": TAG_NAME,
        "name": RELEASE_NAME,
        "body": RELEASE_BODY,
        "draft": False,
        "prerelease": False
    }

    print(f"Creating release {TAG_NAME}...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 201:
        release_data = response.json()
        print(f"✓ Release created successfully!")
        print(f"  URL: {release_data['html_url']}")
        print(f"  ID: {release_data['id']}")
        return release_data
    elif response.status_code == 422:
        print("Error: Release already exists")
        print("\nTo fix this, either:")
        print("  1. Delete the existing release on GitHub")
        print("  2. Create a new version with a different tag")
        sys.exit(1)
    else:
        print(f"Error creating release: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)

def upload_asset(token, release_id, file_path):
    """Upload a file as a release asset"""
    url = f"https://uploads.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/{release_id}/assets"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/octet-stream"
    }

    params = {
        "name": file_path.name
    }

    print(f"Uploading {file_path.name}...")
    with open(file_path, 'rb') as f:
        response = requests.post(url, headers=headers, params=params, data=f)

    if response.status_code == 201:
        print(f"  ✓ Uploaded {file_path.name}")
        return True
    else:
        print(f"  ✗ Failed to upload {file_path.name}: {response.status_code}")
        print(f"    Response: {response.text}")
        return False

def main():
    """Main function"""
    print("=" * 70)
    print("GitHub Release Creation Script")
    print("KotobaTranscriber v2.1.0")
    print("=" * 70)
    print()

    # Check if release directory exists
    if not RELEASE_DIR.exists():
        print(f"Error: Release directory not found: {RELEASE_DIR}")
        sys.exit(1)

    # Get GitHub token
    token = get_github_token()

    # Create release
    release = create_release(token)
    release_id = release['id']

    print()
    print("Uploading release assets...")

    # Upload assets
    assets_to_upload = [
        "KotobaTranscriber-Source-v2.1.0.zip",
        "README.md",
        "INSTALLATION.md",
        "DISTRIBUTION.md",
        "LICENSE",
        "HASHES.json"
    ]

    upload_count = 0
    for asset_name in assets_to_upload:
        asset_path = RELEASE_DIR / asset_name
        if asset_path.exists():
            if upload_asset(token, release_id, asset_path):
                upload_count += 1
        else:
            print(f"  ⚠ Skipping {asset_name} (not found)")

    print()
    print("=" * 70)
    print(f"Release creation completed!")
    print(f"  Uploaded: {upload_count}/{len(assets_to_upload)} files")
    print(f"  Release URL: {release['html_url']}")
    print("=" * 70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)
