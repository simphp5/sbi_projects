# Create the HR login "prajan" (System Console -> Python -> tick Commit -> Execute). Safe to run again.
USERNAME = "prajan"
EMAIL = "prajan@shiv-bharat.com"      # login e-mail (change here if Prajan has a real e-mail)
FIRST_NAME = "Prajan"
PASSWORD = "Hr@2026_SBI"
ROLES = ["HR Manager", "HR User", "Employee"]

# let people log in with the user name (prajan) as well as the e-mail
if not frappe.db.get_single_value("System Settings", "allow_login_using_user_name"):
    frappe.db.set_value("System Settings", "System Settings", "allow_login_using_user_name", 1)
    log("login with user name: turned on")

name = frappe.db.get_value("User", {"username": USERNAME}, "name") or (EMAIL if frappe.db.exists("User", EMAIL) else None)
if name:
    u = frappe.get_doc("User", name)
    log("user exists: " + name + " - updating")
else:
    u = frappe.new_doc("User")
    u.email = EMAIL
    u.flags.is_new_doc = True
u.first_name = FIRST_NAME
u.username = USERNAME
u.enabled = 1
u.user_type = "System User"
u.send_welcome_email = 0
u.new_password = PASSWORD
have = []
for r in u.get("roles") or []:
    have.append(r.role)
for r in ROLES:
    if frappe.db.exists("Role", r) and r not in have:
        u.append("roles", {"role": r})
u.flags.ignore_password_policy = True
if u.flags.is_new_doc:
    u.insert(ignore_permissions=True)
else:
    u.save(ignore_permissions=True)
log("user saved: " + u.name + "  (user name: " + USERNAME + ")")
final = []
for r in frappe.get_doc("User", u.name).roles:
    final.append(r.role)
log("roles: " + ", ".join(final))

# if there is an Employee record for Prajan without a login, link it (so he can also punch in SBI Office)
emps = frappe.get_all("Employee", filters={"employee_name": ["like", "%" + FIRST_NAME + "%"], "status": "Active"}, fields=["name", "employee_name", "user_id"])
if len(emps) == 1 and not emps[0].user_id:
    frappe.db.set_value("Employee", emps[0].name, "user_id", u.name)
    log("linked to employee: " + emps[0].name + " " + emps[0].employee_name)
elif not emps:
    log("no Employee record named " + FIRST_NAME + " found - add one later if he should punch attendance")
else:
    log("employee records found: " + ", ".join([e.name + (" (login " + e.user_id + ")" if e.user_id else "") for e in emps]) + " - link the right one by hand")

frappe.db.commit()
log("DONE. Prajan logs in at /login with  " + USERNAME + "  (or " + u.name + ")  and the password you set.")
