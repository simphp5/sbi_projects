# Copyright (c) 2026, Velmaska and contributors

import io

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, add_days

from sbi_projects.sbi_projects.steel_bom.parser import parse_workbook, summary_categories

FAB_GROUP = "Fabricated Steel"


class SteelFabricationImport(Document):
    def validate(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default("Company")


# ======================================================================
# Whitelisted entry point (client "Process BOM" button)
# ======================================================================
@frappe.whitelist()
def process_import(docname):
    doc = frappe.get_doc("Steel Fabrication Import", docname)
    log = []

    try:
        import openpyxl
    except Exception:
        frappe.throw(_("openpyxl is not available on this bench."))

    if not doc.bom_file:
        frappe.throw(_("Attach the Steel BOM file first."))
    content = _get_file_bytes(doc.bom_file)
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    data = parse_workbook(wb, job=doc.po_no, phase="", wastage=flt(doc.wastage_percent))
    cats = summary_categories(data, include_bolts=bool(doc.include_bolts))
    total_kg = sum(c["weight_kg"] for c in cats)
    log.append(f"Parsed {data['totals']['assemblies']} assemblies -> "
               f"{len(cats)} categories, {total_kg:,.2f} kg.")

    company = doc.company
    abbr = frappe.get_cached_value("Company", company, "abbr")

    # receiving warehouse: explicit -> project's -> Stores
    target = doc.target_warehouse
    if not target and doc.project:
        target = frappe.db.get_value("Project", doc.project, "cost_center")  # placeholder check
        target = _project_warehouse(doc.project, abbr)
    if not target:
        target = f"Stores - {abbr}"
    log.append(f"Receiving warehouse: {target}")

    # 1. item group
    _ensure_item_group(FAB_GROUP)

    # 2. category items (generic, reusable, stock, purchased by Kg)
    for c in cats:
        _ensure_item(dict(
            item_code=c["item_code"],
            item_name=f"Fabricated - {c['label']}",
            item_group=FAB_GROUP, stock_uom="Kg",
            is_stock_item=1, is_purchase_item=1, is_sales_item=0,
            gst_hsn_code="7308",
            item_defaults=[dict(company=company, default_warehouse=target)],
        ))
    log.append(f"Category items ready: {len(cats)}")

    # 3. draft Purchase Order (standard purchase, NOT subcontracted)
    po_name = None
    if doc.supplier:
        po_name = _create_draft_po(doc, cats, target, company)
        log.append(f"Draft PO created: {po_name} (fill Rate/kg in ERPNext).")
        log.append("Flow: PO -> Purchase Receipt (GRN) at site -> Purchase Invoice.")
    else:
        log.append("Supplier not set - masters created, PO skipped. "
                   "Set Supplier and press Process BOM again.")

    # 4. attach annexure workbook to the import doc (and PO if created)
    try:
        _attach_annexure(doc, data, cats, po_name)
        log.append("Annexure attached (category detail + cutting + shipping + bolts).")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Annexure failed: {doc.name}")
        log.append("Annexure generation failed (see Error Log).")

    doc.db_set("status", "Processed")
    doc.db_set("total_weight_mt", round(total_kg / 1000.0, 3))
    doc.db_set("category_count", len(cats))
    doc.db_set("bolt_nos", data["totals"]["bolt_nos"])
    if po_name:
        doc.db_set("created_po", po_name)
    doc.db_set("log", "\n".join(log))
    frappe.db.commit()
    return dict(status="ok", po=po_name, log="\n".join(log))


# ======================================================================
# File reading
# ======================================================================
def _get_file_bytes(file_url):
    from frappe.utils.file_manager import get_file
    _name, content = get_file(file_url)
    if isinstance(content, str):
        content = content.encode("latin-1")
    return content


# ======================================================================
# PO
# ======================================================================
def _create_draft_po(doc, cats, target, company):
    po = frappe.new_doc("Purchase Order")
    po.supplier = doc.supplier
    po.company = company
    po.transaction_date = nowdate()
    po.schedule_date = add_days(nowdate(), 30)
    po.is_subcontracted = 0
    if doc.project:
        po.project = doc.project
    for c in cats:
        secs = ", ".join(s["section"] for s in c["sections"][:8])
        if len(c["sections"]) > 8:
            secs += ", ..."
        po.append("items", dict(
            item_code=c["item_code"],
            item_name=f"Fabricated - {c['label']}",
            description=f"{c['label']} - sections: {secs}. See annexure {doc.po_no}.",
            qty=flt(c["weight_kg"]),
            uom="Kg",
            stock_uom="Kg",
            conversion_factor=1,
            rate=0,
            schedule_date=add_days(nowdate(), 30),
            warehouse=target,
            project=doc.project or None,
        ))
    po.insert(ignore_permissions=True)  # stays Draft
    return po.name


# ======================================================================
# Annexure workbook
# ======================================================================
def _attach_annexure(doc, data, cats, po_name):
    from sbi_projects.sbi_projects.steel_bom.annexure import build_annexure

    content = build_annexure(data, cats, po_no=doc.po_no)
    fname = f"Annexure-{doc.po_no}.xlsx"

    _fresh_file(fname, "Steel Fabrication Import", doc.name, content)
    if po_name:
        _fresh_file(fname, "Purchase Order", po_name, content)


def _fresh_file(fname, dt, dn, content):
    for old in frappe.get_all("File", filters={
        "attached_to_doctype": dt, "attached_to_name": dn, "file_name": fname
    }, pluck="name"):
        frappe.delete_doc("File", old, ignore_permissions=True, force=True)
    frappe.get_doc({
        "doctype": "File", "file_name": fname,
        "attached_to_doctype": dt, "attached_to_name": dn,
        "is_private": 1, "content": content,
    }).insert(ignore_permissions=True)


# ======================================================================
# Idempotent helpers
# ======================================================================
def _ensure_item_group(name):
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc(dict(doctype="Item Group", item_group_name=name,
                            parent_item_group="All Item Groups", is_group=0)).insert()


def _ensure_item(payload):
    if frappe.db.exists("Item", payload["item_code"]):
        return payload["item_code"]
    payload["doctype"] = "Item"
    frappe.get_doc(payload).insert()
    return payload["item_code"]


def _project_warehouse(project, abbr):
    name = frappe.db.get_value("Project", project, "project_name")
    wh = f"{name} - {abbr}"
    return wh if frappe.db.exists("Warehouse", wh) else None
