"""Daily Work Log -> general ledger.

A Daily Work Log is captured by site staff and approved by the owner.  On
approval three things happen:

  1. material rows      -> Stock Entry (Material Issue) from the site warehouse
  2. labour rows        -> Journal Entry, Dr labour expense / Cr wages payable
  3. other cost rows    -> Journal Entry, Dr category expense / Cr payable

Material is issued as stock rather than posted as a plain expense so that
valuation stays correct and the cost is not counted twice: the purchase already
hit the ledger when the material was received.

Wages are accrued, not paid, here.  The payable is settled later by a wage
payment, which keeps site data entry away from cash accounting.

Everything is idempotent -- a log that has already posted is skipped.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

APPROVED_STATE = "Approved"


# ----------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------

def maybe_post_to_gl(doc, method=None):
	"""doc_events hook on Daily Work Log."""
	if doc.get("workflow_state") != APPROVED_STATE:
		return
	if doc.get("sbi_journal_entry") or doc.get("sbi_stock_entry"):
		return  # already posted

	post_work_log(doc)


@frappe.whitelist()
def post_work_log_by_name(name):
	"""Manual re-post, for repairing a log that failed the first time."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc("Daily Work Log", name)
	post_work_log(doc)
	return {"journal_entry": doc.get("sbi_journal_entry"),
	        "stock_entry": doc.get("sbi_stock_entry")}


def post_work_log(doc):
	company = get_company(doc)
	cost_center = get_cost_center(doc)

	material_cost = post_material_issue(doc, company, cost_center)
	labour_lines, labour_cost = build_labour_lines(doc, cost_center)
	other_lines, other_cost = build_other_cost_lines(doc, cost_center)

	je_name = None
	if labour_lines or other_lines:
		je_name = post_journal_entry(doc, company, labour_lines + other_lines)

	doc.db_set("sbi_total_material_cost", material_cost, update_modified=False)
	doc.db_set("sbi_total_labour_cost", labour_cost, update_modified=False)
	doc.db_set("sbi_total_other_cost", other_cost, update_modified=False)
	doc.db_set("sbi_total_cost", flt(material_cost) + flt(labour_cost) + flt(other_cost),
	           update_modified=False)
	if je_name:
		doc.db_set("sbi_journal_entry", je_name, update_modified=False)

	update_task_actuals(doc.task)


# ----------------------------------------------------------------------
# 1. material -> stock entry
# ----------------------------------------------------------------------

def post_material_issue(doc, company, cost_center):
	rows = doc.get("sbi_materials") or []
	rows = [r for r in rows if r.get("item_code") and flt(r.get("qty")) > 0]
	if not rows:
		return 0

	warehouse = get_site_warehouse(doc.project)
	if not warehouse:
		frappe.throw(_("Project {0} has no site warehouse, so material cannot be issued.")
		             .format(doc.project))

	se = frappe.new_doc("Stock Entry")
	se.stock_entry_type = "Material Issue"
	se.company = company
	se.posting_date = getdate(doc.log_date)
	se.project = doc.project
	se.remarks = _("Auto-issued from Daily Work Log {0}").format(doc.name)

	for row in rows:
		se.append("items", {
			"item_code": row.item_code,
			"qty": flt(row.qty),
			"uom": row.get("uom"),
			"s_warehouse": row.get("warehouse") or warehouse,
			"cost_center": cost_center,
			"project": doc.project,
		})

	se.insert(ignore_permissions=True)
	se.submit()

	doc.db_set("sbi_stock_entry", se.name, update_modified=False)

	# write the valuation back so the site sees what the material actually cost
	total = 0
	for row, item in zip(rows, se.items):
		row.db_set("rate", flt(item.basic_rate), update_modified=False)
		row.db_set("amount", flt(item.amount), update_modified=False)
		total += flt(item.amount)

	return total


# ----------------------------------------------------------------------
# 2. labour -> accrual lines
# ----------------------------------------------------------------------

def build_labour_lines(doc, cost_center):
	"""One expense line per wage type, one matching payable line.

	The labour child table is read defensively: an explicit amount on the row
	wins, otherwise the rate is taken from the Labour master and multiplied by
	the days or hours recorded.
	"""
	rows = doc.get("labour_details") or []
	if not rows:
		return [], 0

	by_wage_type = {}
	for row in rows:
		labour = row.get("labour")
		if not labour:
			continue

		amount = flt(row.get("amount"))
		if not amount:
			amount = compute_labour_amount(row, labour)
		if not amount:
			continue

		wage_type = frappe.db.get_value("Labour", labour, "sbi_wage_type")
		by_wage_type.setdefault(wage_type, 0)
		by_wage_type[wage_type] += amount

	lines = []
	total = 0
	for wage_type, amount in by_wage_type.items():
		expense, payable = get_wage_accounts(wage_type)
		lines.append({"account": expense, "debit_in_account_currency": amount,
		              "cost_center": cost_center, "project": doc.project})
		lines.append({"account": payable, "credit_in_account_currency": amount,
		              "cost_center": cost_center, "project": doc.project})
		total += amount

	return lines, total


def compute_labour_amount(row, labour):
	rate = flt(frappe.db.get_value("Labour", labour, "sbi_wage_rate"))
	if not rate:
		rate = flt(frappe.db.get_value("Labour", labour, "daily_wage"))
	if not rate:
		return 0

	hours = flt(row.get("hours"))
	if hours:
		return rate * (hours / 8.0)

	days = flt(row.get("days")) or 1
	return rate * days


# ----------------------------------------------------------------------
# 3. other costs -> accrual lines
# ----------------------------------------------------------------------

def build_other_cost_lines(doc, cost_center):
	rows = doc.get("sbi_costs") or []
	rows = [r for r in rows if flt(r.get("amount")) > 0]
	if not rows:
		return [], 0

	by_category = {}
	for row in rows:
		by_category.setdefault(row.site_cost_category, 0)
		by_category[row.site_cost_category] += flt(row.amount)

	lines = []
	total = 0
	for category, amount in by_category.items():
		expense = frappe.db.get_value("Site Cost Category", category, "expense_account")
		if not expense:
			frappe.throw(_("Cost Category {0} has no expense account set.").format(category))
		payable = get_default_payable(doc)
		lines.append({"account": expense, "debit_in_account_currency": amount,
		              "cost_center": cost_center, "project": doc.project})
		lines.append({"account": payable, "credit_in_account_currency": amount,
		              "cost_center": cost_center, "project": doc.project})
		total += amount

	return lines, total


# ----------------------------------------------------------------------
# journal entry
# ----------------------------------------------------------------------

def post_journal_entry(doc, company, lines):
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = company
	je.posting_date = getdate(doc.log_date)
	je.user_remark = _("Daily Work Log {0} -- {1}").format(doc.name, doc.project)

	for line in lines:
		je.append("accounts", line)

	je.insert(ignore_permissions=True)
	je.submit()
	return je.name


# ----------------------------------------------------------------------
# roll-up
# ----------------------------------------------------------------------

def update_task_actuals(task):
	"""Sum approved work logs into the task's budget rows, by category."""
	if not task or not frappe.db.exists("Task", task):
		return

	doc = frappe.get_doc("Task", task)
	rows = doc.get("sbi_budget_details") or []
	if not rows:
		return

	actuals = get_actuals_by_category(task)

	total_budget = 0
	total_actual = 0
	for row in rows:
		actual = flt(actuals.get(row.site_cost_category))
		row.db_set("actual_amount", actual, update_modified=False)
		row.db_set("variance", flt(row.budget_amount) - actual, update_modified=False)
		total_budget += flt(row.budget_amount)
		total_actual += actual

	frappe.db.set_value("Task", task, {
		"sbi_total_budget": total_budget,
		"sbi_total_actual": total_actual,
	}, update_modified=False)


def get_actuals_by_category(task):
	"""Approved spend on a task, keyed by Site Cost Category."""
	actuals = {}

	other = frappe.db.sql("""
		select c.site_cost_category as category, sum(c.amount) as amount
		from `tabDaily Work Log Cost` c
		inner join `tabDaily Work Log` l on l.name = c.parent
		where l.task = %s and l.workflow_state = %s
		group by c.site_cost_category
	""", (task, APPROVED_STATE), as_dict=True)
	for r in other:
		actuals[r.category] = flt(actuals.get(r.category)) + flt(r.amount)

	material_category = frappe.db.get_value(
		"Site Cost Category", {"category_name": "Material"}, "name")
	if material_category:
		total = frappe.db.sql("""
			select sum(m.amount) from `tabDaily Work Log Material` m
			inner join `tabDaily Work Log` l on l.name = m.parent
			where l.task = %s and l.workflow_state = %s
		""", (task, APPROVED_STATE))
		if total and total[0][0]:
			actuals[material_category] = flt(actuals.get(material_category)) + flt(total[0][0])

	labour_category = frappe.db.get_value(
		"Site Cost Category", {"is_labour_cost": 1}, "name")
	if labour_category:
		total = frappe.db.sql("""
			select sum(sbi_total_labour_cost) from `tabDaily Work Log`
			where task = %s and workflow_state = %s
		""", (task, APPROVED_STATE))
		if total and total[0][0]:
			actuals[labour_category] = flt(actuals.get(labour_category)) + flt(total[0][0])

	return actuals


# ----------------------------------------------------------------------
# lookups
# ----------------------------------------------------------------------

def get_company(doc):
	company = doc.get("company")
	if not company and doc.project:
		company = frappe.db.get_value("Project", doc.project, "company")
	company = company or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Cannot determine the company for this work log."))
	return company


def get_cost_center(doc):
	cc = None
	if doc.project:
		cc = frappe.db.get_value("Project", doc.project, "cost_center")
	if not cc:
		frappe.throw(_("Project {0} has no cost center, so cost cannot be posted.")
		             .format(doc.project))
	return cc


def get_site_warehouse(project):
	if not project:
		return None
	meta = frappe.get_meta("Project")
	for name in ("sbi_site_warehouse", "custom_site_warehouse"):
		if meta.has_field(name):
			wh = frappe.db.get_value("Project", project, name)
			if wh:
				return wh
	return None


def get_wage_accounts(wage_type):
	expense = payable = None
	if wage_type:
		expense, payable = frappe.db.get_value(
			"Wage Type", wage_type, ["expense_account", "payable_account"]) or (None, None)

	if not expense:
		frappe.throw(_("Wage Type {0} has no expense account set. "
		               "Set it before approving labour costs.").format(wage_type or "(none)"))
	if not payable:
		frappe.throw(_("Wage Type {0} has no payable account set.").format(wage_type))
	return expense, payable


def get_default_payable(doc):
	company = get_company(doc)
	account = frappe.get_cached_value("Company", company, "default_payable_account")
	if not account:
		frappe.throw(_("Company {0} has no default payable account.").format(company))
	return account