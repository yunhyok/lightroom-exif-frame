"""Execute the Lua 5.1 plug-in boundary with a small Lightroom SDK substitute.

These checks exercise protocol/settings/cancellation; they do not verify Adobe's UI.
Run with .venv/Scripts/python.exe -m unittest discover -s tests -p test_lua.py
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest

from lupa.lua51 import LuaRuntime


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "LightroomExifFrame.lrplugin"

SDK = r'''
WIN_ENV = true
_PLUGIN = {path = PLUGIN_PATH}
local prefs = {}
messages, renderedSettings, calls = {}, {}, {}
REIMPORTED, REVEALED_PATHS, CONFIRM_CALLS = {}, {}, {}
NEXT_OPEN_PANEL, NEXT_CONFIRM = nil, nil
local function slash(p) return p:gsub('\\','/') end
local paths = {
    child = function(p,c) return slash(p):gsub('/+$','') .. '/' .. c end,
    parent = function(p) return slash(p):match('^(.*)/[^/]+$') end,
    leafName = function(p) return slash(p):match('[^/]+$') end,
    removeExtension = function(p) return p:gsub('%.[^.]+$','') end,
    extension = function(p) return p:match('%.([^.]+)$') or '' end,
    isAbsolute = function(p) return p:match('^%a:[/\\]') ~= nil or p:match('^[/\\][/\\]') ~= nil end,
    getStandardFilePath = function(kind)
        if kind == 'temp' then return TEST_PATH end
        return TEST_PATH .. '/std_' .. tostring(kind)
    end,
}
local fileutils = {
    exists = py_exists, createAllDirectories = py_create, readFile = py_read,
    delete = py_delete, chooseUniqueFileName = function(p)
        while py_exists(p) do p = p .. '-2' end
        return p
    end,
}
local factory = setmetatable({}, {__index = function(_,kind)
    if kind == 'control_spacing' or kind == 'label_spacing' then return function() return 6 end end
    return function(_,args) args.kind = kind; return args end
end})
local function makeProgress()
    local p = {canceled=false,portions={}}
    function p:setCancelable(value) self.cancelable=value end
    function p:setCaption(value) self.caption=value end
    function p:setPortionComplete(done,total) self.portions[#self.portions+1]={done,total} end
    function p:isCanceled() return self.canceled end
    function p:cancel() self.canceled=true end
    function p:done() self.finished=true end
    return p
end
PROGRESS = makeProgress(); RENDER_PROGRESS = makeProgress()
local photo = {}
function photo:getRawMetadata(key)
    local data = {isoSpeedRating=200,aperture=2.8,shutterSpeed=1/800,focalLength=50,
        focalLength35mm=75,path=SOURCE_PATH}
    return data[key]
end
function photo:getFormattedMetadata(key)
    return ({cameraMake='SONY',cameraModel='ILCE-7',lens='50mm lens',artist='작가',
        dateTimeOriginal='2024/04/08 12:31:11'})[key]
end
PHOTO = photo
local catalog = {
    getTargetPhoto = function() return photo end,
    withWriteAccessDo = function(_, name, fn) fn() end,
    addPhoto = function(_, path, target, pos)
        REIMPORTED[#REIMPORTED + 1] = { path = path, stack = target ~= nil, pos = pos }
    end,
}
local sdk = {
    LrApplication = {activeCatalog=function() return catalog end},
    LrBinding = {makePropertyTable=function() return {} end},
    LrDialogs = {
        message=function(title,text) messages[#messages+1] = text end,
        presentModalDialog=function(args) DIALOG=args end,
        runOpenPanel=function(args)
            calls[#calls+1] = {kind='openPanel', args=args}
            return NEXT_OPEN_PANEL
        end,
        confirm=function(msg, info, okVerb, cancelVerb, otherVerb)
            CONFIRM_CALLS[#CONFIRM_CALLS+1] = {msg=msg, ok=okVerb, cancel=cancelVerb, other=otherVerb}
            return NEXT_CONFIRM or 'ok'
        end,
    },
    LrExportSession = function(args)
        renderedSettings[#renderedSettings+1] = args.exportSettings
        local one = {photo=photo, waitForRender=function() return true, INPUT_PATH end}
        return {renditions=function() return ipairs({one}) end}
    end,
    LrFileUtils=fileutils,
    LrFunctionContext = {
        postAsyncTaskWithContext=function(_,func)
            local context = {handlers={}}
            function context:addCleanupHandler(h) self.handlers[#self.handlers+1] = h end
            func(context)
            for _, h in ipairs(context.handlers) do h() end
        end,
    },
    LrLocalization={currentLanguage=function() return LANGUAGE or 'en' end},
    LrPathUtils=paths, LrPrefs={prefsForPlugin=function() return prefs end},
    LrProgressScope=function(args) PROGRESS_ARGS=args; return PROGRESS end,
    LrShell={revealInShell=function(path) REVEALED_PATHS[#REVEALED_PATHS+1] = path end},
    LrTasks={pcall=pcall,execute=py_execute,yield=function()
        YIELD_COUNT=(YIELD_COUNT or 0)+1
        if CANCEL_AT_YIELD then PROGRESS:cancel() end
    end},
    LrView={osFactory=function() return factory end,bind=function(value) return {binding=value} end},
}
function import(name) return assert(sdk[name], 'Unknown SDK namespace: '..name) end
function SETTINGS()
    local p={}; for key,value in pairs(require('Frame').defaults) do p[key]=value end
    p.ef_outputFolder=OUTPUT_PATH
    p.ef_fontPath=FONT_PATH
    return p
end
function CONTEXT()
    local c={handlers={}}
    function c:addCleanupHandler(h) self.handlers[#self.handlers+1]=h end
    function c:cleanup() for _,h in ipairs(self.handlers) do h() end end
    return c
end
'''


class LuaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="exif-frame-test-")
        self.directory = Path(self.temp.name)
        self.output = self.directory / "output"
        self.output.mkdir()
        self.source = self.directory / "original.dng"
        self.source.write_bytes(b"source remains untouched")
        self.input = self.directory / "RENAMED.tif"
        self.input.write_bytes(b"II*\x00dummy")
        self.font = self.directory / "font.ttf"
        self.font.write_bytes(b"dummy")
        self.jobs = []
        self.inspects = []
        self.fail_helper = False
        self.cancel_after_call = False
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        g = self.lua.globals()
        for key, value in {
            "PLUGIN_PATH": PLUGIN.as_posix(), "TEST_PATH": self.directory.as_posix(),
            "SOURCE_PATH": self.source.as_posix(), "INPUT_PATH": self.input.as_posix(),
            "OUTPUT_PATH": self.output.as_posix(), "FONT_PATH": self.font.as_posix(),
        }.items():
            g[key] = value
        g.py_exists = self.exists
        g.py_create = self.create
        g.py_read = lambda p: Path(p).read_text(encoding="utf-8")
        g.py_delete = self.delete
        g.py_execute = self.execute
        self.lua.execute("package.path = PLUGIN_PATH .. '/?.lua;' .. package.path")
        self.lua.execute(SDK)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def exists(path):
        if str(path).replace("\\", "/").endswith("/bin/frame-helper.exe"):
            return "file"
        p = Path(path)
        return "file" if p.is_file() else "directory" if p.is_dir() else False

    @staticmethod
    def create(path):
        p = Path(path)
        created = not p.exists()
        p.mkdir(parents=True, exist_ok=True)
        return True, created

    def delete(self, path):
        p = Path(path)
        if not p.resolve().is_relative_to(self.directory.resolve()):
            raise AssertionError("Attempt to remove a path outside the test directory")
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink(missing_ok=True)
        return True

    def execute(self, command):
        m_job = re.fullmatch(r'""(.+)" --job "([^"]+)""', command)
        m_insp = re.fullmatch(r'""(.+)" --inspect "([^"]+)""', command)
        if m_insp:
            job = json.loads(Path(m_insp[2]).read_text(encoding="utf-8"))
            self.inspects.append(job)
            result = {
                "schema_version": 1, "ok": True,
                "brand_info": {
                    "brand_id": "sony-alpha", "brand_name": "Sony α", "era_id": "2006",
                    "era_label": "2006-Present (SONY + Alpha)",
                    "era_label_ko": "2006-현재 (SONY + α 심볼)",
                    "detected_year": 2013, "year_source": "database", "logo_source": "builtin_svg",
                },
                "warnings": [],
            }
            Path(job["result_path"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            return 0
        if not m_job:
            raise AssertionError(f"Unexpected shell input: {command}")
        job = json.loads(Path(m_job[2]).read_text(encoding="utf-8"))
        self.jobs.append(job)
        if self.fail_helper:
            result = {"schema_version": 1, "ok": False, "error": "Test metadata failure", "warnings": []}
            status = 1
        else:
            Path(job["output_path"]).write_bytes(b"final image")
            result = {
                "schema_version": 1, "ok": True, "output_path": job["output_path"],
                "width": 1000, "height": 800, "warnings": [],
                "brand_info": {
                    "brand_id": "sony-alpha", "brand_name": "Sony α", "era_id": "2006",
                    "era_label": "2006-Present", "era_label_ko": "2006-현재",
                    "detected_year": 2013, "year_source": "database", "logo_source": "builtin_svg",
                },
            }
            status = 0
        Path(job["result_path"]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        if self.cancel_after_call:
            self.lua.globals().PROGRESS.canceled = True
        return status

    def test_all_lua_files_compile(self):
        compile_file = self.lua.eval("function(path) local chunk,err=loadfile(path); assert(chunk,err) end")
        for path in PLUGIN.glob("*.lua"):
            compile_file(path.as_posix())

    def test_dialog_description_and_locale_construct(self):
        self.lua.execute('''
            local e=require('Export');local p=SETTINGS();local observers={}
            function p:addObserver(key,func) observers[key]=func end
            e.startDialog(p)
            assert(p.ef_qualityEnabled and not p.LR_cantExportBecause)
            p.ef_format='webp';p.ef_lossless=true;observers.ef_lossless()
            assert(not p.ef_qualityEnabled)
            assert(e.sectionsForTopOfDialog == nil)
            local hidden = {}
            for _, h in ipairs(e.hideSections) do hidden[h] = true end
            assert(hidden.fileSettings and hidden.video and hidden.postProcessing)
            assert(not hidden.exportLocation and not hidden.fileNaming)
            local f=import('LrView').osFactory()
            assert(#e.sectionsForBottomOfDialog(f,p)==5)
            LANGUAGE='ko';assert(require('Frame').text('English','한국어')=='한국어')
            assert(#e.sectionsForBottomOfDialog(f,p)==5)
            assert(require('Manager').sectionsForTopOfDialog(f))
            local backing={ef_theme='none',LR_removeLocationMetadata=true}
            local observable={pairs=function() return pairs(backing) end}
            local clone=require('Frame').snapshot(observable)
            assert(clone.ef_theme=='none' and clone.LR_removeLocationMetadata)
        ''')

    def test_json_boundary(self):
        self.lua.execute(r'''
            local j=require('Json')
            local raw=[=[{"false":false,"array":[1,null,"\\\"\n한글"],"unicode":"\ud83d\ude00"}]=]
            local decoded=j.decode(raw)
            assert(decoded['false']==false and decoded.array[2]==j.null)
            assert(j.decode(j.encode(decoded)).unicode == '😀')
            assert(j.encode({}) == '{}')
            for _,bad in ipairs({'01','1.','1.E2','[1,]','{"a":1,"a":2}',
                'false true',[=["\ud800"]=],[=["\ude00"]=],'NaN','1e999','{"x":}'}) do
                assert(not pcall(j.decode,bad),bad)
            end
            local cycle={};cycle.self=cycle;assert(not pcall(j.encode,cycle))
        ''')

    def test_render_settings_preserve_lightroom_policy_size_and_snapshot_location(self):
        self.lua.execute('''
            local f=require('Frame'); local p=SETTINGS()
            p.LR_export_destinationType='specificFolder'
            p.LR_export_destinationPathPrefix=OUTPUT_PATH
            p.LR_export_useSubfolder=true
            p.LR_export_destinationPathSuffix='2026/Framed'
            p.LR_collisionHandling='overwrite'
            p.LR_reimportExportedPhoto=true
            p.LR_reimport_stackWithOriginal=true
            p.LR_reimport_stackWithOriginal_position='above'
            p.LR_extensionCase='uppercase'
            p.LR_embeddedMetadataOption='copyrightOnly'; p.LR_removeLocationMetadata=true
            p.LR_removeFaceMetadata=true; p.LR_metadata_keywordOptions='lightroomHierarchical'
            p.LR_size_maxHeight=2048; p.LR_outputSharpeningOn=true
            p.ef_colorSpace='ProPhotoRGB'; f.renderSettings(p)
            assert(p.LR_format=='TIFF' and p.LR_export_bitDepth==16)
            assert(p.LR_export_destinationType=='tempFolder' and not p.LR_export_useSubfolder)
            assert(not p.LR_reimportExportedPhoto)
            assert(p.ef_snap_destType=='specificFolder' and p.ef_snap_destPrefix==OUTPUT_PATH)
            assert(p.ef_snap_useSubfolder==true and p.ef_snap_destSuffix=='2026/Framed')
            assert(p.ef_snap_collision=='overwrite' and p.ef_snap_extCase=='uppercase')
            assert(p.ef_snap_reimport==true and p.ef_snap_stack==true and p.ef_snap_stackPos=='above')
            assert(p.LR_export_colorSpace=='ProPhotoRGB')
            assert(p.LR_embeddedMetadataOption=='copyrightOnly' and p.LR_removeLocationMetadata)
            assert(p.LR_removeFaceMetadata and p.LR_metadata_keywordOptions=='lightroomHierarchical')
            assert(p.LR_size_maxHeight==2048 and p.LR_outputSharpeningOn)
            p.ef_format='webp'; f.renderSettings(p); assert(p.LR_export_colorSpace=='sRGB')
        ''')

    def test_command_quoting_and_validation(self):
        self.lua.execute(r'''
            local f=require('Frame')
            assert(f.command('C:/helper dir/frame.exe','C:/temp/job.json') ==
                '""C:/helper dir/frame.exe" --job "C:/temp/job.json""')
            assert(f.command('C:/helper dir/frame.exe','C:/temp/ins.json','--inspect') ==
                '""C:/helper dir/frame.exe" --inspect "C:/temp/ins.json""')
            for _,path in ipairs({'C:/%TEMP%/job','C:/a!b/job','C:/a"b/job','relative/job'}) do
                assert(not pcall(f.command,'C:/frame.exe',path))
            end
            local p=SETTINGS();assert(not f.validate(p))
            p.ef_template1='{not_a_token}';assert(f.validate(p))
            p.ef_template1='{iso';assert(f.validate(p))
            p.ef_template1='{label} {era}';assert(not f.validate(p))
            p.LR_export_destinationType='specificFolder'
            p.LR_export_destinationPathPrefix=OUTPUT_PATH
            p.LR_export_useSubfolder=true
            p.LR_export_destinationPathSuffix='../escape'
            assert(f.validate(p))
            p.LR_export_destinationPathSuffix='sub/nested'
            assert(not f.validate(p))
        ''')

    def test_native_export_location_modes_and_choose_later_cancel(self):
        chosen_dir = self.directory / "chosen"
        chosen_dir.mkdir()
        g = self.lua.globals()
        g.CHOSEN_DIR = chosen_dir.as_posix()
        self.lua.execute('''
            local f=require('Frame'); local c=CONTEXT(); local w=f.temporary(c)
            -- 1. specificFolder + subfolder
            local p1=SETTINGS()
            p1.LR_export_destinationType='specificFolder'; p1.LR_export_destinationPathPrefix=OUTPUT_PATH
            p1.LR_export_useSubfolder=true; p1.LR_export_destinationPathSuffix='Export/Sub'
            f.renderSettings(p1)
            local r1=f.exportRendition(p1, {photo=PHOTO}, INPUT_PATH, w, {})
            assert(r1.output_path:match('/output/Export/Sub/RENAMED%.jpg$'))

            -- 2. sourceFolder
            local p2=SETTINGS()
            p2.LR_export_destinationType='sourceFolder'
            f.renderSettings(p2)
            local r2=f.exportRendition(p2, {photo=PHOTO}, INPUT_PATH, w, {})
            assert(r2.output_path:match('/RENAMED%.jpg$') and not r2.output_path:match('/output/'))

            -- 3. standard OS folders (desktop, pictures)
            local p3=SETTINGS(); p3.LR_export_destinationType='desktop'; f.renderSettings(p3)
            local d3=f.resolveDestinationDir(p3, SOURCE_PATH, {})
            assert(d3:match('std_desktop$'))
            local p4=SETTINGS(); p4.LR_export_destinationType='pictures'; f.renderSettings(p4)
            local d4=f.resolveDestinationDir(p4, SOURCE_PATH, {})
            assert(d4:match('std_pictures$'))

            -- 4. chooseLater asks ONCE across 2 renditions
            NEXT_OPEN_PANEL={CHOSEN_DIR}
            local p5=SETTINGS(); p5.LR_export_destinationType='chooseLater'; f.renderSettings(p5)
            local sess={}
            local da=f.resolveDestinationDir(p5, SOURCE_PATH, sess)
            NEXT_OPEN_PANEL=nil
            local db=f.resolveDestinationDir(p5, SOURCE_PATH, sess)
            assert(da == CHOSEN_DIR and db == CHOSEN_DIR and #calls == 1)

            -- 5. chooseLater canceled
            NEXT_OPEN_PANEL=nil
            local dc, st = f.resolveDestinationDir(p5, SOURCE_PATH, {})
            assert(dc == nil and st == 'canceled')
            c:cleanup()
        ''')

    def test_collision_modes_extension_case_reimport_and_reveal(self):
        existing = self.output / "RENAMED.JPG"
        existing.write_bytes(b"old")
        self.lua.execute('''
            local e=require('Export'); local f=require('Frame'); local c=CONTEXT()
            -- Skip existing
            local pSkip=SETTINGS(); pSkip.LR_export_destinationType='specificFolder'
            pSkip.LR_export_destinationPathPrefix=OUTPUT_PATH; pSkip.LR_collisionHandling='skip'
            pSkip.LR_extensionCase='uppercase'; f.renderSettings(pSkip)
            local rSkip, stSkip = f.exportRendition(pSkip, {photo=PHOTO}, INPUT_PATH, f.temporary(c), {})
            assert(rSkip == nil and stSkip == 'skipped')

            -- Ask -> choose 'other' (overwrite)
            NEXT_CONFIRM='other'
            local pAsk=SETTINGS(); pAsk.LR_export_destinationType='specificFolder'
            pAsk.LR_export_destinationPathPrefix=OUTPUT_PATH; pAsk.LR_collisionHandling='ask'
            pAsk.LR_extensionCase='uppercase'; pAsk.ef_revealInExplorer=true
            pAsk.LR_reimportExportedPhoto=true; pAsk.LR_reimport_stackWithOriginal=true
            pAsk.LR_reimport_stackWithOriginal_position='below'
            f.renderSettings(pAsk)
            local rendition={photo=PHOTO,waitForRender=function() return true,INPUT_PATH end,
                uploadFailed=function(m) error(m) end}
            local ec={propertyTable=pAsk,configureProgress=function() return RENDER_PROGRESS end,
                exportSession={countRenditions=function() return 1 end},
                renditions=function()
                    local n=0
                    return function() n=n+1; if n==1 then return 1,rendition end end
                end}
            e.processRenderedPhotos(c, ec)
            assert(#CONFIRM_CALLS == 1)
            assert(#REIMPORTED == 1 and REIMPORTED[1].stack == true and REIMPORTED[1].pos == 'below')
            assert(#REVEALED_PATHS == 1 and REVEALED_PATHS[1]:match('RENAMED%.JPG$'))

            -- Protect original source photo against overwrite
            local dSrc = TEST_PATH .. '/original.jpg'
            assert(f.resolveCollision(pAsk, SOURCE_PATH, SOURCE_PATH, {}) == 'rename')
            c:cleanup()
        ''')
        self.assertEqual(self.jobs[0]["collision_mode"], "overwrite")
        self.assertTrue(self.jobs[0]["output_path"].endswith("RENAMED.JPG"))

    def test_job_uses_rendered_basename_and_catalog_visible_fields(self):
        self.lua.execute('''
            local f=require('Frame'); local c=CONTEXT()
            local p=SETTINGS();p.ef_format='png';p.ef_colorSpace='AdobeRGB'
            local r=f.run(p,PHOTO,INPUT_PATH,f.temporary(c),false)
            assert(r.ok and r.output_path:match('RENAMED%.png$'));c:cleanup()
        ''')
        job = self.jobs[0]
        self.assertEqual(job["color_space"], "AdobeRGB")
        self.assertEqual(job["bit_depth"], 16)
        self.assertEqual(job["metadata"]["shutter"], "1/800")
        self.assertEqual(job["metadata"]["focal"], "50")
        self.assertEqual(job["metadata"]["focal35"], "75")
        self.assertEqual(job["logos"], {})
        self.assertNotIn("gps", job["metadata"])
        self.assertEqual(self.source.read_bytes(), b"source remains untouched")
        self.lua.execute('''
            local photo={getRawMetadata=function(_,key) if key=='shutterSpeed' then return .8 end end,
                getFormattedMetadata=function() return '' end}
            assert(require('Frame').displayMetadata(photo).shutter=='0.8')
        ''')

    def test_inspect_brand_svg_registration_and_preview_brand_info(self):
        svg_file = self.directory / "custom.svg"
        svg_file.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>', encoding="utf-8")
        bmp_file = self.directory / "bad.bmp"
        bmp_file.write_bytes(b"BM")
        g = self.lua.globals()
        g.SVG_FILE = svg_file.as_posix()
        g.BMP_FILE = bmp_file.as_posix()
        self.lua.execute('''
            local f=require('Frame'); local p=SETTINGS()
            f.initialize(p)
            local info=f.inspectBrand(p, PHOTO)
            assert(info and info.brand_id == 'sony-alpha')
            assert(p.ef_detectedBrandSummary:find('Sony'))

            p.ef_logoBrand='pentax'
            NEXT_OPEN_PANEL={SVG_FILE}
            f.registerLogo(p)
            assert(p.ef_logoPath == SVG_FILE)
            NEXT_OPEN_PANEL={BMP_FILE}
            assert(not pcall(f.registerLogo, p))

            f.preview(p)
            assert(#renderedSettings==1 and not p.ef_previewBusy)
            local s=renderedSettings[1]
            assert(s.LR_exportServiceProvider=='com.adobe.ag.export.file')
            assert(DIALOG and DIALOG.contents[1].kind=='picture')
            assert(DIALOG.contents[2].title:find('Sony'))
        ''')
        self.assertEqual(len(self.inspects), 1)
        self.assertTrue(self.jobs[0]["preview"])

    def test_preview_uses_current_policy_and_sizing_without_recursive_provider(self):
        self.lua.execute('''
            local f=require('Frame');local p=SETTINGS()
            p.LR_embeddedMetadataOption='copyrightOnly';p.LR_removeLocationMetadata=true
            p.LR_size_maxHeight=3500;p.ef_colorSpace='ProPhotoRGB'
            f.preview(p)
            assert(#renderedSettings==1 and not p.ef_previewBusy)
            local s=renderedSettings[1]
            assert(s.LR_exportServiceProvider=='com.adobe.ag.export.file')
            assert(s.LR_size_maxHeight==3500 and s.LR_export_colorSpace=='ProPhotoRGB')
            assert(s.LR_embeddedMetadataOption=='copyrightOnly' and s.LR_removeLocationMetadata)
            assert(DIALOG and DIALOG.contents[1].kind=='picture')
        ''')
        self.assertTrue(self.jobs[0]["preview"])
        self.assertEqual(Path(self.jobs[0]["output_path"]).suffix, ".png")

    def test_helper_metadata_failure_is_not_reported_as_success(self):
        self.fail_helper = True
        self.lua.execute('''
            local f=require('Frame');local c=CONTEXT()
            local ok,err=pcall(f.run,SETTINGS(),PHOTO,INPUT_PATH,f.temporary(c),false)
            assert(not ok and tostring(err):find('Test metadata failure'));c:cleanup()
        ''')

    def test_batch_cancel_finishes_helper_and_stops_before_next_photo(self):
        self.cancel_after_call = True
        self.lua.execute('''
            local e=require('Export');local c=CONTEXT();local p=SETTINGS()
            local rendition={photo=PHOTO,waitForRender=function() return true,INPUT_PATH end,
                uploadFailed=function() error('Unexpected export failure') end}
            local ec={propertyTable=p,configureProgress=function() return RENDER_PROGRESS end,
                exportSession={countRenditions=function() return 2 end}}
            function ec:renditions(options)
                assert(options.progressScope==RENDER_PROGRESS)
                local n=0
                return function()
                    if options.stopIfCanceled and options.progressScope.canceled then return nil end
                    n=n+1;if n<=2 then return n,rendition end
                end
            end
            e.processRenderedPhotos(c,ec)
            assert(PROGRESS.finished and RENDER_PROGRESS.finished and RENDER_PROGRESS.canceled)
            assert(PROGRESS_ARGS.functionContext==c and PROGRESS.cancelable and YIELD_COUNT==1)
            assert(PROGRESS.portions[#PROGRESS.portions][1]==1)
            c:cleanup()
        ''')
        self.assertEqual(len(self.jobs), 1)
        self.assertTrue(Path(self.jobs[0]["output_path"]).is_file())

    def test_visible_batch_progress_remains_until_all_helpers_complete(self):
        self.lua.execute('''
            local e=require('Export');local c=CONTEXT();local p=SETTINGS()
            local rendition={photo=PHOTO,waitForRender=function() return true,INPUT_PATH end,
                uploadFailed=function(message) error(message) end}
            local ec={propertyTable=p,configureProgress=function() return RENDER_PROGRESS end,
                exportSession={countRenditions=function() return 2 end}}
            function ec:renditions(options)
                assert(options.progressScope==RENDER_PROGRESS and options.stopIfCanceled)
                local n=0
                return function()
                    assert(not PROGRESS.finished)
                    n=n+1;if n<=2 then return n,rendition end
                end
            end
            e.processRenderedPhotos(c,ec)
            assert(PROGRESS.finished and RENDER_PROGRESS.finished and not PROGRESS.canceled)
            assert(PROGRESS.portions[1][1]==0 and PROGRESS.portions[1][2]==2)
            assert(PROGRESS.portions[2][1]==1 and PROGRESS.portions[3][1]==2)
            assert(YIELD_COUNT==2);c:cleanup()
        ''')
        self.assertEqual(len(self.jobs), 2)

    def test_job_passes_explicit_native_person_removal_policy(self):
        self.lua.execute('''
            local f=require('Frame');local c=CONTEXT();local p=SETTINGS()
            p.LR_removeFaceMetadata=true;f.run(p,PHOTO,INPUT_PATH,f.temporary(c),false)
            p.LR_removeFaceMetadata=false;f.run(p,PHOTO,INPUT_PATH,f.temporary(c),false)
            c:cleanup()
        ''')
        self.assertIs(self.jobs[0]["remove_person_info"], True)
        self.assertIs(self.jobs[1]["remove_person_info"], False)

    def test_cancel_when_progress_paints_skips_unstarted_helper(self):
        self.lua.execute('''
            CANCEL_AT_YIELD=true
            local e=require('Export');local c=CONTEXT();local p=SETTINGS()
            local rendition={photo=PHOTO,waitForRender=function() return true,INPUT_PATH end,
                uploadFailed=function(message) error(message) end}
            local ec={propertyTable=p,configureProgress=function() return RENDER_PROGRESS end,
                exportSession={countRenditions=function() return 2 end}}
            function ec:renditions(options)
                local n=0
                return function()
                    if options.progressScope:isCanceled() then return nil end
                    n=n+1;if n<=2 then return n,rendition end
                end
            end
            e.processRenderedPhotos(c,ec)
            assert(PROGRESS.finished and PROGRESS.canceled and RENDER_PROGRESS.canceled)
            c:cleanup()
        ''')
        self.assertEqual(len(self.jobs), 0)
        self.assertFalse(self.input.exists())


if __name__ == "__main__":
    unittest.main()
