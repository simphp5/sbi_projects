import frappe
from frappe.model.document import Document


class SiteCostCategory(Document):
	def validate(self):
		self.category_name = (self.category_name or "").strip()