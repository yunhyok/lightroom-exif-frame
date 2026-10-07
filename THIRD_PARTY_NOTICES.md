# Third-party programs

The plug-in's original Lua and Python source is MIT licensed. The programs below
run as separate executables and retain their own licenses. Camera logos and
Windows fonts are not distributed.

Paths below are relative to the extracted `LightroomExifFrame.lrplugin` folder.
These generated runtime files are included in release ZIPs, not in the source
checkout. The ExifTool upstream test-image directory is omitted from the bundle.

| Component | Version / source | Included notices |
| --- | --- | --- |
| ImageMagick Q16 x64 | [7.1.2-32](https://github.com/ImageMagick/ImageMagick/releases/tag/7.1.2-32) | `bin/imagemagick/LICENSE.txt`, `NOTICE.txt` (including bundled delegate notices) |
| ExifTool | [13.59](https://github.com/exiftool/exiftool/tree/13.59), [official Windows packager](https://oliverbetz.de/pages/Artikel/ExifTool-for-Windows) | `bin/exiftool/exiftool_files` contains upstream licenses and Strawberry Perl notices |
| CPython | [3.12](https://www.python.org/downloads/source/) | `bin/licenses/PYTHON.txt` includes the Python runtime and standard-library notices |
| OpenSSL (CPython dependency) | [3.x](https://github.com/openssl/openssl); exact build version in `bin/licenses/RUNTIME.txt` | `bin/licenses/OPENSSL.txt`, Apache 2.0; copyright The OpenSSL Project Authors and contributors |
| PyInstaller | [6.22.3](https://pyinstaller.org/) | `bin/licenses/PYINSTALLER.txt`; GPL with bootloader exception |

ImageMagick is copyright ImageMagick Studio LLC. ExifTool is copyright Phil
Harvey and is available under the same terms as Perl (Artistic License or GPL).
The Windows package also contains separate third-party dependencies; their
license notices are preserved. Upstream source releases are available from the
linked maintainers. The build uses the SHA-256-pinned official downloads recorded
in `scripts/fetch_vendor.py`.

The OpenSSL license text is preserved from the [3.5.4 source release](https://github.com/openssl/openssl/blob/openssl-3.5.4/LICENSE.txt).
The Windows v0.1.0 release helper uses OpenSSL 3.5.4 through CPython; rebuilding
with another Python 3.12 distribution can change its bundled runtime version.

Adobe, Lightroom, camera brands, and their marks belong to their respective
owners. This project is independent and is not endorsed by those companies.
