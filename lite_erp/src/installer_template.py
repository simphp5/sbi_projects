# =====================================================================
#  LITE ERP  -  one-page app for the Shiv Bharat owner
#
#  Top menu (fixed):  Projects | Sales | Purchase | Cash Flow | Bank |
#                     Site Summary | HR | GST
#  Sales     : sales order (Sl, description, area, unit, cost, MS yes/no)
#              -> bill a milestone (MS lines) / non-MS bill / direct invoice
#  Purchase  : purchase order (same lines) -> milestone bill / non-MS bill,
#              or project -> stage -> BOQ items not yet bought -> bill
#  Cash Flow       : give cash / site expense / import from Tally
#  Site Summary    : billed, received, spent, cash with each site
#  Bank            : upload statement daily, match each entry to a GST invoice or remark it
#  GST             : output, input credit, paid, balance to pay
#
#  Paste ALL of this into System Console -> Execute.  Safe to run again.
#  Then reload the browser and open the "Lite ERP" icon  (/app/lite-erp)
# =====================================================================

LABEL = "Lite ERP"
ROUTE = "/desk/lite-erp"
API_METHOD = "sbi_lite_erp"
ROLES_WANTED = ["System Manager", "Accounts Manager", "Accounts User", "Business Owner", "HR Manager", "HR User"]

# The earlier "Accounts Desk" page is replaced by Lite ERP. Set to False to keep it.
REMOVE_OLD_ACCOUNTS_DESK = True

SERVER_SCRIPT = r'''__SERVER__'''

BLOCK_HTML = r'''__HTML__'''

BLOCK_CSS = r'''__CSS__'''

BLOCK_JS = r'''__JS__'''

# SBI Office: office staff punch app (web page /sbi_office) - GPS + selfie, reminders before office time
OFFICE_LABEL = "SBI Office"
OFFICE_ROUTE = "/sbi_office"
OFFICE_API = "sbi_office_punch"
OFFICE_ROLES_WANTED = ["Employee", "Employee Self Service", "HR Manager", "HR User", "System Manager", "Business Owner", "Accounts Manager", "Accounts User"]
OFFICE_SERVER = r'''__OFFICE_SERVER__'''
OFFICE_HTML = r'''__OFFICE_HTML__'''
OFFICE_CSS = r'''__OFFICE_CSS__'''
OFFICE_JS = r'''__OFFICE_JS__'''
OFFICE_REMINDER = r'''__OFFICE_REMINDER__'''
OFFICE_APK = '__OFFICE_APK__'
ICON_180 = '__ICON_180__'
ICON_192 = '__ICON_192__'
ICON_512 = '__ICON_512__'
OFFICE_SW = """self.addEventListener("install", function (e) { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "/sbi_office";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) { if (cs[i].url.indexOf("/sbi_office") >= 0 && "focus" in cs[i]) return cs[i].focus(); }
    return self.clients.openWindow(url);
  }));
});
"""

roles = []
for r in ROLES_WANTED:
    if frappe.db.exists("Role", r):
        roles.append(r)

# ---------------------------------------------------------------- 1. custom fields
FIELDS = [
    # doctype, fieldname, label, type, options, insert_after, list view, read only
    ["Purchase Invoice", "sbi_stage", "Stage / Milestone", "Data", "", "project", 1, 0],
    ["Site Cash Issue", "sbi_tally_je", "Tally Journal Entry", "Link", "Journal Entry", "remarks", 0, 1],
    ["Site Expense Entry", "sbi_tally_je", "Tally Journal Entry", "Link", "Journal Entry", "entered_by", 0, 1],
]
for f in FIELDS:
    cf_name = f[0] + "-" + f[1]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    frappe.get_doc({
        "doctype": "Custom Field", "dt": f[0], "fieldname": f[1], "label": f[2], "fieldtype": f[3],
        "options": f[4], "insert_after": f[5], "in_list_view": f[6], "in_standard_filter": 1,
        "read_only": f[7], "no_copy": f[7],
    }).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# Bank Transaction: the owner's invoice check, editable after the line is submitted
BT_FIELDS = [
    {"fieldname": "sbi_check_sb", "label": "Invoice check (Lite ERP)", "fieldtype": "Section Break", "insert_after": "description", "collapsible": 0},
    {"fieldname": "sbi_check_status", "label": "Check Status", "fieldtype": "Select", "options": "\nMatched\nNo Invoice",
        "insert_after": "sbi_check_sb", "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "sbi_match_doctype", "label": "Invoice Type", "fieldtype": "Link", "options": "DocType", "insert_after": "sbi_check_status"},
    {"fieldname": "sbi_match_name", "label": "Invoice", "fieldtype": "Dynamic Link", "options": "sbi_match_doctype", "insert_after": "sbi_match_doctype"},
    {"fieldname": "sbi_check_cb", "fieldtype": "Column Break", "insert_after": "sbi_match_name"},
    {"fieldname": "sbi_reason", "label": "No Invoice Reason", "fieldtype": "Data", "insert_after": "sbi_check_cb"},
    {"fieldname": "sbi_remarks", "label": "Remarks", "fieldtype": "Small Text", "insert_after": "sbi_reason"},
    {"fieldname": "sbi_checked_by", "label": "Checked By", "fieldtype": "Link", "options": "User", "insert_after": "sbi_remarks", "read_only": 1},
    {"fieldname": "sbi_checked_on", "label": "Checked On", "fieldtype": "Datetime", "insert_after": "sbi_checked_by", "read_only": 1},
]
if frappe.db.exists("DocType", "Bank Transaction"):
    for f in BT_FIELDS:
        cf_name = "Bank Transaction-" + f["fieldname"]
        if frappe.db.exists("Custom Field", cf_name):
            continue
        row = {"doctype": "Custom Field", "dt": "Bank Transaction", "allow_on_submit": 1, "no_copy": 1}
        row.update(f)
        frappe.get_doc(row).insert(ignore_permissions=True)
        log("field added: " + cf_name)

# Project BOQ Item: Sl. No., description, type and remarks for BOQs typed or uploaded in Lite ERP
PBI_FIELDS = [
    {"fieldname": "sbi_sl_no", "label": "Sl. No.", "fieldtype": "Data", "insert_after": "stage", "columns": 1},
    {"fieldname": "sbi_description", "label": "Item Description", "fieldtype": "Small Text", "insert_after": "sbi_sl_no", "in_list_view": 1, "columns": 3},
    {"fieldname": "sbi_type", "label": "Type", "fieldtype": "Select", "insert_after": "sbi_description", "in_list_view": 1, "columns": 1,
        "options": "\nMaterial\nManpower\nEquipment\nTransport\nSubcontract\nOther"},
    {"fieldname": "sbi_remarks", "label": "Remarks", "fieldtype": "Small Text", "insert_after": "amount"},
]
if frappe.db.exists("DocType", "Project BOQ Item"):
    for f in PBI_FIELDS:
        cf_name = "Project BOQ Item-" + f["fieldname"]
        if frappe.db.exists("Custom Field", cf_name):
            continue
        row = {"doctype": "Custom Field", "dt": "Project BOQ Item"}
        row.update(f)
        frappe.get_doc(row).insert(ignore_permissions=True)
        log("field added: " + cf_name)

# one Site Activity per BOQ type: the whole line amount goes to that type in the budget
if frappe.db.exists("DocType", "Site Activity"):
    for pair in [["Material", "material_rate"], ["Manpower", "labour_rate"], ["Equipment", "equipment_rate"],
                 ["Transport", "other_rate"], ["Subcontract", "subcontract_rate"], ["Other", "other_rate"]]:
        an = "BOQ " + pair[0]
        if not frappe.db.exists("Site Activity", an):
            a = {"doctype": "Site Activity", "activity_name": an, "unit_rate": 1, "labour_rate": 0, "material_rate": 0,
                "equipment_rate": 0, "subcontract_rate": 0, "other_rate": 0}
            a[pair[1]] = 1
            frappe.get_doc(a).insert(ignore_permissions=True)
            log("activity added: " + an)

# ---------------------------------------------------------------- permission repair
# Once a doctype has ANY Custom DocPerm rows, ERPNext ignores its standard permissions. If those
# custom rows exist only at level 1 (used to hide fields such as wages), nobody can open the
# doctype at all - not even from the desk. Give such doctypes their level-0 rows back.
PERM_FIELDS = ["read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "import",
    "print", "email", "share", "select"]
for dtn in frappe.db.sql("""select distinct parent from `tabCustom DocPerm`
        where parent not in (select parent from `tabCustom DocPerm` where ifnull(permlevel, 0)=0)"""):
    dtn = dtn[0]
    if not frappe.db.exists("DocType", dtn):
        continue
    added = []
    std = frappe.db.sql("select * from `tabDocPerm` where parent=%s and ifnull(permlevel, 0)=0", dtn, as_dict=1)
    have = []
    for p in std:
        row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
            "role": p.role, "permlevel": 0, "if_owner": p.if_owner or 0}
        for fld in PERM_FIELDS:
            if fld in p:
                row[fld] = p.get(fld) or 0
        frappe.get_doc(row).insert(ignore_permissions=True)
        have.append(p.role)
        added.append(p.role)
    # roles already trusted with level 1 also need to open the record
    for p in frappe.db.sql("select role, `write` from `tabCustom DocPerm` where parent=%s and permlevel=1 and `read`=1", dtn, as_dict=1):
        if p.role in have:
            continue
        frappe.get_doc({"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
            "role": p.role, "permlevel": 0, "read": 1, "write": p.write or 0, "create": p.write or 0, "report": 1,
            "export": 1, "print": 1, "select": 1}).insert(ignore_permissions=True)
        have.append(p.role)
        added.append(p.role + " (read)")
    log("permissions repaired for " + dtn + ": level 0 for " + ", ".join(added))

# HR team must be able to open the site labour records too (Labour register, Labour punches)
for dtn in ["Labour", "Labour Attendance Log", "Site Shift"]:
    if not frappe.db.exists("DocType", dtn) or not frappe.db.exists("Role", "HR Manager"):
        continue
    if not frappe.db.exists("Custom DocPerm", {"parent": dtn}):
        # first custom row replaces the standard ones, so copy those over first
        for p in frappe.db.sql("select * from `tabDocPerm` where parent=%s", dtn, as_dict=1):
            row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
                "role": p.role, "permlevel": p.permlevel or 0, "if_owner": p.if_owner or 0}
            for fld in PERM_FIELDS:
                if fld in p:
                    row[fld] = p.get(fld) or 0
            frappe.get_doc(row).insert(ignore_permissions=True)
    levels = [0]
    for lv in frappe.db.sql("select distinct ifnull(permlevel, 0) from `tabCustom DocPerm` where parent=%s", dtn):
        if lv[0] not in levels:
            levels.append(lv[0])
    for hrr in ["HR Manager", "HR User"]:
        if not frappe.db.exists("Role", hrr):
            continue
        for lv in levels:
            if frappe.db.exists("Custom DocPerm", {"parent": dtn, "role": hrr, "permlevel": lv}):
                continue
            full = 1 if (hrr == "HR Manager" or lv == 0) else 0
            row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
                "role": hrr, "permlevel": lv, "read": 1, "write": full, "report": 1 if lv == 0 else 0}
            if lv == 0:
                row.update({"create": 1, "delete": 1 if hrr == "HR Manager" else 0, "export": 1, "print": 1, "email": 1, "share": 1, "select": 1})
            frappe.get_doc(row).insert(ignore_permissions=True)
            log("HR access added: " + dtn + " level " + str(lv) + " for " + hrr)

# ---------------------------------------------------------------- 1b. order lines: Sl. No. + MS (milestone) yes / no
ORDER_FIELDS = []
for dt in ["Sales Order Item", "Purchase Order Item", "Sales Invoice Item", "Purchase Invoice Item"]:
    order = dt in ("Sales Order Item", "Purchase Order Item")
    ORDER_FIELDS.append({"dt": dt, "fieldname": "sbi_sl_no", "label": "Sl. No.", "fieldtype": "Data", "insert_after": "item_code",
        "in_list_view": 1, "columns": 1, "length": 20})
    ORDER_FIELDS.append({"dt": dt, "fieldname": "sbi_ms", "label": "MS (milestone)", "fieldtype": "Check", "default": "1",
        "insert_after": "amount", "in_list_view": 1 if order else 0, "columns": 1, "read_only": 0 if order else 1,
        "description": "Ticked = billed by milestones. Not ticked = billed separately (non-MS bill)."})
ORDER_FIELDS.append({"dt": "Payment Schedule", "fieldname": "sbi_ms_percent", "label": "% of milestone work", "fieldtype": "Float",
    "insert_after": "invoice_portion", "read_only": 1, "precision": "4",
    "description": "The milestone % of the MS lines only (Lite ERP)."})
ORDER_FIELDS.append({"dt": "Purchase Invoice", "fieldname": "sbi_source_purchase_order", "label": "Source Purchase Order", "fieldtype": "Link",
    "options": "Purchase Order", "insert_after": "sbi_stage", "read_only": 1, "no_copy": 1})
ORDER_FIELDS.append({"dt": "Purchase Invoice", "fieldname": "sbi_source_payment_terms", "label": "Source Payment Term Rows", "fieldtype": "Small Text",
    "insert_after": "sbi_source_purchase_order", "read_only": 1, "hidden": 1, "no_copy": 1})
if not frappe.get_meta("Sales Invoice").has_field("sbi_source_sales_order"):
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_source_sales_order", "label": "Source Sales Order", "fieldtype": "Link",
        "options": "Sales Order", "insert_after": "project", "read_only": 1, "no_copy": 1})
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_source_payment_terms", "label": "Source Payment Term Rows", "fieldtype": "Small Text",
        "insert_after": "sbi_source_sales_order", "read_only": 1, "hidden": 1, "no_copy": 1})
if not frappe.get_meta("Sales Invoice").has_field("sbi_stage"):
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_stage", "label": "Stage / Milestone", "fieldtype": "Data", "insert_after": "project"})
for f in ORDER_FIELDS:
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# HR: salary month + office location (HR Settings) and office punch details (Employee Checkin)
HR_FIELDS = [
    {"dt": "HR Settings", "fieldname": "sbi_lite_hr_sb", "label": "Lite ERP: salary month and office punch", "fieldtype": "Section Break", "insert_after": None, "collapsible": 0},
    {"dt": "HR Settings", "fieldname": "sbi_salary_start_day", "label": "Salary month starts on day", "fieldtype": "Int", "default": "1", "insert_after": "sbi_lite_hr_sb",
        "description": "1 = calendar month (1st to last day). 26 = 26th to 25th of next month."},
    {"dt": "HR Settings", "fieldname": "sbi_full_day_hours", "label": "Full day (hours)", "fieldtype": "Float", "default": "8", "insert_after": "sbi_salary_start_day"},
    {"dt": "HR Settings", "fieldname": "sbi_half_day_hours", "label": "Half day (hours)", "fieldtype": "Float", "default": "4", "insert_after": "sbi_full_day_hours"},
    {"dt": "HR Settings", "fieldname": "sbi_lite_hr_cb", "fieldtype": "Column Break", "insert_after": "sbi_half_day_hours"},
    {"dt": "HR Settings", "fieldname": "sbi_office_name", "label": "Office name", "fieldtype": "Data", "insert_after": "sbi_lite_hr_cb"},
    {"dt": "HR Settings", "fieldname": "sbi_office_latitude", "label": "Office latitude", "fieldtype": "Float", "precision": "7", "insert_after": "sbi_office_name"},
    {"dt": "HR Settings", "fieldname": "sbi_office_longitude", "label": "Office longitude", "fieldtype": "Float", "precision": "7", "insert_after": "sbi_office_latitude"},
    {"dt": "HR Settings", "fieldname": "sbi_office_radius", "label": "Office area (metres)", "fieldtype": "Int", "default": "200", "insert_after": "sbi_office_longitude"},
    {"dt": "HR Settings", "fieldname": "sbi_block_outside", "label": "Allow punch only inside the office area", "fieldtype": "Check", "default": "1", "insert_after": "sbi_office_radius",
        "description": "Staff marked “Can punch anywhere” on their Employee record are not blocked."},
    {"dt": "HR Settings", "fieldname": "sbi_office_in_time", "label": "Office starts at", "fieldtype": "Time", "default": "09:30:00", "insert_after": "sbi_block_outside"},
    {"dt": "HR Settings", "fieldname": "sbi_office_out_time", "label": "Office ends at", "fieldtype": "Time", "default": "18:30:00", "insert_after": "sbi_office_in_time"},
    {"dt": "HR Settings", "fieldname": "sbi_late_grace", "label": "Late after (minutes of grace)", "fieldtype": "Int", "default": "10", "insert_after": "sbi_office_out_time"},
    {"dt": "HR Settings", "fieldname": "sbi_reminder_minutes", "label": "Punch reminder (minutes before)", "fieldtype": "Int", "default": "15", "insert_after": "sbi_late_grace",
        "description": "SBI Office reminds staff this many minutes before the office start and end time. 0 = no reminders."},
    {"dt": "Employee", "fieldname": "sbi_punch_anywhere", "label": "Can punch anywhere (SBI Office)", "fieldtype": "Check", "default": "0", "insert_after": "user_id",
        "description": "Tick for field staff who punch outside the office area."},
    {"dt": "Employee", "fieldname": "sbi_face_front", "label": "Face photo – front (SBI Office)", "fieldtype": "Attach Image", "insert_after": "sbi_punch_anywhere",
        "description": "Taken once in the SBI Office app. Clear all three to let the employee take them again."},
    {"dt": "Employee", "fieldname": "sbi_face_left", "label": "Face photo – left", "fieldtype": "Attach Image", "insert_after": "sbi_face_front"},
    {"dt": "Employee", "fieldname": "sbi_face_right", "label": "Face photo – right", "fieldtype": "Attach Image", "insert_after": "sbi_face_left"},
    {"dt": "Employee", "fieldname": "sbi_face_on", "label": "Face photos taken on", "fieldtype": "Datetime", "insert_after": "sbi_face_right", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_address", "label": "Place (street, area, city)", "fieldtype": "Small Text", "insert_after": "sbi_remarks", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_punch_sb", "label": "Office punch", "fieldtype": "Section Break", "insert_after": "longitude", "collapsible": 0},
    {"dt": "Employee Checkin", "fieldname": "sbi_photo", "label": "Punch photo", "fieldtype": "Attach Image", "insert_after": "sbi_punch_sb", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_source", "label": "Source", "fieldtype": "Data", "insert_after": "sbi_photo", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_punch_cb", "fieldtype": "Column Break", "insert_after": "sbi_source"},
    {"dt": "Employee Checkin", "fieldname": "sbi_distance", "label": "Distance from office (m)", "fieldtype": "Float", "insert_after": "sbi_punch_cb", "read_only": 1, "in_list_view": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_within", "label": "Inside office area", "fieldtype": "Check", "default": "1", "insert_after": "sbi_distance", "read_only": 1, "in_list_view": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_accuracy", "label": "GPS accuracy (m)", "fieldtype": "Float", "insert_after": "sbi_within", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_remarks", "label": "Reason (if outside)", "fieldtype": "Small Text", "insert_after": "sbi_accuracy", "read_only": 1},
]
for f in HR_FIELDS:
    if not frappe.db.exists("DocType", f["dt"]):
        log("skipped (no " + f["dt"] + "): " + f["fieldname"])
        continue
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    if not row.get("insert_after"):
        flds = frappe.get_meta(f["dt"]).fields
        row["insert_after"] = flds[-1].fieldname if flds else None
    if f["dt"] == "Employee Checkin" and f["fieldname"] == "sbi_punch_sb" and not frappe.get_meta("Employee Checkin").has_field("longitude"):
        row["insert_after"] = "time"
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

module = "SBI Projects" if frappe.db.exists("Module Def", "SBI Projects") else "Accounts"
# ---------------------------------------------------------------- staff: logins by user id, self-service requests, letters
STAFF_ROLE = "SBI Staff"
if not frappe.db.exists("Role", STAFF_ROLE):
    frappe.get_doc({"doctype": "Role", "role_name": STAFF_ROLE, "desk_access": 1}).insert(ignore_permissions=True)
    log("role added: " + STAFF_ROLE)
for r in [STAFF_ROLE, "Employee", "Employee Self Service", "Sales User", "Sales Manager", "Purchase User", "Purchase Manager", "Projects User", "Projects Manager"]:
    if frappe.db.exists("Role", r) and r not in roles:
        roles.append(r)

STAFF_FIELDS = [
    {"dt": "User", "fieldname": "sbi_must_change_password", "label": "Must change password at next login (Lite ERP)", "fieldtype": "Check", "default": "0", "insert_after": "enabled",
        "description": "Set when HR gives a login with the default password. Cleared when the person sets their own password."},
    {"dt": "Attendance Request", "fieldname": "sbi_status", "label": "HR decision", "fieldtype": "Select", "options": "\nPending\nApproved\nRejected", "insert_after": "explanation",
        "in_list_view": 1, "in_standard_filter": 1},
    {"dt": "Attendance Request", "fieldname": "sbi_hr_remarks", "label": "HR remarks", "fieldtype": "Small Text", "insert_after": "sbi_status"},
]
for f in STAFF_FIELDS:
    if not frappe.db.exists("DocType", f["dt"]):
        continue
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    if not frappe.get_meta(f["dt"]).has_field(row["insert_after"]):
        flds = frappe.get_meta(f["dt"]).fields
        row["insert_after"] = flds[-1].fieldname if flds else None
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# more reasons for attendance requests (only "Work From Home" is marked WFH, all others are marked Present); no shifts for office staff
PROPS = [
    ["Attendance Request", "reason", "options", "Work From Home\nOn Duty\nForgot to Punch\nClient / Site Visit\nOfficial Travel\nTraining / Meeting Outside\nMobile / GPS Problem\nOther", "Text"],
    ["Employee", "default_shift", "hidden", "1", "Check"],
    ["Attendance Request", "shift", "hidden", "1", "Check"],
    ["Employee", "employee_number", "label", "Employee ID No.", "Data"],
]
for pp in PROPS:
    if not frappe.db.exists("DocType", pp[0]) or not frappe.get_meta(pp[0]).has_field(pp[1]):
        continue
    psn = pp[0] + "-" + pp[1] + "-" + pp[2]
    if frappe.db.exists("Property Setter", psn):
        ps = frappe.get_doc("Property Setter", psn)
        ps.value = pp[3]
        ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Property Setter", "doctype_or_field": "DocField", "doc_type": pp[0], "field_name": pp[1],
            "property": pp[2], "property_type": pp[4], "value": pp[3]}).insert(ignore_permissions=True)
    log("property set: " + psn)

# employee detail changes waiting for HR
CR_DT = "SBI Employee Change Request"
if not frappe.db.exists("DocType", CR_DT):
    frappe.get_doc({"doctype": "DocType", "name": CR_DT, "module": module, "custom": 1, "autoname": "ECR-.#####", "naming_rule": "Expression (old style)",
        "title_field": "employee_name", "track_changes": 1, "sort_field": "creation", "sort_order": "DESC",
        "fields": [
            {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "employee_name", "label": "Employee name", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Pending\nApproved\nRejected", "default": "Pending", "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "summary", "label": "What changes", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "cb1", "fieldtype": "Column Break"},
            {"fieldname": "reviewed_by", "label": "Checked by", "fieldtype": "Link", "options": "User", "read_only": 1},
            {"fieldname": "reviewed_on", "label": "Checked on", "fieldtype": "Datetime", "read_only": 1},
            {"fieldname": "hr_remarks", "label": "HR remarks", "fieldtype": "Small Text"},
            {"fieldname": "sb1", "fieldtype": "Section Break", "label": "Changes"},
            {"fieldname": "changes", "label": "New values", "fieldtype": "Code", "options": "JSON", "read_only": 1},
            {"fieldname": "new_photo", "label": "New photo", "fieldtype": "Attach Image"},
        ],
        "permissions": [{"role": "HR Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
            {"role": "HR User", "read": 1, "write": 1, "create": 1, "report": 1},
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1}]}).insert(ignore_permissions=True)
    log("doctype added: " + CR_DT)

# log in with the user id (not only e-mail)
if not frappe.db.get_single_value("System Settings", "allow_login_using_user_name"):
    sset = frappe.get_doc("System Settings")
    sset.allow_login_using_user_name = 1
    sset.flags.ignore_mandatory = True
    sset.save(ignore_permissions=True)
    log("System Settings: login with user id allowed")

# every employee with a login opens Lite ERP after login and has the Employee role
EMP_USERS = frappe.db.sql("""select e.user_id from `tabEmployee` e join `tabUser` u on u.name = e.user_id
    where e.status = 'Active' and ifnull(e.user_id, '') != '' and u.user_type = 'System User' and u.enabled = 1""")
n_ws = 0
for eu in EMP_USERS:
    uid = eu[0]
    if uid in ("Administrator", "Guest"):
        continue
    if frappe.db.get_value("User", uid, "default_workspace") != LABEL:
        frappe.db.set_value("User", uid, "default_workspace", LABEL, update_modified=False)
        n_ws = n_ws + 1
    if frappe.db.exists("Role", "Employee") and not frappe.db.exists("Has Role", {"parenttype": "User", "parent": uid, "role": "Employee"}):
        ud = frappe.get_doc("User", uid)
        ud.append("roles", {"role": "Employee"})
        ud.flags.ignore_password_policy = True
        ud.save(ignore_permissions=True)
log("employee logins opening Lite ERP: " + str(len(EMP_USERS)) + " (" + str(n_ws) + " changed)")

# appointment and relieving orders (print formats on Employee - HR can edit the wording in Print Format)
LETTER_TOP = """<style>.sbi-letter { font-size: 13px; line-height: 1.6; } .sbi-letter h3 { text-align: center; text-decoration: underline; letter-spacing: 1px; margin: 18px 0; }
.sbi-letter .r { text-align: right; } .sbi-letter ol li { margin-bottom: 6px; } .sbi-letter .sign { margin-top: 48px; }</style>
{% set mr = "Mr." if doc.gender == "Male" else ("Ms." if doc.gender == "Female" else "") %}
{% set he = "He" if doc.gender == "Male" else ("She" if doc.gender == "Female" else "They") %}
{% set his = "his" if doc.gender == "Male" else ("her" if doc.gender == "Female" else "their") %}
{% set idno = doc.employee_number or doc.name %}
<div class="sbi-letter">
"""
APPOINT_HTML = LETTER_TOP + """<p class="r">Date: {{ frappe.utils.formatdate(frappe.utils.nowdate()) }}</p>
<p>Ref: APT/{{ idno }}</p>
<p>To,<br><b>{{ mr }} {{ doc.employee_name }}</b><br>{{ (doc.current_address or doc.permanent_address or "") | replace("\\n", "<br>") }}</p>
<h3>APPOINTMENT ORDER</h3>
<p>Dear {{ doc.first_name }},</p>
<p>We are pleased to appoint you as <b>{{ doc.designation or "__________" }}</b>{% if doc.department %} in the <b>{{ doc.department.split(" - ")[0] }}</b> department{% endif %}
of <b>{{ doc.company }}</b> with effect from <b>{{ frappe.utils.formatdate(doc.date_of_joining) }}</b>, on the following terms and conditions:</p>
<ol>
<li>Your Employee ID No. is <b>{{ idno }}</b>. Please quote it in all correspondence.</li>
{% if doc.ctc %}<li>Your total cost to the company will be <b>{{ frappe.utils.fmt_money(doc.ctc, currency="INR") }}</b> per year, as detailed in the salary annexure.</li>{% endif %}
<li>You will be on probation for six months from the date of joining. On satisfactory completion you will be confirmed in writing.</li>
<li>Office hours are {{ ((frappe.db.get_single_value("HR Settings", "sbi_office_in_time") or "09:30")|string)[:5] }} to {{ ((frappe.db.get_single_value("HR Settings", "sbi_office_out_time") or "18:30")|string)[:5] }}.
Attendance must be marked every day with the SBI Office app (photo and GPS). Leave must be applied for and approved in advance.</li>
<li>You may be posted to any office, site or project of the company as required by the work.</li>
<li>During probation either party may end the employment with 15 days' notice; after confirmation, with one month's notice or salary in lieu of notice.</li>
<li>You will keep all company information confidential and follow the rules of the company in force from time to time.</li>
</ol>
<p>Please sign the duplicate copy of this order as a token of your acceptance.</p>
<p class="sign">For <b>{{ doc.company }}</b><br><br><br>Authorised Signatory</p>
<hr>
<p><b>Acceptance</b><br>I have read and accept the above terms and conditions.</p>
<p>Signature: ______________________ &nbsp;&nbsp; Name: {{ doc.employee_name }} &nbsp;&nbsp; Date: ______________</p>
</div>"""
RELIEVE_HTML = LETTER_TOP + """<p class="r">Date: {{ frappe.utils.formatdate(doc.relieving_date or frappe.utils.nowdate()) }}</p>
<p>Ref: REL/{{ idno }}</p>
<p>To,<br><b>{{ mr }} {{ doc.employee_name }}</b><br>Employee ID No. {{ idno }}<br>{{ (doc.current_address or doc.permanent_address or "") | replace("\\n", "<br>") }}</p>
<h3>RELIEVING ORDER</h3>
<p>This is to certify that <b>{{ mr }} {{ doc.employee_name }}</b> (Employee ID No. {{ idno }}) was employed with <b>{{ doc.company }}</b>
as <b>{{ doc.designation or "__________" }}</b> from <b>{{ frappe.utils.formatdate(doc.date_of_joining) }}</b>
to <b>{{ frappe.utils.formatdate(doc.relieving_date) if doc.relieving_date else "__________" }}</b>.</p>
<p>{% if doc.resignation_letter_date %}With reference to {{ his }} resignation dated {{ frappe.utils.formatdate(doc.resignation_letter_date) }}, {% endif %}{{ he|lower if doc.resignation_letter_date else he }}
is relieved from {{ his }} duties with effect from the close of working hours on <b>{{ frappe.utils.formatdate(doc.relieving_date) if doc.relieving_date else "__________" }}</b>.</p>
<p>{{ he }} has handed over all company property and documents in {{ his }} charge. {{ his|capitalize }} full and final settlement will be made as per company rules.</p>
<p>During {{ his }} service we found {{ his }} conduct and work satisfactory. We wish {{ "him" if doc.gender == "Male" else ("her" if doc.gender == "Female" else "them") }} success in the future.</p>
<p class="sign">For <b>{{ doc.company }}</b><br><br><br>Authorised Signatory</p>
</div>"""
for pfn in [["SBI Appointment Order", APPOINT_HTML], ["SBI Relieving Order", RELIEVE_HTML]]:
    if frappe.db.exists("Print Format", pfn[0]):
        log("print format exists (kept, HR may have edited it): " + pfn[0])
        continue
    pdoc = frappe.get_doc({"doctype": "Print Format", "name": pfn[0], "__newname": pfn[0], "doc_type": "Employee", "module": module, "standard": "No",
        "custom_format": 1, "print_format_type": "Jinja", "html": pfn[1], "disabled": 0, "font_size": 13})
    pdoc.insert(ignore_permissions=True)
    log("print format added: " + pfn[0])

# units used on order lines (sq.ft and sq.m already come with ERPNext)
for u in ["Square Foot", "Square Meter", "Running Meter", "Lump Sum"]:
    if not frappe.db.exists("UOM", u):
        frappe.get_doc({"doctype": "UOM", "uom_name": u, "must_be_whole_number": 0, "enabled": 1}).insert(ignore_permissions=True)
        log("unit added: " + u)
    elif not frappe.db.get_value("UOM", u, "enabled"):
        frappe.db.set_value("UOM", u, "enabled", 1)

# ---------------------------------------------------------------- 2. server script (API)
if frappe.db.exists("Server Script", "SBI Lite ERP"):
    ss = frappe.get_doc("Server Script", "SBI Lite ERP")
else:
    ss = frappe.new_doc("Server Script")
    ss.name = "SBI Lite ERP"
    ss.flags.is_new_doc = True
ss.script_type = "API"
ss.api_method = API_METHOD
ss.allow_guest = 0
ss.disabled = 0
ss.script = SERVER_SCRIPT
if ss.flags.is_new_doc:
    ss.insert(ignore_permissions=True)
else:
    ss.save(ignore_permissions=True)
log("server script saved: " + ss.name)

# ---------------------------------------------------------------- 3. the page (Custom HTML Block)
if frappe.db.exists("Custom HTML Block", LABEL):
    blk = frappe.get_doc("Custom HTML Block", LABEL)
else:
    blk = frappe.new_doc("Custom HTML Block")
    blk.name = LABEL
    blk.flags.is_new_doc = True
blk.html = BLOCK_HTML
blk.style = BLOCK_CSS
blk.script = BLOCK_JS
blk.private = 0
blk.set("roles", [])
for r in roles:
    blk.append("roles", {"role": r})
if blk.flags.is_new_doc:
    blk.insert(ignore_permissions=True)
else:
    blk.save(ignore_permissions=True)
log("page saved: " + blk.name)

# ---------------------------------------------------------------- 4. workspace  /app/lite-erp
module = "SBI Projects" if frappe.db.exists("Module Def", "SBI Projects") else "Accounts"
if frappe.db.exists("Workspace", LABEL):
    ws = frappe.get_doc("Workspace", LABEL)
else:
    ws = frappe.new_doc("Workspace")
    ws.label = LABEL
    ws.standard = 0
    ws.flags.is_new_doc = True
ws.title = LABEL
ws.module = module
ws.public = 1
ws.is_hidden = 0
ws.type = "Workspace"
ws.icon = "layout"
ws.sequence_id = 0.5
ws.content = '[{"id":"sbiLiteErp01","type":"custom_block","data":{"custom_block_name":"Lite ERP","col":12}}]'
ws.set("custom_blocks", [{"custom_block_name": LABEL, "label": LABEL}])
ws.set("shortcuts", [])
ws.set("roles", [])
for r in roles:
    ws.append("roles", {"role": r})
ws.flags.ignore_links = True
if ws.flags.is_new_doc:
    ws.insert(ignore_permissions=True)
else:
    ws.save(ignore_permissions=True)
log("workspace saved: " + ROUTE)

# ---------------------------------------------------------------- 5. desktop icon (v16)
# v16 only lets a plain "Link" icon through when it belongs to a module sidebar, so the icon
# is an "App" icon that opens /desk/lite-erp. Users who have arranged their desktop see only
# their saved arrangement, so the icon is also added to every saved arrangement.
ICON_FIELDS = ["label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
    "idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image"]
if frappe.db.exists("DocType", "Desktop Icon"):
    if frappe.db.exists("Desktop Icon", LABEL):
        ic = frappe.get_doc("Desktop Icon", LABEL)
    else:
        ic = frappe.new_doc("Desktop Icon")
        ic.label = LABEL
        ic.flags.is_new_doc = True
        top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
        mx = 0
        for i in top:
            if (i or 0) > mx:
                mx = i or 0
        ic.idx = mx + 1
    ic.icon_type = "App"
    ic.link_type = "External"
    ic.link = ROUTE
    ic.link_to = None
    ic.icon = "layout"
    ic.bg_color = "blue"
    ic.app = "sbi_projects"
    ic.standard = 1          # v16 hides a non-standard App icon from everyone but its creator
    ic.hidden = 0
    ic.parent_icon = None
    ic.set("roles", [])
    for r in roles:
        ic.append("roles", {"role": r})
    ic.flags.ignore_links = True
    ic.flags.ignore_mandatory = True
    if ic.flags.is_new_doc:
        ic.insert(ignore_permissions=True)
    else:
        ic.save(ignore_permissions=True)
    frappe.db.set_value("Desktop Icon", ic.name, "owner", "Administrator", update_modified=False)
    log("desktop icon saved: " + ic.name)

    if frappe.db.exists("DocType", "Desktop Layout"):
        entry = {"child_icons": []}
        for fld in ICON_FIELDS:
            entry[fld] = ic.get(fld)
        users = ["Administrator"]
        if roles:
            for u in frappe.db.sql("""select distinct parent from `tabHas Role`
                    where parenttype='User' and role in %(r)s""", {"r": tuple(roles)}):
                users.append(u[0])
        added = 0
        for lay in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
            if lay.name not in users or not lay.layout:
                continue
            try:
                items = json.loads(lay.layout)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            kept = []
            for it in items:
                if not (isinstance(it, dict) and it.get("label") == LABEL):
                    kept.append(it)
            kept.append(entry)
            frappe.db.set_value("Desktop Layout", lay.name, "layout", json.dumps(kept), update_modified=False)
            added += 1
        log("added to " + str(added) + " saved desktop arrangement(s)")

# ---------------------------------------------------------------- 6. remove the earlier Accounts Desk
if REMOVE_OLD_ACCOUNTS_DESK:
    for pair in [["Desktop Icon", "Accounts Desk"], ["Workspace", "Accounts Desk"],
                 ["Custom HTML Block", "Accounts Desk"], ["Server Script", "SBI Accounts Desk"]]:
        if frappe.db.exists("DocType", pair[0]) and frappe.db.exists(pair[0], pair[1]):
            frappe.delete_doc(pair[0], pair[1], ignore_permissions=True)
            log("removed old " + pair[0] + ": " + pair[1])

# ---------------------------------------------------------------- 7. Office Punch app (desktop icon for every employee)
oroles = []
for r in OFFICE_ROLES_WANTED:
    if frappe.db.exists("Role", r):
        oroles.append(r)
if frappe.db.exists("Server Script", "SBI Office Punch"):
    oss = frappe.get_doc("Server Script", "SBI Office Punch")
else:
    oss = frappe.new_doc("Server Script")
    oss.name = "SBI Office Punch"
    oss.flags.is_new_doc = True
oss.script_type = "API"
oss.api_method = OFFICE_API
oss.allow_guest = 0
oss.disabled = 0
oss.script = OFFICE_SERVER
if oss.flags.is_new_doc:
    oss.insert(ignore_permissions=True)
else:
    oss.save(ignore_permissions=True)
log("server script saved: " + oss.name)

# reminders: every 5 minutes, N minutes before office start / end (HR Settings)
if frappe.db.exists("Server Script", "SBI Office Reminder"):
    rss = frappe.get_doc("Server Script", "SBI Office Reminder")
else:
    rss = frappe.new_doc("Server Script")
    rss.name = "SBI Office Reminder"
    rss.flags.is_new_doc = True
rss.script_type = "Scheduler Event"
rss.event_frequency = "Cron"
rss.cron_format = "*/5 * * * *"
rss.disabled = 0
rss.script = OFFICE_REMINDER
if rss.flags.is_new_doc:
    rss.insert(ignore_permissions=True)
else:
    rss.save(ignore_permissions=True)
log("reminder schedule saved: every 5 minutes")

# the app page itself (any logged-in user; the API only lets people punch for their own Employee)
wp_name = frappe.db.get_value("Web Page", {"route": OFFICE_ROUTE.strip("/")}, "name")
if wp_name:
    wp = frappe.get_doc("Web Page", wp_name)
else:
    wp = frappe.new_doc("Web Page")
    wp.flags.is_new_doc = True
wp.title = "SBI Office"
wp.route = OFFICE_ROUTE.strip("/")
wp.published = 1
wp.content_type = "HTML"
wp.main_section_html = OFFICE_HTML
wp.css = OFFICE_CSS
wp.insert_style = 1
wp.javascript = OFFICE_JS
wp.full_width = 1
wp.show_title = 0
wp.dynamic_template = 0
wp.meta_title = "SBI Office"
wp.meta_description = "Shiv Bharat office staff attendance - punch IN / OUT with selfie and GPS"
if wp.meta.has_field("show_sidebar"):
    wp.show_sidebar = 0
if wp.flags.is_new_doc:
    wp.insert(ignore_permissions=True)
else:
    wp.save(ignore_permissions=True)
log("app page saved: " + OFFICE_ROUTE)

# install-as-app files: manifest (Add to Home screen / APK) and the notification worker
app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo") or "/assets/frappe/images/frappe-framework-logo.svg"
# app icons (Android home screen, iPhone home screen)
for pair in [["sbi_office_icon_180.png", ICON_180], ["sbi_office_icon_192.png", ICON_192], ["sbi_office_icon_512.png", ICON_512]]:
    if frappe.get_all("File", filters={"file_url": "/files/" + pair[0]}, pluck="name"):
        continue
    idoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1], "decode": True})
    idoc.flags.ignore_permissions = True
    idoc.insert(ignore_permissions=True)
    log("icon saved: " + idoc.file_url)
MANIFEST = '{"name": "SBI Office - Staff Attendance", "short_name": "SBI Office", "id": "/sbi_office", "start_url": "/sbi_office", "scope": "/sbi_office", ' + \
    '"display": "standalone", "orientation": "portrait", "background_color": "#f3f4f6", "theme_color": "#c8102e", ' + \
    '"description": "Punch IN / OUT with selfie and GPS", "icons": [{"src": "/files/sbi_office_icon_192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}, ' + \
    '{"src": "/files/sbi_office_icon_512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}'
for pair in [["sbi_office_manifest_v2.json", MANIFEST], ["sbi_office_sw.js", OFFICE_SW]]:
    furl = "/files/" + pair[0]
    old = frappe.get_all("File", filters={"file_url": furl}, pluck="name")
    if old:
        log("file kept: " + furl)
        continue
    fdoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1]})
    fdoc.flags.ignore_permissions = True
    fdoc.insert(ignore_permissions=True)
    log("file saved: " + fdoc.file_url)

# Android app (APK) for staff to download: /files/SBI-Office-v1.0.apk
APK_NAME = "SBI-Office-v1.0.apk"
if frappe.get_all("File", filters={"file_url": "/files/" + APK_NAME}, pluck="name"):
    log("android app kept: /files/" + APK_NAME)
else:
    adoc = frappe.get_doc({"doctype": "File", "file_name": APK_NAME, "is_private": 0, "content": OFFICE_APK, "decode": True})
    adoc.flags.ignore_permissions = True
    adoc.insert(ignore_permissions=True)
    log("android app saved: " + adoc.file_url)

# old desk version of the punch page (if an earlier test made it)
for pair in [["Workspace", "Office Punch"], ["Custom HTML Block", "Office Punch"], ["Desktop Icon", "Office Punch"]]:
    if frappe.db.exists(pair[0], pair[1]):
        frappe.delete_doc(pair[0], pair[1], ignore_permissions=True)
        log("removed old " + pair[0] + ": " + pair[1])

if frappe.db.exists("DocType", "Desktop Icon"):
    if frappe.db.exists("Desktop Icon", OFFICE_LABEL):
        oic = frappe.get_doc("Desktop Icon", OFFICE_LABEL)
    else:
        oic = frappe.new_doc("Desktop Icon")
        oic.label = OFFICE_LABEL
        oic.flags.is_new_doc = True
        top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
        mx = 0
        for i in top:
            if (i or 0) > mx:
                mx = i or 0
        oic.idx = mx + 1
    oic.icon_type = "App"
    oic.link_type = "External"
    oic.link = OFFICE_ROUTE
    oic.link_to = None
    oic.icon = "map-pin"
    oic.bg_color = "blue"
    oic.app = "sbi_projects"
    oic.standard = 1
    oic.hidden = 0
    oic.parent_icon = None
    oic.set("roles", [])
    for r in oroles:
        oic.append("roles", {"role": r})
    oic.flags.ignore_links = True
    oic.flags.ignore_mandatory = True
    if oic.flags.is_new_doc:
        oic.insert(ignore_permissions=True)
    else:
        oic.save(ignore_permissions=True)
    frappe.db.set_value("Desktop Icon", oic.name, "owner", "Administrator", update_modified=False)
    log("desktop icon saved: " + oic.name)
    if frappe.db.exists("DocType", "Desktop Layout"):
        oentry = {"child_icons": []}
        for fld in ICON_FIELDS:
            oentry[fld] = oic.get(fld)
        ousers = ["Administrator"]
        if oroles:
            for u in frappe.db.sql("""select distinct parent from `tabHas Role` where parenttype='User' and role in %(r)s""", {"r": tuple(oroles)}):
                ousers.append(u[0])
        oadded = 0
        for lay in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
            if lay.name not in ousers or not lay.layout:
                continue
            try:
                items = json.loads(lay.layout)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            kept = []
            for it in items:
                if not (isinstance(it, dict) and it.get("label") == OFFICE_LABEL):
                    kept.append(it)
            kept.append(oentry)
            frappe.db.set_value("Desktop Layout", lay.name, "layout", json.dumps(kept), update_modified=False)
            oadded = oadded + 1
        log("SBI Office added to " + str(oadded) + " saved desktop arrangement(s)")

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

# who can punch: active employees need their login in Employee -> User ID
nolink = frappe.db.sql("select count(*) from `tabEmployee` where status='Active' and ifnull(user_id, '')=''")[0][0]
log("active employees without a login (cannot punch until User ID is set): " + str(nolink))

frappe.db.commit()
log("DONE. Reload the browser (Ctrl+Shift+R). Lite ERP: " + ROUTE + "   Staff punch app: " + frappe.utils.get_url(OFFICE_ROUTE))
