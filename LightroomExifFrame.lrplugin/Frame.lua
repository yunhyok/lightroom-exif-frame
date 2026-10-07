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
function Frame.text(en, ko) return LrLocalization.currentLanguage() == 'ko' and ko or en end
local T = Frame.text
Frame.defaults = {
    ef_outputFolder = '', ef_format = 'jpg', ef_quality = 95, ef_lossless = false,
    ef_colorSpace = 'sRGB', ef_pngDepth = 16, ef_theme = 'strap', ef_appearance = 'light',
    ef_background = '#ffffff', ef_text = '#161616', ef_secondary = '#555555',
    ef_fontPath = 'C:\\Windows\\Fonts\\malgun.ttf', ef_fontPercent = 1.65,
    ef_bandPercent = 7.3, ef_paddingPercent = 1.7, ef_logoPercent = 10,
    ef_focalMode = 'equivalent', ef_artist = '',
    ef_template1 = 'ISO{iso} {focal}mm F{aperture} {shutter}s', ef_template2 = '{date}',
    ef_template3 = '{make} {model}', ef_template4 = '{lens}',
}
Frame.fields = {}
for key, default in pairs(Frame.defaults) do
    Frame.fields[#Frame.fields + 1] = { key = key, default = default }
end
table.sort(Frame.fields, function(a, b) return a.key < b.key end)
function Frame.initialize(p)
    for key, default in pairs(Frame.defaults) do if p[key] == nil then p[key] = default end end
    p.ef_previewBusy = false
    p.ef_previewStatus = ''
    p.ef_logoBrand = 'canon'
    p.ef_logoPath = (prefs.officialLogos or {})[p.ef_logoBrand] or ''
    p.ef_tokenTarget = 'ef_template1'; p.ef_token = '{iso}'
end
function Frame.snapshot(p)
    local out = {}
    local iterator, state, first
    if type(p.pairs) == 'function' then iterator, state, first = p:pairs()
    else iterator, state, first = pairs(p) end
    for key, value in iterator, state, first do out[key] = value end
    return out
end
function Frame.helperPath()
    return LrPathUtils.child(LrPathUtils.child(_PLUGIN.path, 'bin'), 'frame-helper.exe')
end
function Frame.validate(p, preview)
    if not WIN_ENV then return T('This release supports Windows only.', '이 버전은 Windows만 지원합니다.') end
    if LrFileUtils.exists(Frame.helperPath()) ~= 'file' then
        return T('Missing bundled frame-helper.exe. Install the complete release ZIP.',
            'frame-helper.exe가 없습니다. 전체 릴리스 ZIP을 설치해 주세요.')
    end
    if not preview and (type(p.ef_outputFolder) ~= 'string' or p.ef_outputFolder == ''
        or not LrPathUtils.isAbsolute(p.ef_outputFolder)) then
        return T('Choose an absolute output folder.', '출력 폴더를 선택해 주세요.')
    end
    if not ({ jpg = true, png = true, webp = true })[p.ef_format]
        or not ({ strap = true, simple = true, none = true })[p.ef_theme]
        or not ({ sRGB = true, AdobeRGB = true, ProPhotoRGB = true })[p.ef_colorSpace]
        or not ({ light = true, dark = true, custom = true })[p.ef_appearance]
        or not ({ actual = true, equivalent = true })[p.ef_focalMode] then
        return T('Invalid saved format, theme, or color setting.', '저장된 형식·테마·색상 설정이 올바르지 않습니다.')
    end
    if p.ef_pngDepth ~= 8 and p.ef_pngDepth ~= 16 then return T('PNG depth must be 8 or 16.', 'PNG 비트 깊이는 8 또는 16이어야 합니다.') end
    local ranges = { ef_quality = {1,100}, ef_fontPercent = {0.2,10},
        ef_bandPercent = {1,40}, ef_paddingPercent = {0,20}, ef_logoPercent = {1,50} }
    for key, range in pairs(ranges) do
        local n = tonumber(p[key])
        if not n or n ~= n or n < range[1] or n > range[2] then
            return T('Value out of range: ', '값 범위를 확인해 주세요: ') .. key .. ' (' .. range[1] .. '–' .. range[2] .. ')'
        end
    end
    if p.ef_appearance == 'custom' then
        for _, key in ipairs({'ef_background','ef_text','ef_secondary'}) do
            if type(p[key]) ~= 'string' or not p[key]:match('^#%x%x%x%x%x%x$') then
                return T('Custom colors must use #RRGGBB.', '사용자 색상은 #RRGGBB 형식이어야 합니다.')
            end
        end
    end
    if type(p.ef_fontPath) ~= 'string' or not LrPathUtils.isAbsolute(p.ef_fontPath)
        or (p.ef_theme ~= 'none' and LrFileUtils.exists(p.ef_fontPath) ~= 'file') then
        return T('Choose an existing TTF/OTF font.', '존재하는 TTF/OTF 글꼴을 선택해 주세요.')
    end
    for i = 1, 4 do
        local template = p['ef_template' .. i]
        if type(template) ~= 'string' or #template > 2048 or template:find('%z') then
            return T('Each template must be at most 2048 UTF-8 bytes.', '각 템플릿은 UTF-8 기준 2048바이트 이하여야 합니다.')
        end
        for token in template:gmatch('{([^{}]+)}') do
            if not ({iso=true,focal=true,focal35=true,aperture=true,shutter=true,date=true,
                make=true,model=true,lens=true,artist=true})[token] then
                return T('Unknown template token: ', '알 수 없는 템플릿 토큰: ') .. token
            end
        end
        if template:gsub('{[^{}]+}', ''):find('[{}]') then
            return T('Use balanced braces for template tokens.', '토큰의 중괄호 짝을 확인해 주세요.')
        end
    end
    if type(p.ef_artist) ~= 'string' or #p.ef_artist > 2048 or p.ef_artist:find('%z') then
        return T('Artist must be at most 2048 UTF-8 bytes.', '작가명은 UTF-8 기준 2048바이트 이하여야 합니다.')
    end
end
-- SDK Guide pp.50,65: alter rendering only. Metadata inclusion/removal stays with Lightroom.
function Frame.renderSettings(p)
    p.LR_format = 'TIFF'; p.LR_export_bitDepth = 16
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
        else shutterText = number(shutter) end
    end
    return { make = formatted('cameraMake'), model = formatted('cameraModel'),
        lens = formatted('lens'), artist = formatted('artist'), iso = number(raw('isoSpeedRating')),
        aperture = number(raw('aperture')), shutter = shutterText,
        focal = number(raw('focalLength')), focal35 = number(raw('focalLength35mm')),
        date = formatted('dateTimeOriginal') }
end
function Frame.temporary(context)
    local base = LrPathUtils.getStandardFilePath('temp'):gsub('[\\/]+$','')
    local leaf = 'exif-frame-' .. tostring(os.time()) .. '-' .. tostring(math.random(100000, 999999))
    local dir = LrFileUtils.chooseUniqueFileName(LrPathUtils.child(base, leaf))
    local ok, created = LrFileUtils.createAllDirectories(dir)
    assert(ok and created ~= false, T('Cannot create temporary folder.', '임시 폴더를 만들 수 없습니다.'))
    -- Only this newly created direct child is owned/deleted; never delete a user output folder.
    assert(LrPathUtils.parent(dir):gsub('\\','/'):lower() == base:gsub('\\','/'):lower()
        and LrPathUtils.leafName(dir):match('^exif%-frame%-'))
    context:addCleanupHandler(function() LrFileUtils.delete(dir) end)
    return dir
end
function Frame.command(exe, job)
    for _, path in ipairs({exe, job}) do
        assert(LrPathUtils.isAbsolute(path) and not path:find('["\r\n%%!]'),
            T('Unsafe executable/temporary path for Windows shell.', 'Windows 실행 경로에 지원되지 않는 문자가 있습니다.'))
    end
    -- SDK Guide p.48: Windows cmd.exe requires an extra outer pair of quotes.
    return '""' .. exe .. '" --job "' .. job .. '""'
end
function Frame.run(p, photo, input, dir, preview)
    local err = Frame.validate(p, preview); assert(not err, err)
    local baseName = LrPathUtils.removeExtension(LrPathUtils.leafName(input))
    local output = preview and LrPathUtils.child(dir, 'preview.png')
        or LrPathUtils.child(p.ef_outputFolder, baseName .. '.' .. p.ef_format)
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do logos[brand] = path end
    local resultPath = LrPathUtils.child(dir, 'result.json')
    local jobPath = LrPathUtils.child(dir, 'job.json')
    local function normalized(path) return path:gsub('\\', '/'):gsub('/+$',''):lower() end
    local colors = p.ef_appearance == 'dark' and {'#171717','#f4f4f4','#bbbbbb'}
        or {'#ffffff','#161616','#555555'}
    if p.ef_appearance == 'custom' then colors = {p.ef_background,p.ef_text,p.ef_secondary} end
    local job = { schema_version = 1, input_path = input, output_path = output,
        result_path = resultPath, source_path = tostring(read(photo, 'getRawMetadata', 'path')),
        remove_person_info = p.LR_removeFaceMetadata == true,
        preview = preview or false, preview_max_size = 600, format = p.ef_format,
        quality = tonumber(p.ef_quality), lossless = p.ef_lossless == true,
        bit_depth = p.ef_format == 'png' and p.ef_pngDepth or 8,
        color_space = p.ef_format == 'webp' and 'sRGB' or p.ef_colorSpace,
        theme = p.ef_theme, appearance = p.ef_appearance,
        background_color = colors[1], text_color = colors[2], secondary_color = colors[3],
        font_path = p.ef_fontPath, font_percent = tonumber(p.ef_fontPercent),
        band_percent = tonumber(p.ef_bandPercent), padding_percent = tonumber(p.ef_paddingPercent),
        logo_percent = tonumber(p.ef_logoPercent), focal_mode = p.ef_focalMode, artist = p.ef_artist,
        templates = {p.ef_template1,p.ef_template2,p.ef_template3,p.ef_template4},
        metadata = Frame.displayMetadata(photo), logos = logos }
    if job.source_path == '' or LrFileUtils.exists(job.source_path) ~= 'file'
        or normalized(job.source_path) == normalized(output) then job.source_path = nil end
    local file, message = io.open(jobPath, 'wb'); assert(file, message)
    local ok, writeMessage = file:write(Json.encode(job)); local closed, closeMessage = file:close()
    assert(ok and closed, writeMessage or closeMessage or 'Cannot write helper job')
    local status = LrTasks.execute(Frame.command(Frame.helperPath(), jobPath))
    assert(LrFileUtils.exists(resultPath) == 'file', T('Helper returned no result file (exit ', '헬퍼 결과 파일이 없습니다 (종료 코드 ') .. tostring(status) .. ').')
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
function Frame.browse(p, key, kind)
    local paths = LrDialogs.runOpenPanel { title = T('Choose a path', '경로 선택'),
        canChooseFiles = kind ~= 'folder', canChooseDirectories = kind == 'folder',
        allowsMultipleSelection = false, fileTypes = kind == 'font' and {'ttf','otf','ttc'} or nil }
    if paths and paths[1] then p[key] = paths[1] end
end
function Frame.logoStatus(brand)
    return (prefs.officialLogos or {})[brand] or ''
end
function Frame.registerLogo(p)
    local paths = LrDialogs.runOpenPanel { title = T('Register your official transparent PNG logo', '공식 투명 PNG 로고 등록'),
        canChooseFiles = true, canChooseDirectories = false, allowsMultipleSelection = false, fileTypes = {'png'} }
    if not paths or not paths[1] then return end
    assert(LrPathUtils.extension(paths[1]):lower() == 'png' and LrFileUtils.exists(paths[1]) == 'file', 'Choose an existing PNG file')
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do logos[brand] = path end
    logos[p.ef_logoBrand] = paths[1]; prefs.officialLogos = logos; p.ef_logoPath = paths[1]
end
function Frame.removeLogo(p)
    local logos = {}
    for brand, path in pairs(prefs.officialLogos or {}) do if brand ~= p.ef_logoBrand then logos[brand] = path end end
    prefs.officialLogos = logos; p.ef_logoPath = ''
end
function Frame.preview(p)
    if p.ef_previewBusy then return end
    local settings = Frame.snapshot(p)
    local err = Frame.validate(settings, true)
    if err then LrDialogs.message('EXIF Frame', err, 'warning'); return end
    local photo = LrApplication.activeCatalog():getTargetPhoto()
    if not photo then LrDialogs.message('EXIF Frame', T('Select a photo first.', '사진을 먼저 선택해 주세요.'), 'warning'); return end
    p.ef_previewBusy = true; p.ef_previewStatus = T('Rendering preview…', '프리뷰 렌더링 중…')
    LrFunctionContext.postAsyncTaskWithContext('EXIF Frame preview', function(context)
        context:addCleanupHandler(function() p.ef_previewBusy = false end)
        local success, message = LrTasks.pcall(function()
            local dir = Frame.temporary(context)
            Frame.renderSettings(settings)
            settings.LR_exportServiceProvider = 'com.adobe.ag.export.file'
            settings.LR_exportServiceProviderTitle = 'Hard Drive'
            settings.LR_export_destinationType = 'specificFolder'
            settings.LR_export_destinationPathPrefix = dir
            settings.LR_export_useSubfolder = false; settings.LR_reimportExportedPhoto = false
            settings.LR_export_postProcessing = 'doNothing'; settings.LR_collisionHandling = 'rename'
            settings.LR_exportFiltersFromThisPlugin = nil; settings.LR_exportFilters = nil
            settings.LR_cantExportBecause = nil
            local session = LrExportSession { photosToExport = {photo}, exportSettings = settings }
            local result
            for _, rendition in session:renditions() do
                local rendered, path = rendition:waitForRender(); assert(rendered, path)
                result = Frame.run(settings, photo, path, dir, true)
            end
            assert(result, 'No preview rendition')
            p.ef_previewStatus = T('Preview ready.', '프리뷰를 생성했습니다.')
            local f = LrView.osFactory()
            local props = LrBinding.makePropertyTable(context)
            props.image = result.output_path
            local notes = { T('Preview is sRGB8; export keeps the selected profile/depth.',
                '프리뷰는 sRGB8입니다. 실제 출력에는 선택한 색공간·비트 깊이를 적용합니다.') }
            for _, warning in ipairs(result.warnings or {}) do notes[#notes + 1] = tostring(warning) end
            LrDialogs.presentModalDialog { title = T('EXIF Frame preview', 'EXIF Frame 프리뷰'), actionVerb = T('Close','닫기'),
                contents = f:column { bind_to_object = props, spacing = f:control_spacing(),
                    f:picture { value = LrView.bind('image'), width = result.width, height = result.height },
                    f:static_text { title = table.concat(notes, '\n'), width = 600, height_in_lines = 3, wrap = true } } }
        end)
        if not success then
            p.ef_previewStatus = T('Preview failed.', '프리뷰 생성에 실패했습니다.')
            LrDialogs.message('EXIF Frame', tostring(message), 'critical')
        end
    end)
end
function Frame.diagnostics()
    local lines = { 'Lightroom EXIF Frame 0.1.0', T('Windows: ', 'Windows: ') .. tostring(WIN_ENV),
        T('Plug-in: ', '플러그인: ') .. _PLUGIN.path }
    for _, file in ipairs({'bin/frame-helper.exe','bin/imagemagick/magick.exe','bin/exiftool/exiftool.exe'}) do
        local path = LrPathUtils.child(_PLUGIN.path, file)
        lines[#lines + 1] = (LrFileUtils.exists(path) == 'file' and '[OK] ' or '[MISSING] ') .. file
    end
    lines[#lines + 1] = T('Logo paths are stored only in this plug-in’s preferences.', '로고 경로는 이 플러그인의 환경설정에만 저장됩니다.')
    LrDialogs.message('EXIF Frame', table.concat(lines, '\n'), 'info')
end
return Frame
