# Copyright (c) 2026, Velmaska and contributors
# Applies Shiv Bharat branding (splash, favicon, navbar logo) on every deploy.
# Every step is idempotent and safe to re-run from after_migrate.

import frappe

ASSET = "/assets/sbi_projects/images"

BRANDING = {
	"splash_image": f"{ASSET}/sbi_splash.png",   # desk boot splash
	"favicon": f"{ASSET}/sbi_favicon.png",        # browser tab icon
	"banner_image": f"{ASSET}/sbi_logo.png",      # website navbar logo
	"app_name": "Shiv Bharat ERP",
}


def setup_branding():
	_apply_website_settings()
	_apply_navbar_logo()


def _apply_website_settings():
	ws = frappe.get_single("Website Settings")
	changed = False
	for field, value in BRANDING.items():
		if hasattr(ws, field) and ws.get(field) != value:
			ws.set(field, value)
			changed = True
	if changed:
		ws.save(ignore_permissions=True)


def _apply_navbar_logo():
	# Desk top-left logo lives on the Navbar Settings single.
	if not frappe.db.exists("DocType", "Navbar Settings"):
		return
	nav = frappe.get_single("Navbar Settings")
	logo = f"{ASSET}/sbi_logo.png"
	if hasattr(nav, "app_logo") and nav.get("app_logo") != logo:
		nav.app_logo = logo
		nav.save(ignore_permissions=True)
