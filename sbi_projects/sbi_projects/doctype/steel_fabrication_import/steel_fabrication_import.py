# Copyright (c) 2026, Velmaska and contributors

import io
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, add_days

from sbi_projects.sbi_projects.steel_bom.parser import parse_workbook, summary_categories
from sbi_projects.sbi_projects.steel_bom.annexure import (
    build_annexure, build_annexure_html, build_annexure_pdf)

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
    target = doc.target_warehouse or _project_warehouse(doc.project, abbr) or f"Stores - {abbr}"
    cost_center = frappe.db.get_value("Project", doc.project, "cost_center") if doc.project else None
    if not cost_center:
        cost_center = frappe.db.get_value("Company", company, "cost_center")
    log.append(f"Receiving warehouse: {target} | Cost center: {cost_center}")

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
        po_name = _create_category_po(doc, c, data, target, company, cost_center)
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
def _create_category_po(doc, cat, data, target, company, cost_center):
    po = frappe.new_doc("Purchase Order")
    if doc.supplier:
        po.supplier = doc.supplier
    po.company = company
    po.transaction_date = nowdate()
    po.schedule_date = add_days(nowdate(), 30)
    po.is_subcontracted = 0
    po.project = doc.project
    po.title = cat["label"]
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
            cost_center=cost_center,
            project=doc.project,
        ))
    try:
        po.insert(ignore_permissions=True, ignore_mandatory=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PO create failed: {cat['label']}")
        return None

    # attach this category's annexure to the PO, Excel + PDF (both filtered
    # to just this category, since each category may go to a different supplier)
    tag = cat["item_code"].replace("FAB-", "")
    try:
        xls = build_annexure(data, [cat], po_no=doc.name)
        _fresh_file(f"Annexure-{tag}.xlsx", "Purchase Order", po.name, xls)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PO Excel annexure failed: {po.name}")
    try:
        pdf = build_annexure_pdf(cat, data, po_no=doc.name)
        _fresh_file(f"Annexure-{tag}.pdf", "Purchase Order", po.name, pdf)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"PO PDF annexure failed: {po.name}")
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
                 "fieldtype": "Data", "insert_after": "company", "read_only": 1, "bold": 1, "in_list_view": 1},
                {"fieldname": "sbi_fab_annexure", "label": "Fabrication Annexure",
                 "fieldtype": "Long Text", "insert_after": "sbi_fab_category",
                 "read_only": 1, "hidden": 1, "print_hide": 1},
            ]
        }, ignore_validate=True)
    else:
        # move the category field to the right column if it was created earlier on the left
        if frappe.db.get_value("Custom Field", "Purchase Order-sbi_fab_category", "insert_after") != "company":
            frappe.db.set_value("Custom Field", "Purchase Order-sbi_fab_category", "insert_after", "company")
            frappe.clear_cache(doctype="Purchase Order")

    # upsert the print format so the latest design always applies
    if frappe.db.exists("Print Format", "Fabrication PO"):
        pf = frappe.get_doc("Print Format", "Fabrication PO")
        pf.html = _PO_PRINT_HTML
        pf.print_format_type = "Jinja"
        pf.standard = "No"
        pf.save(ignore_permissions=True)
    else:
        frappe.get_doc({
            "doctype": "Print Format", "name": "Fabrication PO",
            "doc_type": "Purchase Order", "module": "SBI Projects",
            "print_format_type": "Jinja", "standard": "No",
            "html": _PO_PRINT_HTML,
        }).insert(ignore_permissions=True)


_PO_PRINT_HTML = """
<div style="font-family:'Helvetica Neue',Arial,sans-serif;color:#1a1a1a;font-size:12px">

  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              border-bottom:3px solid #BE1E2D;padding-bottom:10px;margin-bottom:14px">
    <div>
      <div style="font-size:20px;font-weight:800;color:#BE1E2D;letter-spacing:.3px">
        SHIV BHARAT INFRASTRUCTURES</div>
      <div style="font-size:10px;color:#666;margin-top:2px">
        Pre-Engineered Buildings &amp; Civil Construction</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:16px;font-weight:700">PURCHASE ORDER</div>
      <div style="font-size:12px;color:#BE1E2D;font-weight:600">{{ doc.name }}</div>
      <div style="font-size:10px;color:#888;margin-top:2px">
        {% if doc.docstatus == 0 %}DRAFT{% elif doc.docstatus == 1 %}SUBMITTED{% else %}CANCELLED{% endif %}</div>
    </div>
  </div>

  <table style="width:100%;font-size:11px;margin-bottom:14px">
    <tr>
      <td style="width:50%;vertical-align:top;padding-right:12px">
        <div style="color:#888;font-size:10px;text-transform:uppercase">Supplier</div>
        <div style="font-weight:700;font-size:13px">{{ doc.supplier_name or doc.supplier or "â€” to be selected â€”" }}</div>
        {% if doc.address_display %}<div style="color:#555;margin-top:2px">{{ doc.address_display }}</div>{% endif %}
      </td>
      <td style="width:25%;vertical-align:top">
        <div style="color:#888;font-size:10px;text-transform:uppercase">Fabrication Category</div>
        <div style="font-weight:700;color:#BE1E2D">{{ doc.sbi_fab_category or "â€”" }}</div>
        <div style="color:#888;font-size:10px;text-transform:uppercase;margin-top:6px">Project / Site</div>
        <div>{{ doc.project or "â€”" }}</div>
      </td>
      <td style="width:25%;vertical-align:top">
        <div style="color:#888;font-size:10px;text-transform:uppercase">Order Date</div>
        <div>{{ frappe.format(doc.transaction_date, {"fieldtype": "Date"}) }}</div>
        <div style="color:#888;font-size:10px;text-transform:uppercase;margin-top:6px">Required By</div>
        <div>{{ frappe.format(doc.schedule_date, {"fieldtype": "Date"}) }}</div>
      </td>
    </tr>
  </table>

  <table style="width:100%;border-collapse:collapse;font-size:11px">
    <thead>
      <tr style="background:#1F3864;color:#fff">
        <th style="padding:7px 6px;text-align:center;width:32px">#</th>
        <th style="padding:7px 6px;text-align:left">Item / Section</th>
        <th style="padding:7px 6px;text-align:right;width:90px">Qty (Kg)</th>
        <th style="padding:7px 6px;text-align:right;width:80px">Rate/Kg</th>
        <th style="padding:7px 6px;text-align:right;width:100px">Amount</th>
      </tr>
    </thead>
    <tbody>
      {% for r in doc.items %}
      <tr style="{% if loop.index is odd %}background:#F7F9FC{% endif %}">
        <td style="padding:6px;text-align:center;border-bottom:1px solid #e5e5e5">{{ loop.index }}</td>
        <td style="padding:6px;border-bottom:1px solid #e5e5e5">{{ r.item_name }}</td>
        <td style="padding:6px;text-align:right;border-bottom:1px solid #e5e5e5">{{ "{:,.2f}".format(r.qty) }}</td>
        <td style="padding:6px;text-align:right;border-bottom:1px solid #e5e5e5">{{ "{:,.2f}".format(r.rate) }}</td>
        <td style="padding:6px;text-align:right;border-bottom:1px solid #e5e5e5">{{ "{:,.2f}".format(r.amount) }}</td>
      </tr>
      {% endfor %}
    </tbody>
    <tfoot>
      <tr style="background:#f0f2f5;font-weight:700">
        <td colspan="2" style="padding:7px 6px;text-align:right">TOTAL</td>
        <td style="padding:7px 6px;text-align:right">{{ "{:,.2f}".format(doc.total_qty) }}</td>
        <td></td>
        <td style="padding:7px 6px;text-align:right">{{ doc.get_formatted("total") }}</td>
      </tr>
    </tfoot>
  </table>

  {% if doc.taxes %}
  <table style="width:45%;margin-left:55%;margin-top:8px;font-size:11px;border-collapse:collapse">
    {% for t in doc.taxes %}
    <tr>
      <td style="padding:3px 6px;color:#555">{{ t.description }}</td>
      <td style="padding:3px 6px;text-align:right">{{ t.get_formatted("tax_amount") }}</td>
    </tr>
    {% endfor %}
    <tr style="border-top:2px solid #BE1E2D;font-weight:800">
      <td style="padding:6px;color:#BE1E2D">GRAND TOTAL</td>
      <td style="padding:6px;text-align:right;color:#BE1E2D">{{ doc.get_formatted("grand_total") }}</td>
    </tr>
  </table>
  {% else %}
  <table style="width:45%;margin-left:55%;margin-top:8px;font-size:11px;border-collapse:collapse">
    <tr style="border-top:2px solid #BE1E2D;font-weight:800">
      <td style="padding:6px;color:#BE1E2D">GRAND TOTAL</td>
      <td style="padding:6px;text-align:right;color:#BE1E2D">{{ doc.get_formatted("grand_total") }}</td>
    </tr>
  </table>
  {% endif %}

  <div style="clear:both;margin-top:20px;font-size:10px;color:#777;border-top:1px solid #ddd;padding-top:8px">
    <b>Note:</b> Detailed section list, cutting reference and technical annexure for
    <b>{{ doc.sbi_fab_category or "this category" }}</b> are provided as a separate attachment
    (Excel &amp; PDF) with this order. Rates are per kilogram of fabricated steel delivered to site.
  </div>

  <table style="width:100%;margin-top:26px;font-size:11px">
    <tr>
      <td style="width:50%;padding-top:30px">_______________________________<br><span style="color:#888">Prepared By</span></td>
      <td style="width:50%;padding-top:30px;text-align:right">_______________________________<br><span style="color:#888">Authorised Signatory</span></td>
    </tr>
  </table>

</div>
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