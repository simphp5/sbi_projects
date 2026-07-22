"""API used by the site tablet / mobile app.

Face recognition runs on the device: the browser computes an embedding with
MediaPipe and sends the vector here.  The raw image never has to leave the
device for matching, and the server only compares numbers, so this works on a
normal bench with no ML dependencies installed.

The server stays the authority on identity: it re-matches every embedding
against the enrolled roster rather than trusting whatever labour id the device
claims.
"""

import base64
import json
import math

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

# Cosine similarity above which two embeddings are treated as the same person.
# MediaPipe FaceEmbedder vectors typically land around 0.9+ for a true match and
# below 0.5 for different people, so 0.75 leaves a wide margin either side.
DEFAULT_MATCH_THRESHOLD = 0.75

# Enrollment is checked against a slightly looser bar than a punch: it is much
# cheaper to ask "is this the same person?" than to end up with one worker
# holding two records and half their attendance in each.
DUPLICATE_THRESHOLD = 0.68


# ----------------------------------------------------------------------
# roster
# ----------------------------------------------------------------------

# The Labour doctype has been through several revisions and field names differ
# between them, so nothing here is hardcoded.  Each logical field lists the
# names it has gone by; the first one that exists on the live schema wins.
FIELD_ALIASES = {
	"name_field":   ["labour_name"],
	"code":         ["labour_code"],
	"gender":       ["gender"],
	"skill":        ["skill", "skill_category"],
	"phone":        ["mobile_no", "phone"],
	"photo":        ["photo"],
	"status":       ["status", "is_active"],
	"site":         ["default_project", "default_site"],
	"enrolled_flag":["face_enrolled"],
	"embedding":    ["face_embedding"],
	"enrolled_on":  ["enrolled_on"],
	"enrolled_by":  ["enrolled_by"],
	"wage_type":    ["sbi_wage_type"],
	"wage_rate":    ["sbi_wage_rate", "daily_wage"],
	"contractor":   ["contractor"],
}


def _f(key):
	"""Resolve a logical field to whatever it is actually called here."""
	meta = frappe.get_meta("Labour")
	for candidate in FIELD_ALIASES.get(key, []):
		if meta.has_field(candidate):
			return candidate
	return None


def _labour_fields():
	"""Every roster field that exists on this site, in a stable order."""
	keys = ["name_field", "code", "gender", "skill", "phone", "photo",
	        "status", "site", "enrolled_flag", "wage_type", "wage_rate"]
	out = []
	for k in keys:
		f = _f(k)
		if f and f not in out:
			out.append(f)
	return out


def _active_filter():
	"""Filter out inactive labour without guessing what 'active' is called."""
	field = _f("status")
	if not field:
		return {}

	df = frappe.get_meta("Labour").get_field(field)
	if df.fieldtype == "Check":
		return {field: 1}

	options = [o.strip() for o in (df.options or "").split("\n") if o.strip()]
	if "Active" in options:
		return {field: "Active"}
	return {}


@frappe.whitelist()
def get_site_roster(project):
	"""Everyone who can punch at this site, with today's status."""
	_check_site_access(project)

	available = _labour_fields()
	kwargs = {"filters": _active_filter(), "fields": ["name"] + available}

	site_field = _f("site")
	if site_field:
		kwargs["or_filters"] = [[site_field, "=", project],
		                        [site_field, "in", ("", None)]]

	name_field = _f("name_field")
	if name_field:
		kwargs["order_by"] = name_field + " asc"

	labour = frappe.get_all("Labour", **kwargs)

	names = [l.name for l in labour]
	status = {}
	if names:
		rows = frappe.get_all(
			"Labour Attendance Log",
			filters={"labour": ("in", names), "log_date": frappe.utils.today()},
			fields=["labour", "log_type", "log_datetime"],
			order_by="log_datetime asc",
		)
		for r in rows:
			status[r.labour] = r.log_type

	name_field = _f("name_field")
	skill_field = _f("skill")
	for l in labour:
		l["last_punch"] = status.get(l.name)
		l["enrolled"] = bool(frappe.db.get_value("Labour", l.name, "face_embedding"))
		# the app reads labour_name and skill_category whatever the schema calls them
		l["labour_name"] = (l.get(name_field) if name_field else None) or l.name
		l["skill_category"] = l.get(skill_field) if skill_field else None

	return labour


# ----------------------------------------------------------------------
# enrollment
# ----------------------------------------------------------------------

@frappe.whitelist()
def get_enroll_options():
	"""Dropdown values for the enrollment form, read from the live schema.

	Sending a value the Select does not allow fails validation, so the app
	populates its dropdowns from here rather than from a hardcoded list.
	"""
	meta = frappe.get_meta("Labour")

	def options_for(key):
		field = _f(key)
		if not field:
			return []
		df = meta.get_field(field)
		if not df or df.fieldtype != "Select":
			return []
		return [o.strip() for o in (df.options or "").split("\n") if o.strip()]

	return {
		"gender": options_for("gender") or ["Male", "Female", "Other"],
		"skill": options_for("skill"),
		"has_skill": bool(_f("skill")),
		"has_phone": bool(_f("phone")),
		"wage_types": frappe.get_all(
			"Wage Type",
			filters={"is_active": 1} if frappe.get_meta("Wage Type").has_field("is_active") else {},
			pluck="name",
		) if frappe.db.exists("DocType", "Wage Type") else [],
	}

@frappe.whitelist()
def enroll_labour(labour_name, gender, embedding, photo=None, project=None,
                  phone=None, skill_category=None, wage_type=None, wage_rate=None):
	"""Create a labour record and store the face vector. Called once per person."""
	if project:
		_check_site_access(project)

	vector = _parse_embedding(embedding)

	# Refuse a second record for a face that is already enrolled.  Without this
	# the same person can be added twice and their attendance splits in half.
	existing = match_face(vector, project, DUPLICATE_THRESHOLD)
	if existing:
		return {
			"duplicate": True,
			"labour": existing["labour"],
			"labour_name": existing["labour_name"],
			"score": existing["score"],
		}

	wanted = {
		"name_field":   (labour_name or "").strip(),
		"gender":       gender,
		"phone":        phone,
		"skill":        skill_category,
		"site":         project,
		"embedding":    json.dumps(vector),
		"enrolled_flag": 1,
		"enrolled_on":  now_datetime(),
		"enrolled_by":  frappe.session.user,
		"wage_type":    wage_type,
		"wage_rate":    flt(wage_rate) or None,
	}

	payload = {"doctype": "Labour"}
	for key, value in wanted.items():
		field = _f(key)
		if field and value is not None:
			payload[field] = value
	payload.update(_active_filter())

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)

	if photo:
		url = _save_photo(photo, "Labour", doc.name, f"labour-{doc.name}.jpg")
		doc.db_set("photo", url, update_modified=False)

	return {"duplicate": False, "labour": doc.name,
	        "labour_name": _labour_display_name(doc.name)}


@frappe.whitelist()
def re_enroll_face(labour, embedding, photo=None):
	"""Replace a stored face vector, e.g. after a bad first capture."""
	vector = _parse_embedding(embedding)
	doc = frappe.get_doc("Labour", labour)
	doc.db_set(_f("embedding"), json.dumps(vector), update_modified=False)
	for key, value in (("enrolled_flag", 1), ("enrolled_on", now_datetime()),
	                   ("enrolled_by", frappe.session.user)):
		field = _f(key)
		if field:
			doc.db_set(field, value, update_modified=False)
	if photo:
		url = _save_photo(photo, "Labour", labour, f"labour-{labour}.jpg")
		doc.db_set("photo", url, update_modified=False)
	return {"labour": labour, "status": "re-enrolled"}


# ----------------------------------------------------------------------
# punch
# ----------------------------------------------------------------------

@frappe.whitelist()
def punch(project, log_type, embedding=None, labour=None, latitude=None,
          longitude=None, photo=None, device_id=None, threshold=None):
	"""Record one attendance punch.

	Identity comes from the embedding when one is supplied.  A labour id on its
	own is accepted only as a supervisor override and is marked as Manual, so
	the two cases stay distinguishable in the record.
	"""
	_check_site_access(project)

	confidence = None
	method = "Manual"

	if embedding:
		vector = _parse_embedding(embedding)
		match = match_face(vector, project, threshold)
		if not match:
			return {"matched": False,
			        "message": _("No enrolled face matched. Enroll this person first.")}
		labour = match["labour"]
		confidence = match["score"]
		method = "Face"
	elif not labour:
		frappe.throw(_("Either a face embedding or a labour id is required."))

	doc = frappe.new_doc("Labour Attendance Log")
	doc.labour = labour
	doc.project = project
	doc.log_type = log_type
	doc.log_datetime = now_datetime()
	doc.latitude = flt(latitude)
	doc.longitude = flt(longitude)
	doc.verification_method = method
	doc.face_confidence = confidence
	doc.device_id = device_id
	doc.insert(ignore_permissions=True)  # geofence + sequence validated in controller

	if photo:
		url = _save_photo(photo, "Labour Attendance Log", doc.name, f"punch-{doc.name}.jpg")
		doc.db_set("photo", url, update_modified=False)

	return {
		"matched": True,
		"log": doc.name,
		"labour": labour,
		"labour_name": _labour_display_name(labour),
		"log_type": doc.log_type,
		"time": str(doc.log_datetime),
		"confidence": confidence,
		"within_geofence": bool(doc.within_geofence),
		"distance_from_site": doc.distance_from_site,
	}


@frappe.whitelist()
def match_face(embedding, project=None, threshold=None):
	"""Best match for an embedding among enrolled labour."""
	vector = _parse_embedding(embedding)
	threshold = flt(threshold) or DEFAULT_MATCH_THRESHOLD

	embed_field = _f("embedding")
	name_field = _f("name_field")

	filters = {embed_field: ("is", "set")}
	filters.update(_active_filter())

	fields = ["name", embed_field]
	if name_field:
		fields.append(name_field)

	candidates = frappe.get_all("Labour", filters=filters, fields=fields)

	best = None
	for row in candidates:
		try:
			stored = json.loads(row.get(embed_field))
		except (TypeError, ValueError):
			continue
		score = cosine_similarity(vector, stored)
		if best is None or score > best["score"]:
			best = {"labour": row.name,
			        "labour_name": (row.get(name_field) if name_field else None) or row.name,
			        "score": score}

	if not best or best["score"] < threshold:
		return None

	best["score"] = round(best["score"], 4)
	return best


# ----------------------------------------------------------------------
# maths
# ----------------------------------------------------------------------

def cosine_similarity(a, b):
	"""1.0 means identical direction, 0.0 orthogonal, -1.0 opposite."""
	if not a or not b or len(a) != len(b):
		return -1.0

	dot = sum(x * y for x, y in zip(a, b))
	na = math.sqrt(sum(x * x for x in a))
	nb = math.sqrt(sum(y * y for y in b))
	if not na or not nb:
		return -1.0
	return dot / (na * nb)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _labour_display_name(labour):
	field = _f("name_field")
	if field:
		return frappe.db.get_value("Labour", labour, field) or labour
	return labour


def _parse_embedding(embedding):
	if isinstance(embedding, str):
		try:
			embedding = json.loads(embedding)
		except ValueError:
			frappe.throw(_("Face embedding is not valid JSON."))

	if not isinstance(embedding, (list, tuple)) or not embedding:
		frappe.throw(_("Face embedding must be a non-empty list of numbers."))

	try:
		return [float(x) for x in embedding]
	except (TypeError, ValueError):
		frappe.throw(_("Face embedding must contain only numbers."))


def _save_photo(data, doctype, name, filename):
	"""Accepts a data URL or bare base64 and attaches it to the document."""
	if "," in data and data.strip().startswith("data:"):
		data = data.split(",", 1)[1]

	try:
		content = base64.b64decode(data)
	except Exception:
		frappe.throw(_("Photo is not valid base64 data."))

	f = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"attached_to_doctype": doctype,
		"attached_to_name": name,
		"is_private": 1,
		"content": content,
	})
	f.save(ignore_permissions=True)
	return f.file_url


def _check_site_access(project):
	if not project or not frappe.db.exists("Project", project):
		frappe.throw(_("Unknown site: {0}").format(project))

	if frappe.session.user == "Administrator":
		return

	allowed = {"System Manager", "Projects Manager", "Projects User", "Site Cost Approver"}
	if not allowed & set(frappe.get_roles()):
		frappe.throw(_("You are not allowed to record site attendance."),
		             frappe.PermissionError)


# ======================================================================
# Site management endpoints (Batch 2b)
# Cost figures are never returned here -- the site app must not show
# budgets, sale values or variance to site staff.
# ======================================================================

import base64
from frappe.utils import now_datetime, today, flt, getdate


def _can_see_full_aadhaar():
	"""Owner / HR / managers see the full number and images; site staff do not."""
	allowed = {"System Manager", "HR Manager", "HR User",
	           "Projects Manager", "Site Cost Approver", "Administrator"}
	return bool(allowed & set(frappe.get_roles()))


# ----------------------------------------------------------------------
# Aadhaar capture
# ----------------------------------------------------------------------

@frappe.whitelist()
def save_aadhaar(labour, aadhaar_number=None, front_image=None, back_image=None):
	"""Store Aadhaar details for a worker.

	Site staff may capture (so a new worker can be enrolled on site), but the
	full number and images are permlevel-1 fields that only owner/HR can read
	back.  We store the last four digits at permlevel 0 so site staff can still
	confirm identity without exposing the whole number.
	"""
	if not frappe.db.exists("Labour", labour):
		frappe.throw("Worker not found.")

	num = "".join(ch for ch in (aadhaar_number or "") if ch.isdigit())
	if num and len(num) != 12:
		frappe.throw("An Aadhaar number must be 12 digits.")

	meta = frappe.get_meta("Labour")
	updates = {}

	if num:
		if meta.has_field("aadhaar_number"):
			updates["aadhaar_number"] = num
		if meta.has_field("aadhaar_last4"):
			updates["aadhaar_last4"] = num[-4:]

	if front_image and meta.has_field("aadhaar_front"):
		updates["aadhaar_front"] = _save_photo(front_image, "Labour", labour,
		                                        labour + "-aadhaar-front.jpg")
	if back_image and meta.has_field("aadhaar_back"):
		updates["aadhaar_back"] = _save_photo(back_image, "Labour", labour,
		                                       labour + "-aadhaar-back.jpg")

	if updates:
		# bypass permlevel for the write; the caller is allowed to capture even
		# though they will not be able to read the value back afterwards.
		frappe.db.set_value("Labour", labour, updates, update_modified=True)
		frappe.db.commit()

	return {"saved": True, "last4": num[-4:] if num else None}


@frappe.whitelist()
def get_aadhaar_status(labour):
	"""What the current user is allowed to see about a worker's Aadhaar."""
	if not frappe.db.exists("Labour", labour):
		return {}

	meta = frappe.get_meta("Labour")
	last4 = frappe.db.get_value("Labour", labour, "aadhaar_last4") \
		if meta.has_field("aadhaar_last4") else None

	out = {"last4": last4, "has_front": False, "has_back": False, "full": None}
	if meta.has_field("aadhaar_front"):
		out["has_front"] = bool(frappe.db.get_value("Labour", labour, "aadhaar_front"))
	if meta.has_field("aadhaar_back"):
		out["has_back"] = bool(frappe.db.get_value("Labour", labour, "aadhaar_back"))

	if _can_see_full_aadhaar() and meta.has_field("aadhaar_number"):
		out["full"] = frappe.db.get_value("Labour", labour, "aadhaar_number")

	return out


# ----------------------------------------------------------------------
# Daily work log from the app -- progress, holiday, remarks
# ----------------------------------------------------------------------

@frappe.whitelist()
def get_app_menu(project):
	"""Site-facing summary for the app home: today's counts, no cost figures."""
	_check_site_access(project)
	roster = get_site_roster(project)
	present = sum(1 for r in roster if r.get("last_punch") and r["last_punch"] != "OUT")

	return {
		"project": project,
		"project_name": frappe.db.get_value("Project", project, "project_name") or project,
		"headcount": len(roster),
		"present": present,
		"today": frappe.utils.formatdate(today(), "dd MMM yyyy"),
		"stages": _open_stages(project),
	}


def _open_stages(project):
	"""Stage names only -- the app never shows stage budgets."""
	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "is_group": 1},
		fields=["name", "subject", "status"],
		order_by="lft asc" if frappe.get_meta("Task").has_field("lft") else "creation asc",
	)
	return [{"task": t.name, "subject": t.subject, "status": t.status} for t in tasks]


@frappe.whitelist()
def submit_daily_log(project, task=None, log_date=None, is_holiday=0,
                     remarks=None, progress_rows=None, petty_cash=None):
	"""Create a Daily Work Log from the app.

	Accepts progress rows and petty-cash rows.  No cost totals are returned to
	the caller; the owner reviews and approves on the desk.
	"""
	import json
	_check_site_access(project)

	log_date = log_date or today()

	existing = frappe.db.exists("Daily Work Log",
		{"project": project, "task": task, "log_date": log_date})
	if existing:
		doc = frappe.get_doc("Daily Work Log", existing)
	else:
		doc = frappe.new_doc("Daily Work Log")
		doc.project = project
		if task and doc.meta.has_field("task"):
			doc.task = task
		if doc.meta.has_field("log_date"):
			doc.log_date = log_date

	if doc.meta.has_field("sbi_is_holiday"):
		doc.sbi_is_holiday = int(is_holiday or 0)
	if remarks and doc.meta.has_field("remarks"):
		doc.remarks = remarks
	elif remarks and doc.meta.has_field("sbi_remarks"):
		doc.sbi_remarks = remarks

	# progress rows
	if progress_rows and doc.meta.has_field("sbi_progress_rows"):
		rows = json.loads(progress_rows) if isinstance(progress_rows, str) else progress_rows
		doc.set("sbi_progress_rows", [])
		for r in rows:
			doc.append("sbi_progress_rows", {
				"progress_parameter": r.get("parameter"),
				"quantity": flt(r.get("quantity")),
				"remarks": r.get("remarks"),
			})

	# petty cash rows -> other-cost table
	if petty_cash and doc.meta.has_field("sbi_costs"):
		rows = json.loads(petty_cash) if isinstance(petty_cash, str) else petty_cash
		for r in rows:
			doc.append("sbi_costs", {
				"site_cost_category": r.get("category"),
				"description": r.get("description"),
				"amount": flt(r.get("amount")),
			})

	doc.flags.ignore_permissions = True
	doc.save()
	frappe.db.commit()

	return {"name": doc.name, "saved": True}


@frappe.whitelist()
def get_progress_parameters():
	"""Active progress parameters for the app dropdown."""
	if not frappe.db.exists("DocType", "Progress Parameter"):
		return []
	filters = {}
	if frappe.get_meta("Progress Parameter").has_field("is_active"):
		filters["is_active"] = 1
	return frappe.get_all("Progress Parameter", filters=filters,
	                      fields=["name", "parameter_name", "uom"], order_by="parameter_name")


@frappe.whitelist()
def get_petty_cash_categories():
	"""Cost categories a site can spend petty cash against (labels only)."""
	if not frappe.db.exists("DocType", "Site Cost Category"):
		return []
	return frappe.get_all("Site Cost Category", fields=["name"], order_by="name", pluck="name")