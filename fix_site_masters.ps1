# fix_site_masters.ps1  --  appends create_site_masters to project_hooks.py
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$target = "sbi_projects\sbi_projects\project_hooks.py"

if (-not (Test-Path $target)) { Write-Error "Not found: $target. Are you in sbi_projects_live?"; exit 1 }
if (Select-String -Path $target -Pattern "def create_site_masters" -Quiet) {
    Write-Host "Already present - nothing to do." -ForegroundColor Yellow; exit 0
}

$code = @'


# ---------------------------------------------------------------------------
# Site masters: auto-create Cost Center + Warehouse for every Project (= Site)
# ---------------------------------------------------------------------------

def create_site_masters(doc, method=None):
    """Project.after_insert -- provision site Cost Center and Warehouse.

    Never raises: a failure here must not block Project creation.
    Idempotent: safe to re-run on any Project.
    """
    try:
        _provision_site_masters(doc)
    except Exception:
        frappe.log_error(
            title="create_site_masters failed: {0}".format(doc.name),
            message=frappe.get_traceback(),
        )
        frappe.msgprint(
            "Site Cost Center / Warehouse could not be created automatically. "
            "The project was saved.",
            title="Site Setup Incomplete",
            indicator="orange",
        )


def _provision_site_masters(doc):
    company = doc.company or frappe.defaults.get_user_default("Company")
    if not company:
        return

    abbr = frappe.get_cached_value("Company", company, "abbr")
    label = (doc.project_name or doc.name).strip()[:120]

    cc = _ensure_site_cost_center(company, abbr, label)
    wh = _ensure_site_warehouse(company, abbr, label)

    _set_if_field_exists(doc, "custom_site_cost_center", cc)
    _set_if_field_exists(doc, "custom_site_warehouse", wh)
    if not doc.get("cost_center"):
        _set_if_field_exists(doc, "cost_center", cc)


def _ensure_site_cost_center(company, abbr, label):
    """Create '<label> - <abbr>' under a 'Sites - <abbr>' group."""
    target = "{0} - {1}".format(label, abbr)
    if frappe.db.exists("Cost Center", target):
        return target

    parent = _ensure_sites_cc_group(company, abbr)
    cc = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": label,
        "company": company,
        "parent_cost_center": parent,
        "is_group": 0,
    }).insert(ignore_permissions=True)
    return cc.name


def _ensure_sites_cc_group(company, abbr):
    group = "Sites - {0}".format(abbr)
    if frappe.db.exists("Cost Center", group):
        return group

    root = frappe.db.get_value(
        "Cost Center",
        {"company": company, "is_group": 1,
         "parent_cost_center": ("in", ("", None))},
        "name",
    ) or frappe.db.get_value(
        "Cost Center", {"company": company, "is_group": 1}, "name"
    )
    if not root:
        frappe.throw("No group Cost Center found for company {0}".format(company))

    doc = frappe.get_doc({
        "doctype": "Cost Center",
        "cost_center_name": "Sites",
        "company": company,
        "parent_cost_center": root,
        "is_group": 1,
    }).insert(ignore_permissions=True)
    return doc.name


def _ensure_site_warehouse(company, abbr, label):
    target = "{0} - {1}".format(label, abbr)
    if frappe.db.exists("Warehouse", target):
        return target

    conventional = "All Warehouses - {0}".format(abbr)
    parent = conventional if frappe.db.exists("Warehouse", conventional) else \
        frappe.db.get_value(
            "Warehouse",
            {"company": company, "is_group": 1,
             "parent_warehouse": ("in", ("", None))},
            "name",
        )

    wh = frappe.get_doc({
        "doctype": "Warehouse",
        "warehouse_name": label,
        "company": company,
        "parent_warehouse": parent,
        "is_group": 0,
    }).insert(ignore_permissions=True)
    return wh.name


def _set_if_field_exists(doc, fieldname, value):
    """Write only if the field actually exists on Project -- avoids errors
    when custom fields have not been installed yet."""
    if not value:
        return
    if not doc.meta.has_field(fieldname):
        return
    doc.db_set(fieldname, value, update_modified=False)


@frappe.whitelist()
def backfill_site_masters(project=None):
    """Repair Projects created while this hook was broken."""
    frappe.only_for("System Manager")
    names = [project] if project else frappe.get_all("Project", pluck="name")
    ok, failed = [], []
    for name in names:
        try:
            _provision_site_masters(frappe.get_doc("Project", name))
            ok.append(name)
        except Exception:
            failed.append(name)
            frappe.log_error(title="backfill failed: {0}".format(name),
                             message=frappe.get_traceback())
    frappe.db.commit()
    return {"ok": len(ok), "failed": failed}
'@

Add-Content -Path $target -Value $code -Encoding UTF8
Write-Host "Appended create_site_masters to $target" -ForegroundColor Green

# verify
Write-Host ""
Write-Host "-- functions now in file --" -ForegroundColor Cyan
Select-String -Path $target -Pattern "^def " | ForEach-Object { $_.Line }
