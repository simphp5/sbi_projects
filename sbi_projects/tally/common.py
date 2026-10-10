# Copyright (c) 2026, Velmaska and contributors
"""Shared helpers for the Tally integration: settings, sync log, name lookups."""

import frappe
from frappe.utils import cint, now_datetime

SETTINGS = "Tally Settings"
LOG = "Tally Sync Log"
AGENT_ROLE = "Tally Agent"
MASTER_DOCTYPES = ("Account", "Customer", "Supplier", "Item")
PARTY_NAME_FIELD = {"Customer": "customer_name", "Supplier": "supplier_name", "Employee": "employee_name"}


COMPANY_MAP = "Tally Company Map"

# Progress markers kept per Tally company (Settings field -> Tally Company Map field)
ROW_STATE = {
	"current_alt_mst_id": "current_alt_mst_id", "last_alt_mst_id": "last_alt_mst_id",
	"current_alt_vch_id": "current_alt_vch_id", "last_alt_vch_id": "last_alt_vch_id",
	"cancel_cursor": "cancel_cursor", "tally_reachable": "reachable", "last_agent_error": "last_error",
}


def settings():
	"""While the agent's work for one Tally company is processed, this returns that company's
	context (settings + the company's own ERPNext company, dates and progress markers)."""
	ctx = frappe.flags.get("tally_ctx")
	return ctx if ctx else frappe.get_single(SETTINGS)


def set_settings(**values):
	"""Write settings without running validate. Progress markers go to the current Tally
	company's row when a company context is active."""
	ctx = frappe.flags.get("tally_ctx")
	if ctx is not None and ctx.get("row"):
		row_values = {}
		for key in list(values):
			if key in ROW_STATE:
				row_values[ROW_STATE[key]] = values[key]
				ctx[key] = values[key]
				if key == "last_agent_error" and values[key]:
					values[key] = (ctx.tally_company or "") + ": " + values[key]
				else:
					values.pop(key)
		if row_values:
			frappe.db.set_value(COMPANY_MAP, ctx.row, row_values, update_modified=False)
	for key, val in values.items():
		frappe.db.set_single_value(SETTINGS, key, val, update_modified=False)


def reset_state(**values):
	"""Reset progress markers for every Tally company (used by the Sync buttons)."""
	for key, val in values.items():
		frappe.db.set_single_value(SETTINGS, key, val, update_modified=False)
	row_values = {ROW_STATE[k]: v for k, v in values.items() if k in ROW_STATE}
	if row_values:
		for name in frappe.get_all(COMPANY_MAP, filters={"parenttype": SETTINGS}, pluck="name"):
			frappe.db.set_value(COMPANY_MAP, name, row_values, update_modified=False)


# ---------------------------------------------------------------- one context per Tally company
def _translate_group_map(rows, company):
	"""Group Map rows point at accounts of the first company; find the same group in `company`."""
	out = []
	for r in rows or []:
		acc = r.get("erpnext_account")
		if not acc:
			continue
		info = frappe.db.get_value("Account", acc, ["company", "account_name"], as_dict=True)
		if info and info.company != company:
			acc = frappe.db.get_value("Account", {"company": company, "account_name": info.account_name,
				"is_group": 1}, "name")
		if acc:
			out.append(frappe._dict(tally_group=r.get("tally_group"), erpnext_account=acc))
	return out


def contexts(s=None, include_disabled=False):
	s = s or frappe.get_single(SETTINGS)
	base = s.as_dict()
	rows = list(s.get("companies") or [])
	out = []
	if not rows:
		if s.company and s.tally_company:
			c = frappe._dict(base)
			c.update(row=None, rowkey="_", primary=True, key_prefix="",
				group_map=_translate_group_map(base.get("group_map"), s.company))
			out.append(c)
		return out
	for r in rows:
		if not (cint(r.enabled) or include_disabled) or not r.erpnext_company or not r.tally_company:
			continue
		c = frappe._dict(base)
		primary = cint(r.idx) == 1
		c.update(
			row=r.name, rowkey=r.name, primary=primary,
			key_prefix="" if primary else r.tally_company.strip() + "|",
			company=r.erpnext_company, tally_company=r.tally_company.strip(),
			start_date=r.start_date or s.start_date,
			current_alt_mst_id=r.current_alt_mst_id, last_alt_mst_id=r.last_alt_mst_id,
			current_alt_vch_id=r.current_alt_vch_id, last_alt_vch_id=r.last_alt_vch_id,
			cancel_cursor=r.cancel_cursor, tally_reachable=r.reachable,
			group_map=_translate_group_map(base.get("group_map"), r.erpnext_company),
		)
		if c.default_cost_center and frappe.db.get_value("Cost Center", c.default_cost_center, "company") != r.erpnext_company:
			c.default_cost_center = None
		out.append(c)
	return out


def context_for(rowkey):
	for c in contexts(include_disabled=True):
		if c.rowkey == rowkey:
			return c
	return None


TALLY_TO_ERP = "Tally to ERPNext only"
ERP_TO_TALLY = "ERPNext to Tally only"
BOTH = "Both ways"


def direction(s):
	return s.get("sync_direction") or TALLY_TO_ERP


def imports_on(s):
	"""Tally -> ERPNext allowed."""
	return direction(s) in (TALLY_TO_ERP, BOTH)


def exports_on(s):
	"""ERPNext -> Tally allowed."""
	return direction(s) in (ERP_TO_TALLY, BOTH)


def tally_ready(s=None):
	s = s or settings()
	return bool(cint(s.enabled) and cint(s.tally_reachable) and s.company and s.tally_company)


# ---------------------------------------------------------------- sync log
def write_log(key, direction, record_type, status, reference_doctype=None, reference_name=None,
		tally_name=None, tally_guid=None, posting_date=None, amount=None, message=None):
	"""One row per record (upsert on key), so counts on the dashboard are record counts."""
	now = now_datetime()
	name = frappe.db.get_value(LOG, {"log_key": key}, "name")
	values = {
		"direction": direction, "record_type": record_type, "status": status,
		"reference_doctype": reference_doctype, "reference_name": reference_name,
		"tally_name": (tally_name or "")[:140], "tally_guid": tally_guid,
		"posting_date": posting_date, "amount": amount,
		"message": (message or "")[:2000], "last_attempt": now,
	}
	values = {k: v for k, v in values.items() if v is not None or k == "message"}
	ctx = frappe.flags.get("tally_ctx")
	if ctx is not None:
		values["company"] = ctx.get("company")
		values["tally_company"] = ctx.get("tally_company")
	if name:
		row = frappe.db.get_value(LOG, name, ["attempts", "synced_on"], as_dict=True)
		values["attempts"] = cint(row.attempts) + 1
		if status in ("Success", "Linked") and not row.synced_on:
			values["synced_on"] = now
		frappe.db.set_value(LOG, name, values, update_modified=True)
		return name
	doc = frappe.new_doc(LOG)
	doc.update(values)
	doc.log_key = key
	doc.attempts = 1
	if status in ("Success", "Linked"):
		doc.synced_on = now
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def log_status(key):
	return frappe.db.get_value(LOG, {"log_key": key}, "status")


def master_key(doctype, name):
	"""Key of a master's log row. The first Tally company keeps the original keys; others are
	prefixed with their Tally company name, so 'exists in Tally' is tracked per company."""
	ctx = frappe.flags.get("tally_ctx")
	prefix = (ctx.get("key_prefix") or "") if ctx else ""
	return "M|" + prefix + doctype + "|" + name


def known_in_tally(doctype, name):
	return log_status(master_key(doctype, name)) in ("Success", "Linked")


# ---------------------------------------------------------------- names
def account_ledger_name(account):
	row = frappe.db.get_value("Account", account, ["tally_ledger_name", "account_name"], as_dict=True)
	if not row:
		return account
	return (row.tally_ledger_name or row.account_name or account).strip()


def party_ledger_name(party_type, party):
	field = PARTY_NAME_FIELD.get(party_type)
	if party_type in ("Customer", "Supplier"):
		row = frappe.db.get_value(party_type, party, ["tally_ledger_name", field], as_dict=True)
		if row:
			return (row.tally_ledger_name or row.get(field) or party).strip()
	elif field:
		return (frappe.db.get_value(party_type, party, field) or party).strip()
	return party


def short(text, n=140):
	text = (text or "").strip()
	return text if len(text) <= n else text[: n - 1] + "…"
