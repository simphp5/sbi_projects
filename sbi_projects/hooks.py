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
    "Sales Order": "public/js/sales_order.js",
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
    "Quotation": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
    "Sales Order": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
    "Sales Invoice": {
        "validate": "sbi_projects.sbi_projects.project_hooks.sync_payment_schedule_stage",
    },
    "Project": {
        "after_insert": [
            "sbi_projects.sbi_projects.project_hooks.build_project_stages",
            "sbi_projects.sbi_projects.project_hooks.create_site_masters",
        ],
    },
    "Lead": {
        "validate": "sbi_projects.sbi_projects.lead_hooks.validate_lead",
    },
    "Opportunity": {
        "validate": "sbi_projects.sbi_projects.crm_hooks.pull_enquiry_to_opportunity",
    },
    "Quotation": {
        "validate": "sbi_projects.sbi_projects.crm_hooks.pull_enquiry_to_quotation",
    },
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

