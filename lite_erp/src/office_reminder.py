# SBI Office - punch reminders. Runs every 5 minutes (Scheduler Event, cron */5 * * * *).
# Sends a bell notification (and the user's notification e-mail) N minutes before office start / end
# to staff who have not punched IN yet, or who are still punched IN near the end of the day.
def_val = {"in": "", "out": "", "rem": 15, "name": "the office"}
hm = frappe.get_meta("HR Settings")
for pair in [["in", "sbi_office_in_time"], ["out", "sbi_office_out_time"], ["rem", "sbi_reminder_minutes"], ["name", "sbi_office_name"]]:
    if hm.has_field(pair[1]):
        v = frappe.db.get_single_value("HR Settings", pair[1])
        if v not in (None, ""):
            def_val[pair[0]] = v
rem = frappe.utils.cint(def_val["rem"])
now = frappe.utils.now_datetime()
today = frappe.utils.nowdate()
jobs = []
for pair in [["IN", def_val["in"]], ["OUT", def_val["out"]]]:
    tp = str(pair[1] or "").split(":")
    if rem <= 0 or not tp[0]:
        continue
    hhmm = ("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2]
    at = frappe.utils.get_datetime(today + " " + hhmm + ":00")
    send_at = frappe.utils.add_to_date(at, minutes=-rem)
    gap = frappe.utils.time_diff_in_seconds(now, send_at)
    if gap >= 0 and gap < 300:
        jobs.append([pair[0], hhmm])
for job in jobs:
    lt = job[0]
    hhmm = job[1]
    staff = frappe.db.sql("""select e.name, e.employee_name, e.user_id, e.company, ifnull(e.holiday_list, '') holiday_list,
        (select c.log_type from `tabEmployee Checkin` c where c.employee = e.name and date(c.time) = %s order by c.time desc limit 1) last_type
        from `tabEmployee` e join `tabUser` u on u.name = e.user_id and u.enabled = 1
        where e.status = 'Active' and ifnull(e.user_id, '') != ''""", today, as_dict=1)
    sent = 0
    for e in staff:
        if lt == "IN" and e.last_type:
            continue
        if lt == "OUT" and e.last_type != "IN":
            continue
        hl = e.holiday_list or frappe.db.get_value("Company", e.company, "default_holiday_list")
        if hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": today}):
            continue
        if frappe.db.exists("DocType", "Leave Application") and frappe.db.sql("""select name from `tabLeave Application` where employee=%s and docstatus=1
                and status='Approved' and %s between from_date and to_date limit 1""", (e.name, today)):
            continue
        if lt == "IN":
            subj = "Punch IN reminder: office starts at " + hhmm + ". Open SBI Office and punch IN."
        else:
            subj = "Punch OUT reminder: office ends at " + hhmm + ". Open SBI Office and punch OUT before you leave."
        if frappe.db.exists("Notification Log", {"for_user": e.user_id, "subject": subj, "creation": [">=", today + " 00:00:00"]}):
            continue
        frappe.get_doc({"doctype": "Notification Log", "for_user": e.user_id, "from_user": "Administrator", "type": "Alert",
            "subject": subj, "email_content": subj + "<br><br><a href='/sbi_office'>Open SBI Office</a>"}).insert(ignore_permissions=True)
        sent = sent + 1
    frappe.db.commit()
