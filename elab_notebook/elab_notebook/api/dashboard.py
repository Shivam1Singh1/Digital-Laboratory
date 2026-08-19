import datetime
import frappe

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
    active_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": ["in", ["Draft", "Saved", "Running"]]})
    completed_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "Completed"})
    pending_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "Pending Approval from System Manager"})
    running_db = frappe.db.count("Lab Experiment", {"project": ["in", allowed_projects], "workflow_state": "Running"})
    
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
            "workflow_state": "Pending Approval from System Manager"
        },
        fields=["name", "workflow_state", "owner", "reviewer", "title"]
    )
    
    pending_temps = frappe.get_all(
        "Experiment Template",
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

@frappe.whitelist()
def get_entity_stats(doctype, status_field, project=None):
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Invalid DocType: {doctype}")
        
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
def get_experiments_list(project=None, workflow_state=None):
    from elab_notebook.elab_notebook.api.dashboard import get_dashboard_projects
    allowed_projects = get_dashboard_projects(project)
    
    filters = {}
    if allowed_projects:
        filters["project"] = ("in", allowed_projects)
    else:
        return []
        
    if workflow_state:
        filters["workflow_state"] = workflow_state
        
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
    templates = frappe.get_list("Experiment Template", fields=["name", "template_name"])
    
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
    """Get experiment counts per team (including zero-count rows)."""
    # Fetch teams user can see
    teams = frappe.get_list("Experiment Team", fields=["name", "team_name", "project", "employee_function"])

    # Query experiment counts by team (grouped by the team itself, not by project+function)
    counts = frappe.get_list(
        "Lab Experiment",
        fields=["project", "employee_function", "count(name) as count"],
        group_by="project, employee_function"
    )

    counts_dict = {}
    for row in counts:
        if row.project and row.employee_function:
            key = (row.project, row.employee_function)
            counts_dict[key] = row.count

    result = []
    for team in teams:
        key = (team.project, team.employee_function)
        count = counts_dict.get(key, 0)
        result.append({
            "team": team.name,
            "team_name": team.team_name,
            "project": team.project,
            "employee_function": team.employee_function,
            "count": count
        })
    return result
