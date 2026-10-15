# Copyright (c) 2026, Velmaska and contributors
import frappe
from frappe.model.document import Document


class CashFlowSettings(Document):
	def validate(self):
		seen = set()
		for row in self.account_map:
			if row.account in seen:
				frappe.throw("Account " + row.account + " is listed twice in the Account Map.")
			seen.add(row.account)


@frappe.whitelist()
def check_expense_ledgers(company=None):
	"""Every expense ledger with the category Cash Flow will use for it."""
	from sbi_projects.cashflow.engine import accounts_info, check_access, resolve_companies

	check_access()
	info = accounts_info(resolve_companies(company))
	rows = [{"account": k, "category": v.category} for k, v in info.items()
		if v.root_type == "Expense" and not frappe.db.get_value("Account", k, "is_group")]
	return sorted(rows, key=lambda r: (r["category"], r["account"]))
