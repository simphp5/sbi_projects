# SBI Office - office staff punch IN / OUT with GPS and a stamped selfie (Employee Checkin). App page: /sbi_office
# API method: sbi_office_punch   (any logged-in user; punches only for the Employee linked to that login)
fd = frappe.form_dict
act = fd.get("act") or "status"
user = frappe.session.user
if user == "Guest":
    frappe.throw("Please log in.")
MANAGER_ROLES = ["System Manager", "HR Manager", "HR User", "Business Owner", "Accounts Manager"]
my_roles = []
for r in frappe.db.sql("select role from `tabHas Role` where parenttype='User' and parent=%s", user):
    my_roles.append(r[0])
is_mgr = False
for r in MANAGER_ROLES:
    if r in my_roles:
        is_mgr = True
if user == "Administrator":
    is_mgr = True

# office location and day rules live in HR Settings (set from Lite ERP -> HR -> Salary month & office settings)
OFF = {"name": "", "lat": 0.0, "lng": 0.0, "radius": 200, "block": 1, "in_time": "", "out_time": "", "grace": 10, "reminder": 15}
hm = frappe.get_meta("HR Settings")
for pair in [["name", "sbi_office_name"], ["lat", "sbi_office_latitude"], ["lng", "sbi_office_longitude"], ["radius", "sbi_office_radius"],
        ["block", "sbi_block_outside"], ["in_time", "sbi_office_in_time"], ["out_time", "sbi_office_out_time"], ["grace", "sbi_late_grace"],
        ["reminder", "sbi_reminder_minutes"]]:
    if hm.has_field(pair[1]):
        v = frappe.db.get_single_value("HR Settings", pair[1])
        if v not in (None, ""):
            OFF[pair[0]] = v
OFF["lat"] = frappe.utils.flt(OFF["lat"])
OFF["lng"] = frappe.utils.flt(OFF["lng"])
OFF["radius"] = frappe.utils.cint(OFF["radius"]) or 200
OFF["set"] = 1 if (OFF["lat"] and OFF["lng"]) else 0
OFF["block"] = frappe.utils.cint(OFF["block"])
OFF["grace"] = frappe.utils.cint(OFF["grace"])
OFF["reminder"] = frappe.utils.cint(OFF["reminder"])
for k in ("in_time", "out_time"):
    tp = str(OFF[k] or "").split(":")
    OFF[k] = (("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2]) if tp[0] else ""
PLUS = frappe.get_meta("Employee Checkin").has_field("sbi_within")

ecols = ["name", "employee_name", "designation", "department", "company", "image"]
if frappe.get_meta("Employee").has_field("sbi_punch_anywhere"):
    ecols.append("sbi_punch_anywhere")
FACE = frappe.get_meta("Employee").has_field("sbi_face_front")
if FACE:
    ecols = ecols + ["sbi_face_front", "sbi_face_left", "sbi_face_right", "sbi_face_on"]
ADDR = frappe.get_meta("Employee Checkin").has_field("sbi_address")
by_hr = 0
emp = None
if is_mgr and fd.get("as_employee"):
    # HR / owner / Administrator can open any employee (to punch for them or check their day)
    emp = frappe.db.get_value("Employee", {"name": fd.get("as_employee"), "status": "Active"}, ecols, as_dict=1)
    if emp:
        by_hr = 1
if not emp:
    emp = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, ecols, as_dict=1)
if emp:
    emp["anywhere"] = frappe.utils.cint(emp.get("sbi_punch_anywhere"))
    emp["by_hr"] = by_hr
    emp["enrolled"] = 1 if (not FACE or (emp.get("sbi_face_front") and emp.get("sbi_face_left") and emp.get("sbi_face_right"))) else 0
    emp["sbi_face_on"] = str(emp.get("sbi_face_on") or "")[:16]
today = frappe.utils.nowdate()
logo = frappe.db.get_single_value("Navbar Settings", "app_logo") or frappe.db.get_single_value("Website Settings", "app_logo") or ""
out = {"user": user, "is_manager": 1 if is_mgr else 0, "office": OFF, "employee": emp, "server_time": str(frappe.utils.now_datetime())[:19], "logo": logo}

if act == "punch":
    if not emp:
        frappe.throw("Your login is not linked to an active Employee. Ask HR to put your login (User ID) on your Employee record.")
    lt = fd.get("log_type") or ""
    if lt not in ("IN", "OUT"):
        frappe.throw("Choose IN or OUT.")
    last = frappe.db.sql("select log_type, time from `tabEmployee Checkin` where employee=%s and date(time)=%s order by time desc limit 1", (emp.name, today), as_dict=1)
    expect = "OUT" if (last and last[0].log_type == "IN") else "IN"
    if lt != expect:
        frappe.throw("You are already punched " + lt + ". Your next punch is " + expect + ". Reload the page.")
    if last and frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), last[0].time) < 60:
        frappe.throw("You punched less than a minute ago. Please wait a minute.")
    lat = frappe.utils.flt(fd.get("latitude"))
    lng = frappe.utils.flt(fd.get("longitude"))
    acc = frappe.utils.flt(fd.get("accuracy"))
    dist = 0.0
    within = 1
    if lat and lng and OFF["set"]:
        # short-distance (equirectangular) formula with a series for cos - no math module in server scripts
        k = 3.141592653589793 / 180.0
        mid = (lat + OFF["lat"]) / 2.0 * k
        c = 1 - mid ** 2 / 2 + mid ** 4 / 24 - mid ** 6 / 720 + mid ** 8 / 40320
        dx = (lng - OFF["lng"]) * k * c
        dy = (lat - OFF["lat"]) * k
        dist = round(6371000.0 * (dx * dx + dy * dy) ** 0.5, 1)
        within = 1 if dist <= OFF["radius"] + min(acc, 100) else 0
    if OFF["block"] and OFF["set"] and not emp.anywhere and not by_hr:
        if not (lat and lng):
            frappe.throw("Your location is needed to punch. Turn on location (GPS) and allow it for this app.")
        if not within:
            frappe.throw("You are " + str(int(dist)) + " m from " + (OFF["name"] or "the office") + ". Punch is allowed only within " + str(OFF["radius"]) + " m. Come inside the office and try again.")
    if FACE and not emp.enrolled:
        frappe.throw("Take the face photos (front, left and right) once before the first punch.")
    doc = {"doctype": "Employee Checkin", "employee": emp.name, "log_type": lt, "time": frappe.utils.now_datetime(),
        "device_id": ("Office Punch " + (fd.get("device") or "web"))[:120]}
    if lat and lng:
        doc["latitude"] = lat
        doc["longitude"] = lng
    if PLUS:
        doc["sbi_distance"] = dist
        doc["sbi_within"] = within
        doc["sbi_accuracy"] = acc
        doc["sbi_remarks"] = ((("Punched by " + user + ". ") if by_hr else "") + (fd.get("remarks") or ""))[:500]
        doc["sbi_source"] = "SBI Office (by HR)" if by_hr else "SBI Office"
    if ADDR:
        doc["sbi_address"] = (fd.get("address") or "")[:500]
    ck = frappe.get_doc(doc)
    ck.flags.ignore_permissions = True
    ck.insert(ignore_permissions=True)
    photo = fd.get("photo") or ""
    url = ""
    if photo and "," in photo:
        f = frappe.get_doc({"doctype": "File", "file_name": emp.name + "-" + lt + "-" + str(frappe.utils.now_datetime())[:19].replace(" ", "_").replace(":", "") + ".jpg",
            "attached_to_doctype": "Employee Checkin", "attached_to_name": ck.name, "content": photo.split(",", 1)[1], "decode": True, "is_private": 0})
        f.flags.ignore_permissions = True
        f.insert(ignore_permissions=True)
        url = f.file_url
        if PLUS:
            frappe.db.set_value("Employee Checkin", ck.name, "sbi_photo", url)
    late = 0
    if lt == "IN" and not last and OFF["in_time"]:
        lim = frappe.utils.add_to_date(frappe.utils.get_datetime(today + " " + OFF["in_time"] + ":00"), minutes=OFF["grace"])
        if ck.time > lim:
            late = int(frappe.utils.time_diff_in_seconds(ck.time, frappe.utils.get_datetime(today + " " + OFF["in_time"] + ":00")) / 60)
    early = 0
    if lt == "OUT" and OFF["out_time"]:
        endt = frappe.utils.get_datetime(today + " " + OFF["out_time"] + ":00")
        if ck.time < endt:
            early = int(frappe.utils.time_diff_in_seconds(endt, ck.time) / 60)
    out["punched"] = {"name": ck.name, "log_type": lt, "time": str(ck.time)[11:16], "distance": dist, "within": within, "photo": url, "late": late, "early": early}

if act == "set_office":
    if not is_mgr:
        frappe.throw("Only HR or the owner can set the office location.")
    la = frappe.utils.flt(fd.get("latitude"))
    lo = frappe.utils.flt(fd.get("longitude"))
    if not la or not lo:
        frappe.throw("No location from the phone yet.")
    if not hm.has_field("sbi_office_latitude"):
        frappe.throw("Run the Lite ERP installer again (office fields are missing).")
    frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_latitude", la)
    frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_longitude", lo)
    if fd.get("radius"):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_radius", max(20, frappe.utils.cint(fd.get("radius"))))
    if hm.has_field("sbi_block_outside") and fd.get("block") not in (None, ""):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_block_outside", 1 if str(fd.get("block")) in ("1", "true") else 0)
    if fd.get("office_name"):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_name", fd.get("office_name")[:140])
    OFF["name"] = fd.get("office_name") or OFF["name"]
    OFF["lat"] = la
    OFF["lng"] = lo
    OFF["radius"] = max(20, frappe.utils.cint(fd.get("radius") or OFF["radius"]))
    OFF["set"] = 1
    out["office"] = OFF

if act == "enroll":
    if not emp:
        frappe.throw("Your login is not linked to an employee.")
    if not FACE:
        frappe.throw("Run the Lite ERP installer again: Employee has no face photo fields yet.")
    if emp.enrolled and not is_mgr:
        frappe.throw("Your face photos are already saved. Ask HR if they must be taken again.")
    saved = {}
    stamp = str(frappe.utils.now_datetime())[:19].replace(" ", "_").replace(":", "")
    for side in ["front", "left", "right"]:
        ph = fd.get("photo_" + side) or ""
        if "," not in ph:
            frappe.throw("The " + side + " photo is missing. Take all three photos.")
        fdoc = frappe.get_doc({"doctype": "File", "file_name": emp.name + "-face-" + side + "-" + stamp + ".jpg", "attached_to_doctype": "Employee",
            "attached_to_name": emp.name, "attached_to_field": "sbi_face_" + side, "content": ph.split(",", 1)[1], "decode": True, "is_private": 1})
        fdoc.flags.ignore_permissions = True
        fdoc.insert(ignore_permissions=True)
        saved["sbi_face_" + side] = fdoc.file_url
    for k in saved:
        frappe.db.set_value("Employee", emp.name, k, saved[k])
    frappe.db.set_value("Employee", emp.name, "sbi_face_on", frappe.utils.now_datetime())
    emp["enrolled"] = 1
    emp["sbi_face_front"] = saved["sbi_face_front"]
    emp["sbi_face_left"] = saved["sbi_face_left"]
    emp["sbi_face_right"] = saved["sbi_face_right"]
    emp["sbi_face_on"] = str(frappe.utils.now_datetime())[:16]
    out["employee"] = emp
    out["enrolled"] = 1

if act == "reset_face":
    if not is_mgr:
        frappe.throw("Only HR, the owner or Administrator can reset face photos.")
    if emp and FACE:
        for k in ["sbi_face_front", "sbi_face_left", "sbi_face_right", "sbi_face_on"]:
            frappe.db.set_value("Employee", emp.name, k, None)
            emp[k] = ""
        emp["enrolled"] = 0
        out["employee"] = emp

if act == "save_settings":
    if not is_mgr:
        frappe.throw("Only HR, the owner or Administrator can change settings.")
    vals = {}
    if fd.get("start_day") not in (None, ""):
        sd = frappe.utils.cint(fd.get("start_day"))
        if sd < 1 or sd > 28:
            frappe.throw("The salary month must start on a day from 1 to 28.")
        vals["sbi_salary_start_day"] = sd
    for pair in [["in_time", "sbi_office_in_time"], ["out_time", "sbi_office_out_time"]]:
        tv = (fd.get(pair[0]) or "").strip()
        if tv:
            tp = tv.split(":")
            if len(tp) < 2 or not tp[0].isdigit() or not tp[1][:2].isdigit() or int(tp[0]) > 23 or int(tp[1][:2]) > 59:
                frappe.throw("Office time " + tv + " is not valid. Use HH:MM, for example 09:30.")
            vals[pair[1]] = ("0" + tp[0])[-2:] + ":" + tp[1][:2] + ":00"
    if vals.get("sbi_office_in_time") and vals.get("sbi_office_out_time") and vals["sbi_office_out_time"] <= vals["sbi_office_in_time"]:
        frappe.throw("Office end time must be after the start time.")
    if fd.get("grace") not in (None, ""):
        vals["sbi_late_grace"] = max(0, min(240, frappe.utils.cint(fd.get("grace"))))
    if fd.get("reminder") not in (None, ""):
        vals["sbi_reminder_minutes"] = max(0, min(120, frappe.utils.cint(fd.get("reminder"))))
    if fd.get("radius") not in (None, ""):
        vals["sbi_office_radius"] = max(20, frappe.utils.cint(fd.get("radius")))
    if fd.get("block") not in (None, ""):
        vals["sbi_block_outside"] = 1 if str(fd.get("block")) in ("1", "true") else 0
    if fd.get("office_name") not in (None, ""):
        vals["sbi_office_name"] = fd.get("office_name")[:140]
    for k in vals:
        if not hm.has_field(k):
            frappe.throw("Run the Lite ERP installer again: HR Settings has no field " + k + ".")
    for k in vals:
        frappe.db.set_value("HR Settings", "HR Settings", k, vals[k])
    m = {"sbi_office_in_time": "in_time", "sbi_office_out_time": "out_time", "sbi_late_grace": "grace", "sbi_reminder_minutes": "reminder",
        "sbi_office_radius": "radius", "sbi_block_outside": "block", "sbi_office_name": "name"}
    for k in vals:
        if m.get(k):
            OFF[m[k]] = vals[k] if k not in ("sbi_office_in_time", "sbi_office_out_time") else vals[k][:5]
    out["office"] = OFF
    out["saved"] = 1

# today's punches for me
cols = "name, log_type, time, latitude, longitude" + (", ifnull(sbi_distance, 0) distance, ifnull(sbi_within, 1) within, ifnull(sbi_photo, '') photo" if PLUS else "") + (", ifnull(sbi_address, '') address" if ADDR else "")
if emp:
    logs = frappe.db.sql("select " + cols + " from `tabEmployee Checkin` where employee=%s and date(time)=%s order by time", (emp.name, today), as_dict=1)
    for l in logs:
        l["t"] = str(l.time)[11:16]
    out["logs"] = logs
    out["next"] = "OUT" if (logs and logs[-1].log_type == "IN") else "IN"
    first_in = ""
    last_out = ""
    for l in logs:
        if l.log_type == "IN" and not first_in:
            first_in = l.time
        if l.log_type == "OUT":
            last_out = l.time
    out["hours"] = round(frappe.utils.time_diff_in_hours(last_out, first_in), 2) if (first_in and last_out and last_out > first_in) else 0
    out["is_holiday"] = 0
    hl = frappe.db.get_value("Employee", emp.name, "holiday_list") or frappe.db.get_value("Company", emp.company, "default_holiday_list")
    if hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": today}):
        out["is_holiday"] = 1
    out["tomorrow_holiday"] = 1 if (hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": frappe.utils.add_days(today, 1)})) else 0
    out["month"] = frappe.db.sql("""select count(distinct date(time)) days from `tabEmployee Checkin` where employee=%s and log_type='IN'
        and time >= %s""", (emp.name, frappe.utils.get_first_day(today)), as_dict=1)[0].days

# my salary month (start day from HR Settings)
if act == "month" and emp:
    sd = 1
    if hm.has_field("sbi_salary_start_day"):
        sd = frappe.utils.cint(frappe.db.get_single_value("HR Settings", "sbi_salary_start_day")) or 1
    sd = max(1, min(28, sd))
    back = frappe.utils.cint(fd.get("back"))
    base = frappe.utils.add_months(today, -back)
    if sd == 1:
        mf = str(frappe.utils.get_first_day(base))
    else:
        if frappe.utils.getdate(base).day < sd:
            base = frappe.utils.add_months(base, -1)
        mf = str(base)[:8] + ("0" + str(sd))[-2:]
    mt = str(frappe.utils.add_days(frappe.utils.add_months(mf, 1), -1))
    rows = frappe.db.sql("""select date(time) d, min(case when log_type='IN' then time end) first_in, max(case when log_type='OUT' then time end) last_out,
        count(*) punches""" + (", sum(case when ifnull(sbi_within, 1)=0 then 1 else 0 end) outside" if PLUS else ", 0 outside") + """
        from `tabEmployee Checkin` where employee=%s and date(time) between %s and %s group by date(time) order by d desc""", (emp.name, mf, mt), as_dict=1)
    tot = 0.0
    late = 0
    for r in rows:
        h = 0.0
        if r.first_in and r.last_out and r.last_out > r.first_in:
            h = round(frappe.utils.time_diff_in_hours(r.last_out, r.first_in), 2)
        r["hours"] = h
        tot = tot + h
        r["late"] = 0
        if OFF["in_time"] and r.first_in and r.first_in > frappe.utils.add_to_date(frappe.utils.get_datetime(str(r.d) + " " + OFF["in_time"] + ":00"), minutes=OFF["grace"]):
            r["late"] = 1
            late = late + 1
        r["first_in"] = str(r.first_in or "")[11:16]
        r["last_out"] = str(r.last_out or "")[11:16]
        r["d"] = str(r.d)
    out["month_view"] = {"from": mf, "to": mt, "days": rows, "hours": round(tot, 2), "late": late, "back": back}

# first login: the default password must be changed in Lite ERP before punching
if act == "status" and frappe.get_meta("User").has_field("sbi_must_change_password") and frappe.db.get_value("User", user, "sbi_must_change_password"):
    out["must_change"] = 1

# team today for HR / owner
if is_mgr:
    own = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "employee_name")
    out["own_employee"] = own or ""
    sdv = frappe.db.get_single_value("HR Settings", "sbi_salary_start_day") if hm.has_field("sbi_salary_start_day") else 1
    out["start_day"] = frappe.utils.cint(sdv) or 1
    out["staff"] = frappe.db.sql("select name, employee_name, designation from `tabEmployee` where status='Active' order by employee_name", as_dict=1)
if is_mgr and act in ("status", "punch", "set_office", "save_settings"):
    team = frappe.db.sql("""select e.name employee, e.employee_name, e.designation, ifnull(e.user_id, '') user_id,
        min(case when c.log_type='IN' then c.time end) first_in, max(case when c.log_type='OUT' then c.time end) last_out,
        substring_index(group_concat(c.log_type order by c.time desc separator '|'), '|', 1) last_type, count(c.name) punches
        """ + (", sum(case when ifnull(c.sbi_within, 1)=0 then 1 else 0 end) outside, max(ifnull(c.sbi_distance, 0)) max_dist" if PLUS else ", 0 outside, 0 max_dist") + """
        from `tabEmployee` e left join `tabEmployee Checkin` c on c.employee = e.name and date(c.time)=%s
        where e.status='Active' group by e.name order by (count(c.name)=0), e.employee_name""", today, as_dict=1)
    for t in team:
        t["first_in"] = str(t.first_in or "")[11:16]
        t["last_out"] = str(t.last_out or "")[11:16]
    out["team"] = team

frappe.response["message"] = out
