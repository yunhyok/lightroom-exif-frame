local LrApplication = import 'LrApplication'
local LrBinding = import 'LrBinding'
local LrDialogs = import 'LrDialogs'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrFunctionContext = import 'LrFunctionContext'
local LrLocalization = import 'LrLocalization'
local LrPathUtils = import 'LrPathUtils'
local LrPrefs = import 'LrPrefs'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local Json = require 'Json'
local Frame = {}
local prefs = LrPrefs.prefsForPlugin()

local DEFAULT_BRANDS = {
    { id='canon', name='Canon', eras={{id='1935',label='1935-1955 (Early Serif-Hook Wordmark)',label_ko='1935-1955 (초기 세리프 훅 워드마크)'}, {id='1956',label='1956-Present (Classic Canon Red)',label_ko='1956-현재 (클래식 Canon 레드)'}} },
    { id='nikon', name='Nikon', eras={{id='1968',label='1968-1987 (Kamekura Track Oval)',label_ko='1968-1987 (카메쿠라 트랙 타원)'}, {id='1988',label='1988-2002 (Italic Wordmark)',label_ko='1988-2002 (이탤릭 워드마크)'}, {id='2003',label='2003-Present (Yellow Rays Square)',label_ko='2003-현재 (노란 정사각 광선 CI)'}} },
    { id='sony', name='Sony', eras={{id='1973',label='1973-Present (Classic Clarendon Serif)',label_ko='1973-현재 (클래식 세리프 SONY)'}} },
    { id='sony-alpha', name='Sony a', eras={{id='2006',label='2006-Present (SONY + Alpha)',label_ko='2006-현재 (SONY + α 심볼)'}} },
    { id='minolta', name='Minolta', eras={{id='1981',label='1981-2003 (Saul Bass Blue Globe)',label_ko='1981-2003 (솔 배스 블루 글로브)'}} },
    { id='konica-minolta', name='Konica Minolta', eras={{id='2003',label='2003-2006 (Globe + Wordmark)',label_ko='2003-2006 (통합 글로브 CI)'}} },
    { id='fujifilm', name='Fujifilm', eras={{id='1980',label='1980-2006 (Green Film Box CI)',label_ko='1980-2006 (그린 필름박스 CI)'}, {id='2006',label='2006-Present (Notched-I Wordmark)',label_ko='2006-현재 (레드 노치 I 워드마크)'}} },
    { id='olympus', name='Olympus', eras={{id='1970',label='1970-2000 (Solid Blue Wordmark)',label_ko='1970-2000 (단독 블루 워드마크)'}, {id='2001',label='2001-2021 (Opto-Digital Gold Bar)',label_ko='2001-2021 (골드 언더라인 CI)'}} },
    { id='om-system', name='OM System', eras={{id='2021',label='2021-Present (Stacked Frame Badge)',label_ko='2021-현재 (사각 프레임 2단 배지)'}} },
    { id='panasonic', name='Panasonic', eras={{id='1971',label='1971-Present (Panasonic Blue Wordmark)',label_ko='1971-현재 (파나소닉 블루 워드마크)'}} },
    { id='lumix', name='LUMIX', eras={{id='2001',label='2001-Present (Red L + LUMIX)',label_ko='2001-현재 (레드 L 심볼 + LUMIX)'}} },
    { id='pentax', name='Pentax', eras={{id='1957',label='1957-1986 (ASAHI PENTAX)',label_ko='1957-1986 (아사히 펜탁스)'}, {id='1987',label='1987-Present (Bold PENTAX Red)',label_ko='1987-현재 (볼드 PENTAX 레드)'}} },
    { id='ricoh', name='Ricoh', eras={{id='1986',label='1986-2005 (Outline Block RICOH)',label_ko='1986-2005 (아웃라인 블록 RICOH)'}, {id='2005',label='2005-Present (Curved Solid Red RICOH)',label_ko='2005-현재 (곡선 솔리드 레드 RICOH)'}} },
    { id='leica', name='Leica', eras={{id='1976',label='1976-1987 (Leitz Red Dot)',label_ko='1976-1987 (Leitz 레드 닷)'}, {id='1986',label='1986-Present (Leica Script Red Dot)',label_ko='1986-현재 (Leica 스크립트 레드 닷)'}} },
    { id='sigma', name='Sigma', eras={{id='1961',label='1961-2012 (Italic Block SIGMA)',label_ko='1961-2012 (이탤릭 블록 SIGMA)'}, {id='2012',label='2012-2024 (Global Vision Upright)',label_ko='2012-2024 (Global Vision 정직립)'}, {id='2025',label='2025-Present (Sigma Serif + Emblem)',label_ko='2025-현재 (Sigma Serif + Σ 심볼)'}} },
    { id='hasselblad', name='Hasselblad', eras={{id='1990',label='1990-2014 (Heavy H-Square & Wordmark)',label_ko='1990-2014 (묵직한 H 사각 CI)'}, {id='2015',label='2015-Present (Wide-Tracked Minimalist)',label_ko='2015-현재 (슬림 와이드트래킹 CI)'}} },
    { id='kodak', name='Kodak', eras={{id='1987',label='1987-2005 (Classic K-Box)',label_ko='1987-2005 (클래식 K-Box)'}, {id='2006',label='2006-2016 (Rounded Red Wordmark)',label_ko='2006-2016 (둥근 레드 워드마크)'}, {id='2016',label='2016-Present (Restored K-Box Vertical)',label_ko='2016-현재 (복원 K-Box 세로 KODAK)'}} },
    { id='samsung', name='Samsung', eras={{id='1993',label='1993-2014 (Tilted Blue Ellipse)',label_ko='1993-2014 (기울어진 블루 타원)'}, {id='2015',label='2015-Present (Flat Clean Wordmark)',label_ko='2015-현재 (타원 없는 플랫 워드마크)'}} },
    { id='polaroid', name='Polaroid', eras={{id='1977',label='1977-2016 (Classic 5-Stripe)',label_ko='1977-2016 (클래식 5색 스펙트럼)'}, {id='2017',label='2017-2019 (Polaroid Originals)',label_ko='2017-2019 (Polaroid Originals)'}, {id='2020',label='2020-Present (Unified Spectrum)',label_ko='2020-현재 (통합 스펙트럼 복원)'}} },
    { id='phase-one', name='Phase One', eras={{id='1993',label='1993-Present (Minimalist Sans)',label_ko='1993-현재 (미니멀 산세리프)'}} },
    { id='mamiya', name='Mamiya', eras={{id='1940',label='1940-Present (Classic Mamiya)',label_ko='1940-현재 (클래식 마미야)'}} },
    { id='contax', name='Contax', eras={{id='1974',label='1974-2005 (Porsche Design Tracked Sans)',label_ko='1974-2005 (포르쉐 디자인 와이드 산세리프)'}} },
    { id='casio', name='Casio', eras={{id='1972',label='1972-Present (Bold Geometric CASIO)',label_ko='1972-현재 (기하학 볼드 CASIO)'}} },
    { id='epson', name='Epson', eras={{id='1994',label='1994-Present (Corporate Blue EPSON)',label_ko='1994-현재 (코퍼레이트 블루 EPSON)'}} },
    { id='kyocera', name='Kyocera', eras={{id='1982',label='1982-Present (KC Mark + KYOCERA)',label_ko='1982-현재 (KC 마크 + KYOCERA)'}} },
    { id='yashica', name='Yashica', eras={{id='1983',label='1983-Present (Industrial Block YASHICA)',label_ko='1983-현재 (인더스트리얼 블록 YASHICA)'}} },
    { id='rollei', name='Rollei', eras={{id='1962',label='1962-Present (Bold Geometric Rollei)',label_ko='1962-현재 (볼드 기하학 Rollei)'}} },
    { id='zeiss', name='ZEISS', eras={{id='1991',label='1991-Present (Blue Tessar Frame)',label_ko='1991-현재 (블루 테사 프레임 ZEISS)'}} },
    { id='pixii', name='Pixii', eras={{id='2017',label='2017-Present (Besancon Minimalist)',label_ko='2017-현재 (미니멀 기하학 PIXII)'}} },
    { id='red', name='RED', eras={{id='2005',label='2005-Present (RED Digital Cinema)',label_ko='2005-현재 (RED 시네마 배지)'}} },
    { id='arri', name='ARRI', eras={{id='2010',label='2010-Present (ARRI Blue Engineering)',label_ko='2010-현재 (ARRI 블루 시네마 CI)'}} },
    { id='blackmagic', name='Blackmagic Design', eras={{id='2001',label='2001-Present (Blackmagic Badge)',label_ko='2001-현재 (Blackmagic 배지)'}} },
    { id='apple', name='Apple', eras={{id='1977',label='1977-1997 (Six-Color Rainbow Apple)',label_ko='1977-1997 (6색 무지개 사과)'}, {id='2007',label='2007-2012 (Chrome / Glass 3D Apple)',label_ko='2007-2012 (크롬 글래스 입체 사과)'}, {id='2013',label='2013-Present (Flat Minimalist Apple)',label_ko='2013-현재 (플랫 미니멀 사과)'}} },
    { id='google', name='Google', eras={{id='2010',label='2010-2014 (Catull Serif Google)',label_ko='2010-2014 (Catull 세리프 Google)'}, {id='2015',label='2015-Present (Product Sans + 4-Color G)',label_ko='2015-현재 (Product Sans + 4색 G)'}} },
    { id='xiaomi', name='Xiaomi', eras={{id='2014',label='2014-2020 (Sharp Orange MI Box)',label_ko='2014-2020 (직각 라운드 오렌지 MI)'}, {id='2021',label='2021-Present (Kenya Hara Squircle MI)',label_ko='2021-현재 (하라 켄야 초타원 Squircle MI)'}} },
    { id='huawei', name='Huawei', eras={{id='2006',label='2006-2017 (3D Gradient 8-Petals)',label_ko='2006-2017 (3D 그라데이션 8꽃잎)'}, {id='2018',label='2018-Present (Flat Red 8-Petals)',label_ko='2018-현재 (플랫 레드 8꽃잎)'}} },
    { id='oppo', name='OPPO', eras={{id='2013',label='2013-2018 (Wide Rounded Green)',label_ko='2013-2018 (넓은 라운드 그린 oppo)'}, {id='2019',label='2019-Present (Pentagram Geometric)',label_ko='2019-현재 (펜타그램 기하학 oppo)'}} },
    { id='vivo', name='vivo', eras={{id='2009',label='2009-2018 (Rounded Blue vivo)',label_ko='2009-2018 (둥근 블루 vivo)'}, {id='2019',label='2019-Present (Sharp Geometric #415FFF)',label_ko='2019-현재 (샤프 기하학 비비드 블루)'}} },
    { id='oneplus', name='OnePlus', eras={{id='2013',label='2013-2019 (Sharp 1+ & Condensed)',label_ko='2013-2019 (직각 1+ & 좁은 ONEPLUS)'}, {id='2020',label='2020-Present (Refined 1+ & Wide)',label_ko='2020-현재 (곡선 1+ & 넓은 ONEPLUS)'}} },
    { id='lg', name='LG', eras={{id='1995',label='1995-2013 (3D Glossy Magenta LG)',label_ko='1995-2013 (3D 광택 마젠타 LG)'}, {id='2014',label='2014-2022 (Flat Heritage Magenta LG)',label_ko='2014-2022 (플랫 헤리티지 마젠타 LG)'}, {id='2023',label='2023-Present (Active Red LG)',label_ko='2023-현재 (액티브 레드 LG)'}} },
    { id='goldstar', name='GoldStar', eras={{id='1983',label='1983-1995 (Lucky-GoldStar Emblem)',label_ko='1983-1995 (금성사 럭키금성 심볼)'}} },
    { id='sony-ericsson', name='Sony Ericsson', eras={{id='2001',label='2001-2012 (Liquid Energy Orb)',label_ko='2001-2012 (리퀴드 에너지 오브)'}} },
    { id='motorola', name='Motorola', eras={{id='1955',label='1955-2012 (Batwing + Italic MOTOROLA)',label_ko='1955-2012 (Batwing + 이탤릭 MOTOROLA)'}, {id='2013',label='2013-Present (Circle M + Lowercase)',label_ko='2013-현재 (원형 M + 소문자 motorola)'}} },
    { id='nokia', name='Nokia', eras={{id='1992',label='1992-2022 (Classic Bold Blue NOKIA)',label_ko='1992-2022 (클래식 볼드 블루 NOKIA)'}, {id='2023',label='2023-Present (Segmented Modern NOKIA)',label_ko='2023-현재 (분절 모던 NOKIA)'}} },
    { id='honor', name='HONOR', eras={{id='2013',label='2013-2017 (Lowercase honor)',label_ko='2013-2017 (소문자 honor)'}, {id='2018',label='2018-Present (Uppercase HONOR)',label_ko='2018-현재 (대문자 HONOR)'}} },
    { id='realme', name='realme', eras={{id='2018',label='2018-Present (Pentagram realme)',label_ko='2018-현재 (펜타그램 realme)'}} },
    { id='nothing', name='NOTHING', eras={{id='2020',label='2020-Present (NDot Matrix NOTHING)',label_ko='2020-현재 (도트 매트릭스 NOTHING)'}} },
    { id='asus', name='ASUS', eras={{id='1995',label='1995-Present (Sliced Geometric ASUS)',label_ko='1995-현재 (수평 절개선 ASUS)'}} },
    { id='htc', name='HTC', eras={{id='2008',label='2008-Present (Rounded Green htc)',label_ko='2008-현재 (라운드 그린 htc)'}} },
    { id='sharp', name='SHARP', eras={{id='1960',label='1960s-Present (Bold Red SHARP)',label_ko='1960s-현재 (볼드 레드 SHARP)'}} },
    { id='blackberry', name='BlackBerry', eras={{id='2004',label='2004-Present (7-Dot Berry + Wordmark)',label_ko='2004-현재 (7도트 베리 + 워드마크)'}} },
    { id='pantech', name='Pantech', eras={{id='2005',label='2005-Present (Pantech Blue Block)',label_ko='2005-현재 (팬택 블루 블록)'}} },
    { id='gopro', name='GoPro', eras={{id='2004',label='2004-2011 (Early Bold GoPro)',label_ko='2004-2011 (초기 볼드 GoPro)'}, {id='2012',label='2012-Present (GoPro + 4 Blue Squares)',label_ko='2012-현재 (GoPro + 4색 블루 사각)'}} },
    { id='dji', name='DJI', eras={{id='2006',label='2006-2011 (Early Engineering DJI)',label_ko='2006-2011 (초기 공학 DJI)'}, {id='2012',label='2012-Present (Iconic Heavy Slanted DJI)',label_ko='2012-현재 (중량 사선 컷 DJI)'}} },
    { id='insta360', name='Insta360', eras={{id='2015',label='2015-2019 (Early Lens Swirl + Insta360)',label_ko='2015-2019 (초기 렌즈 심볼 + Insta360)'}, {id='2020',label='2020-Present (Think Bold Minimalist)',label_ko='2020-현재 (Think Bold 옐로우 포인트)'}} },
    { id='ricoh-theta', name='RICOH THETA', eras={{id='2013',label='2013-Present (RICOH THETA)',label_ko='2013-현재 (RICOH THETA)'}} },
    { id='garmin', name='Garmin', eras={{id='2006',label='2006-Present (GARMIN + Blue Delta)',label_ko='2006-현재 (GARMIN + 블루 델타)'}} },
    { id='autel', name='Autel Robotics', eras={{id='2014',label='2014-Present (Autel Orange A-Mark)',label_ko='2014-현재 (Autel 오렌지 심볼)'}} },
    { id='parrot', name='Parrot', eras={{id='1994',label='1994-Present (Minimalist Parrot)',label_ko='1994-현재 (미니멀 Parrot)'}} },
    { id='sjcam', name='SJCAM', eras={{id='2010',label='2010-Present (Monza Red Italic SJCAM)',label_ko='2010-현재 (몬자 레드 이탤릭 SJCAM)'}} },
    { id='akaso', name='AKASO', eras={{id='2013',label='2013-Present (Geometric AKASO)',label_ko='2013-현재 (기하학 AKASO)'}} },
}

local cachedCatalog = nil

local function isKorean(p)
    local lang = (p and p.ef_language) or prefs.language or 'auto'
    if lang == 'ko' then return true end
    if lang == 'en' then return false end
    local ok, current = LrTasks.pcall(function() return LrLocalization.currentLanguage() end)
    return ok and type(current) == 'string' and current:lower():sub(1, 2) == 'ko'
end

local function T(en, ko, p)
    return isKorean(p) and ko or en
end
Frame.text = function(en, ko) return T(en, ko, nil) end
Frame.T = T

local function normalized(path)
    return tostring(path or ''):gsub('\\', '/'):gsub('/+$', ''):lower()
end

local function loadCatalog()
    if cachedCatalog then return cachedCatalog end
    local candidates = {
        LrPathUtils.child(_PLUGIN.path, 'bin/data/brands.json'),
        LrPathUtils.child(LrPathUtils.parent(_PLUGIN.path), 'helper/data/brands.json'),
    }
    for _, path in ipairs(candidates) do
        if LrFileUtils.exists(path) == 'file' then
            local ok, raw = LrTasks.pcall(function() return LrFileUtils.readFile(path) end)
            if ok and type(raw) == 'string' and raw ~= '' then
                local dok, decoded = LrTasks.pcall(function() return Json.decode(raw) end)
                if dok and type(decoded) == 'table' and type(decoded.brands) == 'table' and #decoded.brands > 0 then
                    cachedCatalog = decoded.brands
                    return cachedCatalog
                end
            end
        end
    end
    cachedCatalog = DEFAULT_BRANDS
    return cachedCatalog
end

function Frame.brands()
    return loadCatalog()
end

function Frame.brandItems(p, includeAuto)
    local items = {}
    if includeAuto ~= false then
        items[#items + 1] = { title = T('(Auto Detect)', '(자동 감지)', p), value = '' }
    end
    for _, b in ipairs(loadCatalog()) do
        items[#items + 1] = { title = b.name, value = b.id }
    end
    return items
end

function Frame.eraItemsForBrand(brandId, p)
    local items = {{ title = T('(Latest / Auto)', '(최신 / 자동)', p), value = '' }}
    for _, b in ipairs(loadCatalog()) do
        if b.id == brandId then
            for _, e in ipairs(b.eras or {}) do
                local lbl = isKorean(p) and (e.label_ko or e.label) or e.label
                items[#items + 1] = { title = tostring(e.id) .. ' — ' .. tostring(lbl), value = e.id }
            end
            break
        end
    end
    return items
end

function Frame.themeItems(p)
    return {
        { title = T('Strap (Footer + Logo)', '스트랩 (하단 바 + 로고)', p), value = 'strap' },
        { title = T('Simple (Full Border + Centered)', '심플 (외곽 테두리 + 중앙 텍스트)', p), value = 'simple' },
        { title = T('One Line', '원 라인 (한 줄 정보)', p), value = 'one_line' },
        { title = T('Two Line', '투 라인 (두 줄 정보)', p), value = 'two_line' },
        { title = T('Shot On (One Line + Logo)', 'Shot On (한 줄 + 로고)', p), value = 'shot_on_one_line' },
        { title = T('Shot On (Two Line)', 'Shot On (두 줄)', p), value = 'shot_on_two_line' },
        { title = T('Film (Retro Data Back)', '필름 (레트로 데이터백)', p), value = 'film' },
        { title = T('Monitor (Camera LiveView HUD)', '모니터 (카메라 뷰파인더 HUD)', p), value = 'monitor' },
        { title = T('Lightroom (Bar)', '라이트룸 (하단 메타 바)', p), value = 'lightroom' },
        { title = T('Just Frame (Border Only)', '저스트 프레임 (텍스트 없는 테두리)', p), value = 'just_frame' },
        { title = T('Cinemascope (2.35:1 Letterbox)', '시네마스코프 (2.35:1 레터박스)', p), value = 'cinemascope' },
        { title = T('Poster (Typo Overlay)', '포스터 (타이포그래피 오버레이)', p), value = 'poster' },
        { title = T('Tip (Lookbook Card)', '팁 (룩북 카드 오버레이)', p), value = 'tip' },
        { title = T('Custom One Line', '사용자 지정 (한 줄)', p), value = 'custom_one_line' },
        { title = T('Custom Two Line', '사용자 지정 (두 줄)', p), value = 'custom_two_line' },
        { title = T('None (Metadata Copy Only)', '없음 (프레임 없이 메타데이터 복사)', p), value = 'none' },
    }
end

function Frame.aspectRatioItems(p)
    return {
        { title = T('Original (Free)', '원본 비율 유지 (Free)', p), value = 'free' },
        { title = '1:1 (Instagram Square)', value = '1:1' },
        { title = '4:5 (Instagram Portrait)', value = '4:5' },
        { title = '5:4', value = '5:4' },
        { title = '3:4', value = '3:4' },
        { title = '4:3', value = '4:3' },
        { title = '2:3', value = '2:3' },
        { title = '3:2', value = '3:2' },
        { title = '16:9', value = '16:9' },
        { title = '9:16', value = '9:16' },
    }
end

function Frame.dateNotationItems(p)
    return {
        { title = 'YYYY/MM/DD HH:MM:SS', value = 'slash_datetime' },
        { title = 'YYYY-MM-DD HH:MM:SS', value = 'dash_datetime' },
        { title = 'YYYY년 MM월 DD일 HH시 MM분', value = 'ko_datetime' },
        { title = 'YYYY年MM月DD日 HH時MM分', value = 'ja_datetime' },
        { title = 'YYYY/MM/DD', value = 'slash_date' },
        { title = 'YYYY-MM-DD', value = 'dash_date' },
        { title = 'YYYY년 MM월 DD일', value = 'ko_date' },
        { title = 'YYYY年MM月DD日', value = 'ja_date' },
        { title = 'MMM DD, YYYY', value = 'en_date' },
        { title = T('Hide Date', '날짜 숨김', p), value = 'none' },
    }
end

local winDir = os.getenv('WINDIR') or 'C:\\Windows'
Frame.defaults = {
    ef_language = 'auto',
    ef_outputFolder = '',
    ef_format = 'jpg',
    ef_quality = 95,
    ef_lossless = false,
    ef_colorSpace = 'sRGB',
    ef_pngDepth = 16,
    ef_revealInExplorer = false,
    ef_theme = 'strap',
    ef_appearance = 'auto',
    ef_background = '#ffffff',
    ef_text = '#161616',
    ef_secondary = '#555555',
    ef_aspectRatio = 'free',
    ef_noCrop = false,
    ef_paddingInside = false,
    ef_compact = false,
    ef_fontPath = LrPathUtils.child(winDir, 'Fonts\\malgun.ttf'),
    ef_fontPercent = 1.65,
    ef_bandPercent = 7.3,
    ef_paddingPercent = 1.7,
    ef_logoPercent = 10,
    ef_fontStyle = 'normal',
    ef_textAlign = 'center',
    ef_textAlpha = 1.0,
    ef_shadowSize = 0.0,
    ef_logoMode = 'auto_era',
    ef_logoStyle = 'brand',
    ef_manualBrand = '',
    ef_manualEra = '',
    ef_focalMode = 'equivalent',
    ef_cropFactor = 1.0,
    ef_dateNotation = 'slash_datetime',
    ef_showMake = true,
    ef_showModel = true,
    ef_showLens = true,
    ef_showExposure = true,
    ef_overrideMake = '',
    ef_overrideModel = '',
    ef_overrideLens = '',
    ef_artist = '',
    ef_label = '',
    ef_divider = '∙',
    ef_template1 = 'ISO{iso} {focal}mm F{aperture} {shutter}s',
    ef_template2 = '{date}',
    ef_template3 = '{make} {model}',
    ef_template4 = '{lens}',
}

Frame.fields = {}
for key, default in pairs(Frame.defaults) do
    Frame.fields[#Frame.fields + 1] = { key = key, default = default }
end
table.sort(Frame.fields, function(a, b) return a.key < b.key end)

function Frame.presetFields()
    return Frame.fields
end

function Frame.applyDefaults(p)
    for key, value in pairs(Frame.defaults) do
        if p[key] == nil then p[key] = value end
    end
end

function Frame.logoStatus(brand)
    return (prefs.officialLogos or {})[brand] or ''
end

function Frame.customLogosSummary(p)
    local count, names = 0, {}
    for brand, path in pairs(prefs.officialLogos or {}) do
        if type(path) == 'string' and path ~= '' then
            count = count + 1
            names[#names + 1] = brand
        end
    end
    table.sort(names)
    if count == 0 then
        return T('No custom overrides (61 built-in era CI vector logos active).',
            '사용자 로고 미등록 (내장 61개 브랜드 시대별 벡터 CI 자동 적용).', p)
    end
    return T(tostring(count) .. ' custom override(s): ' .. table.concat(names, ', '),
        '사용자 로고 ' .. tostring(count) .. '개 등록: ' .. table.concat(names, ', '), p)
end

function Frame.initialize(p)
    Frame.applyDefaults(p)
    p.ef_previewBusy = false
    p.ef_previewStatus = ''
    p.ef_logoBrand = p.ef_logoBrand or 'canon'
    p.ef_logoPath = Frame.logoStatus(p.ef_logoBrand)
    p.ef_tokenTarget = p.ef_tokenTarget or 'ef_template1'
    p.ef_token = p.ef_token or '{iso}'
    p.ef_eraItems = Frame.eraItemsForBrand(p.ef_manualBrand, p)
    p.ef_detectedBrandSummary = ''
    p.ef_customLogosSummary = Frame.customLogosSummary(p)
end

function Frame.resetDefaults(p)
    for key, value in pairs(Frame.defaults) do
        if key ~= 'ef_outputFolder' then
            p[key] = value
        end
    end
    p.ef_eraItems = Frame.eraItemsForBrand(p.ef_manualBrand, p)
end

function Frame.snapshot(p)
    local out = {}
    local iterator, state, first
    if type(p.pairs) == 'function' then
        iterator, state, first = p:pairs()
    else
        iterator, state, first = pairs(p)
    end
    for key, value in iterator, state, first do
        out[key] = value
    end
    return out
end

function Frame.helperPath()
    return LrPathUtils.child(LrPathUtils.child(_PLUGIN.path, 'bin'), 'frame-helper.exe')
end

local VALID_THEMES = {
    strap = true, simple = true, one_line = true, two_line = true,
    shot_on_one_line = true, shot_on_two_line = true, film = true,
    monitor = true, lightroom = true, just_frame = true, cinemascope = true,
    custom_one_line = true, custom_two_line = true, poster = true, tip = true, none = true,
}

local VALID_TOKENS = {
    iso = true, focal = true, focal35 = true, aperture = true, shutter = true,
    date = true, make = true, model = true, lens = true, artist = true,
    label = true, era = true,
}

local VALID_DEST_TYPES = {
    specificFolder = true, sourceFolder = true, chooseLater = true,
    desktop = true, documents = true, myDocuments = true,
    pictures = true, myPictures = true, home = true,
}

local function validateSubfolder(suffix, p)
    if type(suffix) ~= 'string' or not suffix:match('%S') then return {} end
    assert(not LrPathUtils.isAbsolute(suffix), T('Subfolder name must be relative.', '하위 폴더 경로는 상대 경로여야 합니다.', p))
    assert(not suffix:find('[:%*%?"<>|\r\n%z]') and not suffix:match('^[\\/]'),
        T('Invalid characters in subfolder name.', '하위 폴더 이름에 사용할 수 없는 문자가 있습니다.', p))
    local parts = {}
    for seg in suffix:gmatch('[^\\/]+') do
        assert(seg ~= '' and seg ~= '.' and seg ~= '..',
            T('Subfolder cannot contain . or .. traversal segments.', '하위 폴더 이름에 . 또는 .. 경로 이동을 사용할 수 없습니다.', p))
        parts[#parts + 1] = seg
    end
    return parts
end

function Frame.validate(p, preview)
    Frame.applyDefaults(p)
    if not WIN_ENV then
        return T('This release supports Windows only.', '이 버전은 Windows만 지원합니다.', p)
    end
    if LrFileUtils.exists(Frame.helperPath()) ~= 'file' then
        return T('Missing bundled frame-helper.exe. Install the complete release ZIP.',
            'frame-helper.exe가 없습니다. 전체 릴리스 ZIP을 설치해 주세요.', p)
    end
    if not preview then
        local destType = p.ef_snap_destType or p.LR_export_destinationType
        if destType ~= nil and destType ~= 'tempFolder' then
            if not VALID_DEST_TYPES[destType] then
                return T('Unsupported Export Location destination type.', '지원되지 않는 내보내기 위치 유형입니다.', p)
            end
            if destType == 'specificFolder' then
                local prefix = p.ef_snap_destPrefix or p.LR_export_destinationPathPrefix
                if type(prefix) ~= 'string' or prefix == '' or not LrPathUtils.isAbsolute(prefix) then
                    return T('Choose an absolute destination folder in Export Location.', '내보내기 위치에서 절대 경로 폴더를 선택해 주세요.', p)
                end
            end
        elseif type(p.ef_outputFolder) ~= 'string' or p.ef_outputFolder == '' or not LrPathUtils.isAbsolute(p.ef_outputFolder) then
            return T('Choose an absolute output folder.', '출력 폴더를 선택해 주세요.', p)
        end
        local useSub = p.ef_snap_useSubfolder
        if useSub == nil then useSub = p.LR_export_useSubfolder end
        local suffix = p.ef_snap_destSuffix
        if suffix == nil then suffix = p.LR_export_destinationPathSuffix end
        if useSub and type(suffix) == 'string' and suffix:match('%S') then
            local okSub, subErr = LrTasks.pcall(validateSubfolder, suffix, p)
            if not okSub then return tostring(subErr) end
        end
    end
    if not ({ jpg = true, png = true, webp = true })[p.ef_format]
        or not VALID_THEMES[p.ef_theme]
        or not ({ sRGB = true, AdobeRGB = true, ProPhotoRGB = true })[p.ef_colorSpace]
        or not ({ auto = true, light = true, dark = true, custom = true })[p.ef_appearance]
        or not ({ actual = true, equivalent = true, ratio = true })[p.ef_focalMode] then
        return T('Invalid saved format, theme, or color setting.', '저장된 형식·테마·색상 설정이 올바르지 않습니다.', p)
    end
    if p.ef_pngDepth ~= 8 and p.ef_pngDepth ~= 16 then
        return T('PNG depth must be 8 or 16.', 'PNG 비트 깊이는 8 또는 16이어야 합니다.', p)
    end
    local ranges = {
        ef_quality = { 1, 100 }, ef_fontPercent = { 0.2, 10 },
        ef_bandPercent = { 1, 40 }, ef_paddingPercent = { 0, 20 },
        ef_logoPercent = { 1, 50 }, ef_cropFactor = { 0.1, 20 },
        ef_textAlpha = { 0.05, 1.0 }, ef_shadowSize = { 0, 50 },
    }
    for key, range in pairs(ranges) do
        local n = tonumber(p[key])
        if not n or n ~= n or n < range[1] or n > range[2] then
            return T('Value out of range: ', '값 범위를 확인해 주세요: ', p) .. key .. ' (' .. range[1] .. '-' .. range[2] .. ')'
        end
    end
    if p.ef_appearance == 'custom' then
        for _, key in ipairs({ 'ef_background', 'ef_text', 'ef_secondary' }) do
            if type(p[key]) ~= 'string' or not p[key]:match('^#%x%x%x%x%x%x$') then
                return T('Custom colors must use #RRGGBB.', '사용자 색상은 #RRGGBB 형식이어야 합니다.', p)
            end
        end
    end
    local needFont = p.ef_theme ~= 'none' and p.ef_theme ~= 'just_frame' and p.ef_theme ~= 'cinemascope'
    if type(p.ef_fontPath) ~= 'string' or not LrPathUtils.isAbsolute(p.ef_fontPath)
        or (needFont and LrFileUtils.exists(p.ef_fontPath) ~= 'file') then
        return T('Choose an existing TTF/OTF font.', '존재하는 TTF/OTF 글꼴을 선택해 주세요.', p)
    end
    for i = 1, 4 do
        local template = p['ef_template' .. i]
        if type(template) ~= 'string' or #template > 2048 then
            return T('Templates must be short text strings.', '템플릿은 짧은 문자열이어야 합니다.', p)
        end
        local stripped = template:gsub('{([a-zA-Z0-9_]+)}', function(name)
            return VALID_TOKENS[name] and '' or '{INVALID}'
        end)
        if stripped:find('[{}]') then
            return T('Unknown or unclosed token in template ', '템플릿에 잘못되거나 닫히지 않은 토큰이 있습니다 ', p) .. tostring(i)
        end
    end
    return nil
end

-- SDK Guide pp.50,65: alter rendering only; preserve snapshot of Export Location & File Naming.
function Frame.renderSettings(p)
    Frame.applyDefaults(p)
    if p.LR_export_destinationType ~= 'tempFolder' then
        p.ef_snap_destType = p.LR_export_destinationType
        p.ef_snap_destPrefix = p.LR_export_destinationPathPrefix
        p.ef_snap_useSubfolder = p.LR_export_useSubfolder
        p.ef_snap_destSuffix = p.LR_export_destinationPathSuffix
        p.ef_snap_collision = p.LR_collisionHandling
        p.ef_snap_reimport = p.LR_reimportExportedPhoto
        p.ef_snap_stack = p.LR_reimport_stackWithOriginal
        p.ef_snap_stackPos = p.LR_reimport_stackWithOriginal_position
        p.ef_snap_extCase = p.LR_extensionCase
    end
    p.LR_export_destinationType = 'tempFolder'
    p.LR_export_useSubfolder = false
    p.LR_reimportExportedPhoto = false
    p.LR_collisionHandling = 'rename'
    p.LR_extensionCase = 'lowercase'
    p.LR_format = 'TIFF'
    p.LR_export_bitDepth = 16
    p.LR_export_colorSpace = p.ef_format == 'webp' and 'sRGB' or p.ef_colorSpace
    p.LRtiff_compressionMethod = 'compressionMethod_ZIP'
end

local function read(photo, method, key)
    local ok, value = LrTasks.pcall(function() return photo[method](photo, key) end)
    if ok and value ~= nil then return value end
    return ''
end

local function number(value)
    local n = tonumber(value)
    return n and string.format('%.6g', n) or ''
end

function Frame.displayMetadata(photo)
    local function raw(key) return read(photo, 'getRawMetadata', key) end
    local function formatted(key) return tostring(read(photo, 'getFormattedMetadata', key)) end
    local shutter = tonumber(raw('shutterSpeed'))
    local shutterText = ''
    if shutter and shutter > 0 then
        local reciprocal, rounded = 1 / shutter, math.floor(1 / shutter + 0.5)
        if shutter < 1 and math.abs(reciprocal - rounded) <= reciprocal * 0.001 then
            shutterText = '1/' .. number(rounded)
        else
            shutterText = number(shutter)
        end
    end
    return {
        make = formatted('cameraMake'),
        model = formatted('cameraModel'),
        lens = formatted('lens'),
        artist = formatted('artist'),
        iso = number(raw('isoSpeedRating')),
        aperture = number(raw('aperture')),
        shutter = shutterText,
        focal = number(raw('focalLength')),
        focal35 = number(raw('focalLength35mm')),
        date = formatted('dateTimeOriginal'),
    }
end

function Frame.temporary(context)
    local base = LrPathUtils.getStandardFilePath('temp'):gsub('[\\/]+$', '')
    local leaf = 'exif-frame-' .. tostring(os.time()) .. '-' .. tostring(math.random(100000, 999999))
    local dir = LrFileUtils.chooseUniqueFileName(LrPathUtils.child(base, leaf))
    local ok, errMsg = LrFileUtils.createAllDirectories(dir)
    assert(ok, T('Cannot create temporary folder.', '임시 폴더를 만들 수 없습니다.') .. (errMsg and (' ' .. tostring(errMsg)) or ''))
    -- Only this newly created direct child is owned/deleted; never delete a user output folder.
    assert(normalized(LrPathUtils.parent(dir)) == normalized(base)
        and LrPathUtils.leafName(dir):match('^exif%-frame%-'))
    context:addCleanupHandler(function() LrFileUtils.delete(dir) end)
    return dir
end

function Frame.command(exe, job, flag)
    local switch = flag or '--job'
    for _, path in ipairs({ exe, job }) do
        assert(LrPathUtils.isAbsolute(path) and not path:find('["\r\n%%!]'),
            T('Unsafe executable/temporary path for Windows shell.', 'Windows 실행 경로에 지원되지 않는 문자가 있습니다.'))
    end
    -- SDK Guide p.48: Windows cmd.exe requires an extra outer pair of quotes.
    return '""' .. exe .. '" ' .. switch .. ' "' .. job .. '""'
end

function Frame.resolveDestinationDir(p, sourcePath, session)
    local destType = p.ef_snap_destType or p.LR_export_destinationType
    local baseDir
    if destType == 'specificFolder' then
        baseDir = p.ef_snap_destPrefix or p.LR_export_destinationPathPrefix
    elseif destType == 'sourceFolder' then
        assert(type(sourcePath) == 'string' and sourcePath ~= '',
            T('Source photo path unavailable for Same Folder as Original.', '원본 사진 경로를 확인할 수 없습니다.', p))
        baseDir = LrPathUtils.parent(sourcePath)
    elseif destType == 'chooseLater' then
        if session and session.chosenFolder then
            baseDir = session.chosenFolder
        else
            local chosen = LrDialogs.runOpenPanel {
                title = T('Choose Export Destination Folder', '내보낼 대상 폴더 선택', p),
                canChooseFiles = false,
                canChooseDirectories = true,
                allowsMultipleSelection = false,
            }
            if not chosen or not chosen[1] then return nil, 'canceled' end
            baseDir = chosen[1]
            if session then session.chosenFolder = baseDir end
        end
    elseif destType == 'desktop' or destType == 'home' or destType == 'documents' or destType == 'pictures' then
        baseDir = LrPathUtils.getStandardFilePath(destType)
    elseif destType == 'myPictures' then
        baseDir = LrPathUtils.getStandardFilePath('pictures')
    elseif destType == 'myDocuments' then
        baseDir = LrPathUtils.getStandardFilePath('documents')
    elseif (destType == nil or destType == 'tempFolder') and type(p.ef_outputFolder) == 'string' and p.ef_outputFolder ~= '' then
        baseDir = p.ef_outputFolder
    else
        error(T('Export destination folder is not configured.', '내보내기 대상 폴더가 설정되지 않았습니다.', p))
    end

    assert(type(baseDir) == 'string' and baseDir ~= '' and LrPathUtils.isAbsolute(baseDir),
        T('Destination folder must be an absolute path.', '내보내기 폴더는 절대 경로여야 합니다.', p))

    local useSub = p.ef_snap_useSubfolder
    if useSub == nil then useSub = p.LR_export_useSubfolder end
    local suffix = p.ef_snap_destSuffix
    if suffix == nil then suffix = p.LR_export_destinationPathSuffix end
    local dir = baseDir
    if useSub and type(suffix) == 'string' and suffix:match('%S') then
        for _, part in ipairs(validateSubfolder(suffix, p)) do
            dir = LrPathUtils.child(dir, part)
        end
    end
    local ok, errMsg = LrFileUtils.createAllDirectories(dir)
    assert(ok, T('Cannot create destination folder: ', '대상 폴더를 만들 수 없습니다: ', p) .. tostring(dir))
    return dir, nil
end

function Frame.buildOutputPath(p, destDir, renderedTiff, preview)
    if preview then
        return LrPathUtils.child(destDir, 'preview.png')
    end
    local baseName = LrPathUtils.removeExtension(LrPathUtils.leafName(renderedTiff))
    local ext = p.ef_format
    local extCase = p.ef_snap_extCase or p.LR_extensionCase
    if extCase == 'uppercase' then
        ext = string.upper(ext)
    end
    return LrPathUtils.child(destDir, baseName .. '.' .. ext)
end

function Frame.resolveCollision(p, targetPath, sourcePath, session)
    if LrFileUtils.exists(targetPath) == false then
        return 'rename'
    end
    local mode = p.ef_snap_collision or p.LR_collisionHandling or 'rename'
    local isSource = type(sourcePath) == 'string' and sourcePath ~= '' and normalized(targetPath) == normalized(sourcePath)
    if mode == 'skip' then
        return 'skip'
    elseif mode == 'overwrite' then
        if isSource then return 'rename' end
        return 'overwrite'
    elseif mode == 'ask' then
        local cached = session and session.applyAllCollision
        if cached then
            if cached == 'overwrite' and isSource then return 'rename' end
            return cached
        end
        local name = LrPathUtils.leafName(targetPath)
        local otherVerb = not isSource and T('Overwrite', '덮어쓰기', p) or nil
        local choice = LrDialogs.confirm(
            T('File already exists: ', '파일이 이미 존재합니다: ', p) .. name,
            T('Choose how to handle existing files for this export.', '기존 파일이 있을 때 처리 방법을 선택하세요.', p),
            T('Use Unique Name', '새 이름 사용', p),
            T('Skip', '건너뛰기', p),
            otherVerb
        )
        local resolved = choice == 'cancel' and 'skip' or (choice == 'other' and not isSource and 'overwrite' or 'rename')
        if session then session.applyAllCollision = resolved end
        return resolved
    end
    return 'rename'
end

local function buildColors(p)
    local colors = p.ef_appearance == 'dark' and { '#171717', '#f4f4f4', '#bbbbbb' }
        or { '#ffffff', '#161616', '#555555' }
    if p.ef_appearance == 'custom' then
        colors = { p.ef_background, p.ef_text, p.ef_secondary }
    end
    return colors
end

local function copyLogosTable()
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do
        logos[brand] = path
    end
    return logos
end

function Frame.run(p, photo, input, dir, preview, explicitOutput, collisionMode)
    local err = Frame.validate(p, preview); assert(not err, err)
    local output = preview and LrPathUtils.child(dir, 'preview.png')
        or explicitOutput
        or Frame.buildOutputPath(p, p.ef_outputFolder, input, false)
    local resultPath = LrPathUtils.child(dir, 'result.json')
    local jobPath = LrPathUtils.child(dir, 'job.json')
    local colors = buildColors(p)
    local job = {
        schema_version = 1,
        input_path = input,
        output_path = output,
        result_path = resultPath,
        source_path = tostring(read(photo, 'getRawMetadata', 'path')),
        remove_person_info = p.LR_removeFaceMetadata == true,
        preview = preview or false,
        preview_max_size = 600,
        format = p.ef_format,
        quality = tonumber(p.ef_quality),
        lossless = p.ef_lossless == true,
        bit_depth = p.ef_format == 'png' and tonumber(p.ef_pngDepth) or 8,
        color_space = p.ef_format == 'webp' and 'sRGB' or p.ef_colorSpace,
        theme = p.ef_theme,
        appearance = p.ef_appearance,
        background_color = colors[1],
        text_color = colors[2],
        secondary_color = colors[3],
        aspect_ratio = p.ef_aspectRatio,
        no_crop = p.ef_noCrop == true,
        padding_inside = p.ef_paddingInside == true,
        compact = p.ef_compact == true,
        font_path = p.ef_fontPath,
        font_percent = tonumber(p.ef_fontPercent),
        band_percent = tonumber(p.ef_bandPercent),
        padding_percent = tonumber(p.ef_paddingPercent),
        logo_percent = tonumber(p.ef_logoPercent),
        font_style = p.ef_fontStyle,
        text_align = p.ef_textAlign,
        text_alpha = tonumber(p.ef_textAlpha),
        shadow_size = tonumber(p.ef_shadowSize),
        logo_mode = p.ef_logoMode,
        logo_style = p.ef_logoStyle,
        manual_brand = p.ef_manualBrand,
        manual_era = p.ef_manualEra,
        focal_mode = p.ef_focalMode,
        crop_factor = tonumber(p.ef_cropFactor),
        date_notation = p.ef_dateNotation,
        show_make = p.ef_showMake ~= false,
        show_model = p.ef_showModel ~= false,
        show_lens = p.ef_showLens ~= false,
        show_exposure = p.ef_showExposure ~= false,
        override_make = p.ef_overrideMake,
        override_model = p.ef_overrideModel,
        override_lens = p.ef_overrideLens,
        artist = p.ef_artist,
        label = p.ef_label,
        divider = p.ef_divider,
        collision_mode = collisionMode or 'rename',
        templates = { p.ef_template1, p.ef_template2, p.ef_template3, p.ef_template4 },
        metadata = Frame.displayMetadata(photo),
        logos = copyLogosTable(),
    }
    if job.source_path == '' or LrFileUtils.exists(job.source_path) ~= 'file'
        or (normalized(job.source_path) == normalized(output) and job.collision_mode == 'overwrite') then
        job.source_path = nil
    end

    local file, message = io.open(jobPath, 'wb'); assert(file, message)
    local ok, writeMessage = file:write(Json.encode(job)); local closed, closeMessage = file:close()
    assert(ok and closed, writeMessage or closeMessage or 'Cannot write helper job')

    local status = LrTasks.execute(Frame.command(Frame.helperPath(), jobPath, '--job'))
    assert(LrFileUtils.exists(resultPath) == 'file',
        T('Helper returned no result file (exit ', '헬퍼 결과 파일이 없습니다 (종료 코드 ', p) .. tostring(status) .. ').')
    local result = Json.decode(LrFileUtils.readFile(resultPath))
    assert(type(result) == 'table' and result.schema_version == 1, 'Invalid helper result schema')
    assert(status == 0 and result.ok == true, tostring(result.error or ('Helper exit ' .. tostring(status))))
    assert(type(result.output_path) == 'string' and LrPathUtils.isAbsolute(result.output_path)
        and LrFileUtils.exists(result.output_path) == 'file', 'Helper output does not exist')
    assert(normalized(LrPathUtils.parent(result.output_path)) == normalized(LrPathUtils.parent(output)), 'Helper output escaped destination')
    assert(LrPathUtils.extension(result.output_path):lower() == (preview and 'png' or p.ef_format), 'Wrong helper output format')
    assert(type(result.width) == 'number' and result.width > 0
        and type(result.height) == 'number' and result.height > 0, 'Invalid helper image dimensions')
    assert(type(result.warnings) == 'table', 'Invalid helper warnings')
    return result
end

local function formatBrandSummary(info, p)
    if type(info) ~= 'table' then return '' end
    local brand = tostring(info.brand_name or '')
    if brand == '' then
        return T('No camera manufacturer detected.', '카메라 제조사를 감지하지 못했습니다.', p)
    end
    local era = isKorean(p) and (info.era_label_ko or info.era_label) or info.era_label
    local yearStr = info.detected_year and (' · ' .. tostring(info.detected_year)) or ''
    local srcStr = info.logo_source and (' [' .. tostring(info.logo_source) .. ']') or ''
    return brand .. ' · ' .. tostring(era or '') .. yearStr .. srcStr
end

function Frame.inspectBrand(p, photo)
    Frame.applyDefaults(p)
    local target = photo or LrApplication.activeCatalog():getTargetPhoto()
    if not target then
        p.ef_detectedBrandSummary = T('No photo selected.', '선택된 사진이 없습니다.', p)
        return nil
    end
    if LrFileUtils.exists(Frame.helperPath()) ~= 'file' then
        p.ef_detectedBrandSummary = T('Helper executable missing.', '헬퍼 실행 파일이 없습니다.', p)
        return nil
    end
    local infoResult
    LrFunctionContext.postAsyncTaskWithContext('EXIF Frame inspect', function(context)
        local dir = Frame.temporary(context)
        local ok, res = LrTasks.pcall(function()
            local jobPath = LrPathUtils.child(dir, 'inspect.json')
            local resultPath = LrPathUtils.child(dir, 'inspect-result.json')
            local colors = buildColors(p)
            local srcPath = tostring(read(target, 'getRawMetadata', 'path'))
            if srcPath == '' or LrFileUtils.exists(srcPath) ~= 'file' then srcPath = nil end
            local job = {
                schema_version = 1,
                result_path = resultPath,
                source_path = srcPath,
                theme = p.ef_theme,
                appearance = p.ef_appearance,
                background_color = colors[1],
                text_color = colors[2],
                secondary_color = colors[3],
                logo_mode = p.ef_logoMode,
                logo_style = p.ef_logoStyle,
                manual_brand = p.ef_manualBrand,
                manual_era = p.ef_manualEra,
                metadata = Frame.displayMetadata(target),
                logos = copyLogosTable(),
            }
            local file, message = io.open(jobPath, 'wb'); assert(file, message)
            local wok, wmsg = file:write(Json.encode(job)); local closed, cmsg = file:close()
            assert(wok and closed, wmsg or cmsg or 'Cannot write inspect job')
            local status = LrTasks.execute(Frame.command(Frame.helperPath(), jobPath, '--inspect'))
            assert(LrFileUtils.exists(resultPath) == 'file', 'Inspect returned no result (exit ' .. tostring(status) .. ')')
            local decoded = Json.decode(LrFileUtils.readFile(resultPath))
            assert(type(decoded) == 'table' and decoded.ok == true, tostring(decoded and decoded.error or 'Inspect failed'))
            return decoded.brand_info
        end)
        if ok and res then
            infoResult = res
            p.ef_detectedBrandSummary = formatBrandSummary(res, p)
        elseif not ok then
            p.ef_detectedBrandSummary = T('Inspect error: ', '감지 오류: ', p) .. tostring(res)
        end
    end)
    return infoResult
end

function Frame.exportRendition(p, rendition, renderedTiff, workDir, session)
    local photo = rendition.photo
    local sourcePath = tostring(read(photo, 'getRawMetadata', 'path'))
    local destDir, cancelStatus = Frame.resolveDestinationDir(p, sourcePath, session)
    if not destDir then
        if cancelStatus == 'canceled' then
            rendition:uploadFailed(T('Export canceled by user.', '사용자가 내보내기를 취소했습니다.', p))
        end
        return nil, cancelStatus
    end
    local outputPath = Frame.buildOutputPath(p, destDir, renderedTiff, false)
    local action = Frame.resolveCollision(p, outputPath, sourcePath, session)
    if action == 'skip' then
        return nil, 'skipped'
    end
    local result = Frame.run(p, photo, renderedTiff, workDir, false, outputPath, action)
    if session and not session.revealedPath then
        session.revealedPath = result.output_path
    end
    local reimport = p.ef_snap_reimport
    if reimport == nil then reimport = p.LR_reimportExportedPhoto end
    if reimport == true then
        local catalog = LrApplication.activeCatalog()
        local stackOriginal = p.ef_snap_stack
        if stackOriginal == nil then stackOriginal = p.LR_reimport_stackWithOriginal end
        local stackPos = p.ef_snap_stackPos or p.LR_reimport_stackWithOriginal_position or 'below'
        local okAdd, addErr = LrTasks.pcall(function()
            catalog:withWriteAccessDo(T('Add EXIF Frame Photo', 'EXIF Frame 사진 카탈로그 추가', p), function()
                catalog:addPhoto(result.output_path, stackOriginal and photo or nil, stackPos)
            end)
        end)
        if not okAdd and addErr and session and session.warnings then
            session.warnings[#session.warnings + 1] = tostring(addErr)
        end
    end
    return result, nil
end

function Frame.preview(p)
    if p.ef_previewBusy then return end
    local settings = Frame.snapshot(p)
    local err = Frame.validate(settings, true)
    if err then
        LrDialogs.message('EXIF Frame', err, 'warning')
        return
    end
    local photo = LrApplication.activeCatalog():getTargetPhoto()
    if not photo then
        LrDialogs.message('EXIF Frame', T('Select a photo first.', '사진을 먼저 선택해 주세요.', p), 'warning')
        return
    end
    p.ef_previewBusy = true
    p.ef_previewStatus = T('Rendering preview…', '프리뷰 렌더링 중…', p)
    LrFunctionContext.postAsyncTaskWithContext('EXIF Frame preview', function(context)
        context:addCleanupHandler(function() p.ef_previewBusy = false end)
        local success, message = LrTasks.pcall(function()
            local dir = Frame.temporary(context)
            Frame.renderSettings(settings)
            settings.LR_exportServiceProvider = 'com.adobe.ag.export.file'
            settings.LR_exportServiceProviderTitle = 'Hard Drive'
            settings.LR_export_destinationType = 'specificFolder'
            settings.LR_export_destinationPathPrefix = dir
            settings.LR_export_useSubfolder = false
            settings.LR_reimportExportedPhoto = false
            settings.LR_export_postProcessing = 'doNothing'
            settings.LR_collisionHandling = 'rename'
            settings.LR_exportFiltersFromThisPlugin = nil
            settings.LR_exportFilters = nil
            settings.LR_cantExportBecause = nil
            local session = LrExportSession { photosToExport = { photo }, exportSettings = settings }
            local result
            for _, rendition in session:renditions() do
                local rendered, path = rendition:waitForRender(); assert(rendered, path)
                result = Frame.run(settings, photo, path, dir, true)
            end
            assert(result, 'No preview rendition')
            p.ef_previewStatus = T('Preview ready.', '프리뷰를 생성했습니다.', p)
            if result.brand_info then
                p.ef_detectedBrandSummary = formatBrandSummary(result.brand_info, p)
            end
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)
            props.image = result.output_path
            local notes = {
                tostring(result.width) .. ' x ' .. tostring(result.height) .. ' px'
                    .. (result.brand_info and ('   |   ' .. formatBrandSummary(result.brand_info, p)) or ''),
                T('Preview is sRGB8; export keeps the selected profile/depth.',
                    '프리뷰는 sRGB8입니다. 실제 출력에는 선택한 색공간·비트 깊이를 적용합니다.', p),
            }
            for _, warning in ipairs(result.warnings or {}) do
                notes[#notes + 1] = tostring(warning)
            end
            LrDialogs.presentModalDialog {
                title = T('EXIF Frame preview', 'EXIF Frame 프리뷰', p),
                actionVerb = T('Close', '닫기', p),
                contents = f:column {
                    bind_to_object = props,
                    spacing = f:control_spacing(),
                    f:picture { value = LrView.bind('image'), width = result.width, height = result.height },
                    f:static_text { title = table.concat(notes, '\n'), width = 600, height_in_lines = 4, wrap = true },
                },
            }
        end)
        if not success then
            p.ef_previewStatus = T('Preview failed.', '프리뷰 생성에 실패했습니다.', p)
            LrDialogs.message('EXIF Frame', tostring(message), 'critical')
        end
    end)
end

function Frame.browse(p, key, kind)
    local paths = LrDialogs.runOpenPanel {
        title = T('Choose a path', '경로 선택', p),
        canChooseFiles = kind ~= 'folder',
        canChooseDirectories = kind == 'folder',
        allowsMultipleSelection = false,
        fileTypes = kind == 'font' and { 'ttf', 'otf', 'ttc' } or nil,
    }
    if paths and paths[1] then p[key] = paths[1] end
end

function Frame.registerLogo(p)
    local paths = LrDialogs.runOpenPanel {
        title = T('Register your custom PNG or SVG logo', '사용자 PNG 또는 SVG 로고 등록', p),
        canChooseFiles = true,
        canChooseDirectories = false,
        allowsMultipleSelection = false,
        fileTypes = { 'png', 'svg' },
    }
    if not paths or not paths[1] then return end
    local ext = LrPathUtils.extension(paths[1]):lower()
    assert((ext == 'png' or ext == 'svg') and LrFileUtils.exists(paths[1]) == 'file',
        'Choose an existing PNG or SVG file')
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do logos[brand] = path end
    local key = p.ef_logoBrand or 'canon'
    logos[key] = paths[1]
    prefs.officialLogos = logos
    p.ef_logoPath = paths[1]
    p.ef_customLogosSummary = Frame.customLogosSummary(p)
end

function Frame.removeLogo(p)
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do
        if brand ~= p.ef_logoBrand then logos[brand] = path end
    end
    prefs.officialLogos = logos
    p.ef_logoPath = ''
    p.ef_customLogosSummary = Frame.customLogosSummary(p)
end

function Frame.diagnostics()
    local brands = Frame.brands()
    local customCount = 0
    for _, v in pairs(prefs.officialLogos or {}) do
        if type(v) == 'string' and v ~= '' then customCount = customCount + 1 end
    end
    local lines = {
        'Lightroom EXIF Frame 0.2.0',
        'Windows: ' .. tostring(WIN_ENV),
        T('Plug-in: ', '플러그인: ') .. _PLUGIN.path,
        'Built-in CI Brands: ' .. tostring(#brands),
        'Custom Logo Overrides: ' .. tostring(customCount),
    }
    for _, file in ipairs({
        'bin/frame-helper.exe',
        'bin/imagemagick/magick.exe',
        'bin/exiftool/exiftool.exe',
        'bin/data/brands.json',
    }) do
        local path = LrPathUtils.child(_PLUGIN.path, file)
        lines[#lines + 1] = (LrFileUtils.exists(path) == 'file' and '[OK] ' or '[MISSING] ') .. file
    end
    lines[#lines + 1] = T('Logo paths are stored only in this plug-in’s preferences.',
        '사용자 로고 경로는 이 플러그인의 환경설정에만 저장됩니다.')
    LrDialogs.message('EXIF Frame', table.concat(lines, '\n'), 'info')
end

return Frame
