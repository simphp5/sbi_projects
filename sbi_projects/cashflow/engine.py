# Copyright (c) 2026, Velmaska and contributors
"""Cash Flow (owner view): one engine behind the dashboard page and the reports.

Two sources, as agreed:
- No project picked -> the books. GL Entries (ERPNext + everything imported from Tally):
  income accounts = sales, expense accounts = costs split into 7 categories, cash/bank
  accounts = money in / out.
- A project picked -> that project's site records (petty cash vouchers, material issues,
  site expense entries, labour attendance x daily wage) plus any GL entries tagged with the
  project, and its Project BOQ as the budget.

Expense category of an account: Cash Flow Settings > Account Map (an account or any parent
group), else a guess from the account name (see KEYWORDS).
"""

from collections import OrderedDict

import frappe
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate, nowdate

ROLES = ("Business Owner",)
CATEGORIES = ("Petty Cash", "Material", "Equipment", "Employee", "Transport", "Subcontracting", "Other")
# BOQ budget columns -> our categories (petty cash and transport are budgeted under 'other')
BOQ_MAP = OrderedDict([
	("Employee", ("labour_amount",)),
	("Material", ("material_amount",)),
	("Equipment", ("equipment_amount",)),
	("Subcontracting", ("subcontract_amount",)),
	("Other", ("other_amount",)),
])
BUDGET_GROUP = {"Petty Cash": "Other", "Transport": "Other"}
KEYWORDS = (
	("Petty Cash", ("petty", "site cash", "imprest")),
	("Subcontracting", ("subcontract", "sub contract", "sub-contract", "contractor", "job work", "labour contract")),
	("Transport", ("transport", "freight", "carriage", "cartage", "lorry", "truck", "vehicle", "loading",
		"unloading", "courier", "shifting", "conveyance", "travel")),
	("Equipment", ("equipment", "machinery", "machine", "hire", "rent of", "rental", "crane", "jcb", "hydra",
		"scaffold", "tools", "generator", "dg set", "repair")),
	("Employee", ("salary", "salaries", "wage", "labour", "labor", "staff", "employee", "esi", "provident",
		" pf", "bonus", "gratuity", "incentive", "mess", "welfare", "manpower")),
	("Material", ("material", "purchase", "cost of goods", "consumable", "steel", "cement", "sand",
		"aggregate", "brick", "paint", "electrical", "plumbing", "hardware", "stock", "raw")),
)
PERIODS = ("Today", "This Week", "This Month", "This Quarter", "This Half Year", "This Financial Year",
	"Last Month", "Last Quarter", "Last Financial Year", "Custom")


def check_access():
	frappe.only_for(ROLES)


# ---------------------------------------------------------------- dates

def fy_start(d):
	d = getdate(d)
	return getdate(f"{d.year if d.month >= 4 else d.year - 1}-04-01")


def resolve_period(period=None, from_date=None, to_date=None):
	"""-> (from, to) for a preset. Financial year April-March, halves Apr-Sep / Oct-Mar."""
	today = getdate(nowdate())
	period = period or "This Financial Year"
	if period == "Custom":
		f = getdate(from_date or fy_start(today))
		t = getdate(to_date or today)
		return (f, t) if f <= t else (t, f)
	if period == "Today":
		return today, today
	if period == "This Week":
		start = add_days(today, -today.weekday())
		return getdate(start), today
	if period == "This Month":
		return get_first_day(today), today
	if period == "Last Month":
		last = add_months(get_first_day(today), -1)
		return getdate(last), get_last_day(last)
	q_start = getdate(f"{today.year}-{((today.month - 1) // 3) * 3 + 1:02d}-01")
	if period == "This Quarter":
		return q_start, today
	if period == "Last Quarter":
		start = getdate(add_months(q_start, -3))
		return start, getdate(add_days(q_start, -1))
	fy = fy_start(today)
	if period == "This Half Year":
		half = fy if today < getdate(add_months(fy, 6)) else getdate(add_months(fy, 6))
		return half, today
	if period == "Last Financial Year":
		start = getdate(add_months(fy, -12))
		return start, getdate(add_days(fy, -1))
	return fy, today


def auto_granularity(from_date, to_date):
	days = (getdate(to_date) - getdate(from_date)).days + 1
	return "Daily" if days <= 31 else "Weekly" if days <= 120 else "Monthly"


def make_periods(from_date, to_date, granularity=None):
	"""Ordered buckets [{key, label, start, end}] covering the range."""
	f, t = getdate(from_date), getdate(to_date)
	g = granularity if granularity in ("Daily", "Weekly", "Monthly", "Quarterly") else auto_granularity(f, t)
	out = []
	if g == "Daily":
		cur = f
		while cur <= t:
			out.append({"key": str(cur), "label": cur.strftime("%d %b"), "start": cur, "end": cur})
			cur = getdate(add_days(cur, 1))
	elif g == "Weekly":
		cur = getdate(add_days(f, -f.weekday()))
		while cur <= t:
			end = getdate(add_days(cur, 6))
			out.append({"key": str(cur), "label": "Wk " + cur.strftime("%d %b"), "start": max(cur, f),
				"end": min(end, t)})
			cur = getdate(add_days(cur, 7))
	elif g == "Quarterly":
		cur = getdate(f"{f.year}-{((f.month - 1) // 3) * 3 + 1:02d}-01")
		while cur <= t:
			end = getdate(add_days(add_months(cur, 3), -1))
			fyq = (cur.month - 4) % 12 // 3 + 1
			out.append({"key": str(cur), "label": f"Q{fyq} " + cur.strftime("%b %y"), "start": max(cur, f),
				"end": min(end, t)})
			cur = getdate(add_months(cur, 3))
	else:
		cur = get_first_day(f)
		while cur <= t:
			out.append({"key": cur.strftime("%Y-%m"), "label": cur.strftime("%b %y"), "start": max(cur, f),
				"end": min(get_last_day(cur), t)})
			cur = getdate(add_months(cur, 1))
	for p in out:
		p["start"], p["end"] = str(p["start"]), str(p["end"])
	return g, out


def bucket_of(periods):
	"""date -> period index (periods are contiguous and sorted)."""
	starts = [getdate(p["start"]) for p in periods]

	def find(d):
		d = getdate(d)
		idx = None
		for i, s in enumerate(starts):
			if d >= s:
				idx = i
			else:
				break
		return idx
	return find


# ---------------------------------------------------------------- scope

def company_list():
	return frappe.get_all("Company", pluck="name", order_by="name")


def resolve_companies(company=None):
	all_ = company_list()
	if company and company != "__all__" and company in all_:
		return (company,)
	return tuple(all_) or ("",)


# ---------------------------------------------------------------- accounts

def _account_map():
	try:
		rows = frappe.db.sql("""select account, category from `tabCash Flow Account Map`
			where parenttype = 'Cash Flow Settings'""", as_dict=True)
	except Exception:
		rows = []
	out = []
	for r in rows:
		if not r.account or r.category not in CATEGORIES:
			continue
		lft, rgt = frappe.db.get_value("Account", r.account, ["lft", "rgt"]) or (None, None)
		if lft is not None:
			out.append((cint(lft), cint(rgt), r.category))
	# most specific (deepest) mapping wins
	out.sort(key=lambda m: -m[0])
	return out


def guess_category(name):
	text = " " + (name or "").lower() + " "
	for cat, words in KEYWORDS:
		if any(w in text for w in words):
			return cat
	return "Other"


def accounts_info(companies):
	"""{account: {root_type, account_type, category}} for the companies."""
	mapping = _account_map()
	info = {}
	for a in frappe.get_all("Account", filters={"company": ["in", companies]},
			fields=["name", "account_name", "root_type", "account_type", "lft", "rgt", "parent_account"],
			ignore_permissions=True):
		cat = None
		if a.root_type == "Expense":
			for lft, rgt, c in mapping:
				if lft <= cint(a.lft) and cint(a.rgt) <= rgt:
					cat = c
					break
			if not cat:
				cat = guess_category((a.account_name or "") + " " + (a.parent_account or ""))
		info[a.name] = frappe._dict(root_type=a.root_type, account_type=a.account_type or "", category=cat,
			account_name=a.account_name)
	return info


def petty_cash_jes(companies):
	if not frappe.db.exists("DocType", "Site Petty Cash Voucher"):
		return set()
	return set(frappe.get_all("Site Petty Cash Voucher", filters={"company": ["in", companies],
		"docstatus": 1, "journal_entry": ["is", "set"]}, pluck="journal_entry", ignore_permissions=True))


def gl_rows(companies, from_date, to_date, root_types=("Income", "Expense"), project=None):
	cond = ["company in %(companies)s", "is_cancelled = 0", "posting_date between %(f)s and %(t)s"]
	if project:
		cond.append("project = %(project)s")
	return frappe.db.sql("""
		select gle.posting_date, gle.account, gle.debit, gle.credit, gle.voucher_type, gle.voucher_no,
			gle.party_type, gle.party, gle.project
		from `tabGL Entry` gle
		where """ + " and ".join(cond) + """
			and gle.account in (select name from `tabAccount` where root_type in %(roots)s and company in %(companies)s)""",
		{"companies": companies, "f": from_date, "t": to_date, "roots": tuple(root_types), "project": project},
		as_dict=True)


# ---------------------------------------------------------------- project (site records)

def _site_rows(project, from_date, to_date):
	"""[(date, category, amount, source, ref_doctype, ref_name)] from the site records."""
	rows = []
	f, t = str(from_date), str(to_date)

	def has(dt):
		return frappe.db.exists("DocType", dt)

	if has("Site Petty Cash Voucher"):
		for r in frappe.get_all("Site Petty Cash Voucher", filters={"project": project, "docstatus": 1,
				"posting_date": ["between", [f, t]]}, fields=["name", "posting_date", "amount", "paid_to"],
				ignore_permissions=True):
			rows.append((r.posting_date, "Petty Cash", flt(r.amount), "Petty Cash Voucher", "Site Petty Cash Voucher", r.name))
	for r in frappe.get_all("Stock Entry", filters={"project": project, "docstatus": 1,
			"stock_entry_type": "Material Issue", "posting_date": ["between", [f, t]]},
			fields=["name", "posting_date", "total_outgoing_value"], ignore_permissions=True):
		rows.append((r.posting_date, "Material", flt(r.total_outgoing_value), "Material Issue", "Stock Entry", r.name))
	if has("Site Expense Entry"):
		cat_of = {"Equipment": "Equipment", "Subcontract": "Subcontracting", "Transport": "Transport"}
		for r in frappe.get_all("Site Expense Entry", filters={"project": project,
				"entry_date": ["between", [f, t]]}, fields=["name", "entry_date", "category", "amount"],
				ignore_permissions=True):
			rows.append((r.entry_date, cat_of.get(r.category, "Other"), flt(r.amount), "Site Expense",
				"Site Expense Entry", r.name))
	for d, amount, src in _labour_rows(project, f, t):
		rows.append((d, "Employee", amount, src, None, None))
	return rows


def _labour_rows(project, f, t):
	"""Labour cost per day: attendance (one man-day per labour per date) x daily wage; falls back to
	progress-entry hours / 8 x wage when there is no attendance for the project."""
	if not frappe.db.exists("DocType", "Labour"):
		return []
	wages = {r.name: flt(r.daily_wage) for r in frappe.get_all("Labour", fields=["name", "daily_wage"],
		ignore_permissions=True)} if frappe.get_meta("Labour").has_field("daily_wage") else {}
	out = []
	if frappe.db.exists("DocType", "Labour Attendance Log"):
		days = frappe.db.sql("""select distinct labour, log_date from `tabLabour Attendance Log`
			where project = %s and log_date between %s and %s""", (project, f, t), as_dict=True)
		if days:
			per_day = {}
			for r in days:
				per_day[str(r.log_date)] = per_day.get(str(r.log_date), 0.0) + wages.get(r.labour, 0.0)
			return [(d, a, "Attendance x wage") for d, a in per_day.items()]
	if frappe.db.exists("DocType", "Site Progress Entry"):
		for r in frappe.db.sql("""select spe.entry_date, spl.labour, spl.hours
				from `tabSite Progress Labour` spl join `tabSite Progress Entry` spe on spe.name = spl.parent
				where spe.project = %s and spe.entry_date between %s and %s""", (project, f, t), as_dict=True):
			out.append((r.entry_date, flt(r.hours) / 8.0 * wages.get(r.labour, 0.0), "Progress hours x wage"))
	return out


def project_boq_budget(project):
	"""{category: budget} from the project's BOQ (BOQ_MAP categories) + total."""
	out = {c: 0.0 for c in BOQ_MAP}
	out["total"] = 0.0
	if not frappe.db.exists("DocType", "Project BOQ"):
		return out
	names = frappe.get_all("Project BOQ", filters={"project": project}, pluck="name", ignore_permissions=True)
	if not names:
		return out
	for it in frappe.get_all("Project BOQ Item", filters={"parent": ["in", names]},
			fields=["amount"] + [f for fs in BOQ_MAP.values() for f in fs], ignore_permissions=True):
		for cat, fields in BOQ_MAP.items():
			out[cat] += sum(flt(it.get(f)) for f in fields)
		out["total"] += flt(it.amount)
	return out


def project_costs(project, from_date, to_date, info=None, pc_jes=None, companies=None):
	"""-> list of (date, category, amount, source, ref_doctype, ref_name): site records + GL entries
	tagged with the project (except stock entries and petty-cash journal entries, counted above)."""
	rows = _site_rows(project, from_date, to_date)
	companies = companies or resolve_companies(frappe.db.get_value("Project", project, "company"))
	info = info or accounts_info(companies)
	pc_jes = pc_jes if pc_jes is not None else petty_cash_jes(companies)
	for g in gl_rows(companies, from_date, to_date, ("Expense",), project=project):
		if g.voucher_type == "Stock Entry" or g.voucher_no in pc_jes:
			continue
		a = info.get(g.account)
		if not a:
			continue
		rows.append((g.posting_date, a.category or "Other", flt(g.debit) - flt(g.credit), "Books (" + g.voucher_type + ")",
			g.voucher_type, g.voucher_no))
	return rows


def project_sales(project, from_date, to_date, companies=None):
	companies = companies or resolve_companies(frappe.db.get_value("Project", project, "company"))
	return [(g.posting_date, flt(g.credit) - flt(g.debit), g.voucher_type, g.voucher_no)
		for g in gl_rows(companies, from_date, to_date, ("Income",), project=project)]


def project_list(companies, active_only=False):
	filters = {"company": ["in", companies]}
	if active_only:
		filters["status"] = ["not in", ["Cancelled"]]
	return frappe.get_all("Project", filters=filters, fields=["name", "project_name", "status", "company"],
		order_by="modified desc", ignore_permissions=True)


# ---------------------------------------------------------------- cash and bank

def cash_accounts(companies):
	return [a.name for a in frappe.get_all("Account", filters={"company": ["in", companies],
		"account_type": ["in", ["Cash", "Bank"]], "is_group": 0}, fields=["name"], ignore_permissions=True)]


def cash_movements(companies, from_date, to_date):
	"""Rows on cash/bank accounts, leaving out contra vouchers (money moved between own cash/bank
	accounts). -> (opening_balance, rows[date, in, out, party_type])"""
	accs = cash_accounts(companies)
	if not accs:
		return 0.0, []
	opening = flt(frappe.db.sql("""select sum(debit - credit) from `tabGL Entry`
		where account in %s and is_cancelled = 0 and posting_date < %s""", (tuple(accs), from_date))[0][0])
	rows = frappe.db.sql("""
		select g.posting_date, g.debit, g.credit, g.voucher_no,
			(select max(o.party_type) from `tabGL Entry` o where o.voucher_no = g.voucher_no
				and o.voucher_type = g.voucher_type and o.is_cancelled = 0 and ifnull(o.party_type, '') != '') as party_type
		from `tabGL Entry` g
		where g.account in %(accs)s and g.is_cancelled = 0 and g.posting_date between %(f)s and %(t)s
			and exists (select 1 from `tabGL Entry` x where x.voucher_no = g.voucher_no
				and x.voucher_type = g.voucher_type and x.is_cancelled = 0 and x.account not in %(accs)s)""",
		{"accs": tuple(accs), "f": from_date, "t": to_date}, as_dict=True)
	return opening, rows


def cash_balance_now(companies, to_date):
	accs = cash_accounts(companies)
	if not accs:
		return []
	return frappe.db.sql("""select g.account, a.account_type, sum(g.debit - g.credit) as balance
		from `tabGL Entry` g join `tabAccount` a on a.name = g.account
		where g.account in %s and g.is_cancelled = 0 and g.posting_date <= %s
		group by g.account, a.account_type order by balance desc""", (tuple(accs), to_date), as_dict=True)


def outstanding(doctype, companies, to_date, project=None):
	party = "customer" if doctype == "Sales Invoice" else "supplier"
	cond = "company in %(c)s and docstatus = 1 and outstanding_amount > 0.5"
	if project:
		cond += " and project = %(p)s"
	args = {"c": companies, "t": to_date, "p": project}
	total, overdue = frappe.db.sql(f"""select sum(outstanding_amount),
		sum(case when due_date < %(t)s then outstanding_amount else 0 end)
		from `tab{doctype}` where {cond}""", args)[0]
	top = frappe.db.sql(f"""select {party} as party, sum(outstanding_amount) as amount,
		sum(case when due_date < %(t)s then outstanding_amount else 0 end) as overdue
		from `tab{doctype}` where {cond} group by {party} order by amount desc limit 8""", args, as_dict=True)
	drafts = frappe.db.sql(f"""select count(*), sum(grand_total) from `tab{doctype}`
		where company in %(c)s and docstatus = 0""" + (" and project = %(p)s" if project else ""), args)[0]
	return {"total": flt(total), "overdue": flt(overdue), "top": top,
		"drafts": cint(drafts[0]), "drafts_amount": flt(drafts[1])}


def site_cash(companies, to_date, project=None):
	"""Cash given to sites vs spent from site cash, per project (all time to date)."""
	if not frappe.db.exists("DocType", "Site Cash Issue"):
		return []
	projects = [project] if project else [p.name for p in project_list(companies)]
	if not projects:
		return []
	issued = dict(frappe.db.sql("""select project, sum(amount) from `tabSite Cash Issue`
		where project in %s and issue_date <= %s group by project""", (tuple(projects), to_date)))
	spent = dict(frappe.db.sql("""select project, sum(amount) from `tabSite Expense Entry`
		where project in %s and payment_source = 'Site Cash' and entry_date <= %s group by project""",
		(tuple(projects), to_date))) if frappe.db.exists("DocType", "Site Expense Entry") else {}
	out = []
	for p in projects:
		i, s = flt(issued.get(p)), flt(spent.get(p))
		if i or s:
			out.append({"project": p, "issued": i, "spent": s, "balance": i - s})
	return sorted(out, key=lambda r: -r["balance"])


# ---------------------------------------------------------------- dashboard

@frappe.whitelist()
def get_dashboard(period=None, from_date=None, to_date=None, company=None, project=None, granularity=None):
	check_access()
	return compute(period, from_date, to_date, company, project, granularity)


def compute(period=None, from_date=None, to_date=None, company=None, project=None, granularity=None, light=False):
	"""Everything the dashboard shows. light=True skips budget / receivables / site cash (reports)."""
	f, t = resolve_period(period, from_date, to_date)
	companies = resolve_companies(project and frappe.db.get_value("Project", project, "company") or company)
	gran, periods = make_periods(f, t, granularity if granularity != "Auto" else None)
	find = bucket_of(periods)
	n = len(periods)
	info = accounts_info(companies)
	pc_jes = petty_cash_jes(companies)

	sales_p = [0.0] * n
	exp_p = {c: [0.0] * n for c in CATEGORIES}
	exp_src = {}

	if project:
		for d, amt, _vt, _vn in project_sales(project, f, t, companies):
			i = find(d)
			if i is not None:
				sales_p[i] += amt
		for d, cat, amt, src, _dt, _dn in project_costs(project, f, t, info, pc_jes, companies):
			i = find(d)
			if i is not None:
				exp_p[cat][i] += amt
				exp_src[src] = exp_src.get(src, 0.0) + amt
	else:
		for g in gl_rows(companies, f, t):
			i = find(g.posting_date)
			a = info.get(g.account)
			if i is None or not a:
				continue
			if a.root_type == "Income":
				sales_p[i] += flt(g.credit) - flt(g.debit)
			else:
				cat = "Petty Cash" if g.voucher_no in pc_jes else (a.category or "Other")
				exp_p[cat][i] += flt(g.debit) - flt(g.credit)
				exp_src[g.voucher_type] = exp_src.get(g.voucher_type, 0.0) + flt(g.debit) - flt(g.credit)

	split = {c: round(sum(v), 2) for c, v in exp_p.items()}
	exp_total_p = [sum(exp_p[c][i] for c in CATEGORIES) for i in range(n)]
	sales = sum(sales_p)
	expenses = sum(split.values())
	profit_p = [sales_p[i] - exp_total_p[i] for i in range(n)]

	# cash in / out (books)
	opening, moves = cash_movements(companies, f, t)
	cin, cout = [0.0] * n, [0.0] * n
	split_p = {k: [0.0] * n for k in ("From customers", "Other receipts", "To suppliers", "To employees",
		"Other payments")}
	for m in moves:
		i = find(m.posting_date)
		if i is None:
			continue
		cin[i] += flt(m.debit)
		cout[i] += flt(m.credit)
		if flt(m.debit):
			split_p["From customers" if m.party_type == "Customer" else "Other receipts"][i] += flt(m.debit)
		if flt(m.credit):
			key = {"Supplier": "To suppliers", "Employee": "To employees"}.get(m.party_type, "Other payments")
			split_p[key][i] += flt(m.credit)
	in_split = {k: sum(split_p[k]) for k in ("From customers", "Other receipts")}
	out_split = {k: sum(split_p[k]) for k in ("To suppliers", "To employees", "Other payments")}
	closing_p, run = [], opening
	for i in range(n):
		run += cin[i] - cout[i]
		closing_p.append(run)

	base = {
		"from_date": str(f), "to_date": str(t), "granularity": gran, "periods": periods,
		"labels": [p["label"] for p in periods], "companies_in_scope": companies,
		"sales_series": sales_p, "expense_series": exp_total_p, "profit_series": profit_p,
		"expense_split": split, "expense_by_period": exp_p, "expense_sources": exp_src,
		"cash": {"in": cin, "out": cout, "closing": closing_p, "opening": opening, "in_split": in_split,
			"out_split": out_split, "split_by_period": split_p},
	}
	if light:
		return base

	# budget vs actual
	if project:
		budget = budget_vs_actual_project(project, t, companies, info, pc_jes)
	else:
		budget = budget_vs_actual_all(companies, t, info, pc_jes)

	recv = outstanding("Sales Invoice", companies, t, project)
	pay = outstanding("Purchase Invoice", companies, t, project)
	balances = cash_balance_now(companies, t)

	return {
		"period": period or "This Financial Year", "from_date": str(f), "to_date": str(t),
		"granularity": gran, "labels": [p["label"] for p in periods], "periods": periods,
		"company": company or "__all__", "companies": company_list(), "project": project,
		"projects": [{"name": p.name, "label": p.project_name or p.name, "company": p.company}
			for p in project_list(resolve_companies(company))],
		"source": "Site records + project-tagged books" if project else "Books (ERPNext + Tally)",
		"kpi": {
			"sales": sales, "expenses": expenses, "profit": sales - expenses,
			"margin": round((sales - expenses) / sales * 100, 1) if sales else None,
			"cash_in": sum(cin), "cash_out": sum(cout), "net_cash": sum(cin) - sum(cout),
			"opening_cash": opening, "closing_cash": opening + sum(cin) - sum(cout),
			"receivable": recv["total"], "receivable_overdue": recv["overdue"],
			"payable": pay["total"], "payable_overdue": pay["overdue"],
			"draft_sales": recv["drafts"], "draft_sales_amount": recv["drafts_amount"],
			"draft_purchases": pay["drafts"], "draft_purchases_amount": pay["drafts_amount"],
		},
		"sales_series": sales_p, "expense_series": exp_total_p, "profit_series": profit_p,
		"expense_split": split, "expense_by_period": exp_p, "expense_sources": exp_src,
		"cash": dict(base["cash"], balances=balances),
		"budget": budget,
		"top_receivable": recv["top"], "top_payable": pay["top"],
		"site_cash": site_cash(companies, t, project),
		"categories": CATEGORIES,
	}


def budget_vs_actual_project(project, to_date, companies, info, pc_jes):
	"""BOQ budget vs actual from the project's start to `to_date` (budgets are for the whole job)."""
	budget = project_boq_budget(project)
	f = getdate("2000-01-01")  # everything booked to the project so far
	actual = {c: 0.0 for c in BOQ_MAP}
	for _d, cat, amt, _s, _dt, _dn in project_costs(project, f, to_date, info, pc_jes, companies):
		actual[BUDGET_GROUP.get(cat, cat)] += amt
	rows = []
	for cat in BOQ_MAP:
		b, a = budget[cat], actual[cat]
		rows.append({"category": cat + (" (incl. petty cash, transport)" if cat == "Other" else ""), "budget": b,
			"actual": a, "variance": b - a, "used_pct": round(a / b * 100, 1) if b else None})
	sales_to_date = sum(x[1] for x in project_sales(project, f, to_date, companies))
	return {"mode": "project", "rows": rows, "budget_total": budget["total"],
		"actual_total": sum(actual.values()), "sales_to_date": sales_to_date}


def budget_vs_actual_all(companies, to_date, info, pc_jes, limit=15):
	"""One row per project that has a BOQ: budget vs actual to date."""
	rows = []
	if not frappe.db.exists("DocType", "Project BOQ"):
		return {"mode": "all", "rows": rows}
	with_boq = set(frappe.get_all("Project BOQ", pluck="project", ignore_permissions=True))
	for p in project_list(companies):
		if p.name not in with_boq:
			continue
		r = budget_vs_actual_project(p.name, to_date, companies, info, pc_jes)
		rows.append({"project": p.name, "label": p.project_name or p.name, "status": p.status,
			"budget": r["budget_total"], "actual": r["actual_total"], "variance": r["budget_total"] - r["actual_total"],
			"used_pct": round(r["actual_total"] / r["budget_total"] * 100, 1) if r["budget_total"] else None,
			"sales": r["sales_to_date"]})
	rows.sort(key=lambda r: -(r["used_pct"] or 0))
	return {"mode": "all", "rows": rows[:limit], "more": max(len(rows) - limit, 0)}
