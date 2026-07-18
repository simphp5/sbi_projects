# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document

from frappe.utils import flt


class SitePettyCashVoucher(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero."))
		self.set_cost_center()

	def set_cost_center(self):
		if self.cost_center or not self.project:
			return
		if frappe.db.has_column("Project", "cost_center"):
			self.cost_center = frappe.db.get_value("Project", self.project, "cost_center")

	def on_submit(self):
		self.make_journal_entry()

	def on_cancel(self):
		if self.journal_entry:
			try:
				je = frappe.get_doc("Journal Entry", self.journal_entry)
				if je.docstatus == 1:
					je.cancel()
			except Exception:
				frappe.log_error(frappe.get_traceback(), "Petty cash JE cancel failed")

	def make_journal_entry(self):
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Cash Entry"
		je.company = self.company
		je.posting_date = self.posting_date
		je.user_remark = f"Site petty cash {self.name} - {self.paid_to}"
		je.append("accounts", {
			"account": self.expense_account,
			"debit_in_account_currency": flt(self.amount),
			"cost_center": self.cost_center,
			"project": self.project,
		})
		je.append("accounts", {
			"account": self.credit_account,
			"credit_in_account_currency": flt(self.amount),
			"cost_center": self.cost_center,
			"project": self.project,
		})
		je.insert(ignore_permissions=True)
		je.submit()
		self.db_set("journal_entry", je.name)
