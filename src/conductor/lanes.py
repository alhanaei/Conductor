"""Phase 3 tmux lane adapter: targets, provider registry, classifier, adapter.

Layering:

* :func:`parse_target` / :func:`escape_target` — pure target handling.
* :data:`PROVIDERS` — provider profiles holding the *only* place provider-specific
  readiness patterns live (the "adapter edge").
* :func:`classify` — a pure, deterministic function
  ``(transcript, profile, session_exists) -> LaneState``. Fully unit-testable.
* :class:`LaneAdapter` — orchestrates tmux + store: ensure/status/capture/submit,
  persisting a :class:`LaneRecord` and emitting delivery/heartbeat events.

Safety is the headline behavior: ``submit`` refuses to send into anything that
is not ``provider_ready`` (no pasting work into a bare shell).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .models import LaneRecord, LaneState, utc_now_iso
from .store import ConductorStore, atomic_write_text
from .tmux import TmuxClient


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class LaneError(RuntimeError):
    """Raised on invalid lane operations (bad target, unsafe submit, etc.)."""


# --------------------------------------------------------------------------- #
# Target parsing
# --------------------------------------------------------------------------- #
@dataclass
class LaneTarget:
    raw: str
    session: str   # session / project segment
    window: str    # window / provider segment
    provider: Optional[str] = None


def parse_target(raw: str) -> LaneTarget:
    """Parse ``session:window`` / ``project:provider`` into a :class:`LaneTarget`.

    Exactly one ``:`` separator is expected; both segments must be non-empty.
    The window segment doubles as the provider name when it matches a known
    provider profile.
    """
    if raw is None or not isinstance(raw, str) or raw.strip() == "":
        raise LaneError("lane target is required (expected 'session:window')")
    if raw.count(":") != 1:
        raise LaneError(
            f"invalid lane target {raw!r}; expected exactly one ':' as in 'session:window'"
        )
    session, window = raw.split(":", 1)
    session, window = session.strip(), window.strip()
    if not session or not window:
        raise LaneError(
            f"invalid lane target {raw!r}; both session and window must be non-empty"
        )
    provider = _provider_from_window(window)
    return LaneTarget(raw=raw, session=session, window=window, provider=provider)


def _provider_from_window(window: str) -> Optional[str]:
    """Resolve the provider from a window name, honoring pool suffixes.

    Lane-pool windows are named ``<provider>-<n>`` (``claude-2``, ``codex-3``);
    they still classify with the base provider's profile.
    """
    name = window.lower()
    if name in PROVIDERS:
        return name
    base, sep, suffix = name.rpartition("-")
    if sep and suffix.isdigit() and base in PROVIDERS:
        return base
    return None


_ESCAPE_RE = re.compile(r"[^A-Za-z0-9_.-]")


def escape_target(raw: str) -> str:
    """Map a raw target to a stable, filesystem-safe id (e.g. ``Conductor_claude``)."""
    return _ESCAPE_RE.sub("_", raw)


# --------------------------------------------------------------------------- #
# Provider registry (adapter edge — provider quirks live here, not in classify)
# --------------------------------------------------------------------------- #
@dataclass
class ProviderProfile:
    name: str
    ready_patterns: List[str] = field(default_factory=list)
    busy_patterns: List[str] = field(default_factory=list)
    blocked_patterns: List[str] = field(default_factory=list)
    # How to start this provider's CLI in a bare shell pane (argv, no shell string).
    launch_command: List[str] = field(default_factory=list)
    # CLI flag used to select a model, if the provider supports one.
    model_flag: Optional[str] = None


# Generic patterns shared across providers. Substring match on lowercased text.
# Keep these scoped to *live prompt text* in classify(); broad words such as
# "approval" or "trust" can appear in completed assistant output and must not
# poison readiness from stale scrollback.
_GENERIC_BLOCKED = [
    "do you want", "y/n", "[y/n]", "(y/n)", "yes/no", "(yes/no)", "proceed?",
    "permission to", "grant access", "allow this", "do you trust",
    "press enter to continue", "overwrite?",
    "1. yes", "❯ 1.", "would you like to proceed", "continue? (",
    "would you like to make", "press enter to confirm",
]
_AUTH_BLOCKED = [
    "authenticate", "authentication", "please log in", "please login",
    "log in", "sign in",
]
_GENERIC_BUSY = [
    "esc to interrupt", "thinking", "working…", "working...", "generating",
    "incubating", "processing", "compiling", "please wait", "running command",
    "executing", "tool call", "⏳", "running…",
]
# Shell prompt: last non-empty line ends in $ / # / % (optionally trailing space),
# or a bare prompt symbol — without any provider UI markers present.
_SHELL_LAST_LINE_RE = re.compile(r"(?:[#$%]|➜|»)\s*$")
_SHELL_HINTS = ["bash-", "zsh", "$ ", "# ", "~$", "@", "sh-"]


PROVIDERS: Dict[str, ProviderProfile] = {
    "claude": ProviderProfile(
        name="claude",
        ready_patterns=["? for shortcuts", "claude code", "welcome to claude", "│ >",
                        "⏵⏵ auto mode", "← for agents"],
        busy_patterns=["esc to interrupt", "thinking"],
        blocked_patterns=["do you want to make this edit", "do you want to proceed",
                          "1. yes", "press enter to confirm"],
        launch_command=["claude"],
        model_flag="--model",
    ),
    "codex": ProviderProfile(
        name="codex",
        ready_patterns=["codex", "codex>", "/status", "send a message"],
        busy_patterns=["esc to interrupt", "thinking", "working"],
        blocked_patterns=["allow command", "y/n", "do you want", "press enter to confirm"],
        launch_command=["codex"],
        model_flag="--model",
    ),
    "gemini": ProviderProfile(
        name="gemini",
        ready_patterns=["gemini", "gemini>", "type your message"],
        busy_patterns=["esc to cancel", "thinking", "loading"],
        blocked_patterns=["y/n", "do you want", "authorize", "press enter to confirm"],
        launch_command=["gemini"],
        model_flag="--model",
    ),
    "grok": ProviderProfile(
        name="grok",
        ready_patterns=["grok", "grok>", "ask grok"],
        busy_patterns=["thinking", "working", "esc to interrupt"],
        blocked_patterns=["y/n", "do you want", "press enter to confirm"],
        launch_command=["grok"],
        model_flag="--model",
    ),
}

# Tiered lane-model policy, keyed by provider then method id (see methods.py).
# Only claude ships defaults: demanding long-horizon work gets Fable 5,
# scoped/mechanical work gets Sonnet. Codex/gemini/grok model lineups move
# fast and their CLIs have their own configured defaults, so they launch bare
# unless configured — set per-provider maps in conductor.json:
#   {"lane_models": {"claude": {"build": "..."}, "codex": {"default": "..."}}}
# (A flat map {"build": "..."} is also accepted and treated as the claude map.)
DEFAULT_LANE_MODELS: Dict[str, Dict[str, str]] = {
    "claude": {
        "spec": "claude-sonnet-4-6",
        "plan": "claude-fable-5",
        "build": "claude-fable-5",
        "test": "claude-sonnet-4-6",
        "review": "claude-fable-5",
        "ship": "claude-opus-4-8",
        "default": "claude-opus-4-8",
    },
}


def resolve_lane_model(provider: Optional[str], method: Optional[str] = None,
                       config: Optional[Dict] = None) -> Optional[str]:
    """Resolve the launch model for ``provider`` from tier policy + config.

    Returns ``None`` when no policy applies (launch the provider CLI bare and
    let it use its own configured default). Config overrides merge over the
    defaults; a flat ``lane_models`` map is treated as the claude map for
    backward compatibility.
    """
    if not provider:
        return None
    provider = provider.lower()
    models = dict(DEFAULT_LANE_MODELS.get(provider, {}))

    override = (config or {}).get("lane_models") or {}
    if isinstance(override, dict):
        if any(isinstance(v, dict) for v in override.values()):
            # Nested per-provider form.
            provider_override = override.get(provider) or {}
        else:
            # Legacy flat form applies to claude only.
            provider_override = override if provider == "claude" else {}
        if isinstance(provider_override, dict):
            models.update({k: str(v) for k, v in provider_override.items()
                           if isinstance(v, str)})

    if method and method in models:
        return models[method]
    return models.get("default")

# Future extension points; not yet classified specially.
FUTURE_PROVIDERS = ["cursor", "opencode"]

_GENERIC_PROFILE = ProviderProfile(name="generic")


def provider_profile(name: Optional[str]) -> ProviderProfile:
    if name and name.lower() in PROVIDERS:
        return PROVIDERS[name.lower()]
    return _GENERIC_PROFILE


# --------------------------------------------------------------------------- #
# Classifier (pure / deterministic)
# --------------------------------------------------------------------------- #
def _matches_any(text: str, patterns: List[str]) -> bool:
    return any(p in text for p in patterns)


def _tail_text(transcript: str, lines: int = 40) -> str:
    """Return recent pane text used for prompt-state decisions.

    tmux capture includes scrollback. A completed worker response may contain
    ordinary words like "approval", "trustworthy", or copied task text that look
    like blocker phrases even though the live provider prompt is ready. Prompt
    blockers/busy spinners should therefore be detected from the recent visible
    tail, not the full historical transcript.
    """
    parts = transcript.splitlines()
    return "\n".join(parts[-lines:]) if parts else ""


def _looks_like_shell(transcript: str) -> bool:
    lines = [ln for ln in transcript.splitlines() if ln.strip()]
    if not lines:
        return False
    last = lines[-1]
    if _SHELL_LAST_LINE_RE.search(last):
        return True
    low = last.lower()
    return any(h in low for h in _SHELL_HINTS) and _SHELL_LAST_LINE_RE.search(last) is not None


def classify(transcript: str, profile: ProviderProfile,
             session_exists: bool = True) -> LaneState:
    """Classify pane state. Precedence: absent > blocked > busy > ready > shell > unknown.

    Blocked is checked before busy/ready because an approval prompt often also
    contains provider UI; an operator action must win.
    """
    if not session_exists:
        return LaneState.ABSENT

    text = transcript.lower()
    tail = _tail_text(transcript).lower()

    blocked = _GENERIC_BLOCKED + profile.blocked_patterns
    if _matches_any(tail, [p.lower() for p in blocked]):
        return LaneState.BLOCKED_PROMPT

    ready = _matches_any(text, [p.lower() for p in profile.ready_patterns])
    auth_blocked = _matches_any(tail, [p.lower() for p in _AUTH_BLOCKED])
    if auth_blocked and not ready:
        return LaneState.BLOCKED_PROMPT

    busy = _GENERIC_BUSY + profile.busy_patterns
    if _matches_any(tail, [p.lower() for p in busy]):
        return LaneState.BUSY

    if ready:
        return LaneState.PROVIDER_READY

    if _looks_like_shell(transcript):
        return LaneState.SHELL

    return LaneState.UNKNOWN


# Readiness states from which it is safe to submit an instruction.
_SUBMITTABLE = {LaneState.PROVIDER_READY}

SUBMIT_INSTRUCTION_TEMPLATE = (
    "Read {task_file} and execute it. Write result artifacts when done."
)

# Some full-screen TUIs need a short render tick after literal text is pasted
# before Enter is interpreted as submit. Codex has shown this in live tmux: the
# instruction appears at the prompt, but the immediate Enter can be swallowed
# until an operator presses Enter again. Keep the delay provider-scoped so Claude
# and other lanes retain their fast path.
SUBMIT_ENTER_DELAY_SECONDS = {
    "codex": 0.5,
}


# --------------------------------------------------------------------------- #
# Lane adapter
# --------------------------------------------------------------------------- #
class LaneAdapter:
    def __init__(self, store: ConductorStore, tmux: Optional[TmuxClient] = None):
        self.store = store
        self.tmux = tmux if tmux is not None else TmuxClient()

    def _send_instruction_to_tmux(self, tgt: LaneTarget, instruction: str) -> bool:
        """Send text then submit it, honoring provider-specific TUI timing."""
        if not self.tmux.send_text(tgt.raw, instruction):
            return False
        delay = SUBMIT_ENTER_DELAY_SECONDS.get((tgt.provider or "").lower(), 0.0)
        if delay > 0:
            time.sleep(delay)
        return self.tmux.send_enter(tgt.raw)

    # -- persistence -------------------------------------------------------- #
    def _record_path(self, target_raw: str) -> Path:
        return self.store.lanes_dir / f"{escape_target(target_raw)}.json"

    def _load_or_new(self, tgt: LaneTarget) -> LaneRecord:
        existing = self.store.read_lane_record_path(self._record_path(tgt.raw))
        if existing is not None:
            return existing
        return LaneRecord(
            target=tgt.raw, session=tgt.session, window=tgt.window, provider=tgt.provider,
        )

    def _persist(self, record: LaneRecord) -> None:
        record.updated_at = utc_now_iso()
        self.store.write_lane_record(self._record_path(record.target), record)

    # -- classification helper --------------------------------------------- #
    def _classify_live(self, tgt: LaneTarget, lines: int = 200) -> Tuple[LaneState, str, bool]:
        """Return ``(state, transcript, tmux_available)`` from a live capture."""
        if not self.tmux.available():
            return LaneState.ABSENT, "", False
        ok, text = self.tmux.capture(tgt.raw, lines=lines)
        if not ok:
            return LaneState.ABSENT, "", True
        state = classify(text, provider_profile(tgt.provider), session_exists=True)
        return state, text, True

    # -- public API --------------------------------------------------------- #
    def ensure(self, target_raw: str) -> Dict[str, Any]:
        tgt = parse_target(target_raw)
        record = self._load_or_new(tgt)
        now = utc_now_iso()

        if not self.tmux.available():
            record.tmux_available = False
            record.state = LaneState.ABSENT
            record.last_heartbeat_at = now
            self._persist(record)
            raise LaneError(
                "tmux is not available on this host; cannot ensure lane "
                f"{target_raw!r}. Install tmux or run on the tmux host."
            )

        created = self.tmux.ensure(tgt.session, tgt.window)
        if not created:
            record.tmux_available = True
            self._persist(record)
            raise LaneError(f"failed to ensure tmux lane {target_raw!r}")

        state, _, _ = self._classify_live(tgt)
        record.tmux_available = True
        record.state = state
        record.last_classified_at = now
        record.last_heartbeat_at = now
        record.last_event = {"event": "lane_ensured", "at": now}
        self._persist(record)
        self.store.append_event({"event": "lane_ensured", "target": tgt.raw,
                                 "state": state.value})
        return self._status_dict(record, note="lane ensured (shell window; provider not launched)")

    def launch(self, target_raw: str, model: Optional[str] = None,
               wait_seconds: float = 15.0, poll: float = 1.0) -> Dict[str, Any]:
        """Start the provider CLI in a bare shell pane (e.g. ``claude --model ...``).

        Safety gate mirrors submit: the launch command is only ever typed into a
        pane classified ``shell``. A ``provider_ready`` lane returns success
        without relaunching; ``busy``/``blocked_prompt``/``unknown``/``absent``
        refuse — never inject text into a pane in an unknown state.
        """
        import shlex
        import time

        tgt = parse_target(target_raw)
        profile = provider_profile(tgt.provider)
        if not profile.launch_command:
            raise LaneError(
                f"no launch command known for provider {tgt.provider!r} "
                f"(window {tgt.window!r}); launch it manually in the pane"
            )
        if model and not profile.model_flag:
            raise LaneError(
                f"provider {profile.name!r} does not support model selection via "
                f"conductor; launch without --model or start it manually"
            )

        record = self._load_or_new(tgt)
        now = utc_now_iso()
        state, _, available = self._classify_live(tgt)
        record.state = state
        record.tmux_available = available
        record.last_classified_at = now
        record.last_heartbeat_at = now

        if state is LaneState.PROVIDER_READY:
            self._persist(record)
            return {**self._status_dict(record), "launched": False,
                    "note": "provider already running; not relaunching"}
        if state is not LaneState.SHELL:
            record.last_event = {"event": "launch_refused", "state": state.value, "at": now}
            self._persist(record)
            raise LaneError(
                f"refusing to launch into lane {target_raw!r}: state is "
                f"{state.value!r}, not 'shell'. Only a bare shell pane accepts a "
                f"launch command."
            )

        argv = list(profile.launch_command)
        if model:
            argv += [profile.model_flag, model]
        command = shlex.join(argv)
        sent = self.tmux.send_text(tgt.raw, command) and self.tmux.send_enter(tgt.raw)
        if not sent:
            raise LaneError(f"failed to send launch command to lane {target_raw!r}")

        record.model = model
        record.last_event = {"event": "lane_launched", "command": command, "at": now}
        self._persist(record)
        self.store.append_event({"event": "lane_launched", "target": tgt.raw,
                                 "command": command, "model": model})

        # Wait for the provider UI to come up (bounded, classifier-driven).
        deadline = time.monotonic() + max(0.0, wait_seconds)
        final_state = state
        while True:
            final_state, _, _ = self._classify_live(tgt)
            if final_state in (LaneState.PROVIDER_READY, LaneState.BLOCKED_PROMPT):
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(max(0.05, poll))
        record.state = final_state
        record.last_classified_at = utc_now_iso()
        self._persist(record)

        return {**self._status_dict(record), "launched": True, "command": command,
                "model": model,
                "note": ("provider ready" if final_state is LaneState.PROVIDER_READY
                         else f"launched; lane state is {final_state.value} "
                              "(may still be starting or waiting on a prompt)")}

    def status(self, target_raw: str) -> Dict[str, Any]:
        tgt = parse_target(target_raw)
        record = self._load_or_new(tgt)
        state, _, available = self._classify_live(tgt)
        now = utc_now_iso()
        record.state = state
        record.tmux_available = available
        record.last_classified_at = now
        record.last_heartbeat_at = now
        self._persist(record)
        return self._status_dict(record)

    def capture(self, target_raw: str, lines: int = 200) -> Dict[str, Any]:
        tgt = parse_target(target_raw)
        record = self._load_or_new(tgt)
        now = utc_now_iso()

        state, transcript, available = self._classify_live(tgt, lines=lines)
        line_count = len(transcript.splitlines()) if transcript else 0

        transcript_ref = None
        if transcript:
            transcript_ref = str(self.store.lanes_dir /
                                 f"{escape_target(tgt.raw)}.transcript.txt")
            atomic_write_text(Path(transcript_ref), transcript)

        record.state = state
        record.tmux_available = available
        record.last_line_count = line_count
        record.last_transcript_ref = transcript_ref
        record.last_capture_at = now
        record.last_classified_at = now
        record.last_heartbeat_at = now
        self._persist(record)

        result = self._status_dict(record)
        result.update({
            "captured_at": now,
            "line_count": line_count,
            "transcript": transcript,
            "transcript_ref": transcript_ref,
        })
        return result

    def submit(self, target_raw: str, task_file: str, force: bool = False) -> Dict[str, Any]:
        """Submit a short artifact-reference instruction. Safe by default.

        Refuses unless readiness is ``provider_ready`` (or ``force=True``). Never
        pastes the task file body — only its path is referenced.
        """
        tgt = parse_target(target_raw)
        record = self._load_or_new(tgt)
        now = utc_now_iso()

        state, _, available = self._classify_live(tgt)
        record.state = state
        record.tmux_available = available
        record.last_classified_at = now
        record.last_heartbeat_at = now

        if not force and state not in _SUBMITTABLE:
            record.last_event = {"event": "submit_refused", "state": state.value, "at": now}
            self._persist(record)
            self.store.append_event({"event": "lane_submit_refused", "target": tgt.raw,
                                     "state": state.value})
            raise LaneError(
                f"refusing to submit to lane {target_raw!r}: readiness is {state.value!r}, "
                f"not 'provider_ready'. This prevents pasting work into a shell/busy/blocked "
                f"pane. Use --force only if you are certain."
            )

        # Validate the artifact exists (we reference its path, never its body).
        task_path = Path(task_file)
        if not task_path.exists():
            record.last_event = {"event": "submit_failed", "reason": "task_file_missing", "at": now}
            self._persist(record)
            raise LaneError(f"task file not found: {task_file}")

        instruction = SUBMIT_INSTRUCTION_TEMPLATE.format(task_file=str(task_path))
        sent = self._send_instruction_to_tmux(tgt, instruction)
        if not sent:
            record.last_event = {"event": "submit_failed", "reason": "tmux_send_failed", "at": now}
            self._persist(record)
            raise LaneError(f"failed to send instruction to lane {target_raw!r}")

        event = {"event": "lane_submit", "target": tgt.raw, "task_file": str(task_path),
                 "instruction": instruction, "forced": force, "at": now}
        record.last_submit_at = now
        record.last_event = event
        self._persist(record)
        self.store.append_event(event)
        return {
            "ok": True,
            "submitted": True,
            "target": tgt.raw,
            "state": state.value,
            "forced": force,
            "task_file": str(task_path),
            "instruction": instruction,
            "submitted_at": now,
        }

    def send_instruction(self, target_raw: str, instruction: str,
                         force: bool = False, kind: str = "lane_instruction") -> Dict[str, Any]:
        """Send a short, caller-built instruction behind the same readiness gate.

        Used by Phase 4 nudge/follow-up. Refuses unless ``provider_ready`` (or
        ``force``). The instruction must already be short (an artifact reference),
        not a pasted body — this method does not read any file.
        """
        if len(instruction) > 500:
            raise LaneError("instruction too long; pass an artifact reference, not a body")
        tgt = parse_target(target_raw)
        record = self._load_or_new(tgt)
        now = utc_now_iso()
        state, _, available = self._classify_live(tgt)
        record.state = state
        record.tmux_available = available
        record.last_classified_at = now
        record.last_heartbeat_at = now

        if not force and state not in _SUBMITTABLE:
            record.last_event = {"event": f"{kind}_pending", "state": state.value, "at": now}
            self._persist(record)
            raise LaneError(
                f"lane {target_raw!r} not ready (state={state.value!r}); instruction not sent"
            )

        sent = self._send_instruction_to_tmux(tgt, instruction)
        if not sent:
            raise LaneError(f"failed to send instruction to lane {target_raw!r}")
        event = {"event": kind, "target": tgt.raw, "instruction": instruction, "at": now}
        record.last_event = event
        self._persist(record)
        self.store.append_event(event)
        return {"ok": True, "sent": True, "target": tgt.raw, "state": state.value,
                "instruction": instruction, "sent_at": now}

    # -- shaping ------------------------------------------------------------ #
    def _status_dict(self, record: LaneRecord, note: Optional[str] = None) -> Dict[str, Any]:
        data = {
            "ok": True,
            "lane_id": record.lane_id,
            "target": record.target,
            "session": record.session,
            "window": record.window,
            "provider": record.provider,
            "state": record.state.value,
            "tmux_available": record.tmux_available,
            "current_task_id": record.current_task_id,
            "last_line_count": record.last_line_count,
            "last_transcript_ref": record.last_transcript_ref,
            "last_event": record.last_event,
            "last_classified_at": record.last_classified_at,
            "last_capture_at": record.last_capture_at,
            "last_submit_at": record.last_submit_at,
            "last_heartbeat_at": record.last_heartbeat_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "escaped_id": escape_target(record.target),
        }
        if note:
            data["note"] = note
        return data


def list_lane_status(store: ConductorStore) -> List[Dict[str, Any]]:
    """Read-only summary of all known lanes (used by `status`)."""
    out = []
    for record in store.list_lane_records():
        out.append({
            "target": record.target,
            "provider": record.provider,
            "state": record.state.value,
            "last_heartbeat_at": record.last_heartbeat_at,
            "updated_at": record.updated_at,
        })
    return out
