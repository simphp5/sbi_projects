# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WorkGroup(Document):
	def validate(self):
		self.work_group_name = (self.work_group_name or "").strip().upper()
