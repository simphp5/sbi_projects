"""Site operations API for the /sbi_ops PWA page.

Sequential stage rule: only the CURRENT stage (first stage task,
by stage number, whose Task status is not Completed) is workable.
Office closes a stage by setting its Task status to Completed;
the next stage then opens automatically on site.

No budget or money aggregates are ever returned to site users.
"""

import json
import re

import frappe
from frappe.utils import flt, today


def _check_site_user():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def _stage_no(subject):
    m = re.match(r"\s*Stage\s+(\d+)", subject or "", re.I)
    return int(m.group(1)) if m else 999


def _get_stage_state(project):
    """Return (ordered stage list with status, current stage subject)."""
    tasks = frappe.get_all("Task",
                           filters={"project": project, "is_group": 1},
                           fields=["subject", "status"])
    tasks.sort(key=lambda t: (_stage_no(t.subject), t.subject))
    current = None
    for t in tasks:
        if t.status not in ("Completed", "Cancelled"):
            current = t.subject
            break
    stages = [{"stage": t.subject, "status": t.status,
               "is_current": 1 if t.subject == current else 0}
              for t in tasks]
    return stages, current


@frappe.whitelist()
def get_bootstrap(project):
    """Everything the ops page needs on load. Qty only, no amounts."""
    _check_site_user()
    stages, current = _get_stage_state(project)

    activities = []
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name")
    if boq and current:
        items = frappe.get_all("Project BOQ Item",
                               filters={"parent": boq, "stage": current},
                               fields=["activity", "unit", "qty"],
                               order_by="idx")
        activities = [{"activity": it.activity, "unit": it.unit,
                       "qty": it.qty} for it in items]

    workers = frappe.get_all("Labour",
                             filters={"default_project": project},
                             fields=["name", "labour_name"],
                             order_by="labour_name") \
        if frappe.db.exists("DocType", "Labour") else []

    warehouses = frappe.get_all("Warehouse",
                                filters={"is_group": 0, "disabled": 0},
                                fields=["name"], order_by="name")
    pname = frappe.db.get_value("Project", project, "project_name") or project
    return {"project": project, "project_name": pname,
            "stages": stages, "current_stage": current,
            "activities": activities, "workers": workers,
            "warehouses": [w.name for w in warehouses]}


@frappe.whitelist()
def add_expense(project, entry_date, category, description, amount,
                stage=None, equipment_type=None, party=None,
                qty=None, uom=None, rate=None):
    _check_site_user()
    _stages, current = _get_stage_state(project)
    doc = frappe.new_doc("Site Expense Entry")
    doc.project = project
    doc.entry_date = entry_date or today()
    doc.category = category
    doc.stage = current
    doc.equipment_type = equipment_type if category == "Equipment" else None
    doc.party = party
    doc.description = description
    doc.qty = flt(qty)
    doc.uom = uom
    doc.rate = flt(rate)
    doc.amount = flt(amount) or (flt(qty) * flt(rate))
    doc.entered_by = frappe.session.user
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def add_progress(project, entry_date, qty_done=None,
                 activity=None, remarks=None, labours=None):
    _check_site_user()
    _stages, current = _get_stage_state(project)
    if not current:
        frappe.throw("All stages are completed. Ask office to open a stage.")
    doc = frappe.new_doc("Site Progress Entry")
    doc.project = project
    doc.entry_date = entry_date or today()
    doc.stage = current
    doc.activity = activity
    doc.qty_done = flt(qty_done)
    doc.remarks = remarks
    if labours:
        if isinstance(labours, str):
            labours = json.loads(labours)
        for row in labours:
            doc.append("labours", {"labour": row.get("labour"),
                                   "hours": flt(row.get("hours") or 8)})
    doc.entered_by = frappe.session.user
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def get_items(warehouse):
    """Items with stock in the given warehouse. Qty only, no valuation."""
    _check_site_user()
    bins = frappe.get_all("Bin", filters={"warehouse": warehouse,
                                          "actual_qty": [">", 0]},
                          fields=["item_code", "actual_qty", "stock_uom"],
                          order_by="item_code", limit_page_length=200)
    return bins


@frappe.whitelist()
def material_issue(project, warehouse, item_code, qty):
    """Create a submitted Material Issue stock entry against the project.
    FIFO valuation applies automatically; cost never returned to site."""
    _check_site_user()
    _stages, current = _get_stage_state(project)
    se = frappe.new_doc("Stock Entry")
    se.stock_entry_type = "Material Issue"
    se.purpose = "Material Issue"
    se.project = project
    se.append("items", {"item_code": item_code, "qty": flt(qty),
                        "s_warehouse": warehouse})
    if current:
        se.remarks = "Stage: " + current
    se.insert(ignore_permissions=True)
    se.submit()
    frappe.db.commit()
    return {"name": se.name}


@frappe.whitelist()
def list_today(project, entry_date=None):
    """Entries made today - shown back for confirmation."""
    _check_site_user()
    d = entry_date or today()
    exp = frappe.get_all("Site Expense Entry",
                         filters={"project": project, "entry_date": d},
                         fields=["name", "category", "description", "amount"],
                         order_by="creation desc")
    prg = frappe.get_all("Site Progress Entry",
                         filters={"project": project, "entry_date": d},
                         fields=["name", "stage", "activity", "qty_done"],
                         order_by="creation desc")
    mat = frappe.get_all("Stock Entry",
                         filters={"project": project, "posting_date": d,
                                  "stock_entry_type": "Material Issue",
                                  "docstatus": 1},
                         fields=["name"], order_by="creation desc")
    return {"expenses": exp, "progress": prg, "materials": mat}
