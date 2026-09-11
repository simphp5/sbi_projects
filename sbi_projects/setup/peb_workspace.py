# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
The PEB Estimation workspace.

Without this, the module page lists whatever doctypes Frappe happens to pick
up, in no useful order, and everything else has to be reached by typing a URL.

The layout follows the order the work is actually done:

    shortcuts   the four things opened every day
    Estimation  the enquiry-to-BOQ flow
    Pricing     the four masters, in the order they must be filled
    Questions   the client questionnaire
    Downstream  where a BOQ goes once it is priced

Rebuilt on every migrate, so the layout lives here rather than in the UI.
"""

import frappe

WORKSPACE = "PEB Estimation"
MODULE = "PEB Estimation"

# Opened most days -- these become the tiles across the top.
SHORTCUTS = [
	("Building Enquiry", "Blue"),
	("Estimation Sheet BOQ", "Green"),
	("Quotation", "Orange"),
	("Sales Order", "Grey"),
]

# (card label, [(doctype, optional description), ...])
CARDS = [
	(
		"Estimation",
		[
			("Building Enquiry", "Client requirement, collected through the portal"),
			("Estimation Sheet BOQ", "Quantities, rates and the resource plan"),
			("Quantity Rule", "Formulas that turn parameters into quantities"),
		],
	),
	(
		"Pricing Masters",
		[
			("Resource Type", "1. Categories, and how each is counted"),
			("Resource", "2. Cement, mason, JCB -- the single list"),
			("Rate Card", "3. Price per resource"),
			("Work Item", "4. Per-unit norms. The heart of the system"),
		],
	),
	(
		"Client Questionnaire",
		[
			("Building Work Type", "PEB civil, structure, both, other"),
			("Building Parameter Section", "The 14 sections"),
			("Building Parameter", "The 143 questions"),
			("Building Parameter Template", "What gets sent to a client"),
		],
	),
	(
		"Downstream",
		[
			("Quotation", "Markup folded into the rates"),
			("Sales Order", "Carries the BOQ link and the stages"),
			("Project", "Site execution"),
			("Material Request", "Materials from the BOQ roll-up"),
		],
	),
]


def setup_workspace():
	"""Create or rebuild the workspace. Safe to run on every migrate."""
	if not frappe.db.exists("DocType", "Workspace"):
		return 0
	if not frappe.db.exists("Module Def", MODULE):
		return 0

	doc = _get_doc()

	doc.label = WORKSPACE
	doc.title = WORKSPACE
	doc.module = MODULE
	doc.icon = "sitemap"
	doc.public = 1
	doc.is_hidden = 0
	if doc.meta.has_field("sequence_id"):
		doc.sequence_id = 20

	doc.links = []
	doc.shortcuts = []

	_add_shortcuts(doc)
	_add_cards(doc)
	doc.content = frappe.as_json(_content())

	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return 1


def _get_doc():
	if frappe.db.exists("Workspace", WORKSPACE):
		return frappe.get_doc("Workspace", WORKSPACE)
	doc = frappe.new_doc("Workspace")
	doc.name = WORKSPACE
	return doc


def _add_shortcuts(doc):
	for label, colour in SHORTCUTS:
		if not frappe.db.exists("DocType", label):
			continue
		doc.append("shortcuts", {
			"type": "DocType",
			"link_to": label,
			"label": label,
			"color": colour,
			"doc_view": "List",
		})


def _add_cards(doc):
	for card_label, entries in CARDS:
		usable = [(dt, d) for dt, d in entries if frappe.db.exists("DocType", dt)]
		if not usable:
			continue

		doc.append("links", {
			"type": "Card Break",
			"label": card_label,
			"link_count": len(usable),
			"hidden": 0,
			"onboard": 0,
		})
		for doctype, description in usable:
			doc.append("links", {
				"type": "Link",
				"label": doctype,
				"link_type": "DocType",
				"link_to": doctype,
				"description": description,
				"hidden": 0,
				"onboard": 0,
				"is_query_report": 0,
			})


def _content():
	"""The block layout Frappe renders: a heading, the tiles, then the cards."""
	blocks = [
		_block("header", {
			"text": '<span class="h4"><b>PEB Estimation</b></span>',
			"col": 12,
		}),
		_block("paragraph", {
			"text": "Set the masters up once, in the order shown, then work "
			        "left to right: enquiry, BOQ, quotation.",
			"col": 12,
		}),
	]

	present = [s for s, _ in SHORTCUTS if frappe.db.exists("DocType", s)]
	if present:
		blocks.append(_block("header", {
			"text": '<span class="h4"><b>Open often</b></span>', "col": 12,
		}))
		for label in present:
			blocks.append(_block("shortcut", {"shortcut_name": label, "col": 3}))

	blocks.append(_block("spacer", {"col": 12}))

	for card_label, entries in CARDS:
		if any(frappe.db.exists("DocType", dt) for dt, _ in entries):
			blocks.append(_block("card", {"card_name": card_label, "col": 4}))

	return blocks


def _block(block_type, data):
	return {"id": frappe.generate_hash(length=10), "type": block_type, "data": data}
