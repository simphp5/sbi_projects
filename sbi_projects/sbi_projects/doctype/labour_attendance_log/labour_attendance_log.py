import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, now_datetime

DEFAULT_GEOFENCE_RADIUS_M = 200.0

# What may follow what, within a single day.
ALLOWED_NEXT = {
	None: ("IN",),
	"IN": ("LUNCH OUT", "TEA OUT", "OUT"),
	"LUNCH OUT": ("LUNCH IN",),
	"LUNCH IN": ("LUNCH OUT", "TEA OUT", "OUT"),
	"TEA OUT": ("TEA IN",),
	"TEA IN": ("LUNCH OUT", "TEA OUT", "OUT"),
	"OUT": (),
}


class LabourAttendanceLog(Document):
	def validate(self):
		self.set_log_date()
		self.set_geofence()
		self.validate_sequence()

	def set_log_date(self):
		self.log_datetime = self.log_datetime or now_datetime()
		self.log_date = getdate(self.log_datetime)

	# ------------------------------------------------------------------
	# geo-fence
	# ------------------------------------------------------------------

	def set_geofence(self):
		if not (self.latitude and self.longitude):
			self.distance_from_site = 0
			self.within_geofence = 0
			return

		site_lat, site_lng, radius = get_site_geo(self.project)
		if not (site_lat and site_lng):
			# Site has no coordinates recorded -- cannot judge, do not block.
			self.distance_from_site = 0
			self.within_geofence = 0
			return

		distance = haversine_metres(
			flt(site_lat), flt(site_lng), flt(self.latitude), flt(self.longitude)
		)
		self.distance_from_site = distance
		self.within_geofence = 1 if distance <= radius else 0

	# ------------------------------------------------------------------
	# sequence
	# ------------------------------------------------------------------

	def validate_sequence(self):
		previous = self.get_previous_log_type()
		allowed = ALLOWED_NEXT.get(previous, ())

		if self.log_type in allowed:
			return

		if previous is None:
			frappe.throw(
				_("The first punch of the day must be IN, not {0}.").format(self.log_type)
			)

		if not allowed:
			frappe.throw(
				_("{0} has already punched OUT for {1}. No further punches are allowed.").format(
					self.labour_name or self.labour, self.log_date
				)
			)

		frappe.throw(
			_("Cannot record {0} after {1}. Expected one of: {2}.").format(
				self.log_type, previous, ", ".join(allowed)
			)
		)

	def get_previous_log_type(self):
		rows = frappe.get_all(
			"Labour Attendance Log",
			filters={
				"labour": self.labour,
				"log_date": self.log_date,
				"name": ("!=", self.name or ""),
			},
			fields=["log_type", "log_datetime"],
			order_by="log_datetime desc",
			limit=1,
		)
		if not rows:
			return None

		last = rows[0]
		if get_datetime(self.log_datetime) < get_datetime(last.log_datetime):
			frappe.throw(
				_("This punch is earlier than the last recorded punch ({0}).").format(
					last.log_datetime
				)
			)
		return last.log_type


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def get_site_geo(project):
	"""Return (latitude, longitude, radius_in_metres) for a site.

	Field names are resolved defensively: the Project custom fields were
	installed under an sbi_ prefix, but fall back to custom_ and to a
	default radius so a missing field never breaks a punch.
	"""
	if not project:
		return None, None, DEFAULT_GEOFENCE_RADIUS_M

	meta = frappe.get_meta("Project")

	def pick(*candidates):
		for name in candidates:
			if meta.has_field(name):
				return frappe.db.get_value("Project", project, name)
		return None

	lat = pick("sbi_site_latitude", "custom_site_latitude")
	lng = pick("sbi_site_longitude", "custom_site_longitude")
	radius = pick("sbi_geofence_radius", "custom_geofence_radius")

	return lat, lng, flt(radius) or DEFAULT_GEOFENCE_RADIUS_M


def haversine_metres(lat1, lon1, lat2, lon2):
	"""Great-circle distance between two points, in metres."""
	radius = 6371000.0
	phi1, phi2 = math.radians(lat1), math.radians(lat2)
	d_phi = math.radians(lat2 - lat1)
	d_lambda = math.radians(lon2 - lon1)

	a = (
		math.sin(d_phi / 2) ** 2
		+ math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
	)
	return round(2 * radius * math.asin(math.sqrt(a)), 1)


@frappe.whitelist()
def get_day_status(labour, log_date=None):
	"""What punch is expected next -- used by the tablet/PWA to show buttons."""
	log_date = getdate(log_date or now_datetime())
	rows = frappe.get_all(
		"Labour Attendance Log",
		filters={"labour": labour, "log_date": log_date},
		fields=["log_type", "log_datetime"],
		order_by="log_datetime asc",
	)
	last = rows[-1].log_type if rows else None
	return {
		"labour": labour,
		"date": str(log_date),
		"punches": rows,
		"last": last,
		"allowed_next": list(ALLOWED_NEXT.get(last, ())),
	}