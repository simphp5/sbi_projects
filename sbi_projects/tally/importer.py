# Copyright (c) 2026, Velmaska and contributors
"""Tally -> ERPNext.

Stage "status":         which companies Tally has open and whether anything changed.
Stage "masters":        groups + ledgers (+ stock items) -> link or create Account /
                        Customer / Supplier / Item.
Stage "import_vouchers": Day Book month by month -> one Journal Entry per Tally
                        voucher. Edits re-post (cancel + amend), deletions cancel.
Stage "opening":        ledger opening balances -> one DRAFT opening Journal Entry.
"""

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

from sbi_projects.tally import tallyxml as tx
from sbi_projects.tally.common import imports_on, master_key, settings, set_settings, short, write_log

PARTY_GROUPS = {"sundry debtors": "Customer", "sundry creditors": "Supplier"}
ACCOUNT_TYPE_BY_GROUP = {
	"bank accounts": "Bank", "bank od a/c": "Bank", "bank occ a/c": "Bank",
	"cash-in-hand": "Cash", "duties & taxes": "Tax",
}
SKIP_GROUPS = {"stock-in-hand"}

# Tally primary group -> candidate ERPNext group account names (first match wins)
DEFAULT_GROUP_MAP = [
	("Bank Accounts", ["Bank Accounts"]),
	("Bank OD A/c", ["Bank Overdraft Account", "Loans (Liabilities)"]),
	("Cash-in-Hand", ["Cash In Hand"]),
	("Duties & Taxes", ["Duties and Taxes"]),
	("Sundry Debtors", ["Accounts Receivable"]),
	("Sundry Creditors", ["Accounts Payable"]),
	("Sales Accounts", ["Direct Income", "Income"]),
	("Purchase Accounts", ["Stock Expenses", "Direct Expenses"]),
	("Direct Incomes", ["Direct Income"]),
	("Indirect Incomes", ["Indirect Income"]),
	("Direct Expenses", ["Direct Expenses"]),
	("Indirect Expenses", ["Indirect Expenses"]),
	("Fixed Assets", ["Fixed Assets"]),
	("Current Assets", ["Current Assets"]),
	("Loans & Advances (Asset)", ["Loans and Advances (Assets)", "Current Assets"]),
	("Deposits (Asset)", ["Securities and Deposits", "Current Assets"]),
	("Investments", ["Investments"]),
	("Misc. Expenses (ASSET)", ["Current Assets"]),
	("Current Liabilities", ["Current Liabilities"]),
	("Provisions", ["Current Liabilities"]),
	("Loans (Liability)", ["Loans (Liabilities)"]),
	("Secured Loans", ["Secured Loans", "Loans (Liabilities)"]),
	("Unsecured Loans", ["Unsecured Loans", "Loans (Liabilities)"]),
	("Capital Account", ["Capital Account", "Capital Stock", "Equity"]),
	("Reserves & Surplus", ["Reserves and Surplus", "Retained Earnings", "Equity"]),
	("Branch / Divisions", ["Current Liabilities"]),
	("Suspense A/c", ["Temporary Accounts", "Current Liabilities"]),
]


# ================================================================ status
def status_jobs(s):
	return [{"id": "status", "xml": tx.status_request()}], False


def process_status(results):
	s = settings()
	res = results[0] if results else {"error": "No answer from agent"}
	if res.get("error"):
		set_settings(tally_reachable=0, last_agent_error=short("Cannot reach TallyPrime: " + res["error"], 500))
		return
	try:
		companies = tx.parse_companies(res.get("response") or "")
	except ValueError as e:
		set_settings(tally_reachable=0, last_agent_error=short(str(e), 500))
		return
	names = [c["name"] for c in companies]
	set_settings(tally_companies="\n".join(names) or "(none)")
	match = next((c for c in companies if c["name"].strip().lower() == (s.tally_company or "").strip().lower()), None)
	if not match:
		set_settings(tally_reachable=0, last_agent_error=short(
			"Company '" + (s.tally_company or "") + "' is not open in TallyPrime. Open companies: " +
			(", ".join(names) or "none"), 500))
		return
	set_settings(tally_reachable=1, last_agent_error="",
		current_alt_mst_id=match["alt_mst_id"], current_alt_vch_id=match["alt_vch_id"])


# ================================================================ lookups
class LedgerIndex:
	"""Tally ledger name -> ERPNext master, built once per run."""

	def __init__(self, company):
		self.company = company
		self.exact, self.loose = {}, {}
		for dt, field in (("Customer", "customer_name"), ("Supplier", "supplier_name")):
			for r in frappe.get_all(dt, fields=["name", field, "tally_ledger_name"], limit_page_length=0):
				self._add(r.tally_ledger_name, r.get(field), r.name, (dt, r.name))
		for r in frappe.get_all("Account", filters={"company": company, "is_group": 0},
				fields=["name", "account_name", "tally_ledger_name"], limit_page_length=0):
			self._add(r.tally_ledger_name, r.account_name, None, ("Account", r.name))

	def _add(self, tally_name, display, docname, target):
		if tally_name:
			self.exact.setdefault(tally_name.strip().lower(), target)
		for n in (display, docname):
			if n:
				self.loose.setdefault(n.strip().lower(), target)

	def find(self, ledger):
		key = (ledger or "").strip().lower()
		return self.exact.get(key) or self.loose.get(key)

	def add(self, ledger, target):
		self.exact[(ledger or "").strip().lower()] = target


def _group_account_map(s):
	return {(r.tally_group or "").strip().lower(): r.erpnext_account for r in s.group_map if r.erpnext_account}


def default_group_rows(company):
	rows = []
	for tally_group, candidates in DEFAULT_GROUP_MAP:
		for cand in candidates:
			acc = frappe.db.get_value("Account", {"company": company, "account_name": cand, "is_group": 1}, "name")
			if acc:
				rows.append({"tally_group": tally_group, "erpnext_account": acc})
				break
	return rows


# ================================================================ masters
def masters_jobs(s):
	if cint(s.current_alt_mst_id) and cint(s.current_alt_mst_id) == cint(s.last_alt_mst_id):
		return [], False
	jobs = [
		{"id": "groups", "xml": tx.groups_request(s.tally_company)},
		{"id": "ledgers", "xml": tx.ledgers_request(s.tally_company)},
	]
	if cint(s.import_stock_items) and imports_on(s):
		jobs.append({"id": "items", "xml": tx.stock_items_request(s.tally_company)})
	return jobs, False


def process_masters(results):
	s = settings()
	by_id = {r["id"]: r for r in results}
	for rid in ("groups", "ledgers"):
		if by_id.get(rid, {}).get("error"):
			set_settings(last_agent_error=short("Reading Tally " + rid + " failed: " + by_id[rid]["error"], 500))
			return
	groups = tx.parse_groups(by_id["groups"]["response"])
	ledgers = tx.parse_ledgers(by_id["ledgers"]["response"])
	index = LedgerIndex(s.company)
	group_map = _group_account_map(s)
	done_guids = set(frappe.get_all("Tally Sync Log",
		filters={"record_type": ["in", ["Ledger", "Party"]], "status": ["in", ["Success", "Linked"]],
			"tally_guid": ["is", "set"]}, pluck="tally_guid"))

	for i, led in enumerate(ledgers):
		if led["guid"] and led["guid"] in done_guids:
			continue
		primary = tx.primary_group(groups, led["parent"]) if led["parent"] else ""
		if not primary or primary.strip().lower() in SKIP_GROUPS:
			continue
		frappe.db.savepoint("tally_ledger")
		try:
			_sync_ledger(s, led, primary, groups, group_map, index)
		except Exception as e:
			frappe.db.rollback(save_point="tally_ledger")
			write_log("T|L|" + (led["guid"] or led["name"]), "Import", "Ledger", "Failed",
				tally_name=led["name"], tally_guid=led["guid"], message=short(_err(e), 1000))
		if i % 50 == 49:
			frappe.db.commit()

	items = by_id.get("items")
	if items and not items.get("error") and cint(s.import_stock_items) and imports_on(s):
		_sync_items(s, tx.parse_stock_items(items["response"]))

	set_settings(last_alt_mst_id=cint(s.current_alt_mst_id))


def _sync_ledger(s, led, primary, groups, group_map, index):
	name = led["name"]
	party_type = PARTY_GROUPS.get(primary.strip().lower())
	target = index.find(name)
	if target and (party_type is None) == (target[0] == "Account"):
		doctype, docname = target
		_set_tally_fields(doctype, docname, name, led["guid"])
		key = master_key(doctype, docname)
		if frappe.db.get_value("Tally Sync Log", {"log_key": key}, "status") in ("Success", "Linked"):
			# created in Tally by an earlier export - keep that history, just remember the GUID
			frappe.db.set_value("Tally Sync Log", {"log_key": key}, "tally_guid", led["guid"], update_modified=False)
			return
		write_log(master_key(doctype, docname), "Import", "Party" if party_type else "Ledger", "Linked",
			doctype, docname, name, led["guid"], message="Matched an existing ERPNext record by name")
		return
	if not cint(s.import_masters) or not imports_on(s):
		return

	if party_type:
		doc = _new_party(s, party_type, name, led)
	else:
		parent = None
		for g in tx.group_chain(groups, led["parent"]):
			parent = group_map.get(g.strip().lower())
			if parent:
				break
		if not parent:
			raise frappe.ValidationError(
				"Tally group '" + led["parent"] + "' (under " + primary + ") has no row in Tally Settings > Group Map")
		doc = frappe.get_doc({
			"doctype": "Account", "account_name": name, "parent_account": parent, "company": s.company,
			"is_group": 0, "account_type": ACCOUNT_TYPE_BY_GROUP.get(primary.strip().lower(), ""),
			"tally_ledger_name": name, "tally_guid": led["guid"],
		})
		doc.flags.ignore_permissions = True
		doc.insert()
	index.add(name, (doc.doctype, doc.name))
	write_log(master_key(doc.doctype, doc.name), "Import", "Party" if party_type else "Ledger", "Success",
		doc.doctype, doc.name, name, led["guid"], amount=None, message="Created from Tally")


def _new_party(s, party_type, name, led):
	if party_type == "Customer":
		doc = frappe.get_doc({
			"doctype": "Customer", "customer_name": name, "customer_type": "Company",
			"customer_group": s.default_customer_group or frappe.db.get_single_value("Selling Settings", "customer_group")
				or "All Customer Groups",
			"territory": s.default_territory or frappe.db.get_single_value("Selling Settings", "territory")
				or "All Territories",
		})
	else:
		doc = frappe.get_doc({
			"doctype": "Supplier", "supplier_name": name, "supplier_type": "Company",
			"supplier_group": s.default_supplier_group or frappe.db.get_single_value("Buying Settings", "supplier_group")
				or "All Supplier Groups",
		})
	doc.tally_ledger_name = name
	doc.tally_guid = led["guid"]
	if led.get("gstin") and doc.meta.has_field("gstin"):
		doc.gstin = led["gstin"]
	doc.flags.ignore_permissions = True
	try:
		doc.insert()
	except Exception:
		if not doc.get("gstin"):
			raise
		frappe.db.rollback(save_point="tally_ledger")
		frappe.db.savepoint("tally_ledger")
		doc = frappe.get_doc(doc.as_dict())  # retry without a GSTIN Tally may hold in another format
		doc.name = None
		doc.gstin = None
		doc.flags.ignore_permissions = True
		doc.insert()
	return doc


def _set_tally_fields(doctype, docname, ledger, guid):
	values = {"tally_ledger_name": ledger}
	if guid:
		values["tally_guid"] = guid
	frappe.db.set_value(doctype, docname, values, update_modified=False)


def _sync_items(s, items):
	done = set(frappe.get_all("Tally Sync Log",
		filters={"record_type": "Stock Item", "status": ["in", ["Success", "Linked"]], "tally_guid": ["is", "set"]},
		pluck="tally_guid"))
	has_hsn = frappe.get_meta("Item").has_field("gst_hsn_code")
	for i, it in enumerate(items):
		if it["guid"] and it["guid"] in done:
			continue
		frappe.db.savepoint("tally_item")
		try:
			existing = (it["guid"] and frappe.db.get_value("Item", {"tally_guid": it["guid"]}, "name")) or \
				frappe.db.get_value("Item", {"item_code": it["name"][:140]}, "name")
			if existing:
				_set_tally_fields("Item", existing, it["name"], it["guid"])
				write_log(master_key("Item", existing), "Import", "Stock Item", "Linked", "Item", existing,
					it["name"], it["guid"], message="Matched an existing Item by code")
				continue
			if not cint(s.import_masters) or not imports_on(s):
				continue
			doc = frappe.get_doc({
				"doctype": "Item", "item_code": it["name"][:140], "item_name": it["name"][:140],
				"item_group": _item_group(s, it["parent"]), "stock_uom": _uom(it["uom"]),
				"is_stock_item": 1, "include_item_in_manufacturing": 0,
				"tally_ledger_name": it["name"], "tally_guid": it["guid"],
			})
			if has_hsn and it["hsn"] and frappe.db.exists("GST HSN Code", it["hsn"]):
				doc.gst_hsn_code = it["hsn"]
			doc.flags.ignore_permissions = True
			doc.insert()
			write_log(master_key("Item", doc.name), "Import", "Stock Item", "Success", "Item", doc.name,
				it["name"], it["guid"], message="Created from Tally")
		except Exception as e:
			frappe.db.rollback(save_point="tally_item")
			write_log("T|I|" + (it["guid"] or it["name"]), "Import", "Stock Item", "Failed",
				tally_name=it["name"], tally_guid=it["guid"], message=short(_err(e), 1000))
		if i % 50 == 49:
			frappe.db.commit()


def _item_group(s, tally_group):
	if tally_group:
		if frappe.db.exists("Item Group", tally_group):
			return tally_group
		doc = frappe.get_doc({"doctype": "Item Group", "item_group_name": tally_group,
			"parent_item_group": s.default_item_group or "All Item Groups", "is_group": 0})
		doc.flags.ignore_permissions = True
		doc.insert()
		return doc.name
	return s.default_item_group or "All Item Groups"


def _uom(uom):
	uom = (uom or "").strip() or "Nos"
	if not frappe.db.exists("UOM", uom):
		doc = frappe.get_doc({"doctype": "UOM", "uom_name": uom})
		doc.flags.ignore_permissions = True
		doc.insert()
	return uom


# ================================================================ vouchers
def voucher_months(s):
	start = getdate(s.start_date)
	end = getdate(add_days(nowdate(), 31))
	months, cur = [], get_first_day(start)
	while cur <= end:
		months.append((max(cur, start), min(get_last_day(cur), end)))
		cur = add_months(cur, 1)
	return months


def import_vouchers_jobs(s):
	if not cint(s.import_vouchers) or not imports_on(s):
		return [], False
	if cint(s.current_alt_vch_id) and cint(s.current_alt_vch_id) == cint(s.last_alt_vch_id):
		return [], False
	jobs = []
	for frm, to in voucher_months(s):
		jobs.append({"id": "dbk|" + str(frm) + "|" + str(to), "xml": tx.daybook_request(s.tally_company, frm, to)})
	return jobs, False


def process_import_vouchers(results):
	s = settings()
	complete = all(not r.get("error") for r in results)
	vouchers, range_end, checked_months = [], None, []
	for r in results:
		_, frm, to = r["id"].split("|")
		range_end = max(range_end or to, to)
		if r.get("error"):
			continue
		try:
			month = tx.parse_vouchers(r["response"])
		except ValueError as e:
			complete = False
			set_settings(last_agent_error=short("Day Book " + frm + " to " + to + ": " + str(e), 500))
			continue
		vouchers += month
		if month:
			# an empty month is never trusted as "everything was deleted"
			checked_months.append((frm, to))

	exported = {(n or "").strip().lower() for n in frappe.get_all("Tally Sync Log",
		filters={"direction": "Export", "record_type": "Voucher"}, pluck="tally_name")}
	live = {r.tally_guid: r for r in frappe.get_all("Journal Entry",
		filters={"tally_guid": ["is", "set"], "docstatus": ["<", 2], "company": s.company},
		fields=["name", "tally_guid", "tally_alter_id", "docstatus", "posting_date"], limit_page_length=0)}
	index = LedgerIndex(s.company)
	start = getdate(s.start_date)
	seen = set()

	for i, v in enumerate(vouchers):
		if not v["guid"] or not v["date"] or getdate(v["date"]) < start:
			continue
		seen.add(v["guid"])
		if v["optional"] or _is_ours(v, exported):
			continue
		je = live.get(v["guid"])
		key = "V|I|" + v["guid"]
		label = (v["vtype"] + " " + v["number"]).strip()
		frappe.db.savepoint("tally_vch")
		try:
			if v["cancelled"] or v["deleted"]:
				if je:
					_remove_je(je.name)
					write_log(key, "Import", "Voucher", "Deleted", "Journal Entry", je.name, label, v["guid"],
						v["date"], _amount(v), "Cancelled in Tally - Journal Entry cancelled")
				continue
			if je and cint(je.tally_alter_id) == v["alter_id"]:
				continue
			new = _make_je(s, v, index, amend=je.name if je else None)
			write_log(key, "Import", "Voucher", "Success", "Journal Entry", new, label, v["guid"], v["date"],
				_amount(v), "Updated in Tally - re-posted as " + new if je else "")
		except Exception as e:
			frappe.db.rollback(save_point="tally_vch")
			write_log(key, "Import", "Voucher", "Failed", "Journal Entry", je.name if je else None, label,
				v["guid"], v["date"], _amount(v), short(_err(e), 1500))
		if i % 25 == 24:
			frappe.db.commit()

	if complete and range_end:
		gone = [(guid, je) for guid, je in live.items() if guid not in seen and
			any(frm <= str(je.posting_date) <= to for frm, to in checked_months)]
		in_range = [je for je in live.values() if start <= getdate(je.posting_date) <= getdate(range_end)]
		if len(gone) > 5 and len(gone) > 0.2 * len(in_range):
			# guard against a partial Day Book (Tally filter, educational mode, etc.)
			set_settings(last_agent_error=short(str(len(gone)) + " imported Tally vouchers look deleted in Tally. "
				"Not cancelling them automatically - check Tally, then use Re-check Tally Vouchers.", 500))
			gone = []
		for guid, je in gone:
			frappe.db.savepoint("tally_vch")
			try:
				_remove_je(je.name)
				write_log("V|I|" + guid, "Import", "Voucher", "Deleted", "Journal Entry", je.name,
					message="Deleted in Tally - Journal Entry cancelled")
			except Exception as e:
				frappe.db.rollback(save_point="tally_vch")
				write_log("V|I|" + guid, "Import", "Voucher", "Failed", "Journal Entry", je.name,
					message="Deleted in Tally, but cancelling in ERPNext failed: " + short(_err(e), 900))

	if complete:
		set_settings(last_alt_vch_id=cint(s.current_alt_vch_id))


def _is_ours(v, exported):
	if v["remote_id"].startswith(tx.REMOTE_PREFIX) or v["guid"].startswith(tx.REMOTE_PREFIX):
		return True
	return (v["vtype"] + " " + v["number"]).strip().lower() in exported


def _amount(v):
	return round(sum(l["net"] for l in v["lines"] if l["net"] > 0), 2)


def _remove_je(name):
	doc = frappe.get_doc("Journal Entry", name)
	doc.flags.ignore_permissions = True
	if doc.docstatus == 1:
		doc.cancel()
	elif doc.docstatus == 0:
		frappe.delete_doc("Journal Entry", name, ignore_permissions=True, force=True)


def _resolve(index, company, ledger):
	target = index.find(ledger)
	if not target:
		raise frappe.ValidationError("Tally ledger '" + ledger + "' has no matching Account, Customer or Supplier in ERPNext")
	doctype, name = target
	if doctype == "Account":
		return {"account": name}
	from erpnext.accounts.party import get_party_account
	return {"account": get_party_account(doctype, name, company), "party_type": doctype, "party": name}


def _bill_reference(row, bill_name):
	dt = {"Customer": "Sales Invoice", "Supplier": "Purchase Invoice"}.get(row.get("party_type"))
	if not dt:
		return None
	field = "customer" if dt == "Sales Invoice" else "supplier"
	if frappe.db.exists(dt, {"name": bill_name, "docstatus": 1, field: row["party"]}):
		return dt
	return None


def _je_rows(s, v, index, with_refs):
	cost_center = s.default_cost_center or frappe.get_cached_value("Company", s.company, "cost_center")
	rows = []

	def add(base, net, **extra):
		if not round(net, 2):
			return
		row = dict(base, cost_center=cost_center, **extra)
		row["debit_in_account_currency"] = round(net, 2) if net > 0 else 0
		row["credit_in_account_currency"] = round(-net, 2) if net < 0 else 0
		rows.append(row)

	for line in v["lines"]:
		base = _resolve(index, s.company, line["ledger"])
		if base.get("party") and line["bills"]:
			used = 0.0
			for bill_name, bill_type, amt in line["bills"]:
				extra = {}
				ref_dt = _bill_reference(base, bill_name) if with_refs and bill_type.lower() == "agst ref" else None
				if ref_dt:
					extra = {"reference_type": ref_dt, "reference_name": bill_name}
				elif bill_type.lower() == "advance":
					extra = {"is_advance": "Yes"}
				add(base, amt, **extra)
				used += amt
			add(base, line["net"] - used)
		else:
			add(base, line["net"])
	return rows


def _je_type(s, v, rows):
	vt = v["vtype"].lower()
	if "credit note" in vt:
		return "Credit Note"
	if "debit note" in vt:
		return "Debit Note"
	types = [frappe.get_cached_value("Account", r["account"], "account_type") for r in rows if not r.get("party")]
	bank = "Bank" in types
	cash = "Cash" in types
	if rows and not any(r.get("party") for r in rows) and all(t in ("Bank", "Cash") for t in types):
		return "Contra Entry"
	if bank:
		return "Bank Entry"
	if cash:
		return "Cash Entry"
	return "Journal Entry"


def _make_je(s, v, index, amend=None):
	if not v["lines"]:
		raise frappe.ValidationError("Voucher has no ledger lines")
	if v["imbalance"]:
		raise frappe.ValidationError("Voucher does not balance (difference " + str(v["imbalance"]) +
			") - ledgers: " + ", ".join(l["ledger"] for l in v["lines"]))

	def build(with_refs):
		rows = _je_rows(s, v, index, with_refs)
		je = frappe.new_doc("Journal Entry")
		je.company = s.company
		je.posting_date = v["date"]
		je.voucher_type = _je_type(s, v, rows)
		je.cheque_no = short(v["reference"] or v["number"] or v["guid"], 140)
		je.cheque_date = v["date"]
		remark = "Tally " + v["vtype"] + " " + v["number"]
		je.user_remark = (v["narration"] + "\n" if v["narration"] else "") + remark
		je.tally_guid = v["guid"]
		je.tally_voucher = short(v["vtype"] + " " + v["number"], 140)
		je.tally_alter_id = v["alter_id"]
		je.tally_sync_status = "Synced"
		for row in rows:
			je.append("accounts", row)
		return je

	if amend:
		_remove_je(amend)
	je = build(True)
	if amend and frappe.db.get_value("Journal Entry", amend, "docstatus") == 2:
		je.amended_from = amend
	je.flags.ignore_permissions = True
	try:
		je.insert()
		if cint(s.submit_imported):
			je.submit()
	except Exception:
		has_refs = any(r.get("reference_name") for r in je.accounts)
		if not has_refs:
			raise
		# a bill reference ERPNext won't accept (amount / side mismatch) must not block the voucher
		frappe.db.rollback(save_point="tally_vch")
		frappe.db.savepoint("tally_vch")
		if amend and frappe.db.exists("Journal Entry", amend):
			if frappe.db.get_value("Journal Entry", amend, "docstatus") != 2:
				_remove_je(amend)
		je = build(False)
		if amend and frappe.db.get_value("Journal Entry", amend, "docstatus") == 2:
			je.amended_from = amend
		je.flags.ignore_permissions = True
		je.insert()
		if cint(s.submit_imported):
			je.submit()
	return je.name


# ================================================================ opening balances
def opening_jobs(s):
	if not cint(s.opening_requested) or not imports_on(s):
		return [], False
	return [{"id": "opening", "xml": tx.ledgers_request(s.tally_company)}], False


def process_opening(results):
	s = settings()
	res = results[0] if results else {"error": "No answer"}
	if res.get("error"):
		set_settings(opening_requested=0, opening_status=short("Failed: " + res["error"], 500))
		return
	index = LedgerIndex(s.company)
	rows, missing, skipped = [], [], []
	cost_center = s.default_cost_center or frappe.get_cached_value("Company", s.company, "cost_center")
	for led in tx.parse_ledgers(res["response"]):
		net = round(led["opening_net"], 2)
		if not net:
			continue
		target = index.find(led["name"])
		if not target:
			missing.append(led["name"])
			continue
		base = _resolve(index, s.company, led["name"])
		acc = frappe.get_cached_value("Account", base["account"], ["report_type", "account_type"], as_dict=True)
		if acc.report_type == "Profit and Loss" or acc.account_type == "Stock":
			skipped.append(led["name"])
			continue
		base.update(cost_center=cost_center,
			debit_in_account_currency=net if net > 0 else 0, credit_in_account_currency=-net if net < 0 else 0)
		rows.append(base)

	if not rows:
		set_settings(opening_requested=0, opening_status="No opening balances found to import.")
		return
	diff = round(sum(r["debit_in_account_currency"] - r["credit_in_account_currency"] for r in rows), 2)
	if diff:
		temp = frappe.db.get_value("Account", {"company": s.company, "account_type": "Temporary", "is_group": 0}, "name")
		if not temp:
			set_settings(opening_requested=0, opening_status="Failed: no Temporary Opening account in " + s.company)
			return
		rows.append({"account": temp, "cost_center": cost_center,
			"debit_in_account_currency": -diff if diff < 0 else 0, "credit_in_account_currency": diff if diff > 0 else 0})

	je = frappe.new_doc("Journal Entry")
	je.company = s.company
	je.voucher_type = "Opening Entry"
	je.is_opening = "Yes"
	je.posting_date = s.opening_date or s.start_date
	je.user_remark = "Opening balances imported from Tally company " + s.tally_company
	je.tally_sync_status = "Skip"
	for r in rows:
		je.append("accounts", r)
	je.flags.ignore_permissions = True
	je.insert()
	write_log("O|" + je.name, "Import", "Opening Balance", "Success", "Journal Entry", je.name,
		"Opening balances", posting_date=je.posting_date, amount=je.total_debit,
		message=str(len(rows)) + " lines (draft)")
	status = "Draft " + je.name + " created with " + str(len(rows)) + " lines. Check it and submit."
	if skipped:
		status += "\nSkipped (income/expense or stock): " + ", ".join(skipped[:30])
	if missing:
		status += "\nNot found in ERPNext (run a masters sync first): " + ", ".join(missing[:30])
	set_settings(opening_requested=0, opening_status=short(status, 2000))


def _err(e):
	msg = str(e) or e.__class__.__name__
	return frappe.utils.strip_html(msg)
