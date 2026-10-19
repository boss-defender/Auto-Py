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
BASE_DIR = os.path.normpath(os.path.expanduser("~/.caches"))
STATE_FILE = os.path.join(BASE_DIR, "state.json")
LINUX_AUTOSTART_DIR = os.path.expanduser("~/.config/autostart")
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


# ------------------------------------------------------------------
# Helpers (shared)
# ------------------------------------------------------------------
def ensure_directory():
    os.makedirs(BASE_DIR, exist_ok=True)
    if platform.system().lower() == "linux":
        os.makedirs(LINUX_AUTOSTART_DIR, exist_ok=True)
    elif _is_macos():
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
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def sanitize_name(name):
    base = os.path.basename(str(name).replace("\\", "/"))
    for ext in (".pyw", ".py"):
        if base.lower().endswith(ext):
            base = base[: -len(ext)]
            break
    return re.sub(r"[^a-zA-Z0-9\-_]", "-", base).lower() or "program"


def _escape_exec_value(s):
    """Escape for Desktop Entry Exec key (Linux).
    Per the Desktop Entry Specification, within double quotes the characters
    `` ` ``, `` $ ``, `` " `` and `` \\ `` must be escaped.  Literal `` % ``
    must be written as `` %% `` so it is not interpreted as a field code."""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("`", "\\`")
    s = s.replace("$", "\\$")
    s = s.replace("%", "%%")
    return s


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
# Linux — XDG Autostart
# ------------------------------------------------------------------
def linux_desktop_path(name):
    return os.path.join(LINUX_AUTOSTART_DIR, f"{name}.desktop")


def linux_create_autostart(copy_path, copy_dir, name, hidden):
    python_exe = sys.executable
    inner = f'cd "{copy_dir}" && "{python_exe}" "{copy_path}"'

    if hidden:
        escaped_inner = _escape_exec_value(inner)
        exec_line = f'sh -c "{escaped_inner}"'
        terminal = "false"
    else:
        cmd = _find_linux_terminal(python_exe, copy_path, copy_dir)
        if cmd:
            exec_line = _escape_exec_value(shlex.join(cmd))
            terminal = "false"
        else:
            escaped_inner = _escape_exec_value(inner)
            exec_line = f'sh -c "{escaped_inner}"'
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


def _find_linux_terminal(python_exe, copy_path, copy_dir):
    inner = f'cd "{copy_dir}" && "{python_exe}" "{copy_path}"'
    candidates = [
        ["xdg-terminal-exec", "sh", "-c", inner],
        ["x-terminal-emulator", "-e", "sh", "-c", inner],
        ["ptyxis", "--", "sh", "-c", inner],
        ["kgx", "--", "sh", "-c", inner],
        ["gnome-terminal", "--", "sh", "-c", inner],
        ["konsole", "-e", "sh", "-c", inner],
        ["xfce4-terminal", "-e", f'sh -c "{inner}"'],
        ["mate-terminal", "-e", f'sh -c "{inner}"'],
        ["cosmic-term", "-e", "sh", "-c", inner],
        ["ghostty", "-e", "sh", "-c", inner],
        ["foot", "-e", "sh", "-c", inner],
        ["xterm", "-e", "sh", "-c", inner],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    return None


def linux_launch_now(copy_path, copy_dir, hidden):
    python_exe = sys.executable
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
        cmd = _find_linux_terminal(python_exe, copy_path, copy_dir)
        if cmd:
            subprocess.Popen(cmd, start_new_session=True)
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


def linux_kill(copy_path):
    for pid in linux_find_pids(copy_path):
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[+] Killed PID {pid}")
        except ProcessLookupError:
            pass
        except Exception as e:
            print(f"[-] Could not kill PID {pid}: {e}")


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
        script = (
            f'tell application "Terminal" to do script '
            f'"{python_exe} {shlex.quote(copy_path)}"'
        )
        program_args = ["/usr/bin/osascript", "-e", script]

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
    loaded = False
    # macOS 26 Tahoe can return EIO (5) on bootstrap even when the label is
    # not loaded; legacy `load -w` still works and registers the job in gui/<uid>.
    for cmd in (
        ["launchctl", "bootstrap", f"gui/{uid}", plist_path],
        ["launchctl", "load", "-w", plist_path],
    ):
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            loaded = True
            break
        print(f"[!] {' '.join(cmd)} failed: {res.stderr.strip() or res.stdout.strip()}")

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
        script = (
            f'tell application "Terminal" to do script '
            f'"{python_exe} {shlex.quote(copy_path)}"'
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
def android_create_autostart(copy_path, copy_dir, name, hidden):
    if not _is_termux():
        print("[-] Android support requires Termux.")
        print("    Install Termux from F-Droid, then install Termux:Boot,")
        print("    and run this script inside Termux.")
        sys.exit(1)

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
        # Visible mode: start a new Termux session via TermuxActivity.
        # The RUN_COMMAND_PATH / RUN_COMMAND_ARGUMENTS extras are accepted
        # by TermuxActivity (see Termux discussion #4463).
        script_content = (
            "#!/data/data/com.termux/files/usr/bin/sh\n"
            "termux-wake-lock\n"
            "am start --user 0 \\\n"
            "  -n com.termux/.app.TermuxActivity \\\n"
            "  -a android.intent.action.RUN \\\n"
            f"  --es com.termux.RUN_COMMAND_PATH {shlex.quote(python_exe)} \\\n"
            f"  --esa com.termux.RUN_COMMAND_ARGUMENTS {shlex.quote(copy_path)}\n"
        )

    with open(boot_script, "w") as f:
        f.write(script_content)
    os.chmod(boot_script, 0o755)
    print(f"[+] Android Termux boot script written: {boot_script}")
    print("[!] Make sure Termux:Boot is installed and has been opened once.")
    print("[!] Disable battery optimisation for Termux and Termux:Boot.")


def android_remove_autostart(name):
    boot_script = os.path.join(TERMUX_BOOT_DIR, f"start-{name}.sh")
    if os.path.exists(boot_script):
        os.remove(boot_script)
        print(f"[+] Removed Termux boot script: {boot_script}")


def android_launch_now(copy_path, copy_dir, hidden):
    if not _is_termux():
        print("[-] Cannot launch now: not running inside Termux.")
        return
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
        # Use TermuxActivity with RUN intent for a visible session.
        subprocess.Popen(
            [
                "am", "start", "--user", "0",
                "-n", "com.termux/.app.TermuxActivity",
                "-a", "android.intent.action.RUN",
                "--es", "com.termux.RUN_COMMAND_PATH", python_exe,
                "--esa", "com.termux.RUN_COMMAND_ARGUMENTS", copy_path,
            ]
        )
        print("[+] Started now in a new visible Termux session.")


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
    print("    Apple's background execution model suspends third‑party code")
    print("    within seconds of leaving the foreground, and there is no")
    print("    equivalent of launchd, systemd, or Task Scheduler for user scripts.")
    print("    This is a documented platform limitation, not a missing feature.")
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
    action = f'"{wscript_exe}" //B //Nologo "{vbs_path}"'

    if build >= 26100:
        action = f'cmd /c timeout /t 5 /nobreak >nul && {action}'

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
        print(f"[-] schtasks failed: {res.stderr.strip() or res.stdout.strip()}")
        return False
    print(f"[+] Windows Task Scheduler entry created: {task_name}")
    print(f"[+] VBS launcher written: {vbs_path}")
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
        copy_path = os.path.normpath(
            os.path.join(BASE_DIR, os.path.basename(target_script))
        )
        copy_dir = BASE_DIR
        shutil.copy2(target_script, copy_path)
        print(f"[+] Copied '{target_script}' → '{copy_path}'")
        linux_create_autostart(copy_path, copy_dir, name, hidden)
        linux_launch_now(copy_path, copy_dir, hidden)
    else:
        print(f"[-] Unsupported OS: {system}")
        sys.exit(1)

    state = load_state()
    state[name] = {
        "source": os.path.abspath(target_script),
        "copy": copy_path,
        "hidden": hidden,
        "platform": "macos" if _is_macos() else ("android" if _is_android() else system),
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

    # Kill every running process for every resolved path.
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
            linux_kill(cp)

    # Remove autostart entry.
    if _is_android():
        android_remove_autostart(name)
    elif _is_macos():
        macos_remove_autostart(name)
    elif system == "windows":
        windows_remove_autostart(name)
        _windows_remove_vbs_launcher(name)
    else:
        linux_remove_autostart(name)

    # Delete copies.
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