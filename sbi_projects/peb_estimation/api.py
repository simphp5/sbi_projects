# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Guest-facing API for the client Building Enquiry portal.

SECURITY MODEL
--------------
Every endpoint here is reachable by unauthenticated (Guest) users, so each one
independently re-validates the caller against the enquiry's access token. There
is no implicit trust: a valid ``(enquiry, token)`` pair is the only credential.

- Tokens are 32-char cryptographic hashes, stored on the enquiry, sent only by
  email. A token grants access to exactly one enquiry.
- Links expire on ``link_expires_on``; expired links are rejected everywhere.
- OTP is OPTIONAL: the client may verify their email for extra trust, but the
  portal works without it. Verification only sets ``client_verified_email``.
- OTP codes are hashed (never stored in clear), expire in 5 minutes, allow 5
  verify attempts, and are rate-limited to 3 sends per email per hour.
- The portal never exposes budgets, rates, costs, or profit -- only the
  parameter questionnaire and the client's own uploads (Q3 principle).

None of these endpoints trust anything in the request beyond the token match.
"""

import os

import frappe
from frappe import _
from frappe.utils import now_datetime, add_to_date, cint, get_datetime

OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
OTP_SENDS_PER_HOUR = 3

BOQ_EXTENSIONS = (".xlsx", ".xls", ".pdf")
DRAWING_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")


# --------------------------------------------------------------------------- #
# Token / access helpers
# --------------------------------------------------------------------------- #
def _get_enquiry_by_token(enquiry, token):
	"""Return the enquiry doc iff the token matches and the link is live.

	Raises a 403 otherwise. This is the single gate every endpoint passes
	through -- there is no other way in.
	"""
	if not enquiry or not token:
		frappe.throw(_("Invalid link."), frappe.PermissionError)

	stored = frappe.db.get_value(
		"Building Enquiry",
		enquiry,
		["access_token", "link_expires_on", "status", "name"],
		as_dict=True,
	)
	if not stored or not stored.access_token:
		frappe.throw(_("Invalid or unshared link."), frappe.PermissionError)

	# constant-time compare
	import hmac

	if not hmac.compare_digest(str(stored.access_token), str(token)):
		frappe.throw(_("Invalid link."), frappe.PermissionError)

	if stored.link_expires_on and get_datetime(stored.link_expires_on) < now_datetime():
		frappe.throw(
			_("This link has expired. Please ask SBI to send a fresh link."),
			frappe.PermissionError,
		)

	if stored.status in ("Won", "Lost"):
		frappe.throw(_("This enquiry is closed."), frappe.PermissionError)

	# Load with ignore_permissions -- the token IS the permission.
	return frappe.get_doc("Building Enquiry", enquiry)


def _client_ip():
	return frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None


# --------------------------------------------------------------------------- #
# Portal data: read
# --------------------------------------------------------------------------- #
@frappe.whitelist(allow_guest=True)
def get_enquiry(enquiry, token):
	"""Return the portal-safe view of an enquiry. No financial data, ever."""
	doc = _get_enquiry_by_token(enquiry, token)

	sections = frappe.get_all(
		"Building Parameter Section",
		filters={"is_active": 1},
		fields=["name", "section_no", "bucket", "description"],
		order_by="section_no asc",
	)
	section_meta = {s.name: s for s in sections}

	params = []
	for row in (doc.parameters or []):
		meta = frappe.db.get_value(
			"Building Parameter",
			row.parameter,
			["fieldtype", "options", "help_text", "default_value"],
			as_dict=True,
		) or {}
		params.append({
			"idx": row.idx,
			"parameter": row.parameter,
			"parameter_name": row.parameter_name,
			"section": row.section,
			"section_no": row.section_no,
			"fieldtype": meta.get("fieldtype") or row.fieldtype or "Data",
			"options": meta.get("options"),
			"help_text": meta.get("help_text"),
			"uom": row.uom,
			"value": row.value,
			"sbi_value": row.sbi_value,
			"is_mandatory": cint(row.is_mandatory),
		})

	return {
		"enquiry": doc.name,
		"status": doc.status,
		"customer_name": doc.customer_name,
		"project_name": doc.project_name,
		"project_location": doc.project_location,
		"contact_person": doc.contact_person,
		"contact_email": doc.contact_email,
		"work_type": doc.work_type,
		"client_chooses_work_type": bool(doc.client_chooses_work_type),
		"work_types": _active_work_types() if doc.client_chooses_work_type else [],
		"input_mode": doc.input_mode,
		"link_expires_on": str(doc.link_expires_on) if doc.link_expires_on else None,
		"submitted": bool(doc.client_submitted_on),
		"verified_email": doc.client_verified_email,
		"read_only": bool(doc.client_submitted_on),
		"sections": [dict(s) for s in sections if s.name in section_meta],
		"parameters": params,
		"drawings": [
			{"idx": d.idx, "drawing_no": d.drawing_no, "revision": d.revision,
			 "description": d.description, "drawing_file": d.drawing_file}
			for d in (doc.drawings or [])
		],
		"boq_lines": [
			{"idx": b.idx, "sl_no": b.sl_no, "client_description": b.client_description,
			 "uom": b.uom, "qty": b.qty}
			for b in (doc.boq_lines or [])
		],
		"client_boq_file": doc.client_boq_file,
	}


# --------------------------------------------------------------------------- #
# Portal data: save (draft) and submit
# --------------------------------------------------------------------------- #
@frappe.whitelist(allow_guest=True)
def save_enquiry(enquiry, token, payload):
	"""Persist client edits without submitting. Override-with-audit for values."""
	doc = _get_enquiry_by_token(enquiry, token)
	if doc.client_submitted_on:
		frappe.throw(_("This enquiry has already been submitted and is read-only."))

	data = frappe.parse_json(payload) if isinstance(payload, str) else payload

	# input mode (client may switch)
	mode = (data.get("input_mode") or "").strip()
	if mode in ("SBI Parameters", "BOQ Upload", "Drawing Upload"):
		doc.input_mode = mode

	# parameter values -- match by parameter code, preserve SBI value
	incoming = {p.get("parameter"): p.get("value") for p in (data.get("parameters") or [])}
	for row in (doc.parameters or []):
		if row.parameter not in incoming:
			continue
		new_val = (incoming[row.parameter] or "").strip()
		old_val = (row.value or "").strip()
		if new_val == old_val:
			continue
		# preserve the SBI assumption the first time the client changes it
		if row.filled_by == "SBI" and not row.sbi_value:
			row.sbi_value = row.value
		row.value = new_val
		row.filled_by = "Client"
		row.value_changed = 1

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"ok": True, "message": _("Saved.")}


@frappe.whitelist(allow_guest=True)
def submit_enquiry(enquiry, token):
	"""Client finalises. Sets status, timestamps, notifies SBI. Then read-only."""
	doc = _get_enquiry_by_token(enquiry, token)
	if doc.client_submitted_on:
		frappe.throw(_("Already submitted."))

	# mandatory check only applies to the parameter mode
	if doc.input_mode == "SBI Parameters":
		pending = [
			r.parameter_name for r in (doc.parameters or [])
			if r.is_mandatory and not (r.value or "").strip()
		]
		if pending:
			frappe.throw(
				_("Please fill all mandatory fields before submitting. Pending: {0}").format(
					", ".join(pending[:8]) + ("..." if len(pending) > 8 else "")
				)
			)

	doc.client_submitted_on = now_datetime()
	doc.status = "Client Submitted"
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	_notify_sbi_submission(doc)
	return {"ok": True, "message": _("Submitted. Thank you.")}


def _notify_sbi_submission(doc):
	"""Email the enquiry owner / sales team that the client has submitted."""
	recipients = set()
	if doc.owner and doc.owner != "Guest":
		recipients.add(doc.owner)
	# add anyone assigned
	for u in frappe.get_all(
		"ToDo",
		filters={"reference_type": "Building Enquiry", "reference_name": doc.name,
				 "status": "Open"},
		pluck="allocated_to",
	):
		if u:
			recipients.add(u)

	if not recipients:
		return

	try:
		frappe.sendmail(
			recipients=list(recipients),
			subject=_("Client submitted enquiry {0}").format(doc.name),
			message=_(
				"<p>{customer} has submitted the building enquiry "
				"<b>{name}</b> via the portal.</p>"
				"<p>Input mode: {mode}<br>Verified email: {verified}</p>"
				"<p><a href='{url}'>Open the enquiry</a></p>"
			).format(
				customer=frappe.utils.escape_html(doc.customer_name or ""),
				name=doc.name,
				mode=doc.input_mode,
				verified=doc.client_verified_email or _("not verified"),
				url=frappe.utils.get_url_to_form("Building Enquiry", doc.name),
			),
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Enquiry submission notify failed")


# --------------------------------------------------------------------------- #
# OTP: send + verify (optional email verification)
# --------------------------------------------------------------------------- #
@frappe.whitelist(allow_guest=True)
def send_otp(enquiry, token, email):
	"""Generate and email a 6-digit OTP. Rate-limited per email."""
	_get_enquiry_by_token(enquiry, token)  # gate

	email = (email or "").strip().lower()
	if not email or "@" not in email:
		frappe.throw(_("Enter a valid email address."))

	# rate limit: max N sends per email per hour
	one_hour_ago = add_to_date(now_datetime(), hours=-1)
	recent = frappe.db.count(
		"Enquiry OTP",
		{"enquiry": enquiry, "email": email, "creation": [">", one_hour_ago]},
	)
	if recent >= OTP_SENDS_PER_HOUR:
		frappe.throw(
			_("Too many OTP requests. Please try again later."),
			frappe.ValidationError,
		)

	import random

	code = "{:06d}".format(random.randint(0, 999999))
	otp = frappe.get_doc({
		"doctype": "Enquiry OTP",
		"enquiry": enquiry,
		"email": email,
		"otp_hash": frappe.utils.sha256_hash(code) if hasattr(frappe.utils, "sha256_hash")
		else _sha256(code),
		"expires_on": add_to_date(now_datetime(), minutes=OTP_TTL_MINUTES),
		"attempts": 0,
		"verified": 0,
		"ip_address": _client_ip(),
	})
	otp.insert(ignore_permissions=True)
	frappe.db.commit()

	try:
		frappe.sendmail(
			recipients=[email],
			subject=_("Your verification code: {0}").format(code),
			message=_(
				"<p>Your verification code for the building enquiry is:</p>"
				"<h2 style='letter-spacing:4px'>{code}</h2>"
				"<p>This code expires in {mins} minutes.</p>"
			).format(code=code, mins=OTP_TTL_MINUTES),
			now=True,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "OTP send failed")
		frappe.throw(_("Could not send the code. Please try again."))

	return {"ok": True, "message": _("Code sent to {0}.").format(email)}


@frappe.whitelist(allow_guest=True)
def verify_otp(enquiry, token, email, code):
	"""Verify the latest OTP for this email. On success, mark the enquiry."""
	doc = _get_enquiry_by_token(enquiry, token)

	email = (email or "").strip().lower()
	code = (code or "").strip()
	if not code:
		frappe.throw(_("Enter the code."))

	latest = frappe.get_all(
		"Enquiry OTP",
		filters={"enquiry": enquiry, "email": email, "verified": 0},
		fields=["name", "otp_hash", "expires_on", "attempts"],
		order_by="creation desc",
		limit=1,
	)
	if not latest:
		frappe.throw(_("No active code. Please request a new one."))

	otp = latest[0]
	if get_datetime(otp.expires_on) < now_datetime():
		frappe.throw(_("Code expired. Please request a new one."))

	if cint(otp.attempts) >= OTP_MAX_ATTEMPTS:
		frappe.throw(_("Too many attempts. Please request a new code."))

	expected = otp.otp_hash
	got = frappe.utils.sha256_hash(code) if hasattr(frappe.utils, "sha256_hash") else _sha256(code)

	if got != expected:
		frappe.db.set_value("Enquiry OTP", otp.name, "attempts", cint(otp.attempts) + 1)
		frappe.db.commit()
		remaining = OTP_MAX_ATTEMPTS - cint(otp.attempts) - 1
		frappe.throw(_("Incorrect code. {0} attempt(s) left.").format(max(remaining, 0)))

	# success
	frappe.db.set_value("Enquiry OTP", otp.name, {
		"verified": 1,
		"verified_on": now_datetime(),
	})
	doc.client_verified_email = email
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "message": _("Email verified."), "verified_email": email}


def _sha256(text):
	import hashlib

	return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Portal file upload (guest-safe, token-gated)
# --------------------------------------------------------------------------- #
@frappe.whitelist(allow_guest=True)
def portal_upload(enquiry, token):
	"""Accept a client file upload for an enquiry, enforcing type + size.

	Stores the file as a private File attached to the enquiry, and wires it in:
	- BOQ types -> set as client_boq_file
	- Drawing types -> appended to the drawings table
	The token is the only credential; guests never touch the desk upload path.
	"""
	doc = _get_enquiry_by_token(enquiry, token)
	if doc.client_submitted_on:
		frappe.throw(_("This enquiry is already submitted."))

	files = frappe.request.files
	if not files or "file" not in files:
		frappe.throw(_("No file received."))

	filedata = files["file"]
	filename = filedata.filename or "upload"
	ext = os.path.splitext(filename)[1].lower()

	allowed = BOQ_EXTENSIONS + DRAWING_EXTENSIONS
	if ext not in allowed:
		frappe.throw(
			_("File type {0} is not allowed. Accepted: {1}").format(
				ext or _("unknown"), ", ".join(sorted(set(allowed)))
			)
		)

	content = filedata.stream.read()
	max_bytes = 15 * 1024 * 1024  # 15 MB
	if len(content) > max_bytes:
		frappe.throw(_("File is too large. Maximum size is 15 MB."))

	saved = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"attached_to_doctype": "Building Enquiry",
		"attached_to_name": doc.name,
		"is_private": 1,
		"content": content,
	})
	saved.insert(ignore_permissions=True)

	# wire into the right slot
	if ext in BOQ_EXTENSIONS and doc.input_mode == "BOQ Upload":
		doc.client_boq_file = saved.file_url
	elif ext in DRAWING_EXTENSIONS:
		doc.append("drawings", {
			"drawing_no": filename,
			"drawing_file": saved.file_url,
			"uploaded_by": "Client",
		})
	elif ext in BOQ_EXTENSIONS:
		# BOQ file uploaded while not strictly in BOQ mode -- still keep it
		doc.client_boq_file = saved.file_url

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"file_url": saved.file_url, "file_name": filename}


# --------------------------------------------------------------------------- #
# Client-chosen work type (portal selector)
# --------------------------------------------------------------------------- #
def _active_work_types():
	"""Work types offered to the client on the portal, in display order."""
	return frappe.get_all(
		"Building Work Type",
		filters={"is_active": 1},
		fields=["name as work_type", "description"],
		order_by="display_order asc, name asc",
	)


@frappe.whitelist(allow_guest=True)
def set_work_type(enquiry, token, work_type):
	"""Client picks a work type on the portal; load that type's parameters.

	Only allowed when the enquiry was flagged 'Let Client Choose Work Type'.
	Replaces the parameter set (a different work type has a different set), so
	any previously entered values for parameters not in the new set are dropped.
	Values for parameters common to both sets are preserved.
	"""
	doc = _get_enquiry_by_token(enquiry, token)
	if doc.client_submitted_on:
		frappe.throw(_("This enquiry is already submitted."))
	if not doc.client_chooses_work_type:
		frappe.throw(_("Work type is fixed for this enquiry."))

	if not frappe.db.exists("Building Work Type", work_type):
		frappe.throw(_("Unknown work type."))

	# remember current answers so we can carry over the overlap
	prior = {r.parameter: r.value for r in (doc.parameters or []) if (r.value or "").strip()}

	from sbi_projects.peb_estimation.doctype.building_parameter.building_parameter import (
		get_parameters_for_work_type,
	)

	rows = get_parameters_for_work_type(work_type)
	if not rows:
		frappe.throw(_("No parameters defined for {0}.").format(work_type))

	doc.work_type = work_type
	doc.parameters = []
	for row in rows:
		doc.append("parameters", {
			"parameter": row.parameter,
			"is_mandatory": row.is_mandatory,
			"filled_by": "Client" if prior.get(row.parameter) else "SBI",
			"value": prior.get(row.parameter),
		})

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()

	return {"ok": True, "work_type": work_type, "count": len(rows)}
