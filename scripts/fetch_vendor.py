"""Fetch hash-pinned official Windows tools. Run from any directory."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = {
    "imagemagick": ("https://github.com/ImageMagick/ImageMagick/releases/download/7.1.2-32/ImageMagick-7.1.2-32-portable-Q16-x64.7z", "2540f87550bd24488d71248427b8ab6754573a0506ea0cbe943579fdbddab299", ".7z"),
    "exiftool": ("https://oliverbetz.de/cms/files/Artikel/ExifTool-for-Windows/exiftool-13.59_64.zip", "577257dd22baebe77157d905792d6ed2c5916cd03aa627f40b2175db12110ac6", ".zip"),
}


def main():
    vendor = ROOT / "vendor"
    vendor.mkdir(exist_ok=True)
    for name, (url, checksum, suffix) in PACKAGES.items():
        archive = vendor / (name + suffix)
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            request = urllib.request.Request(url, headers={"User-Agent": "Lightroom-EXIF-Frame-build/0.1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
            raise RuntimeError(f"SHA-256 mismatch: {name}")
        destination = vendor / name
        destination.mkdir(exist_ok=True)
        if suffix == ".zip":
            with zipfile.ZipFile(archive) as zipped:
                zipped.extractall(destination)
        else:
            # Windows ships bsdtar, which supports the official archive's BCJ2 filter.
            subprocess.run(["tar", "-xf", str(archive), "-C", str(destination)], check=True)
        print(f"Verified {name}: {checksum}")


if __name__ == "__main__":
    main()
