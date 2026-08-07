<<<<<<< HEAD
# Elab Notebook

A modern, high-fidelity, and enterprise-grade Experiment Tracker and Laboratory Management application built on top of the [Frappe Framework](https://github.com/frappe/frappe).

---

## 🚀 What Has Been Built So Far

We have developed both the Frappe-based backend infrastructure and a high-performance Vue 3 client interface. Here is a summary of the implemented features:

### 1. Backend Architecture (`elab_notebook`)
- **Dynamic DB Setup ([user.py](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab_notebook/elab_notebook/api/user.py)):** Includes a programmatic schema initializer (`setup_db()`) that automatically registers:
  - Custom child DocTypes: `Template Ingredient`, `Template Parameter`, and `Template Protocol Step`.
  - Extensions to the core `Experiment Template` DocType (e.g., adding `template_name`, `category`, `version`, `status`, `objective_hypothesis`, and ingredient/parameter/step tables).
  - Extensions to the core `Experiment` DocType (e.g., linking it to a template and injecting template child tables).
- **Authentication & User Management:** Custom session APIs to fetch user profile cards, initials, and designation values (`get_current_user_profile()`), along with development-redirect hooks (`login_redirect()`).
- **Template APIs ([template.py](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab_notebook/elab_notebook/api/template.py)):** Endpoints to query, save, retrieve detail, and instantiate new draft `Experiment` records directly from template models.
- **Analytics APIs ([dashboard.py](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab_notebook/elab_notebook/api/dashboard.py)):** Standard whitelist endpoints exposing lab summary numbers, monthly throughput trends, success rate distributions, chemical volume metrics, active logs, and pending tasks.

### 2. Frontend Interface (`elab-notebook-ui`)
A beautifully styled, high-performance web app built using **Vue 3, Vite, Pinia, and Chart.js**. Key features include:
- **Local Dev Proxy & Router Auth:** The app checks session state and coordinates login redirections smoothly between the Vite dev server (port `5173`) and the local Frappe bench (port `8000`).
- **Shell Layout ([ShellLayout.vue](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/layout/ShellLayout.vue)):** A custom layout featuring a side navigation bar, active breadcrumbs, user status cards, and responsive page routing.
- **Interactive Dashboard ([Dashboard.vue](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/dashboard/Dashboard.vue)):** Visualizes lab analytics, instrument metrics, monthly experiment completion trends (via Chart.js), chemical inventories, and active logs.
- **Templates Catalog ([TemplatesList.vue](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/templates/TemplatesList.vue)):** A filterable grid display of existing experiment protocols with usage counters and a new template creator modal.
- **Template Workspaces ([TemplateDetail.vue](file:///wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/templates/TemplateDetail.vue)):** An editor showing exact formulation specs (chemical grade/concentration), instrument settings (target, min, max parameters), and step-by-step checklists.

---

## 🛠️ Installation & Setup

### 1. Install Backend App
You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app elab_notebook
```

### 2. Bootstrap Database Schema
Run the database setup script via bench console or call the API endpoint once to ensure all child DocTypes and field customisations are created:

```python
# In bench console:
frappe.init(site="your-site-name")
frappe.connect()
from elab_notebook.elab_notebook.api.user import setup_db
setup_db()
```

### 3. Run Frontend Dev Server
Navigate to the UI folder, install node dependencies, and boot Vite:

```bash
cd apps/elab_notebook/elab-notebook-ui
npm install
npm run dev
```

The application is pre-configured to proxy `/api` requests to a local Frappe site running on `http://localhost:8000`.

---

## 🧪 Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/elab_notebook
pre-commit install
```

Pre-commit is configured to use the following tools:
- `ruff` (Python linting & formatting)
- `eslint` (JS/Vue linting)
- `prettier` (Code style & markup formatting)
- `pyupgrade` (Python syntax modernization)

---

## 📦 CI/CD Workflows

The repository has two configured GitHub Actions workflows:
- **CI:** Installs the app dependencies and runs test files on push to `develop`.
- **Linters:** Executes Semgrep checks and `pip-audit` to detect security vulnerabilities on pull requests.

---

## 🔄 Function-Scoped Project Selector & Dual Dashboard Mode

We have implemented a role-based, function-scoped project access control mechanism and a dual-mode filtering system on the laboratory dashboard:

### 1. Function-Scoped Access Control (Backend & Frontend)
- **Whitelisted API (`get_employee_scope`):** Checks the user session, identifies the corresponding `Employee` record, and parses their active functions (from `custom_function_code` child table).
- **Scope Categorization & Priority:** 
  - **Function Scope (Highest Priority):** If the user is mapped to an active `Employee` record with active functions, they are strictly restricted to projects defined in the `project_list` child table of their linked `Employee Function` documents, even if they possess Administrator/System Manager roles.
  - **All Projects Fallback:** If they have no mapped active functions but carry the Administrator or System Manager roles, they bypass restriction and get access to all projects in the system.
  - **None:** If they are a regular employee with zero active functions, they are flagged as "No Function Assigned" and cannot access any projects.
- **Frontend Integration & Layout controls:** 
  - The top bar selector in [ShellLayout.vue](file://wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/layout/ShellLayout.vue) dynamically populates allowed projects in the dropdown menu.
  - If a user has no active functions assigned, the dropdown is disabled, showing a `"No function assigned"` warning state.
  - Added a **Sidebar Toggle Button** in the top bar that collapses the sidebar smoothly using CSS transitions.
  - Optimized dashboard layout rules in [Dashboard.css](file://wsl.localhost/Ubuntu/home/shivam/frappe-bench/frappe-bench/apps/elab_notebook/elab-notebook-ui/src/components/dashboard/Dashboard.css) to support responsive scaling, wrapping metrics widgets, stacking sections vertically on narrower viewports, and eliminating horizontal side-by-side scrolls.

### 2. Dual-Mode Dashboard Aggregation
- Every metrics widget (Summary Cards, Chemical Consumption, Run Volume trends, Success rates, yield trends, recent experiments, feeds, and tasks) accepts a `project` parameter.
- **Mode 'All Projects' (Aggregation):** If `All Projects` is selected, the dashboard aggregates metrics and averages trends specifically across the employee's subset of allowed projects (instead of blindly querying every project in the system).
- **Mode Specific Project (Filtering):** If a single project is selected, all dashboard components are filtered exclusively to that project's database entries and deterministic trends.

---

## 🧬 Experiment Template — Rebuilt as Versioned Code

The `Experiment Template` DocType and its child tables were rebuilt from scratch and **converted from UI-created custom DocTypes (`custom=1`, DB-only) into version-controlled code** under `elab_notebook/elab_notebook/doctype/`. They now belong to the **`Elab Notebook`** module (previously `Stock`).

### 1. Pre-flight findings (verified against the live site)

Two structural facts drove the implementation and are worth recording, because both differ from the naive assumption:

| Question | Answer found in DB |
|---|---|
| Employee Function head field | **No `head_name` field exists.** The doctype has `function_head` (Link → **User**) and `function_head_name` (Data, `fetch_from: function_head.full_name`). |
| Employee Function ↔ Project link | **Not a direct Link — two child tables, in both directions.** |
| Project ID source | **`Project` has no `project_id` field.** The template's `project_id` mirrors `Project.name`, so `fetch_from: project.name` is used. |

The EF ↔ Project relationship is stored on **both** sides, and neither table is complete on its own:

- **A.** `Employee Function.project_list` → child `Project list`, whose `projects` field is **Data (not a Link)** holding the Project name, e.g. `PLTP-2025-0041`. Covers 96 / 109 Employee Functions.
- **B.** `Project.custom_function_info` → child `Employee Function Child`, whose `function_code` is a Link to Employee Function. Covers 89 / 167 Projects.

Because neither is authoritative alone, the resolver **unions both paths**.

### 2. Child DocTypes (`istable = 1`)

| DocType | Fields |
|---|---|
| `Experiment Step CT` | `step_no` (Int), `instruction` (Small Text), `expected_duration` (Duration), `is_critical` (Check) |
| `Observations CT` | `parameter` (Data), `observed_value` (Data), `remarks` (Small Text), `observed_on` (Datetime) |
| `Material Required CT` | `item_code` (Link → Item, reqd), `item_name` (Data, fetch `item_code.item_name`, read-only), `uom` (Link → UOM, fetch `item_code.stock_uom`), `qty` (Float, reqd) |
| `Equipment Details CT` | `refer_to_experiment` (Link → Experiment), `equipment_name` (Data), `equipment_id` (Data), `remarks` (Small Text) |
| `Methodology CT` | `method` (Small Text, reqd), `time_to_complete` (Duration) |

### 3. `Experiment Template` DocType

Doctype-level settings: `is_submittable = 1`, `autoname = format:ET-{project_id}-{######}`, `module = Elab Notebook`, `sort_field = modified`, `sort_order = DESC`, `title_field = title`, `track_changes = 1`.

Field sequence (42 fields, in order):

1. `title` (Data, **reqd**) · 2. `type` (Select: R&D-Early Stage / R&D-Analytical / Validation / Scale-Up / Process Development) · 3. `description` (Small Text) · 4. `disable` (Check, default 0)
5. `employee_function` (Link → Employee Function, **reqd**, standard filter) · 6. `head_name` (Data, `fetch_from: employee_function.function_head_name`, read-only)
7. *Column Break* · 8. `allowed_roles` (Link → Department, label **Department**) · 9. `project` (Link → Project, **reqd**, standard filter) · 10. `project_id` (Data, `fetch_from: project.name`, read-only) · 11. `remark` (Small Text)
12. *Section Break* · 13. `aim` (Data) · 14. `sub_aim` (Small Text) · 15. *Column Break* · 16. `rationale` (Long Text)
17. *Section: Material Required* · 18. `material_required` (Table → Material Required CT)
19. *Section: Equipment Details* · 20. `equipment_details` (Table → Equipment Details CT)
21. *Section: Methodology* · 22. `methodology` (Table → Methodology CT) · 23. `methodology_comments` (Text Editor, standalone)
24. *Section: Protocol* · 25. `protocol_steps` (Table → Experiment Step CT) · 26. `steps` (Text Editor)
27. *Section: Observation* · 28. `observation_table` (Table → Observations CT) · 29. `observation_comments` (Text Editor)
30. *Section Break* · 31. `amended_from` (Link → Experiment Template, read-only, no_copy, print_hide)
32. *Section: Legacy Template Fields* (collapsible) · 33–42. `template_name`, `category`, `version`, `status`, `objective_hypothesis`, `created_by`, `department`, `template_ingredients`, `template_parameters`, `template_protocol_steps`

> The legacy fields (33–42) are **retained deliberately** — [template.py](elab_notebook/elab_notebook/api/template.py) reads them. Removing them would break the template APIs and the Vue templates catalog.

**Permissions:** `System Manager` — full (read/write/create/delete/submit/cancel/amend/report/export/print/email/share). `Employee` — read/write/create/submit/amend with `if_owner = 1` and `delete = 0`.

### 4. Naming fix — `before_naming`

`autoname` depends on `project_id`, but Frappe runs `set_new_name()` **before** `fetch_from` is applied. Pre-existing records show the resulting bug (`ET--022223`, with a null `project_id`). [experiment_template.py](elab_notebook/elab_notebook/elab_notebook/doctype/experiment_template/experiment_template.py) resolves `project_id` in `before_naming()` so names come out correctly as `ET-PLTP-2025-0041-022229`.

`validate()` additionally rejects an `employee_function` that is not mapped to the selected `project` — server-side enforcement, so the client filter cannot be bypassed via API.

### 5. Employee Function filtering

[api/employee_function.py](elab_notebook/elab_notebook/api/employee_function.py) exposes:
- `get_employee_functions_for_project(project)` — unions link paths **A** and **B**.
- `employee_function_query(...)` — a `@frappe.validate_and_sanitize_search_inputs` link-field query used by `frm.set_query`.
- `get_project_employee_functions(project)` — plain whitelisted helper for the Vue UI.

[experiment_template.js](elab_notebook/elab_notebook/elab_notebook/doctype/experiment_template/experiment_template.js) wires the query in `setup`, and on `project` change clears `employee_function`, `head_name`, and re-seeds `project_id` so a stale EF from a previous project cannot survive.

### 6. Owner-based access isolation (critical)

`Employee Function` is a **shared master** — many employees sit under the same function — so field-level scoping cannot isolate one employee's templates from a colleague's. Isolation is therefore **owner-based and enforced on the server**, in [permissions.py](elab_notebook/permissions.py), registered in [hooks.py](elab_notebook/hooks.py):

```python
permission_query_conditions = {
    "Experiment Template": "elab_notebook.permissions.get_permission_query_conditions",
}
has_permission = {
    "Experiment Template": "elab_notebook.permissions.has_permission",
}
```

- `get_permission_query_conditions` appends `` `tabExperiment Template`.`owner` = <user> `` to list/report queries.
- `has_permission` applies the same owner check to single-document access, so opening another user's record **by direct URL** is blocked too.
- `System Manager` and `Administrator` bypass both.

**Verified with two real users sharing one Employee Function (`VP-LTP-POC-008`):**

| Check | Result |
|---|---|
| List as user A | only A's own record |
| List as user B | only B's own record |
| B opens A's doc by URL | `PermissionError` (blocked) |
| A opens A's own doc | allowed |
| List as Administrator | both records (bypass) |

Also verified: autoname → `ET-PLTP-2025-0041-022229`; `head_name` auto-fetch → `Hitendra Jadhav`; submit → `docstatus = 1`; an Employee Function not mapped to the project is rejected on insert.

### 7. Migration notes & follow-ups

- The previous UI-built `Experiment Template` (14 records), `Experiment Step CT` (40 rows) and `Observations CT` (18 rows) were **dropped and recreated** from code. A SQL dump was taken before the drop.
- ⚠️ `Experiment Step CT` and `Observations CT` are **shared with the `Experiment` DocType** (`protocol_steps`, `observation_table`). Their rows under `Experiment` parents (6 and 5) were dropped along with the rebuild, and those two CTs now carry the new field set on the `Experiment` form as well.
- ⚠️ One `Experiment` record still links to a deleted template via `experiment_template` — a dangling link to clean up.
- ⚠️ A child DocType named **`Equipment Details`** already exists with effectively the same fields as the new `Equipment Details CT` (plus `equipment_status` and `qualification`). `Experiment.equipment_details` still points at the old one. Worth consolidating.
- ⚠️ `workflow_state` is **not** declared in the DocType JSON. The active Workflow **`Template flow`** owns it as an auto-generated Custom Field (standard Frappe behaviour); declaring it in both places raises *"A field with the name workflow_state already exists"* during migrate.
- ⚠️ `Template flow`'s states are `Draft → Pending from Reviewer → Pending Approval Of HOD → Rejected → Approved By HOD` and it grants transitions to a **`Reviewer`** role — tied to the removed `reviewer` field. This does **not** match the proposed `Draft → Planned → Ready → In Progress → Completed → Under Review → Approved → Closed` flow. Rebuilding it needs role/transition decisions and was left untouched.

---

## 📄 License
MIT License
=======
# Digital-Laboratory
An enterprise-grade laboratory experiment management platform for planning, executing, tracking, and analyzing experiments.
>>>>>>> 8c58dd6d784ece8c01d205a2ee6097c2d0bbffc6
