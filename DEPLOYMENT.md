# Deploying Elab Notebook

What a production site needs that a development bench does not. Everything here
was verified against this bench on 2026-08-29; where a value is site-specific it
says so rather than guessing.

---

## 1. Required site configuration

### `elab_spa_url` — where login lands

After Frappe's login page authenticates someone it redirects to
`login_redirect` (`elab_notebook.elab_notebook.api.user.login_redirect`), which
forwards to the SPA. That destination is configuration, not code:

```bash
bench --site <site> set-config elab_spa_url "https://lab.example.com/elab"
```

If the key is absent the endpoint falls back to `/elab`. It used to be a
hardcoded `http://localhost:5173/`, which sent every production login to the
developer's own machine.

On this bench `site_local` is set to `http://localhost:5173/` for the Vite dev
server. **A production site must not carry that value.**

---

## 2. Configuration that must NOT reach production

These are set on the development sites here and are correct there. Each one is a
real problem if it is copied to a live site.

| Key | Dev value | Why it must not ship |
|---|---|---|
| `ignore_csrf` | `1` on `site_local` | Disables cross-site request forgery protection entirely. Every state-changing endpoint becomes callable from any origin that can make the browser send its cookies. |
| `server_script_enabled` | `1` | Lets Server Script documents run arbitrary Python. Anyone who can write one gets code execution. |
| `developer_mode` | `1` in `common_site_config.json` | Lets schema be edited through the UI and writes those edits to disk. On a live site it means the database schema can drift from the app. |
| `allow_tests` | `true` | Permits the test runner, which creates and deletes records against the site. |
| `allow_cors` | `http://localhost:5173` | Grants a developer machine cross-origin access. |
| `disable_search` | `1` on `site_local` | Turns off the global search the app's search box depends on. |

Check before going live:

```bash
bench --site <site> execute frappe.client.get_value \
  --args '["System Settings","name","name"]' >/dev/null   # site boots
cat sites/<site>/site_config.json                          # read it and mean it
cat sites/common_site_config.json
```

---

## 3. Build and install

```bash
# Front end - the built bundle is what Frappe serves
cd apps/elab_notebook/elab-notebook-ui
npm ci
npm run build

# Back end
cd ../../..
bench --site <site> install-app elab_notebook
bench --site <site> migrate
bench build
bench --site <site> clear-cache
```

`bench migrate` runs the patches in `elab_notebook/patches.txt`, including the
workflow definition (`create_lab_experiment_workflow`). The workflow is what the
approval chain depends on — a site without it has no `Lab Experiment Flow` and
every run stays in Draft.

---

## 4. Tests

Two suites need no site and should pass before any deploy:

```bash
# Pure logic - category ladder, template numbering, suffix parsing
cd apps/elab_notebook
python3 -m unittest discover -s tests -t .

# Front-end helpers - date formatting, durations, tab visibility rules
cd elab-notebook-ui
npm test
```

The doctype tests need a site:

```bash
bench --site <site> run-tests --app elab_notebook --skip-test-records
```

`--skip-test-records` is not optional on this bench. Without it the runner tries
to build ERPNext's fixture chain and dies on `_Test Supplier`, which has no
`default_currency` here — the run aborts before a single elab_notebook test
executes.

**Know what this does and does not prove.** The doctype suite currently reports
`10 skipped, 0 failed`: every test in `test_sample.py` skips for want of seed
data, and the test files for Lab Experiment, Experiment Team and Lab Experiment
Template are empty stubs. The permission model, the workflow locks, the four-level
hierarchy rules and sample/stock generation have **no automated coverage at all**.
A green run here is not evidence those rules work.

---

## 5. Things to know before you deploy

- **`setup_db()` is not an API.** It lives in `api/user.py` but carries no
  `@frappe.whitelist()` and must not be given one — it rewrites DocType
  permission rows. Run it from a trusted console only:
  `bench --site <site> execute elab_notebook.elab_notebook.api.user.setup_db`.
  New schema belongs in doctype JSON plus a patch. (The repository README still
  describes this as a "Dynamic DB Setup" feature; that section is out of date.)

- **Profile photos are stored as public files.** The avatar renders in a plain
  `<img>` on every screen, so the file is readable by anyone with the URL. If
  that is unacceptable in your environment, it needs changing before rollout.

- **Two menu items lead nowhere.** *AI Predictions* and *Reports & Analytics* in
  the sidebar's Intelligence group are `href="#"` placeholders, and the first
  carries a **New** badge. Hide them or label them as planned before users see
  them.

- **Chart colours do not render.** The dashboard charts pass
  `color: 'var(--text-muted)'` to Chart.js, which paints to a canvas and cannot
  resolve CSS custom properties. Axis and legend fall back to Chart.js's default
  grey. Cosmetic, but visible on the first screen anyone opens.

- **`frappe.get_all` outnumbers `frappe.get_list` 72 to 24.** `get_all` bypasses
  permissions by design. Many uses are legitimate internal resolvers, but the set
  has not been audited end to end, and each one that answers a user request is a
  potential disclosure.
