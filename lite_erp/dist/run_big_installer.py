# Run a big installer file (too long to paste) from an uploaded file.
# 1) Upload lite_erp_console.txt (or .py) in ERPNext:  /app/file  ->  Upload
# 2) Paste THIS small script in System Console -> Python -> tick Commit -> Execute
# 3) Open the link it prints (same browser, logged in as Administrator). The page shows the installer log.
FILE_NAME = "lite_erp_console"          # start of the uploaded file name

rows = frappe.db.sql("""select name, file_name, file_url, creation from `tabFile`
    where ifnull(is_folder, 0) = 0 and (file_name like %s or file_url like %s)
    and (file_name like '%%.py' or file_name like '%%.txt') order by creation desc limit 1""", ("%" + FILE_NAME + "%", "%" + FILE_NAME + "%"), as_dict=1)
if not rows:
    recent = frappe.db.sql("""select file_name from `tabFile` where ifnull(is_folder, 0) = 0 order by creation desc limit 8""")
    frappe.throw("Could not find an uploaded file named " + FILE_NAME + ".py or .txt. Upload it at /app/file (Upload button). Latest uploads I can see: "
        + ", ".join([str(r[0]) for r in recent]))
f = frappe.get_doc("File", rows[0].name)
code = f.get_content()
if not isinstance(code, str):
    code = code.decode("utf-8")
code = code.replace("\r\n", "\n")
if "log(\"DONE." not in code:
    frappe.throw("The uploaded file looks incomplete (no DONE line at the end). Upload it again.")

PREFIX = """# runs the uploaded installer - only System Manager / Administrator
if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
    frappe.throw("Not allowed")
RUN_LOG = []
def log(*args, buf=RUN_LOG):
    buf.append(" ".join([str(x) for x in args]))
"""
SUFFIX = """
frappe.db.commit()
frappe.db.set_value("Server Script", "SBI Run Installer", "disabled", 1)
frappe.db.commit()
frappe.response["message"] = RUN_LOG
"""
if frappe.db.exists("Server Script", "SBI Run Installer"):
    ss = frappe.get_doc("Server Script", "SBI Run Installer")
else:
    ss = frappe.new_doc("Server Script")
    ss.name = "SBI Run Installer"
    ss.flags.is_new_doc = True
ss.script_type = "API"
ss.api_method = "sbi_run_installer"
ss.allow_guest = 0
ss.disabled = 0
ss.script = PREFIX + code + SUFFIX
if ss.flags.is_new_doc:
    ss.insert(ignore_permissions=True)
else:
    ss.save(ignore_permissions=True)
frappe.db.commit()
log("Loaded " + rows[0].file_name + " (" + str(len(code)) + " characters, uploaded " + str(rows[0].creation)[:16] + ")")
log("NOW OPEN THIS LINK in the same browser:  " + frappe.utils.get_url("/api/method/sbi_run_installer"))
log("When it shows a list ending with DONE, the install is finished. (The link switches itself off after one run.)")
