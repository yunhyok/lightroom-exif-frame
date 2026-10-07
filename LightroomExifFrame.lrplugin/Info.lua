return {
    LrSdkVersion = 13.0,
    LrSdkMinimumVersion = 13.0,
    LrToolkitIdentifier = 'io.github.yunhyok.lightroomexifframe',
    LrPluginName = 'Lightroom EXIF Frame',
    LrPluginInfoProvider = 'Manager.lua',
    LrExportServiceProvider = { title = 'EXIF Frame', file = 'Export.lua' },
    LrLimitNumberOfTempRenditions = true,
    LrLibraryMenuItems = {{ title = 'EXIF Frame: Diagnostics / 진단', file = 'Diagnostics.lua' }},
    VERSION = { major = 0, minor = 1, revision = 0, build = 0 },
}
