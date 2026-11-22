# Frame Helper Protocol (`schema_version = 1`, Plug-in `0.2.2`)

`LightroomExifFrame.lrplugin` (Lua) spawns `bin/frame-helper.exe` (PyInstaller frozen Python + ImageMagick 7 Q16 + ExifTool 13.59 + `resvg_py`) with no shell expansion (`LrTasks.execute` extra outer quotes on Windows).

---

## CLI Entry Points

```text
frame-helper.exe --job <absolute_job.json>
frame-helper.exe --inspect <absolute_inspect.json>
```

Both modes decode `<json>` as UTF-8 with optional BOM (`utf-8-sig`, max `1 MiB`) and write `result.json` atomically (`os.replace` over sibling temp file) to `result_path`.

- `--job`: Renders the 16-bit TIFF into JPG, PNG (8/16-bit), WebP (lossy/VP8L lossless), or 8-bit sRGB preview PNG, preserves ICC & mapped metadata/MWG regions, and atomically publishes output.
- `--inspect`: Resolves manufacturer brand, hardware release year, and historical CI SVG metadata quickly without launching ImageMagick or rendering pixels.

---

## Job JSON Request Schema

Required for `--job`:
- `schema_version` (`1`), `input_path` (existing TIFF16 path), `output_path` (absolute target file path), `result_path` (absolute non-colliding JSON result path).

Required for `--inspect`:
- `schema_version` (`1`), `result_path`.

Optional / v0.2.0 fields:
- `source_path` (`string | null`): Original file path used only as read-only EXIF fallback when Lightroom metadata fields are blank. Never overwritten.
- `preview` (`bool`, default `false`), `preview_max_size` (`64..4096`, default `600`).
- `format` (`"jpg" | "png" | "webp"`), `quality` (`1..100`), `lossless` (`bool`), `bit_depth` (`8 | 16`), `color_space` (`"sRGB" | "AdobeRGB" | "ProPhotoRGB"`).
- `theme` (16 options: `"strap"`, `"simple"`, `"one_line"`, `"two_line"`, `"shot_on_one_line"`, `"shot_on_two_line"`, `"film"`, `"monitor"`, `"lightroom"`, `"just_frame"`, `"cinemascope"`, `"custom_one_line"`, `"custom_two_line"`, `"poster"`, `"tip"`, `"none"`).
- `appearance` (`"auto" | "light" | "dark" | "custom"`), `background_color`, `text_color`, `secondary_color` (`#RRGGBB`).
- `aspect_ratio` (`"free" | "1:1" | "4:5" | "5:4" | "3:4" | "4:3" | "2:3" | "3:2" | "16:9" | "9:16"`), `no_crop` (`bool`), `padding_inside` (`bool`), `compact` (`bool`).
- `font_path`, `font_percent` (`0.2..10`), `band_percent` (`1..40`), `padding_percent` (`0..20`), `logo_percent` (`1..50`).
- `font_style` (`"normal" | "italic"`), `text_align` (`"left" | "center" | "right"`), `text_alpha` (`0.05..1.0`), `shadow_size` (`0..50`).
- `logo_mode` (`"auto_era" | "auto_latest" | "manual_era" | "text_only" | "none"`), `logo_style` (`"brand" | "mono"`), `manual_brand`, `manual_era`.
- `focal_mode` (`"equivalent" | "actual" | "ratio"`), `crop_factor` (`0.1..20`), `date_notation` (10 options), `show_make`, `show_model`, `show_lens`, `show_exposure`, `override_make`, `override_model`, `override_lens`, `artist`, `label`, `divider`.
- `collision_mode` (`"rename" | "overwrite" | "skip" | "ask"`), `remove_person_info` (`bool`).
- `templates` (`list[str]` of 4 templates), `metadata` (`dict[str, str]`), `logos` (`dict[brand_key, png_or_svg_path]`).

---

## Result JSON Response Schema

On success (`exit 0`):
```json
{
  "schema_version": 1,
  "ok": true,
  "output_path": "C:\\Export\\Photo.jpg",
  "width": 3264,
  "height": 2686,
  "warnings": [],
  "brand_info": {
    "brand_id": "kodak",
    "brand_name": "Kodak",
    "era_id": "2006",
    "era_label": "2006–2016 (Rounded Red Wordmark)",
    "era_label_ko": "2006–2016 (둥근 레드 워드마크)",
    "detected_year": 2006,
    "year_source": "database",
    "logo_source": "builtin_svg"
  }
}
```
(`--inspect` omits `output_path`, `width`, and `height`.)

On failure (`exit 1`):
```json
{
  "schema_version": 1,
  "ok": false,
  "error": "...",
  "warnings": []
}
```

---

## Security & Atomicity Invariants

- All paths must be absolute strings without NUL characters; `result_path` cannot collide with `job_path`, `input_path`, `source_path`, `output_path`, `font_path`, or user `logos`.
- `publish()` never overwrites `source_path` even if `collision_mode == "overwrite"`.
- In `"rename"` mode, outputs allocate unique `_1`, `_2`, ... suffixes atomically without overwrite.
- Bundled `helper/data/` and `helper/assets/logos/` contain only pure-vector SVGs (`<text>` forbidden) and offline JSON catalogs; `resvg_py` renders SVGs with `skip_system_fonts=True` for built-in logos.
