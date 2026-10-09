# Copyright (c) 2026, Velmaska and contributors
"""ERPNext -> Tally.

Stage "export_masters": create in Tally every ledger that a pending voucher
needs (accounts and parties), plus new Customers / Suppliers if enabled.
Stage "export_vouchers": send submitted vouchers, and delete in Tally the
vouchers whose ERPNext document was cancelled.
"""

import frappe
from frappe.utils import cint, get_datetime, getdate, now_datetime

from sbi_projects.tally import tallyxml as tx
from sbi_projects.tally.common import (
	account_ledger_name, known_in_tally, master_key, party_ledger_name, settings, set_settings,
	short, write_log,
)

DOCTYPES = (
	("Sales Invoice", "export_sales_invoice"),
	("Purchase Invoice", "export_purchase_invoice"),
	("Payment Entry", "export_payment_entry"),
	("Journal Entry", "export_journal_entry"),
)

HEADER_FIELDS = {
	"Sales Invoice": ["is_return", "remarks", "po_no", "base_grand_total as amount"],
	"Purchase Invoice": ["is_return", "remarks", "bill_no", "base_grand_total as amount"],
	"Payment Entry": ["payment_type", "remarks", "reference_no", "base_paid_amount as amount"],
	"Journal Entry": ["voucher_type", "is_opening", "user_remark", "cheque_no", "total_debit as amount"],
}

REMOTE_CODE = {"Sales Invoice": "SI", "Purchase Invoice": "PI", "Payment Entry": "PE", "Journal Entry": "JE"}

ROOT_TYPE_GROUP = {
	"Asset": "Current Assets", "Liability": "Current Liabilities", "Equity": "Capital Account",
	"Income": "Indirect Incomes", "Expense": "Indirect Expenses",
}
ACCOUNT_TYPE_GROUP = {"Bank": "Bank Accounts", "Cash": "Cash-in-Hand", "Tax": "Duties & Taxes"}


def enabled_doctypes(s):
	if not cint(s.export_enabled):
		return []
	return [dt for dt, flag in DOCTYPES if cint(s.get(flag))]


# ---------------------------------------------------------------- pending vouchers
def pending_docs(s, doctype, limit):
	fields = ["name", "posting_date", "modified"] + HEADER_FIELDS[doctype]
	base = [["docstatus", "=", 1], ["company", "=", s.company], ["posting_date", ">=", s.start_date]]
	if doctype == "Journal Entry":
		base.append(["tally_guid", "is", "not set"])
	docs = frappe.get_all(doctype, filters=base + [["tally_sync_status", "=", "Retry"]], fields=fields,
		order_by="posting_date asc, name asc", limit_page_length=limit)
	if len(docs) < limit:
		docs += frappe.get_all(doctype, filters=base + [["tally_sync_status", "is", "not set"]],
			fields=fields, order_by="posting_date asc, name asc", limit_page_length=limit - len(docs))
	return docs


def gl_lines(doctype, name, bill_wise):
	"""GL Entries netted per Tally ledger, with the ERPNext master behind each line."""
	gl = frappe.get_all("GL Entry",
		filters={"voucher_type": doctype, "voucher_no": name, "is_cancelled": 0},
		fields=["account", "party_type", "party", "debit", "credit", "against_voucher"],
		order_by="creation asc")
	lines, order = {}, []
	for g in gl:
		net = float(g.debit or 0) - float(g.credit or 0)
		if g.party_type and g.party:
			ledger = party_ledger_name(g.party_type, g.party)
			master = (g.party_type, g.party)
		else:
			ledger = account_ledger_name(g.account)
			master = ("Account", g.account)
		key = ledger.lower()
		if key not in lines:
			lines[key] = {"ledger": ledger, "net": 0.0, "is_party": bool(g.party), "master": master, "bills": {}}
			order.append(key)
		line = lines[key]
		line["net"] += net
		if g.party and bill_wise:
			if g.against_voucher and g.against_voucher != name:
				ref = (g.against_voucher, "Agst Ref")
			elif doctype in ("Sales Invoice", "Purchase Invoice"):
				ref = (name, "New Ref")
			else:
				ref = (name, "On Account")
			line["bills"][ref] = line["bills"].get(ref, 0.0) + net
	out = []
	for key in order:
		line = lines[key]
		line["net"] = round(line["net"], 2)
		line["bills"] = [(r, t, round(a, 2)) for (r, t), a in line["bills"].items() if round(a, 2)]
		if line["net"]:
			out.append(line)
	return out


def voucher_type(s, doctype, head):
	if doctype == "Sales Invoice":
		return s.vt_sales_return if head.is_return else s.vt_sales
	if doctype == "Purchase Invoice":
		return s.vt_purchase_return if head.is_return else s.vt_purchase
	if doctype == "Payment Entry":
		return {"Receive": s.vt_receipt, "Pay": s.vt_payment, "Internal Transfer": s.vt_contra}.get(
			head.payment_type, s.vt_payment)
	return {"Contra Entry": s.vt_contra, "Credit Note": s.vt_sales_return,
		"Debit Note": s.vt_purchase_return}.get(head.voucher_type, s.vt_journal)


def mark(doctype, name, status, error=""):
	values = {"tally_sync_status": status, "tally_sync_error": (error or "")[:1000]}
	if status == "Synced":
		values["tally_synced_on"] = now_datetime()
	frappe.db.set_value(doctype, name, values, update_modified=False)


# ---------------------------------------------------------------- masters
def _reverse_group_map(s):
	return {row.erpnext_account: row.tally_group for row in s.group_map if row.erpnext_account}


def tally_group_for_account(account, reverse_map):
	acc = frappe.db.get_value("Account", account, ["lft", "rgt", "root_type", "account_type"], as_dict=True)
	if not acc:
		return "Suspense A/c"
	if acc.account_type in ACCOUNT_TYPE_GROUP:
		return ACCOUNT_TYPE_GROUP[acc.account_type]
	ancestors = frappe.get_all("Account", filters={"lft": ["<", acc.lft], "rgt": [">", acc.rgt]},
		pluck="name", order_by="lft desc")
	for anc in ancestors:
		if anc in reverse_map:
			return reverse_map[anc]
	return ROOT_TYPE_GROUP.get(acc.root_type, "Suspense A/c")


def master_job(s, doctype, name, reverse_map):
	gstin = None
	if doctype == "Account":
		ledger = account_ledger_name(name)
		parent = tally_group_for_account(name, reverse_map)
		billwise = False
	else:
		ledger = party_ledger_name(doctype, name)
		parent = s.tally_customer_group if doctype == "Customer" else s.tally_supplier_group
		billwise = cint(s.bill_wise)
		if doctype in ("Customer", "Supplier") and frappe.get_meta(doctype).has_field("gstin"):
			gstin = frappe.db.get_value(doctype, name, "gstin")
	xml = tx.import_envelope(s.tally_company, "All Masters", tx.ledger_xml(ledger, parent, billwise, gstin))
	return {"id": "m|" + doctype + "|" + name, "xml": xml, "label": ledger}


def export_masters_jobs(s):
	if not enabled_doctypes(s) and not cint(s.export_new_parties):
		return [], False
	reverse_map = _reverse_group_map(s)
	needed, seen = [], set()
	limit = cint(s.batch_size) or 25
	for doctype in enabled_doctypes(s):
		for head in pending_docs(s, doctype, limit):
			for line in gl_lines(doctype, head.name, cint(s.bill_wise)):
				master = line["master"]
				if master not in seen and not known_in_tally(*master):
					seen.add(master)
					needed.append(master)

	more = False
	if cint(s.export_new_parties):
		for doctype in ("Customer", "Supplier"):
			rows = frappe.db.sql("""
				select p.name from `tab{dt}` p
				left join `tabTally Sync Log` l on l.log_key = concat('M|{dt}|', p.name)
				where p.disabled = 0 and l.name is null
				order by p.creation limit 101""".format(dt=doctype), as_dict=True)
			more = more or len(rows) > 100
			for r in rows[:100]:
				if (doctype, r.name) not in seen:
					seen.add((doctype, r.name))
					needed.append((doctype, r.name))

	return [master_job(s, dt, name, reverse_map) for dt, name in needed], more


def process_export_masters(results):
	for res in results:
		_, doctype, name = res["id"].split("|", 2)
		key = master_key(doctype, name)
		record_type = "Ledger" if doctype == "Account" else "Party"
		label = res.get("label") or name
		if res.get("error"):
			write_log(key, "Export", record_type, "Failed", doctype, name, label, message=res["error"])
			continue
		parsed = tx.parse_import_response(res.get("response") or "")
		if tx.import_ok(parsed) or tx.already_exists(parsed):
			status = "Success" if tx.import_ok(parsed) else "Linked"
			write_log(key, "Export", record_type, status, doctype, name, label,
				message="" if status == "Success" else "Ledger already existed in Tally - linked")
			if doctype in ("Account", "Customer", "Supplier"):
				if not frappe.db.get_value(doctype, name, "tally_ledger_name"):
					frappe.db.set_value(doctype, name, "tally_ledger_name", label, update_modified=False)
		else:
			write_log(key, "Export", record_type, "Failed", doctype, name, label,
				message=tx.describe_error(parsed))


# ---------------------------------------------------------------- vouchers
def export_vouchers_jobs(s):
	jobs = []
	limit = cint(s.batch_size) or 25
	more = False
	for doctype in enabled_doctypes(s):
		docs = pending_docs(s, doctype, limit)
		more = more or len(docs) >= limit
		for head in docs:
			job = _voucher_job(s, doctype, head)
			if job:
				jobs.append(job)
	if cint(s.sync_cancellations):
		jobs += _delete_jobs(s)
	return jobs, more


def _voucher_job(s, doctype, head):
	name = head.name
	if doctype == "Journal Entry" and head.is_opening == "Yes":
		mark(doctype, name, "Skip", "Opening entry - opening balances are not sent to Tally")
		return None
	lines = gl_lines(doctype, name, cint(s.bill_wise))
	if not lines:
		mark(doctype, name, "Skip", "No accounting impact")
		return None
	if round(sum(l["net"] for l in lines), 2):
		mark(doctype, name, "Failed", "Debit and credit do not match after netting")
		return None
	missing = [l["ledger"] for l in lines if not known_in_tally(*l["master"])]
	if missing:
		reasons = []
		for l in lines:
			if l["ledger"] in missing:
				msg = frappe.db.get_value("Tally Sync Log", {"log_key": master_key(*l["master"])}, "message")
				reasons.append("'" + l["ledger"] + "'" + (" (" + msg + ")" if msg else ""))
		mark(doctype, name, "Failed", "Ledger could not be created in Tally: " + ", ".join(reasons) +
			". Fix it, then set Tally Sync Status to Retry.")
		write_log("V|E|" + doctype + "|" + name, "Export", "Voucher", "Failed", doctype, name, name,
			posting_date=head.posting_date, amount=head.amount, message="Missing ledger: " + ", ".join(missing))
		return None

	vtype = voucher_type(s, doctype, head)
	remark = (head.get("remarks") or head.get("user_remark") or "").strip()
	if remark.lower() == "no remarks":
		remark = ""
	narration = (remark[:400] + " | " if remark else "") + "ERPNext " + doctype + " " + name
	reference = head.get("bill_no") or head.get("reference_no") or head.get("cheque_no") or head.get("po_no") or ""
	remote_id = tx.REMOTE_PREFIX + REMOTE_CODE[doctype] + ":" + name
	body = tx.voucher_xml(vtype, name, head.posting_date, narration, reference, lines, remote_id)
	return {"id": "v|" + doctype + "|" + name, "xml": tx.import_envelope(s.tally_company, "Vouchers", body),
		"vtype": vtype, "posting_date": str(head.posting_date), "amount": head.amount}


def _delete_jobs(s):
	jobs = []
	cursor = get_datetime(s.cancel_cursor or str(s.start_date) + " 00:00:00")
	newest = cursor
	for doctype in enabled_doctypes(s):
		rows = frappe.get_all(doctype,
			filters=[["docstatus", "=", 2], ["company", "=", s.company], ["modified", ">=", cursor]],
			fields=["name", "modified", "posting_date"], order_by="modified asc", limit_page_length=200)
		for r in rows:
			newest = max(newest, get_datetime(r.modified))
			if frappe.db.get_value("Tally Sync Log", {"log_key": "V|E|" + doctype + "|" + r.name}, "status") == "Success":
				jobs.append(_delete_job(s, doctype, r.name))
	# deletions that failed before are retried
	for row in frappe.get_all("Tally Sync Log",
			filters={"direction": "Export", "record_type": "Voucher", "status": "Failed",
				"message": ["like", "Delete failed%"]},
			fields=["reference_doctype", "reference_name"], limit_page_length=50):
		jobs.append(_delete_job(s, row.reference_doctype, row.reference_name))
	if newest != cursor:
		set_settings(cancel_cursor=newest)
	return [j for j in jobs if j]


def _delete_job(s, doctype, name):
	log = frappe.db.get_value("Tally Sync Log", {"log_key": "V|E|" + doctype + "|" + name},
		["tally_name", "posting_date"], as_dict=True)
	if not log or not log.tally_name or not log.posting_date:
		return None
	vtype = log.tally_name.rsplit(" ", 1)[0] if " " in log.tally_name else log.tally_name
	body = tx.delete_voucher_xml(vtype, name, log.posting_date)
	return {"id": "d|" + doctype + "|" + name, "xml": tx.import_envelope(s.tally_company, "Vouchers", body)}


def process_export_vouchers(results):
	for res in results:
		kind, doctype, name = res["id"].split("|", 2)
		info = res
		key = "V|E|" + doctype + "|" + name
		parsed = None if res.get("error") else tx.parse_import_response(res.get("response") or "")
		error = res.get("error") or (None if parsed and tx.import_ok(parsed) else tx.describe_error(parsed))

		if kind == "d":
			ok = parsed and (parsed["deleted"] or parsed["cancelled"] or tx.import_ok(parsed))
			if ok:
				write_log(key, "Export", "Voucher", "Deleted", doctype, name,
					message="Cancelled in ERPNext - deleted in Tally")
			else:
				write_log(key, "Export", "Voucher", "Failed", doctype, name,
					message="Delete failed: " + (res.get("error") or tx.describe_error(parsed)))
			continue

		tally_name = (info.get("vtype") or "") + " " + name
		if error:
			mark(doctype, name, "Failed", error)
			write_log(key, "Export", "Voucher", "Failed", doctype, name, tally_name,
				posting_date=info.get("posting_date"), amount=info.get("amount"), message=error)
		else:
			mark(doctype, name, "Synced")
			write_log(key, "Export", "Voucher", "Success", doctype, name, tally_name,
				tally_guid=tx.REMOTE_PREFIX + REMOTE_CODE[doctype] + ":" + name,
				posting_date=info.get("posting_date"), amount=info.get("amount"), message="")
