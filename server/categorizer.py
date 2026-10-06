"""Automatic activity categorizer and productivity rule engine."""

from __future__ import annotations

from typing import Tuple

DEV_PROCESSES = {
    "code.exe",
    "cursor.exe",
    "idea64.exe",
    "pycharm64.exe",
    "clion64.exe",
    "webstorm64.exe",
    "rider64.exe",
    "datagrip64.exe",
    "goland64.exe",
    "rustrover64.exe",
    "phpstorm64.exe",
    "rubymine64.exe",
    "androidstudio64.exe",
    "studio64.exe",
    "eclipse.exe",
    "devenv.exe",
    "sublime_text.exe",
    "notepad++.exe",
    "windowsterminal.exe",
    "wt.exe",
    "powershell.exe",
    "pwsh.exe",
    "cmd.exe",
    "git-bash.exe",
    "bash.exe",
    "wsl.exe",
    "alacritty.exe",
    "neovim.exe",
    "vim.exe",
    "python.exe",
    "py.exe",
    "node.exe",
    "postman.exe",
    "insomnia.exe",
    "dbeaver.exe",
    "pgadmin4.exe",
    "docker.exe",
}

COMM_PROCESSES = {
    "slack.exe",
    "teams.exe",
    "ms-teams.exe",
    "discord.exe",
    "telegram.exe",
    "zoom.exe",
    "skype.exe",
    "outlook.exe",
    "thunderbird.exe",
    "whatsapp.exe",
    "signal.exe",
    "zalo.exe",
    "wechat.exe",
    "mattermost.exe",
    "line.exe",
}

BROWSER_PROCESSES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
}

OFFICE_PROCESSES = {
    "winword.exe",
    "excel.exe",
    "powerpnt.exe",
    "notion.exe",
    "obsidian.exe",
    "onenote.exe",
    "acrobat.exe",
    "acrord32.exe",
    "wps.exe",
    "et.exe",
    "wpp.exe",
    "foxitreader.exe",
    "foxitpdfreader.exe",
}

DESIGN_MEDIA_PROCESSES = {
    "photoshop.exe",
    "figma.exe",
    "illustrator.exe",
    "premiere.exe",
    "afterfx.exe",
    "blender.exe",
    "spotify.exe",
    "vlc.exe",
    "gimp.exe",
    "inkscape.exe",
    "canva.exe",
    "obs64.exe",
    "resolve.exe",
    "lightroom.exe",
}

SYSTEM_PROCESSES = {
    "explorer.exe",
    "taskmgr.exe",
    "systemsettings.exe",
    "regedit.exe",
    "control.exe",
}


def classify_activity(
    process_name: str,
    window_title: str,
    is_idle: bool,
    existing_category: str = "",
) -> str:
    """
    Classify an activity into a productivity category based on process name and window title.
    """
    if is_idle or process_name.lower() == "idle":
        return "Idle / Away"

    if existing_category and existing_category not in ("Uncategorized", ""):
        return existing_category

    proc = (process_name or "").lower()
    title = (window_title or "").lower()

    if "[private" in proc or "[private" in title:
        return "Privacy / Ignored"

    # Browser contextual routing based on window title
    if proc in BROWSER_PROCESSES:
        if any(w in title for w in ["github", "gitlab", "stackoverflow", "stack overflow", "pull request", "commit"]):
            return "Development"
        if any(w in title for w in ["gmail", "outlook", "mail", "inbox", "slack", "discord"]):
            return "Communication"
        if any(w in title for w in ["google docs", "google sheets", "google slides", "notion", "coda"]):
            return "Productivity & Office"
        if any(w in title for w in ["youtube", "netflix", "spotify", "twitch"]):
            return "Design & Media"
        return "Browsing"

    if proc in DEV_PROCESSES:
        return "Development"

    if proc in COMM_PROCESSES:
        return "Communication"

    if proc in OFFICE_PROCESSES:
        return "Productivity & Office"

    if proc in DESIGN_MEDIA_PROCESSES:
        return "Design & Media"

    if proc in SYSTEM_PROCESSES:
        return "System & Utilities"

    return "Other"


def format_duration(seconds: float) -> str:
    """Convert duration in seconds into a friendly human-readable format."""
    total_secs = int(round(seconds))
    if total_secs < 0:
        total_secs = 0

    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60

    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    elif minutes > 0:
        return f"{minutes}m {secs:02d}s"
    else:
        return f"{secs}s"
