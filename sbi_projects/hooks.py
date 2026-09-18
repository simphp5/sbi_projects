app_name = "sbi_projects"
app_title = "SBI Projects"
app_publisher = "Velmaska"
app_description = "Site Management, Project Templates and BOQ for Shiv Bharat Infrastructures"
app_email = "info@velmaska.com"
app_license = "mit"
required_apps = ["erpnext"]
# ------------------------------------------------------------------
# Includes
# ------------------------------------------------------------------
app_include_css = "/assets/sbi_projects/css/sbi_branding.css"
doctype_js = {
    "Project": "public/js/project.js",
    "Sales Order": ["public/js/sales_order.js", "public/js/sales_order_milestone.js"],
    "Lead": "public/js/lead.js",
}
# ------------------------------------------------------------------
# Installation
# ------------------------------------------------------------------
after_install = "sbi_projects.setup.install.after_install"
# Re-run on every deploy so new custom fields / seeds land without a
# fresh install. Every step is idempotent.
after_migrate = "sbi_projects.setup.install.after_install"
# ------------------------------------------------------------------
# Document Events
# ------------------------------------------------------------------
doc_events = {
    "Daily Work Log": {
        "on_update": "sbi_projects.sbi_projects.work_log_hooks.maybe_post_to_gl",
        "on_update_after_submit": "sbi_projects.sbi_projects.work_log_hooks.maybe_post_to_gl",
    },
    "Quotation": {
        "validate": [
            "sbi_projects.sbi_projects.crm_hooks.pull_enquiry_to_quotation",
            "sbi_projects.sbi_projects.payment_terms_net.set_payment_terms_on_net",
        ]
    },
    "Sales Order": {
        "validate": [
            "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
            "sbi_projects.sbi_projects.payment_terms_net.set_payment_terms_on_net",
        ]
    },
    "Sales Invoice": {
        "validate": [
            "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
            "sbi_projects.sbi_projects.payment_terms_net.set_payment_terms_on_net",
        ],
        "on_submit": "sbi_projects.api.milestone_billing.mark_terms_billed",
        "on_cancel": "sbi_projects.api.milestone_billing.unmark_terms_billed",
    },
    "Payment Entry": {
        "on_submit": "sbi_projects.api.payment_hooks.update_received_on_submit",
        "on_cancel": "sbi_projects.api.payment_hooks.update_received_on_cancel",
    },
    "Project": {
        "after_insert": [
            "sbi_projects.sbi_projects.project_hooks.build_project_stages",
            "sbi_projects.sbi_projects.project_hooks.create_site_masters",
            "sbi_projects.sbi_projects.so_fetch.build_stages_if_new",
        ],
        "validate": "sbi_projects.sbi_projects.so_fetch.sync_from_sales_order",
    },
    "Lead": {"validate": "sbi_projects.sbi_projects.lead_hooks.validate_lead"},
    "Opportunity": {"validate": "sbi_projects.sbi_projects.crm_hooks.pull_enquiry_to_opportunity"},
}
# ------------------------------------------------------------------
# Fixtures  (exported masters + custom fields travel with git)
# ------------------------------------------------------------------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["name", "like", "Project-sbi_%"]],
    },
    {
        "dt": "Project Stage",
    },
    {
        "dt": "Lead Stage",
    },
    {
        "dt": "Lead Activity Type",
    },
]

# ---------------------------------------------------------------------------
# SBI: open the print view in a new browser tab
# ---------------------------------------------------------------------------
app_include_js = "/assets/sbi_projects/js/sbi_print_newtab.js"


# --- SBI print format wiring (auto-added) ---
try:
    jinja
except NameError:
    jinja = {}

if not isinstance(jinja, dict):
    jinja = {}

jinja.setdefault("methods", [])
for _sbi_m in [
    "sbi_projects.utils.print_helpers.invoice_ctx",
    "sbi_projects.utils.print_helpers.stage_line",
    "sbi_projects.utils.print_helpers.hsn_summary",
    "sbi_projects.utils.print_helpers.in_words",
    "sbi_projects.utils.print_helpers.amt",
    "sbi_projects.utils.print_helpers.pct",
    "sbi_projects.utils.print_helpers.fdate",
    "sbi_projects.utils.print_helpers.qr_base64",
]:
    if _sbi_m not in jinja["methods"]:
        jinja["methods"].append(_sbi_m)

try:
    after_migrate
except NameError:
    after_migrate = []

if isinstance(after_migrate, str):
    after_migrate = [after_migrate]

if "sbi_projects.setup.print_formats.sync_print_formats" not in after_migrate:
    after_migrate = list(after_migrate) + [
        "sbi_projects.setup.print_formats.sync_print_formats"
    ]


# --- SBI sales naming wiring (auto-added) ---
try:
    doc_events
except NameError:
    doc_events = {}

if not isinstance(doc_events, dict):
    doc_events = {}


def _sbi_add_event(_dt, _event, _method):
    _entry = doc_events.setdefault(_dt, {})
    _existing = _entry.get(_event)
    if _existing is None:
        _entry[_event] = _method
    elif isinstance(_existing, str):
        if _existing != _method:
            _entry[_event] = [_existing, _method]
    elif isinstance(_existing, (list, tuple)):
        _existing = list(_existing)
        if _method not in _existing:
            _existing.append(_method)
        _entry[_event] = _existing


_sbi_add_event("Sales Order", "autoname", "sbi_projects.setup.sales_naming.sales_order_autoname")
_sbi_add_event("Sales Invoice", "autoname", "sbi_projects.setup.sales_naming.sales_invoice_autoname")
_sbi_add_event("Sales Invoice", "validate", "sbi_projects.setup.sales_naming.sales_invoice_validate")


# --- SBI purchase print wiring (auto-added) ---
try:
    jinja
except NameError:
    jinja = {}

if not isinstance(jinja, dict):
    jinja = {}

jinja.setdefault("methods", [])
for _sbi_pm in [
    "sbi_projects.utils.print_helpers.purchase_ctx",
    "sbi_projects.utils.print_helpers.fdate",
]:
    if _sbi_pm not in jinja["methods"]:
        jinja["methods"].append(_sbi_pm)


# --- SBI item HSN wiring (auto-added) ---
try:
    doc_events
except NameError:
    doc_events = {}

if not isinstance(doc_events, dict):
    doc_events = {}


def _sbi_hsn_event(_dt, _event, _method):
    _entry = doc_events.setdefault(_dt, {})
    _existing = _entry.get(_event)
    if _existing is None:
        _entry[_event] = _method
    elif isinstance(_existing, str):
        if _existing != _method:
            _entry[_event] = [_existing, _method]
    elif isinstance(_existing, (list, tuple)):
        _existing = list(_existing)
        if _method not in _existing:
            _existing.append(_method)
        _entry[_event] = _existing


_sbi_hsn_event("Item", "validate", "sbi_projects.setup.item_hsn.item_validate")


# --- SBI project warehouse wiring (auto-added) ---
try:
    doc_events
except NameError:
    doc_events = {}

if not isinstance(doc_events, dict):
    doc_events = {}


def _sbi_pw_event(_dt, _event, _method):
    _entry = doc_events.setdefault(_dt, {})
    _existing = _entry.get(_event)
    if _existing is None:
        _entry[_event] = _method
    elif isinstance(_existing, str):
        if _existing != _method:
            _entry[_event] = [_existing, _method]
    elif isinstance(_existing, (list, tuple)):
        _existing = list(_existing)
        if _method not in _existing:
            _existing.append(_method)
        _entry[_event] = _existing


_sbi_pw_event(
    "Project", "after_insert",
    "sbi_projects.setup.project_warehouse.project_after_insert",
)
_sbi_pw_event(
    "Project", "on_update",
    "sbi_projects.setup.project_warehouse.project_on_update",
)
