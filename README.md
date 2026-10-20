<div align="center">

# 🚀 auto.py

**Install any Python script to start automatically — on every reboot, on every OS.**

Visible when you want to see it. Silent when you don't. One command to install, one command to remove.

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![Linux](https://img.shields.io/badge/Linux-Arch%20%7C%20Fedora%20%7C%20Ubuntu%20%7C%20Mint-FCC624?style=for-the-badge&logo=linux&logoColor=black)](https://www.kernel.org/)
[![License](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](./LICENSE)

[**Quick Start**](#-quick-start) · [**Features**](#-features) · [**Usage**](#-usage) · [**How It Works**](#-how-it-works) · [**FAQ**](#-faq)

</div>

---

> [!TIP]
> **TL;DR** — Run `python auto.py myprogram.py` once. Your script now starts on every reboot, visibly. Add `--hide` to run it silently. Add `--stop` to remove it forever.

> [!WARNING]
> **Windows users — run `cmd.exe` as Administrator.**
> `auto.py` uses Task Scheduler (`schtasks`), which returns an **`ERROR: Access is denied`** (or `ERRO`) if the terminal is not elevated. Right-click **Command Prompt → Run as administrator** before running any `auto.py` command.

> [!NOTE]
> **Linux users — no `sudo` or root needed.** Everything runs at the user level via XDG Autostart.

> [!NOTE]
> **macOS users — no `sudo` or root needed.** LaunchAgents run at the user level in `~/Library/LaunchAgents/`. Running `auto.py` with `sudo` loads the job into the `system` domain instead of your GUI login session, where it will not behave as expected. The first time the script runs from a LaunchAgent, macOS may prompt for privacy-protected resources (Files & Folders, Accessibility, Automation) — approve the prompt under **System Settings → Privacy & Security**, otherwise the script starts but silently fails on those resources.

> [!NOTE]
> **iOS users — unsupported by platform design.** `auto.py` detects iOS (`$HOME` starts with `/private/var/mobile`) and exits with a full explanation; it never writes a plist, never touches `~/Library/LaunchAgents`, and never calls `launchctl`. No elevation, entitlement, or provisioning profile can make a user script run persistently in the background on iOS.

> [!NOTE]
> **Android users — Termux + Termux:Boot from F-Droid are required, plus two settings.** Install **Termux** and **Termux:Boot** from **F-Droid only** (mixing F-Droid and Play Store builds causes signature failures and breaks boot execution), open Termux:Boot **once** so Android registers it, and disable **battery optimisation for both apps**. On **Android 14+**, also enable **Settings → System → Developer options → Disable child process restrictions** (the setting survives reboots, but switching Developer options off re-arms the phantom process killer); on **Android 12–13** there is no toggle — use the documented `adb` commands from the Termux wiki if the process dies with signal 9. On **Android 15** the OS may still terminate the process despite all of the above (Termux issue #5150); the Developer-options toggle is the only mitigation on devices that expose it.

> **Tested on: Windows, Arch linux , Kali linux , Fedora , Linux mint**

> **In Linux mint , it's not working after reboot**


---

## 📑 Table of Contents

<details open>
<summary><b>Click to expand / collapse</b></summary>

- [Why auto.py?](#-why-autopy)
- [Quick Start](#-quick-start)
- [Features](#-features)
- [Supported Operating Systems](#-supported-operating-systems)
- [Installation](#-installation)
- [Usage](#-usage)
  - [Visible mode](#-visible-mode-default)
  - [Hidden mode](#-hidden-mode---hide)
  - [Stop / Uninstall](#-stop--uninstall---stop)
- [Behavior Matrix](#-behavior-matrix)
- [How It Works](#-how-it-works)
  - [Windows internals](#windows)
  - [Linux internals](#linux)
- [File Layout](#-file-layout)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Prompt for Future Updates](#-prompt-for-future-updates)
- [License](#-license)

</details>

---

## 🤔 Why auto.py?

You wrote a Python script — a bot, a watcher, a server, a monitor — and you want it to **start on every boot**, on **both Linux and Windows**, with **one command**, without touching `systemd`, Task Scheduler, or `.desktop` files by hand.

`auto.py` does exactly that:

```bash
python auto.py myprogram.py            # visible, survives reboot
python auto.py myprogram.py --hide     # silent, survives reboot
python auto.py myprogram.py --stop     # remove permanently
```

**Three commands. Two operating systems. Zero configuration files to edit.**

---

## 🤖 Prompt for Future Updates

OSes evolve. When Windows 12 ships, or when Fedora changes its default terminal again, paste the block below into any AI agent along with this file.

<details>
<summary><b>📋 Click to expand the full prompt</b></summary>

```text
You are a senior cross-platform systems engineer. Update the provided `auto.py` script so it remains fully compatible with the latest documented behavior of ALL platforms listed below. Treat this prompt as the single source of truth for the script’s contract.

## Supported platforms (must all be preserved)

**Windows:** Windows 10 (all supported builds), Windows 11 (23H2, 24H2, 25H2). Windows 12 has not shipped as of October 2026 — Microsoft has made no announcement and explicitly denied plans for a 2026 release. Do not add Windows 12 code paths; state explicitly in the change log that it is unsupported because it does not exist.

**macOS:** macOS Sequoia (15), macOS Tahoe (26). The script uses LaunchAgents (`~/Library/LaunchAgents/com.visiblebackground.*.plist`) with `RunAtLoad=true` for login persistence. macOS 26 Tahoe has known `launchctl bootstrap` reliability issues; the fallback to legacy `launchctl load -w` must be preserved.

**iOS:** Unsupported by platform design — see the dedicated iOS-specific rules below. Do not attempt to add iOS support.

**Android (9 through 15+):** Supported only via Termux and Termux:Boot (installed from F-Droid, not Google Play). The script writes boot scripts to `~/.termux/boot/`. Critical known issue: On Android 15, the OS aggressively kills Termux background processes even with `termux-wake-lock` active and battery optimization disabled — this is a confirmed upstream bug tracked in Termux issue #5150. The script must preserve `termux-wake-lock` and print a prominent warning that Android 15 may still terminate the process, advising the user to enable “Disable child process restrictions” in Developer Options if available. Do not promise reliability that the platform does not provide.

**Linux (all distributions using XDG Autostart):** Arch Linux, Omarchy Linux, Manjaro, Ubuntu (LTS + interim), Kali Linux, Linux Mint (Cinnamon, XFCE, MATE), Fedora Workstation, Pop!_OS (GNOME + COSMIC), Zorin OS, and any major Debian/Ubuntu/Fedora/Arch derivative. The script writes `~/.config/autostart/<name>.desktop`. No sudo or root is ever required on Linux.

### Terminal-emulator detection order (must be preserved)
`xdg-terminal-exec` → `x-terminal-emulator` → `ptyxis` → `kgx` → `gnome-terminal` → `konsole` → `xfce4-terminal` → `mate-terminal` → `cosmic-term` → `ghostty` → `foot` → `xterm`

If none is found, launch detached and print a warning — do not fail silently.

Current documented defaults (for verification):
- Fedora Workstation 41+ uses `ptyxis` as the default terminal. Ubuntu 25.10+ also defaults to `ptyxis`.
- Linux Mint Cinnamon uses `gnome-terminal`; Linux Mint MATE uses `mate-terminal`.
- Pop!_OS COSMIC uses `cosmic-term`.

## What the script must do (unchanged CLI contract)

1. `python auto.py myprogram.py` → copies `myprogram.py` into `~/.configs/`, installs an autostart entry that runs the copy visibly on every reboot/login.
2. `python auto.py myprogram.py --hide` → same copy, but runs silently in the background on every reboot/login.
3. `python auto.py myprogram.py --stop` → kills the running copy, removes the autostart entry, and deletes the copy permanently.
4. Manual kill (Task Manager / kill / Activity Monitor) must only stop the current session; the autostart entry must survive so the program returns on next login.

## Windows-specific rules (must be preserved exactly)

- Admin elevation required. `schtasks /Create` and `schtasks /Delete` must be run from an elevated Command Prompt. Detect non-elevated execution via `ctypes.windll.shell32.IsUserAnAdmin()` and print a clear instruction before attempting `schtasks`.
- `.py` input without `--hide` → saved as `.py`, run with `python.exe` (visible console), task created with `/SC ONLOGON /IT`.
- `.pyw` input OR `--hide` → saved as `.pyw`, run with `pythonw.exe`, no console window, task created with `/SC ONLOGON /IT`.
- Hidden subprocess flags: `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB`. Must NOT include `DETACHED_PROCESS` — MSDN documents that `CREATE_NO_WINDOW` is ignored when combined with `DETACHED_PROCESS`.
- For Windows 11 build ≥ 26100 (25H2), prepend `timeout /t 5 /nobreak >nul &&` to the task action (not inside the VBS launcher) for “Delayed Desktop Initialization.”
- `--stop` must work regardless of whether the original argument was `.py` or `.pyw`; use the sanitized base name to locate the copy.

## macOS-specific rules

- Write `~/Library/LaunchAgents/com.visiblebackground.<name>.plist` with `RunAtLoad=true`.
- Load via `launchctl bootstrap gui/$(id -u) <plist>` first. If it fails (macOS 26 Tahoe is known to return EIO/exit 5 on valid plists), fall back to `launchctl load -w <plist>`. On `--stop`, try `launchctl bootout gui/$(id -u)/<label>` first, then `launchctl unload -w`.
- Visible mode: open Terminal via `osascript -e 'tell application "Terminal" to do script "..."'`.
- Hidden mode: run Python directly with `stdout=DEVNULL`, `stderr=DEVNULL`, `start_new_session=True`.

## iOS-specific rules

- iOS is unsupported. The script must detect iOS and exit with a clear, documented explanation instead of attempting an install that the OS will silently break.
- Detection: `platform.system() == "darwin"` and `$HOME` starts with `/private/var/mobile`.
- The explanation must state the following facts, each backed by Apple’s own documentation:
  - iOS suspends third-party apps shortly after they move to the background. This suspension prevents the process from running any code.[reference:0]
  - There is no general-purpose mechanism for running code continuously, at a specific time, at a guaranteed interval, or in response to a network/IPC request in the background.[reference:1]
  - `BGAppRefreshTask` is opportunistic and time-bounded to roughly 30 seconds.[reference:2][reference:3] `BGProcessingTask` is also opportunistic and typically runs only when the device is idle and plugged in, for about 60 seconds (sometimes a few minutes).[reference:4] Neither is a substitute for a persistent autostart daemon.
  - Scheduling is decided by `dasd` (Duet Activity Scheduler Daemon), not by the app. Battery level below ~20%, Low Power Mode, thermal pressure, and low user engagement can all cause a submitted task to be dropped entirely.[reference:5]
  - Once the user force-quits an app, iOS will not restart it in the background. No third-party library can bypass this.[reference:6]
  - A Jailbroken device or an MDM-supervised device does not change this contract for ordinary user scripts; do not suggest jailbreak or MDM workarounds as part of the script.
- The script must not write any files to `~/Library/LaunchAgents` on iOS, must not call `launchctl`, and must not create any plist.
- The same `ios_unsupported()` guard must run at the top of both `install()` and `uninstall()` so that neither `--hide` nor `--stop` can ever reach platform-specific code on iOS.
- If the user asks for a best-effort alternative, the script may print (but must not implement) that the only Apple-sanctioned path is a Shortcuts automation triggered by “Device Unlocked” or “Wi-Fi connected” after boot. This is a user-configured workaround, not something a Python script can install.[reference:7][reference:8] The script must not pretend it has configured this for the user.

## Android / Termux rules

- Require Termux (F-Droid build) and the Termux:Boot add-on. Refuse to install if `$PREFIX` does not start with `/data/data/com.termux`.
- Write boot scripts to `~/.termux/boot/start-<name>.sh` with `termux-wake-lock` as the first command after the shebang.
- Visible mode: use `am start --user 0 -n com.termux/.app.TermuxActivity -a android.intent.action.RUN` with the `RUN_COMMAND_PATH` / `RUN_COMMAND_ARGUMENTS` extras so a terminal window appears.
- Hidden mode: background the Python process with output redirected to `/dev/null`.
- Print a warning that Android 15 may still kill the process despite the wake-lock (upstream issue #5150) and instruct the user to disable child-process restrictions if the option exists.

## Linux-specific rules (XDG Autostart)

- No sudo / root. Ever.
- Write `~/.config/autostart/<name>.desktop`.
- Always wrap `Exec=` in `sh -c 'cd "<copy_dir>" && …'` because XFCE and KDE Plasma ignore the `Path=` key.
- Exec-key quoting must follow the Desktop Entry Specification: escape `\`, `"`, `` ` ``, `$`, and literal `%` (as `%%`) inside double quotes.
- Hidden mode: `subprocess.Popen` with `stdout=DEVNULL`, `stderr=DEVNULL`, `start_new_session=True`, `cwd=copy_dir`.
- Visible mode: explicitly launch a terminal emulator from the detection list. Do not rely on `Terminal=true` alone — many desktop environments ignore it.
- If no terminal is found, fall back to detached launch and print a warning.

## Mandatory verification steps for every update

Before changing any code, the agent must consult the latest official sources:

1. Microsoft Learn: `schtasks` syntax, `/IT` flag, elevation requirements, session-0 isolation, Windows 11 25H2 desktop-init behavior.
2. Apple Developer Documentation: `launchd.plist` man page, `launchctl bootstrap` / `bootout` domain targets, macOS 26 Tahoe release notes.
3. Apple Developer Forums: iOS Background Execution Limits, `BGTaskScheduler` time budgets, `dasd` scheduling behavior, force-quit restrictions.
4. Termux Wiki: Termux:Boot setup, `~/.termux/boot/` script requirements, Android 15 background restrictions.
5. freedesktop.org: XDG Autostart Specification (current version), Desktop Entry Specification (Exec key quoting rules).
6. XFCE Bugzilla / KDE Bugzilla: status of `Path=` key support in autostart entries.
7. Distribution release notes: default terminal emulator changes for Fedora (Ptyxis), Ubuntu (Ptyxis 25.10+), Linux Mint (gnome-terminal / mate-terminal), Pop!_OS COSMIC.
8. Python `subprocess` docs: current `creationflags` constants on Windows.

Compare each documented behavior against the current script. Fix every mismatch, deprecated flag, or newly documented bug. If a platform has no confirmed changes, state that explicitly instead of guessing.

## What the agent must return

1. The complete corrected `auto.py` script.
2. A table with one row per bug found, showing:
   - The bug (with exact location in the old script).
   - The fix applied.
   - The authoritative documentation that justifies the fix (URL or document title).

Do not add features that were not requested. Do not change the `.py` / `.pyw` naming rules on Windows or the `--hide` semantics. Do not introduce elevation requirements on Linux. Do not attempt to add iOS support — it is impossible by platform design.
```

**Then again give this prompt:**

```text
Re-check the script again, find bugs and fix them. Always read the latest documentation and guidelines of every supported Linux distro, even ubuntu server , Red Hat Enterprise server , latest windows 10/ 11 or latest windows and latest mac os , latest ios and android 9 to 15 or latest available version . So make sure that on every distro and operating system , it perfectly works, even after reboot and even after shutdown and start operating system again. Fix all the bugs and errors. Please re-check it perfectly again. Don't make any errors, it should work very smoothly without causing any issues. you can do online deep research for latest documentation for every supported Linux distro  even ubuntu server , Red Hat Enterprise server, latest windows 10/ 11 or latest windows and latest mac os , latest ios and android 9 to 15 or latest available version . double check everything and make it perfect . 
```

</details>

---

---

## ⚡ Quick Start

> [!IMPORTANT]
> **Windows:** open **Command Prompt as Administrator** first (Start → type `cmd` → right-click → **Run as administrator**). Without elevation, `schtasks` returns `ERROR: Access is denied` and the script will exit.
> **Linux:** run normally as your user — **no `sudo` needed**.

**Windows — open elevated terminal:**

```cmd
:: Start menu → search "cmd" → Right-click → "Run as administrator"
:: OR press Win+X → "Terminal (Admin)" / "Command Prompt (Admin)"
:: Then, in the elevated window:
cd C:\path\to\auto
python auto.py C:\path\to\myprogram.py
```

**Linux — open a normal terminal:**

```bash
# 1. Clone the repo
git clone https://github.com/boss-defender/Auto-Py.git
cd auto

# 2. Install your script — visible on every reboot
python3 auto.py /path/to/myprogram.py

# 3. Or install it silently in the background
python3 auto.py /path/to/myprogram.py --hide

# 4. Remove it permanently when done
python3 auto.py myprogram.py --stop
```

That's it. No `pip install`, no virtualenv, no compiled extensions.

---

## ✨ Features

<table>
<tr>
<td width="50%">

**🔁 Reboot persistence**
Auto-starts on every login/reboot until you `--stop` it.

**👁️ Visible or hidden**
Show a terminal window, or run silently with no UI.

**📦 Self-contained**
Copies your script to `~/.configs/` — keeps running even if the original is deleted.

**You can change .configs to any folder name like .msdxs or visible-folder etc**

**🐍 `.py` / `.pyw` aware on Windows**
Automatically swaps to `pythonw.exe` + `.pyw` when `--hide` is used.

</td>
<td width="50%">

**🛡️ Session-safe kill**
Killing via Task Manager / `kill` stops only the *current* session. Next reboot brings it back.

**🧹 One-shot uninstall**
`--stop` kills the process, removes the autostart entry, and deletes the copy.

**🌐 XDG-compliant on Linux**
GNOME · KDE · XFCE · Cinnamon · MATE · Hyprland · COSMIC — **no root needed**.

**⚡ Modern terminal support**
`xdg-terminal-exec`, `ptyxis`, `kgx`, `ghostty`, `foot`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `xterm`, `x-terminal-emulator`.

</td>
</tr>
</table>

---

## 💻 Supported Operating Systems

| OS | Version Tested | Autostart Mechanism | Elevation Required? | Notes |
|:---|:---|:---|:---:|:---|
| **Arch Linux** | Rolling | XDG Autostart | ❌ no | Any DE / WM |
| **Omarchy Linux** | Rolling (Hyprland) | XDG + `xdg-terminal-exec` | ❌ no | Ghostty / Foot / Alacritty / Kitty |
| **Ubuntu** | 22.04 · 24.04 · 25.04 | XDG Autostart | ❌ no | GNOME |
| **Kali Linux** | Latest | XDG Autostart | ❌ no | XFCE / GNOME |
| **Linux Mint** | 21 · 22 | XDG Autostart | ❌ no | Cinnamon / XFCE / MATE |
| **Fedora Workstation** | 39 · 40 · 41 | XDG Autostart | ❌ no | GNOME / KDE / XFCE |
| **Pop!_OS** | 22.04 · 24.04 (COSMIC) | XDG Autostart | ❌ no | Auto-detects `ptyxis` / `kgx` |
| **Zorin OS** | 17 · 18 | XDG Autostart | ❌ no | GNOME-based |
| **Windows 10** | 22H2 | Task Scheduler | ✅ **Administrator** | `ONLOGON /IT` |
| **Windows 11** | 23H2 · 24H2 · 25H2 | Task Scheduler | ✅ **Administrator** | 25H2 gets extra startup delay |

---

## 📥 Installation

<details>
<summary><b>Prerequisites</b></summary>

| Requirement | Linux | Windows |
|:---|:---|:---|
| **Python 3.8+** | ✅ required | ✅ required |
| **`pythonw.exe`** | — | ✅ ships with the standard installer |
| **Desktop environment** | ✅ any XDG-compliant DE | — (Task Scheduler) |
| **Elevation** | ❌ **not needed** — user-level autostart | ✅ **Administrator cmd.exe required** |

> [!WARNING]
> **Windows:** Task Scheduler operations (`schtasks /Create`, `/Delete`) fail with `ERROR: Access is denied` (or `ERRO`) when the terminal is not elevated. There is no way around this — Windows requires admin rights to register tasks that run at logon.

</details>

<details>
<summary><b>Steps — Linux</b></summary>

```bash
git clone https://github.com/<your-username>/auto.git
cd auto

# Verify Python
python3 --version
```

`auto.py` uses **only the Python standard library** — no third-party packages, no compilation, no virtualenv required.

</details>

<details>
<summary><b>Steps — Windows</b></summary>

1. **Open an elevated Command Prompt:**
   - Start menu → search `cmd` → right-click **Run as administrator**, **or**
   - Press <kbd>Win</kbd> + <kbd>X</kbd> → **Terminal (Admin)** / **Command Prompt (Admin)**
2. Verify the window title says **"Administrator"**.
3. Clone and run:

```cmd
git clone https://github.com/<your-username>/auto.git
cd auto

python --version
```

</details>

---

## 🎯 Usage

> [!IMPORTANT]
> **Windows:** every command below must be run from an **elevated** Command Prompt.
> **Linux:** run from any normal terminal — no elevation.

### Visible mode (default)

```bash
python auto.py myprogram.py
```

1. Copies `myprogram.py` → `~/.configs/myprogram.py`
2. Registers it to run **with a terminal window** on every login
3. Starts it immediately so you don't have to reboot

### Hidden mode (`--hide`)

```bash
python auto.py myprogram.py --hide
```

1. Copies `myprogram.py` → `~/.configs/myprogram.pyw` **(Windows only)**
2. Registers it to run **with no window** on every login
3. Starts it immediately in the background

### Stop / Uninstall (`--stop`)

```bash
python auto.py myprogram.py --stop
```

1. Kills the running copy
2. Deletes the autostart entry (Task Scheduler task or `.desktop` file)
3. Removes the copy from `~/.configs/`

> [!IMPORTANT]
> After `--stop`, the program **will not come back** on reboot.
> On **Windows**, `--stop` also requires an **elevated** Command Prompt because deleting a scheduled task needs admin rights.

<details>
<summary><b>Handling <code>.pyw</code> files on Windows</b></summary>

```bash
python auto.py myprogram.pyw            # background, .pyw saved
python auto.py myprogram.pyw --hide     # same result (redundant)
python auto.py myprogram.pyw --stop     # remove by base name
```

The **base name** (`myprogram`) is what `--stop` uses to find the copy, so `--stop` works regardless of whether you originally passed `.py` or `.pyw`.

</details>

---

## 📊 Behavior Matrix

| Command | Saved as | Runs with | Window? | Survives reboot? | Elevation? |
|:---|:---|:---|:---:|:---:|:---:|
| `auto.py app.py` *(Linux)* | `app.py` | `python3` | ✅ terminal | ✅ yes | ❌ no |
| `auto.py app.py --hide` *(Linux)* | `app.py` | `python3` *(detached)* | ❌ none | ✅ yes | ❌ no |
| `auto.py app.py` *(Windows)* | `app.py` | `python.exe` | ✅ console | ✅ yes | ✅ **Admin** |
| `auto.py app.py --hide` *(Windows)* | `app.pyw` | `pythonw.exe` | ❌ none | ✅ yes | ✅ **Admin** |
| `auto.py app.pyw` *(Windows)* | `app.pyw` | `pythonw.exe` | ❌ none | ✅ yes | ✅ **Admin** |
| `auto.py app.py --stop` | — | — | — | ❌ removed | ✅ **Admin** *(Windows only)* |

### Session kill vs. permanent stop

| Action | Effect | Elevation? |
|:---|:---|:---:|
| Task Manager → End task | ❌ stops current session only — **returns next login** | ❌ no |
| `kill <pid>` *(Linux)* | ❌ stops current session only — **returns next login** | ❌ no |
| `auto.py app.py --stop` | ✅ **permanent** — autostart entry deleted, will never return | ✅ **Admin** *(Windows only)* |

> [!NOTE]
> This is by design — it mirrors how real "always-on" services behave. Only an explicit `--stop` removes the autostart entry.

---

## ⚙️ How It Works

### Windows

Uses **Task Scheduler** with `/SC ONLOGON /IT /RL LIMITED`:

| Flag | Purpose |
|:---|:---|
| `/SC ONLOGON` | Fires at every user login |
| `/IT` | Runs in the **interactive user session** — required for visible console (session 0 cannot draw UI) |
| `/RL LIMITED` | Runs with normal user rights, not elevated |

> [!WARNING]
> **`schtasks /Create` and `schtasks /Delete` require an elevated terminal**, even with `/RL LIMITED`. The `/RL LIMITED` flag controls the rights of the *running task*, not the rights needed to *create* it. Running `auto.py` from a non-elevated `cmd.exe` returns:
> ```
> ERROR: Access is denied.
> ```

<details>
<summary><b>Visible mode (<code>.py</code>) — task action</b></summary>

```cmd
cmd.exe /c cd /d "%USERPROFILE%\.configs" && start "" "python.exe" "app.py"
```

`start` forces a fresh console window even if the parent has none.

</details>

<details>
<summary><b>Hidden mode (<code>.pyw</code>) — task action</b></summary>

```cmd
cmd.exe /c cd /d "%USERPROFILE%\.configs" && "pythonw.exe" "app.pyw"
```

`pythonw.exe` is the windowless Python interpreter that ships with the standard installer.

</details>

<details>
<summary><b>Windows 11 25H2 (build ≥ 26100) — extra startup delay</b></summary>

Windows added a **Delayed Desktop Initialization** phase that can fire ONLOGON tasks before the shell is ready. On those builds, `auto.py` prefixes the task action with:

```cmd
timeout /t 5 /nobreak >nul &&
```

so the program waits for the desktop to finish loading.

</details>

<details>
<summary><b>Hidden subprocess flags — why no <code>DETACHED_PROCESS</code>?</b></summary>

For the immediate-start call, the script uses:

```python
CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB
```

> [!WARNING]
> `DETACHED_PROCESS` is **intentionally omitted** — per MSDN, `CREATE_NO_WINDOW` is silently ignored when combined with `DETACHED_PROCESS`, which would allow a console to flash. `CREATE_BREAKAWAY_FROM_JOB` prevents the child from being killed if the parent is in a job object.

</details>

---

### Linux

Uses the **XDG Autostart specification** — a `.desktop` file at `~/.config/autostart/<name>.desktop`.

> [!TIP]
> **No `sudo`, no root, no elevation needed.** Everything is written inside the user's own `$HOME`, which is the standard, spec-compliant location for per-user autostart entries.

<details>
<summary><b>Example generated <code>.desktop</code> file</b></summary>

```ini
[Desktop Entry]
Type=Application
Name=myprogram
Exec=sh -c 'cd "/home/user/.configs" && "/usr/bin/python3" "/home/user/.configs/myprogram.py"'
Path=/home/user/.configs
Terminal=true
X-GNOME-Autostart-enabled=true
Hidden=false
```

</details>

<details>
<summary><b>Why the <code>sh -c 'cd … && …'</code> wrapper?</b></summary>

The spec allows a `Path=` key for the working directory, but **XFCE and KDE Plasma ignore it** (confirmed, long-standing bugs in both trackers). The shell wrapper guarantees the working directory is correct on every DE.

</details>

<details>
<summary><b>Terminal selection order (visible mode)</b></summary>

| # | Terminal | Used by |
|:---:|:---|:---|
| 1 | `xdg-terminal-exec` | Omarchy, Arch, Fedora 40+ |
| 2 | `x-terminal-emulator` | Debian alternatives — Ubuntu, Mint, Kali |
| 3 | `ptyxis` | Pop!_OS 24.04+, GNOME 47+ |
| 4 | `kgx` | GNOME Console |
| 5 | `gnome-terminal` | Ubuntu, Fedora, Zorin |
| 6 | `konsole` | KDE Plasma |
| 7 | `xfce4-terminal` | XFCE |
| 8 | `ghostty` | Omarchy fallback |
| 9 | `foot` | Wayland-native fallback |
| 10 | `xterm` | Last resort |

If none are found, the script launches detached and prints a warning — it never fails silently.

</details>

<details>
<summary><b>Hidden mode on Linux — no terminal needed</b></summary>

```python
subprocess.Popen(
    [python, script],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
    cwd=copy_dir,
)
```

`start_new_session=True` detaches the process from the parent so killing the terminal does not kill the script.

</details>

---

## 🗑️ Uninstalling

```bash
python auto.py myprogram.py --stop
```

> [!IMPORTANT]
> **Windows:** `--stop` deletes a scheduled task, which requires an **elevated** Command Prompt. If you skip this, you'll see `ERROR: Access is denied`.
> **Linux:** run normally — no `sudo`.

> [!NOTE]
> This single command kills every running instance, deletes the autostart entry, removes the copy, and cleans up `state.json`.

<details>
<summary><b>Nuke everything auto.py ever created</b></summary>

**Linux** *(no `sudo`)*:

```bash
rm -rf ~/.configs
rm -f ~/.config/autostart/*.desktop   # inspect first!
```

**Windows (PowerShell — Run as Administrator):**

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\.configs"
Get-ScheduledTask | Where-Object { $_.TaskName -like "VisibleBackground_*" } | Unregister-ScheduledTask -Confirm:$false
```

</details>

---

## 📁 File Layout

After installing `myprogram.py`, your home directory contains:

```text
~/
├── .configs/
│   ├── myprogram.py        ← the copied script
│   ├── state.json          ← registry of installed scripts
│   └── ...                 ← other scripts you installed
└── .config/
    └── autostart/
        └── myprogram.desktop   ← Linux only
```

On Windows, the autostart entry lives **outside** the home folder — it's a Task Scheduler entry named `VisibleBackground_myprogram`.

<details>
<summary><b>What does <code>state.json</code> look like?</b></summary>

```json
{
  "myprogram": {
    "source": "/home/user/projects/myprogram.py",
    "copy":   "/home/user/.configs/myprogram.py",
    "hidden": false,
    "ext":    null
  }
}
```

</details>

---

## 🩺 Troubleshooting

<details>
<summary><b>🪟 Windows issues</b></summary>

### `ERROR: Access is denied` / `ERRO` when running `auto.py`

**This is the most common issue.** `schtasks` requires an elevated terminal.

**Fix:** Open **Command Prompt as Administrator**, then re-run the command.

- Start menu → search `cmd` → right-click → **Run as administrator**
- Or press <kbd>Win</kbd> + <kbd>X</kbd> → **Terminal (Admin)** / **Command Prompt (Admin)**
- Verify the window title bar says **"Administrator: C:\Windows\System32\cmd.exe"**

### Visible console doesn't appear after reboot

- Confirm the task exists: `schtasks /Query /TN VisibleBackground_myprogram`
- Confirm `/IT` is set — tasks without `/IT` run in **session 0** and cannot show UI
- On Windows 11 25H2, the 5-second delay is expected — check again after ~10 seconds

### Hidden process shows a console flash at boot

- Make sure the saved file has the `.pyw` extension
- Verify the task action references `pythonw.exe`, not `python.exe`
- Do not edit the task to add `DETACHED_PROCESS` — it breaks `CREATE_NO_WINDOW`

### Task creation fails with "The system cannot find the file specified"

- Ensure the `cmd.exe` working directory is valid
- Confirm `python.exe` / `pythonw.exe` are on `PATH` — run `where python` and `where pythonw`

</details>

<details>
<summary><b>🐧 Linux issues</b></summary>

> [!TIP]
> **Linux never needs `sudo` for `auto.py`.** If any guide or error message tells you to `sudo`, something is wrong — the tool only writes into `$HOME`.

### No terminal opens in visible mode

- Run `which xdg-terminal-exec ptyxis kgx gnome-terminal konsole xfce4-terminal` to see what's installed
- `auto.py` prints `[+] Started now in a visible terminal (X)` with the one it chose
- If nothing is printed, it fell back to detached mode

### `Path=` is ignored

- Expected on **XFCE and KDE Plasma**
- The `sh -c 'cd … && …'` wrapper compensates automatically — **no action needed**

### Autostart entry exists but doesn't run

- Check the `.desktop` file syntax: `desktop-file-validate ~/.config/autostart/myprogram.desktop`
- Ensure the file is executable: `chmod +x ~/.config/autostart/myprogram.desktop`
- Restart your session or run the DE's autostart refresh command (e.g., `systemctl --user restart plasma-plasmashell` on KDE)

### Killing the terminal kills the script

- This happens only if you launch the script **manually** from a terminal
- When launched by `auto.py` via `.desktop`, the process is owned by the DE and survives

</details>

---

## ❓ FAQ

<details>
<summary><b>Do I need to run <code>auto.py</code> as Administrator on Windows?</b></summary>

**Yes — for every command** (`install`, `--hide`, and `--stop`).

- `schtasks /Create` — requires elevation
- `schtasks /Delete` — requires elevation

`/RL LIMITED` in the task itself only affects how the *running program* is launched — it does **not** exempt you from running the *installer* as admin.

</details>

<details>
<summary><b>Do I need <code>sudo</code> on Linux?</b></summary>

**No.** `auto.py` on Linux only writes to `~/.config/autostart/` and `~/.configs/` — both inside your own home directory. Running it with `sudo` would put the files under `root`'s home and break the autostart entry for your user.

</details>

<details>
<summary><b>What happens if I delete the original <code>myprogram.py</code>?</b></summary>

The copy in `~/.configs/` keeps running. `--stop` still works because it uses the copy.

</details>

<details>
<summary><b>Can I install multiple scripts?</b></summary>

Yes. Each script gets its own autostart entry (`VisibleBackground_<name>` on Windows, `<name>.desktop` on Linux). `state.json` tracks all of them.

</details>

<details>
<summary><b>Can I reinstall the same script with different <code>--hide</code> settings?</b></summary>

Yes. Running `auto.py myprogram.py --hide` after `auto.py myprogram.py` will tear down the old visible entry and install the hidden one.

</details>

<details>
<summary><b>Does <code>--stop</code> need the exact original filename?</b></summary>

No — only the **base name** matters. `--stop myprogram.py` and `--stop myprogram.pyw` do the same thing.

</details>

<details>
<summary><b>Can I run this on a server (no desktop)?</b></summary>

`auto.py` targets **user sessions**. On a headless server, use `systemd --user` directly. The visible mode will not work without a display server.

</details>

<details>
<summary><b>Is it safe to edit the <code>.desktop</code> file manually?</b></summary>

Yes, but re-running `auto.py` will overwrite it.

</details>

<details>
<summary><b>Where does the "program" actually run from?</b></summary>

Always from `~/.configs/`, **never** from its original location. This means relative paths inside your script resolve relative to that folder.

</details>

<details>
<summary><b>What Python interpreter is used?</b></summary>

Whatever `sys.executable` points to when you run `auto.py`. If you use a virtualenv, the venv's Python is used. On Windows, the `.exe` is swapped between `python.exe` and `pythonw.exe` as needed.

</details>

---


## 📜 License

**MIT License** — free to use, modify, and redistribute. See [`LICENSE`](./LICENSE) for details.

---

## 🙏 Acknowledgements

- [freedesktop.org XDG Autostart Specification](https://specifications.freedesktop.org/autostart-spec/latest/)
- [Microsoft Learn — `schtasks` reference](https://learn.microsoft.com/windows-server/administration/windows-commands/schtasks)
- [Python docs — `subprocess` creationflags](https://docs.python.org/3/library/subprocess.html#windows-constants)

---

<div align="center">

**⭐ If this saved you time, consider giving the repo a star.**

<sub>Built for people who want their scripts to *Just Keep Running*.</sub>

</div>
