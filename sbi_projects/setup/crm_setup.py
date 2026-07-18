# Copyright (c) 2026, Velmaska and contributors
"""Seeds for the SBI CRM: lead sources, payment terms, T&C, dashboard."""

import frappe
from frappe.utils import flt

ENQUIRY_TYPE_DT = "Enquiry Type"
LEAD_PARAM_DT = "Lead Enquiry Parameter"


# ==================================================================
# 1. LEAD SOURCE
# ==================================================================
LEAD_SOURCES = [
	"Website Enquiry",
	"Referral",
	"Cold Call",
	"Exhibition / Trade Show",
	"Existing Customer",
	"Architect / Consultant",
	"Contractor",
	"Government Tender",
	"Social Media",
	"Walk-in",
]


def seed_lead_sources():
	for s in LEAD_SOURCES:
		if not frappe.db.exists("Lead Source", s):
			frappe.get_doc({"doctype": "Lead Source", "source_name": s}).insert(
				ignore_permissions=True
			)


# ==================================================================
# 2. PAYMENT TERMS  ->  mapped to Project Stage
# ==================================================================
PAYMENT_TERMS = [
	# (name, invoice_portion, credit_days, project_stage)
	("SBI Advance 20%",          20, 0,  "Design & Drawing Approval"),
	("SBI On Foundation 15%",    15, 15, "Foundation / Civil Work"),
	("SBI On Fabrication 30%",   30, 15, "Fabrication"),
	("SBI On Dispatch 10%",      10, 15, "Material Dispatch"),
	("SBI On Erection 20%",      20, 30, "Erection"),
	("SBI On Handover 5%",        5, 30, "Handover"),
]

TERMS_TEMPLATE = "SBI PEB Standard Payment Terms"


def seed_payment_terms():
	for name, portion, days, stage in PAYMENT_TERMS:
		if frappe.db.exists("Payment Term", name):
			# keep the stage mapping in step even if the term already exists
			if frappe.db.exists("Project Stage", stage):
				frappe.db.set_value("Payment Term", name, "sbi_stage", stage)
			continue

		doc = frappe.get_doc({
			"doctype": "Payment Term",
			"payment_term_name": name,
			"invoice_portion": portion,
			"due_date_based_on": "Days after invoice date",
			"credit_days": days,
			"description": f"{portion}% - {stage}",
		})
		if frappe.db.exists("Project Stage", stage):
			doc.sbi_stage = stage
		doc.insert(ignore_permissions=True)

	if not frappe.db.exists("Payment Terms Template", TERMS_TEMPLATE):
		tmpl = frappe.get_doc({
			"doctype": "Payment Terms Template",
			"template_name": TERMS_TEMPLATE,
			"terms": [
				{
					"payment_term": name,
					"invoice_portion": portion,
					"due_date_based_on": "Days after invoice date",
					"credit_days": days,
					"description": f"{portion}% - {stage}",
				}
				for name, portion, days, stage in PAYMENT_TERMS
			],
		})
		tmpl.insert(ignore_permissions=True)


# ==================================================================
# 3. QUOTATION TERMS & CONDITIONS
# ==================================================================
TNC_NAME = "SBI PEB Standard Terms"

TNC_BODY = """<h4>Terms &amp; Conditions</h4>
<ol>
<li><b>Validity:</b> This quotation is valid for 30 days from the date of issue.</li>
<li><b>Taxes:</b> GST as applicable, extra at actuals.</li>
<li><b>Payment:</b> As per the payment schedule attached. All payments by RTGS / NEFT.</li>
<li><b>Design:</b> Fabrication commences only after written approval of GA drawings by the client.</li>
<li><b>Scope Excludes:</b> Soil investigation, civil foundation (unless separately quoted), power and water at site, statutory approvals, and any item not expressly listed.</li>
<li><b>Site Conditions:</b> Client to provide clear, level and accessible site, along with free storage space, power and water.</li>
<li><b>Erection:</b> Erection to be carried out in a continuous run. Idling charges apply for delays attributable to the client.</li>
<li><b>Delivery:</b> As per the agreed schedule from the date of drawing approval and receipt of advance.</li>
<li><b>Price Variation:</b> Steel prices are subject to variation. Rates are firm for 30 days only.</li>
<li><b>Warranty:</b> Structural workmanship warranted for 12 months from handover. Sheeting as per manufacturer's warranty.</li>
<li><b>Force Majeure:</b> Neither party shall be liable for delays caused by events beyond reasonable control.</li>
<li><b>Jurisdiction:</b> Subject to Chennai jurisdiction.</li>
</ol>"""


def seed_terms_and_conditions():
	if frappe.db.exists("Terms and Conditions", TNC_NAME):
		return
	frappe.get_doc({
		"doctype": "Terms and Conditions",
		"title": TNC_NAME,
		"selling": 1,
		"terms": TNC_BODY,
	}).insert(ignore_permissions=True)


# ==================================================================
# 4. OPPORTUNITY / QUOTATION custom fields (enquiry carry-forward)
# ==================================================================
def add_crm_custom_fields():
	"""Only added when the Enquiry Type masters exist on this site."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if not (frappe.db.exists("DocType", ENQUIRY_TYPE_DT)
	        and frappe.db.exists("DocType", LEAD_PARAM_DT)):
		return

	fields = {}
	for dt, anchor in (("Opportunity", "opportunity_type"), ("Quotation", "order_type")):
		fields[dt] = [
			{
				"fieldname": "sbi_enquiry_sb",
				"label": "Enquiry Details",
				"fieldtype": "Section Break",
				"insert_after": anchor,
				"collapsible": 1,
			},
			{
				"fieldname": "sbi_type_of_enquiry",
				"label": "Type of Enquiry",
				"fieldtype": "Link",
				"options": ENQUIRY_TYPE_DT,
				"insert_after": "sbi_enquiry_sb",
			},
			{
				"fieldname": "sbi_enquiry_parameters",
				"label": "Enquiry Parameters",
				"fieldtype": "Table",
				"options": LEAD_PARAM_DT,
				"insert_after": "sbi_type_of_enquiry",
			},
		]

	fields["Opportunity"].append({
		"fieldname": "sbi_lead_stage",
		"label": "Lead Stage (at conversion)",
		"fieldtype": "Link",
		"options": "Lead Stage",
		"insert_after": "sbi_enquiry_parameters",
		"read_only": 1,
	})

	create_custom_fields(fields, ignore_validate=True)


# ==================================================================
# 5. CRM DASHBOARD  (charts + number cards)
# ==================================================================
def seed_dashboard():
	charts = [
		{
			"name": "SBI Lead Pipeline",
			"chart_name": "SBI Lead Pipeline",
			"chart_type": "Group By",
			"document_type": "Lead",
			"group_by_type": "Count",
			"group_by_based_on": "sbi_lead_stage",
			"type": "Bar",
			"number_of_groups": 15,
			"is_public": 1,
			"timeseries": 0,
		},
		{
			"name": "SBI Leads by Source",
			"chart_name": "SBI Leads by Source",
			"chart_type": "Group By",
			"document_type": "Lead",
			"group_by_type": "Count",
			"group_by_based_on": "source",
			"type": "Donut",
			"number_of_groups": 10,
			"is_public": 1,
			"timeseries": 0,
		},
		{
			"name": "SBI Leads Created",
			"chart_name": "SBI Leads Created",
			"chart_type": "Count",
			"document_type": "Lead",
			"based_on": "creation",
			"time_interval": "Monthly",
			"timespan": "Last Year",
			"type": "Line",
			"is_public": 1,
			"timeseries": 1,
		},
	]
	for c in charts:
		if frappe.db.exists("Dashboard Chart", c["name"]):
			continue
		try:
			doc = frappe.get_doc(dict(doctype="Dashboard Chart", **c))
			doc.insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Chart failed: {c['name']}")

	cards = [
		{
			"name": "SBI Open Leads",
			"label": "Open Leads",
			"document_type": "Lead",
			"function": "Count",
			"filters_json": '[["Lead","status","not in",["Converted","Do Not Contact"]]]',
			"color": "#449CF0",
		},
		{
			"name": "SBI Site Visits Pending",
			"label": "Awaiting Site Visit",
			"document_type": "Lead",
			"function": "Count",
			"filters_json": '[["Lead","sbi_lead_stage","in",["New Enquiry","Contacted","First Meeting"]]]',
			"color": "#F8814F",
		},
		{
			"name": "SBI Quotations Submitted",
			"label": "Quotations Submitted",
			"document_type": "Lead",
			"function": "Count",
			"filters_json": '[["Lead","sbi_lead_stage","in",["Quotation Submitted","Negotiation"]]]',
			"color": "#ECAD4B",
		},
		{
			"name": "SBI Leads Won",
			"label": "Leads Won",
			"document_type": "Lead",
			"function": "Count",
			"filters_json": '[["Lead","sbi_lead_stage","=","Won"]]',
			"color": "#29CD42",
		},
		{
			"name": "SBI Follow-ups Overdue",
			"label": "Follow-ups Overdue",
			"document_type": "Lead",
			"function": "Count",
			"filters_json": '[["Lead","sbi_next_followup","<","Today"],["Lead","status","not in",["Converted","Do Not Contact"]]]',
			"color": "#E24C4C",
		},
	]
	for c in cards:
		if frappe.db.exists("Number Card", c["name"]):
			continue
		try:
			frappe.get_doc(dict(
				doctype="Number Card",
				is_public=1,
				type="Document Type",
				**c,
			)).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"Card failed: {c['name']}")


# ==================================================================
# 6. ASSIGNMENT RULE  (round robin across Sales Users)
# ==================================================================
ASSIGNMENT_RULE = "SBI Lead Assignment"


def seed_assignment_rule():
	if frappe.db.exists("Assignment Rule", ASSIGNMENT_RULE):
		return

	users = frappe.get_all(
		"Has Role",
		filters={"role": "Sales User", "parenttype": "User"},
		fields=["parent"],
		limit=20,
	)
	user_list = [
		u.parent for u in users
		if u.parent not in ("Administrator", "Guest")
		and frappe.db.get_value("User", u.parent, "enabled")
	]
	if not user_list:
		return  # nothing to assign to yet; user can add members later

	try:
		frappe.get_doc({
			"doctype": "Assignment Rule",
			"name": ASSIGNMENT_RULE,
			"document_type": "Lead",
			"rule": "Round Robin",
			"disabled": 1,  # enable manually once the user list is right
			"assign_condition": 'status == "Lead"',
			"unassign_condition": 'status in ("Converted", "Do Not Contact")',
			"users": [{"user": u} for u in user_list],
			"assignment_days": [
				{"day": d} for d in
				["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
			],
		}).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Assignment Rule failed")


# ==================================================================
def setup_crm():
	for step in (
		seed_lead_sources,
		seed_payment_terms,
		seed_terms_and_conditions,
		add_crm_custom_fields,
		seed_dashboard,
		seed_assignment_rule,
	):
		try:
			step()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(frappe.get_traceback(), f"sbi CRM setup: {step.__name__}")
