local LrDialogs = import 'LrDialogs'
local LrFileUtils = import 'LrFileUtils'
local LrProgressScope = import 'LrProgressScope'
local LrTasks = import 'LrTasks'
local LrView = import 'LrView'
local Frame = require 'Frame'
local T, bind = Frame.text, LrView.bind
local Export = { exportPresetFields = Frame.fields, canExportVideo = false,
    hideSections = {'exportLocation','fileSettings','video'},
    allowFileFormats = {'TIFF'}, allowColorSpaces = {'sRGB','AdobeRGB','ProPhotoRGB'} }
local function choices(pairs)
    local out = {}
    for _, pair in ipairs(pairs) do out[#out + 1] = {title = pair[1], value = pair[2]} end
    return out
end
local function note(f, text)
    return f:static_text { title = text, width_in_chars = 66, height_in_lines = 2, wrap = true }
end
local function field(f, label, key, width)
    return f:row { spacing = f:label_spacing(), f:static_text {title = label, width_in_chars = 18},
        f:edit_field {value = bind(key), width_in_chars = width or 40, immediate = true} }
end
local function percent(f, label, key, minimum, maximum)
    return f:row { spacing = f:label_spacing(), f:static_text {title = label, width_in_chars = 18},
        f:slider {value = bind(key), min = minimum, max = maximum, width = 180},
        f:edit_field {value = bind(key), width_in_chars = 6, precision = 2,
            validate = function(_, value)
                local n = tonumber(value)
                if n and n >= minimum and n <= maximum then return true, n end
                return false, T('Enter a number within the displayed range.', '표시된 범위의 숫자를 입력해 주세요.')
            end},
        f:static_text {title = '% (' .. minimum .. '–' .. maximum .. ')'} }
end
local function popup(f, label, key, items, enabled)
    return f:row { spacing = f:label_spacing(), f:static_text {title = label, width_in_chars = 18},
        f:popup_menu {value = bind(key), items = choices(items), enabled = enabled, width_in_chars = 27} }
end
function Export.startDialog(p)
    Frame.initialize(p)
    local function validate()
        p.ef_qualityEnabled = p.ef_format == 'jpg' or (p.ef_format == 'webp' and not p.ef_lossless)
        p.LR_cantExportBecause = Frame.validate(p, false)
    end
    for _, fieldInfo in ipairs(Frame.fields) do p:addObserver(fieldInfo.key, validate) end
    p:addObserver('ef_logoBrand', function() p.ef_logoPath = Frame.logoStatus(p.ef_logoBrand) end)
    validate()
end
function Export.updateExportSettings(p)
    Frame.renderSettings(p)
    p.LR_export_destinationType = 'tempFolder'
    p.LR_export_useSubfolder = false
    p.LR_reimportExportedPhoto = false
end
function Export.sectionsForTopOfDialog(f, p)
    local qualityEnabled = bind('ef_qualityEnabled')
    return {{ title = T('EXIF Frame — Output', 'EXIF Frame — 출력'), bind_to_object = p,
        synopsis = bind('ef_outputFolder'), spacing = f:control_spacing(),
        f:row { spacing = f:control_spacing(),
            f:static_text {title = T('Folder', '출력 폴더'), width_in_chars = 18},
            f:edit_field {value = bind('ef_outputFolder'), width_in_chars = 34, immediate = true},
            f:push_button {title = T('Browse…','찾기…'), action = function() Frame.browse(p,'ef_outputFolder','folder') end} },
        popup(f,T('Format','파일 형식'),'ef_format',{{'JPG','jpg'},{'PNG','png'},{'WebP','webp'}}),
        f:row { spacing = f:label_spacing(), f:static_text {title = T('Quality','품질'), width_in_chars = 18},
            f:slider {value = bind('ef_quality'), min = 1, max = 100, integral = true, width = 180, enabled = qualityEnabled},
            f:edit_field {value = bind('ef_quality'), width_in_chars = 5, precision = 0, enabled = qualityEnabled},
            f:checkbox {title = T('WebP lossless','WebP 무손실'), value = bind('ef_lossless'),
                enabled = bind {key = 'ef_format', transform = function(value) return value == 'webp' end}} },
        popup(f,T('Color space','색공간'),'ef_colorSpace',{{'sRGB','sRGB'},{'Adobe RGB','AdobeRGB'},{'ProPhoto RGB','ProPhotoRGB'}},
            bind {key = 'ef_format', transform = function(value) return value ~= 'webp' end}),
        popup(f,T('PNG depth','PNG 비트 깊이'),'ef_pngDepth',{{'8-bit',8},{'16-bit',16}},
            bind {key = 'ef_format', transform = function(value) return value == 'png' end}),
        note(f,T('Sizing below applies to the photo body. The frame adds pixels outside it. Existing files receive numbered names.',
            '아래 크기는 사진 본체에 적용됩니다. 프레임은 바깥에 추가됩니다. 기존 파일은 덮어쓰지 않고 번호를 붙입니다.')),
        note(f,T('WebP is always sRGB8. PNG16 keeps the selected profile. Lightroom controls embedded metadata and GPS removal.',
            'WebP는 sRGB8입니다. PNG16은 선택한 색공간을 유지합니다. 파일 내부 메타데이터·GPS 제거는 Lightroom 설정을 따릅니다.')),
    }}
end
function Export.sectionsForBottomOfDialog(f, p)
    local sections = {}
    sections[#sections + 1] = { title = T('Frame layout','프레임 레이아웃'), bind_to_object = p,
        synopsis = bind('ef_theme'), spacing = f:control_spacing(),
        popup(f,T('Theme','테마'),'ef_theme',{{'Strap','strap'},{'Simple','simple'},{T('None','없음'),'none'}}),
        popup(f,T('Appearance','색상 스타일'),'ef_appearance',{{T('Light','밝게'),'light'},{T('Dark','어둡게'),'dark'},{T('Custom','사용자 지정'),'custom'}}),
        field(f,T('Background #RRGGBB','배경 #RRGGBB'),'ef_background',14),
        field(f,T('Text #RRGGBB','글자 #RRGGBB'),'ef_text',14),
        field(f,T('Secondary #RRGGBB','보조 글자 #RRGGBB'),'ef_secondary',14),
        note(f,T('Custom color values are used only with Custom appearance.', '사용자 색상값은 사용자 지정 스타일에서만 적용됩니다.')),
        f:row {spacing = f:control_spacing(),
            f:static_text {title = T('Font file','글꼴 파일'), width_in_chars = 18},
            f:edit_field {value = bind('ef_fontPath'), width_in_chars = 34, immediate = true},
            f:push_button {title = T('Browse…','찾기…'), action = function() Frame.browse(p,'ef_fontPath','font') end}},
        percent(f,T('Band height','띠 높이'),'ef_bandPercent',1,40),
        percent(f,T('Padding','여백'),'ef_paddingPercent',0,20),
        percent(f,T('Font size','글꼴 크기'),'ef_fontPercent',0.2,10),
        percent(f,T('Logo size','로고 크기'),'ef_logoPercent',1,50),
        popup(f,T('Focal length','초점거리'),'ef_focalMode',{{T('35mm equivalent','35mm 환산'),'equivalent'},{T('Actual','실제'),'actual'}}),
        field(f,T('Artist override','작가명 직접 입력'),'ef_artist'),
        note(f,T('Blank artist uses catalog metadata. Missing 35mm equivalent falls back to actual focal length.',
            '작가명이 비어 있으면 카탈로그 정보를 사용합니다. 35mm 환산값이 없으면 실제 초점거리를 사용합니다.')),
    }
    sections[#sections + 1] = { title = T('Four text areas','네 영역 템플릿'), bind_to_object = p,
        spacing = f:control_spacing(),
        field(f,T('Upper left','왼쪽 위'),'ef_template1'), field(f,T('Lower left','왼쪽 아래'),'ef_template2'),
        field(f,T('Upper right','오른쪽 위'),'ef_template3'), field(f,T('Lower right','오른쪽 아래'),'ef_template4'),
        f:row {spacing = f:control_spacing(),
            f:popup_menu {value = bind('ef_tokenTarget'), items = choices({{T('Upper left','왼쪽 위'),'ef_template1'},
                {T('Lower left','왼쪽 아래'),'ef_template2'},{T('Upper right','오른쪽 위'),'ef_template3'},
                {T('Lower right','오른쪽 아래'),'ef_template4'}})},
            f:popup_menu {value = bind('ef_token'), items = choices({{'{iso}','{iso}'},{'{focal}','{focal}'},{'{focal35}','{focal35}'},
                {'{aperture}','{aperture}'},{'{shutter}','{shutter}'},{'{date}','{date}'},{'{make}','{make}'},
                {'{model}','{model}'},{'{lens}','{lens}'},{'{artist}','{artist}'}})},
            f:push_button {title = T('Append token','토큰 추가'), action = function()
                local key = p.ef_tokenTarget; p[key] = (p[key] or '') .. p.ef_token
            end}},
        note(f,T('Tokens have no units: add ISO, mm, F, or s in the template. Empty templates hide the area.',
            '토큰에는 단위가 없습니다. ISO·mm·F·s를 직접 붙여 주세요. 템플릿을 비우면 해당 영역을 숨깁니다.')),
    }
    local brands = {{'Canon','canon'},{'Nikon','nikon'},{'Sony','sony'},{'Fujifilm','fujifilm'},{'Pentax','pentax'},
        {'Ricoh','ricoh'},{'Leica','leica'},{'Panasonic / Lumix','panasonic'},{'Olympus','olympus'},
        {'OM System','om-system'},{'Sigma','sigma'},{'Hasselblad','hasselblad'}}
    sections[#sections + 1] = { title = T('Official logos — your files','공식 로고 — 사용자 파일'), bind_to_object = p,
        spacing = f:control_spacing(), popup(f,T('Brand','브랜드'),'ef_logoBrand',brands),
        f:static_text {title = bind('ef_logoPath'), width_in_chars = 66, height_in_lines = 2, wrap = true},
        f:row {spacing = f:control_spacing(),
            f:push_button {title = T('Register PNG…','PNG 등록…'), action = function() Frame.registerLogo(p) end},
            f:push_button {title = T('Remove registration','등록 해제'), action = function() Frame.removeLogo(p) end}},
        note(f,T('Register an official transparent PNG once per brand. Paths are remembered for all exports; logos are not bundled.',
            '브랜드별 공식 투명 PNG를 한 번 등록하세요. 다음 내보내기에서도 경로를 기억합니다. 로고는 배포본에 포함되지 않습니다.')),
    }
    sections[#sections + 1] = { title = T('Preview','프리뷰'), bind_to_object = p, spacing = f:control_spacing(),
        f:push_button {title = T('Preview selected photo…','선택한 사진 프리뷰…'),
            enabled = bind {key = 'ef_previewBusy', transform = function(value) return not value end},
            action = function() Frame.preview(p) end},
        f:static_text {title = bind('ef_previewStatus'), width_in_chars = 66},
        note(f,T('A fresh Lightroom TIFF uses the current sizing/sharpening settings. Preview is sRGB PNG; full export keeps its selected profile/depth.',
            '현재 크기·샤프닝 설정으로 Lightroom TIFF를 새로 렌더합니다. 프리뷰는 sRGB PNG이며 실제 출력은 선택한 색공간·비트 깊이를 유지합니다.')),
    }
    return sections
end
function Export.processRenderedPhotos(context, exportContext)
    local p = Frame.snapshot(exportContext.propertyTable)
    local err = Frame.validate(p, false)
    if err then error(err) end
    local created, createMessage = LrFileUtils.createAllDirectories(p.ef_outputFolder)
    assert(created, createMessage)
    local title = T('Exporting EXIF Frame','EXIF Frame 내보내기')
    local renderProgress = exportContext:configureProgress {title = title, renderPortion = 1}
    -- Lightroom can finish/dismiss its render scope while our external helper is
    -- still running. Keep a separate visible scope alive for the complete batch.
    local progress = LrProgressScope {title = title, functionContext = context}
    progress:setCancelable(true)
    renderProgress:setCancelable(true)
    local total = math.max(1, exportContext.exportSession:countRenditions())
    progress:setPortionComplete(0, total)
    local completed, processed, warnings = 0, 0, {}
    for _, rendition in exportContext:renditions {progressScope = renderProgress, stopIfCanceled = true} do
        if progress:isCanceled() or renderProgress:isCanceled() then
            progress:cancel(); renderProgress:cancel(); break
        end
        local rendered, path = rendition:waitForRender()
        if rendered then
            -- ponytail: cancel between photos; finish this helper call before taking the next rendition.
            if not progress:isCanceled() and not renderProgress:isCanceled() then
                progress:setCaption(T('Framing ','프레임 합성 중: ') .. tostring(path))
                LrTasks.yield() -- Let Lightroom paint the scope before launching the helper.
                if not progress:isCanceled() and not renderProgress:isCanceled() then
                    local ok, result = LrTasks.pcall(function()
                        return Frame.run(p, rendition.photo, path, Frame.temporary(context), false)
                    end)
                    if ok then
                        completed = completed + 1
                        for _, warning in ipairs(result.warnings or {}) do warnings[#warnings + 1] = tostring(warning) end
                    else rendition:uploadFailed(tostring(result)) end
                end
            end
            LrFileUtils.delete(path)
        else rendition:uploadFailed(tostring(path)) end
        processed = processed + 1
        progress:setPortionComplete(processed, total)
        if progress:isCanceled() or renderProgress:isCanceled() then
            progress:cancel(); renderProgress:cancel(); break
        end
    end
    if progress:isCanceled() then
        LrDialogs.message('EXIF Frame', T('Canceled after finishing the current photo. Saved files: ',
            '현재 사진을 마친 후 취소했습니다. 저장한 파일: ') .. completed, 'info')
    end
    if #warnings > 0 then
        -- Keep a complete report for a batch without displaying one modal dialog per photo.
        LrDialogs.message('EXIF Frame', T('Export warnings:\n','내보내기 참고 사항:\n') .. table.concat(warnings, '\n'), 'warning')
    end
    progress:done()
    renderProgress:done()
end
return Export
