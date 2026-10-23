#!/usr/bin/env python3
"""Conductor task boundaries: ``start`` claims a readied task, ``finish`` closes it.

Python 3 standard library only. The helper writes only inside the checkout's Git
metadata (``<git-dir>/conductor-local/``): the claim, the verification evidence, the
checkpoint pointer and the drafted comment and pull-request bodies. It reads the task
record through ``--record FILE``, the ``gh`` CLI, or the GitHub REST API with a token
from GITHUB_TOKEN or GH_TOKEN, in that order. Posting the comment or opening the pull
request happens only with ``--post`` or ``--open`` and a working ``gh``; otherwise the
drafted text is left for the assistant to publish through its own authorized access.

Exit codes: 0 done; 2 task not ready or record unavailable; 3 claim conflict or missing
claim; 4 finish stopped (a check failed, the tree is dirty, or evidence does not match
HEAD); 5 evidence check failed; 6 Git or publishing command failed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

READY_LABEL = "status:ready"
LOCAL_DIR = "conductor-local"
CLAIM = "claim.json"
EVIDENCE = "verification.json"
CHECKPOINT = "checkpoint.md"
CLAIM_COMMENT = "claim-comment.md"
MILESTONE_COMMENT = "milestone-comment.md"
PR_BODY = "pr-body.md"
ALLOWED_HEADING = re.compile(r"^#{1,6}\s*allowed paths", re.I)


class BoundaryError(Exception):
    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.code = code


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise BoundaryError(f"git {' '.join(args)} failed: {result.stderr.strip()}", 6)
    return result.stdout.strip()


def repo_root(start: Path) -> Path:
    try:
        return Path(git(start, "rev-parse", "--show-toplevel"))
    except BoundaryError as error:
        raise BoundaryError(f"not inside a Git checkout: {error}", 6)


def local_dir(root: Path) -> Path:
    git_dir = Path(git(root, "rev-parse", "--git-dir"))
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    folder = git_dir / LOCAL_DIR
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def repo_slug(root: Path, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    url = git(root, "remote", "get-url", "origin", check=False)
    match = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?$", url)
    return match[1] if match else None


def normalize_record(data: dict) -> dict:
    labels = []
    for label in data.get("labels") or []:
        labels.append(label["name"] if isinstance(label, dict) else str(label))
    return {
        "number": int(data["number"]),
        "title": data.get("title") or "",
        "body": data.get("body") or "",
        "labels": labels,
        "state": data.get("state", "open"),
        "url": data.get("html_url") or data.get("url") or "",
    }


def fetch_record(number: int, repo: str | None, record_file: str | None) -> dict:
    if record_file:
        data = json.loads(Path(record_file).read_text())
        record = normalize_record(data)
        if record["number"] != number:
            raise BoundaryError(f"--record describes #{record['number']}, not #{number}", 2)
        return record
    if shutil.which("gh") and repo:
        result = subprocess.run(
            ["gh", "issue", "view", str(number), "--repo", repo,
             "--json", "number,title,body,labels,state,url"],
            capture_output=True, text=True)
        if result.returncode == 0:
            return normalize_record(json.loads(result.stdout))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and repo:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/issues/{number}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                     "User-Agent": "conductor-task-boundary"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return normalize_record(json.loads(response.read()))
        except (urllib.error.URLError, ValueError) as error:
            raise BoundaryError(f"GitHub API read of #{number} failed: {error}", 2)
    raise BoundaryError(
        f"no supported access to task #{number}: fetch the record with your own GitHub access "
        "and pass it as --record FILE (JSON with number, title, body, labels)", 2)


def allowed_paths(body: str) -> list[str]:
    """Backtick-quoted items under the record's 'Allowed paths' heading."""
    found: list[str] = []
    inside = False
    for line in body.splitlines():
        if re.match(r"^#{1,6}\s", line):
            inside = bool(ALLOWED_HEADING.match(line.strip()))
            continue
        if inside:
            for item in re.findall(r"`([^`\s]+)`", line):
                if ("/" in item or "." in item) and item not in found:  # paths, not words
                    found.append(item)
    return found


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:40].rstrip("-") or "task"


def always_on_lines(claim: dict) -> list[str]:
    paths = ", ".join(claim["allowed_paths"]) or "none recorded on the task; ask the owner"
    return [
        (f"Conductor task #{claim['task']} \"{claim['title']}\": role {claim['role']} on branch "
         f"{claim['branch']} from {claim['base']} at {claim['base_sha'][:12]}. Allowed paths: {paths}."),
        (f"Owner gates: never merge, push to {claim['base']}, rewrite history or apply {READY_LABEL}; "
         "anything found mid-task is proposed on its record, not done here."),
        (f"Finish with task-finish: the verification contract on the exact head into "
         f"{LOCAL_DIR}/{EVIDENCE}, a pull request with Closes #{claim['task']} and the ledger, the "
         "checkpoint pointer, and the milestone comment on the record."),
    ]


def claim_comment(claim: dict) -> str:
    paths = ", ".join(f"`{p}`" for p in claim["allowed_paths"]) or "none recorded"
    return (f"**Claim.** Task #{claim['task']} claimed by {claim['assistant']} as {claim['role']} "
            f"in {claim['runtime']} at {claim['claimed_at']}. Reference: {claim['reference']}. "
            f"Branch `{claim['branch']}` from `{claim['base']}` at `{claim['base_sha'][:12]}`. "
            f"Allowed paths: {paths}. The milestone is posted here by task-finish.")


def cmd_start(args: argparse.Namespace) -> int:
    root = repo_root(Path.cwd())
    folder = local_dir(root)
    claim_path = folder / CLAIM
    if claim_path.exists():
        existing = json.loads(claim_path.read_text())
        if existing.get("task") != args.number and not existing.get("finished_at"):
            raise BoundaryError(
                f"claim conflict: {claim_path} holds task #{existing.get('task')} on branch "
                f"{existing.get('branch')}; finish it (task-finish, --stopped if needed) first", 3)
    repo = repo_slug(root, args.repo)
    record = fetch_record(args.number, repo, args.record)
    if record["state"] != "open":
        raise BoundaryError(f"task #{args.number} is {record['state']}, not open", 2)
    if READY_LABEL not in record["labels"]:
        raise BoundaryError(
            f"task #{args.number} is not ready: label {READY_LABEL} is absent "
            f"(labels: {', '.join(record['labels']) or 'none'}). The owner applies it; do not start.", 2)

    base = args.base
    if not args.no_fetch:
        git(root, "fetch", "origin", base, check=False)
    base_ref = base
    if git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{base}", check=False):
        base_ref = f"origin/{base}"
    base_sha = git(root, "rev-parse", base_ref)
    current = git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    branch = args.branch or f"{args.assistant}/{slugify(record['title'])}-{dt.date.today():%Y%m%d}"
    if current != branch:
        if git(root, "status", "--porcelain", check=False):
            raise BoundaryError("working tree is not clean; commit or stash before branching", 6)
        if git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
            git(root, "checkout", branch)
        else:
            git(root, "checkout", "-b", branch, base_ref)

    claim = {
        "task": record["number"], "title": record["title"], "url": record["url"],
        "repository": repo, "role": args.role, "runtime": args.runtime,
        "reference": args.reference, "assistant": args.assistant,
        "claimed_at": now(), "branch": branch, "base": base, "base_sha": base_sha,
        "allowed_paths": allowed_paths(record["body"]), "labels": record["labels"],
    }
    claim["lines"] = always_on_lines(claim)
    claim_path.write_text(json.dumps(claim, indent=2) + "\n")
    comment = claim_comment(claim)
    (folder / CLAIM_COMMENT).write_text(comment + "\n")
    posted = False
    if args.post:
        posted = post_comment(repo, record["number"], comment)
    print("\n".join(claim["lines"]))
    print(f"\nClaim: {claim_path}")
    if posted:
        print(f"Claim comment posted on #{record['number']}.")
    else:
        print(f"Claim comment drafted at {folder / CLAIM_COMMENT}; post it on #{record['number']} "
              "with your GitHub access before changing anything.")
    return 0


def post_comment(repo: str | None, number: int, body: str) -> bool:
    if not (shutil.which("gh") and repo):
        return False
    result = subprocess.run(["gh", "issue", "comment", str(number), "--repo", repo, "--body", body],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise BoundaryError(f"gh issue comment failed: {result.stderr.strip()}", 6)
    return True


def parse_check(spec: str) -> tuple[str, str]:
    if "=" not in spec:
        raise BoundaryError(f"--check needs NAME=COMMAND, got {spec!r}", 6)
    name, command = spec.split("=", 1)
    return name.strip(), command.strip()


def run_checks(root: Path, specs: list[str]) -> list[dict]:
    results = []
    for spec in specs:
        name, command = parse_check(spec)
        completed = subprocess.run(command, shell=True, cwd=root, capture_output=True, text=True)
        output = (completed.stdout + completed.stderr).strip().splitlines()
        results.append({"name": name, "command": command, "cwd": ".",
                        "exit": completed.returncode, "passed": completed.returncode == 0,
                        "output_tail": output[-20:]})
    return results


def ledger_rows(evidence: dict) -> str:
    rows = []
    for check in evidence["checks"]:
        result = "passed" if check["passed"] else f"failed (exit {check['exit']})"
        rows.append(f"| {check['name']} | `{check['command']}`, `.` | {result} | `{evidence['sha'][:12]}` |")
    return "\n".join(rows) or "| none run | | not run | |"


def pr_body(claim: dict, evidence: dict, summary: str, proposals: list[str], auto_merge: bool = False) -> str:
    found = "\n".join(f"- {p}" for p in proposals) or "- none"
    merge = ("- Merge: GitHub auto-merge (squash) enabled by task-finish; GitHub merges when the required checks are green "
             f"(approval mode auto, integration branch `{claim['base']}`)." if auto_merge
             else "- Merge: the owner's gate.")
    return "\n".join([
        "## Task", "", f"Closes #{claim['task']}", "",
        "## What changed and why", "", summary or claim["title"], "",
        "## Verification against the exact head", "",
        "| Check | Command or procedure, cwd | Result (passed / failed / not run) | Tested SHA |",
        "| --- | --- | --- | --- |", ledger_rows(evidence), "",
        f"Evidence: `{LOCAL_DIR}/{EVIDENCE}` at `{evidence['sha']}`, run {evidence['run_at']}.", "",
        "## Merge danger", "",
        "- Door: state two-way or one-way and why.",
        "- Blast radius: what else breaks if this is wrong, and who notices first.", "",
        "## Review", "", "- Independent reviewer and reviewed SHA (advisory; merge remains the owner's gate):", merge, "",
        "## Found and left", "", found, "",
    ])


def milestone(claim: dict, evidence: dict | None, state: str, pr_url: str | None,
              proposals: list[str], blocker: str | None, next_action: str | None) -> str:
    lines = [f"**{state.capitalize()}.** Task #{claim['task']} by {claim['assistant']} "
             f"({claim['role']}, {claim['runtime']}, {claim['reference']}) on branch "
             f"`{claim['branch']}` at `{evidence['sha'][:12] if evidence else 'n/a'}`, {now()}."]
    if evidence and evidence["checks"]:
        checks = "; ".join(f"{c['name']}: {'passed' if c['passed'] else 'failed'}" for c in evidence["checks"])
        lines.append(f"Checks: {checks}.")
    if pr_url:
        lines.append(f"Pull request: {pr_url}." + (" Auto-merge (squash) enabled." if claim.get("auto_merge") else ""))
    elif state == "finished":
        lines.append(f"Pull request: opened from `{LOCAL_DIR}/{PR_BODY}` by the assistant's own access.")
    if blocker:
        lines.append(f"Blocker: {blocker}")
    if next_action:
        lines.append(f"Next action: {next_action}")
    if proposals:
        lines.append("Proposals (found mid-task, left for the owner):")
        lines.extend(f"- {p}" for p in proposals)
    return "\n".join(lines)


def checkpoint(claim: dict, head: str, state: str, evidence_path: Path | None, pr_url: str | None,
               blocker: str | None, next_action: str | None, dirty: list[str]) -> str:
    rows = [
        "# Conductor checkpoint pointer", "",
        f"- Task: #{claim['task']} {claim['title']}",
        f"- Branch: `{claim['branch']}` from `{claim['base']}` at `{claim['base_sha'][:12]}`",
        f"- Head: `{head}`",
        f"- State: {state} at {now()} by {claim['assistant']} ({claim['role']}, {claim['runtime']})",
        f"- Evidence: `{evidence_path}`" if evidence_path else "- Evidence: none",
        f"- Pull request: {pr_url or 'not opened by the helper'}",
        f"- Blocker: {blocker or 'none'}",
        f"- Next action: {next_action or ('owner review and merge' if state == 'finished' else 'resume from the blocker above')}",
        f"- Uncommitted files: {', '.join(dirty) if dirty else 'none'}",
        "",
        "The task record and the pull request are the record; this file only points at them.", "",
    ]
    return "\n".join(rows)


def cmd_finish(args: argparse.Namespace) -> int:
    root = repo_root(Path.cwd())
    folder = local_dir(root)
    claim_path = folder / CLAIM
    if not claim_path.exists():
        raise BoundaryError(f"no claim at {claim_path}; run task-start first", 3)
    claim = json.loads(claim_path.read_text())
    head = git(root, "rev-parse", "HEAD")
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    dirty = [line[3:] for line in git(root, "status", "--porcelain", check=False).splitlines()]
    proposals = args.proposal or []
    evidence_path = folder / EVIDENCE
    evidence = None
    if args.check:
        checks = run_checks(root, args.check)
        evidence = {"task": claim["task"], "branch": branch, "sha": head, "run_at": now(),
                    "dirty": dirty, "ok": all(c["passed"] for c in checks) and not dirty,
                    "checks": checks}
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n")

    blocker, next_action, state = args.blocker, args.next, "finished"
    if args.stopped:
        state = "stopped"
        blocker = blocker or "stopped by the assistant without a recorded blocker"
    elif dirty:
        state, blocker = "stopped", f"uncommitted changes at finish: {', '.join(dirty)}"
        next_action = next_action or "commit the changes, then run task-finish again"
    elif not args.check:
        state, blocker = "stopped", "no verification contract checks were passed (--check NAME=COMMAND)"
        next_action = next_action or "run task-finish with every applicable contract row"
    elif not evidence["ok"]:
        failed = ", ".join(c["name"] for c in evidence["checks"] if not c["passed"])
        state, blocker = "stopped", f"verification failed on {head[:12]}: {failed}"
        next_action = next_action or "fix the failure, commit, and run task-finish again"
    elif branch != claim["branch"]:
        state, blocker = "stopped", f"HEAD is on {branch}, the claim names {claim['branch']}"

    pr_url = None
    if state == "finished":
        body = pr_body(claim, evidence, args.summary, proposals, args.auto_merge)
        (folder / PR_BODY).write_text(body)
        if args.open:
            pr_url = open_pr(root, claim, args.title or f"#{claim['task']} {claim['title']}", folder / PR_BODY)
            if pr_url and args.auto_merge:
                enable_auto_merge(root, pr_url)
        claim["auto_merge"] = bool(args.auto_merge)
        claim["finished_at"] = now()
        claim_path.write_text(json.dumps(claim, indent=2) + "\n")
    note = milestone(claim, evidence, state, pr_url, proposals, blocker, next_action)
    (folder / MILESTONE_COMMENT).write_text(note + "\n")
    (folder / CHECKPOINT).write_text(checkpoint(
        claim, head, state, evidence_path if evidence else None, pr_url, blocker, next_action, dirty))
    posted = args.post and post_comment(claim.get("repository"), claim["task"], note)

    print(note)
    print(f"\nCheckpoint: {folder / CHECKPOINT}")
    if evidence:
        print(f"Evidence: {evidence_path}")
    if state == "finished":
        print(f"Pull request body: {folder / PR_BODY}" + (f" (opened: {pr_url})" if pr_url else
              " (open it with your GitHub access; keep Closes #n and the ledger)"))
    print(f"Milestone comment {'posted' if posted else 'drafted at ' + str(folder / MILESTONE_COMMENT)}.")
    return 0 if state == "finished" else 4


def open_pr(root: Path, claim: dict, title: str, body_file: Path) -> str | None:
    if not shutil.which("gh"):
        return None
    git(root, "push", "-u", "origin", claim["branch"])
    result = subprocess.run(["gh", "pr", "create", "--base", claim["base"], "--head", claim["branch"],
                             "--title", title, "--body-file", str(body_file)],
                            cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        raise BoundaryError(f"gh pr create failed: {result.stderr.strip()}", 6)
    return result.stdout.strip().splitlines()[-1]


def enable_auto_merge(root: Path, pr_url: str) -> None:
    """Approval mode auto: ask GitHub to squash-merge the pull request once its checks are green.

    The helper never merges; GitHub does, under the branch protection the owner set."""
    result = subprocess.run(["gh", "pr", "merge", pr_url, "--auto", "--squash"],
                            cwd=root, capture_output=True, text=True)
    if result.returncode != 0:
        raise BoundaryError(f"gh pr merge --auto failed: {result.stderr.strip()}", 6)


def cmd_verify_evidence(args: argparse.Namespace) -> int:
    root = repo_root(Path.cwd())
    path = local_dir(root) / EVIDENCE
    if not path.exists():
        raise BoundaryError(f"no evidence at {path}", 5)
    evidence = json.loads(path.read_text())
    head = git(root, "rev-parse", "HEAD")
    if evidence.get("sha") != head:
        raise BoundaryError(f"evidence is for {evidence.get('sha', '?')[:12]}, HEAD is {head[:12]}", 5)
    if not evidence.get("ok"):
        raise BoundaryError("evidence records a failed or dirty run", 5)
    print(f"Evidence matches HEAD {head[:12]}: {len(evidence['checks'])} checks passed.")
    return 0


def cmd_lines(args: argparse.Namespace) -> int:
    path = local_dir(repo_root(Path.cwd())) / CLAIM
    if not path.exists():
        raise BoundaryError(f"no claim at {path}", 3)
    print("\n".join(always_on_lines(json.loads(path.read_text()))))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start", help="claim a readied task and branch for it")
    start.add_argument("number", type=int)
    start.add_argument("--role", required=True, choices=["Owner", "Planner", "Implementer", "Reviewer"])
    start.add_argument("--runtime", required=True, help="for example 'Claude Code project thread'")
    start.add_argument("--reference", required=True, help="session, thread or task URL or id")
    start.add_argument("--assistant", default="claude", help="branch prefix and claim identity")
    start.add_argument("--repo", help="owner/name; default from the origin remote")
    start.add_argument("--record", help="JSON file with the task record (number, title, body, labels)")
    start.add_argument("--branch", help="use this branch instead of <assistant>/<slug>-<date>")
    start.add_argument("--base", default="main", help="the project's integration branch (default main)")
    start.add_argument("--no-fetch", action="store_true", help="do not fetch the base branch first")
    start.add_argument("--post", action="store_true", help="post the claim comment with gh")
    start.set_defaults(func=cmd_start)
    finish = sub.add_parser("finish", help="verify the exact head, draft the PR and the milestone")
    finish.add_argument("--stopped", action="store_true")
    finish.add_argument("--check", action="append", help="NAME=COMMAND from the verification contract")
    finish.add_argument("--proposal", action="append", help="something found mid-task, left for the owner")
    finish.add_argument("--summary", default="", help="what changed and why, for the pull request")
    finish.add_argument("--title", help="pull request title")
    finish.add_argument("--blocker")
    finish.add_argument("--next", help="next action")
    finish.add_argument("--open", action="store_true", help="push and open the pull request with gh")
    finish.add_argument("--auto-merge", action="store_true",
                        help="approval mode auto: record it in the body and, with --open, enable GitHub squash auto-merge")
    finish.add_argument("--post", action="store_true", help="post the milestone comment with gh")
    finish.set_defaults(func=cmd_finish)
    verify = sub.add_parser("verify-evidence", help="exit 0 only if the evidence matches HEAD and passed")
    verify.set_defaults(func=cmd_verify_evidence)
    lines = sub.add_parser("lines", help="print the three always-on lines from the claim")
    lines.set_defaults(func=cmd_lines)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except BoundaryError as error:
        print(f"task-boundary: {error}", file=sys.stderr)
        return error.code


if __name__ == "__main__":
    raise SystemExit(main())
