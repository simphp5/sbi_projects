"""Stage-wise material planning and procurement.

For the given project stage: required qty per stock Item comes from
BOQ line qty x Site Activity coefficients (Material resources linked
to Items). Compared against issued-so-far and warehouse stock to give
a shortage list ("RFQ view"), from which draft Purchase Orders (per
default supplier) and a Material Request (items with no supplier) are
created - all carrying 'Site: <name> | Stage: <stage>' text.
"""

import frappe
from frappe.utils import add_days, flt, today

OWNER_ROLES = ("System Manager", "Projects Manager", "Purchase Manager",
               "Purchase User", "Accounts Manager")


def _current_stage(project):
    import re
    tasks = frappe.get_all("Task",
                           filters={"project": project, "is_group": 1},
                           fields=["subject", "status"])

    def keyf(t):
        m = re.match(r"\s*Stage\s+(\d+)", t.subject or "", re.I)
        return (int(m.group(1)) if m else 999, t.subject)
    tasks.sort(key=keyf)
    for t in tasks:
        if t.status not in ("Completed", "Cancelled"):
            return t.subject
    return None


def compute_stage_rows(project, stage):
    """Qty-only requirement rows for one stage (no money - safe for site)."""
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name")
    if not boq:
        frappe.throw("No Project BOQ found. Import the BOQ first.")
    filters = {"parent": boq}
    if stage:
        filters["stage"] = stage
    lines = frappe.get_all("Project BOQ Item", filters=filters,
                           fields=["activity", "qty"], limit_page_length=0)
    req = {}
    for ln in lines:
        for r in frappe.get_all("Site Activity Resource",
                                filters={"parent": ln.activity},
                                fields=["resource", "coefficient"],
                                limit_page_length=0):
            res = frappe.db.get_value(
                "Site Resource", r.resource,
                ["category", "item", "unit", "min_stock"], as_dict=True)
            if not res or res.category != "Material" or not res.item:
                continue
            e = req.setdefault(res.item, {"item": res.item,
                                          "resource": r.resource,
                                          "uom": res.unit,
                                          "min_stock": flt(res.min_stock),
                                          "required": 0.0})
            e["required"] += flt(ln.qty) * flt(r.coefficient)

    out = []
    for item, e in req.items():
        stock = flt(frappe.db.get_value("Bin", {"item_code": item},
                                        "sum(actual_qty)"))
        issued = flt(frappe.db.sql(
            """select sum(sed.qty) from `tabStock Entry Detail` sed
               join `tabStock Entry` se on se.name = sed.parent
               where se.docstatus = 1 and se.project = %s
                 and se.stock_entry_type = 'Material Issue'
                 and sed.item_code = %s""", (project, item))[0][0])
        pending = max(0.0, e["required"] - issued)
        shortage = max(0.0, pending + e["min_stock"] - stock)
        out.append({"item": item, "uom": e["uom"],
                    "required": round(e["required"], 3),
                    "issued": round(issued, 3),
                    "in_stock": round(stock, 3),
                    "min_stock": e["min_stock"],
                    "shortage": round(shortage, 3)})
    out.sort(key=lambda x: -x["shortage"])
    return out


@frappe.whitelist()
def stage_material_status(project, stage=None):
    """Office view: requirement vs issued vs stock per Item."""
    frappe.only_for(OWNER_ROLES)
    stage = stage or _current_stage(project)
    return {"stage": stage, "rows": compute_stage_rows(project, stage)}


@frappe.whitelist()
def make_stage_procurement(project, stage=None, warehouse=None):
    """Create draft POs (grouped by item default supplier) and one
    Material Request for shortage items without a supplier."""
    frappe.only_for(OWNER_ROLES)
    status = stage_material_status(project, stage)
    stage = status["stage"]
    shortages = [r for r in status["rows"] if flt(r["shortage"]) > 0]
    if not shortages:
        return {"message": "No shortages - stock is sufficient.",
                "pos": [], "mr": None}
    pname = frappe.db.get_value("Project", project, "project_name") or project
    tag = "Site: " + pname + " | Stage: " + (stage or "All")
    company = frappe.db.get_single_value("Global Defaults",
                                         "default_company")
    by_sup = {}
    no_sup = []
    for r in shortages:
        sup = frappe.db.get_value("Item Default", {"parent": r["item"]},
                                  "default_supplier")
        if sup:
            by_sup.setdefault(sup, []).append(r)
        else:
            no_sup.append(r)

    pos = []
    for sup, rows in by_sup.items():
        po = frappe.new_doc("Purchase Order")
        po.supplier = sup
        if company:
            po.company = company
        po.project = project
        po.remarks = tag
        for r in rows:
            po.append("items", {"item_code": r["item"],
                                "qty": flt(r["shortage"]),
                                "schedule_date": add_days(today(), 7),
                                "warehouse": warehouse or None,
                                "project": project})
        po.insert(ignore_permissions=True)
        pos.append(po.name)

    mr_name = None
    if no_sup:
        mr = frappe.new_doc("Material Request")
        mr.material_request_type = "Purchase"
        if company:
            mr.company = company
        mr.remarks = tag
        for r in no_sup:
            mr.append("items", {"item_code": r["item"],
                                "qty": flt(r["shortage"]),
                                "schedule_date": add_days(today(), 7),
                                "warehouse": warehouse or None,
                                "project": project})
        mr.insert(ignore_permissions=True)
        mr_name = mr.name

    frappe.db.commit()
    return {"message": str(len(pos)) + " draft PO(s)" +
            (" + 1 Material Request" if mr_name else "") +
            " created with tag [" + tag + "]",
            "pos": pos, "mr": mr_name, "shortage_count": len(shortages)}
