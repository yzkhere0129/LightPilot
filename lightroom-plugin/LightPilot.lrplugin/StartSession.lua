-- StartSession.lua — executed when user clicks "LightPilot — Start"

local LrTasks           = import "LrTasks"
local LrDialogs         = import "LrDialogs"
local LrFunctionContext = import "LrFunctionContext"

local State       = require "State"
local FileWatcher = require "FileWatcher"

if State.running then
    LrDialogs.message("LightPilot", "Session is already running.", "info")
    return
end

State.running = true

LrTasks.startAsyncTask(function()
    LrFunctionContext.callWithContext("lightpilot_session", function(context)
        LrDialogs.showBezel("LightPilot session started", 3)

        FileWatcher.run(context, function()
            return State.running
        end)

        LrDialogs.showBezel("LightPilot session ended", 2)
        State.running = false
    end)
end)
