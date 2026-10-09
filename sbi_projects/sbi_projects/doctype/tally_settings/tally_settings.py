# Copyright (c) 2026, Velmaska and contributors
import frappe
from frappe.model.document import Document
from frappe.utils import cint


# Written by the agent / sync buttons, never by the form. Saving the form keeps the stored value,
# so a Save right after "Retry Failed" or "Re-read Tally Masters" no longer undoes it.
SYNC_STATE = (
	"agent_user", "last_heartbeat", "agent_version", "agent_host", "tally_reachable", "tally_companies",
	"last_sync_on", "last_agent_error", "current_alt_mst_id", "last_alt_mst_id", "current_alt_vch_id",
	"last_alt_vch_id", "cancel_cursor", "force_import_guids", "opening_requested", "opening_status",
)


class TallySettings(Document):
	def validate(self):
		stored = frappe.db.get_singles_dict("Tally Settings")
		for field in SYNC_STATE:
			if field in stored:
				self.set(field, stored.get(field))

		self.tally_company = (self.tally_company or "").strip()
		self.tally_host = (self.tally_host or "localhost").strip()
		if not 1 <= cint(self.tally_port) <= 65535:
			frappe.throw("Tally Port must be between 1 and 65535 (TallyPrime default is 9000).")
		if cint(self.poll_seconds) < 30:
			self.poll_seconds = 30
		if cint(self.batch_size) < 1:
			self.batch_size = 25

		before = self.get_doc_before_save()
		if before and (before.company != self.company or str(before.start_date) != str(self.start_date)
				or before.tally_company != self.tally_company):
			# a different company or period means everything must be re-read
			self.last_alt_mst_id = 0
			self.last_alt_vch_id = 0
			self.cancel_cursor = None

		if self.company and not self.group_map:
			from sbi_projects.tally.importer import default_group_rows
			for row in default_group_rows(self.company):
				self.append("group_map", row)

		for row in self.group_map:
			if row.erpnext_account and frappe.db.get_value("Account", row.erpnext_account, "company") != self.company:
				frappe.throw("Group Map row " + str(row.idx) + ": " + row.erpnext_account +
					" does not belong to " + str(self.company))
