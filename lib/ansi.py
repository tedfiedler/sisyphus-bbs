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


def panel(title: str, lines: list[str], width: int = 0) -> str:
    """Draw a panel with = header and - separator, Mille Bornes style.

    Width auto-sizes to fit the longest line (min 40). Content is
    indented 2 spaces, so the bar extends 4 chars beyond the widest
    visible content.
    """
    # Auto-size: 2-space indent + content + 2-space right margin
    widest = len(title)
    for line in lines:
        vlen = len(strip_ansi(line))
        if vlen > widest:
            widest = vlen
    auto = widest + 4
    w = max(width, auto, 40)

    out = [f"{CYAN}{'=' * w}{RESET}"]
    out.append(f"  {WHITE}{BOLD}{title}{RESET}")
    out.append(f"{CYAN}{'=' * w}{RESET}")
    for line in lines:
        out.append(f"  {line}")
    out.append(f"{CYAN}{'-' * w}{RESET}")
    return "\r\n".join(out)


# Keep box() as alias for backwards compatibility
box = panel


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
