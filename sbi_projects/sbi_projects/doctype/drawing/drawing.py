# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document


class Drawing(Document):
	def validate(self):
		self.mark_superseded()

	def mark_superseded(self):
		"""Flag the drawing this revision replaces."""
		if self.supersedes and self.supersedes != self.name:
			frappe.db.set_value("Drawing", self.supersedes, "status", "Superseded")
