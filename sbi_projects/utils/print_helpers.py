import base64
import io
import json
import re

import frappe
from frappe.utils import flt, formatdate, money_in_words


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
	"""Return base64 PNG for the e-invoice signed QR string."""
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


# ---------------------------------------------------------------- stage line


_STAGE_NO = ("sbi_stage_no", "stage_no", "sbi_stage_index", "sbi_stage_number", "idx_stage")
_STAGE_NAME = ("sbi_stage", "sbi_stage_name", "stage", "stage_name", "sbi_milestone", "milestone")
_STAGE_PCT = (
	"sbi_invoice_portion",
	"invoice_portion",
	"sbi_percentage",
	"sbi_stage_percent",
	"sbi_stage_percentage",
)


def _pick(row, fields):
	for f in fields:
		try:
			value = row.get(f)
		except Exception:
			value = getattr(row, f, None)
		if value not in (None, "", 0, 0.0):
			return value
	return None


def stage_line(row):
	"""Build:  Stage : #2 - Plinth Beam - 30%"""
	stage_no = _pick(row, _STAGE_NO)
	stage_name = _pick(row, _STAGE_NAME)
	portion = _pick(row, _STAGE_PCT)
	term = None
	try:
		term = row.get("payment_term")
	except Exception:
		term = getattr(row, "payment_term", None)

	if not stage_name and term:
		stage_name = term
	if not stage_no and term:
		match = re.search(r"(\d+)", str(term))
		if match:
			stage_no = match.group(1)
	if stage_name:
		stage_name = re.sub(r"^\s*stage\s*[#:\-]*\s*\d*\s*[-:]*\s*", "", str(stage_name), flags=re.I).strip()

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
	out = {"lines": [], "gstin": "", "state": "", "state_code": ""}
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
	return out


def _state_code(state, fallback_gstin=None):
	if fallback_gstin and len(fallback_gstin) >= 2 and fallback_gstin[:2].isdigit():
		return fallback_gstin[:2]
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
	"""item_code -> {cgst: {rate, amount}, ...}"""
	out = {}
	for tax in doc.get("taxes") or []:
		key = _tax_key(tax.account_head)
		if not key or not tax.get("item_wise_tax_detail"):
			continue
		try:
			detail = json.loads(tax.item_wise_tax_detail)
		except Exception:
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


def hsn_summary(doc):
	"""Return {'rows': [...], 'total': {...}, 'has_igst': bool}"""
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	item_tax = _item_wise_tax(doc)
	code_to_hsn = {}
	rows = {}

	for row in doc.get("items") or []:
		hsn = row.get("gst_hsn_code") or row.get("hsn_code") or ""
		code_to_hsn.setdefault(row.item_code, hsn)
		entry = rows.setdefault(
			hsn,
			{
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
			},
		)
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

	out_rows = []
	total = {
		"taxable": 0.0,
		"cgst": 0.0,
		"sgst": 0.0,
		"igst": 0.0,
		"cess": 0.0,
		"total_tax": 0.0,
	}
	for entry in rows.values():
		entry["total_tax"] = entry["cgst"] + entry["sgst"] + entry["igst"] + entry["cess"]
		out_rows.append(entry)
		for key in total:
			total[key] += entry[key]

	out_rows.sort(key=lambda x: x["hsn"] or "")
	has_igst = total["igst"] > 0
	return {"rows": out_rows, "total": total, "has_igst": has_igst}


# ---------------------------------------------------------------- main ctx


def invoice_ctx(doc):
	if isinstance(doc, str):
		doc = frappe.get_doc("Sales Invoice", doc)

	company = frappe.get_doc("Company", doc.company)
	company_addr = _address_block(doc.get("company_address"))
	buyer_addr = _address_block(doc.get("customer_address"))
	shipping_addr = _address_block(doc.get("shipping_address_name"))

	company_gstin = doc.get("company_gstin") or company_addr.get("gstin") or ""
	buyer_gstin = doc.get("billing_address_gstin") or buyer_addr.get("gstin") or ""
	shipping_gstin = shipping_addr.get("gstin") or buyer_gstin

	tax_rows = []
	for tax in doc.get("taxes") or []:
		if not flt(tax.tax_amount):
			continue
		key = _tax_key(tax.account_head)
		label = {
			"cgst": "CGST",
			"sgst": "SGST",
			"igst": "IGST",
			"cess": "CESS",
		}.get(key)
		if not label:
			label = (tax.description or tax.account_head or "").split(" - ")[0]
		tax_rows.append({"label": label, "amount": flt(tax.base_tax_amount or tax.tax_amount)})

	logo = company.get("company_logo") or frappe.db.get_single_value("Website Settings", "app_logo") or ""

	return {
		"is_einvoice": bool(doc.get("irn")),
		"irn": doc.get("irn") or "",
		"ack_no": doc.get("ack_no") or "",
		"ack_date": fdate(doc.get("ack_date")),
		"qr": qr_base64(doc.get("signed_qr_code")),
		"logo": logo,
		"company": {
			"name": company.company_name,
			"lines": company_addr["lines"],
			"gstin": company_gstin,
			"state": company_addr["state"] or "Tamil Nadu",
			"state_code": company_addr["state_code"] or _state_code(None, company_gstin),
			"email": company.get("email") or doc.get("contact_email") or "",
		},
		"buyer": {
			"name": doc.customer_name,
			"lines": buyer_addr["lines"],
			"gstin": buyer_gstin,
			"state": buyer_addr["state"],
			"state_code": buyer_addr["state_code"] or _state_code(None, buyer_gstin),
		},
		"consignee": {
			"name": doc.customer_name,
			"lines": shipping_addr["lines"] or buyer_addr["lines"],
			"gstin": shipping_gstin,
			"state": shipping_addr["state"] or buyer_addr["state"],
			"state_code": shipping_addr["state_code"] or _state_code(None, shipping_gstin),
		},
		"invoice_no": doc.name,
		"invoice_date": fdate(doc.posting_date),
		"po_no": doc.get("po_no") or "",
		"po_date": fdate(doc.get("po_date")),
		"tax_rows": tax_rows,
		"grand_total": flt(doc.base_rounded_total or doc.base_grand_total or doc.grand_total),
		"total_tax": sum([r["amount"] for r in tax_rows]),
		"bank": _bank_block(doc, company),
		"hsn": hsn_summary(doc),
	}


def _bank_block(doc, company):
	name = doc.get("company_bank_account") or company.get("default_bank_account")
	out = {"bank_name": "", "account_no": "", "branch": "", "ifsc": ""}
	if name and frappe.db.exists("Bank Account", name):
		ba = frappe.get_doc("Bank Account", name)
		out["bank_name"] = ba.get("bank") or ""
		out["account_no"] = ba.get("bank_account_no") or ""
		out["branch"] = ba.get("branch_code") or ""
		out["ifsc"] = ba.get("branch_code") or ""
		if ba.get("bank"):
			bank = frappe.db.get_value(
				"Bank", ba.bank, ["bank_name"], as_dict=True
			)
			if bank:
				out["bank_name"] = bank.bank_name
	return out
