--[[
  FileWatcher.lua — LightPilot
  Polls the bridge directory and reacts to status changes written by Python.

  Protocol (status.txt values):
    idle         — nothing to do
    exporting    — Python wants a preview + settings export
    ready        — Lua has written preview + settings
    applying     — Python has written pending_update.json
    done         — Lua has applied the params
    scan_history / scan_selected / scan_done — style learning
    export_thumbs / thumbs_done — before/after thumbnails
    error        — something went wrong
--]]

local LrApplication       = import "LrApplication"
local LrDevelopController = import "LrDevelopController"
local LrFileUtils         = import "LrFileUtils"
local LrPathUtils         = import "LrPathUtils"
local LrTasks             = import "LrTasks"
local LrDate              = import "LrDate"

local JSON = require "JSON"

-- -----------------------------------------------------------------------
-- Helpers
-- -----------------------------------------------------------------------

local BRIDGE_DIR = LrPathUtils.child(
    LrPathUtils.getStandardFilePath("home"),
    ".lightpilot"
)

local function bridgePath(filename)
    return LrPathUtils.child(BRIDGE_DIR, filename)
end

local function readFile(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local s = f:read("*a")
    f:close()
    return s
end

local function writeFile(path, content)
    LrFileUtils.createAllDirectories(BRIDGE_DIR)
    local f = io.open(path, "w")
    if not f then error("Cannot write to " .. path) end
    f:write(content)
    f:close()
end

local function readStatus()
    return readFile(bridgePath("status.txt")) or "idle"
end

local function writeStatus(s)
    writeFile(bridgePath("status.txt"), s)
end

local function writeHeartbeat()
    writeFile(bridgePath("heartbeat.txt"), tostring(os.time()))
end

local function appendLog(msg)
    local f = io.open(bridgePath("log.txt"), "a")
    if f then
        f:write(os.date("[%Y-%m-%d %H:%M:%S] ") .. msg .. "\n")
        f:close()
    end
end

-- -----------------------------------------------------------------------
-- All LR Develop parameters (PV2012+)
-- -----------------------------------------------------------------------

local DEVELOP_PARAMS = {
    "Exposure2012", "Contrast2012", "Highlights2012", "Shadows2012",
    "Whites2012", "Blacks2012", "Texture", "Clarity2012", "Dehaze",
    "Vibrance", "Saturation", "Temperature", "Tint",
    "ParametricDarks", "ParametricLights",
    "ParametricShadows", "ParametricHighlights",
    "ParametricShadowSplit", "ParametricMidtoneSplit", "ParametricHighlightSplit",
    "HueAdjustmentRed", "HueAdjustmentOrange", "HueAdjustmentYellow",
    "HueAdjustmentGreen", "HueAdjustmentAqua", "HueAdjustmentBlue",
    "HueAdjustmentPurple", "HueAdjustmentMagenta",
    "SaturationAdjustmentRed", "SaturationAdjustmentOrange",
    "SaturationAdjustmentYellow", "SaturationAdjustmentGreen",
    "SaturationAdjustmentAqua", "SaturationAdjustmentBlue",
    "SaturationAdjustmentPurple", "SaturationAdjustmentMagenta",
    "LuminanceAdjustmentRed", "LuminanceAdjustmentOrange",
    "LuminanceAdjustmentYellow", "LuminanceAdjustmentGreen",
    "LuminanceAdjustmentAqua", "LuminanceAdjustmentBlue",
    "LuminanceAdjustmentPurple", "LuminanceAdjustmentMagenta",
    "ColorGradeShadowHue", "ColorGradeShadowSat", "ColorGradeShadowLum",
    "ColorGradeMidtoneHue", "ColorGradeMidtoneSat", "ColorGradeMidtoneLum",
    "ColorGradeHighlightHue", "ColorGradeHighlightSat", "ColorGradeHighlightLum",
    "ColorGradeGlobalHue", "ColorGradeGlobalSat", "ColorGradeGlobalLum",
    "ColorGradeBlending", "ColorGradeBalance",
    "Sharpness", "SharpenRadius", "SharpenDetail", "SharpenEdgeMasking",
    "LuminanceSmoothing", "LuminanceNoiseReductionDetail",
    "LuminanceNoiseReductionContrast",
    "ColorNoiseReduction", "ColorNoiseReductionDetail",
    "ColorNoiseReductionSmoothness",
    "LensProfileDistortionScale", "LensProfileChromaticAberrationScale",
    "LensProfileVignettingScale", "LensManualDistortionAmount",
    "DefringePurpleAmount", "DefringeGreenAmount",
    "PerspectiveVertical", "PerspectiveHorizontal",
    "PerspectiveRotate", "PerspectiveScale", "PerspectiveAspect",
    "PostCropVignetteAmount", "PostCropVignetteMidpoint",
    "PostCropVignetteFeather", "PostCropVignetteRoundness",
    "PostCropVignetteHighlightContrast",
    "GrainAmount", "GrainSize", "GrainFrequency",
    "ShadowTint", "RedHue", "RedSaturation",
    "GreenHue", "GreenSaturation", "BlueHue", "BlueSaturation",
    "CropTop", "CropLeft", "CropBottom", "CropRight", "CropAngle",
}

-- -----------------------------------------------------------------------
-- Export develop settings as JSON
-- -----------------------------------------------------------------------

local function exportSettings(photo)
    local settings = {}
    local devSettings = photo:getDevelopSettings()
    for _, param in ipairs(DEVELOP_PARAMS) do
        local val = devSettings[param]
        if val ~= nil then settings[param] = val end
    end
    return settings
end

-- -----------------------------------------------------------------------
-- Write photo file path + metadata for Python to generate its own preview.
-- No export/render calls here — avoids the "Yielding" error entirely.
-- -----------------------------------------------------------------------

local function exportPreview(photo)
    local filePath = photo:getRawMetadata("path") or ""
    writeFile(bridgePath("current_photo_path.txt"), filePath)

    -- If source is JPEG/PNG/TIFF, copy it as preview for Python
    local previewPath = bridgePath("current_preview.jpg")
    local ext = filePath:lower():match("%.(%w+)$") or ""

    if ext == "jpg" or ext == "jpeg" or ext == "png" or ext == "tif" or ext == "tiff" then
        pcall(function()
            if LrFileUtils.exists(previewPath) then
                LrFileUtils.delete(previewPath)
            end
            LrFileUtils.copy(filePath, previewPath)
            appendLog("Copied source image as preview: " .. ext)
        end)
    else
        -- RAW file: write path, Python will use rawpy/dcraw to render
        appendLog("Source is RAW (" .. ext .. "), Python will render preview")
    end

    return previewPath
end

-- -----------------------------------------------------------------------
-- Apply parameter deltas
-- -----------------------------------------------------------------------

local function applyDeltas(photo, catalog, deltas)
    -- Try LrDevelopController (immediate, works in Develop module)
    local controllerOK = true
    for param, delta in pairs(deltas) do
        local ok = pcall(function()
            if param == "Temperature" then
                LrDevelopController.setValue(param, delta)
            else
                local current = LrDevelopController.getValue(param) or 0
                LrDevelopController.setValue(param, current + delta)
            end
        end)
        if not ok then controllerOK = false; break end
    end

    -- Fallback: photo:applyDevelopSettings (works from any module)
    if not controllerOK then
        catalog:withWriteAccessDo("LightPilot: apply", function()
            local cur = photo:getDevelopSettings()
            local newS = {}
            for param, delta in pairs(deltas) do
                if param == "Temperature" then
                    newS[param] = delta
                else
                    newS[param] = (cur[param] or 0) + delta
                end
            end
            photo:applyDevelopSettings(newS)
        end)
    end
end

-- -----------------------------------------------------------------------
-- EXIF metadata
-- -----------------------------------------------------------------------

local EXIF_KEYS = {
    "isoSpeedRating", "focalLength", "aperture", "shutterSpeed",
    "dateTimeOriginal", "cameraMake", "cameraModel", "lensModel",
    "flashFired", "gps",
}

local function getPhotoMetadata(photo)
    local meta = {}
    for _, key in ipairs(EXIF_KEYS) do
        local ok, val = pcall(function() return photo:getRawMetadata(key) end)
        if ok and val ~= nil then
            if key == "gps" and type(val) == "table" then
                meta["gpsLatitude"] = val.latitude
                meta["gpsLongitude"] = val.longitude
            else meta[key] = val end
        end
    end
    for _, key in ipairs({"rating", "colorNameForLabel", "fileFormat"}) do
        local ok, val = pcall(function() return photo:getRawMetadata(key) end)
        if ok and val ~= nil then meta[key] = val end
    end
    local dt = meta["dateTimeOriginal"]
    if dt then
        local ok, d = pcall(function() return LrDate.timestampToComponents(dt) end)
        if ok and d then
            local h = d.hour or 12
            if h >= 5 and h < 9 then meta["timeBucket"] = "golden_morning"
            elseif h >= 9 and h < 16 then meta["timeBucket"] = "midday"
            elseif h >= 16 and h < 20 then meta["timeBucket"] = "golden_evening"
            else meta["timeBucket"] = "night" end
        end
    end
    return meta
end

-- -----------------------------------------------------------------------
-- Style learning: scan catalog
-- -----------------------------------------------------------------------

local _scannedPhotoObjects = {}

local function scanCatalogHistory(catalog, sourcePhotos)
    if not sourcePhotos or #sourcePhotos == 0 then
        sourcePhotos = catalog:getAllPhotos()
    end
    appendLog("Scanning " .. #sourcePhotos .. " photos")

    local editedEntries = {}
    _scannedPhotoObjects = {}

    for idx, photo in ipairs(sourcePhotos) do
        local ok, devSettings = pcall(function() return photo:getDevelopSettings() end)
        if ok and devSettings then
            local exp = devSettings["Exposure2012"] or 0
            local con = devSettings["Contrast2012"] or 0
            local hig = devSettings["Highlights2012"] or 0
            local sha = devSettings["Shadows2012"] or 0

            if math.abs(exp) > 0.01 or math.abs(con) > 1 or
               math.abs(hig) > 1 or math.abs(sha) > 1 then

                local id = tostring(idx)
                pcall(function() id = tostring(photo:getRawMetadata("uuid") or idx) end)

                local entry = { id = id, develop = {}, exif = getPhotoMetadata(photo) }
                for _, param in ipairs(DEVELOP_PARAMS) do
                    local val = devSettings[param]
                    if val ~= nil then entry.develop[param] = val end
                end
                editedEntries[#editedEntries + 1] = entry
                _scannedPhotoObjects[id] = photo
            end
        end
    end

    appendLog("Found " .. #editedEntries .. " edited photos")
    writeFile(bridgePath("style_history.json"), JSON.encode(editedEntries))

    local ok2, targets = pcall(function() return catalog:getTargetPhotos() end)
    if ok2 and targets and #targets > 0 then
        writeFile(bridgePath("current_exif.json"),
                  JSON.encode(getPhotoMetadata(targets[1])))
    end
    return #editedEntries
end

-- -----------------------------------------------------------------------
-- Export before/after thumbnails — writes file paths for Python to handle
-- -----------------------------------------------------------------------

local function exportBeforeAfterThumbs(catalog)
    local raw = readFile(bridgePath("export_thumbs_request.json"))
    if not raw then error("export_thumbs_request.json not found") end
    local ids = JSON.decode(raw).ids or {}

    -- For each requested photo, write its source path + develop settings
    -- Python will handle rendering
    local thumbsInfo = {}
    for _, id in ipairs(ids) do
        local photo = _scannedPhotoObjects[tostring(id)]
        if photo then
            local filePath = photo:getRawMetadata("path") or ""
            local devSettings = photo:getDevelopSettings() or {}
            local entry = { id = id, path = filePath, develop = {} }
            for _, param in ipairs(DEVELOP_PARAMS) do
                local val = devSettings[param]
                if val ~= nil then entry.develop[param] = val end
            end
            thumbsInfo[#thumbsInfo + 1] = entry
        end
    end

    writeFile(bridgePath("thumbs_info.json"), JSON.encode(thumbsInfo))
    appendLog("Wrote thumbs_info for " .. #thumbsInfo .. " photos")
    return #thumbsInfo
end

-- -----------------------------------------------------------------------
-- Main watcher loop
-- -----------------------------------------------------------------------

local FileWatcher = {}

function FileWatcher.run(context, isRunning)
    appendLog("LightPilot started")
    LrFileUtils.createAllDirectories(BRIDGE_DIR)
    writeStatus("idle")

    local catalog = LrApplication.activeCatalog()

    while isRunning() do
        writeHeartbeat()
        local status = readStatus()

        if status == "exporting" then
            local ok, err = pcall(function()
                local photos = catalog:getTargetPhotos()
                if #photos == 0 then error("No photo selected") end
                writeFile(bridgePath("current_settings.json"),
                          JSON.encode(exportSettings(photos[1])))
                exportPreview(photos[1])
                writeStatus("ready")
                appendLog("Export done")
            end)
            if not ok then appendLog("Export error: " .. tostring(err)); writeStatus("error") end

        elseif status == "applying" then
            local ok, err = pcall(function()
                local raw = readFile(bridgePath("pending_update.json"))
                if not raw then error("No pending_update.json") end
                local deltas = JSON.decode(raw).adjustments or {}
                local photos = catalog:getTargetPhotos()
                if #photos == 0 then error("No photo selected") end
                applyDeltas(photos[1], catalog, deltas)
                writeStatus("done")
                appendLog("Applied adjustments")
            end)
            if not ok then appendLog("Apply error: " .. tostring(err)); writeStatus("error") end

        elseif status == "scan_history" then
            local ok, err = pcall(function()
                scanCatalogHistory(catalog, nil); writeStatus("scan_done")
            end)
            if not ok then appendLog("Scan error: " .. tostring(err)); writeStatus("error") end

        elseif status == "scan_selected" then
            local ok, err = pcall(function()
                local sel = catalog:getTargetPhotos()
                if #sel == 0 then error("No photos selected") end
                scanCatalogHistory(catalog, sel); writeStatus("scan_done")
            end)
            if not ok then appendLog("Scan error: " .. tostring(err)); writeStatus("error") end

        elseif status == "export_thumbs" then
            local ok, err = pcall(function()
                exportBeforeAfterThumbs(catalog); writeStatus("thumbs_done")
            end)
            if not ok then appendLog("Thumb error: " .. tostring(err)); writeStatus("error") end
        end

        LrTasks.sleep(0.5)
    end
    appendLog("LightPilot stopped")
end

return FileWatcher
