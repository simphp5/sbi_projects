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


# ----------------------------------------------------------------------
# roster
# ----------------------------------------------------------------------

@frappe.whitelist()
def get_site_roster(project):
	"""Everyone who can punch at this site, with today's status."""
	_check_site_access(project)

	labour = frappe.get_all(
		"Labour",
		filters={"is_active": 1},
		or_filters=[["default_site", "=", project], ["default_site", "in", ("", None)]],
		fields=["name", "labour_name", "gender", "skill_category", "photo",
		        "sbi_wage_type", "sbi_wage_rate"],
		order_by="labour_name asc",
	)

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

	for l in labour:
		l["last_punch"] = status.get(l.name)
		l["enrolled"] = bool(frappe.db.get_value("Labour", l.name, "face_embedding"))

	return labour


# ----------------------------------------------------------------------
# enrollment
# ----------------------------------------------------------------------

@frappe.whitelist()
def enroll_labour(labour_name, gender, embedding, photo=None, project=None,
                  phone=None, skill_category=None, wage_type=None, wage_rate=None):
	"""Create a labour record and store the face vector. Called once per person."""
	if project:
		_check_site_access(project)

	vector = _parse_embedding(embedding)

	doc = frappe.new_doc("Labour")
	doc.labour_name = (labour_name or "").strip()
	doc.gender = gender
	doc.phone = phone
	doc.skill_category = skill_category
	doc.default_site = project
	doc.is_active = 1
	doc.face_embedding = json.dumps(vector)
	doc.enrolled_on = now_datetime()
	doc.enrolled_by = frappe.session.user

	if doc.meta.has_field("sbi_wage_type"):
		doc.sbi_wage_type = wage_type
		doc.sbi_wage_rate = flt(wage_rate)

	doc.insert(ignore_permissions=True)

	if photo:
		url = _save_photo(photo, "Labour", doc.name, f"labour-{doc.name}.jpg")
		doc.db_set("photo", url, update_modified=False)

	return {"labour": doc.name, "labour_name": doc.labour_name}


@frappe.whitelist()
def re_enroll_face(labour, embedding, photo=None):
	"""Replace a stored face vector, e.g. after a bad first capture."""
	vector = _parse_embedding(embedding)
	doc = frappe.get_doc("Labour", labour)
	doc.db_set("face_embedding", json.dumps(vector), update_modified=False)
	doc.db_set("enrolled_on", now_datetime(), update_modified=False)
	doc.db_set("enrolled_by", frappe.session.user, update_modified=False)
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
		"labour_name": frappe.db.get_value("Labour", labour, "labour_name"),
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

	filters = {"is_active": 1, "face_embedding": ("is", "set")}
	candidates = frappe.get_all("Labour", filters=filters,
	                            fields=["name", "labour_name", "face_embedding"])

	best = None
	for row in candidates:
		try:
			stored = json.loads(row.face_embedding)
		except (TypeError, ValueError):
			continue
		score = cosine_similarity(vector, stored)
		if best is None or score > best["score"]:
			best = {"labour": row.name, "labour_name": row.labour_name, "score": score}

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