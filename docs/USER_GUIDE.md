# Lightroom EXIF Frame 사용자 가이드 (`v0.2.1`)

이 문서는 **Lightroom EXIF Frame** 플러그인의 내보내기 UI 구성, 시대별 제조사 CI 로고 동작 방식, 16가지 프레임 테마 및 메타데이터 옵션을 안내합니다.

---

## 1. 내보내기(Export) 화면 구성

내보내기 대화상자 상단의 **내보낼 위치(Export To)** 드롭다운에서 **EXIF Frame**을 선택하면 아래 순서대로 패널이 표시됩니다.

### 상단 — Lightroom 기본 패널 (네이티브 그대로 사용)
1. **내보내기 위치 (`Export Location`)**:
   - **특정 폴더(`specificFolder`)**, **원본 사진과 동일한 폴더(`sourceFolder`)**, **나중에 폴더 선택(`chooseLater`)**, Windows 표준 폴더(`바탕 화면`, `사진`, `문서`, `홈`)를 모두 지원합니다.
   - **하위 폴더에 넣기**, **이 카탈로그에 추가(원본 아래/위 스택)**, **기존 파일 처리(새 이름 / 덮어쓰기 / 건너뛰기 / 묻기)** 옵션이 그대로 작동합니다.
   - 보안 및 원본 보호를 위해 기존 파일 처리에서 **덮어쓰기**를 선택하더라도 원본 파일 자체를 덮어쓰는 것은 차단됩니다.
2. **파일 이름 지정 (`File Naming`)**:
   - Lightroom 기본 파일명 변경 템플릿과 일련번호, 확장자 대/소문자(`소문자 .jpg` / `대문자 .JPG`) 규칙이 출력 파일명에 그대로 적용됩니다.

### 하단 — EXIF Frame 전용 5개 섹션
1. **EXIF Frame — 파일 형식 및 출력 설정 (`File Settings`)**
   - **파일 형식**: `JPG`, `PNG`, `WebP`
   - **품질 (`1–100`)**: JPG 및 손실 WebP 압축 품질
   - **WebP 무손실**: 활성화 시 `VP8L` 무손실 인코딩(항상 sRGB 8-bit)
   - **색공간**: `sRGB`, `Adobe RGB`, `ProPhoto RGB` (PNG/JPG에 ICC 프로파일 임베딩)
   - **PNG 비트 깊이**: `8-bit` 또는 `16-bit`
   - **Windows 탐색기에서 파일 표시**: 내보내기 완료 시 생성된 파일 위치 열기

2. **EXIF Frame — 프레임 테마 및 레이아웃 (`Theme & Layout`)**
   - **테마 (16종)**:
     - `Strap`: 하단 흰색/다크 바에 좌우 2행 메타 정보 + 중앙/우측 구분선 & 제조사 벡터 CI 로고
     - `Simple`: 4면 테두리 + 하단 중앙 정렬 다중 행 메타데이터
     - `One Line` / `Two Line`: 깔끔한 1줄 또는 2줄 바 + 구분자(`∙`) + 상단 라벨(`label`) 지원
     - `Shot On (One Line / Two Line)`: 스마트폰/모바일 스타일 `Shot on ...` 배지 레이아웃
     - `Film`: 좌/우 하단 모서리에 클래식 필름 카메라 데이터백 스탬프(주황 LED 톤 기본값) 오버레이
     - `Monitor`: 카메라 뷰파인더/라이브뷰 하단 HUD 4열(`F / shutter / ISO / focal`) (`Compact HUD` 지원)
     - `Lightroom`: 좌측 노출 · 중앙 바디/렌즈 · 우측 날짜 배지 바
     - `Just Frame`: 글자 없이 여백 프레임만 추가
     - `Cinemascope`: 2.35:1 아나모픽 크롭 + 상하 시네마 레터박스
     - `Poster`: 에디토리얼 타이포그래피 & 하단 우측 로고 오버레이
     - `Tip`: 룩북 카드 스타일 중앙 상하단 오버레이
     - `Custom One Line` / `Custom Two Line`: 사용자가 입력한 1~2줄 템플릿을 자유롭게 배치
     - `None`: 프레임 없이 메타데이터 안전 복사 및 포맷 변환만 수행
   - **색상 스타일**: `자동 (Auto)` / `밝게 (Light)` / `어둡게 (Dark)` / `사용자 지정 (Custom #RRGGBB)`
   - **비율 (`Aspect Ratio`)**: `Free`(원본 유지), `1:1`, `4:5`, `5:4`, `3:4`, `4:3`, `2:3`, `3:2`, `16:9`, `9:16`
   - **프레임 옵션**:
     - **자르기 없이 여백 맞추기 (`Fit without crop`)**: 지정 비율에 맞춰 사진을 자르지 않고 배경 여백으로 패딩
     - **사진 내부에 프레임 배지 (`Overlay inside photo`)**: `one_line`, `two_line`, `shot_on_two_line`, `monitor` 등에서 사진 하단 내부에 바/텍스트 오버레이
     - **컴팩트 HUD**: `Monitor` 테마의 HUD 폭을 중앙 50%로 축소
   - **크기/타이포그래피**: 하단 띠 높이(`1–40%`), 외곽 여백(`0–20%`), 글꼴 크기(`0.2–10%`), 로고 너비(`1–50%`), TTF/OTF/TTC 글꼴 선택, `Normal`/`Italic`, 정렬(`Left`/`Center`/`Right`), 글자 불투명도(`0.05–1.0`), 그림자 크기(`0–50`)

3. **EXIF Frame — 제조사 로고 및 연대별 CI (`Camera Logo & Historical CI`)**
   - **로고 CI 모드**:
     - `Auto by Release Year CI` *(기본값)*: 카탈로그 데이터베이스(1,161개 모델) 및 모델명 패턴으로 **카메라 출시연도**를 판별해 그 당시 제조사 CI 로고를 자동 선택합니다. (미등록 신제품은 최신 CI 적용)
     - `Auto (Latest CI Always)`: 연대와 무관하게 해당 브랜드의 최신 CI 로고를 사용합니다.
     - `Manual Brand & Era`: 61개 제조사 × 93개 시대 로고 중 원하는 브랜드와 연대를 직접 선택합니다.
     - `Brand Text Only`: 벡터 CI 대신 텍스트 제조사명만 표시합니다.
     - `No Logo`: 로고 슬롯을 비웁니다.
   - **로고 색상 스타일**: `Official Brand Colors`(브랜드 고유의 컬러; 다크 프레임에서는 어두운 남색/녹색 명도를 자동 보정) 또는 `Monochrome`(프레임 글자색에 맞춤)
   - **선택 사진 브랜드·연대 감지**: 내보내기 전 현재 선택된 사진에 어떤 브랜드·시대 CI가 매칭되는지 즉시 확인합니다.
   - **사용자 로고 교체 (PNG/SVG)**: 특정 제조사의 로고를 사용자가 가진 고해상도 PNG 또는 SVG 파일로 영구 오버라이드합니다.

4. **EXIF Frame — 메타데이터 및 문구 템플릿 (`Metadata & Templates`)**
   - **표시 항목 체크박스**: 제조사(`Make`), 카메라(`Model`), 렌즈(`Lens`), 노출(`Exposure`) 개별 숨김
   - **초점거리**: `35mm 환산(equivalent)`, `실제 초점거리(actual)`, `실제 × 크롭 팩터(ratio)`
   - **날짜 표기 형식 (10종)**: `YYYY/MM/DD HH:MM:SS`, `YYYY-MM-DD HH:MM:SS`, `YYYY년 MM월 DD일 HH시 MM분`, `YYYY年MM月DD日 HH時MM分`, 날짜 전용 4종, `MMM DD, YYYY`, `날짜 숨김`
   - **직접 지정**: 제조사, 모델명, 렌즈명, 작가명, 라벨(`{label}`), 구분자(`divider`)
   - **4영역 템플릿 & 확장 토큰**: `{iso}`, `{focal}`, `{focal35}`, `{aperture}`, `{shutter}`, `{date}`, `{make}`, `{model}`, `{lens}`, `{artist}`, `{label}`, `{era}`

5. **EXIF Frame — 미리보기 및 언어 (`Preview & Language`)**
   - **플러그인 언어**: `자동(Lightroom 언어 따름)` / `한국어` / `English`
   - **선택한 사진 미리보기**: 현재 크기 조정/샤프닝 및 프레임 설정으로 600px sRGB8 미리보기와 감지된 브랜드/시대 CI 요약을 즉시 확인합니다.
