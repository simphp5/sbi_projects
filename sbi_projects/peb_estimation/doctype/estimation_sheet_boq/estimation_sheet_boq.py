# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EstimationSheetBOQ(Document):
	def validate(self):
		self.compute_amounts()
		self.compute_totals()

	def compute_amounts(self):
		for row in (self.lines or []):
			row.qty = flt(row.qty)
			row.rate = flt(row.rate)
			row.amount = flt(row.qty) * flt(row.rate)

	def compute_totals(self):
		base = sum(flt(r.amount) for r in (self.lines or []))
		self.base_total = base

		markup = 0.0
		for pct in (self.site_establishment_pct, self.contingency_pct,
		            self.overhead_pct, self.profit_pct, self.incentive_pct):
			markup += base * (flt(pct) / 100.0)

		self.markup_total = markup
		self.grand_total = base + markup

		area = flt(self.built_up_area)
		self.rate_per_sft = (base + markup) / area if area else 0

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
			row.amount = flt(row.qty) * flt(row.rate)
			updated += 1
		self.compute_totals()
		self.save(ignore_permissions=True)
		return updated
