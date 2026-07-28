# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Server context for the guest Building Enquiry portal.

Validates the (id, key) pair up front so the page never renders a working
form for an invalid or expired link. The access token is the only credential;
no desk login is required and nothing financial is exposed.
"""

import hmac

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False

	enquiry = frappe.form_dict.get("id")
	token = frappe.form_dict.get("key")

	context.enquiry = enquiry or ""
	context.token = token or ""
	context.valid = False
	context.error = None
	context.customer_name = ""
	context.project_name = ""

	try:
		if not enquiry or not token:
			context.error = _("This link is incomplete. Please use the link from your email.")
			return context

		row = frappe.db.get_value(
			"Building Enquiry",
			enquiry,
			["access_token", "link_expires_on", "status", "customer_name",
			 "project_name"],
			as_dict=True,
		)

		if not row:
			context.error = _("Enquiry not found for this link.")
			return context

		if not row.access_token:
			context.error = _("No link has been generated for this enquiry yet.")
			return context

		if not hmac.compare_digest(str(row.access_token), str(token)):
			context.error = _("This link is invalid (token mismatch).")
			return context

		if row.link_expires_on:
			try:
				expired = get_datetime(row.link_expires_on) < now_datetime()
			except Exception:
				expired = False
			if expired:
				context.error = _("This link has expired. Please contact SBI for a new link.")
				return context

		if row.status in ("Won", "Lost"):
			context.error = _("This enquiry is already closed.")
			return context

		context.valid = True
		context.customer_name = row.customer_name or ""
		context.project_name = row.project_name or ""
		return context

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Building Enquiry portal context")
		context.error = _("Something went wrong opening this link. Please contact SBI.")
		return context

# rebuild trigger 20260728114333
