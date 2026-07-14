# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class SBIProjectTemplate(Document):
	def validate(self):
		self.calculate_total_weight()
		self.validate_weight()
		self.validate_dependencies()

	def calculate_total_weight(self):
		self.total_weight = sum(flt(r.weight) for r in self.stages)

	def validate_weight(self):
		if not self.stages:
			frappe.throw(_("Add at least one stage"))
		if abs(flt(self.total_weight) - 100.0) > 0.01:
			frappe.throw(
				_("Total weight must be 100%. Currently {0}%").format(flt(self.total_weight, 2))
			)

	def validate_dependencies(self):
		seen = []
		for row in self.stages:
			if row.depends_on_stage:
				if row.depends_on_stage == row.stage:
					frappe.throw(_("Row {0}: A stage cannot depend on itself").format(row.idx))
				if row.depends_on_stage not in seen:
					frappe.throw(
						_("Row {0}: '{1}' must appear before '{2}' in the table").format(
							row.idx, row.depends_on_stage, row.stage
						)
					)
			seen.append(row.stage)
