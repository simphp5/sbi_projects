cd C:\\Users\\simph\\Downloads\\sbi_projects_live

$f0 = @'
# Copyright (c) 2026, Velmaska and contributors
"""Tekla Steel BOM (xlsx) parser for SBI subcontracting.

Pure-python, no Frappe dependency, so it can be unit-tested standalone.
Reads a Tekla detailing BOM export and returns a normalized structure:
raw materials, finished-good categories, per-category BOM lines, plus the
cutting / shipping / bolt lists for the PO annexure.
"""

import re
from collections import defaultdict

# Column map for the ASSM sheet (1-indexed), data starts at DATA_ROW.
DATA_ROW = 18
COL = dict(asm=2, part=3, qty=4, profile=5, material=7, length=8,
           unit_wt=9, total_wt=10, area=11, desc=12)

# Service grouping: which member categories are built-up vs secondary vs misc.
BUILTUP = {"COLUMN", "CRANE_BEAM", "RAFTER", "JACK_BEAM", "PORTAL_COLUMN",
           "PORTAL_BEAM", "MEZZ_BEAM", "MEZZ_JOIST", "EW_COLUMN", "TIE_BEAM",
           "EW_RAFTER", "BEAM", "LANDING_BEAM", "LANDING_COLUMN", "STRINGER"}
SECONDARY = {"PURLIN", "GIRT", "SAGROD", "FLANGE_BRACE", "EAVE_STRUT",
             "ROD_BRACE", "ANGLE_BRACING", "STRUT_TUBE", "BEND_SAGROD",
             "SAG_ROD_CHANNEL", "RM_RAFTER", "RM_COLUMN", "RM_STUB_POST",
             "FOJAMB", "FOHEADER", "STAIR_HAND_RAIL", "STAIR__TREAD",
             "CHEQRD_PLATE"}

GRADE_SPEC = {
    "A572GR50": "IS 2062 E350", "A36": "IS 2062 E250",
    "A653GR50": "ASTM A653M SS Gr.50 GI", "A500GRB": "ASTM A500 Gr.B",
    "GR4.6GI": "Gr 4.6 GI Rod", "A36_CHQD": "IS 2062 E250 Chequered",
    "S275JR": "S275JR",
}

SERVICE_ITEMS = {
    "BUILTUP": ("SVC-FAB-BUILTUP", "Fabrication - Built-Up Members"),
    "SECONDARY": ("SVC-FAB-SECONDARY", "Fabrication - Secondary Members"),
    "MISC": ("SVC-FAB-MISC", "Fabrication - Cleats & Loose Plates"),
}


def _norm_profile(p):
    """Collapse Tekla profile (with width) to a purchasable section code."""
    p = str(p).strip().upper().replace(" ", "")
    m = re.match(r"^PL([\d.]+)\*", p) or re.match(r"^PL([\d.]+)$", p)
    if m:
        return "PL" + m.group(1)
    m = re.match(r"^(\d+[ZC][\d.]+)-", p)
    if m:
        return m.group(1)
    if p.startswith("L40X2.5"):
        return "L40X40X2.5"
    return p


def _clean_cat(desc):
    return str(desc).strip().upper().replace(" ", "_").replace(".", "").replace("__", "_").strip("_")


def rm_code(section):
    return "RM-" + re.sub(r"[^A-Z0-9.]", "-", str(section).upper())


def service_of(cat):
    cat = _clean_cat(cat)
    if cat in BUILTUP:
        return "BUILTUP"
    if cat in SECONDARY:
        return "SECONDARY"
    return "MISC"


def _cell(ws, r, c):
    v = ws.cell(r, c).value
    return "" if v is None else v


def parse_workbook(wb, job="JOB", phase="P1", wastage=0.0):
    """Parse an openpyxl workbook -> normalized dict.

    Returns keys: rm, categories, cat_rm, cutting, shipping, bolt, totals.
    """
    factor = 1.0 + (float(wastage) / 100.0)

    # ---- ASSM: assembly -> parts hierarchy ----
    ws = wb["ASSM"]
    assemblies = {}
    cur = None
    for r in range(DATA_ROW, ws.max_row + 1):
        am = _cell(ws, r, COL["asm"])
        pm = _cell(ws, r, COL["part"])
        qty = _cell(ws, r, COL["qty"]) or 0
        prof = _cell(ws, r, COL["profile"])
        mat = _cell(ws, r, COL["material"])
        twt = _cell(ws, r, COL["total_wt"]) or 0
        desc = _cell(ws, r, COL["desc"])
        if am and str(am).strip().upper() not in ("", "PAGE TOTAL"):
            cur = str(am).strip()
            assemblies[cur] = dict(qty=qty, tot_wt=twt, desc=str(desc).strip(), parts=[])
        elif pm and cur:
            assemblies[cur]["parts"].append(
                dict(profile=str(prof).strip(), mat=str(mat).strip(),
                     tot_wt=twt or 0))

    # ---- build category -> raw material matrix ----
    cat_wt = defaultdict(float)
    cat_pcs = defaultdict(int)
    cat_rm = defaultdict(lambda: defaultdict(float))
    rm_grade = {}
    rm_total = defaultdict(float)
    for mark, a in assemblies.items():
        cat = _clean_cat(a["desc"]) or "MISC"
        cat_wt[cat] += a["tot_wt"]
        cat_pcs[cat] += a["qty"]
        for p in a["parts"]:
            if not p["profile"]:
                continue
            rm = _norm_profile(p["profile"])
            kg = p["tot_wt"] * a["qty"]
            cat_rm[cat][rm] += kg
            rm_total[rm] += kg
            rm_grade.setdefault(rm, str(p["mat"]).strip().upper())

    rm = []
    for section, kg in sorted(rm_total.items(), key=lambda x: -x[1]):
        g = rm_grade[section]
        rm.append(dict(code=rm_code(section), section=section,
                       grade=GRADE_SPEC.get(g, g), grade_raw=g,
                       weight_kg=round(kg, 2)))

    categories = []
    for cat, w in sorted(cat_wt.items(), key=lambda x: -x[1]):
        categories.append(dict(
            category=cat, service=service_of(cat), pieces=cat_pcs[cat],
            weight_kg=round(w, 2),
            bom=[dict(rm_code=rm_code(s), section=s,
                      qty_per_mt=round(kg / w * 1000 * factor, 3),
                      net_kg=round(kg, 2))
                 for s, kg in sorted(cat_rm[cat].items(), key=lambda x: -x[1])]))

    # ---- SECD cutting list ----
    cutting = []
    ws = wb["SECD"]
    for r in range(DATA_ROW, ws.max_row + 1):
        pm = _cell(ws, r, 2)
        qty = _cell(ws, r, 3)
        prof = _cell(ws, r, 4)
        mat = _cell(ws, r, 6)
        ln = _cell(ws, r, 7)
        desc = _cell(ws, r, 12)
        if pm and isinstance(pm, str) and "TOTAL" not in pm.upper() and prof:
            cutting.append(dict(part=pm, qty=qty or 0, profile=str(prof).strip(),
                                grade=str(mat).strip(), length=ln or 0,
                                member=str(desc).strip()))

    # ---- SHIPG shipping list ----
    shipping = []
    ws = wb["SHIPG"]
    for r in range(DATA_ROW, ws.max_row + 1):
        am = _cell(ws, r, 2)
        qty = _cell(ws, r, 3)
        ext = _cell(ws, r, 5)
        uw = _cell(ws, r, 10)
        tw = _cell(ws, r, 11)
        desc = _cell(ws, r, 12)
        if am and isinstance(am, str) and "TOTAL" not in am.upper():
            shipping.append(dict(asm=am, qty=qty or 0, ext=str(ext).strip(),
                                 unit_wt=uw or 0, tot_wt=tw or 0,
                                 member=str(desc).strip()))

    # ---- BOLT list ----
    bolt = []
    ws = wb["BOLT"]
    for r in range(DATA_ROW, ws.max_row + 1):
        qty = _cell(ws, r, 3)
        code = _cell(ws, r, 4)
        uw = _cell(ws, r, 8)
        tw = _cell(ws, r, 9)
        rem = _cell(ws, r, 11)
        if code and isinstance(code, str) and "TOTAL" not in code.upper():
            bolt.append(dict(code=str(code).strip(), qty=qty or 0,
                             unit_wt=uw or 0, tot_wt=tw or 0,
                             remark=str(rem).strip()))

    totals = dict(
        assemblies=len(assemblies),
        rm_items=len(rm),
        fg_categories=len(categories),
        structural_kg=round(sum(rm_total.values()), 2),
        ship_pieces=sum(int(s["qty"]) for s in shipping),
        bolt_nos=sum(int(b["qty"]) for b in bolt),
        bolt_kg=round(sum(b["tot_wt"] for b in bolt), 2),
    )
    return dict(rm=rm, categories=categories, cutting=cutting,
                shipping=shipping, bolt=bolt, totals=totals,
                job=job, phase=phase)


# ======================================================================
# SUMMARY-SHEET CATEGORIES  (for category-priced purchase POs)
# ======================================================================
# Groups raw sections into the 9 material families shown on the SUMMARY
# sheet, plus bolts. Each becomes one PO line priced per kg.

SUMMARY_FAMILIES = [
    ("PLATE",      "Plate Sections",       "FAB-PLATE"),
    ("COLDFORM",   "Cold Form Sections",   "FAB-COLDFORM"),
    ("HOTROLLED",  "Hot Rolled Sections",  "FAB-HOTROLLED"),
    ("TUBE",       "Circular Tubes",       "FAB-TUBE"),
    ("ANGLE",      "Angle Sections",       "FAB-ANGLE"),
    ("SAGROD",     "Sag Rods",             "FAB-SAGROD"),
    ("RODBRACE",   "Rod Bracings",         "FAB-RODBRACE"),
    ("CHEQUERED",  "Chequered Plate",      "FAB-CHEQUERED"),
    ("BOLTS",      "Bolts (bought-out)",   "FAB-BOLTS"),
]
_FAMILY_LABEL = {k: (label, code) for k, label, code in SUMMARY_FAMILIES}


def _family_of(section):
    s = str(section).strip().upper()
    if s.startswith("CPL"):
        return "CHEQUERED"
    if s.startswith("PL"):
        return "PLATE"
    if re.match(r"^\d+[ZC]", s):
        return "COLDFORM"
    if s.startswith(("TS", "CHS")):
        return "TUBE"
    if s == "ROD12":
        return "SAGROD"
    if s == "ROD24":
        return "RODBRACE"
    if s.startswith(("L", "ISA")):
        return "ANGLE"
    if s.startswith(("ISMB", "ISMC")):
        return "HOTROLLED"
    return "HOTROLLED"


def summary_categories(data, include_bolts=True):
    """Group parsed RM into the SUMMARY families. Returns ordered list of
    dicts: key, label, item_code, weight_kg, sections=[{section,grade,kg}]."""
    from collections import defaultdict
    buckets = defaultdict(lambda: {"kg": 0.0, "sections": []})
    for r in data["rm"]:
        fam = _family_of(r["section"])
        buckets[fam]["kg"] += r["weight_kg"]
        buckets[fam]["sections"].append(
            {"section": r["section"], "grade": r["grade"], "kg": r["weight_kg"]})

    if include_bolts:
        bolt_kg = data["totals"]["bolt_kg"]
        bolt_nos = data["totals"]["bolt_nos"]
        if bolt_kg:
            buckets["BOLTS"]["kg"] = bolt_kg
            buckets["BOLTS"]["sections"] = [
                {"section": b["code"], "grade": b.get("remark", ""),
                 "kg": round(b["tot_wt"], 2), "nos": int(b["qty"])}
                for b in data["bolt"]]

    out = []
    for key, label, code in SUMMARY_FAMILIES:
        if key not in buckets:
            continue
        b = buckets[key]
        b["sections"].sort(key=lambda x: -x["kg"])
        out.append({
            "key": key, "label": label, "item_code": code,
            "weight_kg": round(b["kg"], 2), "sections": b["sections"],
        })
    return out
'@
Set-Content -Path "sbi_projects\\sbi_projects\\steel_bom\\parser.py" -Value $f0 -Encoding UTF8

$f1 = @'
# Copyright (c) 2026, Velmaska and contributors
"""Builds the PO annexure workbook for a fabrication purchase order.

One workbook, several linked sheets, so a fabricator can trace a PO
category down to individual sections, cut lengths, assemblies and
shipping pieces. Returns raw xlsx bytes (attached to the PO in ERPNext).
"""

import io


def build_annexure(data, cats, po_no="PO"):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    NAVY, BLUE, LT, GREY = "1F3864", "1F4E78", "DDEBF7", "F2F2F2"
    H = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
    B = Font(bold=True, name="Calibri", size=10)
    N = Font(name="Calibri", size=10)
    T = Font(bold=True, color="FFFFFF", name="Calibri", size=14)
    thin = Border(*[Side("thin", color="B0B0B0")] * 4)
    ctr = Alignment("center", "center", wrap_text=True)
    lft = Alignment("left", "center", wrap_text=True)
    rgt = Alignment("right", "center")
    yel = PatternFill("solid", fgColor="FFF2CC")

    def title(ws, ncol, sub):
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncol)
        c = ws.cell(1, 1, "SHIV BHARAT INFRASTRUCTURES")
        c.fill = PatternFill("solid", fgColor=NAVY); c.font = T; c.alignment = ctr
        ws.row_dimensions[1].height = 22
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncol)
        c = ws.cell(2, 1, f"Fabrication PO Annexure  |  {sub}  |  PO Ref: {po_no}")
        c.fill = PatternFill("solid", fgColor=BLUE); c.font = Font(bold=True, color="FFFFFF", size=10)
        c.alignment = lft
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
            c = ws.cell(r, i, v); c.font = N; c.border = thin
            c.alignment = al[i - 1]
            if shade:
                c.fill = PatternFill("solid", fgColor=GREY)
            if isinstance(v, float):
                c.number_format = "#,##0.00"
        return r + 1

    # ---------------- Sheet 1: PO (category, rate/kg) ----------------
    ws = wb.create_sheet("PO by Category")
    r = title(ws, 5, "Purchase Order - Category-wise")
    r = head(ws, r, [("#", 5), ("Category", 26), ("Item Code", 16),
                     ("Weight (Kg)", 16), ("Rate/Kg (fill)", 16)])
    hdr = r - 1
    first = r
    for i, c in enumerate(cats, 1):
        ws.cell(r, 1, i).alignment = ctr; ws.cell(r, 1).font = N; ws.cell(r, 1).border = thin
        ws.cell(r, 2, c["label"]).alignment = lft; ws.cell(r, 2).font = N; ws.cell(r, 2).border = thin
        ws.cell(r, 3, c["item_code"]).alignment = ctr; ws.cell(r, 3).font = N; ws.cell(r, 3).border = thin
        wc = ws.cell(r, 4, round(c["weight_kg"], 2)); wc.number_format = "#,##0.00"; wc.alignment = rgt; wc.font = N; wc.border = thin
        rc = ws.cell(r, 5); rc.fill = yel; rc.border = thin
        r += 1
    tot = ws.cell(r, 2, "TOTAL"); tot.font = B
    ws.cell(r, 4, f"=SUM(D{first}:D{r-1})").font = B; ws.cell(r, 4).number_format = "#,##0.00"
    for i in range(1, 6):
        ws.cell(r, i).fill = PatternFill("solid", fgColor=LT); ws.cell(r, i).border = thin
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"

    # ---------------- Sheet 2: Category -> Sections (linked) ----------------
    ws = wb.create_sheet("Category Detail")
    r = title(ws, 5, "Category -> Sections")
    r = head(ws, r, [("Category", 24), ("Section", 18), ("Grade / Spec", 30),
                     ("Weight (Kg)", 14), ("Nos", 10)])
    hdr = r - 1
    for c in cats:
        span_start = r
        for s in c["sections"]:
            r = row(ws, r, [c["label"], s["section"], s.get("grade", ""),
                            round(s["kg"], 2), s.get("nos", "")],
                    [lft, lft, lft, rgt, ctr], shade=(cats.index(c) % 2 == 1))
        # merge the category cell down its section rows
        if r - span_start > 1:
            ws.merge_cells(start_row=span_start, start_column=1, end_row=r - 1, end_column=1)
            ws.cell(span_start, 1).alignment = Alignment("left", "top", wrap_text=True)
            ws.cell(span_start, 1).font = B
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"

    # ---------------- Sheet 3: Cutting List (SECD) ----------------
    ws = wb.create_sheet("Cutting List")
    r = title(ws, 6, "Cutting List (Section Details)")
    r = head(ws, r, [("Sl", 5), ("Part Mark", 14), ("Section", 18), ("Grade", 20),
                     ("Cut Length mm", 14), ("Member Type", 20)])
    hdr = r - 1; sl = 0
    for cr in data["cutting"]:
        sl += 1
        r = row(ws, r, [sl, cr["part"], cr["profile"], cr.get("grade", ""),
                        round(float(cr["length"]), 1) if cr["length"] else 0,
                        str(cr.get("member", "")).replace("_", " ").title()],
                [ctr, lft, lft, lft, ctr, lft], shade=(sl % 2 == 0))
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"
    ws.auto_filter.ref = f"A{hdr}:F{r-1}"

    # ---------------- Sheet 4: Shipping List (SHIPG) ----------------
    ws = wb.create_sheet("Shipping List")
    r = title(ws, 5, "Shipping List (Dispatch)")
    r = head(ws, r, [("Sl", 5), ("Assembly Mark", 16), ("External Size mm", 22),
                     ("Total Wt kg", 14), ("Member Type", 22)])
    hdr = r - 1; sl = 0
    for sp in data["shipping"]:
        sl += 1
        r = row(ws, r, [sl, sp["asm"], sp.get("ext", ""),
                        round(float(sp["tot_wt"]), 2) if sp["tot_wt"] else 0,
                        str(sp.get("member", "")).replace("_", " ").title()],
                [ctr, lft, lft, rgt, lft], shade=(sl % 2 == 0))
    ws.sheet_view.showGridLines = False; ws.freeze_panes = f"A{hdr+1}"
    ws.auto_filter.ref = f"A{hdr}:E{r-1}"

    # ---------------- Sheet 5: Bolt List (BOLT) ----------------
    ws = wb.create_sheet("Bolt List")
    r = title(ws, 5, "Bolt List (bought-out)")
    r = head(ws, r, [("Sl", 5), ("Material Code", 28), ("Qty Nos", 12),
                     ("Total Wt kg", 14), ("Remark", 24)])
    hdr = r - 1; sl = 0
    for b in data["bolt"]:
        sl += 1
        r = row(ws, r, [sl, b["code"], int(b["qty"]),
                        round(float(b["tot_wt"]), 2) if b["tot_wt"] else 0, b.get("remark", "")],
                [ctr, lft, ctr, rgt, lft], shade=(sl % 2 == 0))
    ws.sheet_view.showGridLines = False

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
'@
Set-Content -Path "sbi_projects\\sbi_projects\\steel_bom\\annexure.py" -Value $f1 -Encoding UTF8

$f2 = @'
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
'@
Set-Content -Path "sbi_projects\\sbi_projects\\doctype\\steel_fabrication_import\\steel_fabrication_import.py" -Value $f2 -Encoding UTF8

$f3 = @'
// Copyright (c) 2026, Velmaska and contributors

frappe.ui.form.on("Steel Fabrication Import", {
	refresh(frm) {
		frm.disable_save = false;

		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__("Enter PO No, Project, Company, Supplier; attach the Tekla Steel BOM; Save, then Process BOM.")
			);
			return;
		}

		frm.add_custom_button(__("Process BOM"), () => {
			if (!frm.doc.bom_file) {
				frappe.msgprint(__("Attach the Steel BOM file first."));
				return;
			}
			frappe.confirm(
				__("Generate category items{0} and the annexure for {1}?", [
					frm.doc.supplier ? __(" and a draft PO") : "",
					frm.doc.po_no,
				]),
				() => run_process(frm)
			);
		}).addClass("btn-primary");

		if (frm.doc.created_po) {
			frm.add_custom_button(__("Open Draft PO"), () => {
				frappe.set_route("Form", "Purchase Order", frm.doc.created_po);
			});
		}

		if (frm.doc.status === "Processed") {
			frm.dashboard.set_headline(
				__("Processed: {0} MT across {1} categories.{2} Next: fill Rate/kg, submit PO, then GRN at site.", [
					frm.doc.total_weight_mt,
					frm.doc.category_count,
					frm.doc.created_po ? __(" Draft PO: {0}.", [frm.doc.created_po]) : "",
				])
			);
		}
	},
});

function run_process(frm) {
	frappe.dom.freeze(__("Processing - creating category items, PO and annexure..."));
	frappe.call({
		method: "sbi_projects.sbi_projects.doctype.steel_fabrication_import.steel_fabrication_import.process_import",
		args: { docname: frm.doc.name },
		callback(r) {
			frappe.dom.unfreeze();
			frm.reload_doc();
			if (r.message && r.message.status === "ok") {
				frappe.show_alert({ message: __("Done - data generated."), indicator: "green" });
			}
		},
		error() {
			frappe.dom.unfreeze();
		},
	});
}
'@
Set-Content -Path "sbi_projects\\sbi_projects\\doctype\\steel_fabrication_import\\steel_fabrication_import.js" -Value $f3 -Encoding UTF8

$f4 = @'
{
 "actions": [],
 "allow_rename": 1,
 "creation": "2026-07-16 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "po_no",
  "project",
  "cb_1",
  "company",
  "supplier",
  "target_warehouse",
  "sb_options",
  "include_bolts",
  "wastage_percent",
  "cb_2",
  "bom_file",
  "sb_run",
  "process_button_html",
  "sb_results",
  "status",
  "created_po",
  "cb_3",
  "total_weight_mt",
  "category_count",
  "bolt_nos",
  "sb_log",
  "log"
 ],
 "fields": [
  {
   "fieldname": "po_no",
   "fieldtype": "Data",
   "label": "PO No / Reference",
   "reqd": 1,
   "in_list_view": 1,
   "description": "Your PO reference for this fabrication order."
  },
  {
   "fieldname": "project",
   "fieldtype": "Link",
   "label": "Project (Site)",
   "options": "Project",
   "reqd": 1,
   "in_list_view": 1,
   "description": "Material is received against this site's warehouse via GRN."
  },
  {
   "fieldname": "cb_1",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "company",
   "fieldtype": "Link",
   "label": "Company",
   "options": "Company",
   "reqd": 1
  },
  {
   "fieldname": "supplier",
   "fieldtype": "Link",
   "label": "Supplier (Fabricator)",
   "options": "Supplier",
   "description": "Fabricator who supplies the fabricated steel."
  },
  {
   "fieldname": "target_warehouse",
   "fieldtype": "Link",
   "label": "Receiving Warehouse",
   "options": "Warehouse",
   "description": "Site warehouse where fabricated material is received (GRN). Defaults to the project's warehouse."
  },
  {
   "fieldname": "sb_options",
   "fieldtype": "Section Break",
   "label": "Import Options"
  },
  {
   "fieldname": "include_bolts",
   "fieldtype": "Check",
   "label": "Include Bolts as a category",
   "default": "1",
   "description": "Adds a Bolts line (bought-out hardware, priced by weight)."
  },
  {
   "fieldname": "wastage_percent",
   "fieldtype": "Percent",
   "label": "Wastage %",
   "default": 0,
   "description": "Tekla weights are net cut-length; keep 0 unless told otherwise."
  },
  {
   "fieldname": "cb_2",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "bom_file",
   "fieldtype": "Attach",
   "label": "Steel BOM File (xlsx)",
   "reqd": 1,
   "description": "Raw Tekla Steel BOM export (ASSM / SECD / SHIPG / BOLT / SUMMARY)."
  },
  {
   "fieldname": "sb_run",
   "fieldtype": "Section Break",
   "label": "Process"
  },
  {
   "fieldname": "process_button_html",
   "fieldtype": "HTML",
   "label": " "
  },
  {
   "fieldname": "sb_results",
   "fieldtype": "Section Break",
   "label": "Results"
  },
  {
   "fieldname": "status",
   "fieldtype": "Select",
   "label": "Status",
   "options": "Draft\nProcessed\nError",
   "default": "Draft",
   "read_only": 1,
   "in_list_view": 1
  },
  {
   "fieldname": "created_po",
   "fieldtype": "Link",
   "label": "Created Draft PO",
   "options": "Purchase Order",
   "read_only": 1
  },
  {
   "fieldname": "cb_3",
   "fieldtype": "Column Break"
  },
  {
   "fieldname": "total_weight_mt",
   "fieldtype": "Float",
   "label": "Total Weight (MT)",
   "read_only": 1,
   "precision": "3"
  },
  {
   "fieldname": "category_count",
   "fieldtype": "Int",
   "label": "Categories",
   "read_only": 1
  },
  {
   "fieldname": "bolt_nos",
   "fieldtype": "Int",
   "label": "Bolt Nos",
   "read_only": 1
  },
  {
   "fieldname": "sb_log",
   "fieldtype": "Section Break",
   "label": "Run Log"
  },
  {
   "fieldname": "log",
   "fieldtype": "Code",
   "label": "Log",
   "read_only": 1,
   "options": "Text"
  }
 ],
 "index_web_pages_for_search": 1,
 "links": [],
 "modified": "2026-07-16 00:00:00.000000",
 "module": "SBI Projects",
 "name": "Steel Fabrication Import",
 "naming_rule": "Expression",
 "autoname": "format:SFI-{po_no}",
 "owner": "Administrator",
 "permissions": [
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "System Manager",
   "share": 1,
   "write": 1
  },
  {
   "create": 1,
   "delete": 1,
   "email": 1,
   "print": 1,
   "read": 1,
   "report": 1,
   "role": "Purchase Manager",
   "share": 1,
   "write": 1
  }
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "track_changes": 1
}
'@
Set-Content -Path "sbi_projects\\sbi_projects\\doctype\\steel_fabrication_import\\steel_fabrication_import.json" -Value $f4 -Encoding UTF8

Write-Host "--- written 5 files ---" -ForegroundColor Green
git diff --stat
