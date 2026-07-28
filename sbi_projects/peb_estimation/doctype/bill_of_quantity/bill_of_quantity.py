# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class BillOfQuantity(Document):
	def validate(self):
		self.compute_amounts()
		self.compute_totals()

	def compute_amounts(self):
		for row in (self.lines or []):
			row.amount = (row.qty or 0) * (row.rate or 0)

	def compute_totals(self):
		base = sum((r.amount or 0) for r in (self.lines or []))
		self.base_total = base
		m = base
		for pct in (self.site_establishment_pct, self.contingency_pct,
		            self.overhead_pct, self.profit_pct, self.incentive_pct):
			m += base * ((pct or 0) / 100.0)
		self.markup_total = m - base
		self.grand_total = m
		if self.built_up_area:
			self.rate_per_sft = m / self.built_up_area

	@frappe.whitelist()
	def recalculate_rates(self):
		"""Refresh WA-source line rates from the Rate Card. Manual lines untouched."""
		card = self.rate_card
		if not card:
			from sbi_projects.peb_estimation.doctype.rate_card.rate_card import RateCard
			card = RateCard.get_default()
		if not card:
			frappe.throw(_("No Rate Card selected and no default Rate Card found."))
		updated = 0
		for row in (self.lines or []):
			if row.rate_source == "Manual":
				continue
			if not row.work_item:
				continue
			wi = frappe.get_cached_doc("Work Item", row.work_item)
			row.rate = wi.computed_rate(card)
			row.amount = (row.qty or 0) * (row.rate or 0)
			updated += 1
		self.compute_totals()
		self.save(ignore_permissions=True)
		return updated
