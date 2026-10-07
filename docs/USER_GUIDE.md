# Lightroom EXIF Frame 사용 가이드 · User guide

Windows x64용 v0.1.0입니다. 설치는 [README](../README.md)를, 실제 검사 결과와 남은 검증은 [VALIDATION.md](VALIDATION.md)를 참고하세요. 아래 설명은 구현된 동작과 공식 SDK/도구 문서를 기준으로 합니다. 실제 Lightroom에서 확인하지 않은 항목의 성공을 뜻하지 않습니다.

This guide covers v0.1.0 for Windows x64. See the [README](../README.md) for installation and [VALIDATION.md](VALIDATION.md) for completed and outstanding checks. It describes implemented behavior and the SDK/tool contract; it does not assert success for unperformed live Lightroom checks.

## 내보내기 설정 · Export settings

사진을 선택한 뒤 **파일 → 내보내기 → EXIF Frame**을 선택합니다. 상단의 출력 폴더는 최종 결과 저장 위치입니다. Lightroom의 기본 파일 위치 및 파일 설정 영역 대신 플러그인의 폴더·형식 설정을 사용합니다.

Select photos and choose **File → Export → EXIF Frame**. The custom output folder is the destination for final images. The plug-in supplies folder and format settings in place of Lightroom's native location and file-format sections.

Lightroom의 파일 이름 지정, 이미지 크기 조정, 출력 선명하게 하기, 메타데이터 영역을 계속 사용합니다. 임시 TIFF의 이름을 바탕으로 최종 확장자를 붙이므로 Lightroom 이름 지정 설정이 최종 이름에 반영됩니다. 기존 파일은 덮어쓰지 않고 번호를 붙입니다.

Continue using Lightroom's native naming, image sizing, output sharpening, and metadata sections. The final name derives from the rendered TIFF name with the selected extension, retaining Lightroom naming. Existing files receive numbered alternatives.

이미지 크기 조정은 프레임을 제외한 사진 본체의 크기입니다. 예를 들어 3000 px 너비의 Strap 사진은 하단 띠만큼 높이가 늘어나며, Simple은 주변 여백만큼 너비와 높이가 모두 늘어납니다. 내보낸 파일을 자동으로 카탈로그에 다시 추가하지 않습니다.

Image sizing describes the photo body. A 3000 px-wide Strap image becomes taller by its footer height; Simple increases both dimensions with surrounding padding. Final images are not automatically reimported into the catalog.

| 형식 · Format | 최종 비트 · Final depth | 색공간 · Color space | 옵션 · Options |
|---|---|---|---|
| JPG | 8 | sRGB / Adobe RGB / ProPhoto RGB | 품질 1–100 · quality |
| PNG | 8 또는 16 · or | sRGB / Adobe RGB / ProPhoto RGB | 무손실 · lossless |
| WebP | 8 | sRGB | 품질 1–100 또는 무손실 · quality or lossless |

모든 형식의 사진 본체는 Lightroom이 ICC 프로파일을 포함한 **16비트 TIFF**로 렌더링합니다. JPG/PNG는 선택한 프로파일을 유지하고 WebP는 sRGB로 제한합니다. JPG의 최종 데이터는 8비트이며 PNG는 선택한 비트 깊이로 저장합니다. 16비트 원본 처리와 최종 16비트 PNG는 ImageMagick Q16을 사용합니다.

Lightroom renders the body as a **16-bit TIFF with an embedded ICC profile**. JPG/PNG retain the selected profile; WebP is restricted to sRGB. JPG has 8-bit output; PNG uses its selected depth. ImageMagick Q16 handles 16-bit input and PNG output.

## 테마와 색상 · Themes and colors

**Strap**은 사진 본체 바로 아래 띠를 추가합니다. 왼쪽 위/아래와 오른쪽 위/아래가 네 텍스트 영역이며, 등록된 제조사 로고는 두 열 사이에 들어갑니다. **Simple**은 사진 주변 여백을 추가하고 네 영역의 내용을 하단 가운데에 모읍니다. **None**은 프레임과 텍스트 없이 형식만 변환합니다.

**Strap** adds a footer directly below the photo. Its four text areas are upper/lower left and upper/lower right; the registered logo sits between the columns. **Simple** adds surrounding padding and combines the four templates in a centered footer. **None** converts the format without a frame or text.

밝게/어둡게를 선택하면 미리 정한 배경·주 글자·보조 글자 색상을 사용합니다. 사용자 색상은 `#RRGGBB` 형식입니다. 화면에서 고른 색상은 sRGB 기준으로 해석한 뒤 최종 출력 프로파일로 변환합니다.

Light and dark use predefined background, primary text, and secondary text colors. Custom colors use `#RRGGBB`. Color choices are interpreted as sRGB and converted into the final output profile.

| 조절 · Control | 범위 · Range | 의미 · Meaning |
|---|---|---|
| 띠 높이 · Band | 1–40% | 사진 너비 기준 하단 띠 높이 · footer height relative to photo width |
| 여백 · Padding | 0–20% | 사진 너비 기준 여백 · padding relative to photo width |
| 글자 크기 · Font | 0.2–10% | 사진 너비 기준 목표 크기 · target size relative to photo width |
| 로고 크기 · Logo | 1–50% | 사진 너비 기준 목표 로고 영역 · target logo area relative to photo width |

실제 로고는 촬영 정보 영역을 남기도록 제한됩니다. 글이 길면 줄바꿈하고 글자 크기를 줄입니다. 겹침 없이 배치할 수 없으면 해당 텍스트를 생략하고 경고를 표시합니다. 긴 렌즈 이름은 띠 높이를 늘리거나 글자 크기를 줄여 미리보기에서 확인하세요.

The logo area is constrained to leave room for metadata. Long text wraps and shrinks; text that cannot fit without overlap is omitted with a warning. For long lens names, increase the footer height or reduce the font size and check the preview.

글꼴은 로컬 `.ttf`, `.otf`, `.ttc` 파일을 찾아 선택합니다. 기본 경로는 Windows의 맑은 고딕입니다. 한글 등 필요한 문자를 지원하는 글꼴을 사용하세요. 폰트 파일은 플러그인에 복사하거나 배포하지 않습니다.

Browse for a local `.ttf`, `.otf`, or `.ttc` font file. The default is Windows Malgun Gothic. Choose a font containing the characters you need. The plug-in does not copy or distribute the font.

## 네 영역 템플릿 · Four text templates

템플릿 대상 영역과 토큰을 선택하고 삽입 버튼을 누르면 해당 영역 끝에 `{token}`이 추가됩니다. 템플릿에는 일반 글자·공백·줄바꿈과 아래 토큰을 사용할 수 있습니다. 알 수 없는 토큰이나 맞지 않는 중괄호는 내보내기 전에 오류로 안내합니다.

Choose a target area and token, then press Insert to append `{token}` to that template. Use literal text, spaces, line breaks, and these tokens. Unknown tokens and unmatched braces are rejected before export.

| 토큰 · Token | 값 · Value | 예 · Example |
|---|---|---|
| `{iso}` | ISO 감도 · ISO speed | `800` |
| `{aperture}` | 조리개 분모 · f-number | `2.8` |
| `{shutter}` | 초 단위 노출 시간, 가능한 경우 분수 · exposure seconds, reciprocal where appropriate | `1/250`, `0.8`, `2` |
| `{focal}` | 초점거리 선택값 · selected focal mode | `50` |
| `{focal35}` | 35 mm 환산값, 없으면 `—` · 35 mm equivalent, `—` when absent | `75` |
| `{date}` | Lightroom이 표시하는 촬영 일시 · Lightroom-formatted capture date/time | 카탈로그 값 · catalog value |
| `{make}` | 제조사 · manufacturer | `Canon` |
| `{model}` | 카메라 모델 · camera model | `EOS R5` |
| `{lens}` | 렌즈 이름 · lens name | 카탈로그 값 · catalog value |
| `{artist}` | 직접 입력한 이름, 비워 두면 카탈로그 아티스트 · entered name, otherwise catalog artist | 원하는 이름 · your name |

초점거리 방식은 **실제 / 35 mm 환산**입니다. `{focal}`은 이 설정을 따르며 환산값이 없으면 실제 초점거리로 돌아갑니다. `{focal35}`는 항상 환산값만 사용합니다. 단위는 템플릿에 직접 넣습니다. 예를 들어 `{focal}mm`, `F{aperture}`, `{shutter}s`입니다.

Focal mode is **actual / 35 mm equivalent**. `{focal}` follows that choice and falls back to actual focal length when the equivalent is unavailable. `{focal35}` always requests the equivalent. Add units yourself, such as `{focal}mm`, `F{aperture}`, and `{shutter}s`.

기본 네 영역은 다음과 같습니다. 정보가 없는 토큰은 `—`로 표시합니다. 아티스트 입력을 비워 두면 카탈로그의 아티스트를 사용하며, 이 입력은 최종 파일 내부 메타데이터를 덮어쓰지 않습니다.

The default templates are below. Missing values display `—`. An empty artist override uses the catalog artist; the override does not overwrite embedded metadata.

```text
왼쪽 위 / upper left:   ISO{iso} {focal}mm F{aperture} {shutter}s
왼쪽 아래 / lower left: {date}
오른쪽 위 / upper right: {make} {model}
오른쪽 아래 / lower right: {lens}
```

## 공식 로고 등록 · Registering official logos

제조사를 선택하고 본인이 이용할 수 있는 **공식 투명 PNG 파일**을 등록합니다. 지원 목록은 Canon, Nikon, Sony, Fujifilm, Pentax, Ricoh, Leica, Panasonic, Olympus, OM System, Sigma, Hasselblad입니다. 플러그인은 로고를 다운로드하거나 브랜드 사이트의 자료를 복제하지 않습니다.

Choose the manufacturer and register an **official transparent PNG** you are entitled to use. Supported entries are Canon, Nikon, Sony, Fujifilm, Pentax, Ricoh, Leica, Panasonic, Olympus, OM System, Sigma, and Hasselblad. The plug-in does not download logos or copy brand-site assets.

등록된 **파일 경로**는 사용자별 Lightroom 플러그인 환경설정에 저장됩니다. 제조사별 한 번 등록하면 다음 내보내기에서도 사용할 수 있습니다. 로고를 이동하면 새 경로로 다시 등록하세요. 등록 해제는 경로만 제거하고 로고 파일은 삭제하지 않습니다. 다른 사용자의 PC에는 자동으로 전달되지 않습니다.

The **file path** is stored in your per-user Lightroom plug-in preferences. Register once per manufacturer to reuse it in later exports. Register again if you move the file. Unregister removes its setting, not the file. Paths are not transferred to another user's computer.

등록하지 않은 제조사는 공식 로고 대신 일반 글자로 제조사 이름을 표시합니다. 로고 파일의 유효한 PNG 형식·크기 제한을 확인하며, 등록한 파일이 사라졌거나 손상된 경우 내보내기 오류로 보고합니다. 밝은 배경과 어두운 배경에서 모두 보이는지 미리보기로 확인하세요.

Unregistered manufacturers use plain manufacturer text in place of an official logo. The renderer checks PNG validity and size limits; a missing or damaged registered file produces an export error. Preview the logo against your chosen background.

<a id="metadata"></a>
## 내부 메타데이터 · Embedded metadata

Lightroom의 메타데이터 설정이 최종 파일의 **출발점**입니다. GPS 제거, 인물 정보 제외, 저작권만 포함 등의 정책은 Lightroom의 임시 TIFF에 먼저 적용됩니다. 헬퍼는 그 TIFF의 EXIF/IPTC/XMP만 복사합니다. 원본 사진에서 제거된 태그를 다시 가져오지 않습니다.

Lightroom's metadata settings define the **starting point**. GPS removal, person-information exclusion, copyright-only export, and other policies are applied to the temporary TIFF first. The helper copies EXIF/IPTC/XMP only from that TIFF and does not restore tags from the original photo.

사진 바깥에 보이는 EXIF 텍스트는 카탈로그 촬영 정보입니다. 내부 메타데이터를 제거해도 기본 프레임에는 촬영 정보가 보일 수 있습니다. 그 정보를 결과 이미지에 표시하지 않으려면 해당 템플릿을 비우거나 None을 선택하세요. 사용자 아티스트 입력도 화면에만 적용됩니다.

Visible frame text comes from catalog capture information. Removing embedded metadata can still leave capture information visible in the default frame. Clear the relevant templates or choose None to omit it from the image itself. The artist entry also affects visible text only.

출력 형식별 차이는 다음과 같습니다. “Lightroom 설정 그대로”는 제거 정책을 지키고 지원되는 의미 정보를 보존한다는 뜻이며, TIFF 태그 전체의 바이트 단위 복제는 아닙니다.

Format differences are listed below. “Preserve Lightroom settings” means honoring removal policies and preserving supported semantic information, rather than duplicating every TIFF tag byte-for-byte.

- **JPG:** EXIF/IPTC/XMP를 복사합니다. 출력 ICC는 렌더러가 선택한 프로파일을 유지합니다.<br />Copies EXIF/IPTC/XMP while retaining the renderer's output ICC profile.
- **PNG:** EXIF/XMP와 ExifTool이 쓸 수 있는 IPTC를 복사합니다. PNG의 IPTC 저장 방식은 일부 앱에서 읽지 못할 수 있습니다.<br />Copies EXIF/XMP and IPTC writable by ExifTool; some applications do not read PNG's IPTC representation.
- **WebP:** EXIF/XMP를 복사합니다. WebP에는 IPTC IIM 전용 청크가 없으므로 ExifTool의 공식 매핑으로 지원되는 IPTC 항목을 XMP에 옮기고, 이미 있는 Lightroom XMP 값은 우선합니다. 매핑되지 않는 항목의 동일 보존은 보장하지 않습니다.<br />Copies EXIF/XMP. WebP lacks an IPTC IIM chunk, so supported IPTC fields are mapped to XMP with ExifTool's official mapping, preserving existing Lightroom XMP values. Unmapped fields are not guaranteed to survive.
- **크기·회전 · Geometry:** 프레임을 포함한 최종 크기와 정상 방향으로 맞춥니다. 오래된 썸네일/미리보기 및 MakerNotes는 복사에서 제외합니다.<br />Dimensions and orientation are updated for the framed image. Stale thumbnails/previews and MakerNotes are excluded.
- **인물/영역 · Regions:** 지원되는 정규화된 MWG/Microsoft 인물 영역은 여백·프레임에 맞춰 변환합니다. 지원하지 않는 공간 태그는 오래된 좌표를 남기지 않도록 제외하고 경고합니다.<br />Supported normalized MWG/Microsoft person regions are remapped to the new canvas. Unsupported spatial tags are omitted with warnings to avoid stale coordinates.

색공간 프로파일은 메타데이터 복사와 별개로 렌더러가 관리합니다. PNG/WebP의 태그 호환성은 사용하는 뷰어에서도 확인하세요. 공식 형식별 근거는 [ExifTool RIFF/WebP](https://exiftool.org/TagNames/RIFF.html), [PNG](https://exiftool.org/TagNames/PNG.html), [IPTC→XMP 매핑](https://github.com/exiftool/exiftool/blob/master/arg_files/iptc2xmp.args)에 있습니다.

The renderer manages ICC independently of metadata copying. Check PNG/WebP metadata support in your receiving application. Official references: [ExifTool RIFF/WebP](https://exiftool.org/TagNames/RIFF.html), [PNG](https://exiftool.org/TagNames/PNG.html), and [IPTC→XMP mapping](https://github.com/exiftool/exiftool/blob/master/arg_files/iptc2xmp.args).

## 미리보기와 취소 · Preview and cancellation

미리보기는 Lightroom에서 현재 선택한 대상 사진 한 장을 현재 크기·선명도·메타데이터 정책으로 다시 렌더링합니다. 내보내기와 같은 합성 코드를 사용하고, 최종 표시만 sRGB 8비트 PNG 및 최대 600 px로 줄입니다. 텍스트 줄바꿈은 줄이기 전 실제 사진 크기에서 계산합니다. 최종 파일의 비트 깊이·프로파일·메타데이터 검증을 대신하지는 않습니다.

Preview rerenders one selected target photo through Lightroom with current sizing, sharpening, and metadata policy. It uses the same composition code as export, then converts the display to an sRGB 8-bit PNG capped at 600 px. Text layout is calculated at the actual body size before reduction. Preview does not replace checking the final file's bit depth, profile, or metadata.

배치 취소는 다음 사진으로 넘어가기 전에 적용됩니다. 이미 실행 중인 외부 합성 작업을 강제로 종료하지 않으므로 취소 후 현재 사진이 완성될 수 있습니다. Lightroom 렌더링 실패와 합성 실패는 내보내기 오류로 보고합니다. 텍스트 축소·영역 생략 등 경고는 내보내기 후 요약합니다.

Batch cancellation takes effect before the next photo. An external renderer already processing a photo is allowed to finish, so that photo may be saved after cancellation. Lightroom-render and helper failures are reported as export errors; layout and metadata warnings are summarized afterward.

## 문제 확인 · Troubleshooting

| 증상 · Symptom | 확인 · Check |
|---|---|
| 실행 파일 누락 · Missing helper | ZIP의 `.lrplugin` 전체를 다시 풉니다. 플러그인 관리자의 진단 버튼으로 경로를 확인합니다. / Extract the complete `.lrplugin`; inspect paths with the manager's diagnostics button. |
| 한글 글자가 비어 있음 · Missing glyphs | 해당 문자를 포함한 로컬 글꼴을 선택합니다. / Select a local font containing the required glyphs. |
| 로고 오류 · Logo error | 등록 파일이 존재하는지, 실제 PNG인지 확인하고 다시 등록합니다. / Check that the registered file exists and is a genuine PNG, then register it again. |
| 글자가 작거나 생략됨 · Small/omitted text | 띠를 높이거나 템플릿을 줄입니다. 미리보기 경고를 확인합니다. / Increase footer height or shorten templates; inspect preview warnings. |
| 출력 크기 초과 · Dimension limit | 사진 본체 크기를 줄입니다. 한 변 32768 px 및 100 MP, WebP 한 변 16383 px 제한은 프레임을 포함합니다. / Reduce body size; limits include the frame: 32768 px per side and 100 MP, or 16383 px per side for WebP. |

## 자료 이용과 참고 · Asset rights and references

소스 코드의 MIT 라이선스는 사진 저작권이나 제조사 로고·글꼴의 사용 권한을 포함하지 않습니다. 사진·로고·폰트는 사용자가 해당 권한과 이용 조건을 확인합니다. 이 저장소의 예시는 사용자가 제공한 왜가리 사진을 긴 변 최대 1600 px로 줄이고 내부 메타데이터를 제거한 것입니다. [예시 사진 권리 표시](images/LICENSE.md)는 모든 권리를 유보하며 원본 사진은 포함하지 않습니다. 참조 사이트의 사진/코드/로고를 복사하지 않습니다.

The source's MIT license does not cover photograph copyrights or rights to manufacturer logos/fonts. Check each asset's usage terms. Examples use the user's heron photograph, reduced to a maximum 1600 px long edge with embedded metadata removed. [Example photo rights](images/LICENSE.md) are reserved, and the original photo is not included. Reference-site photographs, code, and logos are not copied.

- [Adobe Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/): 내보내기 서비스 및 Lua SDK · export services and Lua SDK.
- [Adobe Lightroom Classic export settings](https://helpx.adobe.com/lightroom-classic/help/exporting-photos-basic-workflow.html): 기본 내보내기 흐름 · native export workflow.
- [ExifTool metadata copying FAQ](https://exiftool.org/faq.html): 태그 복사와 형식별 제약 · tag copying and format limitations.
- [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md): 번들 도구 버전·출처·라이선스 · bundled tool versions, provenance, and licenses.
