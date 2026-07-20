# install_phase_a.ps1 -- Site Cost Category + Labour Attendance Log
# Run from inside C:\Users\simph\Downloads\sbi_projects_live

$ErrorActionPreference = "Stop"
$base = "sbi_projects\sbi_projects\doctype"

if (-not (Test-Path $base)) { Write-Error "Not found: $base -- are you in sbi_projects_live?"; exit 1 }

# --- read the module name from an existing doctype so it always matches ---
$ref = Join-Path $base "steel_fabrication_import\steel_fabrication_import.json"
if (-not (Test-Path $ref)) { Write-Error "Reference doctype not found: $ref"; exit 1 }
$module = (Get-Content $ref -Raw | ConvertFrom-Json).module
if (-not $module) { Write-Error "Could not read module from $ref"; exit 1 }
Write-Host "Using module: $module" -ForegroundColor Cyan

$c_site_cost_category_json = @'
{
 "actions": [], "allow_rename": 1, "autoname": "field:category_name",
 "creation": "2026-07-20 08:00:00", "doctype": "DocType", "engine": "InnoDB",
 "field_order": ["category_name","is_active","is_labour_cost","cb_1","expense_account","default_cost_type","description"],
 "fields": [
  {"fieldname":"category_name","fieldtype":"Data","label":"Category Name","reqd":1,"unique":1,"in_list_view":1},
  {"fieldname":"is_active","fieldtype":"Check","label":"Is Active","default":"1","in_list_view":1},
  {"fieldname":"is_labour_cost","fieldtype":"Check","label":"Is Labour Cost","description":"Tick for manpower categories. Used by wage roll-up."},
  {"fieldname":"cb_1","fieldtype":"Column Break"},
  {"fieldname":"expense_account","fieldtype":"Link","label":"Default Expense Account","options":"Account","description":"Used when this category is posted to the general ledger."},
  {"fieldname":"default_cost_type","fieldtype":"Select","label":"Cost Source","options":"Site Entry\nERPNext Transaction\nBoth","default":"Site Entry","in_list_view":1,"description":"Site Entry: captured in Daily Work Log. ERPNext Transaction: comes from Stock or Purchase documents."},
  {"fieldname":"description","fieldtype":"Small Text","label":"Description"}
 ],
 "index_web_pages_for_search":1, "links":[],
 "modified":"2026-07-20 08:00:00", "modified_by":"Administrator",
 "module":"__MODULE__", "name":"Site Cost Category", "naming_rule":"By fieldname",
 "owner":"Administrator",
 "permissions":[
  {"role":"System Manager","read":1,"write":1,"create":1,"delete":1,"report":1,"export":1},
  {"role":"Projects Manager","read":1,"write":1,"create":1,"report":1,"export":1},
  {"role":"Projects User","read":1}
 ],
 "sort_field":"modified","sort_order":"DESC","states":[],
 "track_changes":1
}
'@

$c_site_cost_category_py = @'
import frappe
from frappe.model.document import Document


class SiteCostCategory(Document):
	def validate(self):
		self.category_name = (self.category_name or "").strip()
'@

$c_labour_attendance_log_json = @'
{
 "actions": [], "allow_rename": 0, "autoname": "naming_series:",
 "creation": "2026-07-20 08:00:00", "doctype": "DocType", "engine": "InnoDB",
 "field_order": ["naming_series","labour","labour_name","project","cb_1","log_type","log_datetime","log_date","sb_geo","latitude","longitude","cb_2","distance_from_site","within_geofence","sb_verify","photo","verification_method","cb_3","face_confidence","device_id","sb_note","remarks"],
 "fields": [
  {"fieldname":"naming_series","fieldtype":"Select","label":"Series","options":"LATT-.YYYY.-","default":"LATT-.YYYY.-","reqd":1},
  {"fieldname":"labour","fieldtype":"Link","label":"Labour","options":"Labour","reqd":1,"in_list_view":1,"in_standard_filter":1},
  {"fieldname":"labour_name","fieldtype":"Data","label":"Labour Name","fetch_from":"labour.labour_name","read_only":1,"in_list_view":1},
  {"fieldname":"project","fieldtype":"Link","label":"Site (Project)","options":"Project","reqd":1,"in_standard_filter":1},
  {"fieldname":"cb_1","fieldtype":"Column Break"},
  {"fieldname":"log_type","fieldtype":"Select","label":"Log Type","options":"IN\nLUNCH OUT\nLUNCH IN\nTEA OUT\nTEA IN\nOUT","reqd":1,"in_list_view":1,"in_standard_filter":1},
  {"fieldname":"log_datetime","fieldtype":"Datetime","label":"Log Time","reqd":1,"in_list_view":1},
  {"fieldname":"log_date","fieldtype":"Date","label":"Log Date","read_only":1,"in_standard_filter":1},
  {"fieldname":"sb_geo","fieldtype":"Section Break","label":"Location"},
  {"fieldname":"latitude","fieldtype":"Float","label":"Latitude","precision":"6"},
  {"fieldname":"longitude","fieldtype":"Float","label":"Longitude","precision":"6"},
  {"fieldname":"cb_2","fieldtype":"Column Break"},
  {"fieldname":"distance_from_site","fieldtype":"Float","label":"Distance from Site (m)","precision":"1","read_only":1},
  {"fieldname":"within_geofence","fieldtype":"Check","label":"Within Geo-fence","read_only":1},
  {"fieldname":"sb_verify","fieldtype":"Section Break","label":"Verification"},
  {"fieldname":"photo","fieldtype":"Attach Image","label":"Capture Photo"},
  {"fieldname":"verification_method","fieldtype":"Select","label":"Verification Method","options":"Face\nManual\nGPS Only","default":"Face","in_list_view":1},
  {"fieldname":"cb_3","fieldtype":"Column Break"},
  {"fieldname":"face_confidence","fieldtype":"Float","label":"Face Match Confidence","precision":"3","read_only":1},
  {"fieldname":"device_id","fieldtype":"Data","label":"Device ID","read_only":1},
  {"fieldname":"sb_note","fieldtype":"Section Break"},
  {"fieldname":"remarks","fieldtype":"Small Text","label":"Remarks"}
 ],
 "index_web_pages_for_search":1, "links":[],
 "modified":"2026-07-20 08:00:00", "modified_by":"Administrator",
 "module":"__MODULE__", "name":"Labour Attendance Log", "naming_rule":"By \"Naming Series\" field",
 "owner":"Administrator",
 "permissions":[
  {"role":"System Manager","read":1,"write":1,"create":1,"delete":1,"report":1,"export":1},
  {"role":"Projects Manager","read":1,"write":1,"create":1,"delete":1,"report":1,"export":1},
  {"role":"Projects User","read":1,"write":1,"create":1,"report":1}
 ],
 "sort_field":"log_datetime","sort_order":"DESC","states":[],
 "title_field":"labour_name","track_changes":1
}
'@

$c_labour_attendance_log_py = @'
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
'@

$targets = @(
    @{ folder = "site_cost_category"; file = "site_cost_category.json"; body = $c_site_cost_category_json },
    @{ folder = "site_cost_category"; file = "site_cost_category.py"; body = $c_site_cost_category_py },
    @{ folder = "labour_attendance_log"; file = "labour_attendance_log.json"; body = $c_labour_attendance_log_json },
    @{ folder = "labour_attendance_log"; file = "labour_attendance_log.py"; body = $c_labour_attendance_log_py }
)

foreach ($t in $targets) {
    $dir = Join-Path $base $t.folder
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
    $init = Join-Path $dir "__init__.py"
    if (-not (Test-Path $init)) { New-Item -ItemType File -Path $init | Out-Null }
    $body = $t.body -replace "__MODULE__", $module
    Set-Content -Path (Join-Path $dir $t.file) -Value $body -NoNewline -Encoding UTF8
    Write-Host ("  wrote " + $t.folder + "/" + $t.file) -ForegroundColor Green
}

# --- validate the JSON actually parses before we let anything be pushed ---
foreach ($t in $targets | Where-Object { $_.file -like "*.json" }) {
    $p = Join-Path (Join-Path $base $t.folder) $t.file
    try { $j = Get-Content $p -Raw | ConvertFrom-Json }
    catch { Write-Error ("Invalid JSON: " + $p); exit 1 }
    Write-Host ("  ok " + $j.name + "  module=" + $j.module + "  fields=" + $j.fields.Count) -ForegroundColor Cyan
}

Write-Host ""
git status --short
Write-Host ""
$ans = Read-Host "Commit and push? (y/n)"
if ($ans -ne "y") { Write-Host "Stopped. Nothing pushed." -ForegroundColor Yellow; exit 0 }
git add $base
git commit -m "feat: Site Cost Category master and Labour Attendance Log with geofence"
git push origin main
Write-Host "Pushed. Now: Frappe Cloud -> Fetch Latest Updates -> Deploy" -ForegroundColor Green
