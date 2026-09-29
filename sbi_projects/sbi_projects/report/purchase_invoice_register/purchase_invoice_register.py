# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Purchase Invoice Register.

The columns SBI actually wants to see, in the order they want them, with the
one thing a list view cannot give: days overdue, worked out live against
today's date rather than stored on the record and going stale overnight.

Days overdue counts from the due date and only for invoices still carrying an
outstanding amount, so a bill that was paid late does not keep accruing.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Invoice No"), "fieldname": "name", "fieldtype": "Link",
		 "options": "Purchase Invoice", "width": 150},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link",
		 "options": "Project", "width": 150},
		{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link",
		 "options": "Warehouse", "width": 140},
		{"label": _("Supplier"), "fieldname": "supplier_name", "fieldtype": "Data",
		 "width": 200},
		{"label": _("Invoice Date"), "fieldname": "posting_date", "fieldtype": "Date",
		 "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date",
		 "width": 100},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int",
		 "width": 110},
		{"label": _("Tax (GST)"), "fieldname": "total_taxes_and_charges",
		 "fieldtype": "Currency", "width": 120},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency",
		 "width": 130},
		{"label": _("Outstanding"), "fieldname": "outstanding_amount",
		 "fieldtype": "Currency", "width": 130},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Supplier Bill No"), "fieldname": "bill_no", "fieldtype": "Data",
		 "width": 150},
	]


def get_data(filters):
	conditions = ["pi.docstatus < 2"]
	values = {}

	if filters.get("company"):
		conditions.append("pi.company = %(company)s")
		values["company"] = filters.company
	if filters.get("supplier"):
		conditions.append("pi.supplier = %(supplier)s")
		values["supplier"] = filters.supplier
	if filters.get("from_date"):
		conditions.append("pi.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("pi.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date
	if filters.get("status"):
		conditions.append("pi.status = %(status)s")
		values["status"] = filters.status
	if filters.get("only_outstanding"):
		conditions.append("pi.outstanding_amount > 0")

	meta = frappe.get_meta("Purchase Invoice")
	project_col = "pi.project" if meta.has_field("project") else "null"
	warehouse_col = "pi.set_warehouse" if meta.has_field("set_warehouse") else "null"

	if filters.get("project") and meta.has_field("project"):
		# an invoice can be tagged at the top or line by line, so look in both
		conditions.append(
			"""(pi.project = %(project)s or exists (
				select 1 from `tabPurchase Invoice Item` pii
				where pii.parent = pi.name and pii.project = %(project)s))"""
		)
		values["project"] = filters.project

	rows = frappe.db.sql(
		f"""
		select
			pi.name,
			{project_col} as project,
			{warehouse_col} as warehouse,
			pi.supplier_name,
			pi.posting_date,
			pi.due_date,
			pi.total_taxes_and_charges,
			pi.grand_total,
			pi.outstanding_amount,
			pi.status,
			pi.bill_no
		from `tabPurchase Invoice` pi
		where {' and '.join(conditions)}
		order by pi.posting_date desc, pi.name desc
		""",
		values,
		as_dict=True,
	)

	now = getdate(today())
	for r in rows:
		# only an unpaid bill is overdue; a late-but-settled one stops counting
		if r.due_date and flt(r.outstanding_amount) > 0:
			days = (now - getdate(r.due_date)).days
			r["days_overdue"] = days if days > 0 else 0
		else:
			r["days_overdue"] = 0

	return rows
