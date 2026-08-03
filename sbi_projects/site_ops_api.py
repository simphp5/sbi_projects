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


def _cash_balance(project):
    try:
        issued = flt(frappe.db.get_value("Site Cash Issue",
                                         {"project": project},
                                         "sum(amount)"))
        spent = flt(frappe.db.get_value(
            "Site Expense Entry",
            {"project": project, "payment_source": "Site Cash"},
            "sum(amount)"))
        return {"issued": issued, "spent": spent,
                "balance": issued - spent}
    except Exception:
        return {"issued": 0, "spent": 0, "balance": 0}


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
            "warehouses": [w.name for w in warehouses],
            "cash": _cash_balance(project)}


@frappe.whitelist()
def add_expense(project, entry_date, category, description, amount,
                stage=None, equipment_type=None, party=None,
                qty=None, uom=None, rate=None, payment_source=None):
    _check_site_user()
    _stages, current = _get_stage_state(project)
    doc = frappe.new_doc("Site Expense Entry")
    doc.project = project
    doc.entry_date = entry_date or today()
    doc.category = category
    doc.stage = current
    doc.equipment_type = equipment_type if category == "Equipment" else None
    doc.party = party
    doc.payment_source = payment_source or "Site Cash"
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
    return {"expenses": exp, "progress": prg, "materials": mat,
            "cash": _cash_balance(project)}


@frappe.whitelist()
def sign_work(project, customer_name, signature_png, remarks=None):
    """Save a customer-signed work verification for the current stage.
    Signature arrives as a data-url PNG from the canvas pad."""
    _check_site_user()
    if not customer_name or not (customer_name or "").strip():
        frappe.throw("Customer name is required")
    if not signature_png or "," not in signature_png:
        frappe.throw("Signature is empty")
    _stages, current = _get_stage_state(project)
    doc = frappe.new_doc("Site Work Verification")
    doc.project = project
    doc.verify_date = today()
    doc.stage = current
    doc.customer_name = customer_name.strip()
    doc.remarks = remarks
    doc.entered_by = frappe.session.user
    doc.insert(ignore_permissions=True)
    b64 = signature_png.split(",", 1)[1]
    fdoc = frappe.get_doc({"doctype": "File",
                           "file_name": doc.name + "_signature.png",
                           "attached_to_doctype": "Site Work Verification",
                           "attached_to_name": doc.name,
                           "content": b64, "decode": True,
                           "is_private": 1}).insert(ignore_permissions=True)
    doc.db_set("signature_file", fdoc.file_url)
    doc.db_set("signed", 1)
    doc.db_set("signed_at", frappe.utils.now_datetime())
    frappe.db.commit()
    return {"name": doc.name}


@frappe.whitelist()
def list_verifications(project, limit=10):
    _check_site_user()
    return frappe.get_all("Site Work Verification",
                          filters={"project": project, "signed": 1},
                          fields=["name", "verify_date", "stage",
                                  "customer_name"],
                          order_by="creation desc",
                          limit_page_length=int(limit))


@frappe.whitelist()
def get_stage_material(project):
    """Current-stage BOQ material requirement for the site tablet.
    Qty only - required / issued / in stock / shortage. No money."""
    _check_site_user()
    from sbi_projects.boq_procure import compute_stage_rows
    _stages, current = _get_stage_state(project)
    if not current:
        return {"stage": None, "rows": []}
    try:
        rows = compute_stage_rows(project, current)
    except Exception:
        rows = []
    return {"stage": current, "rows": rows}
