"""ANSI art rendering and terminal menu helpers."""

from pathlib import Path

import config

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
WHITE = "\033[1;37m"
DIM = "\033[2m"
CLEAR = "\033[2J\033[H"
RED = "\033[31m"


def load_ansi(name: str) -> str:
    """Load an .ans file from the ansi_art directory.

    Converts literal \\033 sequences to real ESC bytes so .ans files
    can be edited as plain text.
    """
    path = config.BASE_DIR / "ansi_art" / f"{name}.ans"
    if path.exists():
        text = path.read_text()
        return text.replace("\\033", "\033")
    return ""


def box(title: str, lines: list[str], width: int = 60) -> str:
    """Draw a bordered box around content."""
    out = [f"{CYAN}┌{'─' * (width - 2)}┐{RESET}"]
    padded_title = f" {title} "
    left = (width - 2 - len(padded_title)) // 2
    right = width - 2 - left - len(padded_title)
    out.append(f"{CYAN}│{'─' * left}{WHITE}{padded_title}{CYAN}{'─' * right}│{RESET}")
    out.append(f"{CYAN}├{'─' * (width - 2)}┤{RESET}")
    for line in lines:
        visible_len = len(strip_ansi(line))
        pad = width - 2 - visible_len
        if pad < 0:
            pad = 0
        out.append(f"{CYAN}│{RESET} {line}{' ' * (pad - 1)}{CYAN}│{RESET}")
    out.append(f"{CYAN}└{'─' * (width - 2)}┘{RESET}")
    return "\r\n".join(out)


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences for length calculation."""
    import re
    return re.sub(r'\033\[[0-9;]*m', '', text)


def menu_item(key: str, label: str) -> str:
    return f"  {YELLOW}[{key}]{RESET}  {label}"


def prompt(text: str = "Command") -> str:
    return f"\r\n{GREEN}{text}: {RESET}"


def header(text: str) -> str:
    return f"\r\n{WHITE}{BOLD}  {text}{RESET}\r\n"


def error(text: str) -> str:
    return f"{RED}{text}{RESET}"


def success(text: str) -> str:
    return f"{GREEN}{text}{RESET}"


def table_row(cols: list[str], widths: list[int]) -> str:
    parts = []
    for col, w in zip(cols, widths):
        visible = strip_ansi(col)
        pad = w - len(visible)
        if pad < 0:
            pad = 0
        parts.append(col + " " * pad)
    return "  ".join(parts)
