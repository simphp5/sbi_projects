# Copyright (c) 2026, Velmaska and contributors
"""Data for the Tally Dashboard page (/app/tally-dashboard)."""

from collections import OrderedDict

import frappe
from frappe.utils import add_months, cint, flt, get_first_day, getdate, nowdate

from sbi_projects.tally.admin import get_summary
from sbi_projects.tally.common import settings

ROLES = ("System Manager", "Accounts Manager", "Accounts User")


def _vtype(tally_voucher):
	"""'Credit Note 12' -> 'Credit Note'"""
	text = (tally_voucher or "").strip()
	if " " in text:
		head, tail = text.rsplit(" ", 1)
		if any(ch.isdigit() for ch in tail):
			return head.strip()
	return text or "Unknown"


@frappe.whitelist()
def get_dashboard(from_date=None, to_date=None):
	frappe.only_for(ROLES)
	s = settings()
	company = s.company
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or s.start_date or get_first_day(add_months(to_date, -11)))

	summary = get_summary()
	out = {
		"company": company, "from_date": str(from_date), "to_date": str(to_date),
		"health": summary["agent"], "sync_table": summary["table"],
		"pending_export": summary["pending_export"], "today": summary["today"],
	}
	if not company:
		return out

	# ---------------- masters from Tally
	out["masters"] = {
		"accounts": frappe.db.count("Account", {"company": company, "tally_ledger_name": ["is", "set"]}),
		"customers": frappe.db.count("Customer", {"tally_ledger_name": ["is", "set"]}),
		"suppliers": frappe.db.count("Supplier", {"tally_ledger_name": ["is", "set"]}),
		"items": frappe.db.count("Item", {"tally_ledger_name": ["is", "set"]}),
	}

	# ---------------- imported vouchers in the period
	jes = frappe.db.sql("""
		select je.name, je.posting_date, je.tally_voucher, je.total_debit, je.user_remark,
			(select jea.party from `tabJournal Entry Account` jea
				where jea.parent = je.name and ifnull(jea.party, '') != '' order by jea.idx limit 1) as party,
			(select jea.party_type from `tabJournal Entry Account` jea
				where jea.parent = je.name and ifnull(jea.party, '') != '' order by jea.idx limit 1) as party_type
		from `tabJournal Entry` je
		where je.docstatus = 1 and je.company = %s and ifnull(je.tally_guid, '') != ''
			and je.posting_date between %s and %s
		order by je.posting_date desc, je.creation desc""", (company, from_date, to_date), as_dict=True)

	by_type = {}
	months = OrderedDict()
	cur = get_first_day(from_date)
	while cur <= to_date:
		months[cur.strftime("%Y-%m")] = {"label": cur.strftime("%b %y"), "count": 0, "amount": 0.0}
		cur = add_months(cur, 1)
	for je in jes:
		t = by_type.setdefault(_vtype(je.tally_voucher), {"count": 0, "amount": 0.0})
		t["count"] += 1
		t["amount"] += flt(je.total_debit)
		key = getdate(je.posting_date).strftime("%Y-%m")
		if key in months:
			months[key]["count"] += 1
			months[key]["amount"] += flt(je.total_debit)

	out["vouchers"] = {
		"count": len(jes),
		"amount": sum(flt(j.total_debit) for j in jes),
		"by_type": sorted([dict(v, vtype=k) for k, v in by_type.items()], key=lambda r: -r["amount"]),
		"by_month": list(months.values()),
		"recent": [{
			"name": j.name, "posting_date": str(j.posting_date), "tally_voucher": j.tally_voucher,
			"party": j.party, "party_type": j.party_type, "amount": flt(j.total_debit),
		} for j in jes[:15]],
	}

	# ---------------- party balances (Tally customers / suppliers), as on to_date
	def balances(party_type, sign, limit=10):
		rows = frappe.db.sql("""
			select gle.party, sum(gle.debit - gle.credit) as bal
			from `tabGL Entry` gle
			join `tab{pt}` p on p.name = gle.party
			where gle.company = %s and gle.party_type = %s and gle.is_cancelled = 0
				and gle.posting_date <= %s and ifnull(p.tally_ledger_name, '') != ''
			group by gle.party having abs(sum(gle.debit - gle.credit)) >= 1
			order by sum(gle.debit - gle.credit) * %s desc limit %s""".format(pt=party_type),
			(company, party_type, to_date, sign, limit), as_dict=True)
		name_field = "customer_name" if party_type == "Customer" else "supplier_name"
		for r in rows:
			r["display"] = frappe.db.get_value(party_type, r.party, name_field) or r.party
			r["bal"] = flt(r.bal) * sign
		return rows

	def total(party_type, sign):
		v = frappe.db.sql("""
			select sum(gle.debit - gle.credit) from `tabGL Entry` gle
			join `tab{pt}` p on p.name = gle.party
			where gle.company = %s and gle.party_type = %s and gle.is_cancelled = 0
				and gle.posting_date <= %s and ifnull(p.tally_ledger_name, '') != ''""".format(pt=party_type),
			(company, party_type, to_date))[0][0]
		return flt(v) * sign

	out["receivable"] = {"total": total("Customer", 1), "top": balances("Customer", 1)}
	out["payable"] = {"total": total("Supplier", -1), "top": balances("Supplier", -1)}

	# ---------------- bank & cash balances
	out["cash_bank"] = frappe.db.sql("""
		select acc.name as account, acc.account_name, acc.account_type,
			ifnull(sum(gle.debit - gle.credit), 0) as bal
		from `tabAccount` acc
		left join `tabGL Entry` gle on gle.account = acc.name and gle.is_cancelled = 0 and gle.posting_date <= %s
		where acc.company = %s and acc.is_group = 0 and acc.account_type in ('Bank', 'Cash') and acc.disabled = 0
		group by acc.name order by abs(ifnull(sum(gle.debit - gle.credit), 0)) desc""",
		(to_date, company), as_dict=True)

	# ---------------- problems
	out["failed"] = frappe.get_all("Tally Sync Log", filters={"status": "Failed"},
		fields=["name", "direction", "record_type", "tally_name", "message", "last_attempt"],
		order_by="last_attempt desc", limit_page_length=10)
	out["skipped"] = frappe.get_all("Tally Sync Log", filters={"status": "Skipped"},
		fields=["name", "tally_name", "reference_doctype", "reference_name", "amount", "posting_date"],
		order_by="last_attempt desc", limit_page_length=10)
	out["draft_jes"] = frappe.db.count("Journal Entry",
		{"company": company, "docstatus": 0, "tally_guid": ["is", "set"]})
	return out
