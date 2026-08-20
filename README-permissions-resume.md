# Dynamic permission gating — built, tested, frozen

**Status: fully implemented, tested against real users, and frozen inert.**
The four page files differ from `HEAD` by comments only — verified mechanically
by stripping all comments from both sides and diffing (all four identical).

## ⚠️ Read this before saying "remove all comments"

That instruction does the **opposite** of reactivating. Removing a comment
deletes the line; the live code sitting next to it is the *old* hardcoded check,
which would survive. Running it would erase this work and leave current
behaviour in place.

The instruction that actually reactivates:

> **"Reactivate the DYNAMIC-PERMS blocks: in every `=== DYNAMIC-PERMS-START ===`
> / `=== DYNAMIC-PERMS-END ===` block, uncomment the block's contents and delete
> the live original that follows it."**

Find every block with:

```bash
grep -rn "DYNAMIC-PERMS-START" --include="*.vue" --include="*.js" --include="*.py" . | grep -v node_modules
```

## Marker inventory (31 pairs, all balanced)

| File | Pairs | State |
| --- | --- | --- |
| `elab_notebook/elab_notebook/api/permissions.py` | 1 | live, uncalled |
| `elab-notebook-ui/src/api/permissions.js` | 1 | live, unimported |
| `elab-notebook-ui/src/stores/permissions.js` | 1 | live, unimported |
| `elab-notebook-ui/src/components/team/TeamSetup.vue` | 7 | commented out |
| `elab-notebook-ui/src/components/team/TeamDetail.vue` | 7 | commented out |
| `elab-notebook-ui/src/components/samples/SampleDetail.vue` | 6 | commented out |
| `elab-notebook-ui/src/components/experiments/ExperimentDetail.vue` | 8 | commented out |

The three infra files are wrapped but left executable: nothing imports them, so
the bundler drops them entirely (module count returns to 128, its pre-wiring
value). `permissions.py` stays importable so `bench migrate` does not break.

## Three verified findings that shaped the design

These are not opinions — each is asserted by a test in the suite below.

**1. The doctype-level branch under-reports.** `frappe.has_permission(doctype)`
with no doc cannot run this app's `has_permission` hooks (they all read
`doc.owner`, `doc.workflow_state`, …). For Experiment Team, only System Manager
holds `create` in the role table, so the endpoint reports `create=0` for the
Employee Function head — who *can* in fact create a team (verified by a live
rolled-back insert). **Gating a Create button on this alone hides working
functionality.**

**2. Hooks restrict, never grant.** `get_doc_permissions` (frappe
`permissions.py:206`) calls the hook, and on `True` falls through to the role
table anyway. So the owner of a team reads `write=0` from the dict even though
`has_team_permission` returns `True` for them.

**3. ptype-specific hook rules are invisible.** The endpoint calls
`get_doc_permissions` with `ptype=None`, and Frappe passes that same `None` to
the hook, calling it once. `has_experiment_permission` refusing `delete` on an
Approved run therefore never shows up in the dict — confirmed by asserting the
rule fires when the hook is asked about `delete` directly.

**Consequence, encoded in every call site:** the permission dict is **ORed** with
the existing server-computed domain answer, never ANDed and never used as a
replacement. It may add access; it must never subtract it. The one exception is
`SampleDetail`, where the dict is ANDed with `commentsLocked` because that
workflow lock binds everyone, System Managers included.

Also worth knowing: only **one** of the five sites originally flagged as a
"hardcoded role check" actually was one — `isSystemManager` in
`ExperimentDetail.vue`, matching a role string in JS. The other four were already
server-computed domain answers (`isHead`, `team.can_edit`, `can_edit_comments`)
or workflow-state logic, which is the pattern this project was meant to move
*toward*.

## Test suites

Both live in the session scratchpad; copy them into the repo if you want them to
persist.

- **Backend, 26/26 passing** — `scratchpad/test_perms.py`, run with
  `./env/bin/python`. Covers admin vs restricted role, creator vs non-creator
  (Only-If-Creator is induced, since no doctype here ships it, then rolled back),
  before/after a workflow transition, server-side rejection of a bypassed UI
  check, and endpoint hygiene. Every mutation is inside a transaction that is
  rolled back; the suite asserts the rollback restored owner and workflow_state.
- **Frontend, 13/13 passing** — `elab-notebook-ui/perm-store.test.mjs`, run with
  `node perm-store.test.mjs`. Covers fail-closed before any fetch (no
  flash-of-full-access), a failed fetch staying closed and uncached, cache key
  separation between doctype-level and record-level, and invalidation.

Two real bugs were found and fixed by these tests: `get_permissions` returned a
500 for an unknown doctype (both branches — `frappe.get_doc` raises `ImportError`,
not `DoesNotExistError`, because it resolves a controller module before touching
the database), and the store's import needed an explicit `.js` extension to load
under Node.

## If you reactivate

Re-run both suites first. Then re-verify against a **restricted** user — the
suites use `frappe.set_user`, which is not the same as a real HTTP session, and
none of this has been exercised through a browser with a non-admin login.
