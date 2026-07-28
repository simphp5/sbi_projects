# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Legacy hyphen route -> redirect to the underscore page.

Python cannot import a module named with a hyphen, so a www context file named
`building-enquiry.py` may never execute on some setups. The real portal now
lives at `building_enquiry` (underscore). This thin file just forwards any old
hyphen links (already sent by email) to the working underscore route, keeping
the query string intact.
"""

import frappe


def get_context(context):
	qs = frappe.request.query_string.decode() if frappe.request else ""
	target = "/building_enquiry"
	if qs:
		target += "?" + qs
	frappe.local.flags.redirect_location = target
	raise frappe.Redirect
