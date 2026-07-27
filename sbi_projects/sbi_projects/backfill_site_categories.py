# Copyright (c) 2026, Velmaska and contributors
"""One-time backfill: bring OLD site cost centers up to the new structure.

Before this change every Project created a single leaf cost center directly
under "Sites - <abbr>".  New projects now create a GROUP with category leaves
(General, Material, Manpower, Equipment Cost, Equipment Rent, Subcontracting,
Overheads).  This script upgrades the old single leaves to match.

For every leaf directly under a "Sites - <abbr>" group:

  * If it has GL entries (real transactions) -> SKIP and report it. We never
    force-convert a cost center that already carries postings; that has to be
    reviewed by hand.
  * Otherwise -> convert the leaf to a group, create the seven category leaves
    under it, and repoint any Project.cost_center that used the old leaf to the
    new "General" leaf (you cannot post to a group).

Run it in DRY RUN first (dry_run=1, the default): nothing is written, it only
prints what WOULD change.  Review the output, then run again with dry_run=0.

How to run (Frappe Cloud bench console, or desk System Console):

    from sbi_projects.sbi_projects.backfill_site_categories import run
    run(dry_run=1)            # preview only
    run(dry_run=0)            # apply

Or via bench:

    bench --site erp.shiv-bharat.com execute \
        sbi_projects.sbi_projects.backfill_site_categories.run \
        --kwargs "{'dry_run': 1}"
"""

import frappe
from frappe.utils import cint

from sbi_projects.sbi_projects.project_hooks import (
    SITE_COST_CATEGORIES,
    _ensure_category_leaves,
)


def _leaf_name(label, category, abbr):
    """Mirror the naming used in project_hooks._ensure_category_leaves."""
    display = "{0} {1}".format(label, category)[:125]
    return "{0} - {1}".format(display, abbr)


def _has_transactions(cost_center):
    return bool(frappe.db.get_value("GL Entry", {"cost_center": cost_center}))


@frappe.whitelist()
def run(dry_run=1, company=None):
    """Upgrade old site leaf cost centers to group + category leaves.

    dry_run=1 (default) previews; dry_run=0 applies.
    company=<name> limits to one company; omitted = all.

    Whitelisted so it can be triggered from the browser console (F12):
        frappe.call({method: "sbi_projects.sbi_projects.backfill_site_categories.run",
                     args: {dry_run: 1}}).then(r => console.log(r.message));
    Restricted to System Manager because dry_run=0 rewrites the cost center tree.
    """
    frappe.only_for("System Manager")
    dry_run = cint(dry_run)

    report = {
        "dry_run": bool(dry_run),
        "converted": [],
        "skipped_with_transactions": [],
        "already_group": [],
        "errors": [],
    }
    lines = []

    def out(msg):
        lines.append(msg)

    mode = "DRY RUN — no changes will be written" if dry_run else "APPLYING CHANGES"
    out("=" * 60)
    out("Site Cost Center backfill  [{0}]".format(mode))
    out("=" * 60)

    sites_groups = frappe.get_all(
        "Cost Center",
        filters={"cost_center_name": "Sites", "is_group": 1},
        fields=["name", "company"],
    )
    if company:
        sites_groups = [g for g in sites_groups if g.company == company]

    if not sites_groups:
        out("No 'Sites - <abbr>' group cost centers found. Nothing to do.")
        print("\n".join(lines))
        return report

    for sg in sites_groups:
        abbr = frappe.get_cached_value("Company", sg.company, "abbr")
        out("")
        out("Company {0}  ->  group '{1}'".format(sg.company, sg.name))

        children = frappe.get_all(
            "Cost Center",
            filters={"parent_cost_center": sg.name},
            fields=["name", "cost_center_name", "is_group"],
            order_by="name asc",
        )

        for ch in children:
            if ch.is_group:
                report["already_group"].append(ch.name)
                out("  - already a group, skip: {0}".format(ch.name))
                continue

            if _has_transactions(ch.name):
                report["skipped_with_transactions"].append(ch.name)
                out("  ! HAS TRANSACTIONS, skip (manual review): {0}".format(ch.name))
                continue

            label = ch.cost_center_name
            general_leaf = _leaf_name(label, "General", abbr)
            new_leaves = [_leaf_name(label, c, abbr) for c, _ in SITE_COST_CATEGORIES]
            projects = frappe.get_all("Project", filters={"cost_center": ch.name}, pluck="name")

            out("  + CONVERT: {0}".format(ch.name))
            out("      -> becomes GROUP with {0} leaves".format(len(new_leaves)))
            for lf in new_leaves:
                out("         · {0}".format(lf))
            if projects:
                out("      -> repoint Project.cost_center to General: {0}".format(
                    ", ".join(projects)))

            entry = {
                "site": ch.name,
                "general_leaf": general_leaf,
                "new_leaves": new_leaves,
                "projects_repointed": projects,
            }

            if not dry_run:
                try:
                    cc = frappe.get_doc("Cost Center", ch.name)
                    if hasattr(cc, "convert_ledger_to_group"):
                        cc.convert_ledger_to_group()
                    else:
                        cc.is_group = 1
                        cc.save(ignore_permissions=True)

                    _ensure_category_leaves(sg.company, abbr, label, ch.name)

                    for p in projects:
                        frappe.db.set_value("Project", p, "cost_center",
                                            general_leaf, update_modified=False)
                    frappe.db.commit()
                    out("      done.")
                except Exception:
                    frappe.db.rollback()
                    report["errors"].append(ch.name)
                    out("      ERROR converting {0}:".format(ch.name))
                    out(frappe.get_traceback())
                    frappe.log_error(
                        title="backfill_site_categories: {0}".format(ch.name),
                        message=frappe.get_traceback(),
                    )
                    continue

            report["converted"].append(entry)

    out("")
    out("=" * 60)
    out("Summary: {0} to convert, {1} skipped(transactions), "
        "{2} already group, {3} errors".format(
            len(report["converted"]),
            len(report["skipped_with_transactions"]),
            len(report["already_group"]),
            len(report["errors"]),
        ))
    if dry_run:
        out("This was a DRY RUN. Re-run with dry_run=0 to apply.")
    out("=" * 60)

    print("\n".join(lines))
    return report
