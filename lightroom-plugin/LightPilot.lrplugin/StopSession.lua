-- StopSession.lua — executed when user clicks "LightPilot — Stop"

local LrDialogs = import "LrDialogs"
local State     = require "State"

if State.running then
    State.running = false
    LrDialogs.showBezel("LightPilot stopped", 2)
else
    LrDialogs.showBezel("LightPilot is not running", 2)
end
