---
name: verify-conductor
description: "Drive Conductor's verification contract and GitHub checks. Use to launch the local actionlint toolchain, prove the verify job, or check linked-task, the task-boundary skills, the backlog report, and the task and pull request templates. Conductor has no application server."
---

# Verify Conductor

Conductor is the policy page, two prose skills, three GitHub Actions workflows, and the task and pull request templates. There is no application server, port, database, or seed data. The primary surface an agent can drive on a checkout is the `verify` job. The other surfaces run on GitHub. Read `skills/verify-conductor/features/README.md` before driving, then follow one feature file. This skill grants no authority; `AGENTS.md` is the policy and GitHub runs the checks.

A run is one `CONDUCTOR_VERIFY_RUN_ID`. Scratch for that id lives at `/tmp/conductor-verify-scratch/$CONDUCTOR_VERIFY_RUN_ID/` (the actionlint binary and any detection worktree). Evidence lives at `/tmp/conductor-verify-evidence/$CONDUCTOR_VERIFY_RUN_ID/` and cleanup never deletes it. Two ids can launch at once. They share the git worktree, so a `verify-contract` drive refuses a dirty tree instead of racing an editor. Do not download `actionlint` into the repository root: CI does that only on a disposable runner, and a local binary dirties the tree.

## Launch

From the repository root, pick a fresh id and start the toolchain. Ready means the helper prints `ready: actionlint 1.7.7` and leaves that line in the scratch `ready` file. There is no server log and no migration.

```bash
export CONDUCTOR_VERIFY_RUN_ID="verify-$(date -u +%Y%m%dT%H%M%SZ)"
skills/verify-conductor/scripts/conductor-verify launch
```

Launch downloads actionlint **1.7.7** with the same installer CI uses, and passes the scratch directory as the installer's destination argument so the binary stays out of the worktree:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/rhysd/actionlint/v1.7.7/scripts/download-actionlint.bash) 1.7.7 "$SCRATCH"
```

CI's own step omits that destination and then runs `./actionlint -color` in the runner workspace. Locally the binary is `$SCRATCH/actionlint` and the working directory is still the repository root. The version argument stays `1.7.7`.

Teardown is `skills/verify-conductor/scripts/conductor-verify cleanup`. It removes this run's scratch and detection worktree. It does not remove the evidence directory.

## Doctor

Run this first, and again after anything surprising. It is read-only on the repository. It writes `doctor.txt` and `tested-sha.txt` under the evidence directory.

```bash
skills/verify-conductor/scripts/conductor-verify doctor
```

Worth driving means every line below is true:

- `doctor: ok`
- `actionlint: 1.7.7`
- `head:` is the SHA you intend to prove
- `worktree: clean` when the proof is a clean-HEAD `verify-contract` run
- `CLAUDE.md` is exactly `@AGENTS.md`
- `AGENTS.md` is the Conductor page and states there is no application runtime
- `.github/workflows/ci.yml` still runs `git diff --check`, pins `actionlint/v1.7.7`, and runs `./actionlint -color`
- the three workflows, both task skills, the task form, and the pull request template are present

There is no port and no app auth. `gh` auth is not part of this doctor; GitHub features name that precondition themselves. A dirty worktree still prints `doctor: ok` and `worktree: dirty`, because doctor reports the tree rather than hiding it. `drive verify-contract` then refuses that tree.

## Drive

The helper drives one feature, the local `verify` job. Run doctor first (the drive runs doctor again).

```bash
skills/verify-conductor/scripts/conductor-verify drive verify-contract
```

On a clean worktree this does three things, in order, and writes each result under the evidence directory:

1. `git diff --check` at the repository root. Exit 0 and no output. This is the CI step.
2. `$SCRATCH/actionlint -color` at the repository root. Exit 0 and no output. This is the CI step.
3. A detection proof in a detached worktree under this run's scratch: append one trailing-whitespace line to that worktree's `README.md`, expect `git diff --check` to exit 2 and report `trailing whitespace.`, then remove the worktree.

Any other feature is driven by the commands in its file under `skills/verify-conductor/features/`. The helper refuses those names so they are not reported as a helper pass:

```bash
skills/verify-conductor/scripts/conductor-verify drive linked-task
```

That exits 2 and names the feature file. Follow that file. Do not invent a local stand-in for a GitHub job.

## Evidence

Proof files stay in `/tmp/conductor-verify-evidence/$CONDUCTOR_VERIFY_RUN_ID/`. Print the path with:

```bash
skills/verify-conductor/scripts/conductor-verify evidence-path
```

A `verify-contract` pass leaves:

| File | What it proves |
| --- | --- |
| `tested-sha.txt` | The HEAD the doctor read |
| `launch.txt` | Installer log and `ready: actionlint 1.7.7` |
| `doctor.txt` | Doctor report, including `doctor: ok` and `worktree: clean` |
| `verify-whitespace.exit` | `0`, with empty stdout and stderr |
| `verify-whitespace-detect.exit` | `2`, and stdout contains `trailing whitespace.` |
| `verify-workflows.exit` | `0`, with empty stdout and stderr |
| `verify-contract.result` | `pass` |

Capture the command and the resulting state. For `verify-contract` the command output is the state: empty success for the CI steps, and the whitespace finding for the detection step. Save GitHub-feature transcripts into this same directory, using the names in each feature file. Do not commit the evidence directory.

Standards:

- Exercise the path the workflow or the template actually uses. Do not treat a grep of a workflow as a pass of the job that runs it.
- `actionlint` passing is the workflow-lint half of `verify`. It is not a pass of `linked-task` or of the backlog report.
- Do not open a pull request, file an issue, comment, change labels, or `workflow_dispatch` the backlog workflow in order to manufacture a pass. Those are side effects. Read an existing run when the feature file says to.
- A dry local read of YAML does not skip GitHub. If the feature file's live command cannot be run, record the unmet precondition and a failure for that journey.
- Match rendered log lines, not the workflow source that GitHub echoes into the same log. The feature files give the patterns that appear only in the job's own output.

## Cleanup

```bash
skills/verify-conductor/scripts/conductor-verify cleanup
```

Cleanup removes `/tmp/conductor-verify-scratch/$CONDUCTOR_VERIFY_RUN_ID/`, including the actionlint binary and the detection worktree if one was left behind. It then prints `evidence remains at` the evidence path. Confirm the evidence files are still there after cleanup. There is no long-running server. Do not kill processes by name. If a download you started is stuck, stop that process id.

## Helpers

The harness is `skills/verify-conductor/scripts/conductor-verify`. It is executable. From the repository root:

```bash
export CONDUCTOR_VERIFY_RUN_ID="verify-$(date -u +%Y%m%dT%H%M%SZ)"
skills/verify-conductor/scripts/conductor-verify launch
skills/verify-conductor/scripts/conductor-verify doctor
skills/verify-conductor/scripts/conductor-verify drive verify-contract
skills/verify-conductor/scripts/conductor-verify evidence-path
skills/verify-conductor/scripts/conductor-verify cleanup
```

`CONDUCTOR_VERIFY_ROOT` overrides the repository root. Leave it unset when the script's own repository is the tree under test.

## Maintenance

When a workflow, skill, or template changes, re-check this map with `/maintain-verification-skill`. A cadence is the owner's to set. The map is not the policy.
