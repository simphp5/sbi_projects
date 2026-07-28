# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class WorkItem(Document):
	def validate(self):
		if not self.work_item_code:
			frappe.throw(_("Work Item Code is required."))

	@frappe.whitelist()
	def computed_rate(self, rate_card=None):
		"""Unit rate = sum(coefficient x resource effective_rate) from a Rate Card."""
		from sbi_projects.peb_estimation.doctype.rate_card.rate_card import RateCard
		rate_card = rate_card or RateCard.get_default()
		if not rate_card:
			return 0
		card = frappe.get_cached_doc("Rate Card", rate_card)
		total = 0
		for row in (self.resources or []):
			total += (row.coefficient or 0) * card.resource_rate(row.resource)
		return total
