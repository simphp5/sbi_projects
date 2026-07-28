# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Starter Quantity Rules: turn client parameters into BOQ line quantities.

These are worked examples using the Work Items already seeded by
boq_masters.py. SBI is expected to edit the formulas and add more rules --
they are deliberately simple and readable rather than exhaustive.

Idempotent; existing rules are never overwritten, so SBI's edits survive.
"""

import frappe

# (rule_name, work_item, stage, priority, condition, qty_formula, scope_parameter, description)
RULES = [
	(
		"Earth Work - Foundation",
		"CIV-EARTH", "Stage 1", 10,
		"",
		"params.BUILDING_LENGTH * params.BUILDING_WIDTH * 0.15",
		None,
		"Excavation for foundations",
	),
	(
		"PCC Bedding",
		"CIV-PCC-M10", "Stage 1", 20,
		"",
		"params.BUILDING_LENGTH * params.BUILDING_WIDTH * 0.03",
		None,
		"PCC bedding below footings",
	),
	(
		"RCC Foundation",
		"CIV-RCC-M25", "Stage 1", 30,
		"",
		"params.BUILDING_LENGTH * params.BUILDING_WIDTH * 0.05",
		None,
		"RCC footings and pedestals",
	),
	(
		"RCC Mezzanine Slab",
		"CIV-RCC-M25", "Stage 2", 40,
		'params.MEZZANINE_REQD == "Yes"',
		"params.MEZZANINE_AREA * 0.15",
		None,
		"RCC slab for mezzanine floor",
	),
	(
		"Brick Work - Plinth",
		"CIV-BW-CM", "Stage 2", 50,
		"params.AAC_BLOCK_HEIGHT > 0",
		"(params.BUILDING_LENGTH + params.BUILDING_WIDTH) * 2 * params.AAC_BLOCK_HEIGHT * 0.23",
		None,
		"Masonry up to plinth level",
	),
	(
		"PEB Erection",
		"PEB-ERECT", "Stage 3", 60,
		"",
		"params.BUILDING_LENGTH * params.BUILDING_WIDTH * 12",
		"SCOPE_ERECTION",
		"Erection of steel structure (approx 12 kg/sqm)",
	),
	(
		"Roof Sheet Laying",
		"SHT-ROOF-LAY", "Stage 4", 70,
		"",
		"params.BUILDING_LENGTH * params.BUILDING_WIDTH * 1.05",
		"SCOPE_ROOFING",
		"Roof sheeting including 5% lap",
	),
]


def setup_quantity_rules():
	if not frappe.db.exists("DocType", "Quantity Rule"):
		return 0

	created = 0
	for (name, work_item, stage, priority, condition, formula,
	     scope, description) in RULES:

		if frappe.db.exists("Quantity Rule", name):
			continue
		if not frappe.db.exists("Work Item", work_item):
			# work item seed hasn't run or was renamed -- skip quietly
			continue
		if scope and not frappe.db.exists("Building Parameter", scope):
			scope = None

		frappe.get_doc({
			"doctype": "Quantity Rule",
			"rule_name": name,
			"work_item": work_item,
			"stage": stage,
			"priority": priority,
			"condition": condition or None,
			"qty_formula": formula,
			"scope_parameter": scope,
			"line_description": description,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return created
