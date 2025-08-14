# Defold Sublime Package

A Sublime Text package for controlling the Defold Editor using its HTTP API and managing the Defold extender server.

## Features

- Control Defold Editor using the HTTP API
- Start, stop, and restart the local extender server
- Handle multiple open Defold projects simultaneously
- Monitor `.internal/editor.port` file changes automatically
- Support for all Defold Editor commands
- Key bindings for common operations

## Installation

### Manual Installation

1. Clone this repository or download the ZIP
2. Copy the folder to your Sublime Text Packages directory:
   - Windows: `%APPDATA%\Sublime Text\Packages\`
   - macOS: `~/Library/Application Support/Sublime Text/Packages/`
   - Linux: `~/.config/sublime-text/Packages/`

### Package Control

*Coming soon*

## Configuration

Configure the package through the menu: `Tools > Defold > Preferences > Settings`

Key settings:

- `default_port`: Port to use when `.internal/editor.port` is not available (default: null)
- `extender_server_script`: Path to the extender server script (default: "")
- `auto_start_extender`: Whether to automatically start the extender server (default: false)

Example configuration:

```json
{
    "default_port": 9000,
    "extender_server_script": "/path/to/extender/server/scripts/standalone/service-standalone.sh",
    "auto_start_extender": true
}