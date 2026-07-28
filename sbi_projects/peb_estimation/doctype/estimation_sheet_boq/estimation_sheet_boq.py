# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EstimationSheetBOQ(Document):
	def validate(self):
		self.compute_amounts()
		self.compute_totals()

	def compute_amounts(self):
		for row in (self.lines or []):
			row.qty = flt(row.qty)
			row.rate = flt(row.rate)
			row.amount = flt(row.qty) * flt(row.rate)

	def compute_totals(self):
		base = sum(flt(r.amount) for r in (self.lines or []))
		self.base_total = base

		markup = 0.0
		for pct in (self.site_establishment_pct, self.contingency_pct,
		            self.overhead_pct, self.profit_pct, self.incentive_pct):
			markup += base * (flt(pct) / 100.0)

		self.markup_total = markup
		self.grand_total = base + markup

		area = flt(self.built_up_area)
		self.rate_per_sft = (base + markup) / area if area else 0

	@frappe.whitelist()
	def recalculate_rates(self):
		"""Refresh WA-source line rates from the Rate Card. Manual lines untouched."""
		card = self.rate_card
		if not card:
			from sbi_projects.peb_estimation.doctype.rate_card.rate_card import RateCard
			card = RateCard.get_default()
		if not card:
			frappe.throw(_("No Rate Card selected and no default Rate Card found."))
		updated = 0
		for row in (self.lines or []):
			if row.rate_source == "Manual":
				continue
			if not row.work_item:
				continue
			wi = frappe.get_cached_doc("Work Item", row.work_item)
			row.rate = wi.computed_rate(card)
			row.amount = flt(row.qty) * flt(row.rate)
			updated += 1
		self.compute_totals()
		self.save(ignore_permissions=True)
		return updated

	@frappe.whitelist()
	def import_lines(self, file_url, replace=0):
		"""Append (or replace) BOQ lines from an uploaded Excel/CSV file.

		Expected columns (header row, case-insensitive, order-independent):
			Stage, Category, Work Item, Description, UOM, Qty, Rate, Remarks

		Rules applied per row:
		  - Qty / Rate are coerced with flt, so blanks and text are safe.
		  - A rate supplied in the file marks the line Manual, so a later
		    "Recalculate Rates (WA)" will not overwrite the imported price.
		  - A blank rate leaves the line on WA, to be priced from the Rate Card.
		  - Unknown Work Item codes are reported, not silently dropped.
		"""
		if not file_url:
			frappe.throw(_("Attach a file first."))

		rows = _read_tabular(file_url)
		if len(rows) < 2:
			frappe.throw(_("The file has no data rows."))

		header = [str(c or "").strip().lower() for c in rows[0]]
		required = "qty"
		if required not in header:
			frappe.throw(
				_("Could not find a <b>Qty</b> column. Please use the downloaded template.")
			)

		def col(*names):
			for n in names:
				if n in header:
					return header.index(n)
			return None

		idx = {
			"stage": col("stage"),
			"category": col("category"),
			"work_item": col("work item", "work_item", "item"),
			"description": col("description", "particulars"),
			"uom": col("uom", "unit"),
			"qty": col("qty", "quantity"),
			"rate": col("rate"),
			"remarks": col("remarks", "remark"),
		}

		if replace in (1, "1", True, "true"):
			self.lines = []

		valid_items = set(
			frappe.get_all("Work Item", filters={"is_active": 1}, pluck="name")
		)

		added, unknown, skipped = 0, [], 0
		for r_no, raw in enumerate(rows[1:], start=2):
			def val(key):
				i = idx.get(key)
				if i is None or i >= len(raw):
					return None
				v = raw[i]
				return str(v).strip() if v is not None else None

			work_item = val("work_item")
			description = val("description")
			qty = flt(val("qty"))

			# a row with nothing usable is just blank spacing in the sheet
			if not work_item and not description and not qty:
				skipped += 1
				continue

			if work_item and work_item not in valid_items:
				unknown.append(_("Row {0}: {1}").format(r_no, work_item))
				work_item = None

			rate = flt(val("rate"))
			row = self.append("lines", {
				"stage": val("stage"),
				"category": val("category"),
				"work_item": work_item,
				"description": description,
				"uom": val("uom"),
				"qty": qty,
				"rate": rate,
				"rate_source": "Manual" if rate else "WA",
				"remarks": val("remarks"),
			})
			row.amount = flt(row.qty) * flt(row.rate)
			added += 1

		self.compute_totals()
		self.save(ignore_permissions=True)
		frappe.db.commit()

		return {"added": added, "skipped": skipped, "unknown": unknown}


def _read_tabular(file_url):
	"""Return a list of rows from an attached .xlsx / .xls / .csv file."""
	import os

	ext = os.path.splitext((file_url or "").split("?")[0])[1].lower()

	if ext == ".csv":
		from frappe.utils.csvutils import read_csv_content

		file_doc = frappe.get_doc("File", {"file_url": file_url})
		return read_csv_content(file_doc.get_content())

	if ext in (".xlsx", ".xls"):
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		return read_xlsx_file_from_attached_file(file_url=file_url)

	frappe.throw(_("Unsupported file type {0}. Use .xlsx or .csv.").format(ext or "?"))


@frappe.whitelist()
def download_boq_template():
	"""Stream an .xlsx template: BOQ Lines sheet + a reference sheet of Work Items."""
	from io import BytesIO

	import openpyxl
	from openpyxl.styles import Alignment, Font, PatternFill

	headers = ["Stage", "Category", "Work Item", "Description", "UOM", "Qty", "Rate", "Remarks"]

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = "BOQ Lines"

	head_fill = PatternFill("solid", fgColor="BE1E2D")
	head_font = Font(color="FFFFFF", bold=True)
	for c, h in enumerate(headers, start=1):
		cell = ws.cell(row=1, column=c, value=h)
		cell.fill = head_fill
		cell.font = head_font
		cell.alignment = Alignment(horizontal="center")

	for c, w in enumerate([14, 14, 20, 40, 10, 10, 12, 24], start=1):
		ws.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w
	ws.freeze_panes = "A2"

	# two illustrative rows -- one WA-priced, one manually priced
	samples = [
		["Stage 1", "Civil", "CIV-RCC-M25", "RCC M25 for footings", "CUM", 25, "", "leave Rate blank to price from Rate Card"],
		["Stage 1", "Civil", "CIV-PCC-M10", "PCC bedding", "CUM", 12, 5460, "Rate filled = Manual, kept on Recalculate"],
	]
	for r, row in enumerate(samples, start=2):
		for c, v in enumerate(row, start=1):
			ws.cell(row=r, column=c, value=v)

	# reference sheet so the estimator can copy exact codes
	ref = wb.create_sheet("Work Items")
	for c, h in enumerate(["Work Item Code", "Name", "Category", "UOM"], start=1):
		cell = ref.cell(row=1, column=c, value=h)
		cell.fill = head_fill
		cell.font = head_font
	for c, w in enumerate([22, 38, 16, 10], start=1):
		ref.column_dimensions[openpyxl.utils.get_column_letter(c)].width = w
	ref.freeze_panes = "A2"

	items = frappe.get_all(
		"Work Item",
		filters={"is_active": 1},
		fields=["name", "work_item_name", "category", "uom"],
		order_by="category asc, name asc",
	)
	for r, it in enumerate(items, start=2):
		ref.cell(row=r, column=1, value=it.name)
		ref.cell(row=r, column=2, value=it.work_item_name)
		ref.cell(row=r, column=3, value=it.category)
		ref.cell(row=r, column=4, value=it.uom)

	buf = BytesIO()
	wb.save(buf)

	frappe.response["filename"] = "estimation_sheet_boq_template.xlsx"
	frappe.response["filecontent"] = buf.getvalue()
	frappe.response["type"] = "binary"
