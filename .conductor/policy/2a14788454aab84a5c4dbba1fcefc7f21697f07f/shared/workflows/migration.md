# Policy migration workflow

An adoption pins one reviewed Conductor source by commit and digest, and the common
workflow keeps it there until a migration is approved. This procedure is that approval
made concrete: how a project, and each assistant working in it, moves from pin A to pin B
without hand-editing managed content and without losing the ability to go back.

## When

1. A newer reviewed Conductor release exists and the project owner decides to adopt it.
   Checking for a release is part of session start; adopting it is a separate decision.
2. Never mid-task. Finish or checkpoint the active task first; a migration is its own
   bounded task with the usual record, owner and verification.
3. Read the release notes for breaking changes first. A migration that needs new access,
   tools or authority is reported for a decision, not performed.

## Preconditions

- The project has an adoption record (`.conductor/adoption.json`) and at least one
  generated `conductor-project-init` skill; a first adoption uses `generate` and `onboard`.
- Managed sections in `AGENTS.md`, `PROJECT.md` and native instruction files are
  unchanged since the last setup. Edited managed content blocks the migration until it
  is reconciled.
- The new source is verified the same way as for generation: a clean checkout whose HEAD
  is the full requested SHA, or a reviewed artifact with independent manifest and native
  checksum identities.

## Procedure

1. Run `migrate` from the new source's `conductor-init` skill, not from the old generated
   skill, so the helper, template and recipe come from the source being adopted:

   ```sh
   python3 scripts/conductor_init.py migrate --target /approved/project --source /reviewed/Conductor --source-sha <new-full-sha>
   ```

   Add `--manifest-sha <independent-digest>` for an artifact source and `--skill-root`
   when more than one assistant has generated an initializer in the project.
2. Review the plan. The first assistant to migrate moves the shared record: the
   `AGENTS.md` section gains the new commit and digest, the new policy snapshot is written
   under `.conductor/policy/<new-sha>/`, the previous snapshot is removed, this assistant's
   generated skill is regenerated, and its native verification skill is updated when the
   adoption record owns every file in it. Custom verification skills are preserved whole.
3. Apply within setup authority. The transaction backs up every updated and removed file.
4. Each other assistant that onboarded the project runs `migrate` for its own generated
   skill. Until it does, its `onboard` is blocked and the record lists it under
   `assistant_pins` at the previous pin. Its run regenerates only its own skill and
   verification assets; the shared record is already at the new pin.
5. Repeat the preview: expect `unchanged` for `migrate` and for `onboard` with the recorded
   facts. Record the migration in the project checkpoint and task record with the old and
   new identities; `.conductor/adoption.json` keeps the history under `migrations`.
6. Confirm discovery in a fresh native session, as after any setup.

## Personal and global adapters

The helper migrates project-scoped artifacts only. Adapters in a user's home follow the
same decision but are moved by hand, in this order: create the new fixed snapshot of the
reviewed source; update the global adapter's policy path, digest and source identity;
reinstall personal skill copies from the new source and verify them against the kit
checksums; update the installation record; then start a fresh session. Keep the previous
snapshot until the new one is verified. Each assistant's adapters are that assistant's
to migrate, under the library's folder ownership rule.

## Rollback

`rollback --target . --transaction .conductor/backups/<id>/transaction.json` restores the
previous snapshot, managed sections, generated skill and record from the migration's
transaction, and refuses if any of those files changed afterwards. Other assistants that
had already migrated must roll back their own transactions too, newest first.

## What migration does not do

It does not change project facts; use `onboard` with reviewed facts for that. It does
not upgrade a generator at the same pin; that is `generate --update`. It does not touch
checkpoints, task records, custom skills or text outside managed markers, and it grants
no authority beyond the setup authority it runs under.
