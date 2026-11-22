local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrPrefs = import 'LrPrefs'
local LrProgressScope = import 'LrProgressScope'
local LrShell = import 'LrShell'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'

local Frame = require 'Frame'
local bind = LrView.bind
local prefs = LrPrefs.prefsForPlugin()

local Export = {
    exportPresetFields = Frame.fields,
    canExportVideo = false,
    hideSections = { 'fileSettings', 'video', 'postProcessing' },
    allowFileFormats = { 'TIFF' },
    allowColorSpaces = { 'sRGB', 'AdobeRGB', 'ProPhotoRGB' },
}

local function choices(pairs)
    local out = {}
    for _, pair in ipairs(pairs) do
        out[#out + 1] = { title = pair[1], value = pair[2] }
    end
    return out
end

local function note(f, text)
    return f:static_text { title = text, width_in_chars = 68, height_in_lines = 2, wrap = true }
end

local function field(f, label, key, width, enabled)
    return f:row {
        spacing = f:label_spacing(),
        f:static_text { title = label, width_in_chars = 18 },
        f:edit_field { value = bind(key), width_in_chars = width or 40, immediate = true, enabled = enabled },
    }
end

local function sliderNumber(f, label, key, minimum, maximum, precision, suffix, p, enabled)
    return f:row {
        spacing = f:label_spacing(),
        f:static_text { title = label, width_in_chars = 18 },
        f:slider { value = bind(key), min = minimum, max = maximum, width = 180, enabled = enabled },
        f:edit_field {
            value = bind(key),
            width_in_chars = 6,
            precision = precision or 2,
            enabled = enabled,
            validate = function(_, value)
                local n = tonumber(value)
                if n and n >= minimum and n <= maximum then return true, n end
                return false, Frame.T('Enter a number within the displayed range.', '표시된 범위의 숫자를 입력해 주세요.', p)
            end,
        },
        f:static_text { title = suffix or ('(' .. minimum .. '-' .. maximum .. ')') },
    }
end

local function popup(f, label, key, items, enabled)
    return f:row {
        spacing = f:label_spacing(),
        f:static_text { title = label, width_in_chars = 18 },
        f:popup_menu { value = bind(key), items = items, enabled = enabled, width_in_chars = 30 },
    }
end

local function sectionFileSettings(f, p)
    local T = function(en, ko) return Frame.T(en, ko, p) end
    local qualityEnabled = bind('ef_qualityEnabled')
    return {
        title = T('EXIF Frame — File Settings', 'EXIF Frame — 파일 형식 및 출력 설정'),
        bind_to_object = p,
        synopsis = bind('ef_format'),
        spacing = f:control_spacing(),
        popup(f, T('Format', '파일 형식'), 'ef_format', choices({
            { 'JPG', 'jpg' },
            { 'PNG', 'png' },
            { 'WebP', 'webp' },
        })),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Quality', '품질'), width_in_chars = 18 },
            f:slider { value = bind('ef_quality'), min = 1, max = 100, integral = true, width = 180, enabled = qualityEnabled },
            f:edit_field { value = bind('ef_quality'), width_in_chars = 5, precision = 0, enabled = qualityEnabled },
            f:checkbox {
                title = T('WebP lossless', 'WebP 무손실'),
                value = bind('ef_lossless'),
                enabled = bind { key = 'ef_format', transform = function(v) return v == 'webp' end },
            },
        },
        popup(f, T('Color space', '색공간'), 'ef_colorSpace', choices({
            { 'sRGB', 'sRGB' },
            { 'Adobe RGB', 'AdobeRGB' },
            { 'ProPhoto RGB', 'ProPhotoRGB' },
        }), bind { key = 'ef_format', transform = function(v) return v ~= 'webp' end }),
        popup(f, T('PNG depth', 'PNG 비트 깊이'), 'ef_pngDepth', choices({
            { '8-bit', 8 },
            { '16-bit', 16 },
        }), bind { key = 'ef_format', transform = function(v) return v == 'png' end }),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('After export', '내보내기 후'), width_in_chars = 18 },
            f:checkbox { title = T('Show in Windows Explorer', 'Windows 탐색기에서 파일 표시'), value = bind('ef_revealInExplorer') },
        },
        note(f, T(
            'Export destination, file renaming, collision handling, and catalog reimport are controlled by Lightroom Export Location / File Naming panels above.',
            '저장 위치, 하위 폴더, 파일 이름 지정, 기존 파일 처리 및 카탈로그 추가는 상단의 Lightroom 기본 [내보내기 위치] 및 [파일 이름 지정] 패널을 따릅니다.')),
    }
end

local function sectionThemeLayout(f, p)
    local T = function(en, ko) return Frame.T(en, ko, p) end
    local customColors = bind { key = 'ef_appearance', transform = function(v) return v == 'custom' end }
    return {
        title = T('EXIF Frame — Theme & Layout', 'EXIF Frame — 프레임 테마 및 레이아웃'),
        bind_to_object = p,
        synopsis = bind('ef_theme'),
        spacing = f:control_spacing(),
        popup(f, T('Theme (16)', '테마 (16종)'), 'ef_theme', Frame.themeItems(p)),
        popup(f, T('Appearance', '색상 스타일'), 'ef_appearance', choices({
            { T('Auto (Theme Default)', '자동 (테마 기본)'), 'auto' },
            { T('Light', '밝게'), 'light' },
            { T('Dark', '어둡게'), 'dark' },
            { T('Custom', '사용자 지정'), 'custom' },
        })),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Custom #RRGGBB', '사용자 색상'), width_in_chars = 18 },
            f:edit_field { value = bind('ef_background'), width_in_chars = 9, immediate = true, enabled = customColors },
            f:edit_field { value = bind('ef_text'), width_in_chars = 9, immediate = true, enabled = customColors },
            f:edit_field { value = bind('ef_secondary'), width_in_chars = 9, immediate = true, enabled = customColors },
        },
        popup(f, T('Aspect ratio', '비율 (Aspect Ratio)'), 'ef_aspectRatio', Frame.aspectRatioItems(p)),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Frame options', '프레임 옵션'), width_in_chars = 18 },
            f:checkbox { title = T('Fit without crop', '자르기 없이 여백 맞추기'), value = bind('ef_noCrop') },
            f:checkbox { title = T('Overlay inside photo', '사진 내부에 프레임 배지'), value = bind('ef_paddingInside') },
            f:checkbox { title = T('Compact HUD', '컴팩트 HUD'), value = bind('ef_compact') },
        },
        sliderNumber(f, T('Band height', '하단 띠 높이'), 'ef_bandPercent', 1, 40, 2, '% (1-40)', p),
        sliderNumber(f, T('Padding', '외곽 여백'), 'ef_paddingPercent', 0, 20, 2, '% (0-20)', p),
        sliderNumber(f, T('Font size', '글꼴 크기'), 'ef_fontPercent', 0.2, 10, 2, '% (0.2-10)', p),
        sliderNumber(f, T('Logo width', '로고 너비'), 'ef_logoPercent', 1, 50, 2, '% (1-50)', p),
        f:row {
            spacing = f:control_spacing(),
            f:static_text { title = T('Font file', '글꼴 파일'), width_in_chars = 18 },
            f:edit_field { value = bind('ef_fontPath'), width_in_chars = 34, immediate = true },
            f:push_button { title = T('Browse…', '찾기…'), action = function() Frame.browse(p, 'ef_fontPath', 'font') end },
        },
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Style & align', '글꼴 스타일·정렬'), width_in_chars = 18 },
            f:popup_menu { value = bind('ef_fontStyle'), items = choices({
                { T('Normal', '보통'), 'normal' },
                { T('Italic', '기울임 (Italic)'), 'italic' },
            }), width_in_chars = 16 },
            f:popup_menu { value = bind('ef_textAlign'), items = choices({
                { T('Left', '왼쪽'), 'left' },
                { T('Center', '가운데'), 'center' },
                { T('Right', '오른쪽'), 'right' },
            }), width_in_chars = 13 },
        },
        sliderNumber(f, T('Text opacity', '글자 불투명도'), 'ef_textAlpha', 0.05, 1.0, 2, '(0.05-1.0)', p),
        sliderNumber(f, T('Text shadow', '글자 그림자'), 'ef_shadowSize', 0, 50, 1, '(0-50)', p),
    }
end

local function sectionLogoCI(f, p)
    local T = function(en, ko) return Frame.T(en, ko, p) end
    local manualEnabled = bind('ef_manualEnabled')
    return {
        title = T('EXIF Frame — Camera Logo & Historical CI', 'EXIF Frame — 제조사 로고 및 연대별 CI'),
        bind_to_object = p,
        synopsis = bind('ef_logoMode'),
        spacing = f:control_spacing(),
        popup(f, T('Logo CI mode', '로고 CI 모드'), 'ef_logoMode', choices({
            { T('Auto by Release Year CI', '출시연도 기반 시대별 CI 자동 선택'), 'auto_era' },
            { T('Auto (Latest CI Always)', '자동 감지 (항상 최신 CI)'), 'auto_latest' },
            { T('Manual Brand & Era', '수동 브랜드 / 시대 지정'), 'manual_era' },
            { T('Brand Text Only', '텍스트 브랜드명만 표시'), 'text_only' },
            { T('No Logo', '로고 표시 안 함'), 'none' },
        })),
        popup(f, T('Logo color style', '로고 색상 스타일'), 'ef_logoStyle', choices({
            { T('Official Brand Colors', '공식 브랜드 CI 컬러'), 'brand' },
            { T('Monochrome (Match Text)', '단색 모노크롬 (글자색 맞춤)'), 'mono' },
        })),
        popup(f, T('Manual brand', '수동 브랜드'), 'ef_manualBrand', Frame.brandItems(p, true), manualEnabled),
        popup(f, T('Manual CI era', '수동 CI 시대'), 'ef_manualEra', bind('ef_eraItems'), manualEnabled),
        f:row {
            spacing = f:control_spacing(),
            f:push_button {
                title = T('Detect Selected Photo Brand & Era', '선택 사진 브랜드·연대 감지'),
                action = function() Frame.inspectBrand(p) end,
            },
            f:static_text { title = bind('ef_detectedBrandSummary'), width_in_chars = 42 },
        },
        f:row {
            spacing = f:control_spacing(),
            f:static_text { title = T('Custom override', '사용자 로고 교체'), width_in_chars = 18 },
            f:popup_menu { value = bind('ef_logoBrand'), items = Frame.brandItems(p, false), width_in_chars = 22 },
            f:push_button { title = T('Register PNG/SVG…', 'PNG/SVG 등록…'), action = function() Frame.registerLogo(p) end },
            f:push_button { title = T('Remove', '제거'), action = function() Frame.removeLogo(p) end },
        },
        f:static_text { title = bind('ef_customLogosSummary'), width_in_chars = 68, height_in_lines = 2, wrap = true },
    }
end

local function sectionMetadataTemplates(f, p)
    local T = function(en, ko) return Frame.T(en, ko, p) end
    local ratioEnabled = bind { key = 'ef_focalMode', transform = function(v) return v == 'ratio' end }
    return {
        title = T('EXIF Frame — Metadata & Templates', 'EXIF Frame — 메타데이터 및 문구 템플릿'),
        bind_to_object = p,
        spacing = f:control_spacing(),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Visible fields', '표시 항목'), width_in_chars = 18 },
            f:checkbox { title = T('Make', '제조사'), value = bind('ef_showMake') },
            f:checkbox { title = T('Model', '카메라'), value = bind('ef_showModel') },
            f:checkbox { title = T('Lens', '렌즈'), value = bind('ef_showLens') },
            f:checkbox { title = T('Exposure', '노출'), value = bind('ef_showExposure') },
        },
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Focal length', '초점거리'), width_in_chars = 18 },
            f:popup_menu {
                value = bind('ef_focalMode'),
                items = choices({
                    { T('35mm equivalent', '35mm 환산'), 'equivalent' },
                    { T('Actual', '실제 초점거리'), 'actual' },
                    { T('Actual x Crop Factor', '실제 x 크롭 팩터'), 'ratio' },
                }),
                width_in_chars = 24,
            },
            f:static_text { title = T('Factor:', '배율:') },
            f:edit_field { value = bind('ef_cropFactor'), width_in_chars = 6, precision = 2, enabled = ratioEnabled },
        },
        popup(f, T('Date format', '날짜 표기 형식'), 'ef_dateNotation', Frame.dateNotationItems(p)),
        field(f, T('Override make', '제조사 직접 지정'), 'ef_overrideMake'),
        field(f, T('Override model', '카메라명 직접 지정'), 'ef_overrideModel'),
        field(f, T('Override lens', '렌즈명 직접 지정'), 'ef_overrideLens'),
        field(f, T('Artist override', '작가명 직접 지정'), 'ef_artist'),
        f:row {
            spacing = f:label_spacing(),
            f:static_text { title = T('Label / Divider', '라벨 / 구분자'), width_in_chars = 18 },
            f:edit_field { value = bind('ef_label'), width_in_chars = 26, immediate = true },
            f:edit_field { value = bind('ef_divider'), width_in_chars = 6, immediate = true },
        },
        field(f, T('Slot 1 (Upper L)', '영역 1 (좌상단)'), 'ef_template1'),
        field(f, T('Slot 2 (Lower L)', '영역 2 (좌하단)'), 'ef_template2'),
        field(f, T('Slot 3 (Upper R)', '영역 3 (우상단)'), 'ef_template3'),
        field(f, T('Slot 4 (Lower R)', '영역 4 (우하단)'), 'ef_template4'),
        f:row {
            spacing = f:control_spacing(),
            f:popup_menu { value = bind('ef_tokenTarget'), items = choices({
                { T('Slot 1', '영역 1'), 'ef_template1' },
                { T('Slot 2', '영역 2'), 'ef_template2' },
                { T('Slot 3', '영역 3'), 'ef_template3' },
                { T('Slot 4', '영역 4'), 'ef_template4' },
            }) },
            f:popup_menu { value = bind('ef_token'), items = choices({
                { '{iso}', '{iso}' }, { '{focal}', '{focal}' }, { '{focal35}', '{focal35}' },
                { '{aperture}', '{aperture}' }, { '{shutter}', '{shutter}' }, { '{date}', '{date}' },
                { '{make}', '{make}' }, { '{model}', '{model}' }, { '{lens}', '{lens}' },
                { '{artist}', '{artist}' }, { '{label}', '{label}' }, { '{era}', '{era}' },
            }) },
            f:push_button {
                title = T('Append token', '토큰 추가'),
                action = function()
                    local key = p.ef_tokenTarget
                    p[key] = (p[key] or '') .. p.ef_token
                end,
            },
            f:push_button {
                title = T('Reset defaults', '기본값 복원'),
                action = function() Frame.resetDefaults(p) end,
            },
        },
    }
end

local function sectionPreview(f, p)
    local T = function(en, ko) return Frame.T(en, ko, p) end
    return {
        title = T('EXIF Frame — Preview & Language', 'EXIF Frame — 미리보기 및 언어'),
        bind_to_object = p,
        spacing = f:control_spacing(),
        popup(f, T('UI language', '플러그인 언어'), 'ef_language', choices({
            { T('Auto (Follow Lightroom)', '자동 (Lightroom 언어 따름)'), 'auto' },
            { '한국어', 'ko' },
            { 'English', 'en' },
        })),
        f:row {
            spacing = f:control_spacing(),
            f:push_button {
                title = T('Preview selected photo…', '선택한 사진 미리보기…'),
                enabled = bind { key = 'ef_previewBusy', transform = function(v) return not v end },
                action = function() Frame.preview(p) end,
            },
            f:static_text { title = bind('ef_previewStatus'), width_in_chars = 44 },
        },
        note(f, T(
            'A fresh Lightroom 16-bit TIFF uses current Image Sizing and Output Sharpening. Preview is sRGB8 PNG; final export preserves your chosen profile and bit depth.',
            '현재 이미지 크기 조정·샤프닝 설정으로 16-bit TIFF를 생성해 합성합니다. 미리보기는 sRGB8 PNG이며, 실제 내보내기는 선택한 색공간과 비트 깊이를 유지합니다.')),
    }
end

function Export.startDialog(p)
    Frame.initialize(p)
    local function validate()
        p.ef_qualityEnabled = p.ef_format == 'jpg' or (p.ef_format == 'webp' and not p.ef_lossless)
        p.ef_manualEnabled = p.ef_logoMode == 'manual_era'
        p.LR_cantExportBecause = Frame.validate(p, false)
    end
    for _, fieldInfo in ipairs(Frame.fields) do
        p:addObserver(fieldInfo.key, validate)
    end
    for _, nativeKey in ipairs({
        'LR_export_destinationType',
        'LR_export_destinationPathPrefix',
        'LR_export_useSubfolder',
        'LR_export_destinationPathSuffix',
    }) do
        p:addObserver(nativeKey, validate)
    end
    p:addObserver('ef_manualBrand', function()
        p.ef_eraItems = Frame.eraItemsForBrand(p.ef_manualBrand, p)
        local validEra = false
        for _, item in ipairs(p.ef_eraItems) do
            if item.value == p.ef_manualEra then
                validEra = true
                break
            end
        end
        if not validEra then p.ef_manualEra = '' end
    end)
    p:addObserver('ef_logoBrand', function()
        p.ef_logoPath = Frame.logoStatus(p.ef_logoBrand)
    end)
    p:addObserver('ef_language', function()
        prefs.language = p.ef_language
    end)
    validate()
end

function Export.updateExportSettings(p)
    Frame.renderSettings(p)
end

function Export.sectionsForBottomOfDialog(f, p)
    return {
        sectionFileSettings(f, p),
        sectionThemeLayout(f, p),
        sectionLogoCI(f, p),
        sectionMetadataTemplates(f, p),
        sectionPreview(f, p),
    }
end

function Export.processRenderedPhotos(context, exportContext)
    local p = Frame.snapshot(exportContext.propertyTable)
    local err = Frame.validate(p, false)
    if err then error(err) end
    local T = function(en, ko) return Frame.T(en, ko, p) end
    local title = T('Exporting EXIF Frame', 'EXIF Frame 내보내기')
    local renderProgress = exportContext:configureProgress { title = title, renderPortion = 1 }
    local progress = LrProgressScope { title = title, functionContext = context }
    progress:setCancelable(true)
    renderProgress:setCancelable(true)

    local total = math.max(1, exportContext.exportSession:countRenditions())
    progress:setPortionComplete(0, total)
    local workDir = Frame.temporary(context)
    local session = { chosenFolder = nil, applyAllCollision = nil, revealedPath = nil, warnings = {} }
    local completed, processed, canceledByDialog = 0, 0, false

    for _, rendition in exportContext:renditions { progressScope = renderProgress, stopIfCanceled = true } do
        if progress:isCanceled() or renderProgress:isCanceled() or canceledByDialog then
            progress:cancel(); renderProgress:cancel(); break
        end
        local rendered, path = rendition:waitForRender()
        if rendered then
            if not progress:isCanceled() and not renderProgress:isCanceled() and not canceledByDialog then
                progress:setCaption(T('Framing ', '프레임 합성 중: ') .. tostring(path))
                LrTasks.yield()
                if not progress:isCanceled() and not renderProgress:isCanceled() and not canceledByDialog then
                    local ok, resOrErr, status = LrTasks.pcall(function()
                        return Frame.exportRendition(p, rendition, path, workDir, session)
                    end)
                    if ok then
                        if status == 'canceled' then
                            canceledByDialog = true
                            progress:cancel()
                            renderProgress:cancel()
                        elseif resOrErr then
                            completed = completed + 1
                            for _, warning in ipairs(resOrErr.warnings or {}) do
                                session.warnings[#session.warnings + 1] = tostring(warning)
                            end
                        end
                    else
                        rendition:uploadFailed(tostring(resOrErr))
                    end
                end
            end
            LrFileUtils.delete(path)
        else
            rendition:uploadFailed(tostring(path))
        end
        processed = processed + 1
        progress:setPortionComplete(processed, total)
        if progress:isCanceled() or renderProgress:isCanceled() then
            progress:cancel(); renderProgress:cancel(); break
        end
    end

    if p.ef_revealInExplorer and session.revealedPath and LrFileUtils.exists(session.revealedPath) == 'file' then
        LrTasks.pcall(function() LrShell.revealInShell(session.revealedPath) end)
    end
    if progress:isCanceled() then
        LrDialogs.message('EXIF Frame', T('Canceled after finishing the current photo. Saved files: ',
            '현재 사진을 마친 후 취소했습니다. 저장한 파일: ') .. tostring(completed), 'info')
    end
    if #session.warnings > 0 then
        LrDialogs.message('EXIF Frame', T('Export warnings:\n', '내보내기 참고 사항:\n')
            .. table.concat(session.warnings, '\n'), 'warning')
    end
    progress:done()
    renderProgress:done()
end

return Export
