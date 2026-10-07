# 검증 기록 · Validation

검증일: 2026-10-08. 자동 검사, 실제 Lightroom 검사, 미실행 항목을 구분합니다.

Validation date: 2026-10-08. Automated checks, live Lightroom checks, and outstanding checks are recorded separately.

## 자동 검사 · Automated checks

Windows 11 x64, CPython 3.12.12, ImageMagick 7.1.2-32 Q16, ExifTool 13.59에서 **31개 검사 통과** (`unittest`, 132.870 s).

**31 checks passed** on Windows 11 x64 with CPython 3.12.12, ImageMagick 7.1.2-32 Q16, and ExifTool 13.59 (`unittest`, 132.870 s).

| 범위 · Scope | 확인 내용 · Evidence |
|---|---|
| Lua 5.1 | UTF-8 JSON, presets/settings, visible metadata, TIFF16 settings, sequential processing, cancellation, cleanup, error propagation; SDK substituted in these tests |
| RGB16 | Non-8-bit gradient values survive framing and PNG16 export exactly; cropped photo bytes equal input RGB16 bytes |
| Color | Embedded ICC bytes preserved; Adobe RGB/ProPhoto preview converted to sRGB after full layout |
| Formats | JPG/PNG/WebP signatures, PNG IHDR depth, lossless WebP decoded RGB equals prepared sRGB8 |
| Metadata | Filtered-TIFF-only copying, Unicode caption, native XMP priority, IPTC→XMP, region remapping, dimensions/orientation, stripped GPS/person fields remain absent |
| Edge cases | Portrait/panorama, long/literal text, missing metadata, invalid/corrupt logo, zero padding, Unicode/special-character paths, collisions, invalid jobs, WebP size limit |
| Frozen package | Copied bundle executes with only System32 on PATH and Python/Perl development overrides removed; JPG/PNG16/WebP, ICC, metadata, exact pixels, failure cleanup verified |

배포 EXE 검사는 개발 도구 검색 경로를 제거한 현재 PC에서 수행했습니다. 새 Windows 설치 환경 검사를 대신하지 않습니다. Lua 모의 검사는 Lightroom UI 검사를 대신하지 않습니다.

The frozen-bundle test used a restricted environment on the current PC, not a pristine Windows installation. Lua substitute tests do not stand in for Adobe UI verification.

## 실제 Lightroom Classic 15.6 · Live Lightroom Classic 15.6

사용자의 기존 카탈로그와 원본 사진을 수정하지 않고 별도 테스트 카탈로그와 복사한 사진으로 검사했습니다.

Checks use a separate test catalog and copied photograph, leaving the original catalog and source photo unchanged.

| 항목 · Check | 결과 · Result |
|---|---|
| Plug-in registration / Korean UI | Passed: export provider and settings display in Lightroom |
| JPG native export | Passed: 1920×1280 photo body + 140 px footer → 1920×1420; sRGB ICC and camera metadata verified |
| PNG16 native export | Passed: 1920×1420, PNG IHDR 16-bit, sRGB IEC61966-2.1 |
| Preview | Passed: Lightroom-rendered selected photo appears in the plug-in modal with the same frame layout |
| Preset creation | Passed: native export preset saved with PNG16 selection |

추가 실제 SDK 검증 결과는 릴리스 확정 전에 이 문서에 반영합니다.

Additional live SDK results are recorded here before release finalization.

## 남은 검사 · Outstanding checks

- Windows UI 100% / 150% / 200% 배율 전체 조합은 아직 확인하지 않았습니다. All three display-scale configurations have not yet been verified.
- 실제 얼굴 영역이 있는 사진의 Lightroom 인물 정보 제외 동작은 아직 확인하지 않았습니다. Lightroom removal with a real face-region fixture has not yet been verified.
- 별도 Python/ImageMagick 설치가 없는 새 Windows OS에서의 수동 설치 검사는 아직 수행하지 않았습니다. Manual installation on a pristine Windows OS has not yet been performed.

## 재현 · Reproduce

```powershell
python scripts/fetch_vendor.py
python -m unittest discover -s tests -v
python scripts/build.py
python -m unittest discover -s tests -p test_package.py -v
```

`tests/lightroom_smoke.lua`는 개발자용 실제 SDK 하네스이며 배포 플러그인에 포함되지 않습니다. 파일 머리말의 제한된 테스트 카탈로그 경로를 따릅니다. `work/`의 카탈로그, 원본 크기 결과, 개인 경로는 공개하지 않습니다.

`tests/lightroom_smoke.lua` is a developer-only live SDK harness, excluded from the shipping plug-in. Follow its guarded test-catalog instructions. Test catalogs, full-size outputs, and personal paths under `work/` are not published.
