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
doctype_js = {
    "Project": "public/js/project.js",
}

# ------------------------------------------------------------------
# Installation
# ------------------------------------------------------------------
after_install = "sbi_projects.setup.install.after_install"

# ------------------------------------------------------------------
# Document Events
# ------------------------------------------------------------------
doc_events = {
    "Project": {
        "after_insert": "sbi_projects.sbi_projects.doctype.sbi_project_template.sbi_project_template.create_tasks_from_template",
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
]
