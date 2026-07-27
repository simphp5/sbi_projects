# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
PEB Estimation master data seeder.

Idempotent by design -- safe to run on every `after_migrate`. Existing records
are updated in place, never duplicated, and manual edits to fields that are not
listed below are preserved.

Called from sbi_projects.setup.install.after_install()
"""

import frappe

# --------------------------------------------------------------------------- #
# Work types
# --------------------------------------------------------------------------- #
WORK_TYPES = [
	("PEB Civil Only", 1, "Foundation, plinth, flooring and allied civil work only. Steel structure is in client scope."),
	("PEB Structure Only", 2, "Steel structure, sheeting and accessories only. Civil work is in client scope."),
	("Both", 3, "Turnkey - PEB structure plus civil work."),
	("Others", 4, "Any scope that does not fall under the above. Describe in the enquiry."),
]

# Shorthand used in the parameter table below
PCO = "PEB Civil Only"
PSO = "PEB Structure Only"
BOTH = "Both"
OTH = "Others"

ALL = [PCO, PSO, BOTH, OTH]
STRUCT = [PSO, BOTH]
CIVIL = [PCO, BOTH]
STRUCT_CIVIL = [PCO, PSO, BOTH]

YN = "Yes\nNo"
SCOPE_OPT = "SBI Scope\nClient Scope\nNot Applicable"

# --------------------------------------------------------------------------- #
# Sections  (name, no, bucket, description)
# --------------------------------------------------------------------------- #
SECTIONS = [
	("Project Information", 1, "Project", "Client and site identification."),
	("Building Details", 2, "Technical", "Geometry that drives BOQ quantities."),
	("Structural Design Criteria", 3, "Technical", "Codes and design basis."),
	("Loading Requirements", 4, "Technical", "All applied loads including crane."),
	("Roofing and Cladding", 5, "Technical", "Sheeting specification."),
	("Openings", 6, "Technical", "Shutters, doors, windows, louvers."),
	("Crane Requirements", 7, "Technical", "Crane vendor data."),
	("Accessories", 8, "Technical", "Gutters, trims, mesh, canopies."),
	("Civil Interface", 9, "Technical", "Foundation, FFL, flooring interface."),
	("Scope of Work", 10, "Scope", "Decides which BOQ line items are generated."),
	("Commercial Requirements", 11, "Commercial", "Terms carried to the Quotation."),
	("Documents Required from Client", 12, "Document", "Client attachments checklist."),
	("Special Requirements", 13, "Technical", "Fire, green building, corrosion, inspection."),
	("Deliverables", 14, "Commercial", "What SBI submits with the offer."),
]

# --------------------------------------------------------------------------- #
# Parameters
# (code, name, section, fieldtype, options, uom, mandatory, work_types, order)
# --------------------------------------------------------------------------- #
S1, S2, S3 = "Project Information", "Building Details", "Structural Design Criteria"
S4, S5, S6 = "Loading Requirements", "Roofing and Cladding", "Openings"
S7, S8, S9 = "Crane Requirements", "Accessories", "Civil Interface"
S10, S11 = "Scope of Work", "Commercial Requirements"
S12, S13, S14 = "Documents Required from Client", "Special Requirements", "Deliverables"

PARAMETERS = [
	# ---- 1. Project Information ----
	("PROJECT_NAME", "Project Name", S1, "Data", None, None, 1, ALL, 10),
	("CLIENT_NAME", "Client Name", S1, "Data", None, None, 1, ALL, 20),
	("PROJECT_LOCATION", "Project Location", S1, "Data", None, None, 1, ALL, 30),
	("END_USER", "End User", S1, "Data", None, None, 0, ALL, 40),
	("CONTACT_PERSON", "Contact Person", S1, "Data", None, None, 1, ALL, 50),
	("MOBILE_NUMBER", "Mobile Number", S1, "Data", None, None, 1, ALL, 60),
	("EMAIL_ID", "Email ID", S1, "Data", None, None, 1, ALL, 70),

	# ---- 2. Building Details ----
	("BUILDING_PURPOSE", "Purpose of Building", S2, "Select",
	 "Warehouse\nFactory\nWorkshop\nCommercial\nAircraft Hangar\nCold Storage\nMulti-purpose\nOthers",
	 None, 1, ALL, 10),
	("NO_OF_BUILDINGS", "Number of Buildings", S2, "Int", None, "Nos", 1, ALL, 20),
	("BUILDING_LENGTH", "Building Length", S2, "Float", None, "m", 1, ALL, 30),
	("BUILDING_WIDTH", "Building Width", S2, "Float", None, "m", 1, ALL, 40),
	("CLEAR_HEIGHT", "Clear Height / Eave Height", S2, "Float", None, "m", 1, ALL, 50),
	("RIDGE_HEIGHT", "Ridge Height", S2, "Float", None, "m", 0, STRUCT, 60),
	("NO_OF_BAYS", "Number of Bays", S2, "Int", None, "Nos", 0, STRUCT, 70),
	("BAY_SPACING", "Bay Spacing", S2, "Data", None, "mm", 0, STRUCT, 80),
	("ROOF_SLOPE", "Roof Slope", S2, "Data", None, None, 0, STRUCT, 90),
	("MEZZANINE_REQD", "Mezzanine Floor Required", S2, "Select", YN, None, 0, STRUCT_CIVIL, 100),
	("MEZZANINE_AREA", "Mezzanine Area", S2, "Float", None, "sqm", 0, STRUCT_CIVIL, 110),
	("CANOPY_REQD", "Canopy Required", S2, "Select", YN, None, 0, STRUCT, 120),
	("CANOPY_DETAILS", "Canopy Details (L x W x Nos)", S2, "Data", None, None, 0, STRUCT, 130),
	("LEAN_TO_REQD", "Lean-to Required", S2, "Select", YN, None, 0, STRUCT, 140),
	("FUTURE_EXPANSION", "Future Expansion Required", S2, "Select", YN, None, 0, ALL, 150),

	# ---- 3. Structural Design Criteria ----
	("DESIGN_CODE", "Design Code", S3, "Select",
	 "IS 800:2007\nMBMA\nAISC\nEurocode\nOthers", None, 0, STRUCT, 10),
	("WIND_SPEED", "Basic Wind Speed (IS 875 Part 3)", S3, "Float", None, "m/s", 0, STRUCT_CIVIL, 20),
	("SEISMIC_ZONE", "Seismic Zone", S3, "Select",
	 "Zone II\nZone III\nZone IV\nZone V", None, 0, STRUCT_CIVIL, 30),
	("IMPORTANCE_FACTOR", "Importance Factor", S3, "Float", None, None, 0, STRUCT, 40),
	("TERRAIN_CATEGORY", "Terrain Category", S3, "Select",
	 "Category 1\nCategory 2\nCategory 3\nCategory 4", None, 0, STRUCT, 50),
	("SNOW_LOAD", "Ground Snow Load", S3, "Float", None, "kN/sqm", 0, STRUCT, 60),
	("TEMP_RANGE", "Temperature Range", S3, "Data", None, "deg C", 0, STRUCT, 70),

	# ---- 4. Loading Requirements ----
	("ROOF_LIVE_LOAD", "Roof Live Load", S4, "Float", None, "kN/sqm", 0, STRUCT, 10),
	("COLLATERAL_LOAD", "Collateral Load", S4, "Float", None, "kN/sqm", 0, STRUCT, 20),
	("SOLAR_PANEL_LOAD", "Solar Panel Load", S4, "Float", None, "kg/sqm", 0, STRUCT, 30),
	("SUSPENDED_EQUIP_LOAD", "Suspended Equipment Load", S4, "Float", None, "kg/sqm", 0, STRUCT, 40),
	("HVAC_LOAD", "HVAC Load", S4, "Float", None, "kg/sqm", 0, STRUCT, 50),
	("FALSE_CEILING_LOAD", "False Ceiling Load", S4, "Float", None, "kg/sqm", 0, STRUCT, 60),
	("MONORAIL_LOAD", "Monorail Load", S4, "Float", None, "T", 0, STRUCT, 70),
	("CRANE_REQD", "Crane Required", S4, "Select", YN, None, 0, STRUCT_CIVIL, 80),
	("CRANE_TYPE", "Crane Type", S4, "Select",
	 "EOT\nGantry\nSemi-Gantry\nUnderslung\nJib", None, 0, STRUCT, 90),
	("CRANE_CAPACITY", "Crane Capacity", S4, "Float", None, "T", 0, STRUCT, 100),
	("CRANE_SPAN", "Crane Span", S4, "Float", None, "m", 0, STRUCT, 110),
	("CRANE_WHEEL_LOAD", "Crane Maximum Wheel Load", S4, "Float", None, "kN", 0, STRUCT, 120),
	("CRANE_HOOK_HEIGHT", "Crane Hook Height", S4, "Float", None, "m", 0, STRUCT, 130),
	("MEZZANINE_LIVE_LOAD", "Mezzanine Live Load", S4, "Float", None, "kN/sqm", 0, STRUCT_CIVIL, 140),
	("WALKWAY_REQD", "Roof Access Walkway Required", S4, "Select", YN, None, 0, STRUCT, 150),

	# ---- 5. Roofing and Cladding ----
	("ROOF_SHEET_TYPE", "Roof Sheet Type", S5, "Select",
	 "Bare Galvalume\nColour Coated", None, 0, STRUCT, 10),
	("ROOF_SHEET_THICKNESS", "Roof Sheet Thickness", S5, "Select",
	 "0.47\n0.50\n0.60", "mm", 0, STRUCT, 20),
	("ROOF_INSULATION", "Roof Insulation", S5, "Select",
	 "None\nGlass Wool\nRock Wool\nPUF", None, 0, STRUCT, 30),
	("ROOF_INSULATION_THK", "Roof Insulation Thickness", S5, "Float", None, "mm", 0, STRUCT, 40),
	("SKYLIGHT_PCT", "Skylight Percentage", S5, "Float", None, "%", 0, STRUCT, 50),
	("TURBO_VENT_QTY", "Turbo Ventilators", S5, "Int", None, "Nos", 0, STRUCT, 60),
	("RIDGE_VENT_REQD", "Ridge Vent Required", S5, "Select", YN, None, 0, STRUCT, 70),
	("ROOF_MONITOR_REQD", "Roof Monitor Required", S5, "Select", YN, None, 0, STRUCT, 80),
	("WALL_SHEET_TYPE", "Wall Sheet Type", S5, "Select",
	 "Colour Coated Sheet\nSandwich Panel\nInsulated Panel\nNot Required", None, 0, STRUCT, 90),
	("WALL_SHEET_THICKNESS", "Wall Sheet Thickness", S5, "Select",
	 "0.47\n0.50\n0.60", "mm", 0, STRUCT, 100),
	("AAC_BLOCK_HEIGHT", "AAC / Brick Wall Height up to Plinth", S5, "Float", None, "m", 0, STRUCT_CIVIL, 110),

	# ---- 6. Openings ----
	("ROLLING_SHUTTER_QTY", "Rolling Shutters", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 10),
	("ROLLING_SHUTTER_SIZE", "Rolling Shutter Size (W x H)", S6, "Data", None, "m", 0, STRUCT_CIVIL, 20),
	("SLIDING_DOOR_QTY", "Sliding Doors", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 30),
	("INDUSTRIAL_DOOR_QTY", "Industrial Doors", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 40),
	("PERSONNEL_DOOR_QTY", "Personnel Doors", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 50),
	("FIRE_DOOR_QTY", "Fire Doors", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 60),
	("ALUM_WINDOW_QTY", "Aluminium / UPVC Windows", S6, "Int", None, "Nos", 0, STRUCT_CIVIL, 70),
	("ALUM_WINDOW_SIZE", "Window Size (W x H)", S6, "Data", None, "m", 0, STRUCT_CIVIL, 80),
	("LOUVER_QTY", "Louvers", S6, "Int", None, "Nos", 0, STRUCT, 90),
	("VENTILATOR_QTY", "Ventilators", S6, "Int", None, "Nos", 0, STRUCT, 100),

	# ---- 7. Crane Requirements ----
	("CRANE_MANUFACTURER", "Crane Manufacturer", S7, "Data", None, None, 0, STRUCT, 10),
	("CRANE_DUTY_CLASS", "Crane Duty Class", S7, "Select",
	 "Class I\nClass II\nClass III\nClass IV", None, 0, STRUCT, 20),
	("NO_OF_CRANES", "Number of Cranes", S7, "Int", None, "Nos", 0, STRUCT, 30),
	("CRANE_RAIL_DETAILS", "Crane Rail Details", S7, "Data", None, None, 0, STRUCT, 40),
	("CRANE_BEAM_SCOPE", "Crane Beam Scope", S7, "Select", SCOPE_OPT, None, 0, STRUCT, 50),
	("CRANE_RUN_LENGTH", "Crane Run Length", S7, "Float", None, "m", 0, STRUCT, 60),

	# ---- 8. Accessories ----
	("GUTTER_TYPE", "Gutter Type", S8, "Select",
	 "Eave Gutter\nValley Gutter\nBoth\nNot Required", None, 0, STRUCT, 10),
	("DOWNTAKE_PIPE_TYPE", "Down Take Pipe Type", S8, "Select",
	 "PVC\nGI\nNot Required", None, 0, STRUCT, 20),
	("DOWNTAKE_PIPE_DIA", "Down Take Pipe Diameter", S8, "Float", None, "mm", 0, STRUCT, 30),
	("FLASHING_REQD", "Flashings Required", S8, "Select", YN, None, 0, STRUCT, 40),
	("TRIM_REQD", "Trims Required", S8, "Select", YN, None, 0, STRUCT, 50),
	("BIRD_MESH_REQD", "Bird Mesh Required", S8, "Select", YN, None, 0, STRUCT, 60),
	("WIRE_MESH_REQD", "Wire Mesh Required", S8, "Select", YN, None, 0, STRUCT, 70),
	("EAVE_STRUT_REQD", "Eave Strut Required", S8, "Select", YN, None, 0, STRUCT, 80),
	("CANOPY_QTY", "Canopies", S8, "Int", None, "Nos", 0, STRUCT, 90),

	# ---- 9. Civil Interface ----
	("FOUNDATION_SCOPE", "Foundation Scope", S9, "Select", SCOPE_OPT, None, 0, STRUCT_CIVIL, 10),
	("ANCHOR_BOLT_SCOPE", "Anchor Bolt Scope", S9, "Select", SCOPE_OPT, None, 0, STRUCT_CIVIL, 20),
	("GROUTING_SCOPE", "Grouting Scope", S9, "Select", SCOPE_OPT, None, 0, STRUCT_CIVIL, 30),
	("FFL", "Finished Floor Level (FFL)", S9, "Float", None, "m", 0, CIVIL, 40),
	("PLINTH_HEIGHT", "Plinth Height", S9, "Float", None, "m", 0, CIVIL, 50),
	("SOIL_SBC", "Soil Safe Bearing Capacity", S9, "Float", None, "kN/sqm", 0, CIVIL, 60),
	("FLOORING_TYPE", "Flooring Type", S9, "Select",
	 "Power Trowel Finish\nVDF\nTremix\nIPS\nNot Required", None, 0, CIVIL, 70),
	("FLOOR_THICKNESS", "Floor Thickness", S9, "Float", None, "mm", 0, CIVIL, 80),

	# ---- 10. Scope of Work ----
	("SCOPE_DESIGN", "Design", S10, "Check", None, None, 0, ALL, 10),
	("SCOPE_GA_DRAWING", "GA Drawings", S10, "Check", None, None, 0, ALL, 20),
	("SCOPE_APPROVAL_DRAWING", "Approval Drawings", S10, "Check", None, None, 0, ALL, 30),
	("SCOPE_SHOP_DRAWING", "Shop Drawings", S10, "Check", None, None, 0, STRUCT, 40),
	("SCOPE_FABRICATION", "Fabrication", S10, "Check", None, None, 0, STRUCT, 50),
	("SCOPE_SUPPLY", "Supply", S10, "Check", None, None, 0, ALL, 60),
	("SCOPE_TRANSPORTATION", "Transportation", S10, "Check", None, None, 0, ALL, 70),
	("SCOPE_ERECTION", "Erection", S10, "Check", None, None, 0, STRUCT, 80),
	("SCOPE_ROOFING", "Roofing", S10, "Check", None, None, 0, STRUCT, 90),
	("SCOPE_CLADDING", "Cladding", S10, "Check", None, None, 0, STRUCT, 100),
	("SCOPE_FLASHING", "Flashings", S10, "Check", None, None, 0, STRUCT, 110),
	("SCOPE_RAINWATER_SYSTEM", "Rainwater System", S10, "Check", None, None, 0, STRUCT, 120),
	("SCOPE_MEZZANINE", "Mezzanine", S10, "Check", None, None, 0, STRUCT_CIVIL, 130),
	("SCOPE_STAIRCASE", "Staircase", S10, "Check", None, None, 0, STRUCT_CIVIL, 140),
	("SCOPE_HANDRAIL", "Handrails", S10, "Check", None, None, 0, STRUCT_CIVIL, 150),
	("SCOPE_PAINTING", "Painting", S10, "Check", None, None, 0, ALL, 160),
	("SCOPE_CIVIL_FOUNDATION", "Civil Foundation", S10, "Check", None, None, 0, CIVIL, 170),
	("SCOPE_FLOORING", "Flooring", S10, "Check", None, None, 0, CIVIL, 180),
	("SCOPE_TURNKEY_EPC", "Complete Turnkey EPC", S10, "Check", None, None, 0, ALL, 190),

	# ---- 11. Commercial Requirements ----
	("DELIVERY_PERIOD", "Delivery Period", S11, "Data", None, None, 0, ALL, 10),
	("COMPLETION_SCHEDULE", "Project Completion Schedule", S11, "Data", None, None, 0, ALL, 20),
	("PAYMENT_TERMS", "Payment Terms", S11, "Small Text", None, None, 0, ALL, 30),
	("TENDER_SUBMISSION_DATE", "Tender Submission Date", S11, "Date", None, None, 0, ALL, 40),
	("OFFER_VALIDITY", "Validity of Offer", S11, "Data", None, None, 0, ALL, 50),
	("LD_CLAUSE", "LD Clause", S11, "Small Text", None, None, 0, ALL, 60),
	("PBG_REQUIRED", "Performance Bank Guarantee Required", S11, "Select", YN, None, 0, ALL, 70),
	("ABG_REQUIRED", "Advance Bank Guarantee Required", S11, "Select", YN, None, 0, ALL, 80),
	("INSURANCE_REQUIRED", "Insurance Required", S11, "Select", YN, None, 0, ALL, 90),

	# ---- 12. Documents Required from Client ----
	("DOC_ARCHITECTURAL_DRAWING", "Architectural Drawings (DWG/PDF)", S12, "Attach", None, None, 0, ALL, 10),
	("DOC_SITE_LAYOUT", "Site Layout", S12, "Attach", None, None, 0, ALL, 20),
	("DOC_COLUMN_GRID", "Column Grid", S12, "Attach", None, None, 0, STRUCT_CIVIL, 30),
	("DOC_EQUIPMENT_LAYOUT", "Equipment Layout", S12, "Attach", None, None, 0, ALL, 40),
	("DOC_CRANE_VENDOR_DATA", "Crane Vendor Data", S12, "Attach", None, None, 0, STRUCT, 50),
	("DOC_SOIL_REPORT", "Geotechnical (Soil Investigation) Report", S12, "Attach", None, None, 0, STRUCT_CIVIL, 60),
	("DOC_TOPO_SURVEY", "Topographical Survey", S12, "Attach", None, None, 0, CIVIL, 70),
	("DOC_TENDER_SPEC", "Tender Specifications", S12, "Attach", None, None, 0, ALL, 80),
	("DOC_CLIENT_BOQ", "Client BOQ", S12, "Attach", None, None, 0, ALL, 90),
	("DOC_DESIGN_BASIS_REPORT", "Design Basis Report", S12, "Attach", None, None, 0, STRUCT, 100),

	# ---- 13. Special Requirements ----
	("FIRE_RATING", "Fire Rating", S13, "Data", None, None, 0, STRUCT_CIVIL, 10),
	("FM_APPROVED_ROOFING", "FM Approved Roofing", S13, "Select", YN, None, 0, STRUCT, 20),
	("GREEN_BUILDING", "Green Building", S13, "Select",
	 "None\nIGBC\nLEED\nGRIHA", None, 0, ALL, 30),
	("CORROSION_CATEGORY", "Corrosion Category", S13, "Select",
	 "C2\nC3\nC4\nC5", None, 0, STRUCT, 40),
	("HOT_DIP_GALVANIZING", "Hot-Dip Galvanizing Required", S13, "Select", YN, None, 0, STRUCT, 50),
	("SPECIAL_PAINT_SYSTEM", "Special Paint System", S13, "Small Text", None, None, 0, STRUCT, 60),
	("FACTORY_ACCEPTANCE_INSPECTION", "Factory Acceptance Inspection", S13, "Select", YN, None, 0, STRUCT, 70),
	("THIRD_PARTY_INSPECTION", "Third-Party Inspection Required", S13, "Select", YN, None, 0, ALL, 80),

	# ---- 14. Deliverables ----
	("DELV_TECHNICAL_PROPOSAL", "Technical Proposal", S14, "Check", None, None, 0, ALL, 10),
	("DELV_COMMERCIAL_PROPOSAL", "Commercial Proposal", S14, "Check", None, None, 0, ALL, 20),
	("DELV_PRELIM_GA_DRAWING", "Preliminary GA Drawing", S14, "Check", None, None, 0, STRUCT, 30),
	("DELV_LOADING_DATA", "Preliminary Loading Data", S14, "Check", None, None, 0, STRUCT, 40),
	("DELV_MATERIAL_SPEC", "Material Specifications", S14, "Check", None, None, 0, ALL, 50),
	("DELV_DELIVERY_SCHEDULE", "Delivery Schedule", S14, "Check", None, None, 0, ALL, 60),
	("DELV_SCOPE_EXCLUSION", "Scope and Exclusion List", S14, "Check", None, None, 0, ALL, 70),
	("DELV_PAYMENT_TERMS", "Payment Terms", S14, "Check", None, None, 0, ALL, 80),
	("DELV_WARRANTY_TERMS", "Warranty Terms", S14, "Check", None, None, 0, ALL, 90),
]

# --------------------------------------------------------------------------- #
# Workflow
# --------------------------------------------------------------------------- #
WORKFLOW_NAME = "Building Parameter Template Approval"

WORKFLOW_STATES = [
	# state, doc_status, allow_edit, style
	("Draft", "0", "Sales User", ""),
	("Pending Approval", "0", "Sales Manager", "Warning"),
	("Approved", "0", "System Manager", "Success"),
	("Inactive", "0", "System Manager", "Danger"),
]

WORKFLOW_TRANSITIONS = [
	# state, action, next_state, allowed role
	("Draft", "Submit for Approval", "Pending Approval", "Sales User"),
	("Pending Approval", "Approve", "Approved", "Sales Manager"),
	("Pending Approval", "Reject", "Draft", "Sales Manager"),
	("Approved", "Deactivate", "Inactive", "Sales Manager"),
	("Inactive", "Reactivate", "Approved", "Sales Manager"),
]


# --------------------------------------------------------------------------- #
# Seeders
# --------------------------------------------------------------------------- #
def setup_peb_masters():
	"""Entry point. Safe to call repeatedly."""
	if not frappe.db.exists("DocType", "Building Parameter"):
		# App files not migrated yet -- nothing to seed.
		return

	created = {
		"work_types": _seed_work_types(),
		"sections": _seed_sections(),
		"parameters": _seed_parameters(),
		"workflow": _seed_workflow(),
		"templates": _seed_default_templates(),
	}
	frappe.db.commit()
	return created


def _seed_work_types():
	count = 0
	for name, order, description in WORK_TYPES:
		if frappe.db.exists("Building Work Type", name):
			frappe.db.set_value(
				"Building Work Type", name,
				{"display_order": order, "description": description},
				update_modified=False,
			)
			continue
		frappe.get_doc({
			"doctype": "Building Work Type",
			"work_type_name": name,
			"display_order": order,
			"description": description,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		count += 1
	return count


def _seed_sections():
	count = 0
	for name, no, bucket, description in SECTIONS:
		if frappe.db.exists("Building Parameter Section", name):
			frappe.db.set_value(
				"Building Parameter Section", name,
				{"section_no": no, "bucket": bucket, "description": description},
				update_modified=False,
			)
			continue
		frappe.get_doc({
			"doctype": "Building Parameter Section",
			"section_name": name,
			"section_no": no,
			"bucket": bucket,
			"description": description,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		count += 1
	return count


def _seed_parameters():
	count = 0
	for (code, label, section, fieldtype, options, uom,
		 mandatory, work_types, order) in PARAMETERS:

		if frappe.db.exists("Building Parameter", code):
			continue

		doc = frappe.get_doc({
			"doctype": "Building Parameter",
			"parameter_code": code,
			"parameter_name": label,
			"section": section,
			"fieldtype": fieldtype,
			"options": options,
			"uom": uom,
			"is_mandatory": mandatory,
			"display_order": order,
			"is_active": 1,
		})
		for wt in work_types:
			doc.append("applicable_work_type", {"work_type": wt})
		doc.insert(ignore_permissions=True)
		count += 1
	return count


def _seed_workflow():
	for state, _ds, _edit, style in WORKFLOW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({
				"doctype": "Workflow State",
				"workflow_state_name": state,
				"style": style,
			}).insert(ignore_permissions=True)

	for _s, action, _n, _r in WORKFLOW_TRANSITIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({
				"doctype": "Workflow Action Master",
				"workflow_action_name": action,
			}).insert(ignore_permissions=True)

	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return 0

	wf = frappe.get_doc({
		"doctype": "Workflow",
		"workflow_name": WORKFLOW_NAME,
		"document_type": "Building Parameter Template",
		"workflow_state_field": "status",
		"is_active": 1,
		"send_email_alert": 1,
	})
	for state, doc_status, allow_edit, _style in WORKFLOW_STATES:
		wf.append("states", {
			"state": state,
			"doc_status": doc_status,
			"allow_edit": allow_edit,
		})
	for state, action, next_state, role in WORKFLOW_TRANSITIONS:
		wf.append("transitions", {
			"state": state,
			"action": action,
			"next_state": next_state,
			"allowed": role,
			"allow_self_approval": 1,
		})
	wf.insert(ignore_permissions=True)
	return 1


def _seed_default_templates():
	"""One starter template per work type, pre-loaded with all its parameters."""
	count = 0
	for name, _order, _desc in WORK_TYPES:
		template_name = "{0} - Standard".format(name)
		if frappe.db.exists("Building Parameter Template", template_name):
			continue

		doc = frappe.get_doc({
			"doctype": "Building Parameter Template",
			"template_name": template_name,
			"work_type": name,
			"status": "Draft",
			"version": "1.0",
			"remarks": "Auto-generated starter template. Review and submit for approval.",
		})
		doc.load_parameters()
		doc.insert(ignore_permissions=True)
		count += 1
	return count
