# Copyright (c) 2026, Velmaska and contributors
"""Lead stage + activity logic for civil / PEB sales."""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate


def validate_lead(doc, method=None):
	sync_stage_from_activities(doc)
	validate_lost_reason(doc)
	set_next_followup(doc)


# ------------------------------------------------------------------
def sync_stage_from_activities(doc):
	"""If an activity type is mapped to a stage, move the lead forward.

	Only ever moves the lead FORWARD (higher sequence), never backwards,
	so logging an old activity late doesn't regress the pipeline.
	"""
	if not doc.get("sbi_activities"):
		return

	seq = {
		d.name: (d.sequence or 0)
		for d in frappe.get_all("Lead Stage", fields=["name", "sequence"])
	}
	current = seq.get(doc.get("sbi_lead_stage"), -1)

	target_stage = None
	target_seq = current

	for row in doc.sbi_activities:
		if not row.activity_type:
			continue
		moves_to = frappe.db.get_value(
			"Lead Activity Type", row.activity_type, "moves_to_stage"
		)
		if moves_to and seq.get(moves_to, -1) > target_seq:
			target_seq = seq[moves_to]
			target_stage = moves_to

	if target_stage:
		doc.sbi_lead_stage = target_stage


# ------------------------------------------------------------------
def validate_lost_reason(doc):
	stage = doc.get("sbi_lead_stage")
	if not stage:
		return

	flags = frappe.db.get_value(
		"Lead Stage", stage, ["is_lost", "is_converted"], as_dict=True
	)
	if not flags:
		return

	if flags.is_lost and not doc.get("sbi_lost_reason"):
		frappe.throw(
			_("Lost Reason is required when the lead stage is <b>{0}</b>").format(stage)
		)

	# keep the native status roughly in step so Opportunity conversion still works
	if flags.is_converted:
		doc.status = "Converted"
	elif flags.is_lost and doc.status not in ("Do Not Contact",):
		doc.status = "Do Not Contact"


# ------------------------------------------------------------------
def set_next_followup(doc):
	"""Pull the earliest future next-action date off the activity log."""
	dates = [
		getdate(r.next_action_date)
		for r in (doc.get("sbi_activities") or [])
		if r.next_action_date
	]
	future = [d for d in dates if d >= getdate(nowdate())]
	if future:
		doc.sbi_next_followup = min(future)
	elif dates:
		doc.sbi_next_followup = max(dates)


# ==================================================================
# Whitelisted helper - quick-log an activity from the Lead form
# ==================================================================
@frappe.whitelist()
def log_activity(lead, activity_type, activity_date=None, remarks=None,
                 next_action=None, next_action_date=None):
	doc = frappe.get_doc("Lead", lead)
	doc.append("sbi_activities", {
		"activity_type": activity_type,
		"activity_date": activity_date or nowdate(),
		"done_by": frappe.session.user,
		"remarks": remarks,
		"next_action": next_action,
		"next_action_date": next_action_date,
	})
	doc.save()
	return doc.get("sbi_lead_stage")
