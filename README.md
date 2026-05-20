# Hyprland Settings Panel

A visual settings panel for Hyprland with a modern web UI.

## Features

- **Dynamic Theming** — Reads your Omarchy theme's `colors.toml` and generates CSS variables automatically
- **Light/Dark Mode** — Detects `light.mode` or calculates background brightness
- **All Hyprland Settings** — General, Decoration, Animations, Group, Dwindle, Master, Scrolling, Input, Touchpad, Gestures, Tablet, Cursor, Misc, Binds, XWayland, Ecosystem
- **Visual Presets** — Performance, Minimal, Balanced, Full Effects
- **Keyboard Presets** — BR ThinkPad, US Dvorak, US Colemak, German
- **Locale Management** — Change system locale via `localectl`
- **Color Preview** — Real-time color preview for border/color settings
- **Search** — Filter settings by name
- **Systemd Compatible** — SIGTERM handler for clean shutdown

## Installation

```bash
# Copy to your PATH
cp hyprland-settings-panel ~/.local/bin/
chmod +x ~/.local/bin/hyprland-settings-panel

# Run
hyprland-settings-panel
```

## Usage

The panel runs on port 9847 by default. It will:

1. Start an HTTP server on `127.0.0.1:9847`
2. Open the panel in your default browser (or `omarchy-launch-webapp` if available)
3. Apply settings instantly via `hyprctl keyword`
4. Save settings to `~/.config/hypr/user-settings.conf`
5. Auto-source the file in `~/.config/hypr/hyprland.conf`

## Systemd Service

To run as a background service:

```ini
# ~/.config/systemd/user/hyprland-settings-panel.service
[Unit]
Description=Hyprland Settings Panel
After=graphical-session.target

[Service]
ExecStart=%h/.local/bin/hyprland-settings-panel
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now hyprland-settings-panel.service
```

## Keybinding

Add to your Hyprland config:

```
bind = SUPER ALT, V, exec, hyprland-settings-panel
```

## Requirements

- Hyprland 0.54+
- Python 3.10+
- `hyprctl` available in PATH
- `localectl` (optional, for locale management)
- `omarchy` (optional, for theme detection)

## License

MIT
