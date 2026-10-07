-- Small JSON boundary for the file protocol. No executable Lua is read from jobs/results.
local Json = { null = {} }
local escapes = { ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f',
    ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
local function quote(s)
    return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
        return escapes[c] or string.format('\\u%04x', c:byte())
    end) .. '"'
end
function Json.encode(value)
    local seen = {}
    local function encode(v, depth)
        assert(depth <= 64, 'JSON nesting too deep')
        if v == Json.null or v == nil then return 'null' end
        local kind = type(v)
        if kind == 'string' then return quote(v) end
        if kind == 'boolean' then return tostring(v) end
        if kind == 'number' then
            assert(v == v and v ~= math.huge and v ~= -math.huge, 'Invalid JSON number')
            return string.format('%.17g', v)
        end
        assert(kind == 'table' and not seen[v], 'Invalid/cyclic JSON value')
        seen[v] = true
        local count, max, array = 0, 0, true
        for k in pairs(v) do
            count = count + 1
            if type(k) ~= 'number' or k < 1 or k % 1 ~= 0 then array = false
            elseif k > max then max = k end
        end
        array = array and count > 0 and count == max
        local out = {}
        if array then
            for i = 1, max do out[i] = encode(v[i], depth + 1) end
        else
            for k, x in pairs(v) do
                assert(type(k) == 'string', 'JSON object keys must be strings')
                out[#out + 1] = quote(k) .. ':' .. encode(x, depth + 1)
            end
            table.sort(out)
        end
        seen[v] = nil
        return (array and '[' or '{') .. table.concat(out, ',') .. (array and ']' or '}')
    end
    return encode(value, 0)
end
local function utf8(n)
    if n < 128 then return string.char(n) end
    if n < 2048 then return string.char(192 + math.floor(n / 64), 128 + n % 64) end
    if n < 65536 then return string.char(224 + math.floor(n / 4096),
        128 + math.floor(n / 64) % 64, 128 + n % 64) end
    return string.char(240 + math.floor(n / 262144), 128 + math.floor(n / 4096) % 64,
        128 + math.floor(n / 64) % 64, 128 + n % 64)
end
function Json.decode(text)
    assert(type(text) == 'string' and #text <= 1048576, 'Invalid/oversized JSON result')
    if text:sub(1, 3) == '\239\187\191' then text = text:sub(4) end
    local pos = 1
    local function ws() local _, last = text:find('^[ \t\r\n]*', pos); pos = (last or pos - 1) + 1 end
    local function char() return text:sub(pos, pos) end
    local function expect(c) assert(char() == c, 'Invalid JSON at byte ' .. pos); pos = pos + 1 end
    local function hex()
        local h = text:sub(pos, pos + 3)
        assert(#h == 4 and h:match('^%x%x%x%x$'), 'Invalid JSON unicode escape')
        pos = pos + 4
        return tonumber(h, 16)
    end
    local function str()
        expect('"')
        local out = {}
        while pos <= #text do
            local c = char(); pos = pos + 1
            if c == '"' then return table.concat(out) end
            assert(c:byte() >= 32, 'JSON control character')
            if c == '\\' then
                c = char(); pos = pos + 1
                if c == 'u' then
                    local n = hex()
                    if n >= 55296 and n <= 56319 then
                        expect('\\'); expect('u')
                        local low = hex()
                        assert(low >= 56320 and low <= 57343, 'Invalid JSON surrogate pair')
                        n = 65536 + (n - 55296) * 1024 + low - 56320
                    else assert(n < 56320 or n > 57343, 'Invalid JSON surrogate') end
                    c = utf8(n)
                else
                    local unescape = { ['"'] = '"', ['\\'] = '\\', ['/'] = '/', b = '\b',
                        f = '\f', n = '\n', r = '\r', t = '\t' }
                    c = assert(unescape[c], 'Invalid JSON escape')
                end
            end
            out[#out + 1] = c
        end
        error('Unterminated JSON string')
    end
    local parse
    parse = function(depth)
        assert(depth <= 64, 'JSON nesting too deep'); ws()
        local c = char()
        if c == '"' then return str() end
        if c == '{' or c == '[' then
            local object, close, out = c == '{', c == '{' and '}' or ']', {}
            pos = pos + 1; ws()
            if char() == close then pos = pos + 1; return out end
            while true do
                local key
                if object then key = str(); ws(); expect(':') end
                local val = parse(depth + 1)
                if object then assert(out[key] == nil, 'Duplicate JSON key'); out[key] = val
                else out[#out + 1] = val end
                ws()
                if char() == close then pos = pos + 1; return out end
                expect(','); ws()
            end
        end
        for literal, val in pairs({ ['true'] = true, ['false'] = false, ['null'] = Json.null }) do
            if text:sub(pos, pos + #literal - 1) == literal then pos = pos + #literal; return val end
        end
        local token = text:match('^-?%d+%.%d+[eE][+-]?%d+', pos)
            or text:match('^-?%d+[eE][+-]?%d+', pos)
            or text:match('^-?%d+%.%d+', pos) or text:match('^-?%d+', pos)
        assert(token and not token:match('^-?0%d'), 'Invalid JSON value')
        local n = assert(tonumber(token), 'Invalid JSON number')
        assert(n ~= math.huge and n ~= -math.huge, 'JSON number overflow')
        pos = pos + #token; return n
    end
    local value = parse(0); ws()
    assert(pos > #text, 'Trailing JSON data')
    return value
end
return Json
