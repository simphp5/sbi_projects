# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document


class SiteInspection(Document):
	def validate(self):
		self.set_overall_result()

	def set_overall_result(self):
		"""Derive the overall result from the checklist when left blank."""
		if self.overall_result:
			return
		if not self.checklist:
			return
		results = [d.result for d in self.checklist if d.result]
		if "Not OK" in results:
			self.overall_result = "Fail"
		elif any(d.observation for d in self.checklist):
			self.overall_result = "Pass with Observations"
		else:
			self.overall_result = "Pass"

	def on_submit(self):
		self.attach_pdf()

	def attach_pdf(self):
		"""Render the print format to PDF and attach it to this record."""
		try:
			from frappe.utils.pdf import get_pdf

			html = frappe.get_print("Site Inspection", self.name, print_format=None)
			pdf = get_pdf(html)
			frappe.get_doc({
				"doctype": "File",
				"file_name": f"{self.name}.pdf",
				"attached_to_doctype": "Site Inspection",
				"attached_to_name": self.name,
				"is_private": 1,
				"content": pdf,
			}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Site Inspection PDF attach failed")
