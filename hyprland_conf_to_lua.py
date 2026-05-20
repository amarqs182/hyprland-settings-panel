#!/usr/bin/env python3
"""
Hyprland .conf to .lua Converter

Converts Hyprland hyprlang configs to Lua format (Hyprland 0.55+).
Handles:
  - source = → require()
  - $variables → local variables
  - Nested sections → hl.config({ ... })
  - bind/bindd → hl.bind()/hl.bindd()
  - windowrule → hl.windowrule()
  - exec/exec-once → hl.exec_cmd()/hl.on("hyprland.start", ...)
  - monitor → hl.monitor()
  - workspace → hl.workspace()
  - plugin: → hl.plugin()
  - # comments → -- comments

Usage:
  hyprland-conf-to-lua [file.conf]           # Convert single file
  hyprland-conf-to-lua --scan ~/.config/hypr # Scan and convert all .conf
  hyprland-conf-to-lua --dry-run             # Preview without writing
  hyprland-conf-to-lua --backup              # Backup .conf before converting
"""

import os
import re
import sys
import shutil
import glob
import argparse
from pathlib import Path
from datetime import datetime


class HyprlangToLua:
    """Converts hyprlang config to Lua format."""

    def __init__(self, source_file=None):
        self.source_file = source_file
        self.lines = []
        self.output = []
        self.indent = 0
        self.variables = {}  # $var = value
        self.requires = []   # source = path
        self.in_block = False

    def pad(self):
        return "  " * self.indent

    def add(self, line):
        self.output.append(f"{self.pad()}{line}")

    def add_raw(self, line):
        self.output.append(line)

    def convert_value(self, val):
        """Convert a hyprlang value to Lua."""
        val = val.strip()

        # Boolean
        if val.lower() in ("true", "on", "yes"):
            return "true"
        if val.lower() in ("false", "off", "no"):
            return "false"

        # Color values (rgba, rgb, hex)
        if val.startswith("rgba(") or val.startswith("rgb("):
            return f'"{val}"'
        if val.startswith("0x"):
            return f'"{val}"'

        # Gradient with angle (e.g. "rgba(F5B700ee) rgba(7A5C00ee) 45deg")
        if "deg" in val:
            parts = val.split()
            colors = []
            angle = None
            for p in parts:
                if p.endswith("deg"):
                    angle = p.replace("deg", "")
                else:
                    colors.append(p)
            if angle and colors:
                colors_str = ", ".join(f'"{c}"' for c in colors)
                return f'{{ colors = {{ {colors_str} }}, angle = {angle} }}'

        # Variable reference
        if val.startswith("$"):
            var_name = val[1:].replace("-", "_")
            return var_name

        # Number
        try:
            if "." in val:
                float(val)
                return val
            int(val)
            return val
        except ValueError:
            pass

        # Multiple values (e.g. "5 5 5 5" for gaps)
        if " " in val and not val.startswith('"'):
            # Check if it's a multi-value like gaps
            parts = val.split()
            if all(self._is_number(p) for p in parts):
                return f'{{ {", ".join(parts)} }}'

        # String (escape quotes)
        val_escaped = val.replace('"', '\\"')
        return f'"{val_escaped}"'

    def _is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def convert_key(self, key):
        """Convert hyprlang key to Lua key."""
        # col.active_border → col = { active_border = ... }
        # But we handle this at the section level
        return key.replace("-", "_")

    def parse_line(self, line):
        """Parse a single hyprlang line."""
        stripped = line.strip()

        # Empty line
        if not stripped:
            self.add_raw("")
            return

        # Comment
        if stripped.startswith("#"):
            comment = stripped[1:].strip()
            self.add(f"-- {comment}")
            return

        # source = path
        if stripped.startswith("source"):
            match = re.match(r'source\s*=\s*(.+)', stripped)
            if match:
                src_path = match.group(1).strip()
                # Remove comments
                if "#" in src_path:
                    src_path = src_path.split("#")[0].strip()
                self.requires.append(src_path)
                # Keep as source = for external paths, convert to require for local
                if "~/.config/hypr/" in src_path:
                    req_path = src_path.replace("~/.config/hypr/", "").replace(".conf", "")
                    self.add(f'require("{req_path}")')
                else:
                    # External path - keep as source
                    self.add(f'-- source: {src_path}')
                return

        # $variable = value
        if stripped.startswith("$"):
            match = re.match(r'\$(\S+)\s*=\s*(.+)', stripped)
            if match:
                var_name = match.group(1).replace("-", "_")
                value = self.convert_value(match.group(2))
                self.variables[var_name] = value
                self.add(f"local {var_name} = {value}")
                return

        # exec-once = command
        if stripped.startswith("exec-once"):
            match = re.match(r'exec-once\s*=\s*(.+)', stripped)
            if match:
                cmd = match.group(1).strip().replace('"', '\\"')
                self.add(f'hl.on("hyprland.start", function()')
                self.indent += 1
                self.add(f'hl.exec_cmd("{cmd}")')
                self.indent -= 1
                self.add(f'end)')
                return

        # exec = command
        if stripped.startswith("exec "):
            match = re.match(r'exec\s*=\s*(.+)', stripped)
            if match:
                cmd = match.group(1).strip().replace('"', '\\"')
                self.add(f'hl.exec_cmd("{cmd}")')
                return

        # monitor = ...
        if stripped.startswith("monitor"):
            match = re.match(r'monitor\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip()
                self._convert_monitor(args)
                return

        # workspace = ...
        if stripped.startswith("workspace"):
            match = re.match(r'workspace\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip()
                self.add(f'hl.workspace({{ {self._parse_monitor_args(args)} }})')
                return

        # windowrule = ...
        if stripped.startswith("windowrule"):
            match = re.match(r'windowrule\s*=\s*(.+)', stripped)
            if match:
                rule = match.group(1).strip()
                self._convert_windowrule(rule)
                return

        # windowrulev2 = ...
        if stripped.startswith("windowrulev2"):
            match = re.match(r'windowrulev2\s*=\s*(.+)', stripped)
            if match:
                rule = match.group(1).strip()
                self._convert_windowrule(rule, v2=True)
                return

        # bind/bindd/binddm/... (but NOT "binds {" which is a section)
        if stripped.startswith("bind") and "=" in stripped and not stripped.startswith("binds "):
            self._convert_bind(stripped)
            return

        # unbind = ...
        if stripped.startswith("unbind"):
            match = re.match(r'unbind\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip()
                self.add(f'hl.unbind({{ {self._parse_bind_args(args)} }})')
                return

        # plugin:name:option = value
        if stripped.startswith("plugin:"):
            match = re.match(r'plugin:(\S+?):(\S+)\s*=\s*(.+)', stripped)
            if match:
                plugin = match.group(1)
                option = match.group(2).replace("-", "_")
                value = self.convert_value(match.group(3))
                self.add(f'hl.plugin("{plugin}", {{ {option} = {value} }})')
                return

        # bezier = "name, x1, y1, x2, y2" (standalone, top-level only)
        if stripped.startswith("bezier") and self.indent == 0:
            match = re.match(r'bezier\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip().strip('"')
                parts = [p.strip() for p in args.split(",")]
                if len(parts) >= 5:
                    name = parts[0]
                    points = ", ".join(parts[1:])
                    self.add(f'hl.curve("{name}", {{ type = "bezier", points = {{ {{ {points} }} }} }})')
                    return

        # animation = "name, on/off, speed, curve, style" (standalone, top-level only)
        if stripped.startswith("animation") and self.indent == 0:
            match = re.match(r'animation\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip().strip('"')
                parts = [p.strip() for p in args.split(",")]
                if len(parts) >= 4:
                    leaf = parts[0]
                    enabled = parts[1] in ("1", "true", "yes")
                    speed = parts[2]
                    bezier = parts[3]
                    style = parts[4] if len(parts) > 4 else None
                    style_arg = f', style = "{style}"' if style else ""
                    self.add(f'hl.animation({{ leaf = "{leaf}", enabled = {"true" if enabled else "false"}, speed = {speed}, bezier = "{bezier}"{style_arg} }})')
                    return

        # Section opening: name {
        if "{" in stripped and not stripped.startswith("--"):
            match = re.match(r'(\S+)\s*\{', stripped)
            if match:
                section = match.group(1).replace("-", "_")
                self.add(f"{section} = {{")
                self.indent += 1
                self.in_block = True
                return

        # Section closing
        if stripped == "}":
            if self.indent > 0:
                self.indent -= 1
                self.add("},")
            return

        # bezier = "name, x1, y1, x2, y2"
        if stripped.startswith("bezier"):
            match = re.match(r'bezier\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip().strip('"')
                parts = [p.strip() for p in args.split(",")]
                if len(parts) >= 5:
                    name = parts[0]
                    points = ", ".join(parts[1:])
                    if self.indent > 0:
                        # Inside a section - emit as table entry
                        self.add(f'["{name}"] = {{ type = "bezier", points = {{ {{ {points} }} }} }},')
                    else:
                        # Top-level - emit as hl.curve()
                        self.add(f'hl.curve("{name}", {{ type = "bezier", points = {{ {{ {points} }} }} }})')
                    return

        # animation = "name, on/off, speed, curve, style"
        if stripped.startswith("animation"):
            match = re.match(r'animation\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip().strip('"')
                parts = [p.strip() for p in args.split(",")]
                if len(parts) >= 4:
                    leaf = parts[0]
                    enabled = parts[1] in ("1", "true", "yes")
                    speed = parts[2]
                    bezier = parts[3]
                    style = parts[4] if len(parts) > 4 else None
                    style_arg = f', style = "{style}"' if style else ""
                    if self.indent > 0:
                        # Inside a section - emit as table entry
                        self.add(f'["{leaf}"] = {{ enabled = {"true" if enabled else "false"}, speed = {speed}, bezier = "{bezier}"{style_arg} }},')
                    else:
                        # Top-level - emit as hl.animation()
                        self.add(f'hl.animation({{ leaf = "{leaf}", enabled = {"true" if enabled else "false"}, speed = {speed}, bezier = "{bezier}"{style_arg} }})')
                    return

        # env = KEY, VALUE
        if stripped.startswith("env "):
            match = re.match(r'env\s*=\s*(.+)', stripped)
            if match:
                args = match.group(1).strip()
                parts = [p.strip() for p in args.split(",", 1)]
                if len(parts) == 2:
                    self.add(f'hl.env("{parts[0]}", "{parts[1]}")')
                    return

        # Regular key = value
        if "=" in stripped:
            match = re.match(r'(\S+)\s*=\s*(.+)', stripped)
            if match:
                key = self.convert_key(match.group(1))
                value = self.convert_value(match.group(2))
                if "." in key:
                    parts = key.split(".", 1)
                    parent = self.convert_key(parts[0])
                    child = self.convert_key(parts[1])
                    
                    # Check if we already have this parent in current block
                    # Look back in output for "parent = {"
                    parent_found = False
                    for i in range(len(self.output) - 1, max(len(self.output) - 20, 0), -1):
                        line = self.output[i].strip()
                        if line == f"{parent} = {{":
                            # Insert child before the closing },
                            # Find the closing },
                            for j in range(i + 1, len(self.output)):
                                if self.output[j].strip() == "},":
                                    # Insert before closing
                                    child_pad = "  " * (self.indent + 1)
                                    self.output.insert(j, f"{child_pad}{child} = {value},")
                                    parent_found = True
                                    break
                            break
                        elif line == "}," and i > 0:
                            # Check if this closes our parent
                            continue
                    
                    if not parent_found:
                        self.add(f"{parent} = {{")
                        self.indent += 1
                        self.add(f"{child} = {value},")
                        self.indent -= 1
                        self.add("},")
                else:
                    key = self.convert_key(key)
                    self.add(f"{key} = {value},")
                return

        # Fallback: keep as comment
        self.add(f"-- [unconverted] {stripped}")

    def _convert_monitor(self, args):
        """Convert monitor = args to hl.monitor({...})."""
        parts = [p.strip() for p in args.split(",")]
        if len(parts) >= 1:
            output = parts[0].strip() if parts[0].strip() else "" 
            mode = parts[1] if len(parts) > 1 else "preferred"
            position = parts[2] if len(parts) > 2 else "auto"
            scale = parts[3] if len(parts) > 3 else "1"

            self.add(f'hl.monitor({{')
            self.indent += 1
            self.add(f'output = "{output}",')
            self.add(f'mode = "{mode}",')
            self.add(f'position = "{position}",')
            self.add(f'scale = "{scale}",')
            self.indent -= 1
            self.add(f'}})')

    def _parse_monitor_args(self, args):
        """Parse monitor-style args (name:value pairs)."""
        parts = [p.strip() for p in args.split(",")]
        result = []
        for p in parts:
            if ":" in p:
                k, v = p.split(":", 1)
                result.append(f'{k.strip()} = "{v.strip()}"')
            else:
                result.append(f'"{p}"')
        return ", ".join(result)

    def _convert_bind(self, line):
        """Convert bind* = ... to hl.bind*({...})."""
        # Match bind, bindd, binddm, etc.
        match = re.match(r'(bind\w*)\s*=\s*(.+)', line)
        if not match:
            self.add(f"-- [unconverted bind] {line}")
            return

        bind_type = match.group(1)
        args = match.group(2).strip()

        # Parse bind args: MODS, KEY, [description], dispatcher, params
        # Split by comma, but be careful with commas in commands
        parts = []
        current = ""
        in_quote = False
        for char in args:
            if char == '"' and not in_quote:
                in_quote = True
                current += char
            elif char == '"' and in_quote:
                in_quote = False
                current += char
            elif char == "," and not in_quote:
                parts.append(current.strip())
                current = ""
            else:
                current += char
        if current.strip():
            parts.append(current.strip())

        def escape_lua_string(s):
            """Escape a string for Lua, handling nested quotes."""
            # Remove outer quotes if present
            if s.startswith('"') and s.endswith('"'):
                s = s[1:-1]
            # Escape inner quotes
            s = s.replace('"', '\\"')
            return f'"{s}"'

        if len(parts) >= 3:
            # Determine if it's bindd (with description)
            if bind_type == "bindd" and len(parts) >= 4:
                mods = escape_lua_string(parts[0])
                key = escape_lua_string(parts[1])
                desc = escape_lua_string(parts[2])
                dispatcher = escape_lua_string(parts[3])
                params = escape_lua_string(", ".join(parts[4:])) if len(parts) > 4 else '""'
                self.add(f'hl.bindd({{ mods = {mods}, key = {key}, description = {desc}, dispatcher = {dispatcher}, params = {params} }})')
            else:
                mods = escape_lua_string(parts[0])
                key = escape_lua_string(parts[1])
                dispatcher = escape_lua_string(parts[2])
                params = escape_lua_string(", ".join(parts[3:])) if len(parts) > 3 else '""'
                self.add(f'hl.bind({{ mods = {mods}, key = {key}, dispatcher = {dispatcher}, params = {params} }})')
        else:
            self.add(f"-- [unconverted bind] {line}")

    def _parse_bind_args(self, args):
        """Parse simple bind args."""
        parts = [p.strip() for p in args.split(",")]
        result = []
        for p in parts:
            result.append(f'"{p}"')
        return ", ".join(result)

    def _convert_windowrule(self, rule, v2=False):
        """Convert windowrule to hl.windowrule()."""
        if "," in rule:
            parts = [p.strip() for p in rule.split(",", 1)]
            if len(parts) == 2:
                action = parts[0].strip()
                selector = parts[1].strip()
                # Parse v2 selectors like "match:title ^(Hyprland Settings)$"
                # or "title:^(Hyprland Settings)$"
                if selector.startswith("match:"):
                    # match:title pattern → title = "pattern"
                    sel_parts = selector.split(" ", 1)
                    match_type = sel_parts[0].replace("match:", "")
                    pattern = sel_parts[1] if len(sel_parts) > 1 else ""
                    self.add(f'hl.windowrule({{ "{action}", match = {{ {match_type} = "{pattern}" }} }})')
                elif ":" in selector.split(" ")[0]:
                    # title:pattern format
                    sel_parts = selector.split(" ", 1)
                    match_type, pattern = sel_parts[0].split(":", 1)
                    self.add(f'hl.windowrule({{ "{action}", match = {{ {match_type} = "{pattern}" }} }})')
                else:
                    # Simple selector
                    self.add(f'hl.windowrule({{ "{action}", match = {{ "{selector}" }} }})')
                return
        self.add(f'hl.windowrule({{ "{rule}" }})')

    def convert(self, content):
        """Convert full file content."""
        self.output = []
        self.indent = 0

        lines = content.split("\n")

        # Add header
        if self.source_file:
            self.add(f"-- Converted from: {os.path.basename(self.source_file)}")
            self.add(f"-- Generated by hyprland-conf-to-lua")
            self.add_raw("")

        for line in lines:
            self.parse_line(line)

        # Wrap in hl.config({}) if we have settings (not just require/exec)
        has_settings = any(
            "hl.config" not in l and "require" not in l and "hl.bind" not in l and "hl.exec" not in l and "hl.on" not in l and "hl.curve" not in l and "hl.animation" not in l and "hl.monitor" not in l and "hl.env" not in l and "hl.plugin" not in l and "hl.unbind" not in l and "hl.workspace" not in l and "--" not in l and l.strip()
            for l in self.output
        )

        if has_settings:
            # Check if we have top-level sections that need wrapping
            has_sections = any(
                re.match(r'^\w+ = \{', l.strip())
                for l in self.output
            )
            if has_sections:
                # Find first section and wrap everything after header in hl.config
                new_output = []
                header_done = False
                for i, line in enumerate(self.output):
                    if not header_done and (line.startswith("--") or line.strip() == ""):
                        new_output.append(line)
                    else:
                        if not header_done:
                            header_done = True
                            new_output.append("hl.config({")
                            new_output.append("")
                        # Indent the content
                        if line.strip():
                            new_output.append("  " + line)
                        else:
                            new_output.append("")
                new_output.append("")
                new_output.append("})")
                self.output = new_output

        return "\n".join(self.output)


def scan_directory(dir_path):
    """Scan directory and find all .conf files with their relationships."""
    conf_files = {}
    dir_path = os.path.expanduser(dir_path)

    for conf_file in sorted(glob.glob(os.path.join(dir_path, "*.conf"))):
        name = os.path.basename(conf_file)
        if name in ("hyprlock.conf", "hypridle.conf", "hyprsunset.conf", "xdph.conf"):
            continue  # Skip non-Hyprland configs

        with open(conf_file, "r") as f:
            content = f.read()

        # Find source references
        sources = re.findall(r'source\s*=\s*(.+)', content)
        sources = [s.strip() for s in sources]

        conf_files[name] = {
            "path": conf_file,
            "content": content,
            "sources": sources,
        }

    return conf_files


def convert_single_file(input_path, output_path=None, dry_run=False, backup=False):
    """Convert a single .conf file to .lua."""
    input_path = os.path.expanduser(input_path)

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return False

    if output_path is None:
        output_path = input_path.replace(".conf", ".lua")

    with open(input_path, "r") as f:
        content = f.read()

    converter = HyprlangToLua(source_file=input_path)
    result = converter.convert(content)

    if dry_run:
        print(f"\n{'='*60}")
        print(f"  {os.path.basename(input_path)} → {os.path.basename(output_path)}")
        print(f"{'='*60}")
        print(result)
        return True

    if backup:
        backup_path = f"{input_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy2(input_path, backup_path)
        print(f"  Backup: {backup_path}")

    with open(output_path, "w") as f:
        f.write(result)

    print(f"  Converted: {input_path} → {output_path}")
    return True


def convert_all(dir_path, dry_run=False, backup=False):
    """Convert all .conf files in directory."""
    dir_path = os.path.expanduser(dir_path)
    conf_files = scan_directory(dir_path)

    if not conf_files:
        print(f"No .conf files found in {dir_path}")
        return

    print(f"\nHyprland Config Converter")
    print(f"{'='*60}")
    print(f"Directory: {dir_path}")
    print(f"Found {len(conf_files)} config files")
    print(f"Mode: {'Dry Run' if dry_run else 'Convert'}")
    print(f"{'='*60}\n")

    # Convert each file
    for name, info in conf_files.items():
        print(f"\n[{name}]")
        convert_single_file(info["path"], dry_run=dry_run, backup=backup)

    # Generate main hyprland.lua that requires everything
    main_lua_path = os.path.join(dir_path, "hyprland.lua")

    # Read the main conf to get the require order
    main_conf = conf_files.get("hyprland.conf", {})
    main_content = main_conf.get("content", "")

    # Extract require order from source lines
    require_lines = []
    for line in main_content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("source"):
            match = re.match(r'source\s*=\s*(.+)', stripped)
            if match:
                path = match.group(1).strip()
                # Only convert local files
                if "~/.config/hypr/" in path or "./" in path:
                    req_path = path.replace("~/.config/hypr/", "").replace(".conf", "")
                    req_path = req_path.replace("/", ".").replace("\\", ".")
                    comment = ""
                    if "#" in stripped:
                        comment = stripped.split("#", 1)[1].strip()
                    require_lines.append((req_path, comment))
                else:
                    # External file (e.g. Omarchy defaults) - keep as source
                    require_lines.append((None, path))

    if not dry_run:
        with open(main_lua_path, "w") as f:
            f.write("-- Hyprland Lua Configuration\n")
            f.write("-- Converted from hyprlang by hyprland-conf-to-lua\n")
            f.write("-- Docs: https://wiki.hypr.land/Configuring/\n\n")

            for req_path, comment in require_lines:
                if req_path:
                    if comment:
                        f.write(f"-- {comment}\n")
                    f.write(f'require("{req_path}")\n')
                else:
                    # External source - use hl.source() if available, or comment
                    f.write(f'-- source: {comment}\n')

        print(f"\n[{os.path.basename(main_lua_path)}]")
        print(f"  Generated main config with {len(require_lines)} requires")

    print(f"\n{'='*60}")
    print(f"Done! {'(dry run - no files written)' if dry_run else ''}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Hyprland hyprlang configs to Lua format (0.55+)"
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Single .conf file to convert"
    )
    parser.add_argument(
        "--scan", "-s",
        metavar="DIR",
        help="Scan directory and convert all .conf files"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Preview conversion without writing files"
    )
    parser.add_argument(
        "--backup", "-b",
        action="store_true",
        help="Create .bak files before converting"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (single file mode only)"
    )

    args = parser.parse_args()

    if args.scan:
        convert_all(args.scan, dry_run=args.dry_run, backup=args.backup)
    elif args.file:
        convert_single_file(
            args.file,
            output_path=args.output,
            dry_run=args.dry_run,
            backup=args.backup
        )
    else:
        # Default: scan ~/.config/hypr/
        default_dir = "~/.config/hypr"
        print(f"No file specified, scanning {default_dir}")
        convert_all(default_dir, dry_run=args.dry_run, backup=args.backup)


if __name__ == "__main__":
    main()
