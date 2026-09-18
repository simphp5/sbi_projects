import base64
import io
import json
import re

import frappe
from frappe.utils import flt, formatdate, money_in_words, rounded


# ---------------------------------------------------------------- formatting


def amt(value, blank_on_zero=False):
	"""Indian grouped money string without currency symbol: 1,23,456.00"""
	value = flt(value, 2)
	if not value and blank_on_zero:
		return ""
	negative = value < 0
	value = abs(value)
	whole, dec = ("%.2f" % value).split(".")
	if len(whole) > 3:
		last3 = whole[-3:]
		rest = whole[:-3]
		parts = []
		while len(rest) > 2:
			parts.insert(0, rest[-2:])
			rest = rest[:-2]
		if rest:
			parts.insert(0, rest)
		whole = ",".join(parts + [last3])
	out = whole + "." + dec
	return ("-" + out) if negative else out


def pct(value):
	value = flt(value, 2)
	if value == int(value):
		return str(int(value))
	return ("%.2f" % value).rstrip("0").rstrip(".")


def in_words(value, currency="INR"):
	try:
		return money_in_words(flt(value), currency or "INR")
	except Exception:
		return ""


def fdate(value, fmt="dd-MMM-yy"):
	if not value:
		return ""
	try:
		return formatdate(value, fmt)
	except Exception:
		return str(value)


def qr_base64(data):
	if not data:
		return ""
	try:
		import qrcode

		img = qrcode.make(data)
		buf = io.BytesIO()
		img.save(buf, format="PNG")
		return base64.b64encode(buf.getvalue()).decode()
	except Exception:
		pass
	try:
		import pyqrcode

		buf = io.BytesIO()
		pyqrcode.create(data).png(buf, scale=4)
		return base64.b64encode(buf.getvalue()).decode()
	except Exception:
		return ""


# ---------------------------------------------------------------- lookups


def _get(obj, field):
	if obj is None:
		return None
	try:
		return obj.get(field)
	except Exception:
		return getattr(obj, field, None)


_SO_LINK_FIELDS = ("sales_order", "sbi_sales_order", "against_sales_order")


def linked_sales_order(doc, row=None):
	"""Find the Sales Order behind this invoice - link field, then project."""
	for candidate in (row, doc):
		for field in _SO_LINK_FIELDS:
			value = _get(candidate, field)
			if value:
				return value

	for item in _get(doc, "items") or []:
		for field in _SO_LINK_FIELDS:
			value = _get(item, field)
			if value:
				return value

	project = _get(doc, "project")
	if not project and row is not None:
		project = _get(row, "project")
	if not project:
		for item in _get(doc, "items") or []:
			project = _get(item, "project")
			if project:
				break
	if project:
		return frappe.db.get_value(
			"Sales Order",
			{"project": project, "docstatus": 1},
			"name",
			order_by="transaction_date desc",
		)
	return None


_SCHEDULE_CACHE = {}


def _schedule_rows(so):
	if not so:
		return []
	if so in _SCHEDULE_CACHE:
		return _SCHEDULE_CACHE[so]
	try:
		rows = frappe.get_all(
			"Payment Schedule",
			filters={"parent": so, "parenttype": "Sales Order"},
			fields=["*"],
			order_by="idx",
		)
	except Exception:
		rows = []
	_SCHEDULE_CACHE[so] = rows
	return rows


_SCHEDULE_STAGE_FIELDS = (
	"sbi_project_stage",
	"project_stage",
	"sbi_stage",
	"stage",
	"sbi_site_stage",
)


# ---------------------------------------------------------------- stage


_STAGE_NO = ("sbi_stage_no", "stage_no", "sbi_stage_index", "sbi_stage_number")
_STAGE_NAME = ("sbi_stage", "sbi_stage_name", "stage", "stage_name", "sbi_milestone", "milestone")
_TERM_FIELDS = ("payment_term", "sbi_payment_term", "sbi_term", "milestone_term")

_STAGE_PCT = (
	"sbi_invoice_portion",
	"invoice_portion",
	"sbi_percentage",
	"sbi_stage_percent",
	"sbi_stage_percentage",
)


def _pick(row, fields):
	for f in fields:
		value = _get(row, f)
		if value not in (None, "", 0, 0.0):
			return value
	return None


def _match_schedule(so, term, description=None):
	"""Return (sl_no, project_stage, invoice_portion) for the matching schedule row."""
	rows = _schedule_rows(so)
	if not rows:
		return None, None, None

	match = None
	if term:
		term_text = str(term).strip().lower()
		for entry in rows:
			if str(entry.get("payment_term") or "").strip().lower() == term_text:
				match = entry
				break
		if not match:
			for entry in rows:
				for field in _SCHEDULE_STAGE_FIELDS:
					value = entry.get(field)
					if value and str(value).strip().lower() == term_text:
						match = entry
						break
				if match:
					break
	if not match and description:
		text = str(description)
		for entry in rows:
			desc = entry.get("description") or entry.get("payment_term") or ""
			if desc and desc.strip()[:35] in text:
				match = entry
				break
	if not match:
		return None, None, None

	stage = None
	for field in _SCHEDULE_STAGE_FIELDS:
		if match.get(field):
			stage = match.get(field)
			break
	return match.get("idx"), stage, match.get("invoice_portion")


def stage_parts(row, parent=None):
	"""Return (stage_no, stage_name, portion)."""
	stage_no = _pick(row, _STAGE_NO)
	stage_name = _pick(row, _STAGE_NAME)
	portion = _pick(row, _STAGE_PCT)
	term = _pick(row, _TERM_FIELDS)

	so = linked_sales_order(parent, row) if parent is not None else _get(row, "sales_order")
	sched_no, sched_stage, sched_portion = _match_schedule(so, term, _get(row, "description"))
	if sched_no is None and stage_name:
		sched_no, sched_stage, sched_portion = _match_schedule(so, stage_name, None)

	if not stage_no:
		stage_no = sched_no
	if not stage_no and term:
		match = re.search(r"(\d+)", str(term))
		if match:
			stage_no = match.group(1)
	if not stage_no and parent is not None:
		stage_no = _get(parent, "sbi_stage_no") or None

	if not stage_name:
		stage_name = sched_stage or term
	if not portion:
		portion = sched_portion

	if stage_name:
		stage_name = re.sub(
			r"^\s*stage\s*[#:\-]*\s*\d*\s*[-:]*\s*", "", str(stage_name), flags=re.I
		).strip()
	return stage_no, stage_name, portion


def stage_line(row, parent=None):
	"""Build:  Stage : #8 - Completion of Grade Slab - 10%"""
	stage_no, stage_name, portion = stage_parts(row, parent)
	if not (stage_no or stage_name or portion):
		return ""
	parts = ["Stage : #%s" % stage_no if stage_no else "Stage"]
	if stage_name:
		parts.append(str(stage_name))
	if portion:
		parts.append("%s%%" % pct(portion))
	return " - ".join(parts)


# ---------------------------------------------------------------- addresses


def _address_block(address_name):
	out = {"lines": [], "gstin": "", "state": "", "state_code": "", "title": ""}
	if not address_name or not frappe.db.exists("Address", address_name):
		return out
	doc = frappe.get_doc("Address", address_name)
	for field in ("address_line1", "address_line2"):
		value = doc.get(field)
		if value:
			out["lines"].append(value)
	city_line = ", ".join([x for x in [doc.get("city"), doc.get("county")] if x])
	tail = " ".join([x for x in [city_line, doc.get("pincode")] if x]).strip()
	if tail:
		out["lines"].append(tail)
	out["gstin"] = doc.get("gstin") or ""
	out["state"] = doc.get("state") or doc.get("gst_state") or ""
	out["state_code"] = doc.get("gst_state_number") or ""
	out["title"] = doc.get("address_title") or ""
	return out


def _customer_shipping_address(customer):
	if not customer:
		return None
	rows = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"},
		pluck="parent",
	)
	if not rows:
		return None
	name = frappe.db.get_value(
		"Address",
		{"name": ["in", rows], "address_type": "Shipping", "disabled": 0},
		"name",
		order_by="is_shipping_address desc, modified desc",
	)
	return name


def _state_code(gstin):
	if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
		return gstin[:2]
	return ""


# ---------------------------------------------------------------- tax split


def _tax_key(account_head):
	head = (account_head or "").upper()
	if "IGST" in head:
		return "igst"
	if "CGST" in head:
		return "cgst"
	if "SGST" in head or "UTGST" in head:
		return "sgst"
	if "CESS" in head:
		return "cess"
	return None


def _item_wise_tax(doc):
	out = {}
	for tax in doc.get("taxes") or []:
		key = _tax_key(tax.account_head)
		if not key or not tax.get("item_wise_tax_detail"):
			continue
		try:
			detail = json.loads(tax.item_wise_tax_detail)
		except Exception:
			continue
		if not isinstance(detail, dict):
			continue
		for code, value in detail.items():
			if isinstance(value, dict):
				rate = flt(value.get("tax_rate"))
				amount = flt(value.get("tax_amount"))
			elif isinstance(value, (list, tuple)):
				rate = flt(value[0]) if len(value) > 0 else 0
				amount = flt(value[1]) if len(value) > 1 else 0
			else:
				continue
			bucket = out.setdefault(code, {}).setdefault(key, {"rate": 0, "amount": 0})
			bucket["rate"] = rate or bucket["rate"]
			bucket["amount"] += amount
	return out


def _blank_row(hsn):
	return {
		"hsn": hsn,
		"taxable": 0.0,
		"cgst_rate": 0.0,
		"cgst": 0.0,
		"sgst_rate": 0.0,
		"sgst": 0.0,
		"igst_rate": 0.0,
		"igst": 0.0,
		"cess": 0.0,
		"total_tax": 0.0,
	}


def hsn_summary(doc):
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	item_tax = _item_wise_tax(doc)
	code_to_hsn = {}
	rows = {}

	for row in doc.get("items") or []:
		hsn = row.get("gst_hsn_code") or row.get("hsn_code") or ""
		code_to_hsn.setdefault(row.item_code, hsn)
		entry = rows.setdefault(hsn, _blank_row(hsn))
		entry["taxable"] += flt(row.get("net_amount") or row.get("amount"))

	for code, buckets in item_tax.items():
		hsn = code_to_hsn.get(code)
		if hsn is None:
			continue
		entry = rows.get(hsn)
		if not entry:
			continue
		for key in ("cgst", "sgst", "igst", "cess"):
			if key in buckets:
				entry[key] += flt(buckets[key]["amount"])
				if key != "cess":
					entry[key + "_rate"] = flt(buckets[key]["rate"]) or entry[key + "_rate"]

	parsed_tax = sum([r["cgst"] + r["sgst"] + r["igst"] + r["cess"] for r in rows.values()])
	doc_tax = sum([flt(t.base_tax_amount or t.tax_amount) for t in (doc.get("taxes") or [])])
	if rows and flt(parsed_tax, 2) == 0 and flt(doc_tax, 2) != 0:
		base = sum([r["taxable"] for r in rows.values()]) or 1.0
		for tax in doc.get("taxes") or []:
			key = _tax_key(tax.account_head)
			if not key:
				continue
			amount = flt(tax.base_tax_amount or tax.tax_amount)
			if not amount:
				continue
			rate = flt(tax.rate) or flt(amount * 100.0 / base, 2)
			keys = list(rows.keys())
			running = 0.0
			for idx, hsn in enumerate(keys):
				entry = rows[hsn]
				if idx == len(keys) - 1:
					share = amount - running
				else:
					share = flt(amount * entry["taxable"] / base, 2)
					running += share
				entry[key] += share
				if key != "cess":
					entry[key + "_rate"] = rate or entry[key + "_rate"]

	out_rows = []
	total = {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0, "cess": 0.0, "total_tax": 0.0}
	for entry in rows.values():
		entry["total_tax"] = entry["cgst"] + entry["sgst"] + entry["igst"] + entry["cess"]
		out_rows.append(entry)
		for key in total:
			total[key] += entry[key]

	out_rows.sort(key=lambda x: x["hsn"] or "")
	return {"rows": out_rows, "total": total, "has_igst": total["igst"] > 0}


# ---------------------------------------------------------------- bank


def bank_block(doc=None, company=None, bank_account=None):
	out = {"bank_account": "", "bank_name": "", "account_no": "", "branch": "", "complete": False}
	name = bank_account
	if not name and doc is not None:
		name = doc.get("company_bank_account")
	if not name and company:
		name = frappe.db.get_value("Company", company, "default_bank_account")
	if not name and company:
		for filters in (
			{"company": company, "is_company_account": 1, "disabled": 0},
			{"company": company, "disabled": 0},
			{"is_company_account": 1, "disabled": 0},
		):
			name = frappe.db.get_value(
				"Bank Account", filters, "name", order_by="is_default desc, modified desc"
			)
			if name:
				break
	if not name:
		return out

	ba = frappe.get_doc("Bank Account", name)
	bank_name = ba.get("sbi_print_bank_name") or ""
	if not bank_name and ba.get("bank"):
		bank_name = frappe.db.get_value("Bank", ba.bank, "bank_name") or ba.bank

	ifsc = ba.get("branch_code") or ""
	branch = " & ".join([x for x in [ba.get("sbi_branch_name") or "", ifsc] if x])

	out.update(
		{
			"bank_account": ba.name,
			"bank_name": bank_name,
			"account_no": ba.get("bank_account_no") or "",
			"branch": branch,
		}
	)
	out["complete"] = bool(out["bank_name"] and out["account_no"] and ifsc)
	return out


@frappe.whitelist()
def bank_details_for(invoice):
	doc = frappe.get_doc("Sales Invoice", invoice)
	doc.check_permission("read")
	return bank_block(doc=doc, company=doc.company)


# ---------------------------------------------------------------- main ctx


_ORDER_NO_FIELDS = (
	"po_no",
	"sbi_po_no",
	"sbi_customer_order_no",
	"customer_order_no",
	"sbi_customer_po_no",
	"customer_po_no",
	"sbi_order_no",
)

_ORDER_NO_LABELS = (
	"customer order no",
	"customer order number",
	"customer's purchase order",
	"customer purchase order",
	"po no",
	"po number",
)

_ORDER_DATE_FIELDS = (
	"po_date",
	"sbi_po_date",
	"sbi_customer_order_date",
	"customer_order_date",
	"sbi_order_date",
)


def _order_ref_fieldnames(doctype):
	"""Locate the Customer Order No field (and its date) whatever it is named."""
	cache_key = "sbi_order_ref_fields_" + doctype
	cached = frappe.cache().get_value(cache_key)
	if cached:
		return cached.get("no"), cached.get("date")

	meta = frappe.get_meta(doctype)
	fieldnames = {df.fieldname for df in meta.fields}

	no_field = None
	for candidate in _ORDER_NO_FIELDS:
		if candidate in fieldnames:
			no_field = candidate
			break

	fields = list(meta.fields)
	if not no_field:
		for idx, df in enumerate(fields):
			label = (df.label or "").strip().lower()
			if label in _ORDER_NO_LABELS and df.fieldtype in ("Data", "Small Text", "Link"):
				no_field = df.fieldname
				break

	date_field = None
	for candidate in _ORDER_DATE_FIELDS:
		if candidate in fieldnames:
			date_field = candidate
			break

	if not date_field and no_field:
		start = next((i for i, df in enumerate(fields) if df.fieldname == no_field), None)
		if start is not None:
			for df in fields[start + 1 : start + 5]:
				if df.fieldtype in ("Date", "Datetime"):
					date_field = df.fieldname
					break

	frappe.cache().set_value(cache_key, {"no": no_field, "date": date_field}, expires_in_sec=3600)
	return no_field, date_field


def order_reference(doc, doctype=None):
	"""Return (order_no, order_date) read from whichever fields hold them."""
	doctype = doctype or doc.get("doctype")
	no_field, date_field = _order_ref_fieldnames(doctype)
	order_no = ""
	order_date = None
	if no_field:
		order_no = doc.get(no_field) or ""
	if date_field:
		order_date = doc.get(date_field)
	return order_no, order_date


def _reference(doc):
	"""Reference No. & Date = Customer Order No + its date, from the Sales Order."""
	po_no, po_date = order_reference(doc, "Sales Invoice")
	if po_no and po_date:
		return po_no, po_date

	so_name = linked_sales_order(doc)
	if so_name:
		so = frappe.get_doc("Sales Order", so_name)
		so_no, so_date = order_reference(so, "Sales Order")
		po_no = po_no or so_no or ""
		po_date = po_date or so_date or so.get("transaction_date")
	return po_no, po_date


def _project_label(doc):
	project = doc.get("project")
	if not project:
		for row in doc.get("items") or []:
			if row.get("project"):
				project = row.project
				break
	if not project:
		return ""
	label = frappe.db.get_value("Project", project, "project_name") or project
	return label


def invoice_ctx(doc):
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	company = frappe.get_doc("Company", doc.company)
	company_addr = _address_block(doc.get("company_address"))
	buyer_addr = _address_block(doc.get("customer_address"))

	ship_name = doc.get("shipping_address_name") or _customer_shipping_address(doc.get("customer"))
	shipping_addr = _address_block(ship_name)
	has_shipping = bool(shipping_addr["lines"])

	company_gstin = doc.get("company_gstin") or company_addr.get("gstin") or ""
	buyer_gstin = doc.get("billing_address_gstin") or buyer_addr.get("gstin") or ""
	shipping_gstin = shipping_addr.get("gstin") or buyer_gstin

	tax_rows = []
	for tax in doc.get("taxes") or []:
		if not flt(tax.base_tax_amount or tax.tax_amount):
			continue
		key = _tax_key(tax.account_head)
		label = {"cgst": "CGST", "sgst": "SGST", "igst": "IGST", "cess": "CESS"}.get(key)
		if not label:
			label = (tax.description or tax.account_head or "").split(" - ")[0]
		tax_rows.append({"label": label, "amount": flt(tax.base_tax_amount or tax.tax_amount)})

	grand = flt(doc.base_grand_total or doc.grand_total)
	rounded_total = flt(doc.base_rounded_total)
	if not rounded_total:
		rounded_total = flt(rounded(grand, 0))
	round_off = flt(rounded_total - grand, 2)

	po_no, po_date = _reference(doc)
	contact = company_contact(doc.company, doc.get("company_address"))
	prepared_by = _prepared_by(doc)

	return {
		"is_einvoice": bool(doc.get("irn")),
		"irn": doc.get("irn") or "",
		"ack_no": doc.get("ack_no") or "",
		"ack_date": fdate(doc.get("ack_date")),
		"qr": qr_base64(doc.get("signed_qr_code")),
		"logo": company.get("company_logo") or "",
		"company": {
			"name": company.company_name,
			"lines": company_addr["lines"],
			"gstin": company_gstin,
			"state": company_addr["state"] or "Tamil Nadu",
			"state_code": company_addr["state_code"] or _state_code(company_gstin),
			"email": contact.get("email") or "",
			"phone": contact.get("phone") or "",
		},
		"buyer": {
			"name": doc.customer_name,
			"lines": buyer_addr["lines"],
			"gstin": buyer_gstin,
			"state": buyer_addr["state"],
			"state_code": buyer_addr["state_code"] or _state_code(buyer_gstin),
		},
		"consignee": {
			"name": (shipping_addr["title"] or doc.customer_name) if has_shipping else doc.customer_name,
			"lines": shipping_addr["lines"] if has_shipping else buyer_addr["lines"],
			"gstin": shipping_gstin,
			"state": (shipping_addr["state"] if has_shipping else buyer_addr["state"]),
			"state_code": (
				shipping_addr["state_code"] if has_shipping else buyer_addr["state_code"]
			)
			or _state_code(shipping_gstin),
			"from_shipping": has_shipping,
		},
		"invoice_no": doc.name,
		"invoice_date": fdate(doc.posting_date),
		"po_no": po_no,
		"po_date": fdate(po_date),
		"project": _project_label(doc),
		"tax_rows": tax_rows,
		"grand_total": grand,
		"round_off": round_off,
		"rounded_total": rounded_total,
		"prepared_by": prepared_by,
		"bank": bank_block(doc=doc, company=doc.company),
		"hsn": hsn_summary(doc),
	}


# ---------------------------------------------------------------- diagnostics


@frappe.whitelist()
def debug_invoice(invoice):
	"""Show exactly what the print format resolves for one Sales Invoice."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Sales Invoice", invoice)

	interesting = ("stage", "portion", "milestone", "sales_order", "payment_term", "project")

	items = []
	for row in doc.get("items") or []:
		fields = {}
		for key, value in (row.as_dict() or {}).items():
			if value in (None, "", 0, 0.0):
				continue
			low = key.lower()
			if key.startswith("sbi_") or any(word in low for word in interesting):
				fields[key] = str(value)[:80]
		so = linked_sales_order(doc, row)
		sched_no, sched_stage, sched_portion = _match_schedule(
			so, row.get("payment_term"), row.get("description")
		)
		items.append(
			{
				"item_code": row.item_code,
				"gst_hsn_code": row.get("gst_hsn_code") or "(EMPTY - set HSN on the Item master)",
				"fields_found": fields,
				"resolved_sales_order": so,
				"schedule_match_idx": sched_no,
				"schedule_stage": sched_stage,
				"schedule_portion": sched_portion,
				"stage_parts": list(stage_parts(row, doc)),
				"stage_line": stage_line(row, doc),
			}
		)

	so_name = linked_sales_order(doc)
	schedule = [
		{
			"idx": r.get("idx"),
			"payment_term": r.get("payment_term"),
			"invoice_portion": r.get("invoice_portion"),
			"stage_fields": {
				f: r.get(f) for f in _SCHEDULE_STAGE_FIELDS if r.get(f)
			},
		}
		for r in _schedule_rows(so_name)
	]

	po_no, po_date = _reference(doc)
	so_ref_fields = _order_ref_fieldnames("Sales Order")
	so_dump = {}
	if so_name:
		so_doc = frappe.get_doc("Sales Order", so_name)
		for key, value in (so_doc.as_dict() or {}).items():
			if value in (None, "", 0, 0.0) or isinstance(value, (list, dict)):
				continue
			low = key.lower()
			if key.startswith("sbi_") or "po_" in low or "order_no" in low or "customer" in low:
				so_dump[key] = str(value)[:60]
	pf = frappe.db.get_value("Print Format", "SBI Tax Invoice", ["modified", "disabled"], as_dict=True)
	html = frappe.db.get_value("Print Format", "SBI Tax Invoice", "html") or ""

	return {
		"invoice": doc.name,
		"invoice_po_no_field": doc.get("po_no"),
		"invoice_po_date_field": str(doc.get("po_date") or ""),
		"invoice_project_field": doc.get("project"),
		"parent_sbi_stage_no": doc.get("sbi_stage_no"),
		"resolved_sales_order": so_name,
		"resolved_reference": [po_no, str(po_date or "")],
		"resolved_project_label": _project_label(doc),
		"order_ref_fieldnames_on_so": list(so_ref_fields),
		"sales_order_fields": so_dump,
		"shipping_address_name": doc.get("shipping_address_name"),
		"payment_schedule": schedule,
		"items": items,
		"print_format_modified": str(pf.modified) if pf else "(missing)",
		"print_format_is_v4": "Prepared By" in html,
	}


# ---------------------------------------------------------------- purchase


def _first_address(doc, fields):
	for field in fields:
		value = doc.get(field)
		if value:
			return value
	return None


def _company_address(company):
	rows = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": "Company", "link_name": company, "parenttype": "Address"},
		pluck="parent",
	)
	if not rows:
		return None
	return frappe.db.get_value(
		"Address",
		{"name": ["in", rows], "disabled": 0},
		"name",
		order_by="is_primary_address desc, modified desc",
	)


def purchase_ctx(doc):
	"""Shared context for the Purchase Order and Purchase Invoice print formats."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Purchase Order", doc)

	is_invoice = doc.doctype == "Purchase Invoice"
	company = frappe.get_doc("Company", doc.company)

	company_addr_name = _first_address(doc, ("billing_address", "company_address")) or _company_address(
		doc.company
	)
	company_addr = _address_block(company_addr_name)
	supplier_addr = _address_block(doc.get("supplier_address"))
	ship_addr = _address_block(_first_address(doc, ("shipping_address", "shipping_address_name")))
	if not ship_addr["lines"]:
		ship_addr = company_addr

	company_gstin = doc.get("company_gstin") or company_addr.get("gstin") or ""
	supplier_gstin = doc.get("supplier_gstin") or supplier_addr.get("gstin") or ""

	tax_rows = []
	for tax in doc.get("taxes") or []:
		amount = flt(tax.base_tax_amount or tax.tax_amount)
		if not amount:
			continue
		key = _tax_key(tax.account_head)
		label = {"cgst": "CGST", "sgst": "SGST", "igst": "IGST", "cess": "CESS"}.get(key)
		if not label:
			label = (tax.description or tax.account_head or "").split(" - ")[0]
		tax_rows.append({"label": label, "amount": amount})

	grand = flt(doc.base_grand_total or doc.grand_total)
	rounded_total = flt(doc.base_rounded_total)
	if not rounded_total:
		rounded_total = flt(rounded(grand, 0))
	round_off = flt(rounded_total - grand, 2)

	if is_invoice:
		ref_label = "Supplier Invoice No. & Date"
		ref_no = doc.get("bill_no") or ""
		ref_date = doc.get("bill_date")
		doc_label = "Invoice No"
		title = "Purchase Invoice"
	else:
		ref_label = "Supplier Quotation / Ref"
		ref_no = doc.get("supplier_quotation") or ""
		ref_date = None
		doc_label = "Order No"
		title = "Purchase Order"

	contact = company_contact(doc.company, company_addr_name)

	project_labels = {}
	for row in doc.get("items") or []:
		value = row.get("project")
		if value and value not in project_labels:
			project_labels[value] = (
				frappe.db.get_value("Project", value, "project_name") or value
			)

	terms = doc.get("terms") or ""
	if not terms and doc.get("tc_name"):
		terms = frappe.db.get_value("Terms and Conditions", doc.tc_name, "terms") or ""

	return {
		"title": title,
		"is_invoice": is_invoice,
		"doc_label": doc_label,
		"doc_no": doc.name,
		"doc_date": fdate(doc.get("transaction_date") or doc.get("posting_date")),
		"ref_label": ref_label,
		"ref_no": ref_no,
		"ref_date": fdate(ref_date),
		"project": _project_label(doc),
		"company": {
			"name": company.company_name,
			"lines": company_addr["lines"],
			"gstin": company_gstin,
			"state": company_addr["state"] or "",
			"state_code": company_addr["state_code"] or _state_code(company_gstin),
			"email": contact.get("email") or "",
			"phone": contact.get("phone") or "",
		},
		"supplier": {
			"name": doc.get("supplier_name") or doc.get("supplier"),
			"lines": supplier_addr["lines"],
			"gstin": supplier_gstin,
			"state": supplier_addr["state"],
			"state_code": supplier_addr["state_code"] or _state_code(supplier_gstin),
		},
		"ship_to": {
			"name": ship_addr["title"] or company.company_name,
			"lines": ship_addr["lines"],
			"gstin": ship_addr["gstin"] or company_gstin,
			"state": ship_addr["state"],
			"state_code": ship_addr["state_code"] or _state_code(company_gstin),
		},
		"logo": company.get("company_logo") or "",
		"tax_rows": tax_rows,
		"grand_total": grand,
		"round_off": round_off,
		"rounded_total": rounded_total,
		"terms": terms,
		"terms_html": terms_html(terms),
		"projects": project_labels,
		"multi_project": len(project_labels) > 1,
		"prepared_by": _prepared_by(doc),
		"hsn": hsn_summary(doc),
	}


# ---------------------------------------------------------------- terms


_BULLET_PREFIX = re.compile(r"^\s*(?:\d+\s*[.)\]]|[-*\u2022\u00b7])\s*")


def terms_to_lines(raw):
	"""Split stored terms (HTML or plain text) into clean one-per-line items."""
	if not raw:
		return []
	text = str(raw)

	if "<li" in text.lower():
		items = re.findall(r"<li[^>]*>(.*?)</li>", text, flags=re.I | re.S)
	else:
		text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.I)
		text = re.sub(r"</\s*(p|div|tr)\s*>", "\n", text, flags=re.I)
		items = text.split("\n")

	lines = []
	for item in items:
		clean = re.sub(r"<[^>]+>", " ", item)
		clean = clean.replace("&nbsp;", " ").replace("&amp;", "&")
		clean = clean.replace("&lt;", "<").replace("&gt;", ">")
		clean = re.sub(r"\s+", " ", clean).strip()
		clean = _BULLET_PREFIX.sub("", clean).strip()
		if clean:
			lines.append(clean)
	return lines


def terms_html(raw):
	"""Render terms as a numbered list: 1. 2. 3."""
	lines = terms_to_lines(raw)
	if not lines:
		return ""
	items = "".join(
		["<li>%s</li>" % frappe.utils.escape_html(line) for line in lines]
	)
	return '<ol class="sbi-terms">%s</ol>' % items


def _prepared_by(doc):
	"""Full name of the user who entered the document."""
	user = doc.get("owner")
	if not user:
		return ""
	employee = frappe.db.get_value(
		"Employee", {"user_id": user, "status": "Active"}, "employee_name"
	)
	return employee or frappe.db.get_value("User", user, "full_name") or user


@frappe.whitelist()
def terms_for(doctype, name):
	"""Feed the 'confirm terms before print' dialog."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	raw = doc.get("terms") or ""
	if not raw and doc.get("tc_name"):
		raw = frappe.db.get_value("Terms and Conditions", doc.tc_name, "terms") or ""
	lines = terms_to_lines(raw)
	return {
		"tc_name": doc.get("tc_name") or "",
		"lines": lines,
		"text": "\n".join(lines),
		"html": terms_html(raw),
	}


@frappe.whitelist()
def terms_template(tc_name):
	raw = frappe.db.get_value("Terms and Conditions", tc_name, "terms") or ""
	lines = terms_to_lines(raw)
	return {"text": "\n".join(lines), "html": terms_html(raw)}


# ---------------------------------------------------------------- contact


def company_contact(company, address_name=None):
	"""Email + phone for the letterhead block: address first, then Company master."""
	out = {"email": "", "phone": "", "address": address_name or ""}

	if not out["address"] and company:
		out["address"] = _company_address(company)

	if out["address"] and frappe.db.exists("Address", out["address"]):
		addr = frappe.db.get_value(
			"Address", out["address"], ["email_id", "phone"], as_dict=True
		)
		if addr:
			out["email"] = addr.email_id or ""
			out["phone"] = addr.phone or ""

	if company and (not out["email"] or not out["phone"]):
		comp = frappe.db.get_value(
			"Company", company, ["email", "phone_no"], as_dict=True
		)
		if comp:
			out["email"] = out["email"] or comp.email or ""
			out["phone"] = out["phone"] or comp.phone_no or ""

	placeholder = ("test@test.com", "test@example.com", "admin@example.com")
	if out["email"].strip().lower() in placeholder:
		out["email"] = ""

	return out


@frappe.whitelist()
def contact_for(doctype, name):
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	address = (
		doc.get("company_address")
		or doc.get("billing_address")
		or _company_address(doc.company)
	)
	out = company_contact(doc.company, address)
	out["company"] = doc.company
	out["can_edit"] = bool(frappe.has_permission("Company", "write"))
	return out


@frappe.whitelist()
def save_company_contact(company, email=None, phone=None, address=None):
	"""Write the corrected email / phone back to the Company (and its address)."""
	frappe.has_permission("Company", "write", throw=True)

	email = (email or "").strip()
	phone = (phone or "").strip()

	if email:
		frappe.utils.validate_email_address(email, throw=True)

	values = {}
	if email:
		values["email"] = email
	if phone:
		values["phone_no"] = phone
	if values:
		frappe.db.set_value("Company", company, values)

	if not address:
		address = _company_address(company)
	if address and frappe.db.exists("Address", address):
		addr_values = {}
		if email:
			addr_values["email_id"] = email
		if phone:
			addr_values["phone"] = phone
		if addr_values:
			frappe.db.set_value("Address", address, addr_values)

	frappe.db.commit()
	return company_contact(company, address)
