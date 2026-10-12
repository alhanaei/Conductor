<!-- conductor:init:begin -->
# Conductor project facts

- Name: Conductor
- Kind: software
- Purpose: Shared GitHub workflow and practice library for coding and analytics assistants: common workflow, status definitions, reusable skills, techniques, patterns, harness contracts and a two-stage project initializer. Documentation and templates only; no application runtime.
- Repository: https://github.com/alhanaei/Conductor
- Lifecycle: Active
- Authoritative tasks: [https://github.com/alhanaei/Conductor/issues](https://github.com/alhanaei/Conductor/issues), [https://github.com/alhanaei/Conductor/pulls](https://github.com/alhanaei/Conductor/pulls), [docs/contributing.md](docs/contributing.md)
- Checkpoint: [.conductor/HANDOFF.md](.conductor/HANDOFF.md)
- Architecture: "README.md (Structure section): shared/ holds canonical policy, workflows, skills, techniques, patterns, harness and templates; codex/ and assistants/claude-code/ hold thin assistant kits with generated copies of the initializer; docs/ holds usage, validation, contributing and release notes; tests/ holds the initializer test suites and packaging script."
- Data Sources: "unknown"
- Storage: "unknown"

## Verification contract

- Package integrity check: `python3 tests/package_conductor_init.py` from `.`; prerequisites: Python 3 standard library; expected: Exit 0 and a 'Verified ... outputs' line; regenerate with --write only as a reviewed change; evidence: [tests/package_conductor_init.py](tests/package_conductor_init.py).
- Initializer test suites: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` from `.`; prerequisites: Python 3 standard library and Git; packaging check current; expected: OK with all tests passing (57 at the validated revision); evidence: [tests/test_conductor_init.py](tests/test_conductor_init.py).
- Whitespace and conflict-marker check: `git diff --check` from `.`; prerequisites: Git; expected: No output, exit 0; evidence: [docs/initializer-validation.md](docs/initializer-validation.md).

Task progress: Backlog / Ready / In progress / Review / Done.
Execution state: Ready / Running / Waiting quota / Blocked / Needs approval / null.
Done requires verification, review and null execution state. Task records remain authoritative;
labels do not acquire ownership or locks. Missing optional facts remain unknown.
<!-- conductor:init:end -->
