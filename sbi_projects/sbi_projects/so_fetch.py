"""Pull details onto a Project when its Sales Order is set.

Selecting a sales order on the project form should fill in the customer and the
contract value immediately, and lay out the stage tasks from the order's
payment schedule -- without the user having to press a separate button.

Wired on Project validate, so it runs whether the sales order is set at
creation, added later, or changed.
"""

import frappe
from frappe.utils import flt


def sync_from_sales_order(doc, method=None):
	so_name = doc.get("sales_order")
	if not so_name:
		return

	so = frappe.db.get_value(
		"Sales Order", so_name,
		["customer", "customer_name", "rounded_total", "grand_total"],
		as_dict=True,
	)
	if not so:
		return

	# customer, only if the form has such a field and it is not already set
	if not doc.get("customer") and doc.meta.has_field("customer"):
		doc.customer = so.customer

	# contract value, if we track it and it is still blank
	if doc.meta.has_field("sbi_contract_value") and not doc.get("sbi_contract_value"):
		doc.sbi_contract_value = flt(so.rounded_total or so.grand_total)


def build_stages_if_new(doc, method=None):
	"""On first save with a sales order and no tasks yet, lay out the stages.

	Kept separate from sync_from_sales_order so the light-touch fetch always
	runs, while stage creation only happens when it is safe (no tasks yet).
	"""
	if not doc.get("sales_order"):
		return
	if frappe.db.exists("Task", {"project": doc.name}):
		return

	try:
		from sbi_projects.sbi_projects.project_hooks import create_stages_from_sales_order
		create_stages_from_sales_order(doc.name)
	except Exception:
		frappe.log_error(
			title="Auto stage creation failed: {0}".format(doc.name),
			message=frappe.get_traceback(),
		)