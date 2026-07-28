# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


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
		total = 0.0
		for row in (self.resources or []):
			total += flt(row.coefficient) * flt(card.resource_rate(row.resource))
		return total

	def get_or_create_item(self):
		"""Return the ERPNext Item used to sell this work item, creating it once.

		Estimation work items are internal; a Quotation needs a real Item. Rather
		than asking the estimator to maintain both lists, the Item is created on
		first use as a non-stock service item and remembered here.
		"""
		if self.item_code and frappe.db.exists("Item", self.item_code):
			return self.item_code

		code = self.work_item_code
		if frappe.db.exists("Item", code):
			self.db_set("item_code", code)
			return code

		group = _construction_item_group()
		uom = self.uom or "Nos"
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)

		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": code,
			"item_name": self.work_item_name[:140],
			"description": self.description or self.work_item_name,
			"item_group": group,
			"stock_uom": uom,
			"is_stock_item": 0,
			"is_sales_item": 1,
			"is_purchase_item": 0,
			"include_item_in_manufacturing": 0,
		})
		item.insert(ignore_permissions=True)
		self.db_set("item_code", item.name)
		return item.name


def _construction_item_group():
	"""An item group for estimation work items, created once if absent."""
	name = "Construction Works"
	if frappe.db.exists("Item Group", name):
		return name

	parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}, "name")
	parent = parent or "All Item Groups"
	frappe.get_doc({
		"doctype": "Item Group",
		"item_group_name": name,
		"parent_item_group": parent,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	return name
