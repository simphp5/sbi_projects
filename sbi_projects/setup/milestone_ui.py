"""Milestone billing UI.

Two client scripts, both built on the existing milestone_billing API:

  Sales Order   - the Payment Schedule grid shows a Sales Invoice column, and
                  clicking an invoice opens it in a new tab.
  Sales Invoice - a "Bill a Stage" button in the list view: pick a Sales Order,
                  see every stage with its invoice or a Create button.
"""

import frappe

SO_SCRIPT_NAME = "SBI Sales Order Milestone Invoice Column"
SI_SCRIPT_NAME = "SBI Sales Invoice Bill a Stage"

SO_SCRIPT = """
frappe.ui.form.on('Sales Order', {
    refresh() {
        if (window.__sbiMilestoneLink) return;
        window.__sbiMilestoneLink = 1;

        $(document).on('click',
            '[data-fieldname="sbi_sales_invoice"] a, [data-fieldname="sbi_sales_invoice"] .btn-open',
            function (e) {
                let href = this.getAttribute('href') || '';
                if (!href) {
                    const cell = this.closest('[data-fieldname="sbi_sales_invoice"]');
                    const name = cell ? (cell.textContent || '').trim() : '';
                    if (!name) return;
                    href = '/app/sales-invoice/' + encodeURIComponent(name);
                }
                e.preventDefault();
                e.stopPropagation();
                window.open(href, '_blank');
            }
        );
    }
});
"""

SI_SCRIPT = """
frappe.listview_settings['Sales Invoice'] = frappe.listview_settings['Sales Invoice'] || {};

(function () {
    const prior = frappe.listview_settings['Sales Invoice'].onload;

    frappe.listview_settings['Sales Invoice'].onload = function (listview) {
        if (prior) prior(listview);
        listview.page.add_inner_button(__('Bill a Stage'), () => sbiStageDialog());
    };
})();

function sbiStageDialog(preset) {
    const d = new frappe.ui.Dialog({
        title: __('Bill a Stage'),
        size: 'large',
        fields: [
            {
                fieldtype: 'Link', fieldname: 'sales_order', label: __('Sales Order'),
                options: 'Sales Order', reqd: 1,
                get_query: () => ({ filters: { docstatus: 1 } }),
                onchange() { sbiLoadStages(d); }
            },
            { fieldtype: 'HTML', fieldname: 'stages' }
        ]
    });

    d.show();
    d.$wrapper.find('.modal-dialog').css('max-width', '860px');
    d.fields_dict.stages.$wrapper.html(
        '<div class="text-muted" style="padding:14px 2px">' +
        __('Pick a Sales Order to see its stages.') + '</div>');

    if (preset) d.set_value('sales_order', preset);
    return d;
}

function sbiLoadStages(d) {
    const so = d.get_value('sales_order');
    const box = d.fields_dict.stages.$wrapper;
    if (!so) { box.html(''); return; }

    box.html('<div class="text-muted" style="padding:14px 2px">' + __('Loading...') + '</div>');

    frappe.call({
        method: 'sbi_projects.api.milestone_billing.get_payment_terms',
        args: { sales_order: so }
    }).then(r => {
        const data = (r && r.message) || {};
        const rows = data.rows || [];
        if (!rows.length) {
            box.html('<div class="text-muted" style="padding:14px 2px">' +
                     __('This Sales Order has no payment schedule.') + '</div>');
            return;
        }
        box.html(sbiStageTable(rows, data.project));
        box.find('[data-sbi-create]').on('click', function () {
            sbiCreate(d, so, this.getAttribute('data-sbi-create'), this);
        });
    }).catch(() => {
        box.html('<div style="color:#BE1E2D;padding:14px 2px">' +
                 __('Could not read the payment schedule.') + '</div>');
    });
}

function sbiStageTable(rows, project) {
    const esc = frappe.utils.escape_html;
    let html = '';

    if (project) {
        html += '<div class="text-muted" style="margin-bottom:8px">' +
                __('Project') + ': <b>' + esc(project) + '</b></div>';
    }

    html += '<table class="table table-bordered" style="margin:0;font-size:13px">' +
            '<thead><tr>' +
            '<th style="width:44px">#</th>' +
            '<th>' + __('Stage') + '</th>' +
            '<th style="width:70px;text-align:right">%</th>' +
            '<th style="width:130px;text-align:right">' + __('Amount') + '</th>' +
            '<th style="width:210px">' + __('Sales Invoice') + '</th>' +
            '</tr></thead><tbody>';

    rows.forEach(row => {
        const stage = row.stage || row.payment_term || ('Term ' + row.idx);
        let cell;

        if (row.sales_invoice) {
            cell = '<a href="/app/sales-invoice/' + encodeURIComponent(row.sales_invoice) +
                   '" target="_blank" rel="noopener">' + esc(row.sales_invoice) + '</a>';
            if (row.status) {
                cell += '<div class="text-muted" style="font-size:11.5px">' + esc(row.status) + '</div>';
            }
        } else {
            cell = '<button class="btn btn-xs btn-primary" data-sbi-create="' +
                   esc(row.row_name) + '">' + __('Create') + '</button>';
        }

        html += '<tr>' +
                '<td>' + row.idx + '</td>' +
                '<td>' + esc(stage) + '</td>' +
                '<td style="text-align:right">' + (row.invoice_portion || 0) + '</td>' +
                '<td style="text-align:right">' + format_currency(row.payment_amount) + '</td>' +
                '<td>' + cell + '</td>' +
                '</tr>';
    });

    return html + '</tbody></table>';
}

function sbiCreate(d, so, rowName, btn) {
    btn.disabled = true;
    btn.textContent = __('Creating...');

    frappe.call({
        method: 'sbi_projects.api.milestone_billing.make_milestone_invoice',
        args: {
            sales_order: so,
            selected_rows: JSON.stringify([rowName]),
            billing_mode: 'Rate Scaled',
            split: 'combined'
        },
        freeze: true,
        freeze_message: __('Creating the invoice...')
    }).then(r => {
        const names = ((r && r.message) || {}).invoices || [];
        if (!names.length) {
            frappe.msgprint(__('No invoice was created.'));
            btn.disabled = false;
            btn.textContent = __('Create');
            return;
        }
        window.open('/app/sales-invoice/' + encodeURIComponent(names[0]), '_blank');
        sbiLoadStages(d);
    }).catch(() => {
        btn.disabled = false;
        btn.textContent = __('Create');
    });
}
"""


def _upsert(name, dt, view, script):
    if frappe.db.exists("Client Script", name):
        doc = frappe.get_doc("Client Script", name)
    else:
        doc = frappe.new_doc("Client Script")
        doc.name = name
    doc.dt = dt
    doc.view = view
    doc.enabled = 1
    doc.script = script
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)


def _property_setter(doctype, fieldname, prop, value, prop_type="Data"):
    filters = {
        "doc_type": doctype,
        "property": prop,
        "doctype_or_field": "DocField",
        "field_name": fieldname,
    }
    name = frappe.db.get_value("Property Setter", filters, "name")
    if name:
        frappe.db.set_value("Property Setter", name, "value", value)
        return

    ps = frappe.new_doc("Property Setter")
    ps.doctype_or_field = "DocField"
    ps.doc_type = doctype
    ps.field_name = fieldname
    ps.property = prop
    ps.property_type = prop_type
    ps.value = value
    ps.flags.ignore_permissions = True
    ps.insert(ignore_permissions=True)


def sync_milestone_ui():
    """Idempotent. Called from the after_migrate setup run."""
    _upsert(SO_SCRIPT_NAME, "Sales Order", "Form", SO_SCRIPT)
    _upsert(SI_SCRIPT_NAME, "Sales Invoice", "List", SI_SCRIPT)

    # show the invoice against each stage in the Sales Order grid
    meta = frappe.get_meta("Payment Schedule")
    if meta.has_field("sbi_sales_invoice"):
        _property_setter("Payment Schedule", "sbi_sales_invoice", "in_list_view", "1", "Check")
        _property_setter("Payment Schedule", "sbi_sales_invoice", "columns", "2", "Int")
        _property_setter("Payment Schedule", "sbi_sales_invoice", "read_only", "1", "Check")
