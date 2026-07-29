# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Sales Order side of the estimation chain.

Two small jobs, both idempotent so re-submitting or re-running a migrate
never duplicates anything:

  1. Carry the Estimation BOQ link forward from the Quotation, because
     ERPNext's own mapper does not know about our custom field.
  2. On submit, make sure a Project exists for the order and that the BOQ,
     the Sales Order and the Project all point at each other -- that mutual
     linking is what lets the Sales Order act as the cockpit for the job.

Nothing here overrides the existing "Create Project" button; if a project is
already linked, both steps stand down.
"""

import frappe
from frappe import _


def carry_boq_from_quotation(doc, method=None):
	"""validate: pull the BOQ link across from the source quotation."""
	if not _has_boq_field("Sales Order"):
		return
	if doc.get("sbi_estimation_boq"):
		return

	quotations = {
		item.prevdoc_docname
		for item in (doc.items or [])
		if item.get("prevdoc_docname")
	}
	for quo in quotations:
		boq = frappe.db.get_value("Quotation", quo, "sbi_estimation_boq")
		if boq:
			doc.sbi_estimation_boq = boq
			return


def ensure_project(doc, method=None):
	"""on_submit: create and cross-link the Project for this order."""
	if not _has_boq_field("Sales Order"):
		return

	try:
		project = doc.get("project")

		if not project:
			project = _create_project(doc)
			if not project:
				return
			doc.db_set("project", project)

		# cross-link so any of the three opens the other two
		boq = doc.get("sbi_estimation_boq")
		if boq and _has_boq_field("Project"):
			if not frappe.db.get_value("Project", project, "sbi_estimation_boq"):
				frappe.db.set_value("Project", project, "sbi_estimation_boq", boq)

		if boq and frappe.db.exists("Estimation Sheet BOQ", boq):
			frappe.db.set_value("Estimation Sheet BOQ", boq, {
				"sales_order": doc.name,
				"project": project,
			})

	except Exception:
		# a failure here must never block the order from being submitted
		frappe.log_error(frappe.get_traceback(), "PEB: link project to sales order")


def _create_project(doc):
	"""Create a Project mirroring the order. Returns its name, or None."""
	title = (doc.get("project_name") or doc.get("customer_name") or doc.name)[:140]

	existing = frappe.db.get_value("Project", {"sales_order": doc.name}, "name")
	if existing:
		return existing

	project = frappe.new_doc("Project")
	project.project_name = title
	project.customer = doc.customer
	project.company = doc.company
	project.status = "Open"
	project.expected_start_date = doc.get("transaction_date")
	project.expected_end_date = doc.get("delivery_date")

	if project.meta.has_field("sales_order"):
		project.sales_order = doc.name
	if _has_boq_field("Project") and doc.get("sbi_estimation_boq"):
		project.sbi_estimation_boq = doc.get("sbi_estimation_boq")

	project.insert(ignore_permissions=True)
	return project.name


def _has_boq_field(doctype):
	return bool(
		frappe.db.exists(
			"Custom Field", {"dt": doctype, "fieldname": "sbi_estimation_boq"}
		)
	)
