# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Scope of Works master.

The tick matrix on SBI's proposal -- what the company does and what the client
is expected to provide. It is the same list job after job, with the odd item
moved between columns or a remark reworded, so it belongs in a master rather
than being retyped into every quotation.

Seeded from the September 2026 proposal. SBI can add, reword or reorder freely;
existing rows are never overwritten, so edits survive a migrate.
"""

import frappe

# (section, order, description, by, remarks)
SCOPE_ITEMS = [
	("Client Scope", 10, "Soil Investigation", "Client", "To be provided by Client"),
	("Client Scope", 20, "Topographical Survey", "Client", "Existing survey to be provided"),
	("Client Scope", 30, "Site Development", "Client", "Clearing, levelling & access roads"),
	("Client Scope", 40, "Statutory Approvals (Govt.)", "Client", "Client"),
	("Client Scope", 50, "Power During Construction", "Client", "Free issue at site"),
	("Client Scope", 60, "Water During Construction", "Client", "Free issue at site"),

	("PEB - Civil Works", 70, "Marking of building", "SBI", "Isolated foundation"),
	("PEB - Civil Works", 80, "Excavation for foundation", "SBI", "Ordinary soil only 2 m depth"),
	("PEB - Civil Works", 90, "PCC for foundation", "SBI", "100 mm thick M7.5 Grade"),
	("PEB - Civil Works", 100, "RCC foundation", "SBI", "M20 Grade Concrete"),
	("PEB - Civil Works", 110, "Reinforcement Steel", "SBI", "Fe500 Grade"),
	("PEB - Civil Works", 120, "Formwork / Shuttering", "SBI", ""),
	("PEB - Civil Works", 130, "Foundation Bolt Fixing", "SBI", ""),
	("PEB - Civil Works", 140, "Earth Filling & Compaction", "SBI", "Up to FFL"),
	("PEB - Civil Works", 150, "Brickwork for Basement", "SBI", "Up to 1200 mm height"),
	("PEB - Civil Works", 160, "Basement filling NGL to FFL", "SBI", "Filling with Hill Earth 4'"),
	("PEB - Civil Works", 170, "Superstructure Brickwork", "SBI", "Up to 3000 mm height"),
	("PEB - Civil Works", 180, "Plastering", "SBI", "Internal & External"),
	("PEB - Civil Works", 190, "Painting on Brick Walls", "SBI", "Two coats emulsion"),
	("PEB - Civil Works", 200, "Industrial Flooring", "SBI",
	 "With Floor Hardener 100 mm thick M-20 Grade"),
	("PEB - Civil Works", 210, "UPVC Windows", "SBI", "Standard sections"),
	("PEB - Civil Works", 220, "Rolling Shutters", "SBI", "Manual operation"),

	("PEB", 230, "Procurement of Structural Steel", "SBI", "IS 2062 Grade Steel"),
	("PEB", 240, "Fabrication of Structural Steel", "SBI", "Shop Fabricated"),
	("PEB", 250, "Transportation to Site", "SBI", "Included"),
	("PEB", 260, "Structural Steel Erection", "SBI", "Included"),
	("PEB", 270, "Roofing Material Supply", "SBI", "0.47 mm Bare Galvalume"),
	("PEB", 280, "Wall Cladding Supply", "SBI", "0.50 mm Colour Coated Sheet"),
	("PEB", 290, "Fasteners & Accessories", "SBI", "Included"),
	("PEB", 300, "Roof & Wall Sheeting Installation", "SBI", "Included"),
	("PEB", 310, "Ridge Covers & Flashings", "SBI", "Included"),
	("PEB", 320, "Turbo Ventilators", "SBI", "Included - alternate bay, one No."),
	("PEB", 330, "Skylights", "SBI", "Included, 2% of the floor area"),

	("Mezzanine", 340, "Decking sheet", "SBI", "0.7 mm Galvalume Painted Panel"),
	("Mezzanine", 350, "Concrete topping with mesh", "SBI", "75 mm thick M20 Concrete"),
]


def setup_scope_items():
	if not frappe.db.exists("DocType", "Scope Item"):
		return 0

	created = 0
	for section, order, description, by, remarks in SCOPE_ITEMS:
		if frappe.db.exists("Scope Item", description):
			continue
		frappe.get_doc({
			"doctype": "Scope Item",
			"scope_item_name": description,
			"scope_section": section,
			"display_order": order,
			"default_by": by,
			"default_remarks": remarks,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return created
