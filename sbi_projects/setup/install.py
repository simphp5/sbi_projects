# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
	add_custom_fields()
	seed_project_stages()
	frappe.db.commit()


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
