"""Public download page for the SBI Site app (route: /sbi_apps).

Shows the Android (APK), iOS and Windows (EXE) install options plus the
web (PWA) install. Links are filled in once the store packages are built.
"""

import frappe

no_cache = 1


def get_context(context):
	context.no_header = 1
	context.no_breadcrumbs = 1
	# Fill these once the packages are hosted (see notes in chat).
	context.apk_url = "/assets/sbi_projects/site_app/sbi-site.apk"      # Android APK
	context.exe_url = "/assets/sbi_projects/site_app/sbi-site-setup.exe"  # Windows EXE
	context.ios_url = ""   # App Store link once published
	return context