import frappe
from frappe.model.document import Document


class ProgressParameter(Document):
	def validate(self):
		self.parameter_name = (self.parameter_name or "").strip()