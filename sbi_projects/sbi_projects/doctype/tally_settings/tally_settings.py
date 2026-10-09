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
ROW_STATE = (
	"reachable", "last_error", "last_sync_on", "current_alt_mst_id", "last_alt_mst_id",
	"current_alt_vch_id", "last_alt_vch_id", "cancel_cursor",
)
ROW_RESET = ("last_alt_mst_id", "last_alt_vch_id", "cancel_cursor")


class TallySettings(Document):
	def validate(self):
		stored = frappe.db.get_singles_dict("Tally Settings")
		for field in SYNC_STATE:
			if field in stored:
				self.set(field, stored.get(field))

		self.tally_host = (self.tally_host or "localhost").strip()
		if not 1 <= cint(self.tally_port) <= 65535:
			frappe.throw("Tally Port must be between 1 and 65535 (TallyPrime default is 9000).")
		if cint(self.poll_seconds) < 30:
			self.poll_seconds = 30
		if cint(self.batch_size) < 1:
			self.batch_size = 25

		self._migrate_single_company()
		self._validate_companies()
		self._keep_row_state()

		first = self.companies[0] if self.companies else None
		if first:
			self.company = first.erpnext_company
			self.tally_company = first.tally_company

		if self.company and not self.group_map:
			from sbi_projects.tally.importer import default_group_rows
			for row in default_group_rows(self.company):
				self.append("group_map", row)
		for row in self.group_map:
			if row.erpnext_account and frappe.db.get_value("Account", row.erpnext_account, "company") != self.company:
				frappe.throw("Group Map row " + str(row.idx) + ": " + row.erpnext_account + " does not belong to "
					+ str(self.company) + " (the first company). Other companies use the same groups by name.")

	def _migrate_single_company(self):
		"""Settings made before the Tally Companies table: move that company into row 1 with its progress."""
		if self.companies or not (self.company and self.tally_company):
			return
		stored = frappe.db.get_singles_dict("Tally Settings")
		self.append("companies", {
			"enabled": 1, "tally_company": self.tally_company.strip(), "erpnext_company": self.company,
			"start_date": None, "reachable": stored.get("tally_reachable"),
			"current_alt_mst_id": stored.get("current_alt_mst_id"), "last_alt_mst_id": stored.get("last_alt_mst_id"),
			"current_alt_vch_id": stored.get("current_alt_vch_id"), "last_alt_vch_id": stored.get("last_alt_vch_id"),
			"cancel_cursor": stored.get("cancel_cursor"),
		})

	def _validate_companies(self):
		seen_tally, seen_erp = set(), set()
		for row in self.companies:
			row.tally_company = (row.tally_company or "").strip()
			key = row.tally_company.lower()
			if key in seen_tally:
				frappe.throw("Tally company '" + row.tally_company + "' is listed twice.")
			if row.erpnext_company in seen_erp:
				frappe.throw("ERPNext Company '" + row.erpnext_company + "' is used by two Tally companies. "
					"Each Tally company (GSTIN) needs its own ERPNext Company.")
			seen_tally.add(key)
			seen_erp.add(row.erpnext_company)

	def _keep_row_state(self):
		"""Progress markers on each row come from the database, not the form. A row whose company or
		dates change is read again from scratch."""
		for row in self.companies:
			if not row.name or row.is_new() or not frappe.db.exists("Tally Company Map", row.name):
				continue
			stored = frappe.db.get_value("Tally Company Map", row.name,
				list(ROW_STATE) + ["tally_company", "erpnext_company", "start_date"], as_dict=True)
			for field in ROW_STATE:
				row.set(field, stored.get(field))
			if (stored.tally_company != row.tally_company or stored.erpnext_company != row.erpnext_company
					or str(stored.start_date or "") != str(row.start_date or "")):
				for field in ROW_RESET:
					row.set(field, None)
