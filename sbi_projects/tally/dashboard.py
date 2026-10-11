# Copyright (c) 2026, Velmaska and contributors
"""Data for the Tally Dashboard page (/app/tally-dashboard)."""

from collections import OrderedDict

import frappe
from frappe.utils import add_months, cint, flt, get_first_day, getdate, nowdate

from sbi_projects.tally.admin import company_condition, get_summary
from sbi_projects.tally.common import contexts, settings

ALL = "__all__"

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
def get_dashboard(from_date=None, to_date=None, company=None):
	frappe.only_for(ROLES)
	s = settings()
	company = company or s.company
	configured = []
	for c in contexts(include_disabled=True):
		if c.company and c.company not in configured:
			configured.append(c.company)
	companies = tuple(configured) if company == ALL else (company,)
	to_date = getdate(to_date or nowdate())
	from_date = getdate(from_date or s.start_date or get_first_day(add_months(to_date, -11)))

	summary = get_summary(None if company == ALL else company)
	health = dict(summary["agent"])
	this = next((c for c in summary["companies"] if c["company"] == company), None)
	if this:
		health.update(tally_reachable=this["ready"], last_error=this["error"], tally_company=this["tally_company"])
	elif company == ALL:
		health.update(tally_reachable=int(all(c["ready"] for c in summary["companies"]) and bool(summary["companies"])),
			tally_company=", ".join(c["tally_company"] for c in summary["companies"]))
	out = {
		"company": company, "from_date": str(from_date), "to_date": str(to_date),
		"companies": summary["companies"], "company_list": configured, "is_all": company == ALL,
		"health": health, "sync_table": summary["table"],
		"pending_export": summary["pending_export"], "today": summary["today"],
	}
	if not company or not companies[0]:
		return out

	# ---------------- masters from Tally
	out["masters"] = {
		"accounts": frappe.db.count("Account", {"company": ["in", companies], "tally_ledger_name": ["is", "set"]}),
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
		where je.docstatus = 1 and je.company in %s and ifnull(je.tally_guid, '') != ''
			and je.posting_date between %s and %s
		order by je.posting_date desc, je.creation desc""", (companies, from_date, to_date), as_dict=True)

	by_type = {}
	by_day = {}
	months = OrderedDict()
	cur = get_first_day(from_date)
	while cur <= to_date:
		months[cur.strftime("%Y-%m")] = {"label": cur.strftime("%b %y"), "count": 0, "amount": 0.0}
		cur = add_months(cur, 1)
	for je in jes:
		t = by_type.setdefault(_vtype(je.tally_voucher), {"count": 0, "amount": 0.0})
		t["count"] += 1
		t["amount"] += flt(je.total_debit)
		day = (str(je.posting_date), _vtype(je.tally_voucher))
		b = by_day.setdefault(day, {"count": 0, "amount": 0.0})
		b["count"] += 1
		b["amount"] += flt(je.total_debit)
		key = getdate(je.posting_date).strftime("%Y-%m")
		if key in months:
			months[key]["count"] += 1
			months[key]["amount"] += flt(je.total_debit)

	out["vouchers"] = {
		"count": len(jes),
		"amount": sum(flt(j.total_debit) for j in jes),
		"by_type": sorted([dict(v, vtype=k) for k, v in by_type.items()], key=lambda r: -r["amount"]),
		"by_month": list(months.values()),
		# one row per (voucher date, Tally voucher type) - the page groups these by day / week / month
		"by_day": [{"date": d, "vtype": t, "count": v["count"], "amount": v["amount"]}
			for (d, t), v in sorted(by_day.items())],
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
			where gle.company in %s and gle.party_type = %s and gle.is_cancelled = 0
				and gle.posting_date <= %s and ifnull(p.tally_ledger_name, '') != ''
			group by gle.party having abs(sum(gle.debit - gle.credit)) >= 1
			order by sum(gle.debit - gle.credit) * %s desc limit %s""".format(pt=party_type),
			(companies, party_type, to_date, sign, limit), as_dict=True)
		name_field = "customer_name" if party_type == "Customer" else "supplier_name"
		for r in rows:
			r["display"] = frappe.db.get_value(party_type, r.party, name_field) or r.party
			r["bal"] = flt(r.bal) * sign
		return rows

	def total(party_type, sign):
		v = frappe.db.sql("""
			select sum(gle.debit - gle.credit) from `tabGL Entry` gle
			join `tab{pt}` p on p.name = gle.party
			where gle.company in %s and gle.party_type = %s and gle.is_cancelled = 0
				and gle.posting_date <= %s and ifnull(p.tally_ledger_name, '') != ''""".format(pt=party_type),
			(companies, party_type, to_date))[0][0]
		return flt(v) * sign

	out["receivable"] = {"total": total("Customer", 1), "top": balances("Customer", 1)}
	out["payable"] = {"total": total("Supplier", -1), "top": balances("Supplier", -1)}

	# ---------------- bank & cash balances
	out["cash_bank"] = frappe.db.sql("""
		select acc.name as account, acc.account_name, acc.account_type, acc.company,
			ifnull(sum(gle.debit - gle.credit), 0) as bal
		from `tabAccount` acc
		left join `tabGL Entry` gle on gle.account = acc.name and gle.is_cancelled = 0 and gle.posting_date <= %s
		where acc.company in %s and acc.is_group = 0 and acc.account_type in ('Bank', 'Cash') and acc.disabled = 0
		group by acc.name order by abs(ifnull(sum(gle.debit - gle.credit), 0)) desc""",
		(to_date, companies), as_dict=True)

	# ---------------- problems
	cond, params = company_condition(None if company == ALL else company)
	out["failed"] = frappe.db.sql("""select name, direction, record_type, tally_name, message, last_attempt
		from `tabTally Sync Log` where status = 'Failed' and """ + cond + """
		order by last_attempt desc limit 10""", params, as_dict=True)
	out["skipped"] = frappe.db.sql("""select name, tally_name, reference_doctype, reference_name, amount, posting_date
		from `tabTally Sync Log` where status = 'Skipped' and """ + cond + """
		order by last_attempt desc limit 10""", params, as_dict=True)
	out["draft_jes"] = frappe.db.count("Journal Entry",
		{"company": ["in", companies], "docstatus": 0, "tally_guid": ["is", "set"]})
	out["invoices"] = _invoices(companies, from_date, to_date)
	return out


def _invoices(companies, from_date, to_date):
	"""Sales / Purchase Invoices created from Tally vouchers (drafts included)."""
	out = {"sales": {"count": 0, "amount": 0.0, "draft": 0, "draft_amount": 0.0},
		"purchase": {"count": 0, "amount": 0.0, "draft": 0, "draft_amount": 0.0},
		"by_company": {}, "by_month": OrderedDict(), "top_customers": [], "top_suppliers": [], "recent": []}
	cur = get_first_day(from_date)
	while cur <= to_date:
		out["by_month"][cur.strftime("%Y-%m")] = {"label": cur.strftime("%b %y"), "sales": 0.0, "purchase": 0.0}
		cur = add_months(cur, 1)
	rows = []
	for dt, kind, party_field in (("Sales Invoice", "sales", "customer"), ("Purchase Invoice", "purchase", "supplier")):
		if not frappe.get_meta(dt).has_field("tally_guid"):
			continue
		name_field = "customer_name" if kind == "sales" else "supplier_name"
		for r in frappe.db.sql("""
				select name, company, posting_date, docstatus, grand_total, {pf} as party, {nf} as party_name,
					tally_voucher
				from `tab{dt}` where docstatus < 2 and company in %s and ifnull(tally_guid, '') != ''
					and posting_date between %s and %s""".format(dt=dt, pf=party_field, nf=name_field),
				(companies, from_date, to_date), as_dict=True):
			r.kind, r.doctype = kind, dt
			rows.append(r)

	parties = {"sales": {}, "purchase": {}}
	for r in rows:
		amt = flt(r.grand_total)
		t = out[r.kind]
		t["count"] += 1
		t["amount"] += amt
		if r.docstatus == 0:
			t["draft"] += 1
			t["draft_amount"] += amt
		c = out["by_company"].setdefault(r.company, {"company": r.company, "sales": 0.0, "sales_count": 0,
			"purchase": 0.0, "purchase_count": 0, "drafts": 0})
		c[r.kind] += amt
		c[r.kind + "_count"] += 1
		c["drafts"] += 1 if r.docstatus == 0 else 0
		m = out["by_month"].get(getdate(r.posting_date).strftime("%Y-%m"))
		if m:
			m[r.kind] += amt
		p = parties[r.kind].setdefault(r.party, {"party": r.party, "display": r.party_name or r.party,
			"amount": 0.0, "count": 0})
		p["amount"] += amt
		p["count"] += 1

	out["by_company"] = sorted(out["by_company"].values(), key=lambda x: x["company"])
	out["by_month"] = list(out["by_month"].values())
	out["top_customers"] = sorted(parties["sales"].values(), key=lambda x: -x["amount"])[:10]
	out["top_suppliers"] = sorted(parties["purchase"].values(), key=lambda x: -x["amount"])[:10]
	out["recent"] = [{"doctype": r.doctype, "name": r.name, "company": r.company, "posting_date": str(r.posting_date),
		"party": r.party, "party_name": r.party_name, "amount": flt(r.grand_total), "draft": r.docstatus == 0,
		"tally_voucher": r.tally_voucher, "kind": r.kind}
		for r in sorted(rows, key=lambda x: (str(x.posting_date), x.name), reverse=True)[:20]]
	return out
