#!/usr/bin/env python3
"""
Tally <-> ERPNext agent  (Shiv Bharat Infrastructures)
======================================================
Runs on the Windows PC where TallyPrime is open. Python 3.8+, standard library
only. It is a relay: ERPNext decides what to read from or write to Tally, this
program carries the XML to TallyPrime and brings the answer back.

Setup (all settings live in ERPNext > Tally Settings):
  1. In ERPNext open Tally Settings > Agent > Generate Agent Key. A config.json downloads.
  2. Put config.json in the same folder as this file.
  3. Run:  python tally_agent.py test     (checks ERPNext and Tally)
           python tally_agent.py          (runs forever; agent_autostart.ps1 starts it at login)

Commands:
  python tally_agent.py            run continuously
  python tally_agent.py once       run one sync cycle and exit
  python tally_agent.py test       check both connections and exit
"""

import json
import logging
import logging.handlers
import os
import socket
import sys
import time
import urllib.error
import urllib.request

VERSION = "2.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
LOGFILE = os.path.join(HERE, "tally_agent.log")
API = "/api/method/sbi_projects.tally.agent_api."

log = logging.getLogger("tally_agent")


class Stop(Exception):
	pass


def setup_logging():
	log.setLevel(logging.INFO)
	fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
	fh = logging.handlers.RotatingFileHandler(LOGFILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
	fh.setFormatter(fmt)
	log.addHandler(fh)
	if sys.stdout and sys.stdout.isatty() or "pythonw" not in sys.executable.lower():
		ch = logging.StreamHandler(sys.stdout)
		ch.setFormatter(fmt)
		log.addHandler(ch)


def load_config():
	if not os.path.exists(CONFIG):
		raise Stop("config.json not found next to tally_agent.py. In ERPNext: Tally Settings > Agent > Generate Agent Key.")
	with open(CONFIG, "r", encoding="utf-8-sig") as f:
		cfg = json.load(f)
	for key in ("erpnext_url", "api_key", "api_secret"):
		if not cfg.get(key):
			raise Stop("config.json is missing " + key)
	cfg["erpnext_url"] = cfg["erpnext_url"].rstrip("/")
	return cfg


# ---------------------------------------------------------------- ERPNext
class ERPNext:
	def __init__(self, cfg):
		self.url = cfg["erpnext_url"]
		self.auth = "token " + cfg["api_key"] + ":" + cfg["api_secret"]

	def call(self, method, **kwargs):
		data = json.dumps(kwargs).encode("utf-8")
		req = urllib.request.Request(self.url + API + method, data=data, method="POST", headers={
			"Authorization": self.auth, "Content-Type": "application/json", "Accept": "application/json"})
		try:
			with urllib.request.urlopen(req, timeout=300) as resp:
				return json.loads(resp.read().decode("utf-8") or "{}").get("message")
		except urllib.error.HTTPError as e:
			body = e.read().decode("utf-8", "replace")
			try:
				j = json.loads(body)
				body = j.get("exception") or j.get("_server_messages") or body
			except ValueError:
				pass
			if e.code in (401, 403):
				raise Stop("ERPNext refused the key (HTTP " + str(e.code) + "). Generate a new key in Tally Settings "
					"and replace config.json.")
			raise RuntimeError("ERPNext " + method + " failed (HTTP " + str(e.code) + "): " + str(body)[:400])
		except urllib.error.URLError as e:
			raise RuntimeError("Cannot reach ERPNext at " + self.url + ": " + str(e.reason))


# ---------------------------------------------------------------- Tally
def post_to_tally(tally_url, xml):
	body = xml.encode("ascii", "xmlcharrefreplace")
	req = urllib.request.Request(tally_url, data=body, method="POST", headers={"Content-Type": "text/xml"})
	with urllib.request.urlopen(req, timeout=600) as resp:
		raw = resp.read()
	if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
		return raw.decode("utf-16")
	if raw[:200].count(b"\x00") > 20:
		return raw.decode("utf-16-le", "replace")
	return raw.decode("utf-8", "replace")


def run_job(tally_url, job):
	out = {"id": job["id"], "meta": job.get("meta") or {}, "response": "", "error": None}
	try:
		out["response"] = post_to_tally(tally_url, job["xml"])
	except urllib.error.URLError as e:
		out["error"] = "TallyPrime not reachable at " + tally_url + " (" + str(getattr(e, "reason", e)) + \
			"). Is TallyPrime open, and is Client/Server set to Both on that port?"
	except Exception as e:
		out["error"] = str(e)[:500]
	return out


# ---------------------------------------------------------------- cycle
def run_stage(erp, tally_url, stage):
	rounds = 0
	while True:
		rounds += 1
		got = erp.call("get_jobs", stage=stage) or {}
		jobs = got.get("jobs") or []
		if not jobs:
			return 0
		log.info("%s: %d request(s) to Tally", stage, len(jobs))
		results = [run_job(tally_url, job) for job in jobs]
		errors = [r["error"] for r in results if r["error"]]
		if errors:
			log.warning("%s: %s", stage, errors[0])
		ack = erp.call("submit_results", stage=stage, results=results) or {}
		token = ack.get("token")
		if token:
			wait_for(erp, stage, token)
		if not got.get("more") or rounds >= 20:
			return len(jobs)


def wait_for(erp, stage, token):
	started = time.time()
	while time.time() - started < 3600:
		time.sleep(3 if time.time() - started < 60 else 10)
		state = erp.call("stage_status", token=token)
		if state == "done":
			return
		if state and str(state).startswith("error"):
			log.warning("%s processing in ERPNext: %s", stage, state)
			return
	log.warning("%s: ERPNext still processing after an hour; moving on", stage)


def cycle(erp, cfg):
	info = erp.call("hello", agent_version=VERSION, hostname=socket.gethostname()) or {}
	tally_url = (cfg.get("tally_url") or info.get("tally_url") or "http://localhost:9000").rstrip("/")
	for stage in info.get("stages") or []:
		run_stage(erp, tally_url, stage)
	erp.call("cycle_done")
	return info


def main():
	setup_logging()
	cmd = (sys.argv[1] if len(sys.argv) > 1 else "run").lower()
	try:
		cfg = load_config()
	except Stop as e:
		log.error(str(e))
		sys.exit(1)
	erp = ERPNext(cfg)

	if cmd == "test":
		try:
			info = erp.call("hello", agent_version=VERSION, hostname=socket.gethostname())
			print("ERPNext : OK (" + cfg["erpnext_url"] + ")")
		except (Stop, RuntimeError) as e:
			print("ERPNext : FAILED - " + str(e))
			sys.exit(1)
		tally_url = (cfg.get("tally_url") or info.get("tally_url")).rstrip("/")
		try:
			text = post_to_tally(tally_url, "<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
				"<TYPE>Collection</TYPE><ID>C</ID></HEADER><BODY><DESC><STATICVARIABLES><SVEXPORTFORMAT>"
				"$$SysName:XML</SVEXPORTFORMAT></STATICVARIABLES><TDL><TDLMESSAGE><COLLECTION NAME=\"C\">"
				"<TYPE>Company</TYPE><NATIVEMETHOD>Name</NATIVEMETHOD></COLLECTION></TDLMESSAGE></TDL>"
				"</DESC></BODY></ENVELOPE>")
			import re
			names = re.findall(r"<COMPANY\s+NAME=\"([^\"]*)\"", text)
			print("Tally   : OK (" + tally_url + ") - open companies: " + (", ".join(names) or "none"))
		except Exception as e:
			print("Tally   : FAILED (" + tally_url + ") - " + str(e))
			sys.exit(1)
		print("Sync is " + ("ENABLED" if info.get("enabled") else "DISABLED - tick 'Enable Tally Sync' in Tally Settings"))
		return

	log.info("Tally agent %s starting - ERPNext %s", VERSION, cfg["erpnext_url"])
	while True:
		wait = 120
		try:
			info = cycle(erp, cfg)
			wait = int(info.get("poll_seconds") or 120)
		except Stop as e:
			log.error(str(e))
			wait = 600
		except Exception as e:
			log.error("Cycle failed: %s", e)
			try:
				erp.call("cycle_done", error="Agent: " + str(e)[:400])
			except Exception:
				pass
		if cmd == "once":
			break
		time.sleep(wait)


if __name__ == "__main__":
	main()
