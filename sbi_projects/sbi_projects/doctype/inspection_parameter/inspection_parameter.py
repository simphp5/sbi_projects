import frappe
from frappe.model.document import Document


class InspectionParameter(Document):
	def validate(self):
		self.parameter_name = (self.parameter_name or "").strip()