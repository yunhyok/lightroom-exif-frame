local Frame = require 'Frame'
return { sectionsForTopOfDialog = function(f)
    return {{ title = 'Lightroom EXIF Frame 0.1.0',
        f:static_text {title = Frame.text('Windows • Lightroom Classic 13+ API • Strap / Simple / None',
            'Windows • Lightroom Classic 13+ API • Strap / Simple / None')},
        f:static_text {title = Frame.text('Choose EXIF Frame in Export To. Add your own official PNG logos in the export dialog.',
            '내보낼 위치에서 EXIF Frame을 선택하세요. 공식 PNG 로고는 내보내기 창에서 직접 등록할 수 있습니다.'),
            width_in_chars = 70, height_in_lines = 2, wrap = true},
        f:push_button {title = Frame.text('Diagnostics…','진단…'), action = function() Frame.diagnostics() end},
    }}
end }
