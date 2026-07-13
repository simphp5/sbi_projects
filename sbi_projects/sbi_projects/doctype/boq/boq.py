# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class BOQ(Document):
	def validate(self):
		self.calculate_totals()
		self.validate_items()
		self.set_status()

	def calculate_totals(self):
		total_amount = 0.0
		total_qty = 0.0
		for row in self.items:
			row.amount = flt(row.qty) * flt(row.rate)
			total_amount += flt(row.amount)
			total_qty += flt(row.qty)
		self.total_amount = total_amount
		self.total_qty = total_qty

	def validate_items(self):
		if not self.items:
			frappe.throw(_("BOQ must have at least one item"))
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row {0}: Qty must be greater than zero").format(row.idx))

	def set_status(self):
		if self.docstatus == 0:
			self.status = "Draft"
		elif self.docstatus == 1:
			if self.status not in ("Approved", "Revised"):
				self.status = "Submitted"
		elif self.docstatus == 2:
			self.status = "Cancelled"

	def on_submit(self):
		self.link_items_to_tasks()
		self.update_project_estimate()

	def on_cancel(self):
		self.update_project_estimate(cancel=True)

	# ----------------------------------------------------------
	def link_items_to_tasks(self):
		"""Map each BOQ item to the project Task carrying the same stage."""
		if not self.project:
			return

		tasks = frappe.get_all(
			"Task",
			filters={"project": self.project},
			fields=["name", "sbi_stage"],
		)
		stage_to_task = {t.sbi_stage: t.name for t in tasks if t.get("sbi_stage")}

		for row in self.items:
			if row.stage and stage_to_task.get(row.stage):
				row.db_set("task", stage_to_task[row.stage], update_modified=False)

	def update_project_estimate(self, cancel=False):
		"""Push BOQ total into Project.estimated_costing."""
		if not self.project:
			return
		amount = 0 if cancel else flt(self.total_amount)
		frappe.db.set_value("Project", self.project, "estimated_costing", amount)
		frappe.db.set_value("Project", self.project, "sbi_boq", None if cancel else self.name)


@frappe.whitelist()
def get_template_items(boq_template):
	"""Return BOQ Template items so the client can populate the items grid."""
	template = frappe.get_doc("BOQ Template", boq_template)
	rows = []
	for t in template.items:
		rows.append({
			"item_code": t.item_code,
			"description": t.description,
			"uom": t.uom,
			"qty": flt(t.default_qty),
			"rate": flt(t.default_rate),
			"amount": flt(t.default_qty) * flt(t.default_rate),
			"stage": t.stage,
			"category": t.category,
		})
	return rows


@frappe.whitelist()
def make_revision(boq):
	"""Create a new draft BOQ as a revision of a submitted one."""
	source = frappe.get_doc("BOQ", boq)
	new = frappe.copy_doc(source)
	new.revision_no = int(flt(source.revision_no)) + 1
	new.status = "Draft"
	new.amended_from = source.name
	new.insert()
	frappe.db.set_value("BOQ", source.name, "status", "Revised")
	return new.name
