# Copyright (c) 2026, Velmaska and contributors

import io
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, add_days

from sbi_projects.sbi_projects.steel_bom.parser import parse_workbook, summary_categories
from sbi_projects.sbi_projects.steel_bom.annexure import build_annexure, build_annexure_html

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

    _ensure_po_customisations()

    data = parse_workbook(wb, job=doc.name, phase="", wastage=flt(doc.wastage_percent))
    cats = summary_categories(data, include_bolts=bool(doc.include_bolts))
    total_kg = sum(c["weight_kg"] for c in cats)
    log.append(f"Parsed {data['totals']['assemblies']} assemblies -> "
               f"{len(cats)} categories, {total_kg:,.2f} kg.")

    company = doc.company
    abbr = frappe.get_cached_value("Company", company, "abbr")
    target = _project_warehouse(doc.project, abbr) or f"Stores - {abbr}"
    log.append(f"Receiving warehouse: {target}")

    _ensure_item_group(FAB_GROUP)

    # clear previous rows (re-run safe)
    doc.set("created_pos", [])

    made = 0
    for c in cats:
        # 1. section-level items for this category
        for s in c["sections"]:
            _ensure_item(dict(
                item_code=_item_code(s["section"]),
                item_name=f"{s['section']} - {c['label']}",
                item_group=FAB_GROUP, stock_uom="Kg",
                is_stock_item=1, is_purchase_item=1, is_sales_item=0,
                gst_hsn_code="7308",
                item_defaults=[dict(company=company, default_warehouse=target)],
            ))
        # 2. one draft PO for this category
        po_name = _create_category_po(doc, c, data, target, company)
        if po_name:
            made += 1
            doc.append("created_pos", dict(
                category=c["label"], purchase_order=po_name,
                section_count=len(c["sections"]), weight_kg=c["weight_kg"]))
            log.append(f"PO {po_name}: {c['label']} ({len(c['sections'])} lines, {c['weight_kg']:,.1f} kg)")

    # 3. attach the full workbook annexure to the import doc
    try:
        content_x = build_annexure(data, cats, po_no=doc.name)
        _fresh_file(f"Annexure-{doc.name}.xlsx", "Steel Fabrication Import", doc.name, content_x)
        log.append("Full annexure workbook attached to this import.")
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Annexure workbook failed: {doc.name}")

    doc.status = "Processed"
    doc.total_weight_mt = round(total_kg / 1000.0, 3)
    doc.po_count = made
    doc.bolt_nos = data["totals"]["bolt_nos"]
    doc.log = "\n".join(log)
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return dict(status="ok", po_count=made, log="\n".join(log))


# ======================================================================
# PO per category (section lines). Supplier optional -> ignore_mandatory.
# ======================================================================
def _create_category_po(doc, cat, data, target, company):
    po = frappe.new_doc("Purchase Order")
    if doc.supplier:
        po.supplier = doc.supplier
    po.company = company
    po.transaction_date = nowdate()
    po.schedule_date = add_days(nowdate(), 30)
    po.is_subcontracted = 0
    po.project = doc.project
    po.sbi_fab_category = cat["label"]
    po.sbi_fab_annexure = build_annexure_html(cat, data, po_no=doc.name)

    for s in cat["sections"]:
        po.append("items", dict(
            item_code=_item_code(s["section"]),
            item_name=f"{s['section']} - {cat['label']}",
            description=f"{cat['label']} | {s['section']} | {s.get('grade','')}",
            qty=flt(s["kg"]),
            uom="Kg", stock_uom="Kg", conversion_factor=1,
            rate=0,
            schedule_date=add_days(nowdate(), 30),
            warehouse=target,
            project=doc.project,
        ))
    try:
        po.insert(ignore_permissions=True, ignore_mandatory=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PO create failed: {cat['label']}")
        return None

    # attach this category's slim annexure to the PO
    try:
        content_x = build_annexure(data, [cat], po_no=doc.name)
        _fresh_file(f"Annexure-{cat['item_code']}.xlsx", "Purchase Order", po.name, content_x)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PO annexure failed: {po.name}")
    return po.name


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
# PO customisations (custom fields + print format), created on first run
# ======================================================================
def _ensure_po_customisations():
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    if not frappe.db.exists("Custom Field", "Purchase Order-sbi_fab_annexure"):
        create_custom_fields({
            "Purchase Order": [
                {"fieldname": "sbi_fab_category", "label": "Fabrication Category",
                 "fieldtype": "Data", "insert_after": "project", "read_only": 1},
                {"fieldname": "sbi_fab_annexure", "label": "Fabrication Annexure",
                 "fieldtype": "Long Text", "insert_after": "sbi_fab_category",
                 "read_only": 1, "hidden": 1, "print_hide": 1},
            ]
        }, ignore_validate=True)

    if not frappe.db.exists("Print Format", "Fabrication PO"):
        frappe.get_doc({
            "doctype": "Print Format", "name": "Fabrication PO",
            "doc_type": "Purchase Order", "module": "SBI Projects",
            "print_format_type": "Jinja", "standard": "No",
            "html": _PO_PRINT_HTML,
        }).insert(ignore_permissions=True)


_PO_PRINT_HTML = """{{ doc.company }}
<h2 style="margin:4px 0">Purchase Order {{ doc.name }}</h2>
<p><b>Category:</b> {{ doc.sbi_fab_category or "" }} &nbsp;|&nbsp;
<b>Supplier:</b> {{ doc.supplier_name or doc.supplier or "(to be selected)" }} &nbsp;|&nbsp;
<b>Project:</b> {{ doc.project or "" }} &nbsp;|&nbsp; <b>Date:</b> {{ doc.transaction_date }}</p>
<table style="border-collapse:collapse;width:100%;font-size:11px">
<tr>
<th style="border:1px solid #bbb;padding:4px">#</th>
<th style="border:1px solid #bbb;padding:4px">Item</th>
<th style="border:1px solid #bbb;padding:4px">Qty (Kg)</th>
<th style="border:1px solid #bbb;padding:4px">Rate/Kg</th>
<th style="border:1px solid #bbb;padding:4px">Amount</th>
</tr>
{% for r in doc.items %}
<tr>
<td style="border:1px solid #ccc;padding:3px">{{ loop.index }}</td>
<td style="border:1px solid #ccc;padding:3px">{{ r.item_name }}</td>
<td style="border:1px solid #ccc;padding:3px;text-align:right">{{ "{:,.2f}".format(r.qty) }}</td>
<td style="border:1px solid #ccc;padding:3px;text-align:right">{{ "{:,.2f}".format(r.rate) }}</td>
<td style="border:1px solid #ccc;padding:3px;text-align:right">{{ "{:,.0f}".format(r.amount) }}</td>
</tr>
{% endfor %}
<tr>
<td colspan="4" style="border:1px solid #bbb;padding:4px;text-align:right"><b>Total</b></td>
<td style="border:1px solid #bbb;padding:4px;text-align:right"><b>{{ "{:,.0f}".format(doc.total) }}</b></td>
</tr>
</table>
{{ doc.sbi_fab_annexure or "" }}
"""


# ======================================================================
# Idempotent helpers
# ======================================================================
def _item_code(section):
    return "FAB-" + re.sub(r"[^A-Z0-9.]", "-", str(section).upper())[:40]


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
    if not project:
        return None
    name = frappe.db.get_value("Project", project, "project_name")
    wh = f"{name} - {abbr}"
    return wh if frappe.db.exists("Warehouse", wh) else None


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
