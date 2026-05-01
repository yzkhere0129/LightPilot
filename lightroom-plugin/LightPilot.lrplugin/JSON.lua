--[[
  Minimal JSON encoder/decoder for Lua 5.1+ (LR Classic uses Lua 5.1).
  Supports: null, boolean, number, string, array, object.
  Limitations: no unicode escape, no NaN/Infinity.

  Usage:
    local JSON = require "JSON"
    local str  = JSON.encode({ key = "value", n = 42 })
    local tbl  = JSON.decode('{"key":"value","n":42}')
--]]

local JSON = {}

-- -----------------------------------------------------------------------
-- Encode
-- -----------------------------------------------------------------------

local function encodeValue(val, indent, level)
    local t = type(val)
    if val == nil or val == JSON.null then
        return "null"
    elseif t == "boolean" then
        return val and "true" or "false"
    elseif t == "number" then
        if val ~= val then return "null" end  -- NaN
        return tostring(val)
    elseif t == "string" then
        return '"' .. val:gsub('\\', '\\\\')
                         :gsub('"',  '\\"')
                         :gsub('\n', '\\n')
                         :gsub('\r', '\\r')
                         :gsub('\t', '\\t') .. '"'
    elseif t == "table" then
        -- Detect array vs object
        local isArray = true
        local maxN = 0
        for k, _ in pairs(val) do
            if type(k) ~= "number" or k ~= math.floor(k) or k < 1 then
                isArray = false
                break
            end
            if k > maxN then maxN = k end
        end
        if isArray and maxN == #val then
            local parts = {}
            for _, v in ipairs(val) do
                parts[#parts + 1] = encodeValue(v, indent, level + 1)
            end
            return "[" .. table.concat(parts, ",") .. "]"
        else
            local parts = {}
            for k, v in pairs(val) do
                parts[#parts + 1] = encodeValue(tostring(k)) .. ":" .. encodeValue(v, indent, level + 1)
            end
            return "{" .. table.concat(parts, ",") .. "}"
        end
    else
        return '"[' .. t .. ']"'
    end
end

function JSON.encode(val)
    return encodeValue(val, nil, 0)
end

-- Sentinel for explicit null
JSON.null = setmetatable({}, { __tostring = function() return "null" end })

-- -----------------------------------------------------------------------
-- Decode
-- -----------------------------------------------------------------------

local function skipWS(s, i)
    while i <= #s and s:sub(i, i):match("%s") do i = i + 1 end
    return i
end

local decodeValue  -- forward declaration

local function decodeString(s, i)
    -- i points to opening "
    local result = {}
    i = i + 1
    while i <= #s do
        local c = s:sub(i, i)
        if c == '"' then
            return table.concat(result), i + 1
        elseif c == '\\' then
            local e = s:sub(i + 1, i + 1)
            if     e == '"'  then result[#result+1] = '"'
            elseif e == '\\' then result[#result+1] = '\\'
            elseif e == '/'  then result[#result+1] = '/'
            elseif e == 'n'  then result[#result+1] = '\n'
            elseif e == 'r'  then result[#result+1] = '\r'
            elseif e == 't'  then result[#result+1] = '\t'
            elseif e == 'b'  then result[#result+1] = '\b'
            elseif e == 'f'  then result[#result+1] = '\f'
            else result[#result+1] = e
            end
            i = i + 2
        else
            result[#result+1] = c
            i = i + 1
        end
    end
    error("Unterminated string")
end

local function decodeArray(s, i)
    local arr = {}
    i = i + 1  -- skip [
    i = skipWS(s, i)
    if s:sub(i, i) == ']' then return arr, i + 1 end
    while true do
        local val
        val, i = decodeValue(s, i)
        arr[#arr + 1] = val
        i = skipWS(s, i)
        local c = s:sub(i, i)
        if c == ']' then return arr, i + 1
        elseif c == ',' then i = skipWS(s, i + 1)
        else error("Expected ',' or ']' in array at " .. i)
        end
    end
end

local function decodeObject(s, i)
    local obj = {}
    i = i + 1  -- skip {
    i = skipWS(s, i)
    if s:sub(i, i) == '}' then return obj, i + 1 end
    while true do
        i = skipWS(s, i)
        local key
        key, i = decodeString(s, i)
        i = skipWS(s, i)
        if s:sub(i, i) ~= ':' then error("Expected ':' at " .. i) end
        i = skipWS(s, i + 1)
        local val
        val, i = decodeValue(s, i)
        obj[key] = val
        i = skipWS(s, i)
        local c = s:sub(i, i)
        if c == '}' then return obj, i + 1
        elseif c == ',' then i = skipWS(s, i + 1)
        else error("Expected ',' or '}' in object at " .. i)
        end
    end
end

decodeValue = function(s, i)
    i = skipWS(s, i)
    local c = s:sub(i, i)
    if c == '"' then
        return decodeString(s, i)
    elseif c == '[' then
        return decodeArray(s, i)
    elseif c == '{' then
        return decodeObject(s, i)
    elseif s:sub(i, i + 3) == "true" then
        return true, i + 4
    elseif s:sub(i, i + 4) == "false" then
        return false, i + 5
    elseif s:sub(i, i + 3) == "null" then
        return nil, i + 4
    else
        local num = s:match("^-?%d+%.?%d*[eE]?[+-]?%d*", i)
        if num then
            return tonumber(num), i + #num
        end
        error("Unexpected character '" .. c .. "' at position " .. i)
    end
end

function JSON.decode(s)
    local val, _ = decodeValue(s, 1)
    return val
end

return JSON
