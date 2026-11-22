local Frame = require 'Frame'
return { sectionsForTopOfDialog = function(f)
    return {{ title = 'Lightroom EXIF Frame 0.2.1',
        f:static_text {title = Frame.text('Windows • Lightroom Classic 13+ API • 16 Themes • Historical Brand CI Logos',
            'Windows • Lightroom Classic 13+ API • 16개 프레임 테마 • 카메라 연대별 제조사 CI 로고')},
        f:static_text {title = Frame.text('Choose EXIF Frame in Export To. Uses native Export Location and File Naming; add custom PNG/SVG logos in the export dialog.',
            '내보낼 위치에서 EXIF Frame을 선택하세요. 라이트룸 기본 내보내기 위치 및 파일 이름 지정과 연동되며, 내보내기 창에서 사용자 PNG/SVG 로고도 등록할 수 있습니다.'),
            width_in_chars = 70, height_in_lines = 2, wrap = true},
        f:push_button {title = Frame.text('Diagnostics…','진단…'), action = function() Frame.diagnostics() end},
    }}
end }
