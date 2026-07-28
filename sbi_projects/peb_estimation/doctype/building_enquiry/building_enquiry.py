# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document

BOQ_EXTENSIONS = (".xlsx", ".xls", ".pdf")
DRAWING_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png")


class BuildingEnquiry(Document):
	def validate(self):
		self.set_title()
		self.validate_files()
		self.compute_counts()

	def set_title(self):
		parts = [p for p in [self.customer_name or self.customer, self.project_name] if p]
		self.title = " - ".join(parts) if parts else self.name

	def validate_files(self):
		"""Enforce accepted file types for BOQ and drawing uploads."""
		if self.client_boq_file:
			self._check_extension(
				self.client_boq_file, BOQ_EXTENSIONS, _("Client BOQ File")
			)
		for row in (self.drawings or []):
			if row.drawing_file:
				self._check_extension(
					row.drawing_file, DRAWING_EXTENSIONS,
					_("Drawing row {0}").format(row.idx),
				)

	@staticmethod
	def _check_extension(path, allowed, label):
		ext = os.path.splitext((path or "").split("?")[0])[1].lower()
		if ext not in allowed:
			frappe.throw(
				_("{0}: file type {1} is not allowed. Accepted: {2}").format(
					label,
					frappe.bold(ext or _("unknown")),
					", ".join(allowed),
				)
			)

	def compute_counts(self):
		self.total_parameters = len(self.parameters or [])
		self.filled_parameters = len(
			[r for r in (self.parameters or []) if (r.value or "").strip()]
		)
		self.mandatory_pending = len(
			[r for r in (self.parameters or [])
			 if r.is_mandatory and not (r.value or "").strip()]
		)

	@frappe.whitelist()
	def load_from_template(self, template=None, replace=False):
		"""Pull parameters from an Approved template into the questionnaire."""
		template = template or self.parameter_template
		if not template:
			frappe.throw(_("Select a Parameter Template first."))

		status = frappe.db.get_value("Building Parameter Template", template, "status")
		if status != "Approved":
			frappe.throw(
				_("Template {0} is not Approved (current: {1}). "
				  "Only Approved templates can be used for a client enquiry.").format(
					frappe.bold(template), frappe.bold(status or "Draft")
				)
			)

		rows = frappe.get_all(
			"Building Parameter Template Item",
			filters={"parent": template, "parenttype": "Building Parameter Template"},
			fields=["parameter", "is_mandatory"],
			order_by="idx asc",
		)
		if not rows:
			frappe.throw(_("Template {0} has no parameters.").format(frappe.bold(template)))

		if replace:
			self.parameters = []

		existing = {r.parameter for r in (self.parameters or [])}
		added = 0
		for row in rows:
			if row.parameter in existing:
				continue
			self.append("parameters", {
				"parameter": row.parameter,
				"is_mandatory": row.is_mandatory,
				"filled_by": "SBI",
			})
			added += 1
		self.compute_counts()
		return added

	# ------------------------------------------------------------------ #
	# Client portal link (SBI side)
	# ------------------------------------------------------------------ #
	@frappe.whitelist()
	def generate_link(self, valid_days=None, send_email=True):
		"""Create/refresh the access token, set expiry, optionally email the client.

		Called from the desk 'Send Link to Client' button.
		"""
		from frappe.utils import add_to_date, now_datetime, today, add_days

		if not self.contact_email:
			frappe.throw(_("Set Contact Email before sending the link."))

		valid_days = int(valid_days or self.link_valid_days or 15)
		if valid_days < 1:
			frappe.throw(_("Link validity must be at least 1 day."))

		# fresh token each time a link is (re)sent -- invalidates any old link
		self.access_token = frappe.generate_hash(length=32)
		self.link_valid_days = valid_days
		self.link_sent_on = now_datetime()
		self.link_expires_on = add_days(today(), valid_days)
		if self.status == "Draft":
			self.status = "Sent to Client"
		self.flags.ignore_permissions = True
		self.save(ignore_permissions=True)
		frappe.db.commit()

		url = self.get_portal_url()

		if send_email:
			self._send_link_email(url, valid_days)

		return {"url": url, "expires_on": str(self.link_expires_on)}

	@frappe.whitelist()
	def extend_link(self, extra_days=15):
		"""Push the expiry out without changing the token."""
		from frappe.utils import add_days, getdate, today

		extra_days = int(extra_days or 15)
		base = getdate(self.link_expires_on) if self.link_expires_on else getdate(today())
		if base < getdate(today()):
			base = getdate(today())
		self.link_expires_on = add_days(base, extra_days)
		self.flags.ignore_permissions = True
		self.save(ignore_permissions=True)
		frappe.db.commit()
		return {"expires_on": str(self.link_expires_on)}

	def get_portal_url(self):
		from frappe.utils import get_url

		return get_url(
			"/building_enquiry?id={0}&key={1}".format(self.name, self.access_token)
		)

	def _send_link_email(self, url, valid_days):
		try:
			frappe.sendmail(
				recipients=[self.contact_email],
				subject=_("Building Enquiry from SBI - please provide your requirements"),
				message=_(
					"<p>Dear {contact},</p>"
					"<p>Please provide the requirements for your building project "
					"<b>{project}</b> using the secure link below:</p>"
					"<p><a href='{url}'>Open the enquiry form</a></p>"
					"<p>This link is valid for {days} days. You may optionally verify "
					"your email on the form for added security.</p>"
					"<p>Regards,<br>Shiv Bharat Infrastructures</p>"
				).format(
					contact=frappe.utils.escape_html(self.contact_person or ""),
					project=frappe.utils.escape_html(self.project_name or self.customer_name or ""),
					url=url,
					days=valid_days,
				),
				now=True,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Enquiry link email failed")
			frappe.msgprint(
				_("Link generated, but the email could not be sent. "
				  "Copy the link manually: {0}").format(url)
			)
