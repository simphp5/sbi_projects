"""Out-of-boundary attendance, for the office to review.

Attendance is never blocked on distance -- a genuine worker with a poor GPS
fix should not be turned away.  Instead every punch is stored with its distance
from the site centre and whether it fell inside the fence, and this surfaces the
ones that did not so the office can follow up.
"""

import frappe
from frappe.utils import flt, getdate, add_days, today


@frappe.whitelist()
def get_out_of_bounds(project=None, from_date=None, to_date=None):
	"""Punches that landed outside the geo-fence, newest first."""
	from_date = from_date or add_days(today(), -7)
	to_date = to_date or today()

	filters = {
		"within_geofence": 0,
		"log_datetime": ["between", [from_date + " 00:00:00", to_date + " 23:59:59"]],
	}
	if project:
		filters["project"] = project

	if not frappe.get_meta("Labour Attendance Log").has_field("within_geofence"):
		return {"rows": [], "note": "Geo-fence fields are not set up."}

	rows = frappe.get_all(
		"Labour Attendance Log",
		filters=filters,
		fields=["name", "labour", "project", "log_type", "log_datetime",
		        "distance_from_site", "latitude", "longitude"],
		order_by="log_datetime desc",
		limit_page_length=200,
	)

	for r in rows:
		r["labour_name"] = frappe.db.get_value("Labour", r.labour, "labour_name") or r.labour
		r["project_name"] = frappe.db.get_value("Project", r.project, "project_name") or r.project
		r["map_link"] = (
			"https://www.google.com/maps?q={0},{1}".format(r.latitude, r.longitude)
			if r.latitude and r.longitude else None
		)

	return {
		"rows": rows,
		"count": len(rows),
		"from_date": str(from_date),
		"to_date": str(to_date),
	}