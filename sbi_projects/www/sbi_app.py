"""Public PWA entry page (route: /sbi_app).

This page is PUBLIC (allow_guest) so PWABuilder and the browser can read the
manifest + service worker without hitting the login wall. It immediately
forwards a signed-in user to the real app at /sbi_site; a guest is sent to
login and then returns here. This is the URL to give PWABuilder.
"""

import frappe

no_cache = 1


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.logged_in = frappe.session.user != "Guest"
	return context