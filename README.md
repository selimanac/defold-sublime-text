# Defold Sublime Text Package

A Sublime Text package for controlling the Defold Editor using its HTTP API and managing the Defold extender server.

## Features

- Control Defold Editor using the HTTP API
- Start, stop, and restart the local extender server
- Handle multiple open Defold projects simultaneously
- Monitor `.internal/editor.port` file changes automatically
- Support for all Defold Editor commands
- Key bindings for common operations

## Installation

**This package requires Sublime Text 4 build 4200 or newer**

This package was specifically designed for the latest features in Sublime Text 4 (build 4200+) and will not work with earlier versions.

You can enable Python 3.8 support by adding the following to your (Settings->Settings) Preferences.sublime-settings file:

```json
"disable_plugin_host_3.3": true
```

### Manual Installation

1. Clone this repository or download the ZIP
2. Copy the folder to your Sublime Text Packages directory:
   - Windows: `%APPDATA%\Sublime Text\Packages\`
   - macOS: `~/Library/Application Support/Sublime Text/Packages/`
   - Linux: `~/.config/sublime-text/Packages/`

### Package Control

*Coming soon*


## Configuration

Configure the package through the menu: `Tools > Defold > Settings`

Key settings:

- `default_port`: Override the auto-detected port. Only use this if you've launched Defold with a custom port using the `--port` parameter (default: null)
- `extender_server_script`: Path to the extender server script (default: "")
- `auto_start_extender`: Whether to automatically start the extender server (default: false)
- `console_refresh_interval`: How often the console should refresh, in seconds (default: 2.0)

Example configuration:

```json
{
    "default_port": 8181,
    "extender_server_script": "/path/to/extender/server/scripts/standalone/service-standalone.sh",
    "auto_start_extender": true,
    "console_refresh_interval": 1.5
}
```

**Note about port setting:** If you've launched Defold Editor with a custom port like:
```
# on Windows
.\Defold.exe --port 8181

# on Linux:
./Defold --port 8181

# on macOS:
./Defold.app/Contents/MacOS/Defold --port 8181
```

You should set the `default_port` to match this value (8181 in the example).

## Key Bindings
### Build Commands

- **Ctrl+B, Ctrl+B**: Build
- **Ctrl+B, Ctrl+H**: Hot Reload
- **Ctrl+B, Ctrl+R**: Rebuild
- **Ctrl+B, Ctrl+5**: Build HTML5

### Debugger Commands

- **Ctrl+D, Ctrl+S**: Debugger Start
- **Ctrl+D, Ctrl+X**: Debugger Stop
- **Ctrl+D, Ctrl+B**: Debugger Break
- **Ctrl+D, Ctrl+C**: Debugger Continue
- **Ctrl+D, Ctrl+I**: Debugger Step Into
- **Ctrl+D, Ctrl+O**: Debugger Step Over
- **Ctrl+D, Ctrl+U**: Debugger Step Out
- **Ctrl+D, Ctrl+D**: Debugger Detach

### Extender Server Commands

- **Ctrl+E, Ctrl+S**: Start Extender Server
- **Ctrl+E, Ctrl+X**: Stop Extender Server
- **Ctrl+E, Ctrl+R**: Restart Extender Server

### Console Commands

- **Ctrl+D, Ctrl+C**: Show Console

## Customizing Key Bindings

To customize key bindings:

1. Open `Preferences -> Key Bindings`
2. Copy the bindings you want to modify from [Default.sublime-keymap](https://github.com/selimanac/defold-sublime-text/blob/d8267f2cb9ad68c97cc60a95d2cab53b53e33801/Default.sublime-keymap)
3. Paste them into the right panel (User key bindings)
4. Modify them as needed

For example, to change the Hot Reload shortcut to `Ctrl+Shift+R`:

```json
[
    {
        "keys": [
            "ctrl+shift+r"
        ],
        "command": "defold_command_handler",
        "args": {
            "command": "hot-reload"
        }
    }
]
```

## Console Usage

The console view shows output from the Defold Editor with clickable file references. Click on the triangles (▶) next to file paths to jump directly to that file and line number.

## Commands

All Defold commands are available through the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`) and the `Tools > Defold` menu.