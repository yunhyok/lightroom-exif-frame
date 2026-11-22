# Lightroom EXIF Frame (`v0.2.0`)

Lightroom Classic (Windows x64, SDK 13+)용 **고품질 EXIF 프레임 & 시대별 제조사 CI 로고** 내보내기 플러그인입니다.

![Windows checks and package](https://github.com/yunhyok/lightroom-exif-frame/actions/workflows/ci.yml/badge.svg)

---

## 주요 특징 (v0.2.0)

### 1. Lightroom 기본 **내보내기 위치(Export Location)** 및 **파일 이름 지정(File Naming)** 네이티브 연동
- 내보내기 창 상단에 Lightroom의 기본 **내보내기 위치**(`특정 폴더`, `원본 사진과 동일한 폴더`, `나중에 폴더 선택`, `바탕 화면/사진/문서` 표준 폴더, `하위 폴더에 넣기`, `이 카탈로그에 추가 / 스택`, `기존 파일 처리: 덮어쓰기/새 이름/건너뛰기/묻기`)와 **파일 이름 지정**(토큰 프리셋, 소문자/대문자 확장자) 패널을 그대로 사용합니다.
- **파일 형식(JPG / PNG 8·16-bit / WebP 무손실·손실), 색공간, 품질** 설정은 하단의 **EXIF Frame — 파일 형식 및 출력 설정** 섹션으로 깔끔하게 분리되어 있습니다.

### 2. 카메라 **출시·생산연도 기반** 순수 벡터 제조사 CI 로고 (61개 브랜드 · 93개 시대 CI)
- 시스템 글꼴로 흉내 낸 어색한 제조사 이름 대신, **`resvg` 기반 순수 벡터 SVG(`<path>`, `<rect>`, `<circle>` 등)**로 정교하게 제작된 제조사 공식 CI 로고를 합성합니다.
- 촬영 일시(`DateTimeOriginal`)가 아니라 **카메라·스마트폰·액션캠·드론 기종(`Model`)의 실제 출시/생산연도**에 맞춰 해당 시대의 로고를 자동 선택합니다.
  - 예: 2026년에 촬영한 `KODAK C875` 사진이라도 카메라가 출시된 2006년 기준 **Kodak 2006–2016 둥근 레드 워드마크**가 표시됩니다.
  - 모델이 미등록되었거나 신형 기종인 경우 **최신 공식 CI**로 자동 폴백됩니다.
- 전통 카메라/중형/시네마(Canon, Nikon, Sony / Sony α, Minolta, Konica Minolta, Fujifilm, Olympus, OM System, Panasonic, LUMIX, Pentax, Ricoh, Leica, Sigma, Hasselblad, Kodak, Samsung, Polaroid, Phase One, Mamiya, Contax, Casio, Epson, Kyocera, Yashica, Rollei, ZEISS, Pixii, RED, ARRI, Blackmagic Design), 스마트폰(Apple, Google, Xiaomi, Huawei, OPPO, vivo, OnePlus, LG, GoldStar, Sony Ericsson, Motorola, Nokia, HONOR, realme, NOTHING, ASUS, HTC, SHARP, BlackBerry, Pantech), 액션캠/360/드론(GoPro, DJI, Insta360, RICOH THETA, Garmin, Autel Robotics, Parrot, SJCAM, AKASO) 총 **61개 제조사 · 93개 시대 CI**를 내장합니다.
- 원하는 경우 브랜드별 **사용자 PNG/SVG 로고 오버라이드**도 플러그인 설정에서 등록·해제할 수 있습니다.
- 세부 역사·색상표·변천 기준은 [docs/BRAND_LOGO_HISTORY.md](docs/BRAND_LOGO_HISTORY.md)를 참고하세요.

### 3. 16가지 프레임 테마 및 세밀한 메타데이터/비율 제어 (`exif-frame.yuru.cam` 호환)
- **16개 테마**: `strap`, `simple`, `one_line`, `two_line`, `shot_on_one_line`, `shot_on_two_line`, `film`, `monitor`, `lightroom`, `just_frame`, `cinemascope`, `poster`, `tip`, `custom_one_line`, `custom_two_line`, `none`
- **색상/외관**: `Auto`(테마 최적 기본값), `Light`, `Dark`, `Custom (#RRGGBB)` + 다크 배경 자동 CI 명도 보정 + 모노크롬(`mono`) 모드
- **비율 & 레이아웃**: `Free`(원본 비율) 및 9가지 고정 비율(`1:1`, `4:5`, `5:4`, `3:4`, `4:3`, `2:3`, `3:2`, `16:9`, `9:16`), **자르기 없이 여백 맞추기(`Fit without crop`)**, 사진 내부 오버레이(`Overlay inside photo`), 컴팩트 HUD(`Compact`), 글꼴 스타일(`Normal`/`Italic`), 정렬(`Left`/`Center`/`Right`), 투명도, 그림자
- **초점거리 & 날짜 표기**: 35mm 환산(`equivalent`), 실제 초점거리(`actual`), 배율 계산(`ratio` × `crop_factor`), **10가지 날짜 표기 형식**(한국어·일본어·영어·ISO 등)
- **표시 토글 및 직접 지정**: 제조사/바디/렌즈/노출 개별 숨김 및 직접 수정, `{label}`, `{era}` 확장 토큰

### 4. 16-bit Q16 LCMS 색관리 & 안전한 메타데이터 보존
- ImageMagick 7 Q16 LCMS로 `sRGB`, `Adobe RGB`, `ProPhoto RGB` 색공간과 **16-bit PNG 무손실 바디 픽셀**을 정확히 유지합니다.
- ExifTool 13.59로 원본 XMP/IPTC/EXIF 및 얼굴 영역(MWG Region) 좌표를 프레임 오프셋에 맞춰 변환하며, Lightroom의 GPS/인물 정보 제거(`Remove Person Info`) 정책을 존중하고 원본 사진 덮어쓰기를 원천 차단합니다.

---

## 설치 및 사용 방법

1. [Releases](https://github.com/yunhyok/lightroom-exif-frame/releases)에서 최신 `Lightroom-EXIF-Frame-0.2.0-Windows-x64.zip`을 다운로드하고 압축을 풉니다. (SHA-256 체크섬 검증 권장)
2. Lightroom Classic → **파일(File) → 플러그인 관리자(Plug-in Manager) → 추가(Add)**에서 `LightroomExifFrame.lrplugin` 폴더를 선택합니다.
3. **내보내기(Export)** 대화상자 최상단의 **내보낼 위치(Export To)**에서 **EXIF Frame**을 선택합니다.
4. 자세한 사용법과 설정 설명은 [docs/USER_GUIDE.md](docs/USER_GUIDE.md)를 확인하세요.

---

## 개발 및 로컬 빌드

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\fetch_vendor.py

# 전체 단위/통합 테스트 실행
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 배포용 Windows x64 플러그인 ZIP + SHA256SUMS 생성
.\.venv\Scripts\python.exe scripts\build.py
```

- 헬퍼 CLI 프로토콜 명세: [docs/protocol.md](docs/protocol.md)
- 제조사 로고 변천사: [docs/BRAND_LOGO_HISTORY.md](docs/BRAND_LOGO_HISTORY.md)
- 서드파티 라이선스 고지: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
