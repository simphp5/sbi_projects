"""Project cost engine: budget vs earned vs actual, per 5 categories.

Basis rules (as decided):
- Customer view shows BILLING VALUE of work done (BOQ rates), never
  internal actual cost - margin stays private.
- Owner view shows Budget (BOQ), Earned value (billing of work done)
  and Actual internal cost per category.
- Labour actual: attendance-days x Labour.daily_wage when an attendance
  doctype is found; otherwise falls back to Site Progress Entry
  labour-hours. Source used is reported in the response.
"""

import re

import frappe
from frappe.utils import flt

CATS = ["labour", "material", "equipment", "subcontract", "other"]

OWNER_ROLES = ("System Manager", "Projects Manager", "Accounts Manager")


# ---------------------------------------------------------------- helpers

def _stage_no(subject):
    m = re.match(r"\s*Stage\s+(\d+)", subject or "", re.I)
    return int(m.group(1)) if m else 999


def _boq(project):
    name = frappe.db.get_value("Project BOQ", {"project": project}, "name")
    if not name:
        return None, []
    items = frappe.get_all(
        "Project BOQ Item", filters={"parent": name},
        fields=["stage", "activity", "unit", "qty", "rate", "amount",
                "labour_amount", "material_amount", "equipment_amount",
                "subcontract_amount", "other_amount"],
        order_by="idx", ignore_permissions=True)
    return name, items


def _progress_done(project):
    """{(stage, activity): qty_done_total}"""
    rows = frappe.get_all(
        "Site Progress Entry", filters={"project": project},
        fields=["stage", "activity", "qty_done"],
        limit_page_length=0, ignore_permissions=True)
    done = {}
    for r in rows:
        key = (r.stage, r.activity)
        done[key] = done.get(key, 0) + flt(r.qty_done)
    return done


def _earned(project):
    """Billing value of work done, per stage and per category.
    line earned = min(done_qty, boq_qty) / boq_qty * boq amounts."""
    _name, items = _boq(project)
    done = _progress_done(project)
    stages = {}
    lines = []
    for it in items:
        q = flt(it.qty)
        dq = min(flt(done.get((it.stage, it.activity), 0)), q)
        ratio = (dq / q) if q else 0.0
        s = stages.setdefault(it.stage, {c: 0.0 for c in CATS})
        s.setdefault("total", 0.0)
        s.setdefault("budget", 0.0)
        s["labour"] += ratio * flt(it.labour_amount)
        s["material"] += ratio * flt(it.material_amount)
        s["equipment"] += ratio * flt(it.equipment_amount)
        s["subcontract"] += ratio * flt(it.subcontract_amount)
        s["other"] += ratio * flt(it.other_amount)
        s["total"] += ratio * flt(it.amount)
        s["budget"] += flt(it.amount)
        if dq:
            lines.append({"stage": it.stage, "activity": it.activity,
                          "unit": it.unit, "boq_qty": q, "done_qty": dq,
                          "value": ratio * flt(it.amount),
                          "labour": ratio * flt(it.labour_amount),
                          "material": ratio * flt(it.material_amount),
                          "equipment": ratio * flt(it.equipment_amount),
                          "subcontract": ratio * flt(it.subcontract_amount),
                          "other": ratio * flt(it.other_amount)})
    return stages, lines


def _labour_actual(project):
    """(amount, source_note). Attendance adapter with progress fallback."""
    wages = {}
    if frappe.db.exists("DocType", "Labour"):
        for r in frappe.get_all("Labour",
                                filters={"default_project": project},
                                fields=["name", "daily_wage"],
                                ignore_permissions=True):
            wages[r.name] = flt(r.get("daily_wage"))
    # find an attendance-like doctype in our module
    try:
        module = frappe.db.get_value("DocType", "Project BOQ", "module")
        cands = frappe.get_all("DocType",
                               filters={"module": module, "istable": 0},
                               pluck="name")
        skip = {"Project BOQ", "Site Resource", "Site Activity",
                "Site Expense Entry", "Site Progress Entry",
                "Site Work Verification", "Site Customer Access", "Labour"}
        for dt in cands:
            if dt in skip:
                continue
            meta = frappe.get_meta(dt)
            lab_f = next((f.fieldname for f in meta.fields
                          if f.fieldtype == "Link"
                          and f.options == "Labour"), None)
            date_f = next((f.fieldname for f in meta.fields
                           if f.fieldtype in ("Date", "Datetime")), None)
            if not lab_f or not date_f:
                continue
            filters = {}
            if meta.has_field("project"):
                filters["project"] = project
            rows = frappe.get_all(dt, filters=filters,
                                  fields=[lab_f, date_f],
                                  limit_page_length=0,
                                  ignore_permissions=True)
            if not rows:
                continue
            days = set()
            for r in rows:
                lab = r.get(lab_f)
                if not filters and lab not in wages:
                    continue
                dv = str(r.get(date_f) or "")[:10]
                days.add((lab, dv))
            amt = sum(wages.get(lab, 0.0) for lab, _d in days)
            if days:
                return amt, "attendance: " + dt + \
                    " (" + str(len(days)) + " man-days)"
    except Exception:
        pass
    # fallback: progress labour hours
    total = 0.0
    hours = 0.0
    prg = frappe.get_all("Site Progress Entry",
                         filters={"project": project}, pluck="name",
                         ignore_permissions=True)
    if prg:
        for r in frappe.get_all("Site Progress Labour",
                                filters={"parent": ["in", prg]},
                                fields=["labour", "hours"],
                                limit_page_length=0,
                                ignore_permissions=True):
            total += (flt(r.hours) / 8.0) * wages.get(r.labour, 0.0)
            hours += flt(r.hours)
    return total, "progress labour hours (" + str(int(hours)) + " hrs)"


def _actuals(project):
    """Internal actual cost per category (owner only)."""
    labour, labour_src = _labour_actual(project)
    material = flt(frappe.db.get_value(
        "Stock Entry",
        {"project": project, "stock_entry_type": "Material Issue",
         "docstatus": 1},
        "sum(total_outgoing_value)"))
    exp = {"Equipment": 0.0, "Subcontract": 0.0, "Other": 0.0}
    for r in frappe.get_all("Site Expense Entry",
                            filters={"project": project},
                            fields=["category", "amount"],
                            limit_page_length=0, ignore_permissions=True):
        cat = "Other" if r.category in ("Transport", "Other") else r.category
        if cat in exp:
            exp[cat] += flt(r.amount)
    return {"labour": labour, "material": material,
            "equipment": exp["Equipment"],
            "subcontract": exp["Subcontract"],
            "other": exp["Other"],
            "labour_source": labour_src}


# ---------------------------------------------------------------- office

@frappe.whitelist()
def get_cost_overview(project):
    """Owner/office: Budget vs Earned (billing) vs Actual (internal)."""
    frappe.only_for(OWNER_ROLES)
    boq_name, items = _boq(project)
    budget = {c: 0.0 for c in CATS}
    budget["total"] = 0.0
    for it in items:
        budget["labour"] += flt(it.labour_amount)
        budget["material"] += flt(it.material_amount)
        budget["equipment"] += flt(it.equipment_amount)
        budget["subcontract"] += flt(it.subcontract_amount)
        budget["other"] += flt(it.other_amount)
        budget["total"] += flt(it.amount)
    stages, _lines = _earned(project)
    actual = _actuals(project)
    earned_total = {c: sum(s[c] for s in stages.values()) for c in CATS}
    earned_total["total"] = sum(s["total"] for s in stages.values())
    stage_rows = [{"stage": k, **v} for k, v in stages.items()]
    stage_rows.sort(key=lambda r: _stage_no(r["stage"]))
    cash_issued = flt(frappe.db.get_value("Site Cash Issue",
                                          {"project": project},
                                          "sum(amount)"))
    cash_spent = flt(frappe.db.get_value(
        "Site Expense Entry",
        {"project": project, "payment_source": "Site Cash"},
        "sum(amount)"))
    tasks = frappe.get_all("Task",
                           filters={"project": project, "is_group": 1},
                           fields=["subject", "status"])
    tasks.sort(key=lambda t: (_stage_no(t.subject), t.subject))
    current_stage = next((t.subject for t in tasks
                          if t.status not in ("Completed", "Cancelled")),
                         None)
    return {"project": project, "boq": boq_name, "budget": budget,
            "earned": earned_total, "actual": actual,
            "stages": stage_rows,
            "cash": {"issued": cash_issued, "spent": cash_spent,
                     "balance": cash_issued - cash_spent},
            "current_stage": current_stage,
            "sales_order": frappe.db.get_value("Project", project,
                                               "sales_order")}


@frappe.whitelist()
def create_customer_link(project, customer_label=None):
    """Create (or return existing) tokenised customer view link."""
    frappe.only_for(OWNER_ROLES)
    existing = frappe.db.get_value("Site Customer Access",
                                   {"project": project, "enabled": 1},
                                   ["name", "token"], as_dict=True)
    if existing:
        return {"url": "/sbi_customer?token=" + existing.token}
    doc = frappe.new_doc("Site Customer Access")
    doc.project = project
    doc.customer_label = customer_label
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"url": "/sbi_customer?token=" + doc.token}


# ------------------------------------------------------------- customer

def build_customer_view(token):
    """Data for the guest customer page. BILLING values only."""
    acc = frappe.db.get_value("Site Customer Access",
                              {"token": token, "enabled": 1},
                              ["project"], as_dict=True)
    if not acc:
        return None
    project = acc.project
    pname = frappe.db.get_value("Project", project, "project_name") or project
    stages, lines = _earned(project)
    tasks = frappe.get_all("Task",
                           filters={"project": project, "is_group": 1},
                           fields=["subject", "status"],
                           ignore_permissions=True)
    tasks.sort(key=lambda t: (_stage_no(t.subject), t.subject))
    stage_rows = []
    for t in tasks:
        s = stages.get(t.subject, {})
        b = flt(s.get("budget"))
        tot = flt(s.get("total"))
        stage_rows.append({"stage": t.subject, "status": t.status,
                           "value": tot, "budget": b,
                           "pct": round(100.0 * tot / b, 1) if b else 0})
    cats = {c: sum(flt(s.get(c, 0)) for s in stages.values()) for c in CATS}
    total = sum(flt(s.get("total", 0)) for s in stages.values())
    vers = frappe.get_all("Site Work Verification",
                          filters={"project": project, "signed": 1},
                          fields=["verify_date", "stage", "customer_name"],
                          order_by="verify_date desc",
                          limit_page_length=15, ignore_permissions=True)
    return {"project_name": pname, "stages": stage_rows,
            "categories": cats, "total": total, "lines": lines,
            "verifications": vers}


@frappe.whitelist()
def complete_stage(project, stage):
    """Office closes the current stage. Next stage opens on site
    automatically. If the project is linked to a Sales Order, office
    then raises the stage invoice via the SO Milestone Invoice button."""
    frappe.only_for(OWNER_ROLES)
    task = frappe.db.get_value("Task",
                               {"project": project, "subject": stage,
                                "is_group": 1}, "name")
    if not task:
        frappe.throw("Stage task not found: " + stage)
    tdoc = frappe.get_doc("Task", task)
    tdoc.status = "Completed"
    tdoc.save(ignore_permissions=True)
    frappe.db.commit()
    so = frappe.db.get_value("Project", project, "sales_order")
    return {"ok": 1, "sales_order": so,
            "next_step": ("Open Sales Order " + so +
                          " and use Create > Milestone Invoice for this "
                          "stage.") if so else
            "No Sales Order linked to this project."}
