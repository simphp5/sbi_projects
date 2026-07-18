# Copyright (c) 2026, Velmaska and contributors

import frappe
from frappe import _
from frappe.model.document import Document

from frappe.utils import flt


class DailyWorkLog(Document):
	def validate(self):
		self.roll_up_labour()
		self.set_cumulative_qty()

	def roll_up_labour(self):
		self.total_labour = len(self.labour_details or [])
		self.total_hours = sum(flt(d.hours) for d in (self.labour_details or []))

	def set_cumulative_qty(self):
		"""Sum of qty on every submitted log for this task, plus this one."""
		if not self.task:
			self.cumulative_qty = flt(self.qty_completed)
			return
		previous = frappe.db.sql("""
			select sum(qty_completed) from `tabDaily Work Log`
			where task = %s and docstatus = 1 and name != %s
		""", (self.task, self.name or ""))
		self.cumulative_qty = flt(previous[0][0] if previous else 0) + flt(self.qty_completed)

	def on_submit(self):
		self.update_task_progress()

	def update_task_progress(self):
		if self.task and self.progress_percent:
			frappe.db.set_value("Task", self.task, "progress", flt(self.progress_percent))
