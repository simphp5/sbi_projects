# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document


class SiteAssignment(Document):
	def validate(self):
		if self.to_date and self.from_date and self.to_date < self.from_date:
			frappe.throw(_("To Date cannot be before From Date."))
		self.status = "Closed" if self.to_date else "Open"

	def after_insert(self):
		self.close_previous_assignment()
		self.sync_to_project()

	def on_update(self):
		self.sync_to_project()

	def close_previous_assignment(self):
		"""Any other Open row for the same site+role gets closed."""
		previous = frappe.get_all(
			"Site Assignment",
			filters={
				"project": self.project,
				"role": self.role,
				"status": "Open",
				"name": ["!=", self.name],
			},
			pluck="name",
		)
		for name in previous:
			frappe.db.set_value("Site Assignment", name, {
				"to_date": frappe.utils.add_days(self.from_date, -1),
				"status": "Closed",
			}, update_modified=False)

	def sync_to_project(self):
		"""Push the current holder onto the Project custom field."""
		if self.status != "Open":
			return
		field = "sbi_site_incharge" if self.role == "Site In-charge" else "sbi_storekeeper"
		if not frappe.db.has_column("Project", field):
			return
		frappe.db.set_value("Project", self.project, field, self.employee, update_modified=False)
