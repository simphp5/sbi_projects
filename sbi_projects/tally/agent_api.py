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
from sbi_projects.tally.common import AGENT_ROLE, context_for, contexts, settings, set_settings, short, tally_ready

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
	"""Jobs for one stage. Every stage except 'status' runs once per Tally company; each job id is
	prefixed with that company's row so its answer is processed in the right company."""
	_auth()
	if stage not in STAGES:
		frappe.throw("Unknown stage " + str(stage))
	builder = STAGES[stage][0]
	out, more = [], False
	if stage == "status":
		jobs, _ = builder(settings())
		out = [_job("", j) for j in jobs]
	else:
		for c in contexts():
			if not tally_ready(c):
				continue
			frappe.flags.tally_ctx = c
			try:
				jobs, m = builder(c)
			finally:
				frappe.flags.tally_ctx = None
			more = more or m
			out += [_job(c.rowkey + "~", j) for j in jobs]
	frappe.db.commit()
	return {"jobs": out, "more": bool(more)}


def _job(prefix, job):
	meta = {k: v for k, v in job.items() if k not in ("id", "xml")}
	return {"id": prefix + job["id"], "xml": job["xml"], "meta": meta}


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
	"""Process answers; each Tally company's answers are processed inside its own context."""
	if stage == "status":
		groups = [(None, results)]
	else:
		by_key = {}
		for r in results:
			key, _, rest = (r.get("id") or "").partition("~")
			by_key.setdefault(key, []).append(dict(r, id=rest))
		groups = [(context_for(k), rows) for k, rows in by_key.items()]
	failed = []
	for ctx, rows in groups:
		if stage != "status" and ctx is None:
			continue  # company removed from settings meanwhile
		frappe.flags.tally_ctx = ctx
		try:
			processor(rows)
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			tb = frappe.get_traceback()
			frappe.log_error(tb, "Tally sync: " + stage + (" (" + ctx.tally_company + ")" if ctx else ""))
			set_settings(last_agent_error=short("Stage '" + stage + "' failed: " + tb.strip().splitlines()[-1], 500))
			frappe.db.commit()
			failed.append(stage)  # carry on with the other company, report at the end
		finally:
			frappe.flags.tally_ctx = None
	if failed:
		raise frappe.ValidationError("Tally stage '" + stage + "' failed - see Error Log")


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
		for c in contexts():
			if c.row and tally_ready(c):
				frappe.db.set_value("Tally Company Map", c.row, "last_sync_on", values["last_sync_on"],
					update_modified=False)
	set_settings(**values)
	frappe.db.commit()
	return "ok"
