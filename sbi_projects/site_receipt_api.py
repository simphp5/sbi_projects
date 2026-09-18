"""Material receipt from the site tablet.

Site incharge sees item + ordered qty + pending qty only.
Rates, amounts and taxes are never sent to the browser - the Purchase
Receipt is built server-side from the Purchase Order.
"""

import base64
import json

import frappe
from frappe.utils import flt, getdate, nowdate

try:
	from sbi_projects.site_ops_api import _check_site_user
except Exception:  # pragma: no cover - fallback if the helper moves

	def _check_site_user():
		if frappe.session.user == "Guest":
			frappe.throw(frappe._("Not permitted"), frappe.PermissionError)


def _site_store(project):
	from sbi_projects.setup.project_warehouse import warehouse_for_project

	return warehouse_for_project(project)


# ---------------------------------------------------------------- read


@frappe.whitelist()
def pending_purchase_orders(project):
	"""Submitted POs for this project that still have material to receive."""
	_check_site_user()
	if not project:
		return []

	parents = frappe.get_all(
		"Purchase Order Item",
		filters={"project": project, "docstatus": 1},
		fields=["parent"],
		group_by="parent",
		limit_page_length=0,
	)
	names = [p.parent for p in parents if p.parent]
	if not names:
		return []

	orders = frappe.get_all(
		"Purchase Order",
		filters={
			"name": ["in", names],
			"docstatus": 1,
			"status": ["not in", ["Closed", "Completed", "Delivered"]],
		},
		fields=["name", "supplier", "supplier_name", "transaction_date", "per_received"],
		order_by="transaction_date desc",
		limit_page_length=0,
	)

	out = []
	for order in orders:
		rows = frappe.get_all(
			"Purchase Order Item",
			filters={"parent": order.name, "project": project},
			fields=[
				"name",
				"idx",
				"item_code",
				"item_name",
				"uom",
				"stock_uom",
				"qty",
				"received_qty",
				"schedule_date",
			],
			order_by="idx",
			limit_page_length=0,
		)

		items = []
		for row in rows:
			pending = flt(row.qty) - flt(row.received_qty)
			if pending <= 0:
				continue
			items.append(
				{
					"row": row.name,
					"idx": row.idx,
					"item_code": row.item_code,
					"item_name": row.item_name or row.item_code,
					"uom": row.uom or row.stock_uom or "",
					"ordered": flt(row.qty),
					"received": flt(row.received_qty),
					"pending": flt(pending, 3),
					"schedule_date": str(row.schedule_date or ""),
				}
			)

		if items:
			out.append(
				{
					"name": order.name,
					"supplier": order.supplier,
					"supplier_name": order.supplier_name or order.supplier,
					"date": str(order.transaction_date or ""),
					"per_received": flt(order.per_received, 1),
					"items": items,
				}
			)

	return out


@frappe.whitelist()
def recent_receipts(project, limit=10):
	"""Last few receipts booked from this site."""
	_check_site_user()
	rows = frappe.get_all(
		"Purchase Receipt Item",
		filters={"project": project, "docstatus": 1},
		fields=["parent"],
		group_by="parent",
		order_by="parent desc",
		limit_page_length=int(limit),
	)
	names = [r.parent for r in rows if r.parent]
	if not names:
		return []

	receipts = frappe.get_all(
		"Purchase Receipt",
		filters={"name": ["in", names]},
		fields=["name", "supplier_name", "posting_date", "supplier_delivery_note"],
		order_by="posting_date desc, creation desc",
		limit_page_length=int(limit),
	)

	for receipt in receipts:
		receipt["items"] = frappe.get_all(
			"Purchase Receipt Item",
			filters={"parent": receipt.name},
			fields=["item_name", "qty", "uom"],
			order_by="idx",
			limit_page_length=0,
		)
	return receipts


# ---------------------------------------------------------------- write


def _attach_photo(data_url, doctype, docname, label="challan"):
	if not data_url or "," not in data_url:
		return None
	try:
		header, payload = data_url.split(",", 1)
		ext = "jpg"
		if "png" in header:
			ext = "png"
		content = base64.b64decode(payload)
	except Exception:
		return None

	fname = "%s-%s.%s" % (label, docname.replace("/", "-"), ext)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": fname,
			"attached_to_doctype": doctype,
			"attached_to_name": docname,
			"is_private": 1,
			"content": content,
		}
	)
	file_doc.flags.ignore_permissions = True
	file_doc.save(ignore_permissions=True)
	return file_doc.file_url


@frappe.whitelist()
def create_receipt(
	project,
	purchase_order,
	rows,
	challan_no=None,
	challan_date=None,
	photo=None,
	remarks=None,
):
	"""Build and submit a Purchase Receipt from the site tablet."""
	_check_site_user()

	if isinstance(rows, str):
		rows = json.loads(rows)
	wanted = {}
	for row in rows or []:
		qty = flt(row.get("qty"))
		if qty > 0:
			wanted[row.get("row")] = qty
	if not wanted:
		frappe.throw(frappe._("Enter the received quantity for at least one item."))

	po = frappe.get_doc("Purchase Order", purchase_order)
	if po.docstatus != 1:
		frappe.throw(frappe._("Purchase Order is not submitted."))

	po_projects = {r.project for r in po.items if r.project}
	if project not in po_projects:
		frappe.throw(frappe._("This Purchase Order does not belong to the selected site."))

	for row in po.items:
		if row.name in wanted:
			pending = flt(row.qty) - flt(row.received_qty)
			if wanted[row.name] > pending + 0.001:
				frappe.throw(
					frappe._("{0}: received qty {1} is more than the pending {2}.").format(
						row.item_name or row.item_code, wanted[row.name], flt(pending, 3)
					)
				)

	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	pr = make_purchase_receipt(purchase_order)
	pr.posting_date = getdate(nowdate())
	pr.set_posting_time = 0

	warehouse = _site_store(project)
	keep = []
	for row in pr.items:
		po_row = row.purchase_order_item
		if po_row in wanted:
			row.qty = wanted[po_row]
			row.received_qty = wanted[po_row]
			if warehouse:
				row.warehouse = warehouse
			keep.append(row)
	if not keep:
		frappe.throw(frappe._("Nothing to receive against this Purchase Order."))

	pr.items = keep
	for idx, row in enumerate(pr.items, start=1):
		row.idx = idx

	if warehouse:
		pr.set_warehouse = warehouse
	if challan_no:
		pr.supplier_delivery_note = challan_no
	if challan_date:
		pr.lr_date = getdate(challan_date)
	if remarks:
		pr.remarks = remarks

	pr.flags.ignore_permissions = True
	pr.insert(ignore_permissions=True)

	if photo:
		_attach_photo(photo, "Purchase Receipt", pr.name)

	pr.submit()
	frappe.db.commit()

	return {
		"name": pr.name,
		"warehouse": warehouse,
		"items": [
			{"item_name": r.item_name or r.item_code, "qty": flt(r.qty), "uom": r.uom}
			for r in pr.items
		],
	}
