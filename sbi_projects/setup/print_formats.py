import os

import frappe

PRINT_FORMAT_NAME = "SBI Tax Invoice"
CLIENT_SCRIPT_NAME = "SBI Sales Invoice Print New Tab"

CLIENT_SCRIPT = """
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        if (frm.is_new()) return;

        const sbi_open_print = () => {
            const params = [
                'doctype=' + encodeURIComponent(frm.doc.doctype),
                'name=' + encodeURIComponent(frm.doc.name),
                'format=' + encodeURIComponent('SBI Tax Invoice'),
                'no_letterhead=1',
                '_lang=en'
            ].join('&');
            window.open('/printview?' + params, '_blank');
        };

        // core Print menu item / Ctrl+P -> new tab
        frm.print_doc = sbi_open_print;

        if (!frm.__sbi_print_menu) {
            frm.page.add_menu_item(__('Print (new tab)'), sbi_open_print);
            frm.__sbi_print_menu = 1;
        }
    }
});
"""


def _read_html():
	path = os.path.join(
		frappe.get_app_path("sbi_projects"), "print_formats", "sbi_tax_invoice.html"
	)
	with open(path, "r", encoding="utf-8") as f:
		return f.read()


def sync_print_formats():
	"""Idempotent: create or update the SBI Tax Invoice print format + print button."""
	try:
		html = _read_html()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "SBI: print format html not found")
		return

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

	_sync_client_script()
	_set_default_print_format()
	frappe.db.commit()


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


def _set_default_print_format():
	name = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "default_print_format", "doctype_or_field": "DocType"},
		"name",
	)
	if name:
		frappe.db.set_value("Property Setter", name, "value", PRINT_FORMAT_NAME)
		return

	ps = frappe.new_doc("Property Setter")
	ps.doctype_or_field = "DocType"
	ps.doc_type = "Sales Invoice"
	ps.property = "default_print_format"
	ps.property_type = "Data"
	ps.value = PRINT_FORMAT_NAME
	ps.flags.ignore_permissions = True
	ps.insert(ignore_permissions=True)
