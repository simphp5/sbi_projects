# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate, nowdate


class SbiProjectTemplate(Document):
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
				_("Total weight must be 100%. Currently {0}%").format(
					flt(self.total_weight, 2)
				)
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


# ------------------------------------------------------------------
# Hooked on Project.after_insert
# ------------------------------------------------------------------
def create_tasks_from_template(doc, method=None):
	"""When a Project is created with sbi_project_template set, build its Tasks."""
	template_name = doc.get("sbi_project_template")
	if not template_name:
		return

	# don't double-create
	if frappe.db.exists("Task", {"project": doc.name}):
		return

	template = frappe.get_doc("SBI Project Template", template_name)
	start = getdate(doc.expected_start_date or nowdate())

	stage_to_task = {}
	cursor = start

	for row in template.stages:
		exp_start = cursor
		duration = int(row.duration_days or 1)
		exp_end = add_days(exp_start, max(duration - 1, 0))

		task = frappe.new_doc("Task")
		task.subject = row.stage
		task.project = doc.name
		task.status = "Open"
		task.task_weight = flt(row.weight)
		task.exp_start_date = exp_start
		task.exp_end_date = exp_end
		task.is_milestone = row.is_milestone or 0
		task.description = row.stage_description or ""
		task.sbi_stage = row.stage

		if row.depends_on_stage and stage_to_task.get(row.depends_on_stage):
			task.append("depends_on", {"task": stage_to_task[row.depends_on_stage]})

		task.insert(ignore_permissions=True)
		stage_to_task[row.stage] = task.name

		cursor = add_days(exp_end, 1)

	frappe.msgprint(
		_("{0} tasks created from template <b>{1}</b>").format(
			len(template.stages), template_name
		),
		alert=True,
	)
