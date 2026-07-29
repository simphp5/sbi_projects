import frappe
from frappe.model.document import Document
from frappe.utils import flt


class SiteExpenseEntry(Document):
    def validate(self):
        if flt(self.qty) and flt(self.rate) and not flt(self.amount):
            self.amount = flt(self.qty) * flt(self.rate)
        if not self.entered_by:
            self.entered_by = frappe.session.user
