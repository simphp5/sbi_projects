# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Phase 3A seed: a sample Rate Card and a few Work Items.

Rates are indicative starting values taken from the SBI proposal sheet
(Index 01). SBI maintains the weighted-average rates going forward -- this is
only a starting point so the BOQ has something to compute against.

Idempotent; called from after_install.
"""

import frappe

RATE_CARD = "SBI Standard 2026-27"

# (resource_type, resource, uom, rate, wastage_percent)
RESOURCES = [
	("Material", "Cement", "Bag", 350, 2),
	("Material", "M.Sand", "CUM", 2119, 5),
	("Material", "P.Sand", "CUM", 69, 5),
	("Material", "20mm Aggregate", "CUM", 55, 5),
	("Material", "Reinforcement", "Kg", 63, 2),
	("Material", "Binding Wire", "Kg", 85, 0),
	("Material", "Bricks", "Nos", 11, 5),
	("Material", "GSB", "CUM", 1766, 5),
	("Material", "RMC M25", "CUM", 5460, 2),
	("Material", "Water", "KL", 1000, 0),
	("Manpower", "Mason", "Day", 1200, 0),
	("Manpower", "M/C (Male Coolie)", "Day", 1200, 0),
	("Manpower", "F/C (Female Coolie)", "Day", 900, 0),
	("Equipment", "JCB", "Hour", 1000, 0),
	("Equipment", "Crane", "Hour", 300, 0),
	("Equipment", "Vibrator", "Hour", 65, 0),
	("Equipment", "Surveyor", "Day", 5000, 0),
	("Subcontract", "Erection", "Kg", 10, 0),
	("Subcontract", "Sheet Laying", "Sqm", 11, 0),
]

# (code, name, category, uom, [(res_type, resource, coefficient, uom), ...])
WORK_ITEMS = [
	("CIV-PCC-M10", "PCC M10 (1:5:10)", "Civil", "CUM", [
		("Material", "Cement", 2.5, "Bag"),
		("Material", "M.Sand", 0.5, "CUM"),
		("Material", "20mm Aggregate", 0.9, "CUM"),
		("Manpower", "Mason", 0.3, "Day"),
		("Manpower", "F/C (Female Coolie)", 0.5, "Day"),
	]),
	("CIV-RCC-M25", "RCC M25", "Civil", "CUM", [
		("Material", "RMC M25", 1.0, "CUM"),
		("Material", "Reinforcement", 100, "Kg"),
		("Material", "Binding Wire", 1.0, "Kg"),
		("Manpower", "Mason", 0.5, "Day"),
		("Manpower", "F/C (Female Coolie)", 1.0, "Day"),
		("Equipment", "Vibrator", 2.0, "Hour"),
	]),
	("CIV-BW-CM", "Brick Work in CM 1:5", "Civil", "CUM", [
		("Material", "Bricks", 500, "Nos"),
		("Material", "Cement", 1.8, "Bag"),
		("Material", "M.Sand", 0.25, "CUM"),
		("Manpower", "Mason", 1.0, "Day"),
		("Manpower", "F/C (Female Coolie)", 1.0, "Day"),
	]),
	("CIV-EARTH", "Earth Work Excavation", "Civil", "CUM", [
		("Equipment", "JCB", 0.15, "Hour"),
		("Manpower", "F/C (Female Coolie)", 0.1, "Day"),
	]),
	("PEB-ERECT", "PEB Erection", "Structural", "Kg", [
		("Subcontract", "Erection", 1.0, "Kg"),
		("Equipment", "Crane", 0.02, "Hour"),
	]),
	("SHT-ROOF-LAY", "Roof Sheet Laying", "Sheeting", "Sqm", [
		("Subcontract", "Sheet Laying", 1.0, "Sqm"),
	]),
]


def setup_boq_masters():
	if not frappe.db.exists("DocType", "Rate Card"):
		return {}
	created = {
		"rate_card": _seed_rate_card(),
		"work_items": _seed_work_items(),
	}
	frappe.db.commit()
	return created


def _seed_rate_card():
	if frappe.db.exists("Rate Card", RATE_CARD):
		return 0
	doc = frappe.get_doc({
		"doctype": "Rate Card",
		"rate_card_name": RATE_CARD,
		"is_default": 1,
		"valuation_method": "Moving Average",
		"remarks": "Starter card. SBI maintains weighted-average rates.",
	})
	for rt, res, uom, rate, waste in RESOURCES:
		doc.append("items", {
			"resource_type": rt, "resource": res, "uom": uom,
			"rate": rate, "wastage_percent": waste,
		})
	doc.insert(ignore_permissions=True)
	return 1


def _seed_work_items():
	count = 0
	for code, name, cat, uom, resources in WORK_ITEMS:
		if frappe.db.exists("Work Item", code):
			continue
		doc = frappe.get_doc({
			"doctype": "Work Item",
			"work_item_code": code,
			"work_item_name": name,
			"category": cat,
			"uom": uom,
			"is_active": 1,
		})
		for rt, res, coef, ruom in resources:
			doc.append("resources", {
				"resource_type": rt, "resource": res,
				"coefficient": coef, "uom": ruom,
			})
		doc.insert(ignore_permissions=True)
		count += 1
	return count
