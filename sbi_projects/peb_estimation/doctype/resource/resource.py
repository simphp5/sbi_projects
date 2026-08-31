# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Resource(Document):
	def validate(self):
		self.resource_name = (self.resource_name or "").strip()

	def get_or_create_item(self):
		"""Return the ERPNext Item for this resource, creating it once.

		Materials have to exist as Items before they can go on a Material
		Request. Rather than asking someone to maintain the same list twice,
		the Item is created the first time it is needed and remembered here.
		"""
		if self.item_code and frappe.db.exists("Item", self.item_code):
			return self.item_code

		code = self.resource_name
		if frappe.db.exists("Item", code):
			self.db_set("item_code", code)
			return code

		uom = self.uom or "Nos"
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)

		item = frappe.get_doc({
			"doctype": "Item",
			"item_code": code,
			"item_name": code[:140],
			"description": self.description or code,
			"item_group": _resource_item_group(),
			"stock_uom": uom,
			"is_stock_item": 1 if self.is_stock else 0,
			"is_purchase_item": 1,
			"is_sales_item": 0,
			"include_item_in_manufacturing": 0,
		})
		item.insert(ignore_permissions=True)
		self.db_set("item_code", item.name)
		return item.name


def _resource_item_group():
	name = "Construction Materials"
	if frappe.db.exists("Item Group", name):
		return name
	parent = frappe.db.get_value(
		"Item Group", {"is_group": 1, "parent_item_group": ""}, "name"
	) or "All Item Groups"
	frappe.get_doc({
		"doctype": "Item Group",
		"item_group_name": name,
		"parent_item_group": parent,
		"is_group": 0,
	}).insert(ignore_permissions=True)
	return name
