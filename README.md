# 🚀 autorun.py

> Cross-platform Python script installer that survives reboots on **Linux** and **Windows** — run any `.py` script **visibly** or **silently in the background** every time the system starts.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/Linux-Arch%20%7C%20Fedora%20%7C%20Ubuntu%20%7C%20Kali%20%7C%20Mint%20%7C%20Pop!__OS%20%7C%20Omarchy%20%7C%20Zorin-orange)](https://www.kernel.org/)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-blue)](https://www.microsoft.com/windows)

---

## 📑 Table of Contents

- [Why autorun.py?](#-why-autorunpy)
- [Features](#-features)
- [Supported Operating Systems](#-supported-operating-systems)
- [Installation](#-installation)
- [Usage](#-usage)
- [Behavior Matrix](#-behavior-matrix)
- [How It Works](#-how-it-works)
  - [Windows](#windows)
  - [Linux](#linux)
- [Uninstalling](#-uninstalling)
- [File Layout](#-file-layout)
- [Troubleshooting](#-troubleshooting)
- [FAQ](#-faq)
- [Prompt for Future Updates](#-prompt-for-future-updates)
- [License](#-license)

---

## 🤔 Why autorun.py?

You wrote a Python script — a bot, a watcher, a server, a monitor — and you want it to **start automatically whenever the machine boots**, on **both Linux and Windows**, with **one command**, without touching systemd, Task Scheduler, or `.desktop` files by hand.

`autorun.py` does exactly that:

```bash
python autorun.py myprogram.py            # visible, survives reboot
python autorun.py myprogram.py --hide     # silent, survives reboot
python autorun.py myprogram.py --stop     # remove permanently
