# Copyright (c) 2026, Velmaska and contributors
"""Buttons on the Tally Settings form, the summary panel and dashboard number cards."""

import frappe
from frappe.utils import cint, get_url, now_datetime, time_diff_in_seconds

from sbi_projects.tally import exporter, importer
from sbi_projects.tally.common import AGENT_ROLE, LOG, SETTINGS, imports_on, settings, set_settings

MANAGERS = ("System Manager", "Accounts Manager")


# ---------------------------------------------------------------- agent key
@frappe.whitelist()
def generate_agent_key():
	"""Create (or reuse) the agent user and issue a fresh API key + secret.
	Returns the agent's config.json content. The secret is shown only this once."""
	frappe.only_for("System Manager")
	s = settings()
	email = s.agent_user or ("tally.agent@" + (frappe.local.site or "erpnext.local"))
	if not frappe.db.exists("User", email):
		user = frappe.get_doc({
			"doctype": "User", "email": email, "first_name": "Tally", "last_name": "Agent",
			"user_type": "System User", "send_welcome_email": 0, "enabled": 1,
			"roles": [{"role": r} for r in (AGENT_ROLE, "Accounts User") if frappe.db.exists("Role", r)],
		})
		user.flags.ignore_permissions = True
		user.insert()
	user = frappe.get_doc("User", email)
	have = {r.role for r in user.roles}
	for role in (AGENT_ROLE, "Accounts Manager", "Accounts User", "Item Manager",
			"Sales Master Manager", "Purchase Master Manager"):
		if role not in have and frappe.db.exists("Role", role):
			user.append("roles", {"role": role})
	if not user.api_key:
		user.api_key = frappe.generate_hash(length=15)
	secret = frappe.generate_hash(length=15)
	user.api_secret = secret
	user.flags.ignore_permissions = True
	user.save()
	set_settings(agent_user=email)
	frappe.db.commit()
	return {
		"erpnext_url": get_url(),
		"api_key": user.api_key,
		"api_secret": secret,
		"tally_url": "",
		"_note": "Keep this file private. tally_url is optional: leave empty to use Host/Port from Tally Settings.",
	}


# ---------------------------------------------------------------- setup helpers
@frappe.whitelist()
def load_default_group_map():
	frappe.only_for(MANAGERS)
	doc = frappe.get_single(SETTINGS)
	if not doc.company:
		frappe.throw("Select the ERPNext Company first.")
	have = {(r.tally_group or "").strip().lower() for r in doc.group_map}
	added = 0
	for row in importer.default_group_rows(doc.company):
		if row["tally_group"].lower() not in have:
			doc.append("group_map", row)
			added += 1
	doc.save()
	return added


@frappe.whitelist()
def request_opening(opening_date=None):
	frappe.only_for(MANAGERS)
	if not imports_on(settings()):
		frappe.throw("Opening balances come from Tally. Set Sync Direction to 'Tally to ERPNext only' or 'Both ways' first.")
	values = {"opening_requested": 1, "opening_status": "Waiting for the agent's next sync..."}
	if opening_date:
		values["opening_date"] = opening_date
	set_settings(**values)
	return "ok"


@frappe.whitelist()
def resync_masters():
	frappe.only_for(MANAGERS)
	set_settings(last_alt_mst_id=0)
	return "ok"


@frappe.whitelist()
def reimport_vouchers():
	frappe.only_for(MANAGERS)
	set_settings(last_alt_vch_id=0)
	return "ok"


@frappe.whitelist()
def retry_failed():
	"""Failed ERPNext vouchers go back in the queue; failed ledger exports are tried again;
	failed Tally imports are re-read on the next sync."""
	frappe.only_for(MANAGERS)
	s = settings()
	vouchers = 0
	for doctype, _ in exporter.DOCTYPES:
		names = frappe.get_all(doctype, filters={"tally_sync_status": "Failed", "company": s.company}, pluck="name")
		for n in names:
			frappe.db.set_value(doctype, n, "tally_sync_status", "Retry", update_modified=False)
		vouchers += len(names)
	masters = frappe.db.delete(LOG, {"status": "Failed", "record_type": ["in", ["Ledger", "Party", "Stock Item"]]})
	set_settings(last_alt_mst_id=0, last_alt_vch_id=0)
	return {"vouchers": vouchers}


@frappe.whitelist()
def import_anyway(log_name):
	"""A Tally voucher was skipped as a duplicate, but the user says it is a separate transaction."""
	frappe.only_for(MANAGERS)
	log = frappe.get_doc(LOG, log_name)
	if log.direction != "Import" or log.record_type != "Voucher" or log.status != "Skipped" or not log.tally_guid:
		frappe.throw("Only Tally vouchers skipped as duplicates can be imported this way.")
	s = settings()
	guids = {g for g in (s.force_import_guids or "").split() if g}
	guids.add(log.tally_guid)
	set_settings(force_import_guids="\n".join(sorted(guids)), last_alt_vch_id=0)
	frappe.db.set_value(LOG, log_name, {"status": "Failed", "reference_doctype": None, "reference_name": None,
		"message": "Marked 'Import Anyway' - will be imported on the next sync."})
	return "ok"


@frappe.whitelist()
def repair_party_ledgers(dry_run=1):
	"""Undo Accounts that an earlier sync wrongly created for Tally customer / supplier ledgers
	(ledgers under Sundry Debtors / Creditors), so the next sync creates them as Customers and
	Suppliers. Only Accounts this integration created are touched. Also gives Bank / Cash / Tax
	ledgers created from Tally the account type of their group."""
	frappe.only_for("System Manager")
	dry_run = cint(dry_run)
	s = settings()
	roots = [r.erpnext_account for r in s.group_map
		if (r.tally_group or "").strip().lower() in ("sundry debtors", "sundry creditors") and r.erpnext_account]
	if not roots:
		frappe.throw("Group Map has no rows for Sundry Debtors / Sundry Creditors.")
	bounds = [frappe.db.get_value("Account", r, ["lft", "rgt"], as_dict=True) for r in roots]
	bounds = [b for b in bounds if b]

	created = frappe.get_all(LOG, filters={"direction": "Import", "record_type": "Ledger", "status": "Success",
		"reference_doctype": "Account"}, fields=["name", "reference_name"], limit_page_length=0)
	wrong = []
	for row in created:
		acc = frappe.db.get_value("Account", row.reference_name, ["lft", "rgt", "is_group"], as_dict=True)
		if acc and not acc.is_group and any(b.lft < acc.lft and acc.rgt < b.rgt for b in bounds):
			wrong.append(row)
	names = [w.reference_name for w in wrong]

	tally_jes, blocked = set(), {}
	if names:
		for je in set(frappe.get_all("Journal Entry Account", filters={"account": ["in", names]}, pluck="parent")):
			if frappe.db.get_value("Journal Entry", je, "tally_guid"):
				tally_jes.add(je)
		for g in frappe.get_all("GL Entry", filters={"account": ["in", names]},
				fields=["account", "voucher_type", "voucher_no"], limit_page_length=0):
			if not (g.voucher_type == "Journal Entry" and g.voucher_no in tally_jes):
				blocked.setdefault(g.account, g.voucher_type + " " + g.voucher_no)
	fixable = [w for w in wrong if w.reference_name not in blocked]

	typed = []
	for row in created:
		acc = frappe.db.get_value("Account", row.reference_name, ["account_type", "parent_account"], as_dict=True)
		if acc and not acc.account_type and acc.parent_account:
			ptype = frappe.db.get_value("Account", acc.parent_account, "account_type")
			if ptype in ("Bank", "Cash", "Tax"):
				typed.append((row.reference_name, ptype))

	summary = {
		"wrong_accounts": len(wrong), "will_remove": len(fixable),
		"blocked": [a + " (used in " + v + ")" for a, v in list(blocked.items())[:20]],
		"tally_journal_entries": sorted(tally_jes), "account_types_to_set": len(typed),
		"sample": [w.reference_name for w in fixable[:10]],
	}
	if dry_run:
		return summary

	for je in tally_jes:
		doc = frappe.get_doc("Journal Entry", je)
		if doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()
		for dt in ("GL Entry", "Payment Ledger Entry"):
			frappe.db.delete(dt, {"voucher_type": "Journal Entry", "voucher_no": je})
		frappe.delete_doc("Journal Entry", je, ignore_permissions=True, force=True)
		frappe.db.delete(LOG, {"reference_doctype": "Journal Entry", "reference_name": je, "direction": "Import"})
	for w in fixable:
		frappe.delete_doc("Account", w.reference_name, ignore_permissions=True, force=True)
		frappe.db.delete(LOG, {"name": w.name})
	for name, ptype in typed:
		if frappe.db.exists("Account", name):
			frappe.db.set_value("Account", name, "account_type", ptype)
	set_settings(last_alt_mst_id=0, last_alt_vch_id=0)
	frappe.db.commit()
	summary["done"] = 1
	return summary


# ---------------------------------------------------------------- summary
@frappe.whitelist()
def get_summary():
	s = settings()
	rows = frappe.db.sql("""
		select record_type, direction, status, count(*) as n
		from `tabTally Sync Log` group by record_type, direction, status""", as_dict=True)
	table = {}
	for r in rows:
		t = table.setdefault(r.record_type, {"Exported": 0, "Imported": 0, "Linked": 0, "Skipped": 0, "Failed": 0, "Deleted": 0})
		if r.status == "Success":
			t["Exported" if r.direction == "Export" else "Imported"] += r.n
		elif r.status in t:
			t[r.status] += r.n

	seconds = None
	if s.last_heartbeat:
		seconds = time_diff_in_seconds(now_datetime(), s.last_heartbeat)
	online = seconds is not None and seconds < max(cint(s.poll_seconds) or 120, 30) * 3 + 60

	return {
		"agent": {
			"online": online, "seconds_ago": seconds, "version": s.agent_version, "host": s.agent_host,
			"user": s.agent_user, "tally_reachable": cint(s.tally_reachable),
			"companies": s.tally_companies, "last_error": s.last_agent_error,
			"last_sync_on": s.last_sync_on, "enabled": cint(s.enabled),
		},
		"table": table,
		"pending_export": pending_export_count()["value"],
		"today": _today_counts(),
	}


def _today_counts():
	rows = frappe.db.sql("""
		select direction, count(*) as n from `tabTally Sync Log`
		where status = 'Success' and date(synced_on) = curdate() group by direction""", as_dict=True)
	return {r.direction: r.n for r in rows}


@frappe.whitelist()
def pending_export_count(filters=None):
	"""Number Card (Custom): ERPNext vouchers waiting to go to Tally."""
	s = settings()
	total = 0
	if s.company and s.start_date:
		for doctype in exporter.enabled_doctypes(s):
			cond = [["docstatus", "=", 1], ["company", "=", s.company], ["posting_date", ">=", s.start_date]]
			if doctype == "Journal Entry":
				cond.append(["tally_guid", "is", "not set"])
			total += frappe.db.count(doctype, cond + [["tally_sync_status", "is", "not set"]])
			total += frappe.db.count(doctype, cond + [["tally_sync_status", "=", "Retry"]])
	return {"value": total, "fieldtype": "Int"}
