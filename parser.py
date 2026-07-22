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
