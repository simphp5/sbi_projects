# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BuildingParameter(Document):

	def validate(self):
		self.validate_options()
		self.validate_work_type()

	def validate_options(self):
		"""Select fieldtype must carry newline separated options."""
		if self.fieldtype == "Select" and not (self.options or "").strip():
			frappe.throw(
				_("Options is mandatory when Input Type is Select. "
				  "Enter one value per line.")
			)
		if self.fieldtype != "Select" and self.options:
			self.options = None

	def validate_work_type(self):
		"""At least one applicable work type, and no duplicates."""
		if not self.applicable_work_type:
			frappe.throw(_("Select at least one Applicable Work Type."))

		seen = set()
		for row in self.applicable_work_type:
			if row.work_type in seen:
				frappe.throw(
					_("Work Type {0} is repeated at row {1}.").format(
						frappe.bold(row.work_type), row.idx
					)
				)
			seen.add(row.work_type)


@frappe.whitelist()
def get_parameters_for_work_type(work_type, bucket=None):
	"""Return active parameters applicable to a work type, in questionnaire order.

	Used by Building Parameter Template (Load Parameters button) and later by
	Building Enquiry to render the client questionnaire.
	"""
	filters = {"parenttype": "Building Parameter", "work_type": work_type}
	names = frappe.get_all(
		"Building Parameter Work Type", filters=filters, pluck="parent"
	)
	if not names:
		return []

	param_filters = {"name": ["in", names], "is_active": 1}
	if bucket:
		param_filters["bucket"] = bucket

	return frappe.get_all(
		"Building Parameter",
		filters=param_filters,
		fields=[
			"name as parameter",
			"parameter_code",
			"parameter_name",
			"section",
			"section_no",
			"bucket",
			"fieldtype",
			"options",
			"uom",
			"default_value",
			"is_mandatory",
			"display_order",
		],
		order_by="section_no asc, display_order asc, parameter_code asc",
	)
