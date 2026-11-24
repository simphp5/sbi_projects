# Run in System Console (tick Commit). Shows Tally only to the accounts team / owner.
# Tally belongs to the accounts team: hide the Tally workspace and Tally desktop icons from everyone else (e.g. HR)
TALLY_ROLES = []
for r in ["System Manager", "Accounts Manager", "Accounts User", "Business Owner"]:
    if frappe.db.exists("Role", r):
        TALLY_ROLES.append(r)
for pair in [["Workspace", "Tally Integration"], ["Desktop Icon", "Tally"], ["Desktop Icon", "Tally Reports"]]:
    if not frappe.db.exists("DocType", pair[0]) or not frappe.db.exists(pair[0], pair[1]):
        continue
    tdoc = frappe.get_doc(pair[0], pair[1])
    tdoc.set("roles", [])
    for r in TALLY_ROLES:
        tdoc.append("roles", {"role": r})
    tdoc.flags.ignore_links = True
    tdoc.flags.ignore_mandatory = True
    tdoc.save(ignore_permissions=True)
    log("accounts team only: " + pair[0] + " " + pair[1])
frappe.db.commit()
log("DONE. Prajan (and other non-accounts users) must reload the page to see the change.")
