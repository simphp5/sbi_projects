# Copyright (c) 2026, Velmaska and contributors
"""Tally XML: request builders and response parsers.

Pure Python with no Frappe import, so it can be unit-tested on its own.

Sign convention used everywhere in this package
-----------------------------------------------
``net`` = debit - credit, the ERPNext way of thinking.
Tally XML writes a debit as a NEGATIVE <AMOUNT> (with ISDEEMEDPOSITIVE=Yes)
and a credit as a POSITIVE amount, so ``net == -amount``.
"""

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from xml.sax.saxutils import escape as _escape

REMOTE_PREFIX = "ERPN:"

_BAD_DEC_REF = re.compile(r"&#(?:0*(?:[0-8]|1[124-9]|2[0-9]|3[01]));")
_BAD_HEX_REF = re.compile(r"&#x0*(?:[0-8bcef]|1[0-9a-f]);", re.I)
_BAD_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_AMP = re.compile(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)")


# ---------------------------------------------------------------- helpers
def x(value):
	"""Escape text for an XML element or attribute."""
	return _escape("" if value is None else str(value), {'"': "&quot;"})


def clean(text):
	"""Tally emits control characters (&#4; etc.) that no XML parser accepts."""
	text = _BAD_DEC_REF.sub("", text or "")
	text = _BAD_HEX_REF.sub("", text)
	text = _BAD_CHARS.sub("", text)
	return _AMP.sub("&amp;", text)


def decode(raw):
	"""Bytes from Tally -> str (Tally answers in UTF-8 or UTF-16)."""
	if isinstance(raw, str):
		return raw
	if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
		return raw.decode("utf-16")
	if raw[:200].count(b"\x00") > 20:
		return raw.decode("utf-16-le", "replace")
	return raw.decode("utf-8", "replace")


def tally_date(value):
	"""date / 'YYYY-MM-DD' -> 'YYYYMMDD'."""
	if isinstance(value, (date, datetime)):
		return value.strftime("%Y%m%d")
	return str(value)[:10].replace("-", "")


def parse_tally_date(value):
	"""'20261005' or '5-Oct-2026' -> '2026-10-05' (None if unreadable)."""
	value = (value or "").strip()
	if re.fullmatch(r"\d{8}", value):
		return value[:4] + "-" + value[4:6] + "-" + value[6:]
	for fmt in ("%d-%b-%Y", "%d-%b-%y", "%Y-%m-%d"):
		try:
			return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
		except ValueError:
			pass
	return None


def parse_amount(value):
	"""Tally amount text -> float. Handles '-1180.00', '1,180.00 Dr',
	and forex forms like '-$100.00 @ Rs. 83.00/$ = -Rs. 8300.00'."""
	value = (value or "").strip()
	if not value:
		return 0.0
	if "=" in value:
		value = value.rsplit("=", 1)[1]
	m = re.search(r"\d[\d,]*(?:\.\d+)?", value)
	if not m:
		return 0.0
	num = float(m.group(0).replace(",", ""))
	negative = "-" in value[:m.start()] or value.rstrip().endswith("Dr")
	return -num if negative else num


def yes(value):
	return (value or "").strip().lower() == "yes"


def amount_text(net):
	"""ERPNext net (debit positive) -> Tally AMOUNT text."""
	return "%.2f" % (-round(net, 2) + 0.0)


# ---------------------------------------------------------------- requests
def _static(company, extra=None):
	parts = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
	if company:
		parts.append("<SVCURRENTCOMPANY>" + x(company) + "</SVCURRENTCOMPANY>")
	for key, val in (extra or {}).items():
		parts.append("<" + key + ">" + x(val) + "</" + key + ">")
	return "<STATICVARIABLES>" + "".join(parts) + "</STATICVARIABLES>"


def export_report(company, report, extra=None):
	return (
		"<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA>"
		"<REQUESTDESC><REPORTNAME>" + x(report) + "</REPORTNAME>" + _static(company, extra) +
		"</REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"
	)


def export_collection(company, coll_id, coll_type, methods):
	natives = "".join("<NATIVEMETHOD>" + m + "</NATIVEMETHOD>" for m in methods)
	return (
		"<ENVELOPE><HEADER><VERSION>1</VERSION><TALLYREQUEST>Export</TALLYREQUEST>"
		"<TYPE>Collection</TYPE><ID>" + coll_id + "</ID></HEADER><BODY><DESC>" + _static(company) +
		"<TDL><TDLMESSAGE><COLLECTION NAME=\"" + coll_id + "\" ISMODIFY=\"No\"><TYPE>" + coll_type +
		"</TYPE>" + natives + "</COLLECTION></TDLMESSAGE></TDL></DESC></BODY></ENVELOPE>"
	)


def status_request():
	"""All companies loaded in Tally, with their last master / voucher alter IDs."""
	return export_collection(None, "ERPCompanies", "Company",
		["Name", "AltMstId", "AltVchId", "StartingFrom", "BooksFrom"])


def groups_request(company):
	return export_report(company, "List of Accounts", {"ACCOUNTTYPE": "Groups"})


def ledgers_request(company):
	return export_report(company, "List of Accounts", {"ACCOUNTTYPE": "Ledgers"})


def stock_items_request(company):
	return export_report(company, "List of Accounts", {"ACCOUNTTYPE": "Stock Items"})


def tally_date_text(value):
	"""date / 'YYYY-MM-DD' -> '1-Apr-2026' (the form Tally's report variables accept)."""
	d = value if isinstance(value, (date, datetime)) else datetime.strptime(str(value)[:10], "%Y-%m-%d")
	return str(d.day) + "-" + d.strftime("%b-%Y")


def daybook_request(company, from_date, to_date):
	"""Day Book for a period. SVFROMDATE / SVTODATE must carry TYPE="Date", otherwise Tally
	ignores them and returns only the current day."""
	return (
		"<ENVELOPE><HEADER><TALLYREQUEST>Export Data</TALLYREQUEST></HEADER><BODY><EXPORTDATA>"
		"<REQUESTDESC><REPORTNAME>Day Book</REPORTNAME><STATICVARIABLES>"
		"<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"
		"<SVCURRENTCOMPANY>" + x(company) + "</SVCURRENTCOMPANY>"
		"<SVFROMDATE TYPE=\"Date\">" + tally_date_text(from_date) + "</SVFROMDATE>"
		"<SVTODATE TYPE=\"Date\">" + tally_date_text(to_date) + "</SVTODATE>"
		"<EXPLODEFLAG>Yes</EXPLODEFLAG>"
		"</STATICVARIABLES></REQUESTDESC></EXPORTDATA></BODY></ENVELOPE>"
	)


def import_envelope(company, report, body):
	return (
		"<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA>"
		"<REQUESTDESC><REPORTNAME>" + report + "</REPORTNAME><STATICVARIABLES>"
		"<SVCURRENTCOMPANY>" + x(company) + "</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC>"
		"<REQUESTDATA><TALLYMESSAGE xmlns:UDF=\"TallyUDF\">" + body + "</TALLYMESSAGE>"
		"</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
	)


def ledger_xml(name, parent, billwise=False, gstin=None):
	body = (
		"<LEDGER NAME=\"" + x(name) + "\" ACTION=\"Create\"><NAME.LIST><NAME>" + x(name) +
		"</NAME></NAME.LIST><PARENT>" + x(parent) + "</PARENT>"
		"<ISBILLWISEON>" + ("Yes" if billwise else "No") + "</ISBILLWISEON>"
		"<AFFECTSSTOCK>No</AFFECTSSTOCK>"
	)
	if gstin:
		body += "<PARTYGSTIN>" + x(gstin) + "</PARTYGSTIN>"
	return body + "</LEDGER>"


def voucher_xml(vtype, number, posting_date, narration, reference, lines, remote_id):
	"""lines: [{ledger, net, is_party, bills: [(ref_name, bill_type, net)]}]"""
	party = next((l["ledger"] for l in lines if l.get("is_party")), "")
	parts = [
		"<VOUCHER REMOTEID=\"" + x(remote_id) + "\" VCHTYPE=\"" + x(vtype) +
		"\" ACTION=\"Create\" OBJVIEW=\"Accounting Voucher View\">",
		"<DATE>" + tally_date(posting_date) + "</DATE>",
		"<EFFECTIVEDATE>" + tally_date(posting_date) + "</EFFECTIVEDATE>",
		"<VOUCHERTYPENAME>" + x(vtype) + "</VOUCHERTYPENAME>",
		"<VOUCHERNUMBER>" + x(number) + "</VOUCHERNUMBER>",
		"<NARRATION>" + x(narration) + "</NARRATION>",
		"<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>",
		"<ISINVOICE>No</ISINVOICE>",
	]
	if party:
		parts.append("<PARTYLEDGERNAME>" + x(party) + "</PARTYLEDGERNAME>")
	if reference:
		parts.append("<REFERENCE>" + x(reference) + "</REFERENCE>")
	for line in sorted(lines, key=lambda l: 0 if l["net"] > 0 else 1):
		parts.append("<ALLLEDGERENTRIES.LIST><LEDGERNAME>" + x(line["ledger"]) + "</LEDGERNAME>")
		parts.append("<ISDEEMEDPOSITIVE>" + ("Yes" if line["net"] > 0 else "No") + "</ISDEEMEDPOSITIVE>")
		parts.append("<ISPARTYLEDGER>" + ("Yes" if line.get("is_party") else "No") + "</ISPARTYLEDGER>")
		parts.append("<AMOUNT>" + amount_text(line["net"]) + "</AMOUNT>")
		for ref, btype, amt in line.get("bills") or []:
			parts.append("<BILLALLOCATIONS.LIST><NAME>" + x(ref) + "</NAME><BILLTYPE>" + x(btype) +
				"</BILLTYPE><AMOUNT>" + amount_text(amt) + "</AMOUNT></BILLALLOCATIONS.LIST>")
		parts.append("</ALLLEDGERENTRIES.LIST>")
	parts.append("</VOUCHER>")
	return "".join(parts)


def delete_voucher_xml(vtype, number, posting_date):
	d = datetime.strptime(str(posting_date)[:10], "%Y-%m-%d").strftime("%d-%b-%Y")
	return ("<VOUCHER DATE=\"" + d + "\" TAGNAME=\"Voucher Number\" TAGVALUE=\"" + x(number) +
		"\" VCHTYPE=\"" + x(vtype) + "\" ACTION=\"Delete\"><VOUCHERTYPENAME>" + x(vtype) +
		"</VOUCHERTYPENAME></VOUCHER>")


# ---------------------------------------------------------------- responses
def parse_import_response(text):
	text = clean(decode(text))

	def num(tag):
		m = re.search(r"<" + tag + r">\s*(-?\d+)\s*</" + tag + r">", text)
		return int(m.group(1)) if m else 0

	from html import unescape
	errors = [unescape(e).strip() for e in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", text, re.S)]
	return {
		"created": num("CREATED"), "altered": num("ALTERED"), "deleted": num("DELETED"),
		"cancelled": num("CANCELLED"), "errors": num("ERRORS"), "exceptions": num("EXCEPTIONS"),
		"line_errors": errors, "raw": text[:1000],
	}


def import_ok(res):
	return (res["created"] + res["altered"]) >= 1 and not res["errors"] and not res["exceptions"]


def already_exists(res):
	return any("already exist" in e.lower() for e in res["line_errors"])


def describe_error(res):
	if res["line_errors"]:
		return "; ".join(res["line_errors"])[:900]
	return "Tally response: " + re.sub(r"\s+", " ", res["raw"])[:600]


def parse_xml(text):
	text = clean(decode(text))
	if "<LINEERROR>" in text and "<VOUCHER" not in text and "<LEDGER" not in text:
		from html import unescape
		msg = "; ".join(unescape(e) for e in re.findall(r"<LINEERROR>(.*?)</LINEERROR>", text, re.S))
		raise ValueError("Tally returned an error: " + msg)
	try:
		return ET.fromstring(text)
	except ET.ParseError as e:
		raise ValueError("Could not read Tally XML (" + str(e) + ")")


def _t(el, tag):
	val = el.findtext(tag)
	return (val or "").strip()


def _name(el):
	name = (el.get("NAME") or "").strip()
	if not name:
		name = _t(el, "NAME") or _t(el, "NAME.LIST/NAME")
	return name


def _int(value):
	try:
		return int(str(value).strip() or 0)
	except ValueError:
		return 0


def parse_companies(text):
	root = parse_xml(text)
	out = []
	for el in root.iter("COMPANY"):
		name = _name(el)
		if name:
			out.append({"name": name, "alt_mst_id": _int(_t(el, "ALTMSTID")),
				"alt_vch_id": _int(_t(el, "ALTVCHID")),
				"books_from": parse_tally_date(_t(el, "BOOKSFROM") or _t(el, "STARTINGFROM"))})
	return out


def _parent(el):
	p = _t(el, "PARENT")
	return "" if p.lower().endswith("primary") else p


def parse_groups(text):
	"""-> {group_name: parent_name ('' for primary groups)}"""
	return {_name(el): _parent(el) for el in parse_xml(text).iter("GROUP") if _name(el)}


def primary_group(groups, group):
	"""Walk a group up to its primary group (Sundry Debtors, Indirect Expenses ...)."""
	seen = set()
	while group and groups.get(group) and group not in seen:
		seen.add(group)
		group = groups[group]
	return group


def group_chain(groups, group):
	"""[group, parent, grand-parent, ..., primary]"""
	chain, seen = [], set()
	while group and group not in seen:
		seen.add(group)
		chain.append(group)
		group = groups.get(group, "")
	return chain


def _gstin(el):
	for tag in ("PARTYGSTIN", "GSTIN"):
		for sub in el.iter(tag):
			if (sub.text or "").strip():
				return sub.text.strip()
	return ""


def parse_ledgers(text):
	out = []
	for el in parse_xml(text).iter("LEDGER"):
		name = _name(el)
		if not name:
			continue
		out.append({
			"name": name, "parent": _parent(el), "guid": _t(el, "GUID"),
			"alter_id": _int(_t(el, "ALTERID")),
			"opening_net": -parse_amount(_t(el, "OPENINGBALANCE")),
			"gstin": _gstin(el), "billwise": yes(_t(el, "ISBILLWISEON")),
		})
	return out


def parse_stock_items(text):
	out = []
	for el in parse_xml(text).iter("STOCKITEM"):
		name = _name(el)
		if not name:
			continue
		hsn = ""
		for sub in el.iter("HSNCODE"):
			if (sub.text or "").strip():
				hsn = sub.text.strip()
		out.append({"name": name, "parent": _parent(el), "guid": _t(el, "GUID"),
			"alter_id": _int(_t(el, "ALTERID")), "uom": _t(el, "BASEUNITS"), "hsn": hsn})
	return out


def _entries(voucher, tags):
	for tag in tags:
		rows = [e for e in voucher.findall(tag) if _t(e, "LEDGERNAME")]
		if rows:
			return rows
	return []


def parse_vouchers(text):
	"""Day Book / voucher collection -> list of vouchers with lines netted per ledger."""
	out = []
	for v in parse_xml(text).iter("VOUCHER"):
		entries = _entries(v, ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"))
		inventory = v.findall("ALLINVENTORYENTRIES.LIST") or v.findall("INVENTORYENTRIES.LIST")
		for inv in inventory:
			entries += [a for a in inv.findall("ACCOUNTINGALLOCATIONS.LIST") if _t(a, "LEDGERNAME")]

		lines, order = {}, []
		for e in entries:
			ledger = _t(e, "LEDGERNAME")
			key = ledger.lower()
			if key not in lines:
				lines[key] = {"ledger": ledger, "net": 0.0, "bills": {}}
				order.append(key)
			lines[key]["net"] += -parse_amount(_t(e, "AMOUNT"))
			for b in e.findall("BILLALLOCATIONS.LIST"):
				bname = _t(b, "NAME")
				if not bname:
					continue
				bkey = (bname, _t(b, "BILLTYPE") or "Agst Ref")
				lines[key]["bills"][bkey] = lines[key]["bills"].get(bkey, 0.0) - parse_amount(_t(b, "AMOUNT"))

		clean_lines = []
		for k in order:
			ln = lines[k]
			ln["net"] = round(ln["net"], 2)
			ln["bills"] = [(r, t, round(a, 2)) for (r, t), a in ln["bills"].items() if round(a, 2)]
			if ln["net"]:
				clean_lines.append(ln)

		out.append({
			"guid": _t(v, "GUID"),
			"remote_id": (v.get("REMOTEID") or _t(v, "REMOTEID") or "").strip(),
			"alter_id": _int(_t(v, "ALTERID")),
			"vtype": _t(v, "VOUCHERTYPENAME") or (v.get("VCHTYPE") or "").strip(),
			"number": _t(v, "VOUCHERNUMBER"),
			"date": parse_tally_date(_t(v, "DATE")),
			"narration": _t(v, "NARRATION"),
			"reference": _t(v, "REFERENCE"),
			"party": _t(v, "PARTYLEDGERNAME"),
			"cancelled": yes(_t(v, "ISCANCELLED")),
			"optional": yes(_t(v, "ISOPTIONAL")),
			"deleted": yes(_t(v, "ISDELETED")),
			"lines": clean_lines,
			"imbalance": round(sum(l["net"] for l in clean_lines), 2),
		})
	return out
