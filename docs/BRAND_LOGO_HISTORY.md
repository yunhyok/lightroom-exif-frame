# Camera, Smartphone, Action Camera & Drone Brand CI / Logo History Reference

본 문서는 `Lightroom EXIF Frame`의 **제조사별 공식 CI/로고 변천사 및 출시 연도 기반 매핑 엔진**(`helper/data/brands.json`, `helper/data/cameras.json`)의 설계 근거를 정리한 기술 레퍼런스입니다.

## 1. 핵심 설계 원칙

1. **Pure Vector Geometry (시스템 폰트·래스터 미사용)**: 모든 내장 CI 로고는 공식 브랜드 벡터 마크 원형(`scripts/logo_sources.json` · `scripts/fetch_official_logos.py`)을 기반으로 `<text>`/`<image>` 없는 순수 기하학 SVG 경로(`<path>`, `<rect>`, `<circle>`, `<ellipse>`, `<polygon>`)로 정규화하고 알파 바운딩 박스 기준 `viewBox` 크롭을 적용하여 OS/폰트 의존 없이 임의 해상도에서 선명하게 렌더링한다.
2. **Release Year vs Capture Year**: 로고 시대는 **촬영 일시(`DateTimeOriginal`)가 아니라 카메라/스마트폰 기종의 출시·생산 연도**를 기준으로 판정한다. (예: 2012년 출시 Galaxy S3로 2025년에 촬영했더라도 2012년형 Blue Oval CI 사용).
3. **Unknown Model Fallback**: 데이터베이스와 코드 규칙에서 출시 연도를 판정할 수 없는 미등록·신형 기종은 **반드시 해당 브랜드의 최신 CI**를 사용한다. (`DateTimeOriginal`은 출시 연도 폴백으로 사용하지 않는다.)
4. **Make / Model 교차 판정 규칙**:
   - `RICOH IMAGING COMPANY, LTD.` + `Model` 내 `PENTAX` → `pentax`
   - `RICOH` + `Model` 내 `THETA` → `ricoh-theta`
   - `JK Imaging, Ltd.` → `kodak`
   - `Arashi Vision` → `insta360`
   - `SEIKO EPSON CORP.` → `epson`
   - `SAMSUNG TECHWIN` / `samsung` → `samsung`
   - `OM Digital Solutions` → `om-system` (단, 과도기 모델 `OM-1`은 법인 기준 `om-system` 2021 CI 적용, 수동 오버라이드로 `olympus` 전환 가능)
   - `Panasonic` + `DMC-` / `DC-` / `LUMIX` → `lumix`
   - `SONY` + `DSLR-` / `SLT-` / `NEX-` / `ILCA-` / `ILCE-` / `ZV-` / `ILME-` → `sony-alpha`
   - `LGE` / `Motorola` / `Huawei` + `Model` 내 `Nexus` → `google`
   - `Hasselblad` + `L1D-20c` / `L2D-20c` / `L3D-100c` → `hasselblad` (2018 / 2021 / 2025 출시 연도 정밀 매핑)

---

## 2. 전통 디지털 카메라 · 미러리스 · DSLR · 중형 · 시네마 브랜드

| Brand ID | 시대 (Start–End) | 주요 조형 및 타이포그래피 특징 | 공식 대표 HEX | 대표 EXIF 기종 / 경계 참고 |
|---|---|---|---|---|
| `canon` | `1935` (1935–1955)<br>`1956` (1956–현재) | 1935 초기 세리프성 혼재 훅 `C` / 1956 정통 안쪽 훅 `C` 굵은 레드 워드마크 | `#CC0000` | 디지털 전 시대(PowerShot, EOS D30–R5 II) `1956` 동일 워드마크 |
| `nikon` | `1968` (1968–1987)<br>`1988` (1988–2002)<br>`2003` (2003–현재) | 1968 카메쿠라 트랙 타원 / 1988 굵은 이탤릭 블랙 / 2003 노란 사각 대각 광선 + 이탤릭 | `#FFE100`, `#000000` | **2003.04.01 전환**: D1(1999)·D100(2002)=1988, D2H(2003)·D70(2004)~Z9=2003 |
| `sony` | `1973` (1973–현재) | Clarendon 계열 고대비 슬랩 세리프 `SONY` | `#000000` | Cyber-shot `DSC-*` 전 세대 |
| `sony-alpha` | `2006` (2006–현재) | `SONY` + 유기적 소문자 `α` 심볼 (미놀타 마운트 계승) | `#E34234`, `#000000` | `DSLR-A100`(2006)~`ILCE-*`, `ZV-*`, `ILME-FX*` |
| `minolta` | `1981` (1981–2003) | 솔 배스 5줄 스트라이프 블루 글로브 + `minolta` | `#005BAC` | `DiMAGE 7`/`A1` (2001–2003) |
| `konica-minolta` | `2003` (2003–2006) | 솔 배스 글로브 계승 + `KONICA MINOLTA` | `#005BAC` | `DiMAGE A2`, `DYNAX/MAXXUM 7D`(2004), `5D`(2005) |
| `fujifilm` | `1980` (1980–2006)<br>`2006` (2006–현재) | 1980 그린/레드 `FUJI` 필름 박스 / 2006 박스 제거 + 4번째 글자 `I` 대각 레드 노치 | `#FB0020`, `#01916D` | **2006.10.01 전환**: FinePix S1–S3 Pro·F30=1980, S5 Pro(2007)·X·GFX=2006 |
| `olympus` | `1970` (1970–2000)<br>`2001` (2001–2021) | 1970 단독 블루 워드마크 / 2001 Opto-Digital 골드 언더라인 바 추가 | `#08107B`, `#EBB700` | Camedia 초기=1970, Four Thirds `E-1`~`E-M1 III`·`E-P7`(2021.06)=2001 |
| `om-system` | `2021` (2021–현재) | 정사각 테두리 안 2단 `OM` / `SYSTEM` (1970s OM 오마주) | `#000000` | `OM Digital Solutions` (`OM-1`, `OM-5`, `TG-7`, `OM-3`) |
| `panasonic` | `1971` (1971–현재) | 기하학 굵은 산세리프 `Panasonic` (2008 사명 단일화) | `#0041C0` | 일반 Panasonic 기종 |
| `lumix` | `2001` (2001–현재) | 레드 스타일라이즈드 `L` + 모던 `LUMIX` | `#E60012`, `#000000` | `DMC-*`(2001–2016) & `DC-*`(2017–현재) |
| `pentax` | `1957` (1957–1986)<br>`1987` (1987–현재) | 1957 `ASAHI PENTAX` 2단 / 1987 촘촘한 볼드 레드/블랙 `PENTAX` | `#FF0013` | 디지털 `*ist D`(2003)~`K-3 III`(2021) 전원 `1987` CI |
| `ricoh` | `1986` (1986–2005)<br>`2005` (2005–현재) | 1986 솔리드 `R`+아웃라인 `ICOH` / 2005 곡선형 솔리드 레드 `RICOH` | `#D61B3E` | **2005.09 전환**: Caplio 초기=1986, `GR DIGITAL`(2005.10)~`GR IIIx`=2005 |
| `leica` | `1976` (1976–1987)<br>`1986` (1988–현재) | 레드 닷 내부 `Leitz` 스크립트 → 1986 사명변경 / 1988 Solms 이전 후 `Leica` 스크립트 | `#E20612` | 모든 디지털 라이카(Digilux, M8–M11, Q, SL)=`1986` 레드 닷 |
| `sigma` | `1961` (1961–2012)<br>`2012` (2012–2024)<br>`2025` (2025–현재) | 1961 이탤릭 `SIGMA` / 2012 Global Vision 정직립 / **2025.02.24** Sigma Serif + 기하 `Σ` 심볼 | `#000000` | SD9–SD1(2012.08)=1961, Merrill/Quattro/fp/fp L=2012, **`SIGMA BF`(2025.02)=2025** |
| `hasselblad` | `1990` (1990–2015)<br>`2015` (2015–현재) | 1990 묵직한 `H`+블록 `HASSELBLAD` / 2015 와이드트래킹 미니멀 `HASSELBLAD` | `#000000` | H1D–H5D=1990, `X1D-50c`(2016)/`H6D`/`X2D`/`907X`=2015 |
| `kodak` | `1987` (1987–2005)<br>`2006` (2006–2016)<br>`2016` (2016–현재) | 1987 K-Box + `Kodak` / 2006 둥근 레드 워드마크 / 2016 복원 K-Box + 세로 `KODAK` | `#FFB700`, `#ED0000` | DCS·초기 EasyShare=1987, 후기 EasyShare·초기 PIXPRO=2006, 2016.10+ PIXPRO=2016 |
| `samsung` | `1993` (1993–2014)<br>`2015` (2015–현재) | 1993 기울어진 `#1428A0` 블루 타원 / **2015 타원 폐지 플랫 단독 워드마크** | `#1428A0` | Galaxy S1–S5·NX10–NX1(2014)=1993 타원, Galaxy S6(2015)·NX500(2015)~S26=2015 워드마크 |
| `polaroid` | `1977` (1977–2016)<br>`2017` (2017–2019)<br>`2020` (2020–현재) | 5색 스펙트럼 바 ↔ `Polaroid Originals` ↔ 2020 풀 스펙트럼 통합 복원 | 5색 스펙트럼 (`#D60026`~`#00AEEF`) | 각 시기 즉석·디지털 카메라 |
| 단일 CI 카메라 브랜드 | `phase-one`, `mamiya`, `contax`, `casio`, `epson`, `kyocera`, `yashica`, `rollei`, `zeiss`, `pixii`, `red`, `arri`, `blackmagic` | 각 제조사 고유 CI 워드마크/엠블럼 벡터화 | 브랜드별 고유 HEX | Phase One `#000000`, Mamiya `#FC001B`, Zeiss `#0F2DB3`/`#0072EF`, RED `#DC2026`, ARRI `#005BA6`, Blackmagic `#FFA200` 등 |

---

## 3. 스마트폰 · 액션캠 · 360 카메라 · 드론 브랜드

| Brand ID | 시대 (Start–End) | 주요 조형 특징 | 공식 대표 HEX | EXIF `Make`/`Model` 패턴 |
|---|---|---|---|---|
| `apple` | `1977` (1977–1998)<br>`2007` (2007–2012)<br>`2013` (2013–현재) | 6색 무지개 사과 / 크롬 입체 광택 사과 / 플랫 미니멀 사과 | `#A3AAAE`, `#000000` | `Apple` + 마케팅명(`iPhone 4S`, `iPhone 16 Pro`, `iPhone Air`) |
| `google` | `2010` (2010–2015)<br>`2015` (2015–현재) | Catull 세리프 4색 `Google` / Product Sans 4색 `G` + `Google` | `#4285F4`, `#EA4335`, `#FBBC05`, `#34A853` | Nexus 4–6=2010 (`LGE`/`Motorola`), Nexus 5X/6P·Pixel 1–11=2015 |
| `xiaomi` | `2014` (2014–2020)<br>`2021` (2021–현재) | 직각 라운드 오렌지 박스 `MI` / **2021.03.30** Kenya Hara 초타원 Squircle `MI` | `#FF6700` | `^(?:M)?(\d{2})(\d{2})...` 코드에서 연도 자동 추출 |
| `huawei` | `2006` (2006–2017)<br>`2018` (2018–현재) | 3D 그라데이션 8꽃잎 / **2018.03(P20)** 플랫 `#CF0A2C` 8꽃잎 + 직선 `HUAWEI` | `#CF0A2C` | `EVA`/`VTR`(2016–17)=2006, `EML`/`CLT`/`VOG`/`ELS`/`LNA`/`ADY`(2018+)=2018 |
| `oppo` | `2013` (2013–2018)<br>`2019` (2019–현재) | 넓은 라운드 그린 `oppo` / Pentagram 기하 대칭 `oppo` | `#2D683D` | `OPPO` |
| `vivo` | `2009` (2009–2018)<br>`2019` (2019–현재) | 둥근 블루 `vivo` / 샤프 기하 비비드 블루 `#415FFF` `vivo` | `#415FFF` | `vivo` |
| `oneplus` | `2013` (2013–2019)<br>`2020` (2020–현재) | 직각 `1+`+좁은 `ONEPLUS` / 곡선 `1+`+넓은 `ONEPLUS` | `#F50514` | `OnePlus` |
| `lg` / `goldstar` | `goldstar` (1983–1994)<br>`1995` (1995–2013)<br>`2014` (2014–2022)<br>`2023` (2023–현재) | GoldStar 마크 / 3D 마젠타 얼굴 / 플랫 마젠타 / Active Red `#FD312E` | `#A50034`, `#FD312E` | `LGE` / `LG Electronics` / `GoldStar` |
| `sony-ericsson` | `2001` (2001–2012) | Liquid Energy 그린/실버 오브 + 워드마크 | `#00A651`, `#C0C0C0` | `Sony Ericsson` (2012년 Sony Mobile 통합 이후 `SONY`) |
| `motorola` | `1955` (1955–2012)<br>`2013` (2013–현재) | Batwing `M` + 볼드 이탤릭 `MOTOROLA` / 플랫 서클 `M` + 소문자 `motorola` | `#005FBE`, `#E1140A` | `Motorola` / `motorola` |
| `nokia` | `1992` (1992–2022)<br>`2023` (2023–현재) | 클래식 볼드 블루 `NOKIA` / **MWC 2023** 분절 기하학 `NOKIA` | `#124191`, `#005AFF` | `Nokia` / `HMD Global` |
| `honor` | `2013` (2013–2018)<br>`2018` (2018–현재) | 소문자 `honor` / 대문자 `HONOR` | `#000000`, 블루 그라데이션 | `HONOR` / `Honor` |
| `gopro` | `2004` (2004–2011)<br>`2012` (2012–현재) | 초기 볼드 `GoPro` / 4블루 사각(`#00AEEF`~`#005DAC`) + `GoPro` | `#00AEEF`, `#005DAC` | `GoPro` (`HD1`/`HD2` vs `HERO3`–`HERO13`/`GoPro MAX`) |
| `dji` | `2006` (2006–2011)<br>`2012` (2012–현재) | 초기 공학 워드마크 / **2012.11** 중량 사선 컷 블록 `DJI` | `#000000`, `#0971CE` | `DJI` (`FC*`, `OT*`, `OsmoAction*`, `PP-101`) |
| `insta360` | `2015` (2015–2019)<br>`2020` (2020–현재) | 볼드 산세리프+렌즈 / 미니멀 `Insta360` + 세이프티 옐로우 포인트 | `#FFDE00`, `#000000` | `Arashi Vision` / `Insta360` |
| 기타 모바일·드론 | `realme`, `nothing`, `asus`, `htc`, `sharp`, `blackberry`, `pantech`, `ricoh-theta`, `garmin`, `autel`, `parrot`, `sjcam`, `akaso` | 각 브랜드 정통 CI | 브랜드별 고유 HEX | 각 제조사 `Make` 정규화 매핑 |
