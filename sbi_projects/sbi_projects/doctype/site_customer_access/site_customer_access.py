import frappe
from frappe.model.document import Document


class SiteCustomerAccess(Document):
    def validate(self):
        if not self.token:
            self.token = frappe.generate_hash(length=32)
