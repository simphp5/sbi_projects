import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

PRINT_FORMAT_NAME = "SBI Tax Invoice"
CLIENT_SCRIPT_NAME = "SBI Sales Invoice Print New Tab"

PURCHASE_FORMATS = (
	("SBI Purchase Order", "Purchase Order", "sbi_purchase.html"),
	("SBI Purchase Invoice", "Purchase Invoice", "sbi_purchase.html"),
)

PURCHASE_SCRIPT = """
frappe.ui.form.on('__DOCTYPE__', {
    refresh(frm) {
        if (frm.is_new()) return;

        const do_print = () => {
            const p = [
                'doctype=' + encodeURIComponent(frm.doc.doctype),
                'name=' + encodeURIComponent(frm.doc.name),
                'format=' + encodeURIComponent('__FORMAT__'),
                'no_letterhead=1',
                '_lang=en'
            ].join('&');
            window.open('/printview?' + p, '_blank');
        };

        const contact_fields = (state) => ([
            {
                fieldtype: 'Section Break', label: __('Company Contact (printed in the header)')
            },
            {
                fieldtype: 'Data', fieldname: 'company_phone', label: __('Phone'),
                read_only: state.can_edit ? 0 : 1
            },
            {
                fieldtype: 'Column Break'
            },
            {
                fieldtype: 'Data', fieldname: 'company_email', label: __('Email'),
                options: 'Email', read_only: state.can_edit ? 0 : 1
            },
            {
                fieldtype: 'HTML', fieldname: 'contact_note'
            },
            { fieldtype: 'Section Break' }
        ]);

        const contact_note_html = (state) => {
            if (!state.can_edit) {
                return '<div class="text-muted small">' +
                    __('You do not have permission to edit the Company master.') + '</div>';
            }
            const missing = [];
            if (!state.email) missing.push(__('Email'));
            if (!state.phone) missing.push(__('Phone'));
            if (missing.length) {
                return '<div style="color:#BE1E2D" class="small">' +
                    __('Not set: ') + missing.join(', ') +
                    __(' - fill it in and it will be saved to the Company master.') + '</div>';
            }
            return '<div class="text-muted small">' +
                __('Edits here are saved to the Company master and its address.') + '</div>';
        };

        const save_contact = (state, v) => {
            const email = (v.company_email || '').trim();
            const phone = (v.company_phone || '').trim();
            if (!state.can_edit) return Promise.resolve();
            if (email === (state.email || '') && phone === (state.phone || '')) {
                return Promise.resolve();
            }
            return frappe.call({
                method: 'sbi_projects.utils.print_helpers.save_company_contact',
                args: {
                    company: state.company, email: email,
                    phone: phone, address: state.address
                }
            });
        };

        const render_preview = (d, text) => {
            const lines = (text || '').split('\\n').map(x => x.trim()).filter(x => x.length);
            let html;
            if (lines.length) {
                html = '<ol style="margin:0 0 0 18px;padding:0;font-size:12px">' +
                    lines.map(x => '<li style="margin-bottom:3px">' +
                        frappe.utils.escape_html(x) + '</li>').join('') + '</ol>';
            } else {
                html = '<div style="color:#BE1E2D">' +
                    __('No terms set - this section will print blank.') + '</div>';
            }
            d.fields_dict.preview.$wrapper.html(html);
        };

        const verify_before_print = () => {
            Promise.all([
                frappe.call({
                    method: 'sbi_projects.utils.print_helpers.terms_for',
                    args: { doctype: frm.doc.doctype, name: frm.doc.name }
                }),
                frappe.call({
                    method: 'sbi_projects.utils.print_helpers.contact_for',
                    args: { doctype: frm.doc.doctype, name: frm.doc.name }
                })
            ]).then(([tr, cr]) => {
                const t = tr.message || {};
                const state = cr.message || {};

                const d = new frappe.ui.Dialog({
                    title: __('Check Before Printing'),
                    size: 'large',
                    fields: contact_fields(state).concat([
                        {
                            fieldtype: 'Link', fieldname: 'tc_name',
                            label: __('Terms Template'), options: 'Terms and Conditions',
                            onchange() {
                                const v = d.get_value('tc_name');
                                if (!v) return;
                                frappe.call({
                                    method: 'sbi_projects.utils.print_helpers.terms_template',
                                    args: { tc_name: v }
                                }).then(res => {
                                    d.set_value('terms_text', (res.message || {}).text || '');
                                });
                            }
                        },
                        {
                            fieldtype: 'Small Text', fieldname: 'terms_text',
                            label: __('Terms of Purchase - one per line (numbered automatically)'),
                            onchange() { render_preview(d, d.get_value('terms_text')); }
                        },
                        { fieldtype: 'HTML', fieldname: 'preview' }
                    ]),
                    primary_action_label: __('Print'),
                    primary_action(v) {
                        const text = (v.terms_text || '').trim();
                        const terms_changed = text !== (t.text || '').trim() ||
                            (v.tc_name || '') !== (t.tc_name || '');

                        save_contact(state, v).then(() => {
                            if (!terms_changed) { d.hide(); do_print(); return; }
                            if (v.tc_name) frm.set_value('tc_name', v.tc_name);
                            frm.set_value('terms', text);
                            frm.save(frm.doc.docstatus === 1 ? 'Update' : 'Save')
                                .then(() => { d.hide(); do_print(); });
                        });
                    },
                    secondary_action_label: __('Print without changes'),
                    secondary_action() { d.hide(); do_print(); }
                });

                d.show();
                d.set_value('company_email', state.email || '');
                d.set_value('company_phone', state.phone || '');
                d.fields_dict.contact_note.$wrapper.html(contact_note_html(state));
                if (t.tc_name) d.set_value('tc_name', t.tc_name);
                d.set_value('terms_text', t.text || '');
                render_preview(d, t.text || '');
            });
        };

        frm.print_doc = verify_before_print;

        if (!frm.__sbi_print_menu) {
            frm.page.add_menu_item(__('Print (new tab)'), verify_before_print);
            frm.__sbi_print_menu = 1;
        }
    }
});
"""

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

        const contact_fields = (state) => ([
            {
                fieldtype: 'Section Break', label: __('Company Contact (printed in the header)')
            },
            {
                fieldtype: 'Data', fieldname: 'company_phone', label: __('Phone'),
                read_only: state.can_edit ? 0 : 1
            },
            {
                fieldtype: 'Column Break'
            },
            {
                fieldtype: 'Data', fieldname: 'company_email', label: __('Email'),
                options: 'Email', read_only: state.can_edit ? 0 : 1
            },
            {
                fieldtype: 'HTML', fieldname: 'contact_note'
            },
            { fieldtype: 'Section Break' }
        ]);

        const contact_note_html = (state) => {
            if (!state.can_edit) {
                return '<div class="text-muted small">' +
                    __('You do not have permission to edit the Company master.') + '</div>';
            }
            const missing = [];
            if (!state.email) missing.push(__('Email'));
            if (!state.phone) missing.push(__('Phone'));
            if (missing.length) {
                return '<div style="color:#BE1E2D" class="small">' +
                    __('Not set: ') + missing.join(', ') +
                    __(' - fill it in and it will be saved to the Company master.') + '</div>';
            }
            return '<div class="text-muted small">' +
                __('Edits here are saved to the Company master and its address.') + '</div>';
        };

        const save_contact = (state, v) => {
            const email = (v.company_email || '').trim();
            const phone = (v.company_phone || '').trim();
            if (!state.can_edit) return Promise.resolve();
            if (email === (state.email || '') && phone === (state.phone || '')) {
                return Promise.resolve();
            }
            return frappe.call({
                method: 'sbi_projects.utils.print_helpers.save_company_contact',
                args: {
                    company: state.company, email: email,
                    phone: phone, address: state.address
                }
            });
        };

        const verify_before_print = () => {
            Promise.all([
                frappe.call({
                    method: 'sbi_projects.utils.print_helpers.bank_details_for',
                    args: { invoice: frm.doc.name }
                }),
                frappe.call({
                    method: 'sbi_projects.utils.print_helpers.contact_for',
                    args: { doctype: frm.doc.doctype, name: frm.doc.name }
                })
            ]).then(([br, cr]) => {
                const b = br.message || {};
                const state = cr.message || {};
                const miss = '<span style="color:#BE1E2D">' + __('Not set') + '</span>';

                const d = new frappe.ui.Dialog({
                    title: __('Check Before Printing'),
                    size: 'large',
                    fields: contact_fields(state).concat([
                        { fieldtype: 'HTML', fieldname: 'preview' },
                        {
                            fieldtype: 'Link', fieldname: 'bank_account',
                            label: __('Bank Account'), options: 'Bank Account'
                        },
                        { fieldtype: 'HTML', fieldname: 'hint' }
                    ]),
                    primary_action_label: __('Print'),
                    primary_action(v) {
                        save_contact(state, v).then(() => {
                            if (v.bank_account && v.bank_account !== b.bank_account) {
                                frm.set_value('company_bank_account', v.bank_account);
                                frm.save(frm.doc.docstatus === 1 ? 'Update' : 'Save')
                                    .then(() => { d.hide(); do_print(); });
                            } else {
                                d.hide();
                                do_print();
                            }
                        });
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

                d.show();
                d.set_value('company_email', state.email || '');
                d.set_value('company_phone', state.phone || '');
                d.fields_dict.contact_note.$wrapper.html(contact_note_html(state));
                d.fields_dict.preview.$wrapper.html(html);
                d.fields_dict.hint.$wrapper.html(
                    '<div class="text-muted small" style="margin-top:6px">' +
                    __('Bank Name and Branch Name come from the Bank Account master fields "Print Bank Name" and "Branch Name (for print)".') +
                    '</div>'
                );
                if (b.bank_account) d.set_value('bank_account', b.bank_account);
            });
        };

        frm.print_doc = verify_before_print;

        if (!frm.__sbi_print_menu) {
            frm.page.add_menu_item(__('Print (new tab)'), verify_before_print);
            frm.__sbi_print_menu = 1;
        }
    }
});
"""


# ---------------------------------------------------------------- print format


def _read_html(filename="sbi_tax_invoice.html"):
	path = os.path.join(frappe.get_app_path("sbi_projects"), "print_formats", filename)
	with open(path, "r", encoding="utf-8") as f:
		return f.read()


def _upsert_print_format(name, doctype, filename):
	values = {
		"doc_type": doctype,
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
		"html": _read_html(filename),
	}
	if frappe.db.exists("Print Format", name):
		doc = frappe.get_doc("Print Format", name)
	else:
		doc = frappe.new_doc("Print Format")
		doc.name = name
	for key, value in values.items():
		doc.set(key, value)
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def _upsert_client_script(name, doctype, script):
	if frappe.db.exists("Client Script", name):
		doc = frappe.get_doc("Client Script", name)
	else:
		doc = frappe.new_doc("Client Script")
		doc.name = name
	doc.dt = doctype
	doc.view = "Form"
	doc.enabled = 1
	doc.script = script
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def _sync_purchase_formats():
	for name, doctype, filename in PURCHASE_FORMATS:
		_upsert_print_format(name, doctype, filename)
		_upsert_client_script(
			"SBI %s Print New Tab" % doctype,
			doctype,
			PURCHASE_SCRIPT.replace("__DOCTYPE__", doctype).replace("__FORMAT__", name),
		)
		_property_setter(doctype, None, "default_print_format", name, "Data")


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
				{
					"fieldname": "sbi_allow_duplicate_stage",
					"label": "Allow Duplicate Stage Billing",
					"fieldtype": "Check",
					"insert_after": "sbi_gst_paid",
					"no_copy": 1,
					"description": "Tick only when this stage is deliberately part-billed again",
				},
			],
			"Item Group": [
				{
					"fieldname": "sbi_default_hsn",
					"label": "Default HSN/SAC",
					"fieldtype": "Link",
					"options": "GST HSN Code",
					"insert_after": "parent_item_group",
					"description": "New items in this group inherit this HSN/SAC automatically",
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


def _remove_property_setter(doctype, fieldname, prop):
	filters = {
		"doc_type": doctype,
		"property": prop,
		"doctype_or_field": "DocField" if fieldname else "DocType",
	}
	if fieldname:
		filters["field_name"] = fieldname
	for name in frappe.get_all("Property Setter", filters=filters, pluck="name"):
		frappe.delete_doc("Property Setter", name, force=True, ignore_permissions=True)


def _sync_properties():
	# custom naming series options
	_property_setter("Sales Order", "naming_series", "options", SO_SERIES, "Text")
	_property_setter("Sales Invoice", "naming_series", "options", SI_SERIES, "Text")

	# allow the document name to be edited / renamed
	_property_setter("Sales Order", None, "allow_rename", "1", "Check")
	_property_setter("Sales Invoice", None, "allow_rename", "1", "Check")

	# let the bank account be corrected after submit (needed by the print dialog)
	_property_setter("Sales Invoice", "company_bank_account", "allow_on_submit", "1", "Check")

	# let terms be corrected after submit (needed by the purchase print dialog)
	for _dt in ("Purchase Order", "Purchase Invoice"):
		_property_setter(_dt, "terms", "allow_on_submit", "1", "Check")
		_property_setter(_dt, "tc_name", "allow_on_submit", "1", "Check")

	# NOTE: title_field must NOT be forced to "name" - it breaks the list query
	# and the list comes back empty. Clean up any left over from an earlier build.
	_remove_property_setter("Sales Order", None, "title_field")
	_remove_property_setter("Sales Invoice", None, "title_field")


# ---------------------------------------------------------------- list views


SO_LIST_FIELDS = [
	{"fieldname": "name", "label": "ID"},
	{"fieldname": "customer_name", "label": "Customer Name"},
	{"fieldname": "project", "label": "Project"},
	{"fieldname": "grand_total", "label": "Grand Total"},
	{"fieldname": "status", "label": "Status"},
]

SI_LIST_FIELDS = [
	{"fieldname": "name", "label": "ID"},
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


@frappe.whitelist()
def sync_print_formats():
	"""Idempotent. Wired to after_migrate; also callable manually to force a re-sync."""
	if frappe.session and frappe.session.user not in ("Administrator", None):
		frappe.only_for("System Manager")
	steps = (
		("custom fields", _sync_custom_fields),
		("properties", _sync_properties),
		("print format", _sync_print_format),
		("client script", _sync_client_script),
		("purchase formats", _sync_purchase_formats),
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
