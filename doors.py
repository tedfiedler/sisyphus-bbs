import os
import asyncio
from pathlib import Path

import config


def generate_door32sys(
    comm_type: int = 0,
    comm_handle: int = 0,
    baud_rate: int = 115200,
    bbsid: str = "Sisyphus",
    user_id: int = 0,
    username: str = "Guest",
    time_left: int = 60,
) -> str:
    """Generate a DOOR32.SYS drop file for door games."""
    lines = [
        str(comm_type),     # Comm type (0=local)
        str(comm_handle),   # Comm/socket handle
        str(baud_rate),     # Baud rate
        bbsid,              # BBS ID
        str(user_id),       # User record position
        username,           # User's real name / alias
        username,           # User's alias
        str(time_left),     # Time left in minutes
        "1",                # Emulation (1=ANSI)
        "1",                # Current node number
    ]
    return "\n".join(lines) + "\n"


async def list_doors() -> list[dict]:
    """List configured door games from the doors directory."""
    doors_dir = config.BASE_DIR / "doors"
    doors_dir.mkdir(exist_ok=True)
    result = []
    for entry in sorted(doors_dir.iterdir()):
        if entry.is_dir():
            cfg_file = entry / "door.cfg"
            if cfg_file.exists():
                lines = cfg_file.read_text().strip().splitlines()
                name = lines[0] if lines else entry.name
                desc = lines[1] if len(lines) > 1 else ""
                cmd = lines[2] if len(lines) > 2 else ""
                result.append({
                    "id": entry.name,
                    "name": name,
                    "description": desc,
                    "command": cmd,
                    "path": str(entry),
                })
    return result


async def launch_door(
    door_id: str,
    user_id: int,
    username: str,
    stdin: asyncio.StreamReader | None = None,
    stdout: asyncio.StreamWriter | None = None,
) -> int:
    """Launch a door game, returning the exit code."""
    door_dir = config.BASE_DIR / "doors" / door_id
    cfg_file = door_dir / "door.cfg"
    if not cfg_file.exists():
        return -1

    lines = cfg_file.read_text().strip().splitlines()
    if len(lines) < 3:
        return -1

    command = lines[2]

    # Write drop file
    dropfile = door_dir / "DOOR32.SYS"
    dropfile.write_text(generate_door32sys(
        user_id=user_id,
        username=username,
    ))

    proc = await asyncio.create_subprocess_shell(
        command,
        cwd=str(door_dir),
        stdin=stdin if stdin else asyncio.subprocess.PIPE,
        stdout=stdout if stdout else asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.wait()
    return proc.returncode
