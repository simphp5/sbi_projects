# Copyright (c) 2026, Velmaska and contributors
# Serves the custom Shiv Bharat login page at /login.

import frappe

no_cache = 1


def get_context(context):
	# Already signed in -> straight to the desk.
	if frappe.session.user and frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/app"
		raise frappe.Redirect

	context.no_cache = 1
	return context
