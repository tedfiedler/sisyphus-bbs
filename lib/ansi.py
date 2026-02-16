"""ANSI art rendering and terminal menu helpers."""

from lib import config

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
    path = config.ANSI_ART_DIR / f"{name}.ans"
    if path.exists():
        text = path.read_text()
        return text.replace("\\033", "\033")
    return ""


def box(title: str, lines: list[str], width: int = 60) -> str:
    """Draw a bordered box around content."""
    inner = width - 2  # chars between the two │ borders
    out = [f"{CYAN}\u250c{'\u2500' * inner}\u2510{RESET}"]
    padded_title = f" {title} "
    left = (inner - len(padded_title)) // 2
    right = inner - left - len(padded_title)
    out.append(f"{CYAN}\u2502{'\u2500' * left}{WHITE}{padded_title}{CYAN}{'\u2500' * right}\u2502{RESET}")
    out.append(f"{CYAN}\u251c{'\u2500' * inner}\u2524{RESET}")
    for line in lines:
        visible_len = len(strip_ansi(line))
        # 1 leading space + content + trailing pad = inner chars
        pad = inner - 1 - visible_len
        if pad < 0:
            pad = 0
        out.append(f"{CYAN}\u2502{RESET} {line}{' ' * pad}{CYAN}\u2502{RESET}")
    out.append(f"{CYAN}\u2514{'\u2500' * inner}\u2518{RESET}")
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
