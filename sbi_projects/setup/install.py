# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	from sbi_projects.setup.crm_setup import setup_crm
	from sbi_projects.setup.branding import setup_branding

	# Runs on every migrate (after_migrate hook). Each step is isolated so a
	# failure in one seed is logged to Error Log but never aborts the whole
	# migrate -- otherwise the entire deploy (including static files like the
	# login page) gets rolled back.
	steps = (
		add_custom_fields,
		seed_project_stages,
		seed_lead_stages,
		seed_lead_activity_types,
		setup_crm,
		setup_branding,
	)
	for step in steps:
		try:
			step()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), f"sbi_projects setup: {step.__name__}")


# ------------------------------------------------------------------
def add_custom_fields():
	custom_fields = {
		"Project": [
			# --- Site Management section ---
			{
				"fieldname": "sbi_site_sb",
				"label": "Site Management",
				"fieldtype": "Section Break",
				"insert_after": "project_type",
			},
			{
				"fieldname": "sbi_project_template",
				"label": "Project Template",
				"fieldtype": "Link",
				"options": "SBI Project Template",
				"insert_after": "sbi_site_sb",
				"description": "Select a template to auto-create stage tasks on save",
			},
			{
				"fieldname": "sbi_current_stage",
				"label": "Current Stage",
				"fieldtype": "Link",
				"options": "Project Stage",
				"insert_after": "sbi_project_template",
				"in_list_view": 1,
			},
			{
				"fieldname": "sbi_site_incharge",
				"label": "Site In-charge",
				"fieldtype": "Link",
				"options": "Employee",
				"insert_after": "sbi_current_stage",
			},
			{
				"fieldname": "sbi_site_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_site_incharge",
			},
			{
				"fieldname": "sbi_site_address",
				"label": "Site Address",
				"fieldtype": "Small Text",
				"insert_after": "sbi_site_cb",
			},
			{
				"fieldname": "sbi_site_warehouse",
				"label": "Site Warehouse",
				"fieldtype": "Link",
				"options": "Warehouse",
				"insert_after": "sbi_site_address",
			},
			# --- PEB / commercial ---
			{
				"fieldname": "sbi_peb_sb",
				"label": "PEB Details",
				"fieldtype": "Section Break",
				"insert_after": "sbi_site_warehouse",
				"collapsible": 1,
			},
			{
				"fieldname": "sbi_boq",
				"label": "BOQ",
				"fieldtype": "Link",
				"options": "BOQ",
				"insert_after": "sbi_peb_sb",
				"read_only": 1,
			},
			{
				"fieldname": "sbi_contract_value",
				"label": "Contract Value",
				"fieldtype": "Currency",
				"insert_after": "sbi_boq",
			},
			{
				"fieldname": "sbi_peb_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_contract_value",
			},
			{
				"fieldname": "sbi_built_up_area",
				"label": "Built-up Area (sq.ft)",
				"fieldtype": "Float",
				"insert_after": "sbi_peb_cb",
			},
			{
				"fieldname": "sbi_tonnage",
				"label": "Steel Tonnage (MT)",
				"fieldtype": "Float",
				"insert_after": "sbi_built_up_area",
			},
			# --- GPS geofence (for site attendance module) ---
			{
				"fieldname": "sbi_gps_sb",
				"label": "Site Geo-fence",
				"fieldtype": "Section Break",
				"insert_after": "sbi_tonnage",
				"collapsible": 1,
			},
			{
				"fieldname": "sbi_site_latitude",
				"label": "Latitude",
				"fieldtype": "Data",
				"insert_after": "sbi_gps_sb",
			},
			{
				"fieldname": "sbi_gps_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_site_latitude",
			},
			{
				"fieldname": "sbi_site_longitude",
				"label": "Longitude",
				"fieldtype": "Data",
				"insert_after": "sbi_gps_cb",
			},
			{
				"fieldname": "sbi_geofence_radius",
				"label": "Geo-fence Radius (m)",
				"fieldtype": "Int",
				"default": "200",
				"insert_after": "sbi_site_longitude",
			},
		],
		"Task": [
			{
				"fieldname": "sbi_stage",
				"label": "Stage",
				"fieldtype": "Link",
				"options": "Project Stage",
				"insert_after": "project",
				"in_standard_filter": 1,
			},
			{
				"fieldname": "sbi_budget_sb",
				"label": "Stage Budget",
				"fieldtype": "Section Break",
				"insert_after": "task_weight",
				"collapsible": 1,
			},
			{
				"fieldname": "sbi_payment_term",
				"label": "Payment Term",
				"fieldtype": "Link",
				"options": "Payment Term",
				"insert_after": "sbi_budget_sb",
				"read_only": 1,
			},
			{
				"fieldname": "sbi_invoice_portion",
				"label": "Invoice Portion (%)",
				"fieldtype": "Percent",
				"insert_after": "sbi_payment_term",
				"read_only": 1,
			},
			{
				"fieldname": "sbi_budget_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_invoice_portion",
			},
			{
				"fieldname": "sbi_stage_budget",
				"label": "Stage Budget",
				"fieldtype": "Currency",
				"insert_after": "sbi_budget_cb",
				"description": "From the Sales Order payment schedule",
			},
		],
		"Payment Term": [
			{
				"fieldname": "sbi_stage",
				"label": "Project Stage",
				"fieldtype": "Link",
				"options": "Project Stage",
				"insert_after": "invoice_portion",
				"description": "Map this payment milestone to a project stage",
			},
		],
		"Payment Schedule": [
			{
				"fieldname": "sbi_stage",
				"label": "Project Stage",
				"fieldtype": "Link",
				"options": "Project Stage",
				"insert_after": "payment_term",
				"fetch_from": "payment_term.sbi_stage",
				"fetch_if_empty": 1,
				"in_list_view": 1,
			},
		],
		"Lead": [
			{
				"fieldname": "sbi_pipeline_sb",
				"label": "Sales Pipeline",
				"fieldtype": "Section Break",
				"insert_after": "status",
			},
			{
				"fieldname": "sbi_lead_stage",
				"label": "Lead Stage",
				"fieldtype": "Link",
				"options": "Lead Stage",
				"insert_after": "sbi_pipeline_sb",
				"in_list_view": 1,
				"in_standard_filter": 1,
				"bold": 1,
			},
			{
				"fieldname": "sbi_next_followup",
				"label": "Next Follow-up",
				"fieldtype": "Date",
				"insert_after": "sbi_lead_stage",
				"read_only": 1,
				"in_list_view": 1,
				"description": "Earliest pending next-action date from the activity log",
			},
			{
				"fieldname": "sbi_pipeline_cb",
				"fieldtype": "Column Break",
				"insert_after": "sbi_next_followup",
			},
			{
				"fieldname": "sbi_lost_reason",
				"label": "Lost Reason",
				"fieldtype": "Small Text",
				"insert_after": "sbi_pipeline_cb",
				"depends_on": "eval:doc.sbi_lead_stage",
			},
			{
				"fieldname": "sbi_activity_sb",
				"label": "Activity Log",
				"fieldtype": "Section Break",
				"insert_after": "sbi_lost_reason",
			},
			{
				"fieldname": "sbi_activities",
				"label": "Activities",
				"fieldtype": "Table",
				"options": "Lead Activity",
				"insert_after": "sbi_activity_sb",
			},
		],
	}
	create_custom_fields(custom_fields, ignore_validate=True)


# ------------------------------------------------------------------
DEFAULT_STAGES = [
	("Design & Drawing Approval", "DSG", 1, 5, 10),
	("Foundation / Civil Work", "FDN", 2, 15, 25),
	("Fabrication", "FAB", 3, 30, 30),
	("Material Dispatch", "DSP", 4, 10, 7),
	("Erection", "ERC", 5, 25, 25),
	("Sheeting & Cladding", "SHT", 6, 10, 12),
	("Finishing", "FIN", 7, 3, 7),
	("Handover", "HND", 8, 2, 3),
	# extra stages users can pick from
	("Site Mobilization", "MOB", 0, 0, 3),
	("Painting", "PNT", 0, 0, 5),
	("Testing & Commissioning", "TST", 0, 0, 5),
	("Project Management & Consultancy", "PMC", 0, 0, 0),
]


def seed_project_stages():
	for name, code, seq, weight, duration in DEFAULT_STAGES:
		if frappe.db.exists("Project Stage", name):
			continue
		frappe.get_doc({
			"doctype": "Project Stage",
			"stage_name": name,
			"stage_code": code,
			"sequence": seq,
			"default_weight": weight,
			"default_duration": duration,
			"is_active": 1,
		}).insert(ignore_permissions=True)


# ------------------------------------------------------------------
# Lead pipeline seeds  (civil / PEB sales cycle)
# ------------------------------------------------------------------
LEAD_STAGES = [
	# (name, seq, colour, expected_days, is_converted, is_lost)
	("New Enquiry",             1,  "Grey",   2,  0, 0),
	("Contacted",               2,  "Blue",   3,  0, 0),
	("First Meeting",           3,  "Blue",   7,  0, 0),
	("Site Visit",              4,  "Orange", 7,  0, 0),
	("Site Survey",             5,  "Orange", 10, 0, 0),
	("Requirement Finalised",   6,  "Purple", 7,  0, 0),
	("Drawing / Design Shared", 7,  "Purple", 10, 0, 0),
	("Budget Estimate Shared",  8,  "Yellow", 7,  0, 0),
	("Quotation Submitted",     9,  "Yellow", 15, 0, 0),
	("Negotiation",             10, "Orange", 15, 0, 0),
	("Won",                     11, "Green",  0,  1, 0),
	("Lost",                    12, "Red",    0,  0, 1),
	("On Hold",                 13, "Grey",   0,  0, 0),
]


def seed_lead_stages():
	for name, seq, colour, days, won, lost in LEAD_STAGES:
		if frappe.db.exists("Lead Stage", name):
			continue
		frappe.get_doc({
			"doctype": "Lead Stage",
			"stage_name": name,
			"sequence": seq,
			"indicator_color": colour,
			"expected_days": days,
			"is_converted": won,
			"is_lost": lost,
			"is_active": 1,
		}).insert(ignore_permissions=True)


LEAD_ACTIVITY_TYPES = [
	# (name, seq, moves_to_stage)
	("Enquiry Received",        1,  "New Enquiry"),
	("Call / Email",            2,  "Contacted"),
	("First Meeting",           3,  "First Meeting"),
	("Site Visit",              4,  "Site Visit"),
	("Site Survey / Measurement", 5, "Site Survey"),
	("Soil Test Report Received", 6, None),
	("Requirement Confirmed",   7,  "Requirement Finalised"),
	("GA Drawing Shared",       8,  "Drawing / Design Shared"),
	("Budget Estimate Sent",    9,  "Budget Estimate Shared"),
	("Quotation Sent",          10, "Quotation Submitted"),
	("Negotiation Meeting",     11, "Negotiation"),
	("Revised Quotation Sent",  12, "Negotiation"),
	("Work Order Received",     13, "Won"),
	("Client Declined",         14, "Lost"),
	("Follow-up",               15, None),
]


def seed_lead_activity_types():
	for name, seq, moves_to in LEAD_ACTIVITY_TYPES:
		if frappe.db.exists("Lead Activity Type", name):
			continue
		frappe.get_doc({
			"doctype": "Lead Activity Type",
			"activity_name": name,
			"sequence": seq,
			"moves_to_stage": moves_to,
			"is_active": 1,
		}).insert(ignore_permissions=True)
