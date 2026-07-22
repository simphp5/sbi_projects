cd C:\Users\simph\Downloads\sbi_projects_live

$enc = New-Object System.Text.UTF8Encoding($false)  # UTF-8 WITHOUT BOM

$f0 = @'
# Copyright (c) 2026, Velmaska and contributors
"""PO annexure workbook + HTML for a fabrication purchase order.

Per-PO (single category): PO by Category, Category Detail, Cutting List
(filtered to that category's section family), and — for the Bolts PO — a
Bolt List. Shipping is dispatch-level (crosses categories) so it appears
only in the full workbook attached to the import document.
"""

import io

from sbi_projects.sbi_projects.steel_bom.parser import _family_of


def build_annexure(data, cats, po_no="PO"):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    NAVY, BLUE, LT, GREY = "1F3864", "1F4E78", "DDEBF7", "F2F2F2"
    H = Font(bold=True, color="FFFFFF", size=10)
    B = Font(bold=True, size=10)
    N = Font(size=10)
    T = Font(bold=True, color="FFFFFF", size=14)
    thin = Border(*[Side("thin", color="B0B0B0")] * 4)
    ctr = Alignment("center", "center", wrap_text=True)
    lft = Alignment("left", "center", wrap_text=True)
    rgt = Alignment("right", "center")
    yel = PatternFill("solid", fgColor="FFF2CC")

    single = len(cats) == 1
    scope = cats[0]["label"] if single else "All Categories"
    wanted_keys = {c.get("key") for c in cats}

    def title(ws, ncol, sub):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        c = ws.cell(1, 1, "SHIV BHARAT INFRASTRUCTURES")
        c.fill = PatternFill("solid", fgColor=NAVY); c.font = T; c.alignment = ctr
        ws.row_dimensions[1].height = 22
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c = ws.cell(2, 1, f"Fabrication PO Annexure  |  {sub}  |  {scope}  |  Ref: {po_no}")
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.font = Font(bold=True, color="FFFFFF", size=10); c.alignment = lft
        return 4

    def head(ws, r, cols):
        for i, (h, w) in enumerate(cols, 1):
            c = ws.cell(r, i, h); c.fill = PatternFill("solid", fgColor=BLUE)
            c.font = H; c.alignment = ctr; c.border = thin
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.row_dimensions[r].height = 24
        return r + 1

    def row(ws, r, vals, al, shade=False):
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v); c.font = N; c.border = thin; c.alignment = al[i - 1]
            if shade:
                c.fill = PatternFill("solid", fgColor=GREY)
            if isinstance(v, float):
                c.number_format = "#,##0.00"
        return r + 1

    # ---- Sheet 1: PO by Category ----
    ws = wb.create_sheet("PO by Category")
    r = title(ws, 5, "Purchase Order")
    r = head(ws, r, [("#", 5), ("Category", 26), ("Item Code", 16),
                     ("Weight (Kg)", 16), ("Rate/Kg (fill)", 16)])
    hdr = r - 1; first = r
    for i, c in enumerate(cats, 1):
        row(ws, r, [i, c["label"], c["item_code"], round(c["weight_kg"], 2), ""],
            [ctr, lft, ctr, rgt, ctr])
        ws.cell(r, 5).fill = yel
        r += 1
    ws.cell(r, 2, "TOTAL").font = B
    tc = ws.cell(r, 4, f"=SUM(D{first}:D{r-1})"); tc.font = B; tc.number_format = "#,##0.00"
    for i in range(1, 6):
        ws.cell(r, i).fill = PatternFill("solid", fgColor=LT); ws.cell(r, i).border = thin
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"

    # ---- Sheet 2: Category Detail (sections) ----
    ws = wb.create_sheet("Category Detail")
    r = title(ws, 5, "Sections")
    r = head(ws, r, [("Category", 24), ("Section", 18), ("Grade / Spec", 30),
                     ("Weight (Kg)", 14), ("Nos", 10)])
    hdr = r - 1
    for ci, c in enumerate(cats):
        span = r
        for s in c["sections"]:
            row(ws, r, [c["label"], s["section"], s.get("grade", ""),
                        round(s["kg"], 2), s.get("nos", "")],
                [lft, lft, lft, rgt, ctr], shade=(ci % 2 == 1))
            r += 1
        if r - span > 1:
            ws.merge_cells(start_row=span, start_column=1, end_row=r - 1, end_column=1)
            ws.cell(span, 1).alignment = Alignment("left", "top", wrap_text=True)
            ws.cell(span, 1).font = B
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"

    # ---- Sheet 3: Cutting List (filtered to these categories) ----
    ws = wb.create_sheet("Cutting List")
    r = title(ws, 6, "Cutting List (Section Details)")
    r = head(ws, r, [("Sl", 5), ("Part Mark", 14), ("Section", 18), ("Grade", 20),
                     ("Cut Length mm", 14), ("Member Type", 20)])
    hdr = r - 1; sl = 0
    for cr in data["cutting"]:
        if _family_of(cr["profile"]) not in wanted_keys:
            continue
        sl += 1
        row(ws, r, [sl, cr["part"], cr["profile"], cr.get("grade", ""),
                    round(float(cr["length"]), 1) if cr["length"] else 0,
                    str(cr.get("member", "")).replace("_", " ").title()],
            [ctr, lft, lft, lft, ctr, lft], shade=(sl % 2 == 0))
        r += 1
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"
    if sl:
        ws.auto_filter.ref = f"A{hdr}:F{r-1}"

    # ---- Sheet 4: Shipping List (full workbook only) ----
    if not single:
        ws = wb.create_sheet("Shipping List")
        r = title(ws, 5, "Shipping List (Dispatch)")
        r = head(ws, r, [("Sl", 5), ("Assembly Mark", 16), ("External Size mm", 22),
                         ("Total Wt kg", 14), ("Member Type", 22)])
        hdr = r - 1; sl = 0
        for sp in data["shipping"]:
            sl += 1
            row(ws, r, [sl, sp["asm"], sp.get("ext", ""),
                        round(float(sp["tot_wt"]), 2) if sp["tot_wt"] else 0,
                        str(sp.get("member", "")).replace("_", " ").title()],
                [ctr, lft, lft, rgt, lft], shade=(sl % 2 == 0))
            r += 1
        ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"

    # ---- Sheet 5: Bolt List (only when bolts category present) ----
    if any(c.get("key") == "BOLTS" for c in cats):
        ws = wb.create_sheet("Bolt List")
        r = title(ws, 5, "Bolt List (bought-out)")
        r = head(ws, r, [("Sl", 5), ("Material Code", 28), ("Qty Nos", 12),
                         ("Total Wt kg", 14), ("Remark", 24)])
        hdr = r - 1; sl = 0
        for b in data["bolt"]:
            sl += 1
            row(ws, r, [sl, b["code"], int(b["qty"]),
                        round(float(b["tot_wt"]), 2) if b["tot_wt"] else 0, b.get("remark", "")],
                [ctr, lft, ctr, rgt, lft], shade=(sl % 2 == 0))
            r += 1
        ws.sheet_view.showGridLines = False

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ======================================================================
# HTML annexure (used by the PO print format AND the PDF attachment)
# ======================================================================
def build_annexure_html(cat, data, po_no="PO"):
    label = cat["label"]
    wanted = cat.get("key")

    th = "background:#1F4E78;color:#fff;padding:4px 6px;text-align:left;border:1px solid #bbb;"
    td = "padding:3px 6px;border:1px solid #ccc;"
    tbl = "border-collapse:collapse;width:100%;font-size:11px;margin:6px 0;"

    secs = "".join(
        f"<tr><td style='{td}'>{s['section']}</td>"
        f"<td style='{td}'>{s.get('grade','')}</td>"
        f"<td style='{td};text-align:right'>{s['kg']:,.2f}</td>"
        f"<td style='{td};text-align:right'>{s.get('nos','') or ''}</td></tr>"
        for s in cat["sections"]
    )

    cut_rows = [c for c in data.get("cutting", []) if _family_of(c["profile"]) == wanted][:80]
    cuts = "".join(
        f"<tr><td style='{td}'>{c['part']}</td>"
        f"<td style='{td}'>{c['profile']}</td>"
        f"<td style='{td};text-align:right'>{(c['length'] or 0):,.0f}</td>"
        f"<td style='{td}'>{str(c.get('member','')).replace('_',' ').title()}</td></tr>"
        for c in cut_rows
    )
    cut_note = "" if len(cut_rows) < 80 else "<p style='font-size:10px'>First 80 cutting lines; full list in the attached annexure.</p>"

    cut_block = ""
    if cuts:
        cut_block = (
            "<h5 style='margin:10px 0 4px'>Cutting reference (part / section / cut length mm / member)</h5>"
            f"<table style='{tbl}'>"
            f"<tr><th style='{th}'>Part Mark</th><th style='{th}'>Section</th>"
            f"<th style='{th}'>Cut Length</th><th style='{th}'>Member</th></tr>"
            f"{cuts}</table>{cut_note}"
        )

    return f"""
<div style="margin-top:14px">
  <h4 style="color:#BE1E2D;margin:8px 0 4px">Annexure — {label} (Ref {po_no})</h4>
  <table style="{tbl}">
    <tr><th style="{th}">Section</th><th style="{th}">Grade / Spec</th>
        <th style="{th}">Weight (Kg)</th><th style="{th}">Nos</th></tr>
    {secs}
  </table>
  {cut_block}
</div>
"""


# ======================================================================
# PDF annexure (single category) - rendered via frappe's wkhtmltopdf
# ======================================================================
def build_annexure_pdf(cat, data, po_no="PO"):
    from frappe.utils.pdf import get_pdf

    body = build_annexure_html(cat, data, po_no=po_no)
    html = (
        "<div style='font-family:sans-serif'>"
        "<h2 style='color:#1F3864;margin:0'>SHIV BHARAT INFRASTRUCTURES</h2>"
        f"<p style='margin:2px 0 10px;color:#555'>Fabrication PO Annexure "
        f"&nbsp;|&nbsp; <b>{cat['label']}</b> &nbsp;|&nbsp; Ref: {po_no} "
        f"&nbsp;|&nbsp; Total: {cat['weight_kg']:,.2f} Kg</p>"
        f"{body}</div>"
    )
    return get_pdf(html)
'@
[System.IO.File]::WriteAllText((Join-Path (Get-Location) "sbi_projects\sbi_projects\steel_bom\annexure.py"), $f0, $enc)

$f1 = @'
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

    if not frappe.db.exists("Print Format", "Fabrication PO"):
        frappe.get_doc({
            "doctype": "Print Format", "name": "Fabrication PO",
            "doc_type": "Purchase Order", "module": "SBI Projects",
            "print_format_type": "Jinja", "standard": "No",
            "html": _PO_PRINT_HTML,
        }).insert(ignore_permissions=True)


_PO_PRINT_HTML = """{{ doc.company }}
<div style="float:right;background:#BE1E2D;color:#fff;padding:6px 12px;border-radius:6px;font-weight:700;font-size:13px">{{ doc.sbi_fab_category or "Fabrication" }}</div><h2 style="margin:4px 0">Purchase Order {{ doc.name }}</h2>
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
'@
[System.IO.File]::WriteAllText((Join-Path (Get-Location) "sbi_projects\sbi_projects\doctype\steel_fabrication_import\steel_fabrication_import.py"), $f1, $enc)

Write-Host "--- 2 files written WITHOUT BOM ---" -ForegroundColor Green

# verify no BOM anywhere in the app
Get-ChildItem -Recurse -Include *.json,*.py,*.js sbi_projects | ForEach-Object {
  $b=[System.IO.File]::ReadAllBytes($_.FullName)
  if ($b.Length -ge 3 -and $b[0]-eq239 -and $b[1]-eq187 -and $b[2]-eq191){ "BOM: $($_.Name)" }
}
"scan done - nothing above = clean"
git add -A
git status --short
