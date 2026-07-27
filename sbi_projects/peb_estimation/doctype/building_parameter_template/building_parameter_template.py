# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BuildingParameterTemplate(Document):

	def validate(self):
		self.validate_duplicate_parameters()
		self.set_counts()

	def validate_duplicate_parameters(self):
		seen = {}
		for row in self.parameters:
			if row.parameter in seen:
				frappe.throw(
					_("Parameter {0} is repeated at rows {1} and {2}.").format(
						frappe.bold(row.parameter), seen[row.parameter], row.idx
					)
				)
			seen[row.parameter] = row.idx

	def set_counts(self):
		self.total_parameters = len(self.parameters)
		self.mandatory_parameters = len(
			[r for r in self.parameters if r.is_mandatory]
		)

	def on_update(self):
		"""Only one default template per work type."""
		if self.is_default and self.status == "Approved":
			frappe.db.set_value(
				"Building Parameter Template",
				{
					"work_type": self.work_type,
					"is_default": 1,
					"name": ["!=", self.name],
				},
				"is_default",
				0,
				update_modified=False,
			)

	@frappe.whitelist()
	def load_parameters(self, replace=False):
		"""Pull every active parameter applicable to this template's work type."""
		if not self.work_type:
			frappe.throw(_("Set Work Type before loading parameters."))

		from sbi_projects.peb_estimation.doctype.building_parameter.building_parameter import (
			get_parameters_for_work_type,
		)

		rows = get_parameters_for_work_type(self.work_type)
		if not rows:
			frappe.throw(
				_("No active parameters found for Work Type {0}.").format(
					frappe.bold(self.work_type)
				)
			)

		if replace:
			self.parameters = []

		existing = {r.parameter for r in self.parameters}
		added = 0
		for row in rows:
			if row.parameter in existing:
				continue
			self.append(
				"parameters",
				{
					"parameter": row.parameter,
					"is_mandatory": row.is_mandatory,
				},
			)
			added += 1

		return added
