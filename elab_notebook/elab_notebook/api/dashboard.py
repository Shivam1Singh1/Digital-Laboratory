import datetime
import frappe
from frappe import _

def get_dashboard_projects(project=None):
    from elab_notebook.elab_notebook.api.user import get_employee_scope
    scope_data = get_employee_scope()
    allowed_projects = [p["name"] for p in scope_data.get("projects", [])]
    
    if project and project != "all":
        if project in allowed_projects or scope_data.get("scope") == "all":
            return [project]
        else:
            return []
    return allowed_projects

@frappe.whitelist()
def get_dashboard_summary(project=None):
    allowed_projects = get_dashboard_projects(project)
    if not allowed_projects:
        return {
            "active": 0,
            "completed": 0,
            "pending_approval": 0,
            "running": 0,
            "scientists": 0,
            "instruments": 0
        }
    
    # Real DB counts
    # States come from the "Lab Experiment Workflow" Workflow record. Its
    # predecessor's names (Draft / Saved / Running / Pending Approval from System
    # Manager) no longer exist on any run, so every one of these counts read zero
    # until they were renamed:
    #     Draft   -> Start          Running -> In Progress
    #     Pending Approval from System Manager -> Sent for Approval
    # "Edit Completed" is new - a rejected run being corrected is still active
    # work, so it belongs in the active count rather than nowhere.
    active_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": ["in", ["Start", "In Progress", "Edit Completed"]]})
    completed_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "Completed"})
    pending_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "Sent for Approval"})
    running_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "In Progress"})
    
    # Scientists: distinct participants/heads in Experiment Teams for allowed_projects
    teams = frappe.get_all("Experiment Team", filters={"project": ["in", allowed_projects]}, fields=["name", "employee_function"])
    scientists = set()
    if teams:
        team_names = [t.name for t in teams]
        participants = frappe.get_all("Experiment Team Participant", filters={"parenttype": "Experiment Team", "parent": ["in", team_names]}, fields=["user"])
        for p in participants:
            if p.user:
                scientists.add(p.user)
        # Also add heads of those employee functions
        for t in teams:
            head = frappe.db.get_value("Employee Function", t.employee_function, "function_head")
            if head:
                scientists.add(head)
                
    scientists_count = len(scientists)
    instruments_count = frappe.db.count("Workstation", {"status": ["!=", "Inactive"]}) or frappe.db.count("Workstation") or 1
    
    return {
        "active": active_db,
        "completed": completed_db,
        "pending_approval": pending_db,
        "running": running_db,
        "scientists": scientists_count if scientists_count > 0 else 1,
        "instruments": instruments_count
    }

@frappe.whitelist()
def get_monthly_experiments(project=None):
    allowed_projects = get_dashboard_projects(project)
    
    # Calculate last 12 months dynamically
    today = datetime.date.today()
    months_list = []
    month_keys = []  # List of tuples (year, month)
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_keys.append((year, month))
        dt = datetime.date(year, month, 1)
        months_list.append(dt.strftime("%b"))
        
    completed_trend = [0] * 12
    terminated_trend = [0] * 12
    
    if not allowed_projects:
        return {
            "months": months_list,
            "completed": completed_trend,
            "terminated": terminated_trend
        }
        
    experiments = frappe.get_all(
        "Lab Experiment",
        filters={"project": ["in", allowed_projects]},
        fields=["creation", "workflow_state"]
    )
    
    for exp in experiments:
        if not exp.creation:
            continue
        dt = frappe.utils.getdate(exp.creation)
        for idx, (yr, mo) in enumerate(month_keys):
            if dt.year == yr and dt.month == mo:
                state = (exp.workflow_state or "").lower()
                if state in ("completed", "approved"):
                    completed_trend[idx] += 1
                elif state == "rejected":
                    terminated_trend[idx] += 1
                break
                
    return {
        "months": months_list,
        "completed": completed_trend,
        "terminated": terminated_trend
    }

@frappe.whitelist()
def get_success_rate(project=None):
    allowed_projects = get_dashboard_projects(project)
    if not allowed_projects:
        return {
            "passed": 0,
            "failed": 0,
            "inconclusive": 0
        }
        
    experiments = frappe.get_all(
        "Lab Experiment",
        filters={"project": ["in", allowed_projects]},
        fields=["workflow_state"]
    )
    
    passed = 0
    failed = 0
    inconclusive = 0
    
    for exp in experiments:
        state = exp.workflow_state or "Draft"
        if state in ("Approved", "Completed"):
            passed += 1
        elif state == "Rejected":
            failed += 1
        else:
            inconclusive += 1
            
    total = passed + failed + inconclusive
    if total == 0:
        return {"passed": 0, "failed": 0, "inconclusive": 0}
        
    return {
        "passed": round((passed / total) * 100),
        "failed": round((failed / total) * 100),
        "inconclusive": round((inconclusive / total) * 100)
    }

@frappe.whitelist()
def get_yield_trend(project=None):
    allowed_projects = get_dashboard_projects(project)
    
    # Calculate last 8 months dynamically
    today = datetime.date.today()
    month_keys = []
    month_names = []
    for i in range(7, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_keys.append((year, month))
        dt = datetime.date(year, month, 1)
        month_names.append(dt.strftime("%b"))
        
    yield_vals = [0.0] * 8
    
    if allowed_projects:
        # Get all completed experiments in allowed projects
        experiments = frappe.get_all(
            "Lab Experiment",
            filters={
                "project": ["in", allowed_projects],
                "workflow_state": "Completed"
            },
            fields=["name", "creation"]
        )
        for exp in experiments:
            if not exp.creation:
                continue
            dt = frappe.utils.getdate(exp.creation)
            for idx, (yr, mo) in enumerate(month_keys):
                if dt.year == yr and dt.month == mo:
                    # Sum qty from Sample child table of this experiment
                    samples_qty = frappe.db.get_values(
                        "Sample",
                        filters={"experiment": exp.name},
                        fieldname="qty"
                    )
                    qty_sum = sum(float(q[0] or 0) for q in samples_qty if q)
                    yield_vals[idx] += qty_sum
                    break
                    
    return {
        "months": month_names,
        "yield": [round(y, 1) for y in yield_vals]
    }

@frappe.whitelist()
def get_chemical_consumption(project=None):
    allowed_projects = get_dashboard_projects(project)
    if not allowed_projects:
        return []
        
    # Fetch all experiments in allowed_projects
    experiments = frappe.get_all(
        "Lab Experiment",
        filters={"project": ["in", allowed_projects]},
        pluck="name"
    )
    
    chemicals = {}
    
    if experiments:
        # Get all Material Required CT child rows
        materials = frappe.get_all(
            "Material Required CT",
            filters={"parenttype": "Lab Experiment", "parent": ["in", experiments]},
            fields=["item_name", "qty", "uom"]
        )
        for m in materials:
            if not m.item_name:
                continue
            name = m.item_name
            qty = float(m.qty or 0)
            uom = m.uom or "L"
            if name not in chemicals:
                chemicals[name] = {"volume": 0.0, "unit": uom}
            chemicals[name]["volume"] += qty
            
    result = []
    for name, val in chemicals.items():
        result.append({
            "name": name,
            "volume": round(val["volume"], 2),
            "unit": val["unit"]
        })
        
    result.sort(key=lambda x: x["volume"], reverse=True)
    return result

@frappe.whitelist()
def get_recent_experiments(limit=4, project=None):
    if isinstance(limit, str):
        limit = int(limit)
        
    allowed_projects = get_dashboard_projects(project)
    recent = []
    
    if allowed_projects:
        db_exps = frappe.get_all(
            "Lab Experiment",
            fields=["name", "title", "aim", "employee_name", "owner", "workflow_state", "modified", "project"],
            filters={
                "project": ["in", allowed_projects],
                "workflow_state": ["not in", ["Approved", "Rejected", "Completed"]]
            },
            order_by="modified desc",
            limit=limit
        )
        for e in db_exps:
            owner_name = e.get("employee_name") or e.get("owner")
            if owner_name == "Administrator":
                owner_name = "System Admin"
            recent.append({
                "id": e.name,
                "name": e.title or e.aim or "Untitled Experiment",
                "owner": owner_name,
                "status": e.workflow_state or "Draft",
                "progress": 45,
                "updated": frappe.utils.global_date_format(e.modified) if e.modified else "Just now"
            })
            
    return recent

@frappe.whitelist()
def get_activity_feed(limit=5, project=None):
    if isinstance(limit, str):
        limit = int(limit)
        
    allowed_projects = get_dashboard_projects(project)
    feed = []
    
    if allowed_projects:
        recent_updates = frappe.get_all(
            "Lab Experiment",
            fields=["name", "modified_by", "workflow_state", "modified"],
            filters={"project": ["in", allowed_projects]},
            order_by="modified desc",
            limit=limit
        )
        for r in recent_updates:
            user_fullname = frappe.db.get_value("User", r.modified_by, "full_name") or r.modified_by
            if user_fullname == "Administrator":
                user_fullname = "System Admin"
            feed.append({
                "user": user_fullname,
                "action": f"updated state to {r.workflow_state or 'Draft'} for",
                "target": r.name,
                "time": frappe.utils.global_date_format(r.modified) if r.modified else "Just now"
            })
            
    return feed

@frappe.whitelist()
def get_upcoming_tasks(project=None):
    allowed_projects = get_dashboard_projects(project)
    tasks = []
    
    if not allowed_projects:
        return []
        
    user = frappe.session.user
    
    pending_exps = frappe.get_all(
        "Lab Experiment",
        filters={
            "project": ["in", allowed_projects],
            "workflow_state": "Sent for Approval"
        },
        fields=["name", "workflow_state", "owner", "reviewer", "title"]
    )
    
    pending_temps = frappe.get_all(
        "Lab Experiment Template",
        filters={
            "project": ["in", allowed_projects],
            "workflow_state": ["in", ["Pending from System Manager", "Pending For Approval"]]
        },
        fields=["name", "workflow_state", "owner", "title"]
    )
    
    task_idx = 1
    for exp in pending_exps:
        is_approver = False
        # Lab Experiment Flow allows only System Manager to approve or reject;
        # the assigned reviewer still gets the item in their inbox.
        if "System Manager" in frappe.get_roles(user) or exp.reviewer == user:
            is_approver = True
            
        role_label = "Approver" if is_approver else "Owner"
        tasks.append({
            "id": task_idx,
            "text": f"[{role_label}] Review and approve Experiment {exp.title or exp.name} ({exp.workflow_state})",
            "done": False
        })
        task_idx += 1
        
    for temp in pending_temps:
        is_approver = False
        if temp.workflow_state == "Pending from System Manager" and "System Manager" in frappe.get_roles(user):
            is_approver = True
        elif temp.workflow_state == "Pending For Approval" and "System Manager" in frappe.get_roles(user):
            is_approver = True
            
        role_label = "Approver" if is_approver else "Owner"
        tasks.append({
            "id": task_idx,
            "text": f"[{role_label}] Review and approve Template {temp.title or temp.name} ({temp.workflow_state})",
            "done": False
        })
        task_idx += 1
        
    return tasks

# The four tiles the dashboard actually draws (see Dashboard.vue). The endpoint
# takes a doctype as a parameter, which is convenient for the component and an
# open door for everyone else: the scoping further down only bites if the doctype
# carries a `project` field or has a permission_query_conditions hook registered,
# and for anything else on the bench - Salary Slip, User, Employee - neither is
# true, so it answered with unfiltered counts grouped by status and month. A
# parameter that only ever takes four values is an allowlist, so it is written as
# one.
ENTITY_STATS_DOCTYPES = frozenset({
    "Lab Experiment Template",
    "Experiment Team",
    "Lab Experiment",
    "Workstation",
})


@frappe.whitelist()
def get_entity_stats(doctype, status_field, project=None):
    if doctype not in ENTITY_STATS_DOCTYPES:
        frappe.throw(_("{0} is not a dashboard entity.").format(doctype), frappe.PermissionError)

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Invalid DocType: {doctype}")

    # Role-level read on the doctype, on top of the allowlist. The row-level rules
    # are applied further down through the permission_query_conditions hooks; this
    # is the coarser gate that stops a user with no read rights at all from
    # counting rows they could never open.
    if not frappe.has_permission(doctype, "read"):
        frappe.throw(
            _("You are not permitted to read {0}.").format(doctype), frappe.PermissionError
        )

    meta = frappe.get_meta(doctype)
    valid_fields = [f.fieldname for f in meta.fields] + ["name", "owner", "creation", "modified", "docstatus"]
    if status_field not in valid_fields:
        frappe.throw(f"Invalid field: {status_field} on DocType: {doctype}")

    # Project filtering
    from elab_notebook.elab_notebook.api.dashboard import get_dashboard_projects
    allowed_projects = get_dashboard_projects(project)
    
    has_project_field = "project" in valid_fields
    
    where_clauses = []
    query_args = {}
    
    if has_project_field:
        if allowed_projects:
            where_clauses.append("`project` IN %(allowed_projects)s")
            query_args["allowed_projects"] = allowed_projects
        else:
            return {
                "data": [],
                "statuses": []
            }
            
    # Add custom scoping for Experiment Team
    if doctype == "Experiment Team":
        from elab_notebook.permissions import has_bypass
        user = frappe.session.user
        if not has_bypass(user):
            from elab_notebook.elab_notebook.api.experiment_team import get_my_teams
            my_team_names = [t.name for t in get_my_teams()]
            if my_team_names:
                where_clauses.append("`name` IN %(my_team_names)s")
                query_args["my_team_names"] = my_team_names
            else:
                return {
                    "data": [],
                    "statuses": []
                }
    else:
        # The count below is raw SQL, so the permission_query_conditions hooks that
        # scope the matching list view never run against it. Project alone does not
        # isolate a function: two Employee Functions routinely share a project, so
        # without this a function head's card counts another function's templates and
        # experiments - rows that same user cannot open. Applied the way db_query
        # applies them, so the card and the list view answer with the same rows.
        hooks = frappe.get_hooks("permission_query_conditions", {})
        for method in hooks.get(doctype, []) + hooks.get("*", []):
            condition = frappe.call(frappe.get_attr(method), frappe.session.user, doctype=doctype)
            if condition:
                where_clauses.append(f"({condition})")

    where_str = ""
    if where_clauses:
        where_str = "WHERE " + " AND ".join(where_clauses)
        
    # Get possible status options from metadata/database
    status_options = []
    if status_field == "docstatus":
        status_options = ["Draft", "Submitted", "Cancelled"]
    else:
        field_meta = meta.get_field(status_field)
        if field_meta and field_meta.fieldtype == "Select" and field_meta.options:
            status_options = [opt.strip() for opt in field_meta.options.splitlines() if opt.strip()]
            
        if not status_options:
            distinct_vals = frappe.db.get_all(doctype, fields=[status_field], distinct=1)
            status_options = list(set([v.get(status_field) for v in distinct_vals if v.get(status_field)]))
        
    # Execute query
    query = f"""
        SELECT 
            `{status_field}` AS status, 
            YEAR(creation) AS yr,
            MONTH(creation) AS mo,
            COUNT(*) AS count 
        FROM 
            `tab{doctype}` 
        {where_str}
        GROUP BY 
            `{status_field}`, 
            yr,
            mo
    """
    res = frappe.db.sql(query, query_args, as_dict=True)
    
    data = []
    for r in res:
        month_str = f"{r.yr}-{r.mo:02d}" if r.yr and r.mo else "unknown"
        status_val = r.status
        if status_field == "docstatus":
            status_val = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(r.status, "Draft")
            
        data.append({
            "status": status_val or "None",
            "month": month_str,
            "count": r.count
        })
        
    return {
        "data": data,
        "statuses": status_options
    }

@frappe.whitelist()
def get_experiments_list(project=None, workflow_state=None, experiment_category=None):
    from elab_notebook.elab_notebook.api.dashboard import get_dashboard_projects
    allowed_projects = get_dashboard_projects(project)
    
    filters = {}
    if allowed_projects:
        filters["project"] = ("in", allowed_projects)
    else:
        return []
        
    if workflow_state:
        filters["workflow_state"] = workflow_state

    # Same shape as workflow_state above: a blank value is "every level", which is
    # what the list's first, empty option sends. Runs created before the hierarchy
    # existed carry a blank category and are only hidden once a level is picked.
    if experiment_category:
        filters["experiment_category"] = experiment_category

    experiments = frappe.get_all(
        "Lab Experiment",
        fields=["name", "title", "aim", "project", "experiment_category", "workflow_state", "experiment_status", "experiment_start_date", "creation"],
        filters=filters,
        order_by="creation desc"
    )
    return experiments


@frappe.whitelist()
def get_template_experiment_counts():
    """Get experiment counts per template (including zero-count rows)."""
    # Fetch templates user can see
    templates = frappe.get_list("Lab Experiment Template", fields=["name", "template_name"])
    
    # Query experiment counts grouped by template (respects Experiment permissions)
    counts = frappe.get_list(
        "Lab Experiment",
        fields=["experiment_template", "count(name) as count"],
        group_by="experiment_template"
    )
    
    counts_dict = {row.experiment_template: row.count for row in counts if row.experiment_template}
    
    result = []
    for t in templates:
        result.append({
            "template": t.name,
            "template_name": t.template_name,
            "count": counts_dict.get(t.name, 0)
        })
    return result


@frappe.whitelist()
def get_team_experiment_counts():
    """Experiment and Sample counts per team, including zero-count rows."""
    # Fetch teams user can see
    teams = frappe.get_list("Experiment Team", fields=["name", "team_name", "project", "employee_function"])

    # Grouped by the team the run is actually filed under. This used to group by
    # project + employee_function, which is not a team: save_team creates a new
    # record every time, so one project+function pair holds many teams and each
    # of them was handed the pair's whole total. Two teams under one function
    # both reported every run in the pair.
    exp_rows = frappe.get_list(
        "Lab Experiment",
        fields=["name", "experiment_team"],
        limit_page_length=0,
    )
    exp_by_team = {}
    team_of_run = {}
    for row in exp_rows:
        if not row.experiment_team:
            continue
        team_of_run[row.name] = row.experiment_team
        exp_by_team[row.experiment_team] = exp_by_team.get(row.experiment_team, 0) + 1

    # Samples hang off a run, not off a team, so they are counted through the run.
    # Read with get_list rather than a join so the Sample permission query still
    # applies - a count is still a disclosure.
    samples_by_team = {}
    sample_rows = frappe.get_list(
        "Sample",
        fields=["experiment", "count(name) as count"],
        group_by="experiment",
    )
    for row in sample_rows:
        team = team_of_run.get(row.experiment)
        if team:
            samples_by_team[team] = samples_by_team.get(team, 0) + row.count

    return [
        {
            "team": team.name,
            "team_name": team.team_name,
            "project": team.project,
            "employee_function": team.employee_function,
            "count": exp_by_team.get(team.name, 0),
            "sample_count": samples_by_team.get(team.name, 0),
        }
        for team in teams
    ]
