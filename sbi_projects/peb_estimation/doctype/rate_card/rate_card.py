# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RateCard(Document):
	def validate(self):
		self.compute_effective_rates()
		self.enforce_single_default()

	def compute_effective_rates(self):
		for row in (self.items or []):
			w = flt(row.wastage_percent) / 100.0
			row.effective_rate = flt(row.rate) * (1 + w)

	def enforce_single_default(self):
		if self.is_default:
			frappe.db.set_value(
				"Rate Card", {"is_default": 1, "name": ["!=", self.name]},
				"is_default", 0, update_modified=False,
			)

	@staticmethod
	def get_default():
		return frappe.db.get_value("Rate Card", {"is_default": 1}, "name")

	@frappe.whitelist()
	def resource_rate(self, resource):
		"""Effective rate for a named resource in this card."""
		for row in (self.items or []):
			if row.resource == resource:
				return flt(row.effective_rate) or flt(row.rate)
		return 0
