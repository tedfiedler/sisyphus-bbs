"""Keep the two dependency lists honest with each other and with the code."""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Import name -> distribution name, where they differ.
_DIST_NAMES = {"dotenv": "python-dotenv"}


def _name(requirement: str) -> str:
    return re.split(r"[<>=!~\[; ]", requirement.strip(), maxsplit=1)[0].lower()


def _pyproject() -> tuple[set[str], set[str]]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    runtime = {_name(r) for r in project["dependencies"]}
    dev = {_name(r) for r in project["optional-dependencies"]["dev"]}
    return runtime, dev


def _requirement_lines() -> list[str]:
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def test_requirements_are_exactly_pinned():
    for line in _requirement_lines():
        assert re.fullmatch(r"[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9.]*", line), line


def test_requirements_and_pyproject_name_the_same_packages():
    runtime, dev = _pyproject()
    assert {_name(l) for l in _requirement_lines()} == runtime | dev


def test_pyproject_dependencies_all_have_a_floor():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    for requirement in project["dependencies"]:
        assert ">=" in requirement, requirement


def test_every_third_party_import_is_declared():
    """A package the code imports but nobody declared only works by luck."""
    runtime, _ = _pyproject()
    imported = set()
    for folder in ("lib", "src", "admin"):
        for path in (ROOT / folder).rglob("*.py"):
            for match in re.finditer(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", path.read_text(), re.MULTILINE):
                imported.add(match.group(1))
    third_party = {
        _DIST_NAMES.get(name, name) for name in imported
        if name not in sys.stdlib_module_names and name not in ("lib", "src")
    }
    assert third_party <= runtime, third_party - runtime


def test_nothing_declared_is_left_over_from_removed_features():
    runtime, dev = _pyproject()
    assert "asyncssh" not in runtime | dev
    assert "SSH" not in (ROOT / "sisyphus.sh").read_text()
