import frappe
import zlib

def get_project_seed(proj_name):
    return zlib.adler32(proj_name.encode('utf-8')) % 100

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
    active_db = frappe.db.count("Experiment", {"project": ["in", allowed_projects], "workflow_state": ["in", ["Draft", "Running", "Active"]]})
    completed_db = frappe.db.count("Experiment", {"project": ["in", allowed_projects], "workflow_state": "Completed"})
    pending_db = frappe.db.count("Experiment", {"project": ["in", allowed_projects], "workflow_state": ["in", ["Pending Approval", "In Review"]]})
    running_db = frappe.db.count("Experiment", {"project": ["in", allowed_projects], "workflow_state": "Running"})
    
    # Aggregated mock statistics
    active_mock = 0
    completed_mock = 0
    pending_mock = 0
    running_mock = 0
    
    scientists_set = set()
    instruments_set = set()
    
    for p in allowed_projects:
        seed = get_project_seed(p)
        active_mock += 2 + (seed % 3)
        completed_mock += 15 + (seed % 15)
        pending_mock += 1 + (seed % 2)
        running_mock += 1 + (seed % 2)
        
        num_scientists = 2 + (seed % 3)
        for s_idx in range(num_scientists):
            scientists_set.add(f"Scientist-{seed}-{s_idx}")
            
        num_instruments = 3 + (seed % 4)
        for i_idx in range(num_instruments):
            instruments_set.add(f"Instrument-{seed}-{i_idx}")
            
    return {
        "active": active_mock + active_db,
        "completed": completed_mock + completed_db,
        "pending_approval": pending_mock + pending_db,
        "running": running_mock + running_db,
        "scientists": len(scientists_set) if len(scientists_set) > 0 else 1,
        "instruments": len(instruments_set) if len(instruments_set) > 0 else 1
    }

@frappe.whitelist()
def get_monthly_experiments(project=None):
    allowed_projects = get_dashboard_projects(project)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    completed_trend = [0] * 12
    terminated_trend = [0] * 12
    
    if not allowed_projects:
        return {
            "months": months,
            "completed": completed_trend,
            "terminated": terminated_trend
        }
        
    for p in allowed_projects:
        seed = get_project_seed(p)
        for i in range(12):
            completed_trend[i] += 1 + (seed + i) % 5
            terminated_trend[i] += (seed + i) % 2
            
    return {
        "months": months,
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
        
    passed = 0
    failed = 0
    inconclusive = 0
    
    for p in allowed_projects:
        seed = get_project_seed(p)
        passed += 60 + (seed % 25)
        failed += 5 + (seed % 10)
        inconclusive += 5 + (seed % 10)
        
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
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"]
    
    if not allowed_projects:
        return {
            "months": months,
            "yield": [0.0] * 8
        }
        
    yield_sum = [0.0] * 8
    for p in allowed_projects:
        seed = get_project_seed(p)
        for i in range(8):
            yield_sum[i] += 75.0 + float((seed * (i + 1)) % 150) / 10.0
            
    n = len(allowed_projects)
    return {
        "months": months,
        "yield": [round(y / n, 1) for y in yield_sum]
    }

@frappe.whitelist()
def get_chemical_consumption(project=None):
    allowed_projects = get_dashboard_projects(project)
    chemicals = {
        "Ethanol (99.8%)": {"volume": 0, "unit": "L"},
        "Hydrochloric Acid (1M)": {"volume": 0, "unit": "L"},
        "Sodium Hydroxide (2M)": {"volume": 0, "unit": "L"},
        "Acetonitrile (HPLC)": {"volume": 0, "unit": "L"},
        "Methanol (Anhydrous)": {"volume": 0, "unit": "L"}
    }
    
    if not allowed_projects:
        return [{"name": name, "volume": val["volume"], "unit": val["unit"]} for name, val in chemicals.items()]
        
    for p in allowed_projects:
        seed = get_project_seed(p)
        chemicals["Ethanol (99.8%)"]["volume"] += 100 + (seed % 50) * 10
        chemicals["Hydrochloric Acid (1M)"]["volume"] += 50 + (seed % 30) * 10
        chemicals["Sodium Hydroxide (2M)"]["volume"] += 40 + (seed % 25) * 10
        chemicals["Acetonitrile (HPLC)"]["volume"] += 30 + (seed % 20) * 10
        chemicals["Methanol (Anhydrous)"]["volume"] += 20 + (seed % 15) * 10
        
    return [{"name": name, "volume": val["volume"], "unit": val["unit"]} for name, val in chemicals.items()]

@frappe.whitelist()
def get_recent_experiments(limit=4, project=None):
    if isinstance(limit, str):
        limit = int(limit)
        
    allowed_projects = get_dashboard_projects(project)
    recent = []
    
    if allowed_projects:
        db_exps = frappe.get_all(
            "Experiment",
            fields=["name", "title", "aim", "employee_name", "owner", "workflow_state", "modified", "project"],
            filters={"project": ["in", allowed_projects]},
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
                "progress": 100 if e.workflow_state == "Completed" else 45,
                "updated": "Just now"
            })
            
    if len(recent) < limit and allowed_projects:
        mock_pool = [
            {"name": "CRISPR-Cas9 knockout of APP gene in HEK293 cells", "owner": "Dr. Sarah Connor", "status": "In Review", "progress": 85, "updated": "2 hours ago"},
            {"name": "HPLC analysis of synthetic peptide purification", "owner": "John Doe", "status": "Running", "progress": 45, "updated": "3 hours ago"},
            {"name": "Elution kinetics of monoclonal antibody on Protein A column", "owner": "Dr. Sarah Connor", "status": "Completed", "progress": 100, "updated": "Yesterday"},
            {"name": "Buffer preparation and calibration of pH sensors", "owner": "Alice Smith", "status": "Approved", "progress": 100, "updated": "2 days ago"}
        ]
        for i, p_name in enumerate(allowed_projects):
            if len(recent) >= limit:
                break
            mock_idx = (get_project_seed(p_name) + i) % len(mock_pool)
            item = mock_pool[mock_idx].copy()
            item["id"] = f"EXP-{p_name[:4] if len(p_name) >= 4 else p_name}-{1000 + i}"
            recent.append(item)
            
    return recent[:limit]

@frappe.whitelist()
def get_activity_feed(limit=5, project=None):
    if isinstance(limit, str):
        limit = int(limit)
        
    allowed_projects = get_dashboard_projects(project)
    feed = []
    
    mock_actions = [
        {"user": "Dr. Sarah Connor", "action": "submitted experiment", "target_prefix": "EXP-", "time": "10 mins ago"},
        {"user": "System", "action": "flagged sensor anomaly on", "target_prefix": "Bioreactor #", "time": "45 mins ago"},
        {"user": "John Doe", "action": "started run on", "target_prefix": "EXP-", "time": "1 hour ago"},
        {"user": "Alice Smith", "action": "updated calibration for", "target_prefix": "Spectrophotometer SP-", "time": "3 hours ago"},
        {"user": "Dr. Sarah Connor", "action": "signed and approved", "target_prefix": "EXP-", "time": "Yesterday"}
    ]
    
    if allowed_projects:
        for i in range(limit):
            p_name = allowed_projects[i % len(allowed_projects)]
            seed = get_project_seed(p_name)
            action_idx = (seed + i) % len(mock_actions)
            act = mock_actions[action_idx].copy()
            if act["target_prefix"] == "EXP-":
                act["target"] = f"EXP-{p_name[:4] if len(p_name) >= 4 else p_name}-{100 + i}"
            elif act["target_prefix"] == "Bioreactor #":
                act["target"] = f"Bioreactor #{1 + (seed % 5)}"
            elif act["target_prefix"] == "Spectrophotometer SP-":
                act["target"] = f"Spectrophotometer SP-{1 + (seed % 3)}"
            del act["target_prefix"]
            feed.append(act)
            
    return feed[:limit]

@frappe.whitelist()
def get_upcoming_tasks(project=None):
    allowed_projects = get_dashboard_projects(project)
    tasks = []
    
    mock_tasks = [
        {"text": "Sign off review documentation for ", "done": False},
        {"text": "Calibrate pH meters in Lab for ", "done": False},
        {"text": "Order replenishment of HPLC-grade chemicals for ", "done": True},
        {"text": "Review weekly instrument utilization logs for ", "done": False}
    ]
    
    if allowed_projects:
        for i in range(min(4, len(allowed_projects) * 2)):
            p_name = allowed_projects[i % len(allowed_projects)]
            seed = get_project_seed(p_name)
            task_idx = (seed + i) % len(mock_tasks)
            t = mock_tasks[task_idx].copy()
            t["id"] = i + 1
            t["text"] = t["text"] + p_name
            tasks.append(t)
            
    return tasks
