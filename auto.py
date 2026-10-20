import os
import sys
import time
import argparse
import subprocess
import signal
import platform
import json
import re
import shutil
import ctypes
import shlex
import plistlib

# ------------------------------------------------------------------
# Paths
# ------------------------------------------------------------------
BASE_DIR = os.path.normpath(os.path.expanduser("~/.configs"))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LINUX_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
LINUX_SYSTEMD_USER_DIR = os.path.expanduser("~/.config/systemd/user")
MACOS_LAUNCHAGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
TERMUX_BOOT_DIR = os.path.expanduser("~/.termux/boot")


# ------------------------------------------------------------------
# Platform detection
# ------------------------------------------------------------------
def _is_macos():
    return platform.system().lower() == "darwin" and not _is_ios()


def _is_ios():
    return (
        platform.system().lower() == "darwin"
        and os.environ.get("HOME", "").startswith("/private/var/mobile")
    )


def _is_android():
    return os.environ.get("ANDROID_ROOT") is not None or os.path.exists(
        "/system/build.prop"
    )


def _is_termux():
    return os.environ.get("PREFIX", "").startswith("/data/data/com.termux")


def _is_linux_headless():
    """True when no graphical session is available (Ubuntu Server, RHEL Server,
    SSH-only hosts).  XDG Autostart requires DISPLAY or WAYLAND_DISPLAY."""
    if platform.system().lower() != "linux":
        return False
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


# ------------------------------------------------------------------
# Helpers (shared)
# ------------------------------------------------------------------
def ensure_directory():
    os.makedirs(BASE_DIR, exist_ok=True)
    if platform.system().lower() == "linux":
        os.makedirs(LINUX_AUTOSTART_DIR, exist_ok=True)
        os.makedirs(LINUX_SYSTEMD_USER_DIR, exist_ok=True)
    elif _is_macos():
        # Standard permissions for ~/Library/LaunchAgents are 0755; launchd
        # does not require 0700 and happily scans a 0755 directory owned by
        # the user.  Do not force-chmod a directory that may already hold the
        # user's other LaunchAgents.
        os.makedirs(MACOS_LAUNCHAGENTS_DIR, exist_ok=True)


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    # Write atomically so an interrupted run never leaves a truncated,
    # unparseable state.json behind (which load_state would silently discard,
    # losing the record of every installed program).
    os.makedirs(BASE_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE_FILE)


def sanitize_name(name):
    base = os.path.basename(str(name).replace("\\", "/"))
    for ext in (".pyw", ".py"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    return re.sub(r"[^a-zA-Z0-9\-_]", "-", base).lower() or "program"


def _quote_exec_arg(arg):
    """Quote one argument for the Desktop Entry Exec key.

    The freedesktop.org Desktop Entry Specification (1.5) requires the
    general string escape rule (backslash -> \\\\) to be applied *before*
    the Exec quoting rule.  The resulting literal sequences are:

        \\  ->  \\\\\\\\   (four backslashes)
        $   ->  \\\\$     (two backslashes + dollar)
        `   ->  \\\\`     (two backslashes + backtick)
        "   ->  \\\\"     (two backslashes + double quote)
        %   ->  %%       (literal percent)
    """
    arg = arg.replace("\\", "\\\\\\\\")   # 4 backslashes
    arg = arg.replace('"', '\\\\"')       # 2 backslashes + "
    arg = arg.replace("`", "\\\\`")       # 2 backslashes + `
    arg = arg.replace("$", "\\\\$")       # 2 backslashes + $
    arg = arg.replace("%", "%%")
    return f'"{arg}"'


def _build_exec_line(cmd_list):
    """Build a spec-compliant Exec= value from a command list."""
    return " ".join(_quote_exec_arg(arg) for arg in cmd_list)


def _systemd_quote(arg):
    """Quote an argument for a systemd unit file.
    systemd uses double-quote quoting with backslash escapes; literal % must be
    written as %% to avoid specifier expansion."""
    arg = str(arg).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    return f'"{arg}"'


def _applescript_quote(s):
    """Escape a string for inclusion inside an AppleScript double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _linux_user_env():
    """Return an environment suitable for `systemctl --user` and `loginctl`.
    XDG_RUNTIME_DIR is required; set a sensible default when missing."""
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    return env


def _run(cmd, **kwargs):
    """subprocess.run that never raises FileNotFoundError.

    Many optional system binaries (systemctl, loginctl, crontab, pgrep, am)
    are absent on minimal or non-systemd distros (Alpine, Void, Gentoo/OpenRC,
    Devuan, bare containers, WSL).  Calling them with a plain subprocess.run
    aborts the whole install/uninstall with an unhandled traceback.  This
    wrapper returns a synthetic failed CompletedProcess instead, so callers
    can fall back gracefully on the (non-zero) return code."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    try:
        return subprocess.run(cmd, **kwargs)
    except FileNotFoundError:
        exe = cmd[0] if cmd else "command"
        return subprocess.CompletedProcess(cmd, 127, "", f"{exe}: not found")
    except OSError as e:
        return subprocess.CompletedProcess(cmd, 126, "", str(e))


def _has_binary(name):
    return shutil.which(name) is not None


def _has_systemd():
    """True only when a running systemd instance is actually available.

    `shutil.which('systemctl')` alone is not enough: the binary can exist on a
    host booted with another init (OpenRC, runit, SysV, WSL without systemd),
    where every `systemctl` call fails.  /run/systemd/system exists only when
    systemd is PID 1 and running."""
    return _has_binary("systemctl") and os.path.isdir("/run/systemd/system")


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


# ------------------------------------------------------------------
# Windows helpers
# ------------------------------------------------------------------
def _windows_build():
    if platform.system().lower() != "windows":
        return 0
    try:
        return int(platform.version().split(".")[-1])
    except Exception:
        return 0


def _windows_extension(target_script, hidden):
    name = os.path.basename(str(target_script).replace("\\", "/")).lower()
    if hidden or name.endswith(".pyw"):
        return ".pyw"
    return ".py"


def _python_executable(ext):
    py = sys.executable
    if ext == ".pyw":
        if py.lower().endswith("python.exe"):
            return py[:-4] + "w.exe"
        return py
    return py


# ------------------------------------------------------------------
# Linux — XDG Autostart (desktop) and systemd user service (headless/server)
# ------------------------------------------------------------------
def linux_desktop_path(name):
    return os.path.join(LINUX_AUTOSTART_DIR, f"{name}.desktop")


def linux_systemd_unit_path(name):
    return os.path.join(LINUX_SYSTEMD_USER_DIR, f"{name}.service")


def linux_launcher_path(name):
    return os.path.join(BASE_DIR, f"run-{name}.sh")


def linux_write_launcher(copy_path, copy_dir, name):
    """Write a tiny POSIX launcher script and return its path.

    Every Linux autostart mechanism (XDG .desktop Exec, the systemd unit's
    ExecStart, a Hyprland exec-once, a cron @reboot line) points at THIS
    script instead of embedding `cd ... && python ...` inline.  That removes
    the single biggest source of breakage: the freedesktop Exec field and
    KDE's KConfig parser disagree on how `\\"` inside a nested
    `sh -c "cd \\"x\\" && python \\"y\\""` should be unescaped, so GNOME,
    Cinnamon and KDE could each silently refuse to launch the entry.  A plain
    path to an executable script has no quoting ambiguity on any launcher."""
    python_exe = sys.executable or "/usr/bin/python3"
    path = linux_launcher_path(name)
    content = (
        "#!/bin/sh\n"
        f"cd {shlex.quote(copy_dir)} || exit 1\n"
        f"exec {shlex.quote(python_exe)} {shlex.quote(copy_path)} \"$@\"\n"
    )
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)
    return path


def linux_remove_launcher(name):
    path = linux_launcher_path(name)
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"[+] Removed launcher script: {path}")
        except Exception as e:
            print(f"[-] Could not remove launcher {path}: {e}")


def linux_create_autostart(copy_path, copy_dir, name, hidden):
    """XDG Autostart .desktop entry, for traditional desktops (GNOME, Cinnamon,
    MATE, XFCE, KDE, Budgie) that honor ~/.config/autostart.  NOT used on
    Hyprland/Wayland compositors that ignore XDG autostart — those go through
    systemd (see install())."""
    launcher = linux_write_launcher(copy_path, copy_dir, name)

    if hidden:
        exec_line = _build_exec_line([launcher])
        terminal = "false"
    else:
        cmd = _find_linux_terminal(launcher)
        if cmd:
            exec_line = _build_exec_line(cmd)
            terminal = "false"
        else:
            exec_line = _build_exec_line([launcher])
            terminal = "false"
            print("[!] No terminal emulator found for autostart entry; "
                  "the program will run without a visible window.")

    content = f"""[Desktop Entry]
Type=Application
Name={name}
Exec={exec_line}
Path={copy_dir}
Terminal={terminal}
X-GNOME-Autostart-enabled=true
Hidden=false
"""
    path = linux_desktop_path(name)
    with open(path, "w") as f:
        f.write(content)
    os.chmod(path, 0o755)
    print(f"[+] Linux autostart entry: {path}  (Terminal={terminal})")


def linux_remove_autostart(name):
    path = linux_desktop_path(name)
    if os.path.exists(path):
        os.remove(path)
        print(f"[+] Removed Linux autostart entry: {path}")


def _find_linux_terminal(launcher):
    """Return a terminal-emulator command that runs the launcher script, or
    None.  The flag that precedes the command differs per terminal."""
    # Native terminals come BEFORE the Debian `x-terminal-emulator` alternative:
    # on Ubuntu and Linux Mint that alternative is gnome-terminal.wrapper,
    # which re-joins everything after `-e` into one string and re-splits it,
    # mangling any quoted `sh -c "..."` argument (the reason visible mode
    # failed on Mint/Ubuntu before).  A single launcher path survives it, but
    # the native terminal's own `--` syntax is cleaner still.
    candidates = [
        ["xdg-terminal-exec", launcher],          # Omarchy, freedesktop default
        ["ptyxis", "--", launcher],               # Ubuntu 25.10+, Fedora 41+
        ["kgx", "--", launcher],                  # GNOME Console
        ["gnome-terminal", "--", launcher],       # Ubuntu <=25.04, Mint Cinnamon
        ["konsole", "-e", launcher],              # KDE
        ["xfce4-terminal", "-x", launcher],       # Mint Xfce, Xubuntu
        ["mate-terminal", "-x", launcher],        # Mint MATE
        ["cosmic-term", "-e", launcher],          # Pop!_OS COSMIC
        ["alacritty", "-e", launcher],            # Omarchy <=3.x default
        ["kitty", launcher],
        ["ghostty", "-e", launcher],
        ["foot", launcher],                       # Omarchy 4 default
        ["wezterm", "start", "--", launcher],
        ["x-terminal-emulator", "-e", launcher],  # Debian alternative, last
        ["xterm", "-e", launcher],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    return None


def _is_hyprland():
    """True when the current graphical session is Hyprland (incl. Omarchy).

    Hyprland does not implement the XDG Autostart spec, so ~/.config/autostart
    entries never fire; such sessions must use systemd (Omarchy runs uwsm,
    which activates the user manager) or an exec-once in the Hyprland config."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    cur = (os.environ.get("XDG_CURRENT_DESKTOP", "")
           + " " + os.environ.get("XDG_SESSION_DESKTOP", "")
           + " " + os.environ.get("DESKTOP_SESSION", "")).lower()
    return "hyprland" in cur or "omarchy" in cur


def _is_wlroots_wayland():
    """Other Wayland compositors (sway, river, wayfire, niri, ...) that, like
    Hyprland, do not run XDG autostart.  GNOME and KDE Wayland DO run it, so
    they are intentionally excluded here."""
    if os.environ.get("WAYLAND_DISPLAY") is None:
        return False
    cur = (os.environ.get("XDG_CURRENT_DESKTOP", "")
           + " " + os.environ.get("XDG_SESSION_DESKTOP", "")
           + " " + os.environ.get("DESKTOP_SESSION", "")).lower()
    if any(de in cur for de in ("gnome", "kde", "plasma")):
        return False
    return any(wm in cur for wm in
               ("sway", "river", "wayfire", "niri", "hyprland", "labwc", "wlroots"))


# ------------------------------------------------------------------
# Linux — Hyprland / Omarchy autostart
#
# Hyprland ignores ~/.config/autostart, so an XDG entry never fires there.
# The supported mechanism is the compositor's own config:
#   * Omarchy 4.x (Hyprland >=0.55, Lua):  ~/.config/hypr/autostart.lua
#         o.launch_on_start("cmd")          (Omarchy manual, "Dotfiles")
#   * plain Hyprland >=0.55 (Lua):          ~/.config/hypr/hyprland.lua
#         hl.on("hyprland.start", function() hl.exec_cmd("cmd") end)
#   * Omarchy <=3.x (hyprlang):             ~/.config/hypr/autostart.conf
#         exec-once = cmd
#   * plain Hyprland <=0.54 (hyprlang):     ~/.config/hypr/hyprland.conf
#         exec-once = cmd
# Our lines are wrapped in BEGIN/END markers so reinstall replaces them and
# --stop removes exactly what we added, leaving the user's config intact.
# ------------------------------------------------------------------
HYPR_DIR = os.path.expanduser("~/.config/hypr")


def _hypr_marker(name, comment):
    return (f"{comment} VisibleBackground {name} BEGIN",
            f"{comment} VisibleBackground {name} END")


def _lua_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _hypr_target():
    """Pick the Hyprland config file and syntax to use.
    Returns (path, kind) with kind in {"omarchy-lua", "lua", "conf"}, or
    (None, None) when no Hyprland config exists."""
    lua_main = os.path.join(HYPR_DIR, "hyprland.lua")
    lua_auto = os.path.join(HYPR_DIR, "autostart.lua")
    conf_main = os.path.join(HYPR_DIR, "hyprland.conf")
    conf_auto = os.path.join(HYPR_DIR, "autostart.conf")

    def _mentions(path, needle):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                return needle in f.read()
        except OSError:
            return False

    # Lua config takes precedence: since Hyprland 0.55 a hyprland.lua is
    # loaded instead of hyprland.conf, and Omarchy 4 leaves old .conf files
    # in place but no longer sources them.
    if os.path.isfile(lua_main):
        if os.path.isfile(lua_auto) and (
            _mentions(lua_main, "autostart") or _mentions(lua_auto, "o.launch")
            or os.path.isdir("/usr/share/omarchy")
            or os.path.isdir(os.path.expanduser("~/.local/share/omarchy"))
        ):
            return lua_auto, "omarchy-lua"
        return lua_main, "lua"
    if os.path.isfile(conf_main):
        if os.path.isfile(conf_auto) and _mentions(conf_main, "autostart.conf"):
            return conf_auto, "conf"
        return conf_main, "conf"
    return None, None


def _strip_block(text, begin, end):
    out, skip = [], False
    for ln in text.splitlines():
        if ln.strip() == begin:
            skip = True
            continue
        if ln.strip() == end:
            skip = False
            continue
        if not skip:
            out.append(ln)
    return "\n".join(out)


def hyprland_create_autostart(copy_path, copy_dir, name, hidden):
    """Register the launcher in the Hyprland config.  Returns True on success."""
    path, kind = _hypr_target()
    if not path:
        # Hyprland running with no user config yet: create the modern Lua one?
        # No - Hyprland would then stop generating its default config.  Use
        # the legacy-compatible conf only if the dir exists, else give up.
        print("[!] Hyprland detected but no ~/.config/hypr/hyprland.(lua|conf) found.")
        return False

    launcher = linux_write_launcher(copy_path, copy_dir, name)
    if hidden:
        argv = [launcher]
    else:
        argv = _find_linux_terminal(launcher) or [launcher]
    cmd = " ".join(shlex.quote(a) for a in argv)

    comment = "--" if kind in ("omarchy-lua", "lua") else "#"
    begin, end = _hypr_marker(name, comment)
    if kind == "omarchy-lua":
        body = f"o.launch_on_start({_lua_quote(cmd)})"
    elif kind == "lua":
        body = (f'hl.on("hyprland.start", function() '
                f'hl.exec_cmd({_lua_quote(cmd)}) end)')
    else:
        body = f"exec-once = {cmd}"

    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        text = ""
    text = _strip_block(text, begin, end).rstrip("\n")
    text += f"\n\n{begin}\n{body}\n{end}\n"

    tmp = path + ".vbtmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    print(f"[+] Hyprland autostart added to {path} ({kind}).")
    return True


def hyprland_remove_autostart(name):
    for fname, comment in (("autostart.lua", "--"), ("hyprland.lua", "--"),
                           ("autostart.conf", "#"), ("hyprland.conf", "#")):
        path = os.path.join(HYPR_DIR, fname)
        if not os.path.isfile(path):
            continue
        begin, end = _hypr_marker(name, comment)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        if begin not in text:
            continue
        new = _strip_block(text, begin, end).rstrip("\n") + "\n"
        tmp = path + ".vbtmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(new)
        os.replace(tmp, path)
        print(f"[+] Removed Hyprland autostart entry from {path}")


def linux_launch_now(copy_path, copy_dir, name, hidden):
    python_exe = sys.executable or "/usr/bin/python3"

    if _is_linux_headless():
        if _has_systemd():
            env = _linux_user_env()
            res = _run(
                ["systemctl", "--user", "start", f"{name}.service"],
                env=env,
            )
            if res.returncode == 0:
                print("[+] Started now via systemd user service (headless/background).")
                return
            print(f"[!] systemctl --user start failed: "
                  f"{(res.stderr or '').strip() or (res.stdout or '').strip()}")
        subprocess.Popen(
            [python_exe, copy_path],
            cwd=copy_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[+] Started now detached (headless fallback).")
        return

    if hidden:
        subprocess.Popen(
            [python_exe, copy_path],
            cwd=copy_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[+] Started now (hidden/background).")
    else:
        launcher = linux_launcher_path(name)
        if not os.path.exists(launcher):
            launcher = linux_write_launcher(copy_path, copy_dir, name)
        cmd = _find_linux_terminal(launcher)
        if cmd:
            subprocess.Popen(cmd, start_new_session=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
            print(f"[+] Started now in a visible terminal ({cmd[0]}).")
        else:
            subprocess.Popen(
                [python_exe, copy_path],
                cwd=copy_dir,
                start_new_session=True,
            )
            print("[!] No terminal emulator found — launched detached.")


def linux_find_pids(copy_path):
    pattern = f"python.*{re.escape(copy_path)}"
    try:
        res = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )
        if res.returncode == 0:
            return [int(x) for x in res.stdout.split()]
    except FileNotFoundError:
        pass

    pids = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                raw = f.read().replace(b"\x00", b" ").decode(errors="ignore")
            if copy_path in raw and "python" in raw.lower():
                pids.append(int(pid))
        except Exception:
            continue
    return pids


def linux_kill(copy_path, name=None):
    if name and _has_systemd():
        env = _linux_user_env()
        _run(
            ["systemctl", "--user", "stop", f"{name}.service"],
            env=env,
        )
    for pid in linux_find_pids(copy_path):
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[+] Killed PID {pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"[-] Could not kill PID {pid}: {e}")


# ------------------------------------------------------------------
# Linux — systemd user service (headless servers: Ubuntu Server, RHEL Server)
# ------------------------------------------------------------------
def linux_create_systemd_service(copy_path, copy_dir, name, hidden):
    """Install a systemd user unit.  Used on headless servers where XDG
    Autostart never runs because there is no graphical session."""
    _check_ubuntu_2404_systemd255()

    python_exe = sys.executable or "/usr/bin/python3"
    os.makedirs(LINUX_SYSTEMD_USER_DIR, exist_ok=True)

    linux_enable_linger()

    unit_path = linux_systemd_unit_path(name)

    exec_start = f"{_systemd_quote(python_exe)} {_systemd_quote(copy_path)}"
    working_dir = _systemd_quote(copy_dir)

    content = f"""[Unit]
Description=VisibleBackground {name}
After=default.target

[Service]
Type=simple
WorkingDirectory={working_dir}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StandardOutput=null
StandardError=null

[Install]
WantedBy=default.target
"""
    with open(unit_path, "w") as f:
        f.write(content)
    os.chmod(unit_path, 0o644)
    print(f"[+] systemd user unit written: {unit_path}")

    env = _linux_user_env()
    _run(
        ["systemctl", "--user", "daemon-reload"],
        env=env,
    )
    res = _run(
        ["systemctl", "--user", "enable", "--now", f"{name}.service"],
        env=env,
    )
    if res.returncode != 0:
        print(f"[!] systemctl --user enable --now failed: "
              f"{(res.stderr or '').strip() or (res.stdout or '').strip()}")
        _run(
            ["systemctl", "--user", "enable", f"{name}.service"],
            env=env,
        )
        _run(
            ["systemctl", "--user", "start", f"{name}.service"],
            env=env,
        )


def _check_ubuntu_2404_systemd255():
    """Print a warning for Ubuntu 24.04 with systemd 255 where logind's GC
    may kill user@<uid>.service on last logout despite Linger=yes.
    See Launchpad bug #2163239 and systemd issue #43361.
    This is best-effort and never fails the install."""
    try:
        os_release_path = "/etc/os-release"
        if not os.path.exists(os_release_path):
            return
        info = {}
        with open(os_release_path) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    info[k] = v.strip('"')
        if info.get("ID") != "ubuntu":
            return
        if not info.get("VERSION_ID", "").startswith("24.04"):
            return

        res = _run(["systemctl", "--version"])
        if res.returncode != 0 or not res.stdout:
            return
        m = re.search(r"systemd\s+(\d+)", res.stdout)
        if not m or m.group(1) != "255":
            return

        print()
        print("[!] Ubuntu 24.04 with systemd 255 detected.")
        print("    A known logind regression (Launchpad bug #2163239,")
        print("    systemd issue #43361) may kill the user service manager")
        print("    (user@<uid>.service) on the last logout even when Linger=yes.")
        print("    This can prevent the service from surviving logout or reboot.")
        print("    Verify with:")
        print("      loginctl show-user \"$USER\" -p Linger")
        print("    If the service disappears after logout, apply the documented")
        print("    workaround in /etc/systemd/logind.conf (requires root):")
        print("      UserStopDelaySec=infinity")
        print("      KillUserProcesses=no")
        print("    Then restart logind:")
        print("      sudo systemctl restart systemd-logind")
        print("    Do not edit /etc/systemd/logind.conf automatically.")
        print()
    except Exception:
        pass


def linux_enable_linger():
    """Enable linger so the user service starts at boot without a login.
    Self-linger is permitted by default on systemd; fall back to a
    non-interactive sudo call, then print an actionable warning."""
    env = _linux_user_env()
    user = os.environ.get("USER") or os.environ.get("LOGNAME") or str(os.getuid())

    res = _run(
        ["loginctl", "enable-linger"],
        env=env,
    )
    if res.returncode == 0:
        print("[+] loginctl enable-linger succeeded (self).")
        return

    res = _run(
        ["sudo", "-n", "loginctl", "enable-linger", user],
        env=env,
    )
    if res.returncode == 0:
        print(f"[+] loginctl enable-linger {user} succeeded via sudo -n.")
        return

    print("[!] Could not enable linger automatically.")
    print("    Without linger, the systemd user service starts on first login,")
    print("    not at boot.  Run this once with an administrator account:")
    print(f"      sudo loginctl enable-linger {user}")


def linux_remove_systemd_service(name):
    unit_path = linux_systemd_unit_path(name)
    if _has_systemd():
        env = _linux_user_env()
        _run(
            ["systemctl", "--user", "stop", f"{name}.service"],
            env=env,
        )
        _run(
            ["systemctl", "--user", "disable", f"{name}.service"],
            env=env,
        )
    if os.path.exists(unit_path):
        os.remove(unit_path)
        print(f"[+] Removed systemd user unit: {unit_path}")
    if _has_systemd():
        _run(
            ["systemctl", "--user", "daemon-reload"],
            env=_linux_user_env(),
        )


# ------------------------------------------------------------------
# Linux — cron @reboot fallback (non-systemd servers: Alpine/OpenRC, Void/runit,
# Gentoo/OpenRC, Devuan/SysV, bare containers).  Used when the host is headless
# AND has no running systemd, so there is neither an XDG session nor a user
# service manager to start the program at boot.
# ------------------------------------------------------------------
def _cron_marker(name):
    return f"# VisibleBackground {name}"


def linux_create_cron_autostart(copy_path, copy_dir, name):
    """Add an `@reboot` crontab line so the program starts at every boot.

    Returns True on success.  Requires a crontab binary and a running cron
    daemon; when crontab is missing, prints manual instructions and returns
    False so the caller can still launch the program for this session."""
    if not _has_binary("crontab"):
        print("[!] No systemd and no crontab found on this host.")
        print("    Cannot register a boot entry automatically.  To start the")
        print("    program at boot, add an init/rc service for your system that")
        print("    runs:")
        print(f"      cd {shlex.quote(copy_dir)} && "
              f"{shlex.quote(sys.executable or 'python3')} {shlex.quote(copy_path)}")
        return False

    python_exe = sys.executable or "/usr/bin/python3"
    marker = _cron_marker(name)
    line = (
        f"@reboot cd {shlex.quote(copy_dir)} && "
        f"{shlex.quote(python_exe)} {shlex.quote(copy_path)} "
        f"> /dev/null 2>&1  {marker}"
    )

    existing = _run(["crontab", "-l"])
    lines = []
    if existing.returncode == 0 and existing.stdout:
        # Drop any prior entry for this same name so re-install is idempotent.
        lines = [ln for ln in existing.stdout.splitlines()
                 if marker not in ln]
    lines.append(line)
    new_crontab = "\n".join(lines) + "\n"

    res = _run(["crontab", "-"], input=new_crontab)
    if res.returncode == 0:
        print(f"[+] cron @reboot entry installed for '{name}'.")
        if not os.path.isdir("/run/systemd/system"):
            print("[!] Make sure the cron daemon is enabled and started at boot")
            print("    (e.g. `rc-update add cron` + `rc-service cron start` on")
            print("    OpenRC, or `sv enable cron` on runit).")
        return True

    print(f"[!] Could not write crontab: "
          f"{(res.stderr or '').strip() or (res.stdout or '').strip()}")
    return False


def linux_remove_cron_autostart(name):
    if not _has_binary("crontab"):
        return
    marker = _cron_marker(name)
    existing = _run(["crontab", "-l"])
    if existing.returncode != 0 or not existing.stdout:
        return
    kept = [ln for ln in existing.stdout.splitlines() if marker not in ln]
    if len(kept) == len(existing.stdout.splitlines()):
        return  # nothing of ours present
    new_crontab = ("\n".join(kept) + "\n") if kept else ""
    res = _run(["crontab", "-"], input=new_crontab)
    if res.returncode == 0:
        print(f"[+] Removed cron @reboot entry for '{name}'.")


# ------------------------------------------------------------------
# macOS — LaunchAgent
# ------------------------------------------------------------------
def macos_plist_path(name):
    return os.path.join(MACOS_LAUNCHAGENTS_DIR, f"com.visiblebackground.{name}.plist")


def _macos_python_path():
    return sys.executable or "/usr/bin/python3"


def macos_create_autostart(copy_path, copy_dir, name, hidden):
    python_exe = _macos_python_path()
    label = f"com.visiblebackground.{name}"

    if hidden:
        program_args = [python_exe, copy_path]
    else:
        # Terminal windows opened by `do script` start in the user's home
        # directory, NOT the plist's WorkingDirectory.  The cd is required
        # so the Python process runs with the intended working directory.
        shell_command = (
            f"cd {shlex.quote(copy_dir)} && "
            f"{shlex.quote(python_exe)} {shlex.quote(copy_path)}"
        )
        script = (
            f'tell application "Terminal" to do script '
            f'"{_applescript_quote(shell_command)}"'
        )
        program_args = ["/usr/bin/osascript", "-e", script]

    os.makedirs(BASE_DIR, exist_ok=True)

    plist = {
        "Label": label,
        "ProgramArguments": program_args,
        "WorkingDirectory": copy_dir,
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": os.path.join(BASE_DIR, f"{name}.out.log"),
        "StandardErrorPath": os.path.join(BASE_DIR, f"{name}.err.log"),
    }

    plist_path = macos_plist_path(name)
    with open(plist_path, "wb") as f:
        plistlib.dump(plist, f)
    os.chmod(plist_path, 0o644)
    print(f"[+] macOS LaunchAgent written: {plist_path}")

    uid = os.getuid()

    # Bootout any existing instance first.  On macOS 26 Tahoe, `bootstrap`
    # returns EIO/exit 5 if the label is already loaded or if a stale job
    # exists, so bootout is mandatory before re-bootstrapping.
    subprocess.run(
        ["launchctl", "bootout", f"gui/{uid}/{label}"],
        capture_output=True, text=True,
    )

    loaded = False
    res = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{uid}", plist_path],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        loaded = True
    else:
        print(f"[!] launchctl bootstrap failed: "
              f"{res.stderr.strip() or res.stdout.strip()}; "
              f"falling back to launchctl load -w")
        res = subprocess.run(
            ["launchctl", "load", "-w", plist_path],
            capture_output=True, text=True,
        )
        load_failed = (
            res.returncode != 0
            or "failed" in res.stderr.lower()
            or "input/output error" in res.stderr.lower()
        )
        if not load_failed:
            loaded = True
        else:
            print(f"[!] launchctl load -w failed: "
                  f"{res.stderr.strip() or res.stdout.strip()}")

    if not loaded:
        print("[-] Could not load LaunchAgent.  You may need to log out and back in,")
        print("    or load it manually with:")
        print(f"    launchctl bootstrap gui/{uid} {plist_path}")


def macos_remove_autostart(name):
    plist_path = macos_plist_path(name)
    uid = os.getuid()
    label = f"com.visiblebackground.{name}"

    for cmd in (
        ["launchctl", "bootout", f"gui/{uid}/{label}"],
        ["launchctl", "unload", "-w", plist_path],
    ):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            break

    if os.path.exists(plist_path):
        os.remove(plist_path)
        print(f"[+] Removed macOS LaunchAgent: {plist_path}")


def macos_launch_now(copy_path, copy_dir, hidden):
    python_exe = _macos_python_path()
    if hidden:
        subprocess.Popen(
            [python_exe, copy_path],
            cwd=copy_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[+] Started now (hidden/background).")
    else:
        # Terminal windows opened by `do script` start in the user's home
        # directory, so cd to the intended working directory explicitly.
        shell_command = (
            f"cd {shlex.quote(copy_dir)} && "
            f"{shlex.quote(python_exe)} {shlex.quote(copy_path)}"
        )
        script = (
            f'tell application "Terminal" to do script '
            f'"{_applescript_quote(shell_command)}"'
        )
        subprocess.Popen(["osascript", "-e", script])
        print("[+] Started now in Terminal (visible).")


def macos_find_pids(copy_path):
    pattern = f"python.*{re.escape(copy_path)}"
    try:
        res = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )
        if res.returncode == 0:
            return [int(x) for x in res.stdout.split()]
    except FileNotFoundError:
        pass
    return []


def macos_kill(copy_path):
    for pid in macos_find_pids(copy_path):
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[+] Killed PID {pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"[-] Could not kill PID {pid}: {e}")


# ------------------------------------------------------------------
# Android — Termux:Boot
# ------------------------------------------------------------------
def _android15_warning():
    print()
    print("[!] Android 15 known issue:")
    print("    Android 15 may still kill Termux background processes even with")
    print("    termux-wake-lock active and battery optimisation disabled.  This is")
    print("    an upstream Android limitation, tracked in Termux issue #5150.")
    print("    If your device exposes it, enable:")
    print("      Settings → System → Developer options →")
    print("      Disable child process restrictions")
    print("    Do not expect the same background reliability as on Android 14 or older.")
    print()


def android_create_autostart(copy_path, copy_dir, name, hidden):
    if not _is_termux():
        print("[-] Android support requires Termux.")
        print("    Install Termux from F-Droid, then install Termux:Boot,")
        print("    and run this script inside Termux.")
        sys.exit(1)

    _android15_warning()

    os.makedirs(TERMUX_BOOT_DIR, exist_ok=True)
    boot_script = os.path.join(TERMUX_BOOT_DIR, f"start-{name}.sh")
    python_exe = sys.executable or "python"

    if hidden:
        inner = f'{shlex.quote(python_exe)} {shlex.quote(copy_path)}'
        script_content = (
            "#!/data/data/com.termux/files/usr/bin/sh\n"
            "termux-wake-lock\n"
            f"cd {shlex.quote(copy_dir)}\n"
            f"{inner} > /dev/null 2>&1 &\n"
        )
    else:
        # Visible/foreground run via the documented Termux RUN_COMMAND API.
        # The command is delivered to RunCommandService (an exported service),
        # NOT to TermuxActivity with a made-up android.intent.action.RUN, which
        # Termux never handled.  BACKGROUND=false opens a foreground terminal
        # session.  Requires `allow-external-apps=true` in termux.properties.
        script_content = (
            "#!/data/data/com.termux/files/usr/bin/sh\n"
            "termux-wake-lock\n"
            "am startservice --user 0 \\\n"
            "  -n com.termux/com.termux.app.RunCommandService \\\n"
            "  -a com.termux.RUN_COMMAND \\\n"
            f"  --es com.termux.RUN_COMMAND_PATH {shlex.quote(python_exe)} \\\n"
            f"  --esa com.termux.RUN_COMMAND_ARGUMENTS {shlex.quote(copy_path)} \\\n"
            f"  --es com.termux.RUN_COMMAND_WORKDIR {shlex.quote(copy_dir)} \\\n"
            "  --ez com.termux.RUN_COMMAND_BACKGROUND false\n"
        )

    with open(boot_script, "w") as f:
        f.write(script_content)
    os.chmod(boot_script, 0o755)
    print(f"[+] Android Termux boot script written: {boot_script}")
    print("[!] Make sure Termux:Boot is installed and has been opened once.")
    print("[!] Disable battery optimisation for Termux and Termux:Boot.")
    print("[!] Grant Termux the ‘Draw over other apps’ permission on Android 10+")
    if not hidden:
        print("[!] Visible mode uses the Termux RUN_COMMAND API, which needs")
        print("    `allow-external-apps=true` in ~/.termux/termux.properties.")
        print("    If the window does not open at boot, use --hide instead.")


def android_remove_autostart(name):
    boot_script = os.path.join(TERMUX_BOOT_DIR, f"start-{name}.sh")
    if os.path.exists(boot_script):
        os.remove(boot_script)
        print(f"[+] Removed Termux boot script: {boot_script}")


def android_launch_now(copy_path, copy_dir, hidden):
    if not _is_termux():
        print("[-] Cannot launch now: not running inside Termux.")
        return
    _android15_warning()
    python_exe = sys.executable or "python"
    if hidden:
        subprocess.Popen(
            [python_exe, copy_path],
            cwd=copy_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print("[+] Started now (hidden/background).")
    else:
        try:
            subprocess.Popen([
                "am", "startservice", "--user", "0",
                "-n", "com.termux/com.termux.app.RunCommandService",
                "-a", "com.termux.RUN_COMMAND",
                "--es", "com.termux.RUN_COMMAND_PATH", python_exe,
                "--esa", "com.termux.RUN_COMMAND_ARGUMENTS", copy_path,
                "--es", "com.termux.RUN_COMMAND_WORKDIR", copy_dir,
                "--ez", "com.termux.RUN_COMMAND_BACKGROUND", "false",
            ])
            print("[+] Started now in a new visible Termux session.")
        except FileNotFoundError:
            # `am` missing: fall back to a plain background launch so the
            # program still runs this session.
            subprocess.Popen(
                [python_exe, copy_path],
                cwd=copy_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print("[!] 'am' not found; started in background instead.")


def android_find_pids(copy_path):
    pattern = f"python.*{re.escape(copy_path)}"
    try:
        res = subprocess.run(
            ["pgrep", "-f", pattern], capture_output=True, text=True
        )
        if res.returncode == 0:
            return [int(x) for x in res.stdout.split()]
    except FileNotFoundError:
        pass
    return []


def android_kill(copy_path):
    for pid in android_find_pids(copy_path):
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[+] Killed PID {pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"[-] Could not kill PID {pid}: {e}")


# ------------------------------------------------------------------
# iOS — explicitly unsupported
# ------------------------------------------------------------------
def ios_unsupported():
    print("[-] iOS does not allow arbitrary background scripts to run persistently.")
    print()
    print("    Apple’s own documentation establishes the following platform contract:")
    print()
    print("    • iOS suspends third‑party apps shortly after they move to the background.")
    print("      Suspension prevents the process from executing any code.")
    print("    • There is no general‑purpose mechanism for running code continuously,")
    print("      at a specific time, at a guaranteed interval, or in response to a")
    print("      network/IPC request in the background.")
    print("    • BGAppRefreshTask is opportunistic and capped at roughly 30 seconds.")
    print("      BGProcessingTask is also opportunistic and typically runs only when")
    print("      the device is idle and plugged in, for about 60 seconds (occasionally")
    print("      a few minutes). Neither is a substitute for a persistent autostart")
    print("      daemon.")
    print("    • Scheduling is decided by dasd (Duet Activity Scheduler Daemon), not")
    print("      by the app. Battery level below ~20%, Low Power Mode, thermal pressure,")
    print("      and low user engagement can all cause a submitted task to be dropped")
    print("      entirely.")
    print("    • Once the user force‑quits an app, iOS will not restart it in the")
    print("      background. No third‑party library can bypass this.")
    print("    • Jailbroken or MDM‑supervised devices do not change this contract for")
    print("      ordinary user scripts.")
    print()
    print("    The only Apple‑sanctioned best‑effort alternative is a user‑configured")
    print("    Shortcuts automation triggered by “Device Unlocked” or “Wi‑Fi connected”")
    print("    after boot.  This script cannot install that automation for you.")
    sys.exit(1)


# ------------------------------------------------------------------
# Windows — Task Scheduler (VBS launcher: no blank CMD window)
# ------------------------------------------------------------------
def windows_task_name(name):
    return f"VisibleBackground_{name}"


def windows_vbs_path(name):
    return os.path.normpath(os.path.join(BASE_DIR, f"VisibleBackground_{name}.vbs"))


def _write_windows_vbs_launcher(name, copy_path, copy_dir, ext):
    if ext == ".pyw":
        python_exe = _python_executable(".pyw")
        style = "0"
    else:
        python_exe = _python_executable(".py")
        style = "1"

    copy_path = os.path.normpath(copy_path)
    copy_dir = os.path.normpath(copy_dir)

    content = (
        f'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.CurrentDirectory = "{copy_dir}"\n'
        f'WshShell.Run """{python_exe}"" ""{copy_path}""", {style}, False\n'
    )

    vbs_path = windows_vbs_path(name)
    with open(vbs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return vbs_path


def _write_windows_cmd_wrapper(name, inner_action):
    """Write a .cmd wrapper so schtasks /TR never has to parse &&, >, or
    nested quotes.  This is the recommended way to embed compound commands
    in a scheduled task (schtasks has known quoting problems with /TR)."""
    wrapper_path = os.path.normpath(
        os.path.join(BASE_DIR, f"VisibleBackground_{name}_launcher.cmd")
    )
    content = "@echo off\r\n" + inner_action + "\r\n"
    with open(wrapper_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(content)
    return wrapper_path


def windows_create_autostart(copy_path, copy_dir, name, hidden, ext):
    if not is_admin():
        print("[-] ERROR: Administrator privileges required.")
        print("    Please run this script from an elevated Command Prompt.")
        sys.exit(1)

    task_name = windows_task_name(name)
    build = _windows_build()
    vbs_path = _write_windows_vbs_launcher(name, copy_path, copy_dir, ext)

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    wscript_exe = os.path.normpath(
        os.path.join(system_root, "System32", "wscript.exe")
    )

    if build >= 26100:
        # Windows 11 24H2 (26100) and 25H2 (26200) introduce delayed desktop
        # initialization.  A short delay in the task action avoids racing the
        # shell.  Keep this in the CMD wrapper, NOT inside the VBS launcher.
        #
        # Do NOT use `timeout` here: timeout reads stdin and aborts with
        # "ERROR: Input redirection is not supported" when run by Task
        # Scheduler, which gives the process no console input handle.  `ping`
        # with a loopback count is the portable, console-less way to sleep
        # ~5 s (one immediate reply + 5 one-second gaps).
        inner_action = (
            f'ping -n 6 127.0.0.1 >nul & '
            f'"{wscript_exe}" //B //Nologo "{vbs_path}"'
        )
    else:
        inner_action = f'"{wscript_exe}" //B //Nologo "{vbs_path}"'

    wrapper_path = _write_windows_cmd_wrapper(name, inner_action)
    action = f'"{wrapper_path}"'

    args = [
        "schtasks", "/Create", "/F",
        "/TN", task_name,
        "/TR", action,
        "/SC", "ONLOGON",
        "/IT",
        "/RL", "LIMITED",
    ]
    res = subprocess.run(args, capture_output=True, text=True)
    if res.returncode != 0:
        try:
            os.remove(vbs_path)
        except Exception:
            pass
        try:
            os.remove(wrapper_path)
        except Exception:
            pass
        print(f"[-] schtasks failed: {res.stderr.strip() or res.stdout.strip()}")
        return False
    print(f"[+] Windows Task Scheduler entry created: {task_name}")
    print(f"[+] VBS launcher written: {vbs_path}")
    print(f"[+] CMD wrapper written: {wrapper_path}")
    return True


def windows_remove_autostart(name):
    if not is_admin():
        print("[-] ERROR: Administrator privileges required to delete the task.")
        print("    Please run this script from an elevated Command Prompt.")
        sys.exit(1)

    task_name = windows_task_name(name)
    res = subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        capture_output=True,
    )
    if res.returncode == 0:
        print(f"[+] Removed Windows task: {task_name}")


def windows_launch_now(copy_path, copy_dir, name, ext):
    if ext == ".pyw":
        python_exe = _python_executable(".pyw")
        flags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
        )
        subprocess.Popen(
            [python_exe, copy_path],
            cwd=copy_dir,
            creationflags=flags,
            close_fds=True,
        )
        print("[+] Started now (hidden/background, .pyw).")
    else:
        python_exe = _python_executable(".py")
        subprocess.Popen(
            f'start "VisibleBackground-{name}" "{python_exe}" "{copy_path}"',
            shell=True,
            cwd=copy_dir,
        )
        print("[+] Started now (visible console, .py).")


def windows_find_pids(copy_path):
    needle = os.path.normpath(copy_path).lower().replace("'", "''")
    ps = (
        f"$needle = '{needle}'; "
        "Get-CimInstance Win32_Process | "
        "Where-Object { "
        "($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') "
        "-and $_.CommandLine -and "
        "$_.CommandLine.ToLower().Contains($needle) "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True,
        )
        return [int(x) for x in res.stdout.split() if x.strip().isdigit()]
    except Exception:
        return []


def windows_kill(copy_path):
    for pid in windows_find_pids(copy_path):
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True)
        print(f"[+] Killed PID {pid}")


def _windows_remove_vbs_launcher(name):
    vbs_path = windows_vbs_path(name)
    if os.path.exists(vbs_path):
        try:
            os.remove(vbs_path)
            print(f"[+] Removed VBS launcher: {vbs_path}")
        except Exception as e:
            print(f"[-] Could not remove VBS launcher: {e}")


def _windows_remove_cmd_wrapper(name):
    wrapper_path = os.path.normpath(
        os.path.join(BASE_DIR, f"VisibleBackground_{name}_launcher.cmd")
    )
    if os.path.exists(wrapper_path):
        try:
            os.remove(wrapper_path)
            print(f"[+] Removed CMD wrapper: {wrapper_path}")
        except Exception as e:
            print(f"[-] Could not remove CMD wrapper: {e}")


# ------------------------------------------------------------------
# Stop helpers
# ------------------------------------------------------------------
def _resolve_copy_paths(target_script, name, state):
    paths = set()
    if name in state and "copy" in state[name]:
        paths.add(os.path.normpath(state[name]["copy"]))
    base = os.path.basename(str(target_script).replace("\\", "/"))
    if base:
        paths.add(os.path.normpath(os.path.join(BASE_DIR, base)))
    for ext in (".py", ".pyw"):
        paths.add(os.path.normpath(os.path.join(BASE_DIR, name + ext)))
    if os.path.isdir(BASE_DIR):
        for fname in os.listdir(BASE_DIR):
            if sanitize_name(fname) == name:
                paths.add(os.path.normpath(os.path.join(BASE_DIR, fname)))
    return paths


def _remove_with_retry(path, attempts=6, delay=0.5):
    for i in range(attempts):
        try:
            os.remove(path)
            print(f"[+] Removed copy: {path}")
            return True
        except FileNotFoundError:
            return True
        except PermissionError:
            if i < attempts - 1:
                time.sleep(delay)
        except Exception as e:
            print(f"[-] Could not remove copy {path}: {e}")
            return False
    print(f"[-] Could not remove copy {path} (still locked)")
    return False


# ------------------------------------------------------------------
# Install / Uninstall dispatcher
# ------------------------------------------------------------------
def install(target_script, hidden):
    if _is_ios():
        ios_unsupported()

    ensure_directory()
    if not os.path.isfile(target_script):
        print(f"[-] File not found: {target_script}")
        sys.exit(1)

    name = sanitize_name(target_script)
    system = platform.system().lower()

    if _is_android():
        if not _is_termux():
            print("[-] Android support requires Termux.  Install Termux from F-Droid")
            print("    and run this script inside Termux.")
            sys.exit(1)
        copy_path = os.path.normpath(
            os.path.join(BASE_DIR, os.path.basename(target_script))
        )
        copy_dir = BASE_DIR
        shutil.copy2(target_script, copy_path)
        print(f"[+] Copied '{target_script}' → '{copy_path}'")
        android_create_autostart(copy_path, copy_dir, name, hidden)
        android_launch_now(copy_path, copy_dir, hidden)
    elif _is_macos():
        copy_path = os.path.normpath(
            os.path.join(BASE_DIR, os.path.basename(target_script))
        )
        copy_dir = BASE_DIR
        shutil.copy2(target_script, copy_path)
        print(f"[+] Copied '{target_script}' → '{copy_path}'")
        macos_create_autostart(copy_path, copy_dir, name, hidden)
        macos_launch_now(copy_path, copy_dir, hidden)
    elif system == "windows":
        ext = _windows_extension(target_script, hidden)
        saved_name = os.path.basename(str(target_script).replace("\\", "/"))
        for e in (".pyw", ".py"):
            if saved_name.lower().endswith(e):
                saved_name = saved_name[: -len(e)]
                break
        saved_name += ext
        copy_path = os.path.normpath(os.path.join(BASE_DIR, saved_name))
        copy_dir = BASE_DIR
        shutil.copy2(target_script, copy_path)
        print(f"[+] Copied '{target_script}' → '{copy_path}'")
        if not windows_create_autostart(copy_path, copy_dir, name, hidden, ext):
            print("[-] Could not create autostart entry.")
            sys.exit(1)
        windows_launch_now(copy_path, copy_dir, name, ext)
    elif system == "linux":
        if hasattr(os, "geteuid") and os.geteuid() == 0 and os.environ.get("SUDO_USER"):
            print("[!] Running under sudo: the autostart entry will be created for")
            print("    root, not for your desktop user.  Run without sudo instead.")
        copy_path = os.path.normpath(
            os.path.join(BASE_DIR, os.path.basename(target_script))
        )
        copy_dir = BASE_DIR
        shutil.copy2(target_script, copy_path)
        print(f"[+] Copied '{target_script}' → '{copy_path}'")

        if _is_linux_headless():
            if _has_systemd():
                if not hidden:
                    print("[!] Headless Linux detected: no DISPLAY/WAYLAND_DISPLAY.")
                    print("    Visible terminal mode is unavailable; installing in")
                    print("    background mode as a systemd user service.")
                linux_create_systemd_service(copy_path, copy_dir, name, hidden=True)
                linux_mechanism = "systemd"
            else:
                if not hidden:
                    print("[!] Headless Linux detected: no DISPLAY/WAYLAND_DISPLAY.")
                print("[!] No running systemd found; using a cron @reboot entry")
                print("    for boot persistence (Alpine/OpenRC, Void/runit, etc.).")
                linux_create_cron_autostart(copy_path, copy_dir, name)
                linux_mechanism = "cron"
            linux_launch_now(copy_path, copy_dir, name, hidden=True)
        elif _is_hyprland() and hyprland_create_autostart(
                copy_path, copy_dir, name, hidden):
            # Hyprland/Omarchy: use ONLY the compositor config.  Omarchy runs
            # uwsm, which also activates xdg-desktop-autostart.target, so an
            # extra ~/.config/autostart entry would start the program twice.
            linux_remove_autostart(name)
            linux_mechanism = "hyprland"
            linux_launch_now(copy_path, copy_dir, name, hidden)
        else:
            if _is_wlroots_wayland():
                print("[!] This Wayland compositor may not run XDG autostart")
                print("    entries.  If the program does not start after login,")
                print(f"    add `{linux_launcher_path(name)}` to your compositor's")
                print("    startup config (e.g. `exec` in sway's config).")
            linux_create_autostart(copy_path, copy_dir, name, hidden)
            linux_mechanism = "xdg"
            linux_launch_now(copy_path, copy_dir, name, hidden)
    else:
        print(f"[-] Unsupported OS: {system}")
        sys.exit(1)

    # Record the platform and the mechanism actually used.  Order matters:
    # Android reports platform.system() == "linux" and is usually headless,
    # so it MUST be classified before the generic Linux (xdg/systemd)
    # branches — otherwise a Termux install is mislabelled as a systemd
    # service.  Also record the *effective* hidden mode: a headless host has
    # no terminal, so it is always installed in background regardless of the
    # --hide flag the user passed.
    if _is_android():
        plat, mechanism, effective_hidden = "android", "termux-boot", hidden
    elif _is_macos():
        plat, mechanism, effective_hidden = "macos", "launchagent", hidden
    elif system == "windows":
        plat, mechanism, effective_hidden = "windows", "task", hidden
    elif system == "linux":
        plat = "linux"
        # linux_mechanism is set in the install branch above ("xdg", "systemd"
        # or "cron") so the recorded mechanism matches what was actually used.
        mechanism = linux_mechanism
        effective_hidden = True if _is_linux_headless() else hidden
    else:
        plat, mechanism, effective_hidden = system, "unknown", hidden

    state = load_state()
    state[name] = {
        "source": os.path.abspath(target_script),
        "copy": copy_path,
        "hidden": effective_hidden,
        "platform": plat,
        "mechanism": mechanism,
    }
    save_state(state)
    print(f"[+] '{name}' installed. It will auto-start on every reboot/login.")


def uninstall(target_script):
    if _is_ios():
        ios_unsupported()

    ensure_directory()
    name = sanitize_name(target_script)
    system = platform.system().lower()
    state = load_state()

    copy_paths = _resolve_copy_paths(target_script, name, state)
    print(f"[*] Resolved {len(copy_paths)} candidate path(s) for '{name}'.")

    if _is_android():
        for cp in copy_paths:
            android_kill(cp)
    elif _is_macos():
        for cp in copy_paths:
            macos_kill(cp)
    elif system == "windows":
        for cp in copy_paths:
            windows_kill(cp)
    else:
        for cp in copy_paths:
            linux_kill(cp, name)

    if _is_android():
        android_remove_autostart(name)
    elif _is_macos():
        macos_remove_autostart(name)
    elif system == "windows":
        windows_remove_autostart(name)
        _windows_remove_vbs_launcher(name)
        _windows_remove_cmd_wrapper(name)
    else:
        # Remove every Linux mechanism unconditionally: the uninstall may run
        # on a different session type than the install (e.g. installed from a
        # desktop login, removed over SSH), so clear XDG, systemd and cron
        # entries regardless of which one the state file records.
        linux_remove_autostart(name)
        linux_remove_systemd_service(name)
        linux_remove_cron_autostart(name)
        hyprland_remove_autostart(name)
        linux_remove_launcher(name)

    for cp in copy_paths:
        if os.path.exists(cp):
            _remove_with_retry(cp)

    if name in state:
        del state[name]
        save_state(state)

    print(f"[+] '{name}' stopped permanently.")


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Install a Python script to run on every reboot/login — "
                    "visible by default, hidden with --hide."
    )
    parser.add_argument("script", help="Python script to schedule")
    parser.add_argument("--hide", action="store_true",
                        help="run silently in the background (no window)")
    parser.add_argument("--stop", action="store_true",
                        help="stop and permanently remove the autostart entry")
    args = parser.parse_args()

    if args.stop:
        uninstall(args.script)
    else:
        install(args.script, hidden=args.hide)


if __name__ == "__main__":
    main()