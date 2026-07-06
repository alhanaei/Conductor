"""Safe execution of configured verification commands (Phase 5+).

Verification stops being presence-only here: a task's ``verification_commands``
(real, executable commands — never the prose ``verification_requirements``) are
run by the conductor itself, and each becomes a deterministic check with exit
code and captured output evidence.

Safety posture:

* **Allowlist** — only commands whose first token (basename) is on the allowlist
  run at all. Defaults cover common test/build tools; a project can extend the
  list via ``conductor.json`` → ``"verification_allowed_commands": [...]``.
  A non-allowlisted command is a *failed check* with a clear reason, never a
  silent skip — refusing loudly keeps the gate honest.
* **No shell** — commands are ``shlex.split`` into argument arrays and executed
  with ``subprocess.run(list)``; shell metacharacters (``;``, ``|``, ``&&``,
  redirection) are rejected outright so a command string can never smuggle a
  second command.
* **Bounded** — per-command timeout (default 120s) and output captured to a tail
  so evidence stays readable.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ALLOWED_COMMANDS = frozenset({
    "python", "python3", "pytest",
    "npm", "pnpm", "yarn", "npx", "node",
    "go", "cargo", "make",
    "ruff", "mypy", "tox", "black", "flake8",
})

DEFAULT_TIMEOUT_SECONDS = 120
_OUTPUT_TAIL_CHARS = 2000
_SHELL_METACHARS = set(";|&<>`$")


def _output_tail(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= _OUTPUT_TAIL_CHARS:
        return text
    return "…" + text[-_OUTPUT_TAIL_CHARS:]


def _has_unquoted_metachar(command: str) -> bool:
    """True if a shell metacharacter appears outside quotes.

    Commands never touch a shell, so ``pytest && make`` would pass ``&&`` as a
    *literal argument* — almost certainly not what the author meant. Rejecting
    loudly beats confusing pass/fail semantics. Metacharacters inside quotes are
    fine (e.g. ``python -c 'import sys; sys.exit(0)'``) because quoting shows the
    author knows the text is a single argument.
    """
    quote = None
    for ch in command:
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch in _SHELL_METACHARS:
            return True
    return False


def run_verification_command(
    command: str,
    cwd: Path,
    allowlist: Optional[frozenset] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Run one configured command safely; return a check dict.

    The check shape matches the artifact-presence checks in the verification
    gate: ``{name, passed, detail, ...}`` plus ``exit_code`` and ``output_tail``
    evidence fields.
    """
    allowed = allowlist if allowlist is not None else DEFAULT_ALLOWED_COMMANDS
    base = {"name": "verification_command", "command": command}

    if _has_unquoted_metachar(command):
        return {**base, "passed": False, "exit_code": None,
                "detail": ("rejected: unquoted shell metacharacters are not allowed "
                           "(commands run without a shell; chaining/redirection would "
                           "not do what you expect)"),
                "output_tail": ""}
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return {**base, "passed": False, "exit_code": None,
                "detail": f"rejected: unparseable command ({exc})", "output_tail": ""}
    if not argv:
        return {**base, "passed": False, "exit_code": None,
                "detail": "rejected: empty command", "output_tail": ""}

    program = Path(argv[0]).name
    if program not in allowed:
        return {**base, "passed": False, "exit_code": None,
                "detail": (f"rejected: {program!r} is not on the verification allowlist; "
                           f"add it to conductor.json 'verification_allowed_commands' if intended"),
                "output_tail": ""}

    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {**base, "passed": False, "exit_code": None,
                "detail": f"timed out after {timeout}s", "output_tail": ""}
    except (OSError, subprocess.SubprocessError) as exc:
        return {**base, "passed": False, "exit_code": None,
                "detail": f"failed to execute: {exc}", "output_tail": ""}

    passed = proc.returncode == 0
    return {
        **base,
        "passed": passed,
        "exit_code": proc.returncode,
        "detail": f"exit {proc.returncode} (cwd={cwd})",
        "output_tail": _output_tail(proc.stdout + ("\n" + proc.stderr if proc.stderr else "")),
    }


def run_verification_commands(
    commands: List[str],
    cwd: Path,
    allowlist: Optional[frozenset] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> List[Dict[str, Any]]:
    """Run each configured command in order; every command yields one check."""
    return [run_verification_command(c, cwd, allowlist=allowlist, timeout=timeout)
            for c in commands]


def load_allowlist(config: Dict[str, Any]) -> frozenset:
    """Merge the default allowlist with ``verification_allowed_commands`` from config."""
    extra = config.get("verification_allowed_commands") or []
    return DEFAULT_ALLOWED_COMMANDS | frozenset(
        str(e) for e in extra if isinstance(e, str) and e.strip()
    )
