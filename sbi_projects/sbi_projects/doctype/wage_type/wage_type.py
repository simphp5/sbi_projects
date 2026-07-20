import frappe
from frappe import _
from frappe.model.document import Document


class WageType(Document):
	def validate(self):
		self.wage_type_name = (self.wage_type_name or "").strip()
		self.validate_payment_modes()

	def validate_payment_modes(self):
		if not (self.allow_cash or self.allow_bank):
			frappe.throw(_("At least one payment mode must be allowed."))

		if self.requires_bank_details and not self.allow_bank:
			frappe.throw(
				_("Bank details cannot be mandatory when bank transfer is not allowed.")
			)


@frappe.whitelist()
def get_wage_defaults(wage_type):
	"""Used when enrolling a labourer or subcontractor."""
	if not wage_type:
		return {}
	d = frappe.db.get_value(
		"Wage Type",
		wage_type,
		[
			"payment_frequency",
			"rate_basis",
			"default_rate",
			"default_payment_mode",
			"requires_bank_details",
			"site_cost_category",
		],
		as_dict=True,
	)
	return d or {}