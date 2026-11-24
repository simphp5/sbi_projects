# =====================================================================
#  Show Cash Flow + Lite ERP on the owner's desktop (System Console)  v2
#  - makes both icons "standard" App icons that open their page directly
#    (v16 hides a non-standard App icon from everyone except its creator,
#     and hides a Link icon unless that user's sidebar for it resolves)
#  - gives the owner the roles below
#  - refreshes both icons in the owner's saved desktop arrangement
#  Safe to run again.
# =====================================================================

USER_MATCH = "siva7206@gmail.com"   # the owner's login email
ADD_ROLES = ["Business Owner", "Accounts User"]
ICONS = [
    # label, page it opens, icon, colour
    ["Lite ERP", "/desk/lite-erp", "layout", "blue"],
    ["Cash Flow", "/desk/cash-flow", "wallet", "blue"],
]
ICON_FIELDS = ["label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
    "idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image"]

users = frappe.db.sql("""select name, full_name, enabled, user_type from `tabUser`
    where name=%s or email=%s""", (USER_MATCH, USER_MATCH), as_dict=1)
if not users:
    frappe.throw("No user " + USER_MATCH)

# ---------------------------------------------------------------- 1. the icons
entries = {}
for spec in ICONS:
    label = spec[0]
    if not frappe.db.exists("Desktop Icon", label):
        log("MISSING desktop icon: " + label + " - run its setup first")
        continue
    ic = frappe.get_doc("Desktop Icon", label)
    log("before  " + label + ": type=" + str(ic.icon_type) + " link_type=" + str(ic.link_type) +
        " standard=" + str(ic.standard) + " created by=" + str(ic.owner))
    ic.icon_type = "App"
    ic.link_type = "External"
    ic.link = spec[1]
    ic.link_to = None
    ic.app = "sbi_projects"
    ic.standard = 1
    ic.hidden = 0
    ic.parent_icon = None
    if not ic.icon:
        ic.icon = spec[2]
    if not ic.bg_color:
        ic.bg_color = spec[3]
    ic.flags.ignore_links = True
    ic.flags.ignore_mandatory = True
    ic.save(ignore_permissions=True)
    frappe.db.set_value("Desktop Icon", ic.name, "owner", "Administrator", update_modified=False)
    roles_on_icon = []
    for r in ic.get("roles") or []:
        roles_on_icon.append(r.role)
    log("after   " + label + ": App -> " + spec[1] + "  standard=1  roles=" + (", ".join(roles_on_icon) or "everyone"))
    row = {"child_icons": []}
    for fld in ICON_FIELDS:
        row[fld] = ic.get(fld)
    entries[label] = row

# ---------------------------------------------------------------- 2. the owner
for u in users:
    log("----- " + u.name + " (" + str(u.full_name) + ")")
    have = []
    for r in frappe.db.sql("select role from `tabHas Role` where parenttype='User' and parent=%s", u.name):
        have.append(r[0])
    missing = []
    for r in ADD_ROLES:
        if r not in have and frappe.db.exists("Role", r):
            missing.append(r)
    if missing:
        doc = frappe.get_doc("User", u.name)
        for r in missing:
            doc.append("roles", {"role": r})
        doc.save(ignore_permissions=True)
        log("  roles added: " + ", ".join(missing))
    else:
        log("  roles OK (" + ", ".join([r for r in ADD_ROLES if r in have]) + ")")

    if not frappe.db.exists("Desktop Layout", u.name):
        log("  no saved desktop arrangement - every permitted icon shows")
        continue
    raw = frappe.db.get_value("Desktop Layout", u.name, "layout")
    try:
        items = json.loads(raw) if raw else []
    except Exception:
        items = None
    if not isinstance(items, list):
        log("  saved arrangement unreadable - left alone")
        continue
    labels = []
    kept = []
    for it in items:
        if isinstance(it, dict):
            labels.append(str(it.get("label")))
            if it.get("label") in entries:
                continue
        kept.append(it)
    log("  saved desktop had: " + ", ".join(labels))
    for label in entries:
        kept.append(entries[label])
    frappe.db.set_value("Desktop Layout", u.name, "layout", json.dumps(kept), update_modified=False)
    log("  refreshed on saved desktop: " + ", ".join(entries.keys()))

frappe.db.commit()
log("DONE. The owner must reload the desktop (Ctrl+Shift+R) or log out and in.")
log("Note: a later Frappe Cloud migrate re-runs the Cash Flow setup, which turns its icon back into a sidebar link. Run this again after a migrate if Cash Flow disappears for the owner.")
