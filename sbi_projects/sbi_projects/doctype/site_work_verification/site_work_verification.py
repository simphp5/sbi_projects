import frappe
from frappe.model.document import Document


class SiteWorkVerification(Document):
    def validate(self):
        if not self.entered_by:
            self.entered_by = frappe.session.user
        if not self.is_new():
            was_signed = frappe.db.get_value(
                "Site Work Verification", self.name, "signed")
            if was_signed and "System Manager" not in frappe.get_roles():
                frappe.throw(
                    "This verification is signed by the customer "
                    "and cannot be modified.")

    def on_trash(self):
        if self.signed and "System Manager" not in frappe.get_roles():
            frappe.throw("Signed verification cannot be deleted.")
