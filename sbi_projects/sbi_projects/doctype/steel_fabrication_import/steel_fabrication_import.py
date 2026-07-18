# Copyright (c) 2026, Velmaska and contributors

import io
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate, add_days

from sbi_projects.sbi_projects.steel_bom.parser import (
    parse_workbook, rm_code, SERVICE_ITEMS, GRADE_SPEC,
)

RM_GROUP = "Raw Material - Steel"
FG_GROUP = "Finished Goods - PEB"
SVC_GROUP = "Services"


class SteelFabricationImport(Document):
    def validate(self):
        if not self.company:
            self.company = frappe.defaults.get_user_default("Company")


# ======================================================================
# Whitelisted entry point (called from the client "Process" button)
# ======================================================================
@frappe.whitelist()
def process_import(docname):
    doc = frappe.get_doc("Steel Fabrication Import", docname)
    log = []

    def note(msg):
        log.append(msg)

    try:
        import openpyxl
    except Exception:
        frappe.throw(_("openpyxl is not available on this bench."))

    # ---- read the attached workbook ----
    if not doc.bom_file:
        frappe.throw(_("Attach the Steel BOM file first."))
    content = _get_file_bytes(doc.bom_file)
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

    data = parse_workbook(wb, job=doc.job_no, phase=doc.phase or "P1",
                          wastage=flt(doc.wastage_percent))
    t = data["totals"]
    note(f"Parsed: {t['assemblies']} assemblies, {t['rm_items']} RM, "
         f"{t['fg_categories']} categories, {t['structural_kg']} kg.")

    company = doc.company
    abbr = frappe.get_cached_value("Company", company, "abbr")
    store = f"Stores - {abbr}"
    accepted = doc.accepted_warehouse or store

    # ---- 1. item groups ----
    for g in (RM_GROUP, FG_GROUP, SVC_GROUP):
        _ensure_item_group(g)

    # ---- 2. supplier warehouse ----
    sup_wh = doc.supplier_warehouse
    if not sup_wh:
        sup_wh = _ensure_warehouse("Fabricator A", company, abbr)
        doc.db_set("supplier_warehouse", sup_wh)
    note(f"Supplier warehouse: {sup_wh}")

    # ---- 3. raw materials ----
    for r in data["rm"]:
        _ensure_item(dict(
            item_code=r["code"], item_name=f"{r['section']} - {r['grade']}",
            item_group=RM_GROUP, stock_uom="Kg", is_stock_item=1,
            is_purchase_item=1, gst_hsn_code="7308",
            item_defaults=[dict(company=company, default_warehouse=store)]))
    note(f"RM items ok: {len(data['rm'])}")

    # ---- 4. service items ----
    for key, (code, name) in SERVICE_ITEMS.items():
        _ensure_item(dict(
            item_code=code, item_name=name, item_group=SVC_GROUP,
            stock_uom="MT", is_stock_item=0, is_purchase_item=1,
            is_sales_item=0, gst_hsn_code="998873"))

    # ---- 5/6/7. FG + BOM + Subcontracting BOM (per chosen model) ----
    fg_defs = _build_fg_definitions(data, doc.model)
    made = 0
    for fg in fg_defs:
        _ensure_item(dict(
            item_code=fg["code"], item_name=fg["name"], item_group=FG_GROUP,
            stock_uom="Kg", is_stock_item=1, is_sub_contracted_item=1,
            is_purchase_item=0, gst_hsn_code="7308",
            item_defaults=[dict(company=company, default_warehouse=store)]))
        bom_name = _ensure_bom(fg["code"], fg["bom"], company)
        _ensure_subcontracting_bom(fg["code"], fg["service_code"], bom_name, company)
        made += 1
    note(f"FG + BOM + Subcontracting BOM ok: {made}")

    # ---- 8. draft subcontracting PO (rate empty) ----
    po_name = None
    if doc.supplier:
        po_name = _create_draft_po(doc, fg_defs, sup_wh, accepted, company)
        note(f"Draft PO created: {po_name} (rate blank - fill in ERPNext).")
    else:
        note("Supplier not set - skipped PO. Set Supplier and re-run to get a draft PO.")

    # ---- persist results ----
    doc.db_set("status", "Processed")
    doc.db_set("total_weight_mt", round(t["structural_kg"] / 1000.0, 3))
    doc.db_set("rm_count", len(data["rm"]))
    doc.db_set("fg_count", len(fg_defs))
    doc.db_set("bolt_nos", t["bolt_nos"])
    if po_name:
        doc.db_set("created_po", po_name)
    doc.db_set("log", "\n".join(log))
    frappe.db.commit()
    return dict(status="ok", po=po_name, log="\n".join(log))


# ======================================================================
# FG / BOM builders
# ======================================================================
def _build_fg_definitions(data, model):
    """Return list of FG dicts: code, name, service_code, service_key,
    weight_kg, bom=[{rm_code, qty}] (per 1000 kg FG)."""
    job, phase = data["job"], data["phase"]
    prefix = f"FG-{job}-{phase}-"
    is_a = model.startswith("Model A")

    if is_a:
        # aggregate categories into 3 service buckets
        buckets = defaultdict(lambda: dict(weight=0.0, rm=defaultdict(float)))
        for c in data["categories"]:
            b = buckets[c["service"]]
            b["weight"] += c["weight_kg"]
            for line in c["bom"]:
                b["rm"][line["rm_code"]] += line["net_kg"]
        out = []
        for key, (svc_code, svc_name) in SERVICE_ITEMS.items():
            if key not in buckets:
                continue
            b = buckets[key]
            w = b["weight"] or 1
            out.append(dict(
                code=f"{prefix}{key}",
                name=f"{svc_name.split(' - ')[-1]} - {job} {phase}",
                service_code=svc_code, service_key=key,
                weight_kg=round(b["weight"], 2),
                bom=[dict(rm_code=rc, qty=round(kg / w * 1000, 3))
                     for rc, kg in sorted(b["rm"].items(), key=lambda x: -x[1])]))
        return out

    # Model B: one FG per category
    out = []
    for c in data["categories"]:
        code = prefix + c["category"].replace("_", "-")
        out.append(dict(
            code=code,
            name=f"{c['category'].replace('_', ' ').title()} - {job} {phase}",
            service_code=SERVICE_ITEMS[c["service"]][0], service_key=c["service"],
            weight_kg=c["weight_kg"],
            bom=[dict(rm_code=b["rm_code"], qty=b["qty_per_mt"]) for b in c["bom"]]))
    return out


# ======================================================================
# Idempotent helpers
# ======================================================================
def _ensure_item_group(name):
    if not frappe.db.exists("Item Group", name):
        frappe.get_doc(dict(doctype="Item Group", item_group_name=name,
                            parent_item_group="All Item Groups", is_group=0)).insert()


def _ensure_warehouse(wh_name, company, abbr):
    full = f"{wh_name} - {abbr}"
    if not frappe.db.exists("Warehouse", full):
        frappe.get_doc(dict(doctype="Warehouse", warehouse_name=wh_name,
                            company=company, is_group=0)).insert()
    return full


def _ensure_item(payload):
    if frappe.db.exists("Item", payload["item_code"]):
        return payload["item_code"]
    payload["doctype"] = "Item"
    frappe.get_doc(payload).insert()
    return payload["item_code"]


def _ensure_bom(item_code, bom_lines, company):
    existing = frappe.get_all("BOM", filters={"item": item_code, "is_active": 1},
                              limit=1, pluck="name")
    if existing:
        return existing[0]
    bom = frappe.get_doc(dict(
        doctype="BOM", item=item_code, company=company, quantity=1000, uom="Kg",
        is_active=1, is_default=1, with_operations=0, rm_cost_as_per="Valuation Rate",
        items=[dict(item_code=l["rm_code"], qty=l["qty"], uom="Kg",
                    stock_uom="Kg", conversion_factor=1) for l in bom_lines]))
    bom.insert()
    bom.submit()
    return bom.name


def _ensure_subcontracting_bom(fg_code, service_code, bom_name, company):
    if frappe.db.exists("Subcontracting BOM", {"finished_good": fg_code}):
        return
    sc = frappe.get_doc(dict(
        doctype="Subcontracting BOM", finished_good=fg_code, finished_good_qty=1000,
        finished_good_uom="Kg", service_item=service_code, service_item_qty=1,
        service_item_uom="MT", bom=bom_name, company=company, is_active=1))
    sc.insert()
    sc.submit()


def _create_draft_po(doc, fg_defs, sup_wh, accepted, company):
    po = frappe.new_doc("Purchase Order")
    po.supplier = doc.supplier
    po.company = company
    po.transaction_date = nowdate()
    po.schedule_date = add_days(nowdate(), 30)
    po.is_subcontracted = 1
    po.supplier_warehouse = sup_wh
    for fg in fg_defs:
        service_mt = round(flt(fg["weight_kg"]) / 1000.0, 3)
        po.append("items", dict(
            item_code=fg["service_code"],
            fg_item=fg["code"],
            fg_item_qty=flt(fg["weight_kg"]),
            qty=service_mt,
            rate=0,
            schedule_date=add_days(nowdate(), 30),
            warehouse=accepted,
        ))
    po.insert(ignore_permissions=True)  # stays in Draft (docstatus 0)
    return po.name
