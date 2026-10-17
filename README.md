<div align="center">

# 🚀 autorun.py

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
> **TL;DR** — Run `python autorun.py myprogram.py` once. Your script now starts on every reboot, visibly. Add `--hide` to run it silently. Add `--stop` to remove it forever.

---

## 📑 Table of Contents

<details open>
<summary><b>Click to expand / collapse</b></summary>

- [Why autorun.py?](#-why-autorunpy)
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

## 🤔 Why autorun.py?

You wrote a Python script — a bot, a watcher, a server, a monitor — and you want it to **start on every boot**, on **both Linux and Windows**, with **one command**, without touching `systemd`, Task Scheduler, or `.desktop` files by hand.

`autorun.py` does exactly that:

```bash
python autorun.py myprogram.py            # visible, survives reboot
python autorun.py myprogram.py --hide     # silent, survives reboot
python autorun.py myprogram.py --stop     # remove permanently
```

**Three commands. Two operating systems. Zero configuration files to edit.**

---

## ⚡ Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/<your-username>/autorun.git
cd autorun

# 2. Install your script — visible on every reboot
python autorun.py /path/to/myprogram.py

# 3. Or install it silently in the background
python autorun.py /path/to/myprogram.py --hide

# 4. Remove it permanently when done
python autorun.py myprogram.py --stop
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
Copies your script to `~/Visible-Background-Process/` — keeps running even if the original is deleted.

**🐍 `.py` / `.pyw` aware on Windows**
Automatically swaps to `pythonw.exe` + `.pyw` when `--hide` is used.

</td>
<td width="50%">

**🛡️ Session-safe kill**
Killing via Task Manager / `kill` stops only the *current* session. Next reboot brings it back.

**🧹 One-shot uninstall**
`--stop` kills the process, removes the autostart entry, and deletes the copy.

**🌐 XDG-compliant on Linux**
GNOME · KDE · XFCE · Cinnamon · MATE · Hyprland · COSMIC.

**⚡ Modern terminal support**
`xdg-terminal-exec`, `ptyxis`, `kgx`, `ghostty`, `foot`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `xterm`, `x-terminal-emulator`.

</td>
</tr>
</table>

---

## 💻 Supported Operating Systems

| OS | Version Tested | Autostart Mechanism | Notes |
|:---|:---|:---|:---|
| **Arch Linux** | Rolling | XDG Autostart | Any DE / WM |
| **Omarchy Linux** | Rolling (Hyprland) | XDG + `xdg-terminal-exec` | Ghostty / Foot / Alacritty / Kitty |
| **Ubuntu** | 22.04 · 24.04 · 25.04 | XDG Autostart | GNOME |
| **Kali Linux** | Latest | XDG Autostart | XFCE / GNOME |
| **Linux Mint** | 21 · 22 | XDG Autostart | Cinnamon / XFCE / MATE |
| **Fedora Workstation** | 39 · 40 · 41 | XDG Autostart | GNOME / KDE / XFCE |
| **Pop!_OS** | 22.04 · 24.04 (COSMIC) | XDG Autostart | Auto-detects `ptyxis` / `kgx` |
| **Zorin OS** | 17 · 18 | XDG Autostart | GNOME-based |
| **Windows 10** | 22H2 | Task Scheduler | `ONLOGON /IT` |
| **Windows 11** | 23H2 · 24H2 · 25H2 | Task Scheduler | 25H2 gets extra startup delay |

---

## 📥 Installation

<details>
<summary><b>Prerequisites</b></summary>

| Requirement | Details |
|:---|:---|
| **Python 3.8+** | Installed on the target system |
| **Windows** | `pythonw.exe` must be available (ships with the standard installer) |
| **Linux** | A desktop environment that honours the XDG Autostart spec (all mainstream DEs do) |

</details>

<details>
<summary><b>Steps</b></summary>

```bash
git clone https://github.com/<your-username>/autorun.git
cd autorun

# Verify Python
python --version   # or: python3 --version
```

`autorun.py` uses **only the Python standard library** — no third-party packages, no compilation, no virtualenv required.

</details>

---

## 🎯 Usage

### Visible mode (default)

```bash
python autorun.py myprogram.py
```

1. Copies `myprogram.py` → `~/Visible-Background-Process/myprogram.py`
2. Registers it to run **with a terminal window** on every login
3. Starts it immediately so you don't have to reboot

### Hidden mode (`--hide`)

```bash
python autorun.py myprogram.py --hide
```

1. Copies `myprogram.py` → `~/Visible-Background-Process/myprogram.pyw` **(Windows only)**
2. Registers it to run **with no window** on every login
3. Starts it immediately in the background

### Stop / Uninstall (`--stop`)

```bash
python autorun.py myprogram.py --stop
```

1. Kills the running copy
2. Deletes the autostart entry (Task Scheduler task or `.desktop` file)
3. Removes the copy from `~/Visible-Background-Process/`

> [!IMPORTANT]
> After `--stop`, the program **will not come back** on reboot.

<details>
<summary><b>Handling <code>.pyw</code> files on Windows</b></summary>

```bash
python autorun.py myprogram.pyw            # background, .pyw saved
python autorun.py myprogram.pyw --hide     # same result (redundant)
python autorun.py myprogram.pyw --stop     # remove by base name
```

The **base name** (`myprogram`) is what `--stop` uses to find the copy, so `--stop` works regardless of whether you originally passed `.py` or `.pyw`.

</details>

---

## 📊 Behavior Matrix

| Command | Saved as | Runs with | Window? | Survives reboot? |
|:---|:---|:---|:---:|:---:|
| `autorun.py app.py` *(Linux)* | `app.py` | `python3` | ✅ terminal | ✅ yes |
| `autorun.py app.py --hide` *(Linux)* | `app.py` | `python3` *(detached)* | ❌ none | ✅ yes |
| `autorun.py app.py` *(Windows)* | `app.py` | `python.exe` | ✅ console | ✅ yes |
| `autorun.py app.py --hide` *(Windows)* | `app.pyw` | `pythonw.exe` | ❌ none | ✅ yes |
| `autorun.py app.pyw` *(Windows)* | `app.pyw` | `pythonw.exe` | ❌ none | ✅ yes |
| `autorun.py app.py --stop` | — | — | — | ❌ removed |

### Session kill vs. permanent stop

| Action | Effect |
|:---|:---|
| Task Manager → End task | ❌ stops current session only — **returns next login** |
| `kill <pid>` *(Linux)* | ❌ stops current session only — **returns next login** |
| `autorun.py app.py --stop` | ✅ **permanent** — autostart entry deleted, will never return |

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

<details>
<summary><b>Visible mode (<code>.py</code>) — task action</b></summary>

```cmd
cmd.exe /c cd /d "%USERPROFILE%\Visible-Background-Process" && start "" "python.exe" "app.py"
```

`start` forces a fresh console window even if the parent has none.

</details>

<details>
<summary><b>Hidden mode (<code>.pyw</code>) — task action</b></summary>

```cmd
cmd.exe /c cd /d "%USERPROFILE%\Visible-Background-Process" && "pythonw.exe" "app.pyw"
```

`pythonw.exe` is the windowless Python interpreter that ships with the standard installer.

</details>

<details>
<summary><b>Windows 11 25H2 (build ≥ 26100) — extra startup delay</b></summary>

Windows added a **Delayed Desktop Initialization** phase that can fire ONLOGON tasks before the shell is ready. On those builds, `autorun.py` prefixes the task action with:

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

<details>
<summary><b>Example generated <code>.desktop</code> file</b></summary>

```ini
[Desktop Entry]
Type=Application
Name=myprogram
Exec=sh -c 'cd "/home/user/Visible-Background-Process" && "/usr/bin/python3" "/home/user/Visible-Background-Process/myprogram.py"'
Path=/home/user/Visible-Background-Process
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
python autorun.py myprogram.py --stop
```

> [!NOTE]
> This single command kills every running instance, deletes the autostart entry, removes the copy, and cleans up `state.json`.

<details>
<summary><b>Nuke everything autorun.py ever created</b></summary>

**Linux:**

```bash
rm -rf ~/Visible-Background-Process
rm -f ~/.config/autostart/*.desktop   # inspect first!
```

**Windows (PowerShell):**

```powershell
Remove-Item -Recurse -Force "$env:USERPROFILE\Visible-Background-Process"
Get-ScheduledTask | Where-Object { $_.TaskName -like "VisibleBackground_*" } | Unregister-ScheduledTask -Confirm:$false
```

</details>

---

## 📁 File Layout

After installing `myprogram.py`, your home directory contains:

```text
~/
├── Visible-Background-Process/
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
    "copy":   "/home/user/Visible-Background-Process/myprogram.py",
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

### Visible console doesn't appear after reboot

- Confirm the task exists: `schtasks /Query /TN VisibleBackground_myprogram`
- Confirm `/IT` is set — tasks without `/IT` run in **session 0** and cannot show UI
- On Windows 11 25H2, the 5-second delay is expected — check again after ~10 seconds

### Hidden process shows a console flash at boot

- Make sure the saved file has the `.pyw` extension
- Verify the task action references `pythonw.exe`, not `python.exe`
- Do not edit the task to add `DETACHED_PROCESS` — it breaks `CREATE_NO_WINDOW`

### Task creation fails with "Access denied"

- Open an elevated (Administrator) Command Prompt **once**
- `schtasks` with `/RL LIMITED` normally does not need elevation, but some hardened corporate environments enforce it

</details>

<details>
<summary><b>🐧 Linux issues</b></summary>

### No terminal opens in visible mode

- Run `which xdg-terminal-exec ptyxis kgx gnome-terminal konsole xfce4-terminal` to see what's installed
- `autorun.py` prints `[+] Started now in a visible terminal (X)` with the one it chose
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
- When launched by `autorun.py` via `.desktop`, the process is owned by the DE and survives

</details>

---

## ❓ FAQ

<details>
<summary><b>What happens if I delete the original <code>myprogram.py</code>?</b></summary>

The copy in `~/Visible-Background-Process/` keeps running. `--stop` still works because it uses the copy.

</details>

<details>
<summary><b>Can I install multiple scripts?</b></summary>

Yes. Each script gets its own autostart entry (`VisibleBackground_<name>` on Windows, `<name>.desktop` on Linux). `state.json` tracks all of them.

</details>

<details>
<summary><b>Can I reinstall the same script with different <code>--hide</code> settings?</b></summary>

Yes. Running `autorun.py myprogram.py --hide` after `autorun.py myprogram.py` will tear down the old visible entry and install the hidden one.

</details>

<details>
<summary><b>Does <code>--stop</code> need the exact original filename?</b></summary>

No — only the **base name** matters. `--stop myprogram.py` and `--stop myprogram.pyw` do the same thing.

</details>

<details>
<summary><b>Can I run this on a server (no desktop)?</b></summary>

`autorun.py` targets **user sessions**. On a headless server, use `systemd --user` directly. The visible mode will not work without a display server.

</details>

<details>
<summary><b>Is it safe to edit the <code>.desktop</code> file manually?</b></summary>

Yes, but re-running `autorun.py` will overwrite it.

</details>

<details>
<summary><b>Where does the "program" actually run from?</b></summary>

Always from `~/Visible-Background-Process/`, **never** from its original location. This means relative paths inside your script resolve relative to that folder.

</details>

<details>
<summary><b>What Python interpreter is used?</b></summary>

Whatever `sys.executable` points to when you run `autorun.py`. If you use a virtualenv, the venv's Python is used. On Windows, the `.exe` is swapped between `python.exe` and `pythonw.exe` as needed.

</details>

---

## 🤖 Prompt for Future Updates

OSes evolve. When Windows 12 ships, or when Fedora changes its default terminal again, paste the block below into any AI agent along with this file.

<details>
<summary><b>📋 Click to expand the full prompt</b></summary>

```text
You are a senior cross-platform systems engineer. Update the provided `autorun.py` script so it remains fully compatible with the latest documented behavior of ALL of the following operating systems:

**Windows:** Windows 10 (all supported builds), Windows 11 (including 23H2, 24H2, and 25H2), and any confirmed successor (e.g., Windows 12 — if it has shipped, otherwise explicitly state that it has not and skip it).

**Linux distributions:** Arch Linux, Omarchy Linux, Ubuntu (LTS + interim), Kali Linux, Linux Mint (Cinnamon, XFCE, MATE), Fedora Workstation, Pop!_OS (GNOME + COSMIC), Zorin OS, and any other major Debian/Ubuntu/Fedora/Arch derivative that uses the XDG Autostart specification.

### What the script must do (unchanged behavior)
1. `python autorun.py myprogram.py` → copies `myprogram.py` into `~/Visible-Background-Process/`, installs an autostart entry that runs the copy **visibly** on every reboot/login.
2. `python autorun.py myprogram.py --hide` → same copy, but runs **silently in the background** on every reboot/login.
3. `python autorun.py myprogram.py --stop` → kills the running copy, removes the autostart entry, and deletes the copy permanently.
4. Manual kill (Task Manager / `kill`) must only stop the current session; the autostart entry must survive so the program returns on next login.

### Windows-specific rules (must be preserved)
- `.py` input without `--hide` → saved as `.py`, run with `python.exe` (visible console), task created with `/SC ONLOGON /IT`.
- `.pyw` input OR `--hide` → saved as `.pyw`, run with `pythonw.exe`, **no console window**, task created with `/SC ONLOGON /IT`.
- Hidden subprocess flags must be `CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_BREAKAWAY_FROM_JOB` and **must NOT include `DETACHED_PROCESS`** because MSDN documents that `CREATE_NO_WINDOW` is ignored when combined with `DETACHED_PROCESS`.
- For Windows 11 build ≥ 26100 (25H2), add a short `timeout /t 5 /nobreak >nul &&` delay at the start of the task action to account for "Delayed Desktop Initialization."
- `--stop` must work regardless of whether the original argument was `.py` or `.pyw`; use the sanitized base name to locate the copy.

### Linux-specific rules (must be preserved)
- Use `~/.config/autostart/<name>.desktop` for user-level autostart.
- **Always** wrap `Exec=` in `sh -c 'cd "<copy_dir>" && …'` because XFCE and KDE Plasma ignore the `Path=` key in autostart `.desktop` files.
- Hidden mode must use `subprocess.Popen` with `stdout=DEVNULL`, `stderr=DEVNULL`, `start_new_session=True`, and `cwd=copy_dir`.
- Visible mode must try terminal emulators in this order: `xdg-terminal-exec` (Omarchy / modern systems), `x-terminal-emulator` (Debian alternatives), `ptyxis` (Pop!_OS 24.04+ / GNOME 47+), `kgx` (GNOME Console), `gnome-terminal`, `konsole`, `xfce4-terminal`, `ghostty`, `foot`, `xterm`.
- If no terminal is found, launch detached and print a warning (do not fail silently).

### How to update
1. **Search** the latest official documentation for each OS:
   - Microsoft Learn: `schtasks` syntax, `/IT` flag, session-0 isolation, Windows 11 25H2 desktop-init behavior.
   - freedesktop.org: XDG Autostart Specification (current version).
   - XFCE Bugzilla / KDE Bugzilla: status of `Path=` key support in autostart entries.
   - Omarchy docs / GitHub: `xdg-terminal-exec` behavior and default terminal list.
   - Pop!_OS / Fedora / Ubuntu release notes: default terminal emulator changes (e.g., `ptyxis`, `kgx`).
   - Python docs: `subprocess` `creationflags` on Windows (current stable Python).
2. **Compare** each documented behavior against the current script.
3. **Fix** every mismatch, deprecated flag, or newly documented bug.
4. **Preserve** the original feature set and CLI contract exactly.
5. **Return** the complete corrected script, followed by a table of every bug found and the fix applied.

Do not add features that were not requested. Do not change the file-naming rules (`.py` vs `.pyw`) on Windows or the `--hide` semantics. If an OS has no confirmed changes, state that explicitly rather than guessing.
```

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
