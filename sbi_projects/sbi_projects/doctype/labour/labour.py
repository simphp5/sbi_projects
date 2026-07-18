# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document


class Labour(Document):
	def autoname(self):
		if not self.labour_code:
			self.labour_code = frappe.model.naming.make_autoname("LAB-.#####")
		self.name = self.labour_code

	def validate(self):
		self.set_face_status()
		self.validate_aadhaar()

	def set_face_status(self):
		if self.face_embedding and not self.face_enrolled:
			self.face_enrolled = 1
			self.enrolled_on = frappe.utils.now()
		elif not self.face_embedding:
			self.face_enrolled = 0
			self.enrolled_on = None

	def validate_aadhaar(self):
		if self.aadhaar_last4 and (len(self.aadhaar_last4) != 4 or not self.aadhaar_last4.isdigit()):
			frappe.throw(_("Aadhaar (last 4) must be exactly 4 digits."))


@frappe.whitelist()
def enroll_face(labour, embedding):
	"""Store a face descriptor captured on-device (PWA/MediaPipe)."""
	doc = frappe.get_doc("Labour", labour)
	doc.face_embedding = embedding
	doc.save()
	return {"status": "ok", "labour": doc.name}
