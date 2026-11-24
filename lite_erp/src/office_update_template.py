# SBI Office – quick update (app page, icons, install-as-app file). System Console -> Python -> tick Commit -> Execute.
OFFICE_HTML = r'''__OFFICE_HTML__'''
OFFICE_CSS = r'''__OFFICE_CSS__'''
OFFICE_JS = r'''__OFFICE_JS__'''
ICON_180 = '__ICON_180__'
ICON_192 = '__ICON_192__'
ICON_512 = '__ICON_512__'
wp_name = frappe.db.get_value("Web Page", {"route": "sbi_office"}, "name")
if not wp_name:
    frappe.throw("SBI Office page not found. Run the full lite_erp_console.py installer once first.")
wp = frappe.get_doc("Web Page", wp_name)
wp.main_section_html = OFFICE_HTML
wp.css = OFFICE_CSS
wp.insert_style = 1
wp.javascript = OFFICE_JS
wp.save(ignore_permissions=True)
log("app page updated: /sbi_office")
for pair in [["sbi_office_icon_180.png", ICON_180], ["sbi_office_icon_192.png", ICON_192], ["sbi_office_icon_512.png", ICON_512]]:
    if frappe.get_all("File", filters={"file_url": "/files/" + pair[0]}, pluck="name"):
        log("icon kept: /files/" + pair[0])
        continue
    idoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1], "decode": True})
    idoc.flags.ignore_permissions = True
    idoc.insert(ignore_permissions=True)
    log("icon saved: " + idoc.file_url)
MANIFEST = '{"name": "SBI Office - Staff Attendance", "short_name": "SBI Office", "id": "/sbi_office", "start_url": "/sbi_office", "scope": "/sbi_office", ' + \
    '"display": "standalone", "orientation": "portrait", "background_color": "#f3f4f6", "theme_color": "#c8102e", ' + \
    '"description": "Punch IN / OUT with selfie and GPS", "icons": [{"src": "/files/sbi_office_icon_192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}, ' + \
    '{"src": "/files/sbi_office_icon_512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}'
if not frappe.get_all("File", filters={"file_url": "/files/sbi_office_manifest_v2.json"}, pluck="name"):
    mdoc = frappe.get_doc({"doctype": "File", "file_name": "sbi_office_manifest_v2.json", "is_private": 0, "content": MANIFEST})
    mdoc.flags.ignore_permissions = True
    mdoc.insert(ignore_permissions=True)
    log("file saved: " + mdoc.file_url)
frappe.db.commit()
log("DONE. Reload SBI Office (Ctrl+Shift+R). On iPhone: Safari -> Share -> Add to Home Screen.")
