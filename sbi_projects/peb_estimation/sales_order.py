# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Sales Order side of the estimation chain.

Two small jobs, both idempotent so re-submitting or re-running a migrate
never duplicates anything:

  1. Carry the Estimation BOQ link forward from the Quotation, because
     ERPNext's own mapper does not know about our custom field.
  2. Keep the BOQ, the Sales Order and the Project pointing at each other,
     which is what lets the Sales Order act as the cockpit for the job.

Project creation is left entirely to the existing "Project (with Stages)"
action -- nothing here creates or overwrites a project.
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


def link_boq(doc, method=None):
	"""on_submit: cross-link the BOQ with this order, and with its project if one exists.

	The project itself is deliberately NOT created here -- sbi_projects already
	has a "Project (with Stages)" action on the Sales Order that builds a far
	richer project than a bare insert would. This just makes sure the BOQ, the
	order and whatever project is attached all point at each other.
	"""
	boq = doc.get("sbi_estimation_boq")
	if not boq or not frappe.db.exists("Estimation Sheet BOQ", boq):
		return

	try:
		frappe.db.set_value("Estimation Sheet BOQ", boq, "sales_order", doc.name)

		project = doc.get("project")
		if project:
			frappe.db.set_value("Estimation Sheet BOQ", boq, "project", project)
			if _has_boq_field("Project"):
				if not frappe.db.get_value("Project", project, "sbi_estimation_boq"):
					frappe.db.set_value("Project", project, "sbi_estimation_boq", boq)
	except Exception:
		# linking is a convenience; it must never block a submit
		frappe.log_error(frappe.get_traceback(), "PEB: link BOQ to sales order")


def inherit_boq_on_project(doc, method=None):
	"""Project after_insert: pick up the BOQ from the order that spawned it.

	Fires whichever way the project was made -- the existing "Project (with
	Stages)" button, the standard ERPNext action, or by hand with a Sales Order
	set -- so the chain closes without touching that code.
	"""
	if not _has_boq_field("Project"):
		return
	if doc.get("sbi_estimation_boq"):
		return

	so = doc.get("sales_order")
	if not so:
		return

	try:
		boq = frappe.db.get_value("Sales Order", so, "sbi_estimation_boq")
		if not boq:
			return
		doc.db_set("sbi_estimation_boq", boq)
		frappe.db.set_value("Estimation Sheet BOQ", boq, "project", doc.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "PEB: inherit BOQ on project")


def _has_boq_field(doctype):
	return bool(
		frappe.db.exists(
			"Custom Field", {"dt": doctype, "fieldname": "sbi_estimation_boq"}
		)
	)
