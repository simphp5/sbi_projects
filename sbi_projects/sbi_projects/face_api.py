"""Clean face-attendance API for the SBI site app.

One module, one job: enroll faces, match faces, record punches.  Matching uses
Euclidean distance on face-api's 128-d descriptors, which is the metric the
model was trained for â€” same person sits well below 0.5, different people above
0.6.  Everything is scoped to a project so a worker enrolled at one site is not
matched at another.
"""

import json
import frappe
from frappe.utils import flt, now_datetime, today, get_datetime


# ---- tuning -----------------------------------------------------------------
MATCH_THRESHOLD = 0.50       # <= this distance -> confident same person
DUPLICATE_THRESHOLD = 0.50   # enrolling: block if this close to an existing face
# -----------------------------------------------------------------------------


def _euclidean(a, b):
	if not a or not b or len(a) != len(b):
		return 999.0
	total = 0.0
	for i in range(len(a)):
		d = a[i] - b[i]
		total += d * d
	return total ** 0.5


def _parse(emb):
	if isinstance(emb, str):
		try:
			return json.loads(emb)
		except Exception:
			return None
	return emb


def _enrolled_faces(project=None):
	"""All enrolled faces (Labour + Employee), optionally scoped to a project."""
	out = []

	lf = {"face_enrolled": 1, "status": "Active"}
	if project:
		lf["default_project"] = project
	for r in frappe.get_all("Labour", filters=lf,
		fields=["name", "labour_name", "face_embedding", "photo"]):
		emb = _parse(r.face_embedding)
		if emb:
			out.append({"type": "Labour", "id": r.name, "name": r.labour_name,
			            "embedding": emb, "photo": r.photo})

	em = frappe.get_meta("Employee")
	if em.has_field("sbi_face_embedding"):
		ef = {"sbi_face_enrolled": 1, "status": "Active"}
		if project and em.has_field("sbi_default_project"):
			ef["sbi_default_project"] = project
		fields = ["name", "employee_name", "sbi_face_embedding"]
		if em.has_field("sbi_face_photo"):
			fields.append("sbi_face_photo")
		for r in frappe.get_all("Employee", filters=ef, fields=fields):
			emb = _parse(r.sbi_face_embedding)
			if emb:
				out.append({"type": "Employee", "id": r.name,
				            "name": r.employee_name, "embedding": emb,
				            "photo": r.get("sbi_face_photo")})
	return out


def _best_match(embedding, project=None):
	"""Closest enrolled face and its distance."""
	best, best_d = None, 999.0
	for rec in _enrolled_faces(project):
		d = _euclidean(embedding, rec["embedding"])
		if d < best_d:
			best_d, best = d, rec
	return best, best_d


@frappe.whitelist()
def match(embedding, project=None):
	"""Return the matched worker only if within the distance threshold."""
	embedding = _parse(embedding)
	if not embedding:
		return None
	best, dist = _best_match(embedding, project)
	if best and dist <= MATCH_THRESHOLD:
		return {
			"type": best["type"], "id": best["id"], "name": best["name"],
			"distance": round(dist, 3),
			"confidence": round(max(0.0, 1.0 - dist / 0.6), 3),
		}
	return None


@frappe.whitelist()
def enroll(worker_type, name, embedding, photo=None, project=None,
           gender=None, skill=None, wage_type=None, wage_rate=0, phone=None):
	"""Create a Labour or Employee with a face, blocking duplicates everywhere."""
	embedding = _parse(embedding)
	if not embedding or len(embedding) != 128:
		frappe.throw("Face capture was not clear. Please try again.")

	# duplicate guard across ALL sites
	best, dist = _best_match(embedding, project=None)
	if best and dist <= DUPLICATE_THRESHOLD:
		return {"duplicate": True, "type": best["type"], "id": best["id"],
		        "name": best["name"], "distance": round(dist, 3)}

	emb_json = json.dumps(embedding)

	if worker_type == "Employee":
		doc = frappe.new_doc("Employee")
		doc.employee_name = name
		doc.first_name = name
		if gender and doc.meta.has_field("gender"):
			doc.gender = gender
		doc.status = "Active"
		if doc.meta.has_field("date_of_joining"):
			doc.date_of_joining = today()
		if doc.meta.has_field("company"):
			doc.company = (frappe.defaults.get_user_default("company")
			               or frappe.db.get_single_value("Global Defaults", "default_company"))
		doc.sbi_face_embedding = emb_json
		doc.sbi_face_enrolled = 1
		doc.sbi_enrolled_on = now_datetime()
		if project and doc.meta.has_field("sbi_default_project"):
			doc.sbi_default_project = project
		if photo and doc.meta.has_field("sbi_face_photo"):
			doc.sbi_face_photo = _save_photo(photo, "Employee", name)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		wid = doc.name
	else:
		doc = frappe.new_doc("Labour")
		doc.labour_name = name
		if gender:
			doc.gender = gender
		doc.status = "Active"
		if skill and doc.meta.has_field("skill"):
			doc.skill = skill
		if phone and doc.meta.has_field("mobile_no"):
			doc.mobile_no = phone
		if wage_type and doc.meta.has_field("sbi_wage_type"):
			doc.sbi_wage_type = wage_type
		if wage_rate and doc.meta.has_field("sbi_wage_rate"):
			doc.sbi_wage_rate = flt(wage_rate)
		if project and doc.meta.has_field("default_project"):
			doc.default_project = project
		if doc.meta.has_field("date_of_joining"):
			doc.date_of_joining = today()
		doc.face_embedding = emb_json
		doc.face_enrolled = 1
		doc.enrolled_on = now_datetime()
		if photo and doc.meta.has_field("photo"):
			doc.photo = _save_photo(photo, "Labour", name)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		wid = doc.name

	frappe.db.commit()
	return {"type": worker_type, "id": wid, "name": name}


def _save_photo(data_url, doctype, docname):
	"""Save a base64 data URL as a File attached to the record; return its URL."""
	import base64
	if not data_url or "," not in data_url:
		return None
	header, b64 = data_url.split(",", 1)
	content = base64.b64decode(b64)
	fname = frappe.utils.random_string(8) + ".jpg"
	f = frappe.get_doc({
		"doctype": "File", "file_name": fname,
		"attached_to_doctype": doctype, "attached_to_name": docname,
		"content": content, "decode": False, "is_private": 0,
	})
	f.flags.ignore_permissions = True
	f.insert(ignore_permissions=True)
	return f.file_url


# ---- attendance -------------------------------------------------------------

_SEQUENCE = ["IN", "LUNCH OUT", "LUNCH IN", "OUT"]


def _worker_field_values(worker_type, worker_id):
	if worker_type == "Employee":
		name = frappe.db.get_value("Employee", worker_id, "employee_name")
		return {"employee": worker_id, "worker_type": "Employee", "labour_name": name}
	name = frappe.db.get_value("Labour", worker_id, "labour_name")
	return {"labour": worker_id, "worker_type": "Labour", "labour_name": name}


@frappe.whitelist()
def day_status(worker_type, worker_id, project=None):
	"""Today's punches for a worker and what the next allowed punch is."""
	filters = {"log_date": today()}
	if worker_type == "Employee":
		filters["employee"] = worker_id
	else:
		filters["labour"] = worker_id

	punches = frappe.get_all("Labour Attendance Log", filters=filters,
		fields=["log_type", "log_datetime"], order_by="log_datetime asc")
	done = [p.log_type for p in punches]
	next_punch = None
	for step in _SEQUENCE:
		if step not in done:
			next_punch = step
			break
	return {
		"punches": [{"log_type": p.log_type,
		             "time": str(p.log_datetime)[11:16]} for p in punches],
		"next": next_punch,
		"finished": next_punch is None,
	}


@frappe.whitelist()
def punch(worker_type, worker_id, project, log_type,
          latitude=None, longitude=None, photo=None):
	"""Record one punch with the entry time; block a repeat of the same type."""
	existing = {"log_date": today(), "log_type": log_type}
	if worker_type == "Employee":
		existing["employee"] = worker_id
	else:
		existing["labour"] = worker_id
	if frappe.db.exists("Labour Attendance Log", existing):
		name = frappe.db.get_value(
			"Employee" if worker_type == "Employee" else "Labour",
			worker_id, "employee_name" if worker_type == "Employee" else "labour_name")
		return {"already": True, "name": name, "log_type": log_type}

	vals = _worker_field_values(worker_type, worker_id)
	doc = frappe.new_doc("Labour Attendance Log")
	doc.update(vals)
	doc.project = project
	doc.log_type = log_type
	doc.log_datetime = now_datetime()
	doc.log_date = today()

	# geo-fence: record distance, never block
	if latitude and longitude and doc.meta.has_field("latitude"):
		doc.latitude = flt(latitude)
		doc.longitude = flt(longitude)
		fence = _fence(project)
		if fence:
			dist = _haversine(flt(latitude), flt(longitude), fence["lat"], fence["lng"])
			if doc.meta.has_field("distance_from_site"):
				doc.distance_from_site = dist
			if doc.meta.has_field("within_geofence"):
				doc.within_geofence = 1 if dist <= fence["radius"] else 0

	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "name": vals["labour_name"], "log_type": log_type,
	        "time": str(doc.log_datetime)[11:16],
	        "within_geofence": getattr(doc, "within_geofence", 1),
	        "distance": getattr(doc, "distance_from_site", 0)}


def _fence(project):
	d = frappe.db.get_value("Project", project,
		["sbi_site_latitude", "sbi_site_longitude", "sbi_geofence_radius"], as_dict=True)
	if not d or not d.sbi_site_latitude or not d.sbi_site_longitude:
		return None
	return {"lat": flt(d.sbi_site_latitude), "lng": flt(d.sbi_site_longitude),
	        "radius": int(d.sbi_geofence_radius or 200)}


def _haversine(lat1, lng1, lat2, lng2):
	from math import radians, sin, cos, atan2, sqrt
	R = 6371000
	dlat = radians(lat2 - lat1)
	dlng = radians(lng2 - lng1)
	a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
	return R * 2 * atan2(sqrt(a), sqrt(1 - a))


@frappe.whitelist()
def roster(project):
	"""Who is enrolled at this site and their current state today."""
	out = []
	for rec in _enrolled_faces(project):
		ds = day_status(rec["type"], rec["id"], project)
		last = ds["punches"][-1]["log_type"] if ds["punches"] else None
		out.append({"type": rec["type"], "id": rec["id"], "name": rec["name"],
		            "photo": rec.get("photo"), "last": last,
		            "on_site": bool(last and last != "OUT")})
	out.sort(key=lambda x: (not x["on_site"], x["name"] or ""))
	return out


@frappe.whitelist()
def enroll_options():
	"""Dropdown values for the enrollment form."""
	def sel(dt, field):
		meta = frappe.get_meta(dt)
		f = meta.get_field(field)
		return [o for o in (f.options or "").split("\n") if o] if f else []
	wage_types = frappe.get_all("Wage Type", pluck="name") \
		if frappe.db.exists("DocType", "Wage Type") else []
	return {
		"gender": ["Male", "Female", "Other"],
		"skill": sel("Labour", "skill"),
		"wage_types": wage_types,
	}


@frappe.whitelist()
def save_aadhaar(worker_type, worker_id, aadhaar_number=None,
                 front_image=None, back_image=None):
	"""Store Aadhaar on a Labour or Employee. Full number is permlevel-1."""
	dt = "Employee" if worker_type == "Employee" else "Labour"
	if not frappe.db.exists(dt, worker_id):
		frappe.throw("Worker not found.")

	num = "".join(ch for ch in (aadhaar_number or "") if ch.isdigit())
	if num and len(num) != 12:
		frappe.throw("An Aadhaar number must be 12 digits.")

	meta = frappe.get_meta(dt)
	pfx = "sbi_aadhaar_" if dt == "Employee" else "aadhaar_"
	updates = {}
	if num:
		if meta.has_field(pfx + "number"):
			updates[pfx + "number"] = num
		if meta.has_field(pfx + "last4"):
			updates[pfx + "last4"] = num[-4:]
	if front_image and meta.has_field(pfx + "front"):
		updates[pfx + "front"] = _save_photo(front_image, dt, worker_id)
	if back_image and meta.has_field(pfx + "back"):
		updates[pfx + "back"] = _save_photo(back_image, dt, worker_id)

	if updates:
		frappe.db.set_value(dt, worker_id, updates, update_modified=True)
		frappe.db.commit()
	return {"saved": True, "last4": num[-4:] if num else None}