# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Server context for the guest Building Enquiry portal.

Runs on every GET of /building-enquiry. It validates the (id, key) pair up
front so the page never renders for an invalid or expired link -- the browser
gets a clean error instead of a blank shell that later fails on API calls.

No desk login is required; the access token is the credential. Nothing
financial is placed in the context.
"""

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

	if not row or not row.access_token:
		context.error = _("This link is invalid.")
		return context

	import hmac

	if not hmac.compare_digest(str(row.access_token), str(token)):
		context.error = _("This link is invalid.")
		return context

	if row.link_expires_on and get_datetime(row.link_expires_on) < now_datetime():
		context.error = _("This link has expired. Please contact SBI for a new link.")
		return context

	if row.status in ("Won", "Lost"):
		context.error = _("This enquiry is closed.")
		return context

	# valid -- expose only the non-sensitive header for the initial paint;
	# the full questionnaire is fetched client-side via the token-gated API.
	context.valid = True
	context.customer_name = row.customer_name or ""
	context.project_name = row.project_name or ""
	return context
