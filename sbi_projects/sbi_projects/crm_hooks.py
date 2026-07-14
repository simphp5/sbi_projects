# Copyright (c) 2026, Velmaska and contributors
"""Carry enquiry details from Lead -> Opportunity -> Quotation.

The Enquiry Type / Enquiry Parameter master DocTypes were built directly on the
site (not in this app), so every touch here is guarded by an existence check.
If they are absent the hooks quietly do nothing.
"""

import frappe
from frappe.utils import flt

ENQUIRY_TYPE_DT = "Enquiry Type"
LEAD_PARAM_DT = "Lead Enquiry Parameter"


def _enquiry_available():
	return frappe.db.exists("DocType", ENQUIRY_TYPE_DT) and frappe.db.exists(
		"DocType", LEAD_PARAM_DT
	)


def _copy_params(source, target):
	"""Copy the enquiry parameter child rows across."""
	rows = source.get("enquiry_parameters") or source.get("lead_enquiry_parameter") or []
	if not rows:
		return
	target.set("sbi_enquiry_parameters", [])
	for r in rows:
		target.append("sbi_enquiry_parameters", {
			"parameter": r.get("parameter"),
			"value": flt(r.get("value")),
			"uom": r.get("uom"),
		})


# ------------------------------------------------------------------
# Opportunity.validate
# ------------------------------------------------------------------
def pull_enquiry_to_opportunity(doc, method=None):
	if not _enquiry_available():
		return
	if doc.opportunity_from != "Lead" or not doc.party_name:
		return
	if doc.get("sbi_enquiry_parameters"):
		return  # already populated, don't overwrite user edits

	lead = frappe.get_doc("Lead", doc.party_name)

	if not doc.get("sbi_type_of_enquiry"):
		doc.sbi_type_of_enquiry = lead.get("type_of_enquiry")
	if not doc.get("sbi_lead_stage"):
		doc.sbi_lead_stage = lead.get("sbi_lead_stage")

	_copy_params(lead, doc)


# ------------------------------------------------------------------
# Quotation.validate
# ------------------------------------------------------------------
def pull_enquiry_to_quotation(doc, method=None):
	if not _enquiry_available():
		return
	if doc.get("sbi_enquiry_parameters"):
		return

	source = None
	if doc.get("opportunity"):
		source = frappe.get_doc("Opportunity", doc.opportunity)
	elif doc.quotation_to == "Lead" and doc.party_name:
		source = frappe.get_doc("Lead", doc.party_name)

	if not source:
		return

	if not doc.get("sbi_type_of_enquiry"):
		doc.sbi_type_of_enquiry = source.get("sbi_type_of_enquiry") or source.get(
			"type_of_enquiry"
		)

	if source.doctype == "Opportunity":
		rows = source.get("sbi_enquiry_parameters") or []
		for r in rows:
			doc.append("sbi_enquiry_parameters", {
				"parameter": r.parameter,
				"value": flt(r.value),
				"uom": r.uom,
			})
	else:
		_copy_params(source, doc)
