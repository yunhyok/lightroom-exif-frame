# 검증 기록 · Validation

검증일: 2026-10-08. 자동 검사, 실제 Lightroom 검사, 미실행 항목을 구분합니다.

Validation date: 2026-10-08. Automated checks, live Lightroom checks, and outstanding checks are recorded separately.

## 자동 검사 · Automated checks

Windows 11 x64, CPython 3.12.12, ImageMagick 7.1.2-32 Q16, ExifTool 13.59에서 **39개 검사 통과** (`unittest`, 155.699 s).

**39 checks passed** on Windows 11 x64 with CPython 3.12.12, ImageMagick 7.1.2-32 Q16, and ExifTool 13.59 (`unittest`, 155.699 s).

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

최종 EXE의 패키지 검사 2개도 별도로 통과했습니다(20.306 s). ExifTool은 번들 Perl을 직접 실행하고 UTF-8 인수를 표준 입력으로 전달하므로 한글 설치 경로를 지원하며 설치 폴더에 임시 파일을 쓰지 않습니다. 영문 Windows의 GitHub CI에서도 빌드 후 패키지 검사 2개가 통과했습니다.

The final EXE separately passed both frozen-package checks (20.306 s). ExifTool runs through its bundled Perl with UTF-8 arguments on stdin, supporting Unicode installation paths without writing temporary files beside the installed runtime. The English-Windows GitHub CI also passed both post-build package checks.

Helper SHA-256: `41ef9e96ebfc3fd38128c075c6777b778676d281a2724f21cb78f0dde07231fa`.

CI의 사전 빌드 단계에서는 아직 없는 EXE와 기본 제공되지 않는 Adobe RGB/ProPhoto 프로파일 검사를 건너뜁니다. EXE는 빌드 후 검사하며 광색역 프로파일은 위 로컬 전체 검사와 아래 실제 Lightroom 검사에서 확인했습니다.

The CI pre-build phase skips the not-yet-built EXE and unavailable Adobe RGB/ProPhoto profiles. Its EXE checks run after building; wide-gamut profiles were covered by the complete local suite and live Lightroom checks below.

## 실제 Lightroom Classic 15.6 · Live Lightroom Classic 15.6

사용자의 기존 카탈로그와 원본 사진을 수정하지 않고 별도 테스트 카탈로그와 복사한 사진으로 검사했습니다.

Checks use a separate test catalog and copied photograph, leaving the original catalog and source photo unchanged.

| 항목 · Check | 결과 · Result |
|---|---|
| Plug-in registration / Korean UI | Passed: export provider and settings display in Lightroom |
| JPG native export | Passed: 1920×1280 photo body + 140 px footer → 1920×1420; sRGB ICC and camera metadata verified |
| PNG16 native export | Passed: 1920×1420, PNG IHDR 16-bit, sRGB IEC61966-2.1 |
| WebP native export | Passed: two photos exported as lossless WebP, 1920×1420 and 1280×2013, both sRGB |
| Preview | Passed: Lightroom-rendered selected photo appears in the plug-in modal with the same frame layout |
| Preset save/restore | Passed: native PNG16 preset saved; after changing to WebP, selecting the preset restored PNG16 and the saved output settings |
| Batch cancellation | Passed: four photos selected, cancel clicked while a helper was running; that photo finished, the dialog reported two saved files, and the remaining two were skipped |

실제 Lightroom SDK로 렌더한 TIFF와 최종 파일을 별도로 다시 읽어 **13개 내보내기 조합, 473개 비교 항목을 모두 통과**했습니다. 공개 가능한 비교 결과는 [validation-results.json](validation-results.json)에 기록합니다. 성공 알림만으로 판정하지 않고 파일 시그니처, 비트 깊이, ICC, 메타데이터와 사진 영역 픽셀을 확인합니다.

An independent reader passed **all 473 comparisons across 13 live SDK export combinations** against Lightroom-rendered TIFFs. See [validation-results.json](validation-results.json) for sanitized results. Checks inspect signatures, bit depth, ICC, metadata, and photo-body pixels rather than relying on success dialogs.

| SDK 범위 · SDK scope | 확인 내용 · Evidence |
|---|---|
| Format / ICC | JPG and PNG16 in sRGB, Adobe RGB, and ProPhoto RGB; lossless sRGB WebP |
| Metadata modes | All, copyright only, copyright and contact only, camera excluded, GPS excluded, person excluded |
| Unicode | Korean/Japanese caption and title, hierarchical keywords, UTF-8 IPTC/XMP |
| Pixel comparison | Four PNG16 photo regions and one lossless WebP photo region exactly equal the corresponding TIFF-derived RGB bytes |
| Virtual copy | Nontrivial crop, quarter-turn rotation, exposure/contrast changes; Simple frame around the Lightroom-rendered result |

Lightroom 15.6은 인물 정보 제거 설정에도 테스트용 `PersonInImage` 값을 중간 TIFF에 남겼습니다. 플러그인은 이 옵션이 선택되면 명시적 인물 태그와 얼굴 영역을 추가 제거하며, 최종 파일에서 해당 값이 없음을 확인했습니다. 일반 캡션·작가명·키워드에서 사람 이름을 추측하여 삭제하지 않습니다. 실제 얼굴 영역 사진은 아래 미검증 항목에 남깁니다.

Lightroom 15.6 retained the seeded `PersonInImage` value in its TIFF despite the person-removal setting. When requested, the helper explicitly removes typed person fields and face regions; the final file's absence was verified. It does not guess names in ordinary captions, artists, or keywords. A real face-region photograph remains an outstanding check below.

## 남은 검사 · Outstanding checks

- Windows UI 100% / 150% / 200% 배율 전체 조합은 아직 확인하지 않았습니다. All three display-scale configurations have not yet been verified.
- 실제 얼굴 영역이 있는 사진의 Lightroom 인물 정보 제외 동작은 아직 확인하지 않았습니다. Lightroom removal with a real face-region fixture has not yet been verified.
- 별도 Python/ImageMagick 설치가 없는 새 Windows OS에서의 수동 설치 검사는 아직 수행하지 않았습니다. Manual installation on a pristine Windows OS has not yet been performed.

이 PC에서 Windows 설정 앱은 자동화 도구가 제어할 수 있는 창을 제공하지 않았고, Windows Sandbox 및 별도 VM 실행 환경도 확인되지 않았습니다. 배율·새 OS 검사를 통과로 처리하지 않았습니다.

Windows Settings did not expose a targetable automation window, and Windows Sandbox or another VM runtime was unavailable on this PC. Display-scale and pristine-OS checks are not claimed as passed.

## 재현 · Reproduce

```powershell
python scripts/fetch_vendor.py
python -m unittest discover -s tests -v
python scripts/build.py
python -m unittest discover -s tests -p test_package.py -v
```

`tests/lightroom_smoke.lua`는 개발자용 실제 SDK 하네스이며 배포 플러그인에 포함되지 않습니다. 파일 머리말의 제한된 테스트 카탈로그 경로를 따릅니다. `work/`의 카탈로그, 원본 크기 결과, 개인 경로는 공개하지 않습니다.

`tests/lightroom_smoke.lua` is a developer-only live SDK harness, excluded from the shipping plug-in. Follow its guarded test-catalog instructions. Test catalogs, full-size outputs, and personal paths under `work/` are not published.
