-- Manual Adobe SDK harness, NOT an automated test or a shipping plug-in.
-- Copy this as Smoke.lua beside current Frame.lua / Json.lua and the full bin tree
-- in work/LightroomSmoke.lrplugin. A Library menu entry invokes Smoke.lua.
-- Run only with workspace work/Lightroom-Test catalog and work/test-input photos.
-- Outputs and filtered TIFFs remain in work/lr-sdk-output/<unique run> for inspection.
-- SDK 13 Guide p.68 documents the four metadata enums and location-removal key:
-- https://ioconsolerykerprodcdn.azureedge.net/static/installers/lr/sdk/2022/cross_platform/v13/doc/Lightroom%20Classic%20SDK%20Guide_1655133965.pdf
-- API signatures additionally checked against the Adobe SDK LuaDoc mirror:
-- https://lrc.mcor.dev/modules/LrCatalog.html
-- https://lrc.mcor.dev/modules/LrPhoto.html
-- removeFaceMetadata/includeFaceTags* names were additionally observed in the
-- EXIF Frame PNG16 Test preset saved by actual Lightroom Classic 15.6.
-- SDK property tables prefix these native preset names with LR_.
local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
local LrExportSession = import 'LrExportSession'
local LrFileUtils = import 'LrFileUtils'
local LrFunctionContext = import 'LrFunctionContext'
local LrPathUtils = import 'LrPathUtils'
local LrProgressScope = import 'LrProgressScope'
local LrTasks = import 'LrTasks'
local Frame = require 'Frame'
local Json = require 'Json'

local function normalize(path)
    return tostring(path):gsub('\\', '/'):gsub('/+$', ''):lower()
end
local function inside(path, directory)
    local candidate, root = normalize(path), normalize(directory)
    return candidate:sub(1, #root + 1) == root .. '/'
end
local function mkdir(path)
    assert(LrFileUtils.createAllDirectories(path), 'Cannot create harness directory: ' .. path)
end
local function save(path, value)
    local file, message = io.open(path, 'wb'); assert(file, message)
    local written, writeError = file:write(Json.encode(value))
    local closed, closeError = file:close()
    assert(written and closed, writeError or closeError or 'Evidence write failed')
end
local function copySettings(source)
    local out = {}; for key, value in pairs(source) do out[key] = value end; return out
end
local cases = {
    {id='01-all-jpg-srgb', mode='all', format='jpg', profile='sRGB'},
    {id='02-copyright-jpg-srgb', mode='copyrightOnly', format='jpg', profile='sRGB'},
    {id='03-contact-jpg-srgb', mode='copyrightAndContactOnly', format='jpg', profile='sRGB'},
    {id='04-no-camera-jpg-srgb', mode='allExceptCameraInfo', format='jpg', profile='sRGB'},
    {id='05-no-gps-jpg-srgb', mode='all', removeGPS=true, format='jpg', profile='sRGB'},
    {id='06-all-png16-srgb', mode='all', format='png', profile='sRGB'},
    {id='07-all-webp-srgb', mode='all', format='webp', profile='sRGB'},
    {id='08-all-png16-adobe', mode='all', format='png', profile='AdobeRGB'},
    {id='09-all-png16-prophoto', mode='all', format='png', profile='ProPhotoRGB'},
    {id='10-all-jpg-adobe', mode='all', format='jpg', profile='AdobeRGB'},
    {id='11-all-jpg-prophoto', mode='all', format='jpg', profile='ProPhotoRGB'},
    {id='13-no-person-jpg-srgb', mode='all', removePerson=true, format='jpg', profile='sRGB'},
}

LrFunctionContext.postAsyncTaskWithContext('EXIF Frame actual SDK smoke', function(context)
    local evidence, runFolder, evidencePath
    local success, failure = LrTasks.pcall(function()
        assert(WIN_ENV, 'Windows-only SDK harness')
        local work = LrPathUtils.parent(_PLUGIN.path)
        assert(LrPathUtils.leafName(_PLUGIN.path) == 'LightroomSmoke.lrplugin'
            and LrPathUtils.leafName(work):lower() == 'work', 'Install harness only under workspace/work')
        local catalog = LrApplication.activeCatalog()
        local catalogPath = catalog:getPath()
        local testCatalogFolder = LrPathUtils.child(work, 'Lightroom-Test')
        assert(inside(catalogPath, testCatalogFolder)
            and normalize(catalogPath):find('lightroom%-test'), 'Refusing unrelated catalog: ' .. catalogPath)
        local photo = assert(catalog:getTargetPhoto(), 'Select one test-input photo first')
        local inputRoot = LrPathUtils.child(work, 'test-input')
        local sourcePath = photo:getRawMetadata('path')
        assert(inside(sourcePath, inputRoot), 'Refusing photo outside work/test-input')
        assert(LrFileUtils.exists(sourcePath) == 'file', 'Test fixture is missing')
        assert(not photo:getRawMetadata('isVideo'), 'Select an image, not a video')
        assert(LrFileUtils.exists(Frame.helperPath()) == 'file', 'Copy the complete plug-in bin tree')
        -- All source/catalog writes are limited to this disposable, copied test fixture.
        -- Never write metadata to disk, invoke saveMetadata(), or import any other path.
        local root = LrPathUtils.child(work, 'lr-sdk-output'); mkdir(root)
        runFolder = LrFileUtils.chooseUniqueFileName(LrPathUtils.child(root,
            os.date('!%Y%m%dT%H%M%SZ') .. '-' .. tostring(math.random(100000,999999))))
        mkdir(runFolder); evidencePath = LrPathUtils.child(runFolder, 'evidence.json')
        evidence = {schema_version=1, kind='manual-actual-lightroom-sdk',
            started_utc=os.date('!%Y-%m-%dT%H:%M:%SZ'), catalog_path=catalogPath,
            source_path=sourcePath, output_directory=runFolder,
            sdk_baseline=13, metadata_reference='Adobe SDK 13 Guide p.68',
            observations={}, results={}, cancelled=false}
        save(evidencePath, evidence)

        local fixtureOK, fixtureError = LrTasks.pcall(function()
            local parent, child, leaf
            catalog:withWriteAccessDo('EXIF Frame test fixture metadata', function()
                photo:setRawMetadata('caption', '한국어 촬영 설명 · 日本語の撮影説明')
                photo:setRawMetadata('title', 'SDK 한국어 日本語 fixture')
                photo:setRawMetadata('copyright', 'Copyright Yunhyok — SDK test fixture')
                photo:setRawMetadata('creator', 'Yunhyok SDK 테스트')
                parent = catalog:createKeyword('SDK 테스트', {}, true, nil, true)
            end, {timeout=10})
            catalog:withWriteAccessDo('EXIF Frame test keyword child', function()
                child = catalog:createKeyword('日本語', {}, true, parent, true)
            end, {timeout=10})
            catalog:withWriteAccessDo('EXIF Frame test keyword leaf', function()
                leaf = catalog:createKeyword('왜가리', {}, true, child, true)
                photo:addKeyword(leaf)
            end, {timeout=10})
        end)
        evidence.fixture_setup = {ok=fixtureOK, error=not fixtureOK and tostring(fixtureError) or nil}
        -- Each privacy seed is independent: unsupported setters cannot stop any export.
        -- GPS and personShown setters/types are documented in Adobe LrPhoto LuaDoc.
        -- All values below are synthetic test data, not the photographer's location/contact.
        evidence.synthetic_seed={}
        local function seed(key, value, raw)
            local row={synthetic=true}; evidence.synthetic_seed[key]=row
            local ok, err = LrTasks.pcall(function()
                catalog:withWriteAccessDo('EXIF Frame synthetic ' .. key, function()
                    photo:setRawMetadata(key, value)
                end, {timeout=10})
                row.observed=raw and photo:getRawMetadata(key) or photo:getFormattedMetadata(key)
                if key == 'gps' then
                    assert(type(row.observed) == 'table'
                        and math.abs((row.observed.latitude or 999) - value.latitude) < .0001
                        and math.abs((row.observed.longitude or 999) - value.longitude) < .0001,
                        'Synthetic GPS not retained by catalog')
                else assert(row.observed ~= nil and tostring(row.observed) ~= '', 'Seed not retained: ' .. key) end
            end)
            row.ok=ok; if not ok then row.error=tostring(err) end
        end
        seed('gps', {latitude=0.125,longitude=0.25}, true)
        seed('gpsAltitude', 12.5, true)
        seed('personShown', 'SDK Synthetic Person', false)
        seed('creatorEmail', 'sdk-fixture@example.invalid', false)
        seed('creatorPhone', '+00-000-SDK-TEST', false)
        evidence.synthetic_seed.face_region={ok=false,
            reason='SDK has no documented face-region setter; personShown seeds IPTC person data only.'}
        evidence.visible_metadata = Frame.displayMetadata(photo)
        evidence.catalog_fixture = {caption=photo:getFormattedMetadata('caption'),
            title=photo:getFormattedMetadata('title'), copyright=photo:getFormattedMetadata('copyright'),
            keywords=photo:getFormattedMetadata('keywordTagsForExport')}
        save(evidencePath, evidence)

        local progress = LrProgressScope {title='EXIF Frame SDK smoke', functionContext=context}
        progress:setCancelable(true)
        local function renderCase(case, target)
            local row = {id=case.id, format=case.format, profile=case.profile,
                metadata_mode=case.mode, remove_gps=case.removeGPS == true,
                remove_person=case.removePerson == true}
            evidence.results[#evidence.results+1] = row
            local caseFolder = LrPathUtils.child(runFolder, case.id); mkdir(caseFolder)
            local renderFolder = LrPathUtils.child(caseFolder, 'filtered-tiff'); mkdir(renderFolder)
            local p = copySettings(Frame.defaults)
            p.ef_outputFolder=caseFolder; p.ef_format=case.format; p.ef_colorSpace=case.profile
            p.ef_pngDepth=16; p.ef_theme=case.theme or 'strap'; p.ef_lossless=case.format == 'webp'
            p.ef_artist=''; p.ef_template2='{date} · {artist}'
            p.LR_embeddedMetadataOption=case.mode; p.LR_removeLocationMetadata=case.removeGPS == true
            p.LR_removeFaceMetadata=case.removePerson == true
            p.LR_includeFaceTagsAsKeywords=true; p.LR_includeFaceTagsInIptc=true
            p.LR_metadata_keywordOptions='lightroomHierarchical'
            p.LR_renamingTokensOn=false; p.LR_extensionCase='lowercase'
            p.LR_size_doConstrain=true; p.LR_size_doNotEnlarge=true; p.LR_size_resizeType='wh'
            p.LR_size_units='pixels'; p.LR_size_maxWidth=1920; p.LR_size_maxHeight=1920
            p.LR_size_resolution=240; p.LR_size_resolutionUnits='inch'
            p.LR_outputSharpeningOn=true; p.LR_outputSharpeningMedia='screen'; p.LR_outputSharpeningLevel=2
            p.LR_useWatermark=false; p.LR_export_postProcessing='doNothing'
            Frame.renderSettings(p)
            p.LR_exportServiceProvider='com.adobe.ag.export.file'; p.LR_exportServiceProviderTitle='Hard Drive'
            p.LR_export_destinationType='specificFolder'; p.LR_export_destinationPathPrefix=renderFolder
            p.LR_export_useSubfolder=false; p.LR_reimportExportedPhoto=false; p.LR_collisionHandling='rename'
            row.export_settings=copySettings(p)
            local ok, err = LrTasks.pcall(function()
                assert(LrApplication.activeCatalog():getPath() == catalogPath, 'Active catalog changed; stopping')
                assert(inside(target:getRawMetadata('path'), inputRoot), 'Unsafe test target')
                local session = LrExportSession {photosToExport={target}, exportSettings=p}
                local count=0
                for _, rendition in session:renditions() do
                    local rendered, path = rendition:waitForRender()
                    assert(rendered, 'Lightroom render: ' .. tostring(path))
                    assert(inside(path, renderFolder), 'Rendered TIFF escaped harness directory')
                    row.filtered_tiff=path -- Preserved; helper does not modify this TIFF.
                    row.helper=Frame.run(p, target, path, caseFolder, false)
                    count=count+1
                end
                assert(count == 1, 'Expected exactly one rendered test photo')
            end)
            row.ok=ok; if not ok then row.error=tostring(err) end
            save(evidencePath, evidence)
        end
        for index, case in ipairs(cases) do
            if progress:isCanceled() then evidence.cancelled=true; break end
            progress:setCaption(case.id); progress:setPortionComplete(index-1, #cases+1)
            renderCase(case, photo)
        end

        if not progress:isCanceled() then
            -- createVirtualCopies is documented as async and operates on selected photos.
            -- Restrict selection first; crop/rotation only affect the new virtual copy.
            local virtualOK, virtualError = LrTasks.pcall(function()
                assert(LrApplication.activeCatalog():getPath() == catalogPath, 'Catalog changed')
                catalog:setSelectedPhotos(photo, {photo})
                local copies = catalog:createVirtualCopies('EXIF Frame SDK crop rotate')
                local copy = assert(copies and copies[1], 'No virtual copy returned')
                assert(copy:getRawMetadata('isVirtualCopy'), 'Refusing develop writes to a master')
                local settings = copy:getDevelopSettings()
                local crop = {}
                -- Apply only crop keys already exposed by this actual Lightroom build.
                for key, value in pairs({CropLeft=.12,CropRight=.88,CropTop=.12,CropBottom=.88,HasCrop=true}) do
                    if settings[key] ~= nil then crop[key]=value end
                end
                catalog:withWriteAccessDo('EXIF Frame test virtual-copy develop', function()
                    assert(copy:getRawMetadata('isVirtualCopy'), 'Virtual-copy safety guard')
                    if next(crop) then copy:applyDevelopSettings(crop, 'EXIF Frame SDK crop') end
                    copy:rotateRight()
                end, {timeout=10})
                evidence.virtual_copy={local_identifier=copy.localIdentifier, applied_crop=crop,
                    develop_settings=copy:getDevelopSettings()}
                renderCase({id='12-virtual-crop-rotate-png16', mode='all', format='png', profile='sRGB', theme='simple'}, copy)
            end)
            if not virtualOK then evidence.observations[#evidence.observations+1]='Virtual-copy check: ' .. tostring(virtualError) end
            catalog:setSelectedPhotos(photo, {photo})
        else evidence.cancelled=true end
        progress:done()
        evidence.completed_utc=os.date('!%Y-%m-%dT%H:%M:%SZ')
        evidence.success_count=0
        for _, row in ipairs(evidence.results) do if row.ok then evidence.success_count=evidence.success_count+1 end end
        save(evidencePath, evidence)
    end)
    if not success and evidence then
        evidence.harness_error=tostring(failure)
        LrTasks.pcall(function() save(evidencePath, evidence) end)
    end
    LrDialogs.message('EXIF Frame SDK smoke', success
        and ('Finished. Inspect filtered TIFFs, final images, and ' .. evidencePath)
        or ('Harness stopped: ' .. tostring(failure)), success and 'info' or 'critical')
end)
