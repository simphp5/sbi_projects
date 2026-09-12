# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
The BOQ workspace.

Every link is numbered so a new user can simply follow the sequence: finish
1.1 to 1.6 once, then 2.x onward for each job. The numbering mirrors how a BOQ
itself is written, which makes it read naturally to anyone in the trade.

Card 1 is one-time setup and is deliberately ordered -- Work Item cannot pick a
resource that does not exist, and the Rate Card cannot price a resource with no
type. Cards 2 to 4 are the per-job flow.

Rebuilt on every migrate, so this file is the layout. Changes made in the UI
are overwritten.
"""

import frappe

WORKSPACE = "BOQ"
MODULE = "PEB Estimation"

# Opened most days -- tiles across the top.
SHORTCUTS = [
	("Building Enquiry", "Blue"),
	("Estimation Sheet BOQ", "Green"),
	("Quotation", "Orange"),
	("Sales Order", "Grey"),
]

# (card label, [(number, doctype, note), ...])
CARDS = [
	(
		"1. Masters — set up once",
		[
			("1.1", "Resource Type",
			 "Categories, and how each is counted: by quantity, day, hour or trip"),
			("1.2", "Resource",
			 "Cement, mason, JCB — one list, so a name is never spelled twice"),
			("1.3", "Rate Card",
			 "Price per resource. Change a price here and every work item reprices"),
			("1.4", "Work Item",
			 "What one unit consumes. The heart of the system — fill this carefully"),
			("1.5", "Payment Terms Template",
			 "The billing stages. Everything stage-wise reads from here"),
			("1.6", "Quantity Rule",
			 "PEB only. Formulas that turn client answers into quantities"),
		],
	),
	(
		"2. Client requirement — each job",
		[
			("2.1", "Building Work Type",
			 "PEB civil only, structure only, both, or other"),
			("2.2", "Building Parameter Section",
			 "The 14 sections of the questionnaire"),
			("2.3", "Building Parameter",
			 "The 143 questions behind those sections"),
			("2.4", "Building Parameter Template",
			 "What gets sent. Must be Approved before a client can see it"),
			("2.5", "Building Enquiry",
			 "Create it, send the secure link, the client fills it in"),
		],
	),
	(
		"3. Estimate and quote",
		[
			("3.1", "Estimation Sheet BOQ",
			 "Quantities, rates, and the manpower and material the job needs"),
			("3.2", "Quotation",
			 "Created from the BOQ. Markup is folded into the rates"),
		],
	),
	(
		"4. After the order",
		[
			("4.1", "Sales Order",
			 "Carries the BOQ link and the payment stages forward"),
			("4.2", "Project",
			 "Created with its stages. Site execution starts here"),
			("4.3", "Material Request",
			 "Materials from the BOQ roll-up. Labour and plant are left out"),
		],
	),
]

INTRO = (
	"Follow the numbers. Card 1 is done once, when the system is set up. "
	"Cards 2 to 4 are the path every job takes, from enquiry to site."
)


def setup_workspace():
	"""Create or rebuild the BOQ workspace. Safe on every migrate."""
	if not frappe.db.exists("DocType", "Workspace"):
		return 0

	doc = _get_doc()

	doc.label = WORKSPACE
	doc.title = WORKSPACE
	if frappe.db.exists("Module Def", MODULE):
		doc.module = MODULE
	doc.icon = "file"
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
		usable = [e for e in entries if frappe.db.exists("DocType", e[1])]
		if not usable:
			continue

		doc.append("links", {
			"type": "Card Break",
			"label": card_label,
			"link_count": len(usable),
			"hidden": 0,
			"onboard": 0,
		})
		for number, doctype, note in usable:
			doc.append("links", {
				"type": "Link",
				# the number is carried in the label so it shows on the card
				"label": "{0}  {1}".format(number, doctype),
				"link_type": "DocType",
				"link_to": doctype,
				"description": note,
				"hidden": 0,
				"onboard": 0,
				"is_query_report": 0,
			})


def _content():
	blocks = [
		_block("header", {
			"text": '<span class="h4"><b>Bill of Quantities</b></span>',
			"col": 12,
		}),
		_block("paragraph", {"text": INTRO, "col": 12}),
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
		if any(frappe.db.exists("DocType", e[1]) for e in entries):
			blocks.append(_block("card", {"card_name": card_label, "col": 4}))

	return blocks


def _block(block_type, data):
	return {"id": frappe.generate_hash(length=10), "type": block_type, "data": data}
