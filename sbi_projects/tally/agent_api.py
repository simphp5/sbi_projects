# Copyright (c) 2026, Velmaska and contributors
"""Endpoints the Tally agent calls.

The agent is a relay: ERPNext builds every Tally request, the agent posts it
to TallyPrime and hands the raw answer back. Per cycle, for each stage that
hello() lists:

	get_jobs(stage) -> agent runs each job against Tally -> submit_results(stage, results)
	-> (slow stages) stage_status(token) until done

then cycle_done().
"""

import json

import frappe
from frappe.utils import cint, now_datetime

from sbi_projects.tally import exporter, importer
from sbi_projects.tally.common import AGENT_ROLE, settings, set_settings, short, tally_ready

# stage -> (job builder, result processor, run in background?)
STAGES = {
	"status": (importer.status_jobs, importer.process_status, False),
	"masters": (importer.masters_jobs, importer.process_masters, True),
	"export_masters": (exporter.export_masters_jobs, exporter.process_export_masters, False),
	"export_vouchers": (exporter.export_vouchers_jobs, exporter.process_export_vouchers, False),
	"import_vouchers": (importer.import_vouchers_jobs, importer.process_import_vouchers, True),
	"opening": (importer.opening_jobs, importer.process_opening, True),
}
ORDER = ["status", "masters", "export_masters", "export_vouchers", "import_vouchers", "opening"]
CACHE_KEY = "tally_stage:"


def _auth():
	frappe.only_for([AGENT_ROLE, "System Manager"])


@frappe.whitelist(methods=["POST"])
def hello(agent_version=None, hostname=None):
	_auth()
	s = settings()
	set_settings(last_heartbeat=now_datetime(), agent_version=short(agent_version, 40),
		agent_host=short(hostname, 140))
	frappe.db.commit()
	enabled = cint(s.enabled)
	return {
		"enabled": enabled,
		"tally_url": "http://" + (s.tally_host or "localhost").strip() + ":" + str(cint(s.tally_port) or 9000),
		"poll_seconds": max(cint(s.poll_seconds) or 120, 30),
		# Status runs even while disabled, so the setup screen can show the Tally companies.
		"stages": ORDER if enabled else ["status"],
	}


@frappe.whitelist(methods=["POST"])
def get_jobs(stage):
	_auth()
	if stage not in STAGES:
		frappe.throw("Unknown stage " + str(stage))
	s = settings()
	if stage != "status" and not tally_ready(s):
		return {"jobs": [], "more": False}
	builder = STAGES[stage][0]
	jobs, more = builder(s)
	frappe.db.commit()
	out = []
	for job in jobs:
		meta = {k: v for k, v in job.items() if k not in ("id", "xml")}
		out.append({"id": job["id"], "xml": job["xml"], "meta": meta})
	return {"jobs": out, "more": bool(more)}


@frappe.whitelist(methods=["POST"])
def submit_results(stage, results):
	"""results: [{id, meta, response, error}]"""
	_auth()
	if stage not in STAGES:
		frappe.throw("Unknown stage " + str(stage))
	if isinstance(results, str):
		results = json.loads(results)
	flat = []
	for r in results or []:
		row = dict(r.get("meta") or {})
		row.update(id=r.get("id"), response=r.get("response") or "", error=r.get("error"))
		flat.append(row)

	_, processor, background = STAGES[stage]
	if not background:
		_run(stage, processor, flat)
		return {"done": True}

	token = frappe.generate_hash(length=12)
	frappe.cache().set_value(CACHE_KEY + token, "queued", expires_in_sec=6 * 3600)
	frappe.enqueue("sbi_projects.tally.agent_api.run_stage", queue="long", timeout=3600,
		stage=stage, results=flat, token=token, enqueue_after_commit=True)
	return {"token": token}


def run_stage(stage, results, token):
	frappe.cache().set_value(CACHE_KEY + token, "running", expires_in_sec=6 * 3600)
	try:
		_run(stage, STAGES[stage][1], results)
		frappe.cache().set_value(CACHE_KEY + token, "done", expires_in_sec=6 * 3600)
	except Exception as e:
		frappe.cache().set_value(CACHE_KEY + token, "error: " + short(str(e), 300), expires_in_sec=6 * 3600)


def _run(stage, processor, results):
	try:
		processor(results)
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		tb = frappe.get_traceback()
		frappe.log_error(tb, "Tally sync: " + stage)
		set_settings(last_agent_error=short("Stage '" + stage + "' failed: " + tb.strip().splitlines()[-1], 500))
		frappe.db.commit()
		raise


@frappe.whitelist(methods=["POST"])
def stage_status(token):
	_auth()
	return frappe.cache().get_value(CACHE_KEY + str(token)) or "unknown"


@frappe.whitelist(methods=["POST"])
def cycle_done(error=None):
	_auth()
	values = {"last_heartbeat": now_datetime()}
	if error:
		values["last_agent_error"] = short(error, 500)
	else:
		values["last_sync_on"] = now_datetime()
	set_settings(**values)
	frappe.db.commit()
	return "ok"
