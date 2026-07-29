import frappe
from frappe.model.document import Document


class SiteProgressEntry(Document):
    def validate(self):
        if not self.entered_by:
            self.entered_by = frappe.session.user
