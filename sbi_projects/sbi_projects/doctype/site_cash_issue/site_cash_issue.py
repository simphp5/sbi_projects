import frappe
from frappe.model.document import Document


class SiteCashIssue(Document):
    def validate(self):
        if not self.issued_by:
            self.issued_by = frappe.session.user
