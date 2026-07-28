# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class QuantityRule(Document):
	def validate(self):
		self.check_expressions()

	def check_expressions(self):
		"""Compile-check the formula and condition against dummy parameters so a
		typo is caught here rather than halfway through generating a BOQ."""
		sample = build_params_context({})
		for label, expr in (("Qty Formula", self.qty_formula),
		                    ("Condition", self.condition)):
			if not (expr or "").strip():
				continue
			try:
				frappe.safe_eval(expr, get_eval_globals(sample), {})
			except Exception as e:
				frappe.throw(
					_("{0} could not be evaluated: {1}").format(label, frappe.bold(str(e)))
				)


def get_eval_globals(params):
	return {
		"params": params,
		"p": params,
		"flt": flt,
		"round": round,
		"min": min,
		"max": max,
		"abs": abs,
	}


def build_params_context(values):
	"""Return every active parameter code as an attribute-accessible entry.

	Numeric parameter types resolve to numbers, everything else to text, and a
	code the client never answered still resolves (0 or "") -- so a formula can
	never blow up on a missing key.
	"""
	NUMERIC = {"Float", "Int"}
	ctx = frappe._dict()

	for row in frappe.get_all(
		"Building Parameter",
		filters={"is_active": 1},
		fields=["name", "parameter_code", "fieldtype"],
	):
		raw = values.get(row.name)
		if raw is None:
			raw = values.get(row.parameter_code)

		text = str(raw).strip() if raw is not None else ""
		if row.fieldtype in NUMERIC:
			ctx[row.parameter_code] = flt(text)
		else:
			# a numeric-looking answer on a text field is still useful as a number
			ctx[row.parameter_code] = text

	return ctx


def is_ticked(value):
	"""Scope answers arrive as Yes/No from the portal or 1/0 from the desk."""
	return str(value or "").strip().lower() in ("yes", "1", "true", "y")
