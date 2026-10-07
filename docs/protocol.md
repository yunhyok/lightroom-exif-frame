# Helper protocol v1

Invocation: `frame-helper.exe --job JOB.json`. UTF-8 JSON, no BOM required;
reader accepts UTF-8 BOM. All paths absolute. The only command-line input is
the job path; user text never appears on a shell command line.

```json
{
  "schema_version": 1,
  "input_path": "C:/work/rendered.tif",
  "output_path": "C:/export/photo_frame.webp",
  "result_path": "C:/work/result.json",
  "source_path": "C:/photos/original.dng",
  "preview": false,
  "remove_person_info": false,
  "preview_max_size": 600,
  "format": "webp",
  "quality": 95,
  "lossless": false,
  "bit_depth": 8,
  "color_space": "sRGB",
  "theme": "strap",
  "appearance": "light",
  "background_color": "#ffffff",
  "text_color": "#161616",
  "secondary_color": "#555555",
  "font_path": "C:/Windows/Fonts/malgun.ttf",
  "font_percent": 1.65,
  "band_percent": 7.3,
  "padding_percent": 1.7,
  "logo_percent": 10,
  "focal_mode": "equivalent",
  "artist": "",
  "templates": ["ISO{iso} {focal}mm F{aperture} {shutter}s", "{date}", "{make} {model}", "{lens}"],
  "metadata": {"make":"RICOH IMAGING COMPANY, LTD.","model":"PENTAX K-3 Mark III","lens":"HD PENTAX-D FA 150-450mm F4.5-5.6ED DC AW","iso":"1000","aperture":"9","shutter":"1/800","focal":"630","focal35":"973","date":"2024/04/08 12:31:11"},
  "logos": {"pentax": "C:/logos/pentax.png"}
}
```

Formats: jpg/png/webp. Themes: strap/simple/none. Color spaces:
sRGB/AdobeRGB/ProPhotoRGB. JPEG is 8-bit, PNG 8/16-bit, WebP sRGB8.
Lightroom must render TIFF16 already in chosen destination profile (sRGB
for WebP). Input TIFF is the sole embedded-metadata source. Original
source_path is optional and may only supply missing *visible* frame fields.
Preview input must also be a Lightroom-rendered TIFF; preview output is sRGB8
PNG but layout is computed at the input's actual size before downsampling.

`remove_person_info` is an optional boolean, default false. Lua passes the native
`LR_removeFaceMetadata` choice. When true, the metadata module additionally removes
typed person/face-region metadata that Lightroom may leave in the rendered TIFF.
This does not modify the TIFF or original file, and does not heuristically remove
names from captions, creator contacts, or ordinary keywords. Upstream Lightroom
exclusion failures and final-output privacy enforcement must be reported separately.

Helper dependencies next to EXE: `imagemagick/magick.exe`,
`exiftool/exiftool.exe` and its official support files. Development overrides:
`EXIF_FRAME_MAGICK`, `EXIF_FRAME_EXIFTOOL` absolute paths.

Result written atomically (success or failure):
`{"schema_version":1,"ok":true,"output_path":"...","width":1920,"height":1420,"warnings":[]}`
or `{"schema_version":1,"ok":false,"error":"...","warnings":[]}`.
Exit 0 success, nonzero failure. Existing output paths are never overwritten;
numbered suffixes are allocated atomically. Preview can use fresh unique names.

Metadata module interface:
`read_display_metadata(source: pathlib.Path, exiftool: pathlib.Path) -> dict[str,str]`;
`copy_metadata(source: pathlib.Path, destination: pathlib.Path, *, exiftool: pathlib.Path,
format: str, width: int, height: int, body_width: int, body_height: int,
offset_x: int, offset_y: int, remove_person_info: bool = False) -> list[str]`.
Returns warnings; raises on metadata failure. Renderer owns ICC and pixels;
metadata module must not overwrite ICC. Renderer strips metadata from its
intermediates before copying only the Lightroom-filtered metadata.
