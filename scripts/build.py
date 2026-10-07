"""Build the self-contained Windows Lightroom plug-in ZIP."""
from pathlib import Path
import hashlib
import shutil
import subprocess
import sys
import zipfile
import importlib.metadata

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def main():
    subprocess.run([sys.executable, str(ROOT / "scripts/fetch_vendor.py")], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--noconsole",
                    "--name", "frame-helper", "--distpath", str(ROOT / "build/helper-dist"),
                    "--workpath", str(ROOT / "build/pyinstaller"), "--specpath", str(ROOT / "build"),
                    str(ROOT / "helper/frame_helper.py")], check=True, cwd=ROOT)
    bundle = ROOT / "LightroomExifFrame.lrplugin"
    binary = bundle / "bin"
    # Rebuild only the generated binary directory; never retain stale dependency files.
    if binary.exists():
        assert binary.resolve().parent == bundle.resolve() and binary.name == "bin"
        shutil.rmtree(binary)
    shutil.copytree(ROOT / "build/helper-dist/frame-helper", binary, dirs_exist_ok=True)
    licenses = binary / "licenses"
    licenses.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        python_license = Path(sys.base_prefix) / "LICENSE_PYTHON.txt"
    if not python_license.is_file():
        raise RuntimeError("Python runtime license not found")
    shutil.copy2(python_license, licenses / "PYTHON.txt")
    distribution = importlib.metadata.distribution("pyinstaller")
    for file in distribution.files or []:
        if str(file).endswith("licenses/COPYING.txt"):
            shutil.copy2(distribution.locate_file(file), licenses / "PYINSTALLER.txt")
    # The CLI frontends in the portable archive duplicate magick.exe; only magick is used.
    im = binary / "imagemagick"
    im.mkdir(exist_ok=True)
    for source in (ROOT / "vendor/imagemagick").iterdir():
        if source.is_file() and (source.suffix.lower() != ".exe" or source.name == "magick.exe"):
            shutil.copy2(source, im / source.name)
    shutil.copytree(ROOT / "vendor/exiftool", binary / "exiftool", dirs_exist_ok=True,
                    ignore=lambda directory, names: ["t"] if Path(directory).name == "exiftool_files" and "t" in names else [])
    shutil.copy2(ROOT / "LICENSE", bundle / "LICENSE.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", bundle / "THIRD_PARTY_NOTICES.md")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / f"Lightroom-EXIF-Frame-{VERSION}-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(ROOT).as_posix())
        for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md"):
            zipped.write(ROOT / name, name)
        for path in sorted((ROOT / "docs").rglob("*")):
            if path.is_file():
                zipped.write(path, path.relative_to(ROOT).as_posix())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"Built {archive.name}\nSHA-256 {checksum}")


if __name__ == "__main__":
    main()
