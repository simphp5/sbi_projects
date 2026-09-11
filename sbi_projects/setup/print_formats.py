import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PRINT_FORMAT_NAME = "SBI Tax Invoice"
CLIENT_SCRIPT_NAME = "SBI Sales Invoice Print New Tab"

SO_SERIES = "SBI/\nSBIPPL/\nSAL-ORD-.YYYY.-"
SI_SERIES = "SBI/\nSBIPPL/\nACC-SINV-.YYYY.-\nACC-SINV-RET-.YYYY.-"

CLIENT_SCRIPT = """
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (frm.is_new()) return;

        const do_print = () => {
            const p = [
                'doctype=' + encodeURIComponent(frm.doc.doctype),
                'name=' + encodeURIComponent(frm.doc.name),
                'format=' + encodeURIComponent('SBI Tax Invoice'),
                'no_letterhead=1',
                '_lang=en'
            ].join('&');
            window.open('/printview?' + p, '_blank');
        };

        const verify_bank = () => {
            frappe.call({
                method: 'sbi_projects.utils.print_helpers.bank_details_for',
                args: { invoice: frm.doc.name },
                freeze: true,
                freeze_message: __('Checking bank details...')
            }).then(r => {
                const b = r.message || {};
                const miss = '<span style="color:#BE1E2D">' + __('Not set') + '</span>';

                const d = new frappe.ui.Dialog({
                    title: __('Verify Bank Details'),
                    fields: [
                        { fieldtype: 'HTML', fieldname: 'preview' },
                        {
                            fieldtype: 'Link', fieldname: 'bank_account',
                            label: __('Bank Account'), options: 'Bank Account'
                        },
                        { fieldtype: 'HTML', fieldname: 'hint' }
                    ],
                    primary_action_label: __('Print'),
                    primary_action(v) {
                        if (v.bank_account && v.bank_account !== b.bank_account) {
                            frm.set_value('company_bank_account', v.bank_account);
                            frm.save(frm.doc.docstatus === 1 ? 'Update' : 'Save')
                                .then(() => { d.hide(); do_print(); });
                        } else {
                            d.hide();
                            do_print();
                        }
                    },
                    secondary_action_label: __('Edit Bank Master'),
                    secondary_action() {
                        if (b.bank_account) {
                            frappe.set_route('Form', 'Bank Account', b.bank_account);
                        } else {
                            frappe.set_route('List', 'Bank Account');
                        }
                    }
                });

                const rows = [
                    [__('Bank Name'), b.bank_name || miss],
                    [__('A/c No.'), b.account_no || miss],
                    [__('Branch & IFS Code'), b.branch || miss]
                ];
                let html = '<table class="table table-bordered" style="margin-bottom:10px">';
                rows.forEach(x => {
                    html += '<tr><td style="width:42%"><b>' + x[0] + '</b></td><td>' + x[1] + '</td></tr>';
                });
                html += '</table>';
                d.fields_dict.preview.$wrapper.html(html);
                d.fields_dict.hint.$wrapper.html(
                    '<div class="text-muted small" style="margin-top:6px">' +
                    __('Bank Name and Branch Name printed on the invoice come from the Bank Account master fields "Print Bank Name" and "Branch Name (for print)".') +
                    '</div>'
                );
                if (b.bank_account) d.set_value('bank_account', b.bank_account);
                d.show();
            });
        };

        frm.print_doc = verify_bank;

        if (!frm.__sbi_print_menu) {
            frm.page.add_menu_item(__('Print (new tab)'), verify_bank);
            frm.__sbi_print_menu = 1;
        }
    }
});
"""


# ---------------------------------------------------------------- print format


def _read_html():
	path = os.path.join(
		frappe.get_app_path("sbi_projects"), "print_formats", "sbi_tax_invoice.html"
	)
	with open(path, "r", encoding="utf-8") as f:
		return f.read()


def _sync_print_format():
	html = _read_html()
	values = {
		"doc_type": "Sales Invoice",
		"module": "SBI Projects",
		"print_format_type": "Jinja",
		"custom_format": 1,
		"standard": "No",
		"disabled": 0,
		"font_size": 11,
		"margin_top": 10,
		"margin_bottom": 10,
		"margin_left": 10,
		"margin_right": 10,
		"default_print_language": "en",
		"html": html,
	}
	if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
		doc = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
	else:
		doc = frappe.new_doc("Print Format")
		doc.name = PRINT_FORMAT_NAME
	for key, value in values.items():
		doc.set(key, value)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def _sync_client_script():
	if frappe.db.exists("Client Script", CLIENT_SCRIPT_NAME):
		doc = frappe.get_doc("Client Script", CLIENT_SCRIPT_NAME)
	else:
		doc = frappe.new_doc("Client Script")
		doc.name = CLIENT_SCRIPT_NAME
	doc.dt = "Sales Invoice"
	doc.view = "Form"
	doc.enabled = 1
	doc.script = CLIENT_SCRIPT
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------- fields


def _sync_custom_fields():
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "sbi_stage_no",
					"label": "Stage No",
					"fieldtype": "Data",
					"insert_after": "project",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "sbi_stage_name",
					"label": "Stage Name",
					"fieldtype": "Data",
					"insert_after": "sbi_stage_no",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "sbi_gst_filed",
					"label": "GSTR-1 Filed (11th)",
					"fieldtype": "Check",
					"insert_after": "sbi_stage_name",
					"allow_on_submit": 1,
					"no_copy": 1,
				},
				{
					"fieldname": "sbi_gst_paid",
					"label": "GST Paid (21st)",
					"fieldtype": "Check",
					"insert_after": "sbi_gst_filed",
					"allow_on_submit": 1,
					"no_copy": 1,
				},
			],
			"Bank Account": [
				{
					"fieldname": "sbi_print_bank_name",
					"label": "Print Bank Name",
					"fieldtype": "Data",
					"insert_after": "bank",
					"description": "Shown on invoice print, e.g. CITY UNION BANK -CA",
				},
				{
					"fieldname": "sbi_branch_name",
					"label": "Branch Name (for print)",
					"fieldtype": "Data",
					"insert_after": "branch_code",
					"description": "Shown as 'Branch & IFS Code', e.g. CHENNAI CHINMAYA NAGAR",
				},
			],
		},
		ignore_validate=True,
	)


# ---------------------------------------------------------------- properties


def _property_setter(doctype, fieldname, prop, value, prop_type="Data"):
	filters = {
		"doc_type": doctype,
		"property": prop,
		"doctype_or_field": "DocField" if fieldname else "DocType",
	}
	if fieldname:
		filters["field_name"] = fieldname

	name = frappe.db.get_value("Property Setter", filters, "name")
	if name:
		frappe.db.set_value("Property Setter", name, "value", value)
		return

	ps = frappe.new_doc("Property Setter")
	ps.doctype_or_field = "DocField" if fieldname else "DocType"
	ps.doc_type = doctype
	if fieldname:
		ps.field_name = fieldname
	ps.property = prop
	ps.property_type = prop_type
	ps.value = value
	ps.flags.ignore_permissions = True
	ps.insert(ignore_permissions=True)


def _sync_properties():
	# custom naming series options
	_property_setter("Sales Order", "naming_series", "options", SO_SERIES, "Text")
	_property_setter("Sales Invoice", "naming_series", "options", SI_SERIES, "Text")

	# allow the document name to be edited / renamed
	_property_setter("Sales Order", None, "allow_rename", "1", "Check")
	_property_setter("Sales Invoice", None, "allow_rename", "1", "Check")

	# let the bank account be corrected after submit (needed by the print dialog)
	_property_setter("Sales Invoice", "company_bank_account", "allow_on_submit", "1", "Check")

	# show the document ID as the first (subject) column in list views
	_property_setter("Sales Order", None, "title_field", "name", "Data")
	_property_setter("Sales Invoice", None, "title_field", "name", "Data")


# ---------------------------------------------------------------- list views


SO_LIST_FIELDS = [
	{"fieldname": "customer_name", "label": "Customer Name"},
	{"fieldname": "project", "label": "Project"},
	{"fieldname": "grand_total", "label": "Grand Total"},
	{"fieldname": "status", "label": "Status"},
]

SI_LIST_FIELDS = [
	{"fieldname": "customer_name", "label": "Customer Name"},
	{"fieldname": "project", "label": "Project"},
	{"fieldname": "sbi_stage_no", "label": "Stage No"},
	{"fieldname": "net_total", "label": "Taxable Value"},
	{"fieldname": "status", "label": "Status"},
	{"fieldname": "total_taxes_and_charges", "label": "GST Total"},
	{"fieldname": "sbi_gst_filed", "label": "GSTR-1 Filed (11th)"},
	{"fieldname": "sbi_gst_paid", "label": "GST Paid (21st)"},
]


def _sync_list_view(doctype, fields):
	if frappe.db.exists("List View Settings", doctype):
		doc = frappe.get_doc("List View Settings", doctype)
	else:
		doc = frappe.new_doc("List View Settings")
		doc.name = doctype
	doc.fields = json.dumps(fields)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------- entry point


def sync_print_formats():
	"""Idempotent. Wired to after_migrate."""
	steps = (
		("custom fields", _sync_custom_fields),
		("properties", _sync_properties),
		("print format", _sync_print_format),
		("client script", _sync_client_script),
	)
	for label, fn in steps:
		try:
			fn()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "SBI print setup: " + label)

	for doctype, fields in (
		("Sales Order", SO_LIST_FIELDS),
		("Sales Invoice", SI_LIST_FIELDS),
	):
		try:
			_sync_list_view(doctype, fields)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "SBI list view: " + doctype)

	frappe.clear_cache()
	frappe.db.commit()
