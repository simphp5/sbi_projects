# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
Work Group master.

The tag that joins a measurement to the BOQ line it feeds. It was a dropdown
built from whatever the lines happened to carry, which meant it was empty on a
fresh sheet and there was no way to add to it. A master fixes both: it always
has values, and a new one can be created without leaving the BOQ.

Seeded from the twenty-three numbered items on the September estimate, with
the number kept in the description so the quotation still reads the way SBI
writes it.
"""

import frappe

# (tag, how it reads on the quotation, trade, order)
WORK_GROUPS = [
	("EW",       "1  E/W",                    "Civil",   10),
	("PCC",      "2  PCC",                    "Civil",   20),
	("QDUST",    "3  Quarry Dust",            "Filling", 30),
	("RCC",      "3  RCC",                    "Civil",   40),
	("REINF",    "4  Reinf",                  "Civil",   50),
	("CANT",     "5  Cantering",              "Civil",   60),
	("BW",       "6  B/W",                    "Civil",   70),
	("SUPER",    "7  Superstructure",         "Civil",   80),
	("PLAST",    "8  Plastering",             "Civil",   90),
	("FILL",     "9  Filling",                "Filling", 100),
	("RS",       "10  R/S",                   "Civil",   110),
	("WIN",      "11  Windows",               "Civil",   120),
	("PEB",      "12  PEB",                   "PEB",     130),
	("SHEET",    "13  Sheeting",              "PEB",     140),
	("DECK",     "14  Decking Sheeting",      "PEB",     150),
	("SCAF",     "15  Scaffolding",           "Civil",   160),
	("PWRTRVL",  "16  Power travel finishing","Civil",   170),
	("SURV",     "17  Surveyor",              "Civil",   180),
	("FDNBOLT",  "18  Fdn Bolt Fixing",       "PEB",     190),
	("GROUT",    "19  Grouting",              "Civil",   200),
]


def setup_work_groups():
	if not frappe.db.exists("DocType", "Work Group"):
		return 0

	created = 0
	for tag, full, trade, order in WORK_GROUPS:
		if frappe.db.exists("Work Group", tag):
			continue
		frappe.get_doc({
			"doctype": "Work Group",
			"work_group_name": tag,
			"full_name": full,
			# a trade that has not been seeded yet simply leaves the field blank
			"default_trade": trade if frappe.db.exists("BOQ Trade", trade) else None,
			"display_order": order,
			"is_active": 1,
		}).insert(ignore_permissions=True)
		created += 1

	frappe.db.commit()
	return created
