# Copyright (c) 2026, Velmaska and contributors
"""Cash Flow reports. Each Script Report's execute() calls one function here."""

import frappe
from frappe.utils import flt

from sbi_projects.cashflow.engine import (
	CATEGORIES, BOQ_MAP, BUDGET_GROUP, accounts_info, budget_vs_actual_project, check_access, compute,
	petty_cash_jes, project_costs, project_list, project_sales, resolve_companies, resolve_period, site_cash,
)


def _f(filters):
	check_access()
	return frappe._dict(filters or {})


def _money(fieldname, label, width=130):
	return {"fieldname": fieldname, "label": label, "fieldtype": "Currency", "width": width}


def _run(f):
	return compute(f.period, f.from_date, f.to_date, f.company, f.project, f.granularity, light=True)


def _chart(labels, datasets, kind="bar", colors=None):
	return {"data": {"labels": labels, "datasets": datasets}, "type": kind,
		"colors": colors or ["#2a78d6", "#eb6834", "#1baf7a"], "fieldtype": "Currency"}


# ---------------------------------------------------------------- 1. Cash Flow Summary

def cash_flow_summary(filters):
	f = _f(filters)
	d = _run(f)
	c = d["cash"]
	sp = c["split_by_period"]
	cols = [{"fieldname": "period", "label": "Period", "fieldtype": "Data", "width": 120},
		_money("opening", "Opening Cash + Bank"), _money("from_customers", "From Customers"),
		_money("other_receipts", "Other Receipts"), _money("total_in", "Money In"),
		_money("to_suppliers", "To Suppliers"), _money("to_employees", "To Employees"),
		_money("other_payments", "Other Payments"), _money("total_out", "Money Out"),
		_money("net", "Net Cash Flow"), _money("closing", "Closing Cash + Bank")]
	rows, opening = [], c["opening"]
	for i, p in enumerate(d["periods"]):
		row = {"period": p["label"], "opening": opening, "from_customers": sp["From customers"][i],
			"other_receipts": sp["Other receipts"][i], "total_in": c["in"][i], "to_suppliers": sp["To suppliers"][i],
			"to_employees": sp["To employees"][i], "other_payments": sp["Other payments"][i],
			"total_out": c["out"][i], "net": c["in"][i] - c["out"][i], "closing": c["closing"][i]}
		rows.append(row)
		opening = c["closing"][i]
	summary = [
		{"label": "Opening", "value": c["opening"], "datatype": "Currency"},
		{"label": "Money In", "value": sum(c["in"]), "datatype": "Currency", "indicator": "Green"},
		{"label": "Money Out", "value": sum(c["out"]), "datatype": "Currency", "indicator": "Red"},
		{"label": "Closing", "value": c["closing"][-1] if c["closing"] else c["opening"], "datatype": "Currency",
			"indicator": "Blue"},
	]
	chart = _chart(d["labels"], [{"name": "Money In", "values": c["in"]}, {"name": "Money Out", "values": c["out"]}])
	note = "Books of " + ", ".join(d["companies_in_scope"]) + ". Transfers between your own cash/bank accounts are left out."
	return cols, rows, note, chart, summary


# ---------------------------------------------------------------- 2. Expense Split

def expense_split(filters):
	f = _f(filters)
	d = _run(f)
	cols = [{"fieldname": "category", "label": "Category", "fieldtype": "Data", "width": 150}]
	for i, p in enumerate(d["periods"]):
		cols.append(_money("p" + str(i), p["label"], 110))
	cols += [_money("total", "Total"), {"fieldname": "share", "label": "% of Expenses", "fieldtype": "Percent", "width": 110}]
	total_all = sum(d["expense_split"].values())
	rows = []
	for cat in CATEGORIES:
		vals = d["expense_by_period"][cat]
		row = {"category": cat, "total": sum(vals), "share": (sum(vals) / total_all * 100) if total_all else 0}
		row.update({"p" + str(i): v for i, v in enumerate(vals)})
		rows.append(row)
	chart = {"data": {"labels": list(CATEGORIES), "datasets": [{"values": [round(d["expense_split"][c]) for c in CATEGORIES]}]},
		"type": "donut", "colors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]}
	note = ("Project " + f.project + ": site records + entries tagged to the project.") if f.project else \
		"Books. Ledger to category: Cash Flow Settings > Account Map, else by ledger name."
	return cols, rows, note, chart


# ---------------------------------------------------------------- 3. Profit and Loss by Period

def profit_by_period(filters):
	f = _f(filters)
	d = _run(f)
	cols = [{"fieldname": "period", "label": "Period", "fieldtype": "Data", "width": 120}, _money("sales", "Sales")]
	cols += [_money(frappe.scrub(c), c, 115) for c in CATEGORIES]
	cols += [_money("expenses", "Total Expenses"), _money("profit", "Profit / Loss"),
		{"fieldname": "margin", "label": "Margin %", "fieldtype": "Percent", "width": 90}]
	rows = []
	for i, p in enumerate(d["periods"]):
		sales, exp = d["sales_series"][i], d["expense_series"][i]
		row = {"period": p["label"], "sales": sales, "expenses": exp, "profit": sales - exp,
			"margin": ((sales - exp) / sales * 100) if sales else None}
		row.update({frappe.scrub(c): d["expense_by_period"][c][i] for c in CATEGORIES})
		rows.append(row)
	sales, exp = sum(d["sales_series"]), sum(d["expense_series"])
	summary = [
		{"label": "Sales", "value": sales, "datatype": "Currency", "indicator": "Blue"},
		{"label": "Expenses", "value": exp, "datatype": "Currency", "indicator": "Orange"},
		{"label": "Profit" if sales >= exp else "Loss", "value": abs(sales - exp), "datatype": "Currency",
			"indicator": "Green" if sales >= exp else "Red"},
	]
	chart = _chart(d["labels"], [{"name": "Sales", "values": d["sales_series"]},
		{"name": "Expenses", "values": d["expense_series"]}])
	return cols, rows, None, chart, summary


# ---------------------------------------------------------------- 4. Project Profitability

def project_profitability(filters):
	f = _f(filters)
	fr, to = resolve_period(f.period, f.from_date, f.to_date)
	companies = resolve_companies(f.company)
	info = accounts_info(companies)
	pc = petty_cash_jes(companies)
	cols = [{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 140},
		{"fieldname": "project_name", "label": "Name", "fieldtype": "Data", "width": 180},
		{"fieldname": "status", "label": "Status", "fieldtype": "Data", "width": 90}, _money("sales", "Sales")]
	cols += [_money(frappe.scrub(c), c, 110) for c in CATEGORIES]
	cols += [_money("cost", "Total Cost"), _money("profit", "Profit / Loss"),
		{"fieldname": "margin", "label": "Margin %", "fieldtype": "Percent", "width": 90},
		_money("budget", "BOQ Budget"), _money("actual_to_date", "Cost to Date"),
		{"fieldname": "used", "label": "Budget Used %", "fieldtype": "Percent", "width": 110}]
	rows = []
	for p in project_list(companies):
		if f.project and p.name != f.project:
			continue
		row = {"project": p.name, "project_name": p.project_name, "status": p.status}
		row.update({frappe.scrub(c): 0.0 for c in CATEGORIES})
		for _d, cat, amt, _s, _dt, _dn in project_costs(p.name, fr, to, info, pc, companies):
			row[frappe.scrub(cat)] += amt
		row["sales"] = sum(x[1] for x in project_sales(p.name, fr, to, companies))
		row["cost"] = sum(row[frappe.scrub(c)] for c in CATEGORIES)
		row["profit"] = row["sales"] - row["cost"]
		row["margin"] = (row["profit"] / row["sales"] * 100) if row["sales"] else None
		b = budget_vs_actual_project(p.name, to, companies, info, pc)
		row.update(budget=b["budget_total"], actual_to_date=b["actual_total"],
			used=(b["actual_total"] / b["budget_total"] * 100) if b["budget_total"] else None)
		if row["sales"] or row["cost"] or row["budget"]:
			rows.append(row)
	rows.sort(key=lambda r: -r["profit"])
	chart = _chart([r["project"] for r in rows[:15]], [{"name": "Sales", "values": [r["sales"] for r in rows[:15]]},
		{"name": "Cost", "values": [r["cost"] for r in rows[:15]]}])
	return cols, rows, "Sales and costs in the period; BOQ budget and cost to date are for the whole job.", chart


# ---------------------------------------------------------------- 5. Budget vs Actual BOQ

def budget_vs_actual(filters):
	f = _f(filters)
	_fr, to = resolve_period(f.period, f.from_date, f.to_date)
	companies = resolve_companies(f.company)
	info = accounts_info(companies)
	pc = petty_cash_jes(companies)
	cols = [{"fieldname": "name", "label": "Project / Category", "fieldtype": "Data", "width": 260},
		_money("budget", "BOQ Budget"), _money("actual", "Actual to Date"), _money("variance", "Left (Budget - Actual)"),
		{"fieldname": "used", "label": "Used %", "fieldtype": "Percent", "width": 90},
		{"fieldname": "flag", "label": "", "fieldtype": "Data", "width": 110}]
	with_boq = set(frappe.get_all("Project BOQ", pluck="project", ignore_permissions=True)) \
		if frappe.db.exists("DocType", "Project BOQ") else set()
	rows = []
	for p in project_list(companies):
		if (f.project and p.name != f.project) or p.name not in with_boq:
			continue
		b = budget_vs_actual_project(p.name, to, companies, info, pc)
		used = (b["actual_total"] / b["budget_total"] * 100) if b["budget_total"] else None
		rows.append({"name": p.name + " - " + (p.project_name or ""), "indent": 0, "budget": b["budget_total"],
			"actual": b["actual_total"], "variance": b["budget_total"] - b["actual_total"], "used": used,
			"flag": _flag(used)})
		for r in b["rows"]:
			rows.append({"name": r["category"], "indent": 1, "budget": r["budget"], "actual": r["actual"],
				"variance": r["variance"], "used": r["used_pct"], "flag": _flag(r["used_pct"])})
	return cols, rows, "Budget = Project BOQ. Actual = everything booked to the project up to the To date."


def _flag(used):
	if used is None:
		return ""
	return "Over budget" if used > 100 else "Near limit" if used > 85 else "OK"


# ---------------------------------------------------------------- 6. Site Cash Position

def site_cash_position(filters):
	f = _f(filters)
	_fr, to = resolve_period(f.period, f.from_date, f.to_date)
	companies = resolve_companies(f.company)
	cols = [{"fieldname": "project", "label": "Project", "fieldtype": "Link", "options": "Project", "width": 160},
		_money("issued", "Cash Given to Site"), _money("spent", "Spent from Site Cash"),
		_money("balance", "Cash with Site"), _money("petty", "Petty Cash Vouchers")]
	rows = site_cash(companies, to, f.project)
	petty = {}
	if frappe.db.exists("DocType", "Site Petty Cash Voucher"):
		petty = dict(frappe.db.sql("""select project, sum(amount) from `tabSite Petty Cash Voucher`
			where docstatus = 1 and company in %s and posting_date <= %s group by project""", (companies, to)))
	seen = {r["project"] for r in rows}
	for p, amt in petty.items():
		if p and p not in seen and (not f.project or p == f.project):
			rows.append({"project": p, "issued": 0.0, "spent": 0.0, "balance": 0.0})
	for r in rows:
		r["petty"] = flt(petty.get(r["project"]))
	return cols, rows, "All time up to the To date. Cash with Site = given - spent (Site Expense Entries paid from Site Cash)."
