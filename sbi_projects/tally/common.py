# Copyright (c) 2026, Velmaska and contributors
"""Shared helpers for the Tally integration: settings, sync log, name lookups."""

import frappe
from frappe.utils import cint, now_datetime

SETTINGS = "Tally Settings"
LOG = "Tally Sync Log"
AGENT_ROLE = "Tally Agent"
MASTER_DOCTYPES = ("Account", "Customer", "Supplier", "Item")
PARTY_NAME_FIELD = {"Customer": "customer_name", "Supplier": "supplier_name", "Employee": "employee_name"}


def settings():
	return frappe.get_single(SETTINGS)


def set_settings(**values):
	"""Write Single fields without running validate or bumping the form's modified."""
	for key, val in values.items():
		frappe.db.set_single_value(SETTINGS, key, val, update_modified=False)


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
	return cint(s.enabled) and cint(s.tally_reachable) and s.company and s.tally_company


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
	return "M|" + doctype + "|" + name


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
