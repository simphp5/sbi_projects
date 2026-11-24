# =====================================================================
#  LITE ERP  -  one-page app for the Shiv Bharat owner
#
#  Top menu (fixed):  Projects | Sales | Purchase | Cash Flow | Bank |
#                     Site Summary | HR | GST
#  Sales     : sales order (Sl, description, area, unit, cost, MS yes/no)
#              -> bill a milestone (MS lines) / non-MS bill / direct invoice
#  Purchase  : purchase order (same lines) -> milestone bill / non-MS bill,
#              or project -> stage -> BOQ items not yet bought -> bill
#  Cash Flow       : give cash / site expense / import from Tally
#  Site Summary    : billed, received, spent, cash with each site
#  Bank            : upload statement daily, match each entry to a GST invoice or remark it
#  GST             : output, input credit, paid, balance to pay
#
#  Paste ALL of this into System Console -> Execute.  Safe to run again.
#  Then reload the browser and open the "Lite ERP" icon  (/app/lite-erp)
# =====================================================================

LABEL = "Lite ERP"
ROUTE = "/desk/lite-erp"
API_METHOD = "sbi_lite_erp"
ROLES_WANTED = ["System Manager", "Accounts Manager", "Accounts User", "Business Owner", "HR Manager", "HR User"]

# The earlier "Accounts Desk" page is replaced by Lite ERP. Set to False to keep it.
REMOVE_OLD_ACCOUNTS_DESK = True

SERVER_SCRIPT = r'''# SBI Lite ERP - API server script (api_method: sbi_lite_erp)
# Restricted Python: no imports, no .format(), no augmented subscript assignment.

fd = frappe.form_dict
user = frappe.session.user
act = fd.get("action") or "init"
sql = frappe.db.sql

allowed = ("System Manager", "Accounts Manager", "Accounts User", "Business Owner")
hr_roles = ("HR Manager", "HR User")
ROLE_AREAS = {"HR Manager": ["hr", "requests"], "HR User": ["hr", "requests"], "Sales User": ["sales"], "Sales Manager": ["sales"],
    "Purchase User": ["purchase"], "Purchase Manager": ["purchase"], "Projects User": ["projects", "site"], "Projects Manager": ["projects", "site"]}
ok = user == "Administrator"
hr_ok = False
MY_ROLES = []
AREAS = []
for r in sql("select role from `tabHas Role` where parenttype='User' and parent=%s", user):
    MY_ROLES.append(r[0])
    if r[0] in allowed:
        ok = True
    if r[0] in hr_roles:
        hr_ok = True
    for ar in ROLE_AREAS.get(r[0], []):
        if ar not in AREAS:
            AREAS.append(ar)
if ok:
    AREAS = ["projects", "sales", "purchase", "cash", "bank", "site", "hr", "gst", "requests"]
ME = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"},
    ["name", "employee_name", "company", "image", "designation", "department"], as_dict=1) if user != "Guest" else None
if ME or "SBI Staff" in MY_ROLES or "Employee" in MY_ROLES:
    AREAS.append("me")
if not AREAS:
    frappe.throw("You do not have access to Lite ERP.")
AREA_ACTS = {
    "me": ["me_home", "me_att_req", "me_leave_req", "me_profile", "me_profile_save", "me_cancel_req", "set_password"],
    "hr": ["hr", "hr_office", "hr_site", "hr_settings_save", "hr_mark_att", "emp_list", "emp_get", "emp_save", "emp_month", "req_list", "req_action"],
    "requests": ["req_list", "req_action"],
    "sales": ["orders", "order_setup", "order_create", "ms_bill", "nonms_bill", "project_sales"],
    "purchase": ["orders", "order_setup", "order_create", "ms_bill", "nonms_bill", "purchase_stages", "boq_pending"],
    "projects": ["projects_summary", "boq_stages", "boq_add_stage", "boq_get", "boq_save", "project_cash", "project_sales"],
    "site": ["cash_position", "project_cash", "hr_site"],
}
# HR staff and other limited logins only reach their own parts of Lite ERP
HR_ONLY = not ok
if not ok and act != "init":
    can = False
    for ar in AREAS:
        if act in AREA_ACTS.get(ar, []):
            can = True
    if not can:
        frappe.throw("Your login cannot use this part of Lite ERP.")
    if act in ("orders", "order_setup", "order_create", "ms_bill", "nonms_bill"):
        need = "purchase" if fd.get("kind") == "purchase" else "sales"
        if need not in AREAS:
            frappe.throw("Your login cannot use " + need + " orders.")

company = fd.get("company") or ""
project = fd.get("project") or ""
stage = fd.get("stage") or ""
f_date = fd.get("from_date") or frappe.utils.nowdate()
t_date = fd.get("to_date") or frappe.utils.nowdate()
pf = {"c": company, "p": project, "s": stage, "f": f_date, "t": t_date}
out = {}
done = False

PI_STAGE = "ifnull(pi.sbi_stage, '')"
if frappe.get_meta("Purchase Invoice").has_field("sbi_project_stage"):
    PI_STAGE = "coalesce(nullif(pi.sbi_stage, ''), pi.sbi_project_stage, '')"

JE_INFO = """select je.name, je.posting_date, je.tally_voucher, ifnull(je.user_remark, '') remark,
    sum(case when acc.account_type in %(types)s then jea.credit else 0 end) amount,
    group_concat(distinct case when jea.debit > 0 then ifnull(nullif(jea.party, ''), jea.account) end separator ', ') paid_to
    from `tabJournal Entry` je
    join `tabJournal Entry Account` jea on jea.parent = je.name
    join `tabAccount` acc on acc.name = jea.account
    where """

# ================================================================== start-up
if act == "init":
    out["companies"] = frappe.get_all("Company", pluck="name", order_by="name asc")
    out["default_company"] = frappe.db.get_default("company") or ""
    out["logo"] = frappe.db.get_single_value("Navbar Settings", "app_logo") or ""
    out["scope"] = "all" if ok else ("hr" if AREAS == ["hr", "requests"] or AREAS == ["hr", "requests", "me"] else "limited")
    out["areas"] = AREAS
    out["me"] = ME
    out["must_change"] = 1 if (frappe.get_meta("User").has_field("sbi_must_change_password") and frappe.db.get_value("User", user, "sbi_must_change_password")) else 0
    # open the punch page by itself around office start / end time (30 minutes before or after)
    out["punch_window"] = ""
    hsm = frappe.get_meta("HR Settings")
    if ME and hsm.has_field("sbi_office_in_time"):
        nowdt = frappe.utils.now_datetime()
        today = frappe.utils.nowdate()
        lastp = sql("select log_type from `tabEmployee Checkin` where employee=%s and date(time)=%s order by time desc limit 1", (ME.name, today))
        last_type = lastp[0][0] if lastp else ""
        for pair in [["IN", "sbi_office_in_time"], ["OUT", "sbi_office_out_time"]]:
            tv = str(frappe.db.get_single_value("HR Settings", pair[1]) or "")
            tp = tv.split(":")
            if not tp[0]:
                continue
            at = frappe.utils.get_datetime(today + " " + ("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2] + ":00")
            gap = abs(frappe.utils.time_diff_in_seconds(nowdt, at))
            if gap <= 1800 and ((pair[0] == "IN" and not last_type) or (pair[0] == "OUT" and last_type == "IN")):
                out["punch_window"] = pair[0]
    out["projects"] = sql("""select name, project_name, company, status, customer from `tabProject`
        where status != 'Cancelled' order by modified desc limit 2000""", as_dict=1) if (ok or "projects" in AREAS or "sales" in AREAS or "purchase" in AREAS or "site" in AREAS or "hr" in AREAS) else []
    done = True

# ================================================================== all projects with money
if act == "projects_summary":
    cc = " and company=%(c)s" if company else ""
    rows = sql("""select name, project_name, customer, status, company, ifnull(sbi_contract_value, 0) contract,
        sbi_current_stage current_stage from `tabProject` where status != 'Cancelled'""" + cc +
        " order by modified desc limit 1000", pf, as_dict=1)
    by = {}
    for r in rows:
        r["billed"] = 0.0
        r["outstanding"] = 0.0
        r["purchased"] = 0.0
        r["given"] = 0.0
        r["site_spent"] = 0.0
        r["office_spent"] = 0.0
        r["order_value"] = 0.0
        by[r.name] = r
    for x in sql("""select project, sum(base_grand_total), sum(outstanding_amount) from `tabSales Invoice`
            where docstatus=1 and ifnull(project, '') != '' group by project"""):
        if x[0] in by:
            by[x[0]]["billed"] = float(x[1] or 0)
            by[x[0]]["outstanding"] = float(x[2] or 0)
    for x in sql("""select project, sum(base_grand_total) from `tabSales Order`
            where docstatus=1 and ifnull(project, '') != '' group by project"""):
        if x[0] in by:
            by[x[0]]["order_value"] = float(x[1] or 0)
    for x in sql("""select project, sum(base_grand_total) from `tabPurchase Invoice`
            where docstatus=1 and ifnull(project, '') != '' group by project"""):
        if x[0] in by:
            by[x[0]]["purchased"] = float(x[1] or 0)
    for x in sql("select project, sum(amount) from `tabSite Cash Issue` group by project"):
        if x[0] in by:
            by[x[0]]["given"] = float(x[1] or 0)
    for x in sql("""select project, sum(case when payment_source='Site Cash' then amount else 0 end),
            sum(case when payment_source='Site Cash' then 0 else amount end) from `tabSite Expense Entry` group by project"""):
        if x[0] in by:
            by[x[0]]["site_spent"] = float(x[1] or 0)
            by[x[0]]["office_spent"] = float(x[2] or 0)
    lst = []
    for r in rows:
        r["received"] = r["billed"] - r["outstanding"]
        r["cash_balance"] = r["given"] - r["site_spent"]
        r["spent"] = r["purchased"] + r["site_spent"] + r["office_spent"]
        r["value"] = float(r.contract or 0) or r["order_value"]
        lst.append(r)
    out["projects"] = lst
    done = True

# ================================================================== sales milestones of a project
if act == "project_sales":
    if not project:
        frappe.throw("Pick a project.")
    sos = sql("""select name, customer, transaction_date, base_grand_total grand_total, per_billed, status, company
        from `tabSales Order` where docstatus=1
        and (project=%(p)s or name in (select sales_order from `tabProject` where name=%(p)s))
        order by transaction_date""", pf, as_dict=1)
    for so in sos:
        so["terms"] = sql("""select name row_name, idx, payment_term, sbi_stage stage, due_date,
            invoice_portion, payment_amount, sbi_billed billed, sbi_status bill_status,
            sbi_sales_invoice sales_invoice, sbi_received_amount received
            from `tabPayment Schedule` where parenttype='Sales Order' and parent=%s order by idx""", so.name, as_dict=1)
        # a draft invoice already made for a milestone: open it instead of making another
        drafts = sql("""select name, ifnull(sbi_source_payment_terms, '') terms from `tabSales Invoice`
            where docstatus=0 and sbi_source_sales_order=%s""", so.name, as_dict=1)
        for t in so["terms"]:
            t["draft_invoice"] = ""
            for dr in drafts:
                if t.row_name and t.row_name in dr.terms:
                    t["draft_invoice"] = dr.name
    out["orders"] = sos
    out["draft_orders"] = sql("""select name, customer, base_grand_total grand_total, transaction_date,
        (select count(*) from `tabPayment Schedule` ps where ps.parenttype='Sales Order' and ps.parent=so.name) n_terms
        from `tabSales Order` so where docstatus=0
        and (project=%(p)s or name in (select sales_order from `tabProject` where name=%(p)s))
        order by creation desc""", pf, as_dict=1)
    out["invoices"] = sql("""select name, posting_date, customer, sbi_stage stage, base_grand_total grand_total,
        outstanding_amount, status, docstatus from `tabSales Invoice`
        where project=%(p)s and docstatus < 2 order by posting_date desc, creation desc limit 20""", pf, as_dict=1)
    done = True

# ================================================================== purchase: stages of a project
if act == "purchase_stages":
    if not project:
        frappe.throw("Pick a project.")
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    out["boq"] = boq or ""
    seen = {}
    lst = []
    if boq:
        for r in sql("""select stage, count(*) n_lines, sum(amount) amount, sum(material_amount) material
                from `tabProject BOQ Item` where parent=%s group by stage order by min(idx)""", boq, as_dict=1):
            if not r.stage:
                continue
            seen[r.stage] = {"stage": r.stage, "lines": int(r.n_lines or 0), "amount": float(r.amount or 0),
                "material": float(r.material or 0), "bills": 0, "purchased": 0.0, "from_boq": 1}
            lst.append(seen[r.stage])
    for r in sql("""select t.sbi_stage from `tabTask` t left join `tabProject Stage` ps on ps.name = t.sbi_stage
            where t.project=%(p)s and ifnull(t.sbi_stage, '') != ''
            group by t.sbi_stage order by min(ifnull(ps.sequence, 999))""", pf):
        if r[0] not in seen:
            seen[r[0]] = {"stage": r[0], "lines": 0, "amount": 0.0, "material": 0.0, "bills": 0, "purchased": 0.0, "from_boq": 0}
            lst.append(seen[r[0]])
    no_stage = {"bills": 0, "purchased": 0.0}
    for r in sql("select " + PI_STAGE + """ st, count(*) n, sum(pi.base_grand_total) amt from `tabPurchase Invoice` pi
            where pi.project=%(p)s and pi.docstatus < 2 group by st""", pf, as_dict=1):
        if not r.st:
            no_stage = {"bills": int(r.n or 0), "purchased": float(r.amt or 0)}
            continue
        if r.st not in seen:
            seen[r.st] = {"stage": r.st, "lines": 0, "amount": 0.0, "material": 0.0, "bills": 0, "purchased": 0.0, "from_boq": 0}
            lst.append(seen[r.st])
        seen[r.st]["bills"] = int(r.n or 0)
        seen[r.st]["purchased"] = float(r.amt or 0)
    out["stages"] = lst
    out["no_stage"] = no_stage
    done = True

# ================================================================== purchase: BOQ items still to buy
if act == "boq_pending":
    if not project:
        frappe.throw("Pick a project.")
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    pf["boq"] = boq or ""
    sc = " and pbi.stage=%(s)s" if stage else ""
    req = {}
    order = []
    if boq:
        for r in sql("""select sr.item, max(sr.unit) unit, sum(pbi.qty * sar.coefficient) required, max(sr.rate) rate,
                group_concat(distinct pbi.activity separator ', ') activities
                from `tabProject BOQ Item` pbi
                join `tabSite Activity Resource` sar on sar.parent = pbi.activity and sar.parenttype = 'Site Activity'
                join `tabSite Resource` sr on sr.name = sar.resource
                where pbi.parent=%(boq)s and sr.category='Material' and ifnull(sr.item, '') != ''""" + sc +
                " group by sr.item order by min(pbi.idx)", pf, as_dict=1):
            req[r.item] = {"item_code": r.item, "uom": r.unit, "required": float(r.required or 0),
                "rate": float(r.rate or 0), "source": "Project BOQ", "activities": r.activities or ""}
            order.append(r.item)
    sc2 = " and bi.stage=%(s)s" if stage else ""
    for r in sql("""select bi.item_code, max(bi.uom) uom, sum(bi.qty) qty, max(bi.rate) rate
            from `tabBOQ Item` bi join `tabBOQ` b on b.name = bi.parent
            where b.project=%(p)s and b.docstatus=1 and ifnull(bi.item_code, '') != ''""" + sc2 +
            " group by bi.item_code", pf, as_dict=1):
        if r.item_code in req:
            e = req[r.item_code]
            e["required"] = max(e["required"], float(r.qty or 0))
            if not e["rate"]:
                e["rate"] = float(r.rate or 0)
        else:
            req[r.item_code] = {"item_code": r.item_code, "uom": r.uom, "required": float(r.qty or 0),
                "rate": float(r.rate or 0), "source": "BOQ", "activities": ""}
            order.append(r.item_code)
    bought = {}
    stc = (" and " + PI_STAGE + "=%(s)s") if stage else ""
    for r in sql("""select pii.item_code, sum(case when pi.docstatus=1 then pii.stock_qty else 0 end) done_qty,
            sum(case when pi.docstatus=0 then pii.stock_qty else 0 end) draft_qty
            from `tabPurchase Invoice Item` pii join `tabPurchase Invoice` pi on pi.name = pii.parent
            where pi.project=%(p)s and pi.docstatus < 2""" + stc + " group by pii.item_code", pf, as_dict=1):
        bought[r.item_code] = [float(r.done_qty or 0), float(r.draft_qty or 0)]
    items = {}
    if order:
        for r in sql("select name, item_name, stock_uom, last_purchase_rate from `tabItem` where name in %(i)s",
                {"i": tuple(order)}, as_dict=1):
            items[r.name] = r
    rows = []
    for code in order:
        e = req[code]
        it = items.get(code) or {}
        b = bought.get(code) or [0.0, 0.0]
        e["item_name"] = it.get("item_name") or code
        e["uom"] = it.get("stock_uom") or e["uom"] or ""
        if not e["rate"]:
            e["rate"] = float(it.get("last_purchase_rate") or 0)
        e["purchased"] = b[0]
        e["in_draft"] = b[1]
        e["pending"] = max(0.0, e["required"] - b[0] - b[1])
        rows.append(e)
    out["rows"] = rows
    out["boq"] = boq or ""
    # BOQ lines with no material item (subcontract / labour work) - for reference
    other = []
    if boq:
        other = sql("""select pbi.activity, pbi.sbi_description description, pbi.sbi_type type, pbi.unit, pbi.qty, pbi.amount,
                pbi.subcontract_amount, pbi.labour_amount, pbi.equipment_amount from `tabProject BOQ Item` pbi where pbi.parent=%(boq)s""" + sc + """
                and not exists (select 1 from `tabSite Activity Resource` sar join `tabSite Resource` sr on sr.name = sar.resource
                    where sar.parent = pbi.activity and sr.category='Material' and ifnull(sr.item, '') != '')
                order by pbi.idx limit 200""", pf, as_dict=1)
    out["other"] = other
    # the project's Material cost centre, so the bill lands on the right site head
    cc = frappe.db.get_value("Project", project, "cost_center") or ""
    mat_cc = ""
    if cc:
        grp = cc if frappe.db.get_value("Cost Center", cc, "is_group") else frappe.db.get_value("Cost Center", cc, "parent_cost_center")
        if grp:
            hit = sql("""select name from `tabCost Center` where parent_cost_center=%s and is_group=0
                and cost_center_name like 'Material%%' limit 1""", grp)
            if hit:
                mat_cc = hit[0][0]
    out["cost_center"] = mat_cc
    out["company"] = frappe.db.get_value("Project", project, "company") or ""
    done = True

# ================================================================== one project: site cash
if act == "project_cash":
    if not project:
        frappe.throw("Pick a project.")
    given = float(sql("select ifnull(sum(amount), 0) from `tabSite Cash Issue` where project=%(p)s", pf)[0][0] or 0)
    spent = float(sql("select ifnull(sum(amount), 0) from `tabSite Expense Entry` where project=%(p)s and payment_source='Site Cash'", pf)[0][0] or 0)
    office = float(sql("select ifnull(sum(amount), 0) from `tabSite Expense Entry` where project=%(p)s and ifnull(payment_source, '') != 'Site Cash'", pf)[0][0] or 0)
    petty = 0.0
    if frappe.db.exists("DocType", "Site Petty Cash Voucher"):
        petty = float(sql("select ifnull(sum(amount), 0) from `tabSite Petty Cash Voucher` where project=%(p)s and docstatus=1", pf)[0][0] or 0)
    rows = []
    for r in sql("""select 'Site Cash Issue' dt, name, issue_date d, amount, received_by who, remarks note, sbi_tally_je je
            from `tabSite Cash Issue` where project=%(p)s order by issue_date desc, creation desc limit 30""", pf, as_dict=1):
        r["kind"] = "Cash given"
        rows.append(r)
    for r in sql("""select 'Site Expense Entry' dt, name, entry_date d, amount, party who, description note,
            category, payment_source, sbi_tally_je je
            from `tabSite Expense Entry` where project=%(p)s order by entry_date desc, creation desc limit 30""", pf, as_dict=1):
        r["kind"] = "Expense - " + (r.category or "") + " (" + (r.payment_source or "") + ")"
        rows.append(r)
    out = {"given": given, "spent": spent, "balance": given - spent, "office": office, "petty": petty,
        "recent": sorted(rows, key=lambda x: str(x.d), reverse=True)[:30]}
    done = True

# ================================================================== every site: cash position
if act == "cash_position":
    pc = " where project in (select name from `tabProject` where company=%(c)s)" if company else ""
    bal = {}
    for r in sql("select project, sum(amount) from `tabSite Cash Issue`" + pc + " group by project", pf):
        bal[r[0]] = {"project": r[0], "given": float(r[1] or 0), "spent": 0.0, "office": 0.0}
    for r in sql("""select project, sum(case when payment_source='Site Cash' then amount else 0 end),
            sum(case when payment_source='Site Cash' then 0 else amount end) from `tabSite Expense Entry`""" + pc + " group by project", pf):
        if r[0] not in bal:
            bal[r[0]] = {"project": r[0], "given": 0.0, "spent": 0.0, "office": 0.0}
        bal[r[0]]["spent"] = float(r[1] or 0)
        bal[r[0]]["office"] = float(r[2] or 0)
    lst = []
    for key in bal:
        row = bal[key]
        row["balance"] = row["given"] - row["spent"]
        lst.append(row)
    out["projects"] = sorted(lst, key=lambda x: -x["balance"])
    done = True

# ================================================================== give cash / site expense
if act == "add_cash":
    if not project:
        frappe.throw("Pick a project first.")
    amt = frappe.utils.flt(fd.get("amount"))
    if amt <= 0:
        frappe.throw("Enter the amount.")
    d = frappe.get_doc({"doctype": "Site Cash Issue", "naming_series": "SCSH-.####", "project": project,
        "issue_date": fd.get("date") or frappe.utils.nowdate(), "amount": amt,
        "received_by": (fd.get("received_by") or "").strip() or "Site",
        "remarks": fd.get("remarks") or "", "issued_by": user})
    d.insert(ignore_permissions=True)
    out["name"] = d.name
    done = True

if act == "add_expense":
    if not project:
        frappe.throw("Pick a project first.")
    amt = frappe.utils.flt(fd.get("amount"))
    if amt <= 0:
        frappe.throw("Enter the amount.")
    cat = fd.get("category") or "Other"
    if cat not in ("Equipment", "Subcontract", "Transport", "Other"):
        cat = "Other"
    src = "Office" if fd.get("payment_source") == "Office" else "Site Cash"
    d = frappe.get_doc({"doctype": "Site Expense Entry", "naming_series": "SEXP-.#####", "project": project,
        "entry_date": fd.get("date") or frappe.utils.nowdate(), "category": cat, "payment_source": src,
        "stage": stage or None, "party": (fd.get("party") or "")[:140],
        "description": (fd.get("description") or "").strip() or cat, "amount": amt, "entered_by": user})
    d.insert(ignore_permissions=True)
    out["name"] = d.name
    done = True

# ================================================================== Tally cash payments
if act == "tally_cash":
    if not company:
        frappe.throw("Pick a company.")
    pf["types"] = ("Cash", "Bank") if fd.get("include_bank") in ("1", 1, "true", True) else ("Cash",)
    out["rows"] = sql(JE_INFO + """je.company=%(c)s and je.docstatus < 2 and ifnull(je.tally_voucher, '') != ''
        and je.posting_date between %(f)s and %(t)s
        and not exists (select 1 from `tabSite Cash Issue` s where s.sbi_tally_je = je.name)
        and not exists (select 1 from `tabSite Expense Entry` e where e.sbi_tally_je = je.name)
        group by je.name, je.posting_date, je.tally_voucher, je.user_remark
        having amount > 0 order by je.posting_date desc limit 300""", pf, as_dict=1)
    done = True

if act == "import_tally":
    jes = (fd.get("jes") or "").split(",")
    kinds = (fd.get("kinds") or "").split(",")
    projs = (fd.get("projects") or "").split(",")
    made = []
    skipped = 0
    i = 0
    for je in jes:
        kind = kinds[i].strip() if i < len(kinds) else "Cash"
        prj = projs[i].strip() if i < len(projs) else ""
        i += 1
        je = je.strip()
        if not je or not prj:
            skipped += 1
            continue
        if frappe.db.exists("Site Cash Issue", {"sbi_tally_je": je}) or frappe.db.exists("Site Expense Entry", {"sbi_tally_je": je}):
            skipped += 1
            continue
        info = sql(JE_INFO + "je.name=%(je)s and je.docstatus < 2 group by je.name", {"je": je, "types": ("Cash", "Bank")}, as_dict=1)
        if not info or frappe.utils.flt(info[0].amount) <= 0:
            skipped += 1
            continue
        v = info[0]
        who = (v.paid_to or "Tally")[:140]
        note = "Tally " + (v.tally_voucher or "") + " / " + v.name
        if v.remark:
            note = note + "\n" + v.remark
        if kind in ("Equipment", "Subcontract", "Transport", "Other"):
            d = frappe.get_doc({"doctype": "Site Expense Entry", "naming_series": "SEXP-.#####", "project": prj,
                "entry_date": v.posting_date, "category": kind, "payment_source": "Office", "party": who,
                "description": note, "amount": frappe.utils.flt(v.amount), "entered_by": user, "sbi_tally_je": v.name})
        else:
            d = frappe.get_doc({"doctype": "Site Cash Issue", "naming_series": "SCSH-.####", "project": prj,
                "issue_date": v.posting_date, "amount": frappe.utils.flt(v.amount), "received_by": who,
                "remarks": note, "issued_by": user, "sbi_tally_je": v.name})
        d.insert(ignore_permissions=True)
        made.append(d.name)
    out["made"] = made
    out["skipped"] = skipped
    done = True

# ================================================================== GST
if act == "gst":
    if not company:
        frappe.throw("Pick a company.")
    amap = {}
    rows = []
    if frappe.db.exists("DocType", "GST Account"):
        rows = sql("select * from `tabGST Account` where parenttype='GST Settings' and company=%s", company, as_dict=1)
    heads_f = [["CGST", "cgst_account"], ["SGST", "sgst_account"], ["IGST", "igst_account"],
        ["Cess", "cess_account"], ["Cess", "cess_non_advol_account"]]
    for g in rows:
        side = "in" if (g.get("account_type") or "").strip() == "Input" else "out"
        for hf in heads_f:
            a = g.get(hf[1])
            if a:
                amap[a] = [side, hf[0]]
    if not amap:
        for a in frappe.get_all("Account", filters={"company": company, "account_type": "Tax", "is_group": 0}, pluck="name"):
            low = a.lower()
            side = ""
            if "output" in low:
                side = "out"
            elif "input" in low:
                side = "in"
            if not side:
                continue
            head = "SGST"
            if "cess" in low:
                head = "Cess"
            elif "igst" in low:
                head = "IGST"
            elif "cgst" in low:
                head = "CGST"
            amap[a] = [side, head]
    accts = list(amap.keys())
    gst = {"accounts": len(accts)}
    gst["draft_si"] = int(sql("select count(*) from `tabSales Invoice` where docstatus=0 and company=%(c)s and posting_date between %(f)s and %(t)s", pf)[0][0] or 0)
    gst["draft_pi"] = int(sql("select count(*) from `tabPurchase Invoice` where docstatus=0 and company=%(c)s and posting_date between %(f)s and %(t)s", pf)[0][0] or 0)
    if accts:
        pf["a"] = tuple(accts)
        paytypes = ("Journal Entry", "Payment Entry")
        months = {}
        heads = {}
        for r in sql("""select date_format(posting_date, '%%Y-%%m') mon, account, voucher_type vt,
                sum(debit) dr, sum(credit) cr from `tabGL Entry`
                where is_cancelled=0 and company=%(c)s and account in %(a)s
                and posting_date between %(f)s and %(t)s and ifnull(is_opening, 'No') != 'Yes'
                group by date_format(posting_date, '%%Y-%%m'), account, voucher_type""", pf, as_dict=1):
            sh = amap.get(r.account)
            dr = float(r.dr or 0)
            cr = float(r.cr or 0)
            if r.mon not in months:
                months[r.mon] = {"month": r.mon, "output": 0.0, "itc": 0.0, "paid": 0.0, "setoff": 0.0}
            if sh[1] not in heads:
                heads[sh[1]] = {"head": sh[1], "output": 0.0, "itc": 0.0}
            m = months[r.mon]
            h = heads[sh[1]]
            ispay = r.vt in paytypes
            if sh[0] == "out":
                v = cr if ispay else cr - dr
                m["output"] = m["output"] + v
                h["output"] = h["output"] + v
                if ispay:
                    m["paid"] = m["paid"] + dr
            else:
                v = dr if ispay else dr - cr
                m["itc"] = m["itc"] + v
                h["itc"] = h["itc"] + v
                if ispay:
                    m["setoff"] = m["setoff"] + cr
        mlist = []
        tot = {"output": 0.0, "itc": 0.0, "paid": 0.0, "setoff": 0.0}
        for key in sorted(months.keys()):
            m = months[key]
            m["net"] = m["output"] - m["itc"]
            m["cash"] = max(0.0, m["paid"] - m["setoff"])
            for k in ("output", "itc", "paid", "setoff"):
                tot[k] = tot[k] + m[k]
            mlist.append(m)
        tot["net"] = tot["output"] - tot["itc"]
        tot["cash"] = max(0.0, tot["paid"] - tot["setoff"])
        hlist = []
        for key in ("CGST", "SGST", "IGST", "Cess"):
            if key in heads:
                h = heads[key]
                h["net"] = h["output"] - h["itc"]
                hlist.append(h)
        ob = 0.0
        ib = 0.0
        for r in sql("""select account, sum(debit) dr, sum(credit) cr from `tabGL Entry`
                where is_cancelled=0 and company=%(c)s and account in %(a)s and posting_date <= %(t)s
                group by account""", pf, as_dict=1):
            if amap[r.account][0] == "out":
                ob = ob + float(r.cr or 0) - float(r.dr or 0)
            else:
                ib = ib + float(r.dr or 0) - float(r.cr or 0)
        gst.update({"months": mlist, "heads": hlist, "total": tot,
            "output_balance": ob, "itc_balance": ib, "to_pay": ob - ib})
    out = gst
    done = True

# ================================================================== HOME: today's picture
if act == "home":
    if not company:
        frappe.throw("Pick a company.")
    today = frappe.utils.nowdate()
    pf["d"] = today
    pf["m"] = frappe.utils.get_first_day(today)
    pf["fy"] = fd.get("fy_from") or pf["m"]
    pf["due"] = frappe.utils.add_days(today, 30)
    one = lambda q: float(sql(q, pf)[0][0] or 0)
    k = {}
    k["billed_month"] = one("select sum(base_grand_total) from `tabSales Invoice` where docstatus=1 and company=%(c)s and posting_date between %(m)s and %(d)s")
    k["billed_fy"] = one("select sum(base_grand_total) from `tabSales Invoice` where docstatus=1 and company=%(c)s and posting_date between %(fy)s and %(d)s")
    k["received_month"] = one("select sum(base_received_amount) from `tabPayment Entry` where docstatus=1 and company=%(c)s and payment_type='Receive' and posting_date between %(m)s and %(d)s")
    k["receivable"] = one("select sum(outstanding_amount) from `tabSales Invoice` where docstatus=1 and company=%(c)s and outstanding_amount > 0")
    k["receivable_overdue"] = one("select sum(outstanding_amount) from `tabSales Invoice` where docstatus=1 and company=%(c)s and outstanding_amount > 0 and due_date < %(d)s")
    k["purchased_month"] = one("select sum(base_grand_total) from `tabPurchase Invoice` where docstatus=1 and company=%(c)s and posting_date between %(m)s and %(d)s")
    k["paid_month"] = one("select sum(base_paid_amount) from `tabPayment Entry` where docstatus=1 and company=%(c)s and payment_type='Pay' and posting_date between %(m)s and %(d)s")
    k["payable"] = one("select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus=1 and company=%(c)s and outstanding_amount > 0")
    k["payable_overdue"] = one("select sum(outstanding_amount) from `tabPurchase Invoice` where docstatus=1 and company=%(c)s and outstanding_amount > 0 and due_date < %(d)s")
    k["bank_cash"] = one("""select sum(gle.debit - gle.credit) from `tabGL Entry` gle join `tabAccount` acc on acc.name = gle.account
        where gle.is_cancelled=0 and gle.company=%(c)s and acc.account_type in ('Bank', 'Cash')""")
    k["cash_sites"] = one("""select ifnull((select sum(amount) from `tabSite Cash Issue` where project in (select name from `tabProject` where company=%(c)s)), 0)
        - ifnull((select sum(amount) from `tabSite Expense Entry` where payment_source='Site Cash' and project in (select name from `tabProject` where company=%(c)s)), 0)""")
    k["draft_si"] = int(one("select count(*) from `tabSales Invoice` where docstatus=0 and company=%(c)s"))
    k["draft_pi"] = int(one("select count(*) from `tabPurchase Invoice` where docstatus=0 and company=%(c)s"))
    k["labour_today"] = 0
    if frappe.db.exists("DocType", "Labour Attendance Log"):
        k["labour_today"] = int(one("""select count(distinct labour) from `tabLabour Attendance Log`
            where log_date=%(d)s and log_type='IN' and project in (select name from `tabProject` where company=%(c)s)"""))
    k["bank_last"] = ""
    k["bank_to_check"] = 0
    if frappe.db.exists("DocType", "Bank Transaction") and frappe.get_meta("Bank Transaction").has_field("sbi_check_status"):
        bs = sql("""select max(date(creation)) up, sum(case when ifnull(sbi_check_status, '')='' then 1 else 0 end) n
            from `tabBank Transaction` where docstatus=1 and company=%(c)s""", pf, as_dict=1)[0]
        k["bank_last"] = str(bs.up or "")
        k["bank_to_check"] = int(bs.n or 0)
    out["kpi"] = k
    # last six months: sales vs purchases (before tax)
    pf["m6"] = frappe.utils.add_months(pf["m"], -5)
    months = {}
    for r in sql("""select date_format(posting_date, '%%Y-%%m') mon, sum(base_net_total) v from `tabSales Invoice`
            where docstatus=1 and company=%(c)s and posting_date >= %(m6)s group by date_format(posting_date, '%%Y-%%m')""", pf, as_dict=1):
        months[r.mon] = {"month": r.mon, "sales": float(r.v or 0), "purchases": 0.0}
    for r in sql("""select date_format(posting_date, '%%Y-%%m') mon, sum(base_net_total) v from `tabPurchase Invoice`
            where docstatus=1 and company=%(c)s and posting_date >= %(m6)s group by date_format(posting_date, '%%Y-%%m')""", pf, as_dict=1):
        if r.mon not in months:
            months[r.mon] = {"month": r.mon, "sales": 0.0, "purchases": 0.0}
        months[r.mon]["purchases"] = float(r.v or 0)
    series = []
    for i in range(6):
        key = str(frappe.utils.add_months(pf["m6"], i))[:7]
        series.append(months.get(key) or {"month": key, "sales": 0.0, "purchases": 0.0})
    out["months"] = series
    # what is owed, by how late it is
    age_q = """select sum(case when datediff(%(d)s, due_date) <= 0 then outstanding_amount else 0 end) not_due,
        sum(case when datediff(%(d)s, due_date) between 1 and 30 then outstanding_amount else 0 end) d30,
        sum(case when datediff(%(d)s, due_date) between 31 and 60 then outstanding_amount else 0 end) d60,
        sum(case when datediff(%(d)s, due_date) between 61 and 90 then outstanding_amount else 0 end) d90,
        sum(case when datediff(%(d)s, due_date) > 90 then outstanding_amount else 0 end) d90p
        from `tab"""
    ageing = {}
    for pair in [["receive", "Sales Invoice"], ["pay", "Purchase Invoice"]]:
        a = sql(age_q + pair[1] + "` where docstatus=1 and company=%(c)s and outstanding_amount > 0", pf, as_dict=1)[0]
        ageing[pair[0]] = {"not_due": float(a.not_due or 0), "d30": float(a.d30 or 0), "d60": float(a.d60 or 0),
            "d90": float(a.d90 or 0), "d90p": float(a.d90p or 0)}
    out["ageing"] = ageing
    out["milestones"] = sql("""select so.name sales_order, so.project, so.customer, ps.payment_term, ps.sbi_stage stage,
        ps.due_date, ps.payment_amount from `tabPayment Schedule` ps
        join `tabSales Order` so on so.name = ps.parent and ps.parenttype = 'Sales Order'
        where so.docstatus=1 and so.company=%(c)s and ifnull(ps.sbi_billed, 0)=0
        and ifnull(ps.payment_term, '') != 'Non-milestone items' and so.status not in ('Closed', 'Completed') and ps.due_date <= %(due)s
        order by ps.due_date limit 12""", pf, as_dict=1)
    out["sales"] = sql("""select name, posting_date, customer party, project, base_grand_total grand_total, status, docstatus
        from `tabSales Invoice` where company=%(c)s and docstatus < 2 order by creation desc limit 6""", pf, as_dict=1)
    out["purchases"] = sql("""select name, posting_date, supplier party, project, base_grand_total grand_total, status, docstatus
        from `tabPurchase Invoice` where company=%(c)s and docstatus < 2 order by creation desc limit 6""", pf, as_dict=1)
    done = True

# ================================================================== HR: attendance for a day, a salary month or any dates
HRS_MAP = [["start_day", "sbi_salary_start_day", 1], ["full_hours", "sbi_full_day_hours", 8.0], ["half_hours", "sbi_half_day_hours", 4.0],
    ["office_name", "sbi_office_name", ""], ["office_lat", "sbi_office_latitude", 0.0], ["office_lng", "sbi_office_longitude", 0.0],
    ["office_radius", "sbi_office_radius", 200], ["block_outside", "sbi_block_outside", 1], ["in_time", "sbi_office_in_time", "09:30"],
    ["out_time", "sbi_office_out_time", "18:30"], ["late_grace", "sbi_late_grace", 10], ["reminder", "sbi_reminder_minutes", 15]]
HRS = {}
for pair in HRS_MAP:
    HRS[pair[0]] = pair[2]
if act in ("hr", "hr_office", "hr_settings_save", "hr_mark_att") and frappe.db.exists("DocType", "HR Settings"):
    hm = frappe.get_meta("HR Settings")
    for pair in HRS_MAP:
        if hm.has_field(pair[1]):
            v = frappe.db.get_single_value("HR Settings", pair[1])
            if v not in (None, "") and not (pair[0] in ("start_day", "full_hours", "half_hours", "office_radius") and not v):
                HRS[pair[0]] = v
    for k in ("in_time", "out_time"):
        tp = str(HRS[k] or "").split(":")
        HRS[k] = ("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2] if tp[0] else ""
CK_PLUS = frappe.db.exists("DocType", "Employee Checkin") and frappe.get_meta("Employee Checkin").has_field("sbi_within")
HR_F = fd.get("from_date") or fd.get("date") or frappe.utils.nowdate()
HR_T = fd.get("to_date") or HR_F
if HR_T < HR_F:
    hr_tmp = HR_F
    HR_F = HR_T
    HR_T = hr_tmp
pf["f"] = HR_F
pf["t"] = HR_T
OFFICE_SQL = """select c.employee, max(e.employee_name) employee_name, max(e.company) company, date(c.time) d,
    min(case when c.log_type='IN' then c.time end) first_in, max(case when c.log_type='OUT' then c.time end) last_out,
    substring_index(group_concat(c.log_type order by c.time desc separator '|'), '|', 1) last_type, count(*) punches,
    """ + ("sum(case when ifnull(c.sbi_within, 1)=0 then 1 else 0 end) outside, max(ifnull(c.sbi_distance, 0)) max_dist," if CK_PLUS else "0 outside, 0 max_dist,") + """
    max(e.designation) designation
    from `tabEmployee Checkin` c join `tabEmployee` e on e.name = c.employee
    where date(c.time) between %(f)s and %(t)s""" + (" and e.company=%(c)s" if company else "") + """
    group by c.employee, date(c.time) order by c.employee, d"""

if act == "hr":
    pc = " and project in (select name from `tabProject` where company=%(c)s)" if company else ""
    sites = []
    labour_total = 0
    if frappe.db.exists("DocType", "Labour Attendance Log"):
        sites = sql("""select t.project, count(distinct t.labour) labour, count(*) present, sum(t.out_fence) outside, sum(ifnull(lb.daily_wage, 0)) wage
            from (select project, labour, log_date, max(case when ifnull(within_geofence, 1)=0 then 1 else 0 end) out_fence
                from `tabLabour Attendance Log` where log_date between %(f)s and %(t)s and log_type='IN' and ifnull(labour, '')!=''""" + pc + """
                group by project, labour, log_date) t
            left join `tabLabour` lb on lb.name = t.labour
            group by t.project order by present desc""", pf, as_dict=1)
        labour_total = int(sql("select count(*) from `tabLabour` where status='Active'")[0][0] or 0)
    ec = " and company=%(c)s" if company else ""
    emp = {"active": 0, "status": []}
    staff = []
    if frappe.db.exists("DocType", "Employee"):
        staff = sql("select name, employee_name, designation, ifnull(user_id, '') user_id from `tabEmployee` where status='Active'" + ec + " order by employee_name", pf, as_dict=1)
        emp["active"] = len(staff)
    if frappe.db.exists("DocType", "Attendance"):
        emp["status"] = sql("select status, count(*) n from `tabAttendance` where attendance_date between %(f)s and %(t)s and docstatus=1" + ec +
            " group by status", pf, as_dict=1)
    office = {}
    days = []
    if frappe.db.exists("DocType", "Employee Checkin"):
        days = sql(OFFICE_SQL, pf, as_dict=1)
    for r in days:
        hrs = 0.0
        if r.first_in and r.last_out and r.last_out > r.first_in:
            hrs = frappe.utils.time_diff_in_hours(r.last_out, r.first_in)
        o = office.get(r.employee)
        if not o:
            o = {"employee": r.employee, "employee_name": r.employee_name, "designation": r.designation, "days": 0, "full": 0, "half": 0,
                "short": 0, "no_out": 0, "hours": 0.0, "outside": 0, "punches": 0, "late": 0}
            office[r.employee] = o
        o["days"] = o["days"] + 1
        if HRS["in_time"] and r.first_in and r.first_in > frappe.utils.add_to_date(frappe.utils.get_datetime(str(r.d) + " " + HRS["in_time"] + ":00"), minutes=frappe.utils.cint(HRS["late_grace"])):
            o["late"] = o["late"] + 1
        o["hours"] = o["hours"] + hrs
        o["outside"] = o["outside"] + int(r.outside or 0)
        o["punches"] = o["punches"] + int(r.punches or 0)
        if not r.last_out or (r.first_in and r.last_out < r.first_in):
            o["no_out"] = o["no_out"] + 1
        elif hrs >= frappe.utils.flt(HRS["full_hours"]):
            o["full"] = o["full"] + 1
        elif hrs >= frappe.utils.flt(HRS["half_hours"]):
            o["half"] = o["half"] + 1
        else:
            o["short"] = o["short"] + 1
        if HR_F == HR_T:
            o["first_in"] = str(r.first_in or "")[11:16]
            o["last_out"] = str(r.last_out or "")[11:16] if (r.last_out and (not r.first_in or r.last_out > r.first_in)) else ""
            o["last_type"] = r.last_type
            o["max_dist"] = r.max_dist
    rows = []
    for s in staff:
        o = office.get(s.name)
        if o:
            o["hours"] = round(o["hours"], 2)
            rows.append(o)
        else:
            rows.append({"employee": s.name, "employee_name": s.employee_name, "designation": s.designation, "days": 0, "hours": 0,
                "outside": 0, "punches": 0, "full": 0, "half": 0, "short": 0, "no_out": 0, "no_login": 0 if s.user_id else 1})
    for k in office:
        found = False
        for s in staff:
            if s.name == k:
                found = True
        if not found:
            rows.append(office[k])
    pend = {}
    for pair in [["leave", "Leave Application", "status='Open' and docstatus=0"],
                 ["expense", "Expense Claim", "docstatus=0"],
                 ["advance", "Employee Advance", "docstatus=0"]]:
        pend[pair[0]] = 0
        if frappe.db.exists("DocType", pair[1]):
            pend[pair[0]] = int(sql("select count(*) from `tab" + pair[1] + "` where " + pair[2] + ec, pf)[0][0] or 0)
    out = {"from_date": HR_F, "to_date": HR_T, "sites": sites, "labour_total": labour_total, "employees": emp, "office": rows,
        "pending": pend, "settings": HRS, "office_ready": 1 if CK_PLUS else 0}
    done = True

if act == "hr_site":
    if not project:
        frappe.throw("Pick a project.")
    out["rows"] = sql("""select l.labour, max(l.labour_name) labour_name, count(distinct l.log_date) days,
        min(case when l.log_type='IN' then l.log_datetime end) first_in, max(l.log_datetime) last_punch,
        substring_index(group_concat(l.log_type order by l.log_datetime desc separator '|'), '|', 1) last_type,
        min(ifnull(l.within_geofence, 1)) in_fence, max(l.verification_method) method, count(*) punches,
        max(lb.skill) skill, max(lb.daily_wage) wage
        from `tabLabour Attendance Log` l left join `tabLabour` lb on lb.name = l.labour
        where l.project=%(p)s and l.log_date between %(f)s and %(t)s and ifnull(l.labour, '')!='' group by l.labour order by first_in""", pf, as_dict=1)
    done = True

if act == "hr_office":
    emp_id = fd.get("employee") or ""
    if not emp_id:
        frappe.throw("Pick an employee.")
    pf["e"] = emp_id
    cols = "name, log_type, time, latitude, longitude, ifnull(device_id, '') device_id"
    if CK_PLUS:
        cols = cols + ", ifnull(sbi_distance, 0) distance, ifnull(sbi_within, 1) within, ifnull(sbi_photo, '') photo, ifnull(sbi_accuracy, 0) accuracy, ifnull(sbi_remarks, '') remarks"
    if frappe.get_meta("Employee Checkin").has_field("sbi_address"):
        cols = cols + ", ifnull(sbi_address, '') address"
    out["employee"] = frappe.db.get_value("Employee", emp_id, ["name", "employee_name", "designation", "company"], as_dict=1)
    out["punches"] = sql("select " + cols + " from `tabEmployee Checkin` where employee=%(e)s and date(time) between %(f)s and %(t)s order by time", pf, as_dict=1)
    out["attendance"] = sql("select name, attendance_date, status, docstatus from `tabAttendance` where employee=%(e)s and attendance_date between %(f)s and %(t)s and docstatus < 2", pf, as_dict=1)
    out["settings"] = HRS
    done = True

if act == "hr_settings_save":
    vals = {}
    sd = frappe.utils.cint(fd.get("start_day") or 1)
    if sd < 1 or sd > 28:
        frappe.throw("The salary month must start on a day from 1 to 28.")
    vals["sbi_salary_start_day"] = sd
    full = frappe.utils.flt(fd.get("full_hours") or 8)
    half = frappe.utils.flt(fd.get("half_hours") or 4)
    if full <= 0 or half <= 0 or half > full:
        frappe.throw("Half-day hours must be more than 0 and not more than full-day hours.")
    vals["sbi_full_day_hours"] = full
    vals["sbi_half_day_hours"] = half
    if fd.get("office_lat") not in (None, "") or fd.get("office_lng") not in (None, ""):
        la = frappe.utils.flt(fd.get("office_lat"))
        lo = frappe.utils.flt(fd.get("office_lng"))
        if la < -90 or la > 90 or lo < -180 or lo > 180:
            frappe.throw("The office location is not valid.")
        vals["sbi_office_latitude"] = la
        vals["sbi_office_longitude"] = lo
    vals["sbi_office_name"] = (fd.get("office_name") or "")[:140]
    vals["sbi_office_radius"] = max(20, frappe.utils.cint(fd.get("office_radius") or 200))
    vals["sbi_block_outside"] = 1 if str(fd.get("block_outside") or "0") in ("1", "true") else 0
    for pair in [["in_time", "sbi_office_in_time"], ["out_time", "sbi_office_out_time"]]:
        tv = (fd.get(pair[0]) or "").strip()
        if tv:
            tp = tv.split(":")
            if len(tp) < 2 or not tp[0].isdigit() or not tp[1][:2].isdigit() or int(tp[0]) > 23 or int(tp[1][:2]) > 59:
                frappe.throw("Office time " + tv + " is not valid. Use HH:MM, for example 09:30.")
            vals[pair[1]] = ("0" + tp[0])[-2:] + ":" + tp[1][:2] + ":00"
    if vals.get("sbi_office_in_time") and vals.get("sbi_office_out_time") and vals["sbi_office_out_time"] <= vals["sbi_office_in_time"]:
        frappe.throw("Office end time must be after the start time.")
    vals["sbi_late_grace"] = max(0, min(240, frappe.utils.cint(fd.get("late_grace") or 0)))
    vals["sbi_reminder_minutes"] = max(0, min(120, frappe.utils.cint(fd.get("reminder") if fd.get("reminder") not in (None, "") else 15)))
    hm = frappe.get_meta("HR Settings")
    for k in vals:
        if not hm.has_field(k):
            frappe.throw("Run the Lite ERP installer again: HR Settings has no field " + k + ".")
    for k in vals:
        frappe.db.set_value("HR Settings", "HR Settings", k, vals[k])
    out = {"ok": 1}
    done = True

if act == "hr_mark_att":
    if HR_T > frappe.utils.nowdate():
        HR_T = frappe.utils.nowdate()
        pf["t"] = HR_T
    full = frappe.utils.flt(HRS["full_hours"])
    half = frappe.utils.flt(HRS["half_hours"])
    have = {}
    for a in sql("select employee, attendance_date from `tabAttendance` where attendance_date between %(f)s and %(t)s and docstatus < 2", pf, as_dict=1):
        have[a.employee + "|" + str(a.attendance_date)] = 1
    made = 0
    present = 0
    halfd = 0
    skipped = 0
    no_out = 0
    short = 0
    errors = []
    for r in sql(OFFICE_SQL, pf, as_dict=1):
        if have.get(r.employee + "|" + str(r.d)):
            skipped = skipped + 1
            continue
        if not r.last_out or not r.first_in or r.last_out <= r.first_in:
            no_out = no_out + 1
            continue
        hrs = frappe.utils.time_diff_in_hours(r.last_out, r.first_in)
        st = "Present" if hrs >= full else ("Half Day" if hrs >= half else "")
        if not st:
            short = short + 1
            continue
        try:
            att = frappe.get_doc({"doctype": "Attendance", "employee": r.employee, "attendance_date": r.d, "status": st, "company": r.company,
                "in_time": r.first_in, "out_time": r.last_out, "working_hours": round(hrs, 2)})
            if HRS["in_time"]:
                lim = frappe.utils.add_to_date(frappe.utils.get_datetime(str(r.d) + " " + HRS["in_time"] + ":00"), minutes=frappe.utils.cint(HRS["late_grace"]))
                if r.first_in > lim:
                    att.late_entry = 1
            if HRS["out_time"] and r.last_out < frappe.utils.get_datetime(str(r.d) + " " + HRS["out_time"] + ":00"):
                att.early_exit = 1
            att.insert(ignore_permissions=True)
            att.submit()
            made = made + 1
            if st == "Present":
                present = present + 1
            else:
                halfd = halfd + 1
        except Exception as e:
            errors.append((r.employee_name or r.employee) + " " + str(r.d) + ": " + frappe.utils.strip_html(str(e))[:160])
    out = {"made": made, "present": present, "half": halfd, "skipped": skipped, "no_out": no_out, "short": short, "errors": errors[:20]}
    done = True

# ================================================================== BANK: accounts and how up to date they are
BANK_REASONS = ("Loan / capital", "Transfer between own accounts", "Advance (invoice to follow)", "Salary / wages",
    "Bank charges / interest", "Tax / statutory payment", "Refund / return", "Cash deposit / withdrawal", "Other")

if act == "bank_accounts":
    cc = " and ba.company=%(c)s" if company else ""
    rows = sql("""select ba.name, ba.account_name, ba.bank, ba.bank_account_no, ba.account, ba.company
        from `tabBank Account` ba where ifnull(ba.is_company_account, 0)=1 and ifnull(ba.disabled, 0)=0""" + cc +
        " order by ba.account_name", pf, as_dict=1)
    for r in rows:
        st = sql("""select max(date) last_date, max(date(creation)) last_upload, count(*) n_lines,
            sum(case when ifnull(sbi_check_status, '')='' then 1 else 0 end) to_check,
            sum(case when sbi_check_status='Matched' then 1 else 0 end) matched,
            sum(case when sbi_check_status='No Invoice' then 1 else 0 end) no_invoice
            from `tabBank Transaction` where docstatus=1 and bank_account=%s""", r.name, as_dict=1)[0]
        r.update(st)
    out["accounts"] = rows
    out["reasons"] = BANK_REASONS
    done = True

# ================================================================== BANK: save an uploaded statement
if act == "bank_upload":
    ba = fd.get("bank_account") or ""
    if not ba or not frappe.db.exists("Bank Account", ba):
        frappe.throw("Pick the bank account.")
    bco = frappe.db.get_value("Bank Account", ba, "company") or company
    cur = frappe.db.get_value("Company", bco, "default_currency") or "INR"
    rows = json.loads(fd.get("rows") or "[]")
    made = 0
    skipped = 0
    first = ""
    last = ""
    for r in rows:
        d = (r.get("date") or "")[:10]
        wd = round(frappe.utils.flt(r.get("withdrawal")), 2)
        dp = round(frappe.utils.flt(r.get("deposit")), 2)
        if not d or (wd <= 0 and dp <= 0):
            skipped += 1
            continue
        desc = (r.get("description") or "").strip()
        ref = (r.get("reference") or "").strip()[:140]
        key = (ba + "|" + d + "|" + str(wd) + "|" + str(dp) + "|" + str(r.get("balance") or "") + "|" + (ref or desc[:40]))[:140]
        if frappe.db.exists("Bank Transaction", {"transaction_id": key, "docstatus": ["<", 2]}):
            skipped += 1
            continue
        doc = frappe.get_doc({"doctype": "Bank Transaction", "date": d, "bank_account": ba, "company": bco,
            "deposit": dp, "withdrawal": wd, "currency": cur, "description": desc, "reference_number": ref,
            "transaction_id": key})
        doc.insert(ignore_permissions=True)
        doc.submit()
        made += 1
        if not first or d < first:
            first = d
        if not last or d > last:
            last = d
    out = {"made": made, "skipped": skipped, "from_date": first, "to_date": last}
    done = True

# ================================================================== BANK: lines with GST invoice suggestions
if act == "bank_list":
    ba = fd.get("bank_account") or ""
    if not ba:
        frappe.throw("Pick the bank account.")
    pf["b"] = ba
    bco = frappe.db.get_value("Bank Account", ba, "company") or company
    pf["bc"] = bco
    show = fd.get("show") or "check"
    sc = ""
    if show == "check":
        sc = " and ifnull(bt.sbi_check_status, '')=''"
    elif show == "matched":
        sc = " and bt.sbi_check_status='Matched'"
    elif show == "noinv":
        sc = " and bt.sbi_check_status='No Invoice'"
    txns = sql("""select bt.name, bt.date, bt.description, bt.reference_number ref, bt.deposit, bt.withdrawal,
        ifnull(bt.sbi_check_status, '') st, bt.sbi_match_doctype mdt, bt.sbi_match_name mname, bt.sbi_reason reason,
        bt.sbi_remarks remarks, bt.sbi_checked_by checked_by
        from `tabBank Transaction` bt where bt.docstatus=1 and bt.bank_account=%(b)s and bt.date between %(f)s and %(t)s""" + sc +
        " order by bt.date, bt.creation limit 400", pf, as_dict=1)
    counts = sql("""select sum(case when ifnull(sbi_check_status, '')='' then 1 else 0 end) to_check,
        sum(case when sbi_check_status='Matched' then 1 else 0 end) matched,
        sum(case when sbi_check_status='No Invoice' then 1 else 0 end) no_invoice, count(*) total
        from `tabBank Transaction` where docstatus=1 and bank_account=%(b)s and date between %(f)s and %(t)s""", pf, as_dict=1)[0]
    for t in txns:
        t["cands"] = []
        if t.st:
            if t.mname and t.mdt:
                t["minfo"] = sql("select " + ("customer_name" if t.mdt == "Sales Invoice" else "supplier_name") +
                    " party, base_grand_total g, project from `tab" + t.mdt + "` where name=%s", t.mname, as_dict=1)
            continue
        amt = frappe.utils.flt(t.deposit) or frappe.utils.flt(t.withdrawal)
        dt_ = "Sales Invoice" if frappe.utils.flt(t.deposit) > 0 else "Purchase Invoice"
        pcol = "customer_name" if dt_ == "Sales Invoice" else "supplier_name"
        q = {"a": amt, "d": t.date, "bc": bco}
        found = sql("select name, " + pcol + """ party, posting_date, base_grand_total g, outstanding_amount o, project
            from `tab""" + dt_ + """` inv where docstatus=1 and company=%(bc)s and ifnull(is_return, 0)=0
            and posting_date between date_sub(%(d)s, interval 400 day) and date_add(%(d)s, interval 7 day)
            and ((base_grand_total between %(a)s - 1 and %(a)s / 0.85) or (outstanding_amount between %(a)s - 1 and %(a)s + 1))
            and not exists (select 1 from `tabBank Transaction` x where x.sbi_check_status='Matched' and x.sbi_match_name=inv.name)
            order by abs(base_grand_total - %(a)s) limit 6""", q, as_dict=1)
        low = (t.description or "").lower()
        scored = []
        for inv in found:
            g = frappe.utils.flt(inv.g)
            o = frappe.utils.flt(inv.o)
            if abs(g - amt) <= 1 or (o > 0 and abs(o - amt) <= 1):
                note = "exact"
                score = 0.0
            else:
                pct = (g - amt) * 100.0 / g if g else 100.0
                note = "less " + str(round(pct, 1)) + "% (TDS / retention?)"
                score = pct
            named = 0
            for tok in (inv.party or "").lower().replace(".", " ").split():
                if len(tok) >= 4 and tok not in ("private", "limited", "india", "pvt", "ltd", "engineering", "industries") and tok in low:
                    named = 1
            if named:
                score = score - 50
                note = note + ", name in narration"
            scored.append({"doctype": dt_, "name": inv.name, "party": inv.party, "date": inv.posting_date, "amount": g,
                "outstanding": o, "project": inv.project, "note": note, "score": score})
        t["cands"] = sorted(scored, key=lambda x: x["score"])[:3]
        t["kind"] = dt_
    out = {"rows": txns, "counts": counts, "reasons": BANK_REASONS}
    done = True

# ================================================================== BANK: record the check
if act == "bank_set":
    txn = fd.get("txn") or ""
    if not frappe.db.exists("Bank Transaction", txn):
        frappe.throw("Bank line not found.")
    stv = fd.get("status") or ""
    vals = {"sbi_check_status": "", "sbi_match_doctype": None, "sbi_match_name": None, "sbi_reason": None,
        "sbi_remarks": None, "sbi_checked_by": user, "sbi_checked_on": frappe.utils.now()}
    if stv == "Matched":
        inv = (fd.get("name") or "").strip()
        idt = fd.get("doctype") or ""
        if not idt:
            if frappe.db.exists("Sales Invoice", inv):
                idt = "Sales Invoice"
            elif frappe.db.exists("Purchase Invoice", inv):
                idt = "Purchase Invoice"
        if idt not in ("Sales Invoice", "Purchase Invoice") or not frappe.db.exists(idt, inv):
            frappe.throw("No sales or purchase invoice " + inv)
        if frappe.db.get_value(idt, inv, "docstatus") != 1:
            frappe.throw(inv + " is not submitted.")
        other = frappe.db.get_value("Bank Transaction", {"sbi_check_status": "Matched", "sbi_match_name": inv, "name": ["!=", txn]}, "name")
        if other:
            frappe.throw(inv + " is already matched to bank line " + other)
        vals.update({"sbi_check_status": "Matched", "sbi_match_doctype": idt, "sbi_match_name": inv,
            "sbi_remarks": (fd.get("remarks") or "").strip() or None})
    elif stv == "No Invoice":
        rem = (fd.get("remarks") or "").strip()
        rsn = fd.get("reason") or ""
        if not rem:
            frappe.throw("Write a remark saying what this entry is.")
        vals.update({"sbi_check_status": "No Invoice", "sbi_reason": rsn or "Other", "sbi_remarks": rem})
    else:
        vals["sbi_checked_by"] = None
        vals["sbi_checked_on"] = None
    frappe.db.set_value("Bank Transaction", txn, vals)
    out["ok"] = 1
    done = True

# ================================================================== BANK: entries with no invoice (for the owner)
if act == "bank_noinv":
    cc = " and bt.company=%(c)s" if company else ""
    out["rows"] = sql("""select bt.name, bt.date, bt.bank_account, bt.description, bt.reference_number ref, bt.deposit, bt.withdrawal,
        bt.sbi_reason reason, bt.sbi_remarks remarks, bt.sbi_checked_by checked_by, bt.sbi_checked_on checked_on
        from `tabBank Transaction` bt where bt.docstatus=1 and bt.sbi_check_status='No Invoice'
        and bt.date between %(f)s and %(t)s""" + cc + " order by bt.date desc limit 1000", pf, as_dict=1)
    done = True

# ================================================================== PROJECT BOQ: typed or uploaded, per stage
BOQ_TYPES = [["Material", "material_amount", "material_rate"], ["Manpower", "labour_amount", "labour_rate"],
    ["Equipment", "equipment_amount", "equipment_rate"], ["Transport", "other_amount", "other_rate"],
    ["Subcontract", "subcontract_amount", "subcontract_rate"], ["Other", "other_amount", "other_rate"]]

if act == "boq_stages":
    if not project:
        frappe.throw("Pick a project.")
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    seen = {}
    lst = []
    if boq:
        for r in sql("""select stage, count(*) n_lines, sum(amount) amt from `tabProject BOQ Item` where parent=%s
                group by stage order by min(idx)""", boq, as_dict=1):
            if r.stage:
                seen[r.stage] = {"stage": r.stage, "lines": int(r.n_lines or 0), "amount": float(r.amt or 0), "source": "BOQ"}
                lst.append(seen[r.stage])
    for r in sql("""select t.sbi_stage from `tabTask` t left join `tabProject Stage` ps on ps.name = t.sbi_stage
            where t.project=%(p)s and ifnull(t.sbi_stage, '') != '' group by t.sbi_stage order by min(ifnull(ps.sequence, 999))""", pf):
        if r[0] not in seen:
            seen[r[0]] = {"stage": r[0], "lines": 0, "amount": 0.0, "source": "Project tasks"}
            lst.append(seen[r[0]])
    for r in sql("""select ps.sbi_stage from `tabPayment Schedule` ps join `tabSales Order` so on so.name = ps.parent
            where ps.parenttype='Sales Order' and so.docstatus=1 and ifnull(ps.sbi_stage, '') != ''
            and (so.project=%(p)s or so.name in (select sales_order from `tabProject` where name=%(p)s))
            group by ps.sbi_stage order by min(ps.idx)""", pf):
        if r[0] not in seen:
            seen[r[0]] = {"stage": r[0], "lines": 0, "amount": 0.0, "source": "Sales order milestones"}
            lst.append(seen[r[0]])
    out["stages"] = lst
    out["boq"] = boq or ""
    out["master"] = frappe.get_all("Project Stage", filters={"is_active": 1}, pluck="name", order_by="sequence asc") or \
        frappe.get_all("Project Stage", pluck="name", order_by="sequence asc")
    done = True

if act == "boq_add_stage":
    nm = (fd.get("stage_name") or "").strip()
    if not nm:
        frappe.throw("Type the stage name.")
    if len(nm) > 140:
        frappe.throw("Stage name is too long.")
    if not frappe.db.exists("Project Stage", nm):
        top = frappe.db.sql("select max(ifnull(sequence, 0)) from `tabProject Stage`")[0][0] or 0
        frappe.get_doc({"doctype": "Project Stage", "stage_name": nm, "is_active": 1, "sequence": int(top) + 1}).insert(ignore_permissions=True)
    out["stage"] = nm
    done = True

if act == "boq_get":
    if not project or not stage:
        frappe.throw("Pick the project and the stage.")
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    rows = []
    if boq:
        for r in sql("""select idx, sbi_sl_no sl, sbi_description description, activity, sbi_type type, unit, qty, rate, amount,
                labour_amount, material_amount, equipment_amount, subcontract_amount, other_amount, sbi_remarks remarks
                from `tabProject BOQ Item` where parent=%s and stage=%s order by idx""", (boq, stage), as_dict=1):
            typ = r.type or ""
            if not typ:
                best = 0.0
                for t in [["Material", r.material_amount], ["Manpower", r.labour_amount], ["Equipment", r.equipment_amount],
                          ["Subcontract", r.subcontract_amount], ["Other", r.other_amount]]:
                    if frappe.utils.flt(t[1]) > best:
                        best = frappe.utils.flt(t[1])
                        typ = t[0]
            rows.append({"sl": r.sl or str(len(rows) + 1), "description": r.description or r.activity or "", "type": typ or "Material",
                "unit": r.unit or "", "qty": frappe.utils.flt(r.qty), "rate": frappe.utils.flt(r.rate), "remarks": r.remarks or ""})
    out = {"boq": boq or "", "rows": rows}
    done = True

if act == "boq_save":
    if not project or not stage:
        frappe.throw("Pick the project and the stage.")
    rows = json.loads(fd.get("rows") or "[]")
    # one generic activity per type, so the line's whole amount lands on that type
    acts = {}
    for t in BOQ_TYPES:
        an = "BOQ " + t[0]
        if not frappe.db.exists("Site Activity", an):
            a = {"doctype": "Site Activity", "activity_name": an, "unit_rate": 1, "labour_rate": 0, "material_rate": 0,
                "equipment_rate": 0, "subcontract_rate": 0, "other_rate": 0}
            a[t[2]] = 1
            frappe.get_doc(a).insert(ignore_permissions=True)
        acts[t[0]] = [an, t[1]]
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    if boq:
        doc = frappe.get_doc("Project BOQ", boq)
    else:
        doc = frappe.get_doc({"doctype": "Project BOQ", "naming_series": "PBOQ-.####", "project": project,
            "boq_date": frappe.utils.nowdate(), "items": []})
    keep = []
    for it in doc.get("items") or []:
        if (it.stage or "") != stage:
            keep.append(it)
    doc.set("items", keep)
    n = 0
    for r in rows:
        desc = (r.get("description") or "").strip()
        if not desc:
            continue
        typ = r.get("type") or "Material"
        if typ not in acts:
            typ = "Other"
        qty = frappe.utils.flt(r.get("qty"))
        rate = frappe.utils.flt(r.get("rate"))
        amt = qty * rate
        line = {"stage": stage, "activity": acts[typ][0], "sbi_sl_no": str(r.get("sl") or "")[:20], "sbi_description": desc,
            "sbi_type": typ, "unit": (r.get("unit") or "")[:40], "qty": qty, "rate": rate, "amount": amt,
            "labour_amount": 0, "material_amount": 0, "equipment_amount": 0, "subcontract_amount": 0, "other_amount": 0,
            "sbi_remarks": (r.get("remarks") or "").strip()}
        line[acts[typ][1]] = amt
        doc.append("items", line)
        n += 1
    tot = {"amount": 0.0, "labour_amount": 0.0, "material_amount": 0.0, "equipment_amount": 0.0, "subcontract_amount": 0.0, "other_amount": 0.0}
    for it in doc.get("items") or []:
        for key in tot:
            tot[key] = tot[key] + frappe.utils.flt(it.get(key))
    doc.total_amount = tot["amount"]
    doc.total_labour = tot["labour_amount"]
    doc.total_material = tot["material_amount"]
    doc.total_equipment = tot["equipment_amount"]
    doc.total_subcontract = tot["subcontract_amount"]
    doc.total_other = tot["other_amount"]
    # the form's own validate re-derives the split from activity rates; the totals above already match it
    doc.flags.ignore_validate = True
    if boq:
        doc.save(ignore_permissions=True)
    else:
        doc.insert(ignore_permissions=True)
    out = {"boq": doc.name, "lines": n}
    done = True

# ================================================================== ORDERS (sales + purchase): lines with MS yes/no, milestones as payment terms
KIND = "purchase" if fd.get("kind") == "purchase" else "sales"
if KIND == "purchase":
    O_DT = "Purchase Order"
    O_IT = "Purchase Order Item"
    INV_DT = "Purchase Invoice"
    PARTY = "supplier"
    DETAIL = "po_detail"
    SRC = "sbi_source_purchase_order"
    TAX_DT = "Purchase Taxes and Charges Template"
    TAX_CH = "Purchase Taxes and Charges"
    MAKE_INV = "erpnext.buying.doctype.purchase_order.purchase_order.make_purchase_invoice"
    DATE_F = "schedule_date"
    ITEM_FLAG = "is_purchase_item"
else:
    O_DT = "Sales Order"
    O_IT = "Sales Order Item"
    INV_DT = "Sales Invoice"
    PARTY = "customer"
    DETAIL = "so_detail"
    SRC = "sbi_source_sales_order"
    TAX_DT = "Sales Taxes and Charges Template"
    TAX_CH = "Sales Taxes and Charges"
    MAKE_INV = "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"
    DATE_F = "delivery_date"
    ITEM_FLAG = "is_sales_item"
NON_MS_TERM = "Non-milestone items"
UOM_FIRST = ["Square Foot", "Square Meter", "Nos", "Meter", "Running Meter", "Cubic Meter", "Kg", "Tonne", "Metric Ton", "Lump Sum", "Sq Feet", "Sqm"]
UOM_ALIAS = {"sqft": "Square Foot", "sq.ft": "Square Foot", "sq ft": "Square Foot", "sft": "Square Foot", "sq.ft.": "Square Foot",
    "sqm": "Square Meter", "sq.m": "Square Meter", "sq m": "Square Meter", "sq.mt": "Square Meter", "m2": "Square Meter",
    "cum": "Cubic Meter", "cu.m": "Cubic Meter", "m3": "Cubic Meter", "rmt": "Running Meter", "rm": "Running Meter", "r.m": "Running Meter",
    "mtr": "Meter", "m": "Meter", "no": "Nos", "nos.": "Nos", "no.": "Nos", "each": "Nos", "kgs": "Kg", "mt": "Metric Ton", "ton": "Tonne",
    "tons": "Tonne", "ls": "Lump Sum", "l.s": "Lump Sum", "lumpsum": "Lump Sum", "job": "Lump Sum"}

if act == "order_setup":
    if not project:
        frappe.throw("Pick a project.")
    pr = frappe.db.get_value("Project", project, ["customer", "company", "sbi_contract_value"], as_dict=1) or {}
    pco = pr.get("company") or company
    out["company"] = pco
    if KIND == "purchase":
        out["parties"] = frappe.get_all("Supplier", filters={"disabled": 0}, pluck="name", order_by="name asc", limit_page_length=3000)
        out["default_party"] = ""
    else:
        out["parties"] = frappe.get_all("Customer", filters={"disabled": 0}, pluck="name", order_by="name asc", limit_page_length=3000)
        out["default_party"] = pr.get("customer") or ""
    out["items"] = sql("select name, item_name, ifnull(gst_hsn_code, '') hsn from `tabItem` where disabled=0 and is_stock_item=0 and " + ITEM_FLAG +
        "=1 order by (ifnull(gst_hsn_code, '')=''), item_name limit 400", as_dict=1)
    last = sql("select oi.item_code from `tab" + O_IT + "` oi join `tab" + O_DT + "` o on o.name = oi.parent where o.company=%s and o.docstatus=1 order by o.creation desc limit 1", pco)
    out["default_item"] = last[0][0] if last else ""
    out["templates"] = frappe.get_all(TAX_DT, filters={"company": pco, "disabled": 0}, pluck="name", order_by="name asc")
    lt = sql("select taxes_and_charges from `tab" + O_DT + "` where company=%s and docstatus=1 and ifnull(taxes_and_charges, '')!='' order by creation desc limit 1", pco)
    out["default_template"] = lt[0][0] if lt else ""
    allu = frappe.get_all("UOM", filters={"enabled": 1}, pluck="name", order_by="name asc", limit_page_length=1000)
    have = {}
    for u in allu:
        have[u.lower()] = u
    first = []
    for u in UOM_FIRST:
        if u.lower() in have:
            first.append(have[u.lower()])
    out["uoms"] = first
    more = []
    for u in allu:
        if u not in first:
            more.append(u)
    out["uoms_more"] = more
    out["stages"] = frappe.get_all("Project Stage", filters={"is_active": 1}, pluck="name", order_by="sequence asc")
    imports = []
    tcols = "subject, ifnull(task_weight, 0) w, exp_end_date d"
    if frappe.get_meta("Task").has_field("sbi_stage"):
        tcols = "coalesce(nullif(sbi_stage, ''), subject) subject, ifnull(task_weight, 0) w, exp_end_date d"
    tasks = sql("select " + tcols + """ from `tabTask` where project=%s and is_group=1
        and ifnull(parent_task, '')='' and status != 'Cancelled' order by exp_start_date, creation""", project, as_dict=1)
    if tasks:
        imports.append({"key": "tasks", "label": "Project stages", "items": [{"name": t.subject, "weight": frappe.utils.flt(t.w), "due_date": str(t.d or "")} for t in tasks]})
    boq = frappe.db.get_value("Project BOQ", {"project": project}, "name", order_by="creation desc")
    out["boq_lines"] = []
    if boq:
        bs = sql("""select stage, sum(ifnull(amount, 0)) amt from `tabProject BOQ Item` where parent=%s and ifnull(stage, '')!=''
            group by stage order by min(idx)""", boq, as_dict=1)
        if bs:
            imports.append({"key": "boq", "label": "BOQ stages", "items": [{"name": b.stage, "weight": frappe.utils.flt(b.amt), "due_date": ""} for b in bs]})
        dcol = "coalesce(nullif(sbi_description, ''), activity)" if frappe.get_meta("Project BOQ Item").has_field("sbi_description") else "activity"
        slcol = "ifnull(sbi_sl_no, '')" if frappe.get_meta("Project BOQ Item").has_field("sbi_sl_no") else "''"
        for b in sql("select " + slcol + " sl, " + dcol + " description, ifnull(unit, '') unit, ifnull(qty, 0) qty, ifnull(rate, 0) rate, ifnull(stage, '') stage from `tabProject BOQ Item` where parent=%s order by idx", boq, as_dict=1):
            un = (b.unit or "").strip().lower()
            uom = have.get(un) or UOM_ALIAS.get(un) or "Nos"
            if uom.lower() not in have:
                uom = "Nos"
            out["boq_lines"].append({"sl": b.sl, "description": b.description or "", "qty": frappe.utils.flt(b.qty), "uom": uom, "rate": frappe.utils.flt(b.rate), "stage": b.stage})
    for tp in frappe.get_all("Payment Terms Template", pluck="name", order_by="modified desc", limit_page_length=8):
        terms = sql("""select ifnull(pt.sbi_stage, '') stage, ptd.payment_term, ptd.invoice_portion w
            from `tabPayment Terms Template Detail` ptd left join `tabPayment Term` pt on pt.name = ptd.payment_term
            where ptd.parent=%s and ifnull(ptd.payment_term, '')!=%s order by ptd.idx""", (tp, NON_MS_TERM), as_dict=1)
        if terms:
            imports.append({"key": "tpl:" + tp, "label": tp, "items": [{"name": t.stage or t.payment_term, "weight": frappe.utils.flt(t.w), "due_date": ""} for t in terms]})
    out["imports"] = imports
    done = True

if act == "order_create":
    if not project:
        frappe.throw("Pick a project.")
    pr = frappe.db.get_value("Project", project, ["customer", "company", "sales_order", "project_name"], as_dict=1) or {}
    pco = pr.get("company") or company
    party = fd.get("party") or ""
    item = fd.get("item") or ""
    tmpl = fd.get("template") or ""
    today = frappe.utils.nowdate()
    if not party or not frappe.db.exists("Supplier" if KIND == "purchase" else "Customer", party):
        frappe.throw("Choose the " + ("supplier." if KIND == "purchase" else "customer."))
    if not item or not frappe.db.exists("Item", item):
        frappe.throw("Choose the item (for HSN / GST).")
    lines = []
    ms_net = 0.0
    non_net = 0.0
    for r in json.loads(fd.get("lines") or "[]"):
        desc = (r.get("description") or "").strip()
        qty = frappe.utils.flt(r.get("qty"))
        rate = frappe.utils.flt(r.get("rate"))
        if not desc and not qty and not rate:
            continue
        if not desc:
            frappe.throw("Every line needs a description.")
        if qty <= 0:
            frappe.throw("Line " + desc[:40] + ": area / quantity must be more than 0.")
        if rate < 0:
            frappe.throw("Line " + desc[:40] + ": cost per unit cannot be negative.")
        uom = r.get("uom") or "Nos"
        if not frappe.db.exists("UOM", uom):
            frappe.throw("Unit " + uom + " does not exist.")
        ms = 0 if (r.get("ms") is not None and str(r.get("ms")) in ("0", "No", "no", "false", "False")) else 1
        if ms:
            ms_net = ms_net + qty * rate
        else:
            non_net = non_net + qty * rate
        lines.append({"sl": str(r.get("sl") or "")[:20], "description": desc, "qty": qty, "uom": uom, "rate": rate, "ms": ms})
    if not lines:
        frappe.throw("Add at least one line.")
    if ms_net + non_net <= 0:
        frappe.throw("The order total is 0. Fill the cost per unit.")
    ms = []
    if ms_net > 0:
        tot = 0.0
        for r in json.loads(fd.get("rows") or "[]"):
            nm = (r.get("name") or "").strip()
            pc = frappe.utils.flt(r.get("percent"))
            if not nm and not pc:
                continue
            if not nm:
                frappe.throw("Every milestone needs a name.")
            if pc <= 0:
                frappe.throw("Milestone " + nm + " needs a % more than 0.")
            if not r.get("due_date"):
                frappe.throw("Milestone " + nm + " needs a date.")
            dd = str(r.get("due_date"))
            if dd < today:
                dd = today
            for x in ms:
                if x["name"].lower() == nm[:120].lower():
                    frappe.throw("Milestone name " + nm + " is used twice. Give each milestone its own name.")
            ms.append({"name": nm[:120], "percent": pc, "due_date": dd})
            tot = tot + pc
        if not ms:
            frappe.throw("The MS lines need milestones. Add at least one milestone.")
        if abs(tot - 100) > 0.01:
            frappe.throw("The milestones add up to " + str(round(tot, 2)) + "%. They must add up to 100% of the MS work.")
    last_due = today
    for m in ms:
        if m["due_date"] > last_due:
            last_due = m["due_date"]
    if last_due == today:
        last_due = frappe.utils.add_days(today, 30)
    o = frappe.get_doc({"doctype": O_DT, "company": pco, PARTY: party, "project": project, "transaction_date": today, DATE_F: last_due})
    if KIND == "sales":
        o.order_type = "Sales"
    for ln in lines:
        o.append("items", {"item_code": item, "item_name": ln["description"][:140], "description": ln["description"], "qty": ln["qty"],
            "uom": ln["uom"], "conversion_factor": 1, "rate": ln["rate"], "sbi_sl_no": ln["sl"], "sbi_ms": ln["ms"], DATE_F: last_due, "project": project})
    if tmpl and frappe.db.exists(TAX_DT, tmpl):
        o.taxes_and_charges = tmpl
        for t in sql("select * from `tab" + TAX_CH + "` where parent=%s and parenttype=%s order by idx", (tmpl, TAX_DT), as_dict=1):
            row = {}
            for k in ("category", "add_deduct_tax", "charge_type", "account_head", "description", "rate", "cost_center", "included_in_print_rate", "row_id"):
                if k in t:
                    row[k] = t[k]
            o.append("taxes", row)
    if ms:
        share = ms_net / (ms_net + non_net)
        tdet = []
        used = 0.0
        n = len(ms)
        for i in range(n):
            m = ms[i]
            pc = m["percent"]
            if i == n - 1 and non_net <= 0:
                portion = round(100 - used, 2)
            else:
                portion = round(pc * share, 2)
            used = used + portion
            pct = str(int(pc)) if pc == int(pc) else str(round(pc, 2))
            term = m["name"] + " " + pct + "%"
            if not frappe.db.exists("Project Stage", m["name"]):
                top = frappe.db.sql("select max(ifnull(sequence, 0)) from `tabProject Stage`")[0][0] or 0
                frappe.get_doc({"doctype": "Project Stage", "stage_name": m["name"], "is_active": 1, "sequence": int(top) + 1}).insert(ignore_permissions=True)
            if not frappe.db.exists("Payment Term", term):
                frappe.get_doc({"doctype": "Payment Term", "payment_term_name": term, "invoice_portion": pc,
                    "due_date_based_on": "Day(s) after invoice date", "credit_days": 0,
                    "description": pct + "% of milestone work - " + m["name"], "sbi_stage": m["name"]}).insert(ignore_permissions=True)
            elif not frappe.db.get_value("Payment Term", term, "sbi_stage"):
                frappe.db.set_value("Payment Term", term, "sbi_stage", m["name"])
            days = frappe.utils.date_diff(m["due_date"], today)
            tdet.append({"payment_term": term, "invoice_portion": portion, "due_date_based_on": "Day(s) after invoice date",
                "credit_days": days if days > 0 else 0, "description": pct + "% of milestone work - " + m["name"]})
            o.append("payment_schedule", {"payment_term": term, "due_date": m["due_date"], "invoice_portion": portion,
                "description": pct + "% of milestone work - " + m["name"], "sbi_stage": m["name"], "sbi_ms_percent": pc})
        if non_net > 0:
            rest = round(100 - used, 2)
            if not frappe.db.exists("Payment Term", NON_MS_TERM):
                frappe.get_doc({"doctype": "Payment Term", "payment_term_name": NON_MS_TERM, "invoice_portion": 0,
                    "due_date_based_on": "Day(s) after invoice date", "credit_days": 0,
                    "description": "Lines not in any milestone (MS = No), billed separately"}).insert(ignore_permissions=True)
            tdet.append({"payment_term": NON_MS_TERM, "invoice_portion": rest, "due_date_based_on": "Day(s) after invoice date",
                "credit_days": frappe.utils.date_diff(last_due, today), "description": "Non-milestone lines, billed separately"})
            o.append("payment_schedule", {"payment_term": NON_MS_TERM, "due_date": last_due, "invoice_portion": rest,
                "description": "Non-milestone lines, billed separately"})
        pname = pr.get("project_name") or project
        base = pname[:100] + (" - PO milestones" if KIND == "purchase" else " - milestones")
        tname = base
        k = 2
        while frappe.db.exists("Payment Terms Template", tname) and k < 80:
            tname = base + " " + str(k)
            k = k + 1
        frappe.get_doc({"doctype": "Payment Terms Template", "template_name": tname, "terms": tdet}).insert(ignore_permissions=True)
        o.payment_terms_template = tname
    o.insert(ignore_permissions=True)
    out = {"name": o.name, "doctype": O_DT, "grand_total": o.grand_total, "lines": len(lines), "milestones": len(ms)}
    if KIND == "sales" and not pr.get("sales_order"):
        frappe.db.set_value("Project", project, "sales_order", o.name)
    done = True

if act == "orders":
    if not project:
        frappe.throw("Pick a project.")
    extra = " or name in (select sales_order from `tabProject` where name=%(p)s)" if KIND == "sales" else ""
    olist = sql("select name, " + PARTY + " party, transaction_date, base_grand_total grand_total, base_net_total net, per_billed, status, docstatus from `tab" + O_DT +
        "` where docstatus < 2 and (project=%(p)s" + extra + ") order by creation", pf, as_dict=1)
    has_ms = frappe.get_meta(O_IT).has_field("sbi_ms")
    has_pct = frappe.get_meta("Payment Schedule").has_field("sbi_ms_percent")
    for o in olist:
        o["lines"] = sql("select name, idx, " + ("ifnull(sbi_sl_no, '')" if has_ms else "''") + " sl, description, qty, uom, rate, amount, ifnull(billed_amt, 0) billed, " +
            ("ifnull(sbi_ms, 1)" if has_ms else "1") + " ms from `tab" + O_IT + "` where parent=%s order by idx", o.name, as_dict=1)
        msn = 0.0
        non = 0.0
        for ln in o["lines"]:
            ln["description"] = frappe.utils.strip_html(ln.description or "")[:300]
            if ln.ms is None or frappe.utils.cint(ln.ms) == 1:
                msn = msn + frappe.utils.flt(ln.amount)
            else:
                non = non + frappe.utils.flt(ln.amount)
        o["ms_net"] = msn
        o["non_net"] = non
        share = msn / (msn + non) if (msn + non) else 1
        invs = sql("select name, docstatus, ifnull(sbi_source_payment_terms, '') terms, ifnull(sbi_stage, '') stage, base_grand_total grand_total from `tab" + INV_DT +
            "` where " + SRC + "=%s and docstatus < 2 order by creation", o.name, as_dict=1) if frappe.get_meta(INV_DT).has_field(SRC) else []
        nmi = []
        for x in invs:
            if x.stage == NON_MS_TERM:
                nmi.append(x)
        o["nonms_invoices"] = nmi
        o["terms"] = sql("select name row_name, idx, ifnull(payment_term, '') payment_term, ifnull(sbi_stage, '') stage, due_date, invoice_portion, " +
            ("ifnull(sbi_ms_percent, 0)" if has_pct else "0") + " ms_pct, payment_amount, ifnull(sbi_sales_invoice, '') sales_invoice, ifnull(sbi_received_amount, 0) received, ifnull(description, '') description from `tabPayment Schedule` where parenttype=%s and parent=%s order by idx",
            (O_DT, o.name), as_dict=1)
        for t in o["terms"]:
            t["non_ms"] = 1 if t.payment_term == NON_MS_TERM else 0
            pct = frappe.utils.flt(t.ms_pct)
            if not pct:
                pct = frappe.utils.flt(t.invoice_portion) / share if share else frappe.utils.flt(t.invoice_portion)
            t["pct"] = round(pct, 2)
            t["amount"] = msn * pct / 100.0 if msn else frappe.utils.flt(o.net) * pct / 100.0
            t["invoice"] = ""
            t["draft_invoice"] = ""
            for x in invs:
                if t.row_name and t.row_name in x.terms:
                    if x.docstatus == 1:
                        t["invoice"] = x.name
                    else:
                        t["draft_invoice"] = x.name
            if not t["invoice"] and t.sales_invoice and KIND == "sales":
                t["invoice"] = t.sales_invoice
    out["orders"] = olist
    pcol = "customer" if KIND == "sales" else "supplier"
    out["invoices"] = sql("select name, posting_date, " + pcol + " party, ifnull(sbi_stage, '') stage, base_grand_total grand_total, outstanding_amount, status, docstatus from `tab" + INV_DT +
        "` where project=%(p)s and docstatus < 2 order by posting_date desc, creation desc limit 25", pf, as_dict=1)
    done = True

if act == "ms_bill":
    oname = fd.get("order") or ""
    row = fd.get("row") or ""
    o = frappe.get_doc(O_DT, oname)
    if o.docstatus != 1:
        frappe.throw(O_DT + " " + oname + " is not submitted yet. Open it and click Submit first.")
    prj = o.get("project") or ""
    if not prj and KIND == "sales":
        prj = frappe.db.get_value("Project", {"sales_order": oname}, "name") or ""
    cc = frappe.db.get_value("Project", prj, "cost_center") if prj else ""
    term = None
    for t in o.payment_schedule:
        if t.name == row:
            term = t
    if not term:
        frappe.throw("This milestone is no longer on " + oname + ".")
    if term.payment_term == NON_MS_TERM:
        frappe.throw("This line is for non-milestone items. Use Non-MS bill.")
    have = sql("select name from `tab" + INV_DT + "` where " + SRC + "=%s and docstatus < 2 and sbi_source_payment_terms like %s", (oname, "%" + row + "%"))
    if have:
        out = {"name": have[0][0], "doctype": INV_DT, "existing": 1}
    else:
        msn = 0.0
        tot = 0.0
        msmap = {}
        for it in o.items:
            tot = tot + frappe.utils.flt(it.amount)
            if it.get("sbi_ms") is None or frappe.utils.cint(it.get("sbi_ms")) == 1:
                msn = msn + frappe.utils.flt(it.amount)
                msmap[it.name] = it
        if not msmap:
            frappe.throw("This order has no MS lines to bill.")
        pct = frappe.utils.flt(term.get("sbi_ms_percent"))
        if not pct:
            pct = frappe.utils.flt(term.invoice_portion) * tot / msn if msn else frappe.utils.flt(term.invoice_portion)
        stage = term.get("sbi_stage") or term.description or term.payment_term or ("Milestone " + str(term.idx))
        inv = frappe.call(MAKE_INV, source_name=oname)
        keep = []
        for it in inv.items:
            src = msmap.get(it.get(DETAIL))
            if not src:
                continue
            it.qty = src.qty
            it.rate = round(frappe.utils.flt(src.rate) * pct / 100.0, 2)
            it.price_list_rate = 0
            it.discount_percentage = 0
            it.discount_amount = 0
            it.margin_rate_or_amount = 0
            it.amount = it.qty * it.rate
            it.stock_qty = it.qty * frappe.utils.flt(it.conversion_factor or 1)
            if KIND == "sales":
                it.sbi_project = prj
                it.sbi_stage = stage[:140]
                it.sbi_payment_term = term.payment_term
                it.sbi_invoice_portion = pct
            if it.rate > 0:
                keep.append(it)
        if not keep:
            frappe.throw("Nothing left to bill on this order.")
        inv.set("items", keep)
        inv.sbi_stage = stage[:140]
        inv.set(SRC, oname)
        inv.sbi_source_payment_terms = json.dumps([row])
        if KIND == "sales":
            inv.sbi_milestone_portion = frappe.utils.flt(term.invoice_portion)
        due = str(term.due_date or frappe.utils.nowdate())
        if due < frappe.utils.nowdate():
            due = frappe.utils.nowdate()
        if prj:
            inv.project = prj
        if cc:
            for it in inv.items:
                it.cost_center = cc
            for tx in inv.get("taxes") or []:
                tx.cost_center = cc
        inv.payment_terms_template = None
        inv.set("payment_schedule", [])
        inv.due_date = due
        inv.insert(ignore_permissions=True)
        out = {"name": inv.name, "doctype": INV_DT}
    done = True

if act == "nonms_bill":
    oname = fd.get("order") or ""
    o = frappe.get_doc(O_DT, oname)
    if o.docstatus != 1:
        frappe.throw(O_DT + " " + oname + " is not submitted yet. Open it and click Submit first.")
    prj = o.get("project") or ""
    if not prj and KIND == "sales":
        prj = frappe.db.get_value("Project", {"sales_order": oname}, "name") or ""
    cc = frappe.db.get_value("Project", prj, "cost_center") if prj else ""
    nonset = {}
    for it in o.items:
        if not (it.get("sbi_ms") is None or frappe.utils.cint(it.get("sbi_ms")) == 1):
            nonset[it.name] = 1
    if not nonset:
        frappe.throw("This order has no non-MS lines.")
    have = sql("select name from `tab" + INV_DT + "` where " + SRC + "=%s and docstatus=0 and sbi_stage=%s", (oname, NON_MS_TERM))
    if have:
        out = {"name": have[0][0], "doctype": INV_DT, "existing": 1}
    else:
        inv = frappe.call(MAKE_INV, source_name=oname)
        keep = []
        for it in inv.items:
            if nonset.get(it.get(DETAIL)):
                if KIND == "sales":
                    it.sbi_project = prj
                    it.sbi_stage = NON_MS_TERM
                keep.append(it)
        if not keep:
            frappe.throw("All non-MS lines of this order are already billed.")
        inv.set("items", keep)
        inv.sbi_stage = NON_MS_TERM
        inv.set(SRC, oname)
        if prj:
            inv.project = prj
        if cc:
            for it in inv.items:
                it.cost_center = cc
            for tx in inv.get("taxes") or []:
                tx.cost_center = cc
        inv.payment_terms_template = None
        inv.set("payment_schedule", [])
        inv.due_date = frappe.utils.nowdate()
        inv.insert(ignore_permissions=True)
        out = {"name": inv.name, "doctype": INV_DT}
    done = True

# ================================================================== STAFF (my attendance, my requests, my details) + HR employees / approvals
DEFAULT_PW = "SBI@2026"
MOD_ROLES = {"hr": ["HR User"], "sales": ["Sales User"], "purchase": ["Purchase User"], "projects": ["Projects User"],
    "accounts": ["Accounts User"], "attendance": []}
SELF_FIELDS = ["cell_number", "personal_email", "current_address", "permanent_address", "date_of_birth", "blood_group", "marital_status",
    "person_to_be_contacted", "emergency_phone_number", "relation", "bank_name", "bank_ac_no", "ifsc_code"]
HR_FIELDS = ["employee_number", "first_name", "middle_name", "last_name", "gender", "date_of_birth", "date_of_joining", "company", "designation",
    "department", "cell_number", "personal_email", "company_email", "status", "relieving_date", "reason_for_leaving", "reports_to",
    "current_address", "permanent_address", "blood_group", "marital_status", "person_to_be_contacted", "emergency_phone_number", "relation",
    "bank_name", "bank_ac_no", "ifsc_code", "ctc", "salary_mode"]
EMETA = frappe.get_meta("Employee")
CR_DT = "SBI Employee Change Request"

def_sd = 1
if frappe.get_meta("HR Settings").has_field("sbi_salary_start_day"):
    def_sd = max(1, min(28, frappe.utils.cint(frappe.db.get_single_value("HR Settings", "sbi_salary_start_day")) or 1))
SAL_FROM = ""
SAL_TO = ""
if act in ("me_home", "emp_month"):
    back = frappe.utils.cint(fd.get("back"))
    base = frappe.utils.add_months(frappe.utils.nowdate(), -back)
    if def_sd == 1:
        SAL_FROM = str(frappe.utils.get_first_day(base))
    else:
        if frappe.utils.getdate(base).day < def_sd:
            base = frappe.utils.add_months(base, -1)
        SAL_FROM = str(base)[:8] + ("0" + str(def_sd))[-2:]
    SAL_TO = str(frappe.utils.add_days(frappe.utils.add_months(SAL_FROM, 1), -1))
    if fd.get("from_date") and fd.get("to_date") and act == "emp_month" and fd.get("custom"):
        SAL_FROM = fd.get("from_date")
        SAL_TO = fd.get("to_date")

CK_COLS = "name, log_type, time, latitude, longitude"
ckm = frappe.get_meta("Employee Checkin")
for pair in [["sbi_distance", "distance", "0"], ["sbi_within", "within", "1"], ["sbi_photo", "photo", "''"], ["sbi_address", "address", "''"],
        ["sbi_remarks", "remarks", "''"], ["sbi_accuracy", "accuracy", "0"]]:
    if ckm.has_field(pair[0]):
        CK_COLS = CK_COLS + ", ifnull(" + pair[0] + ", " + pair[2] + ") " + pair[1]

if act in ("me_home", "emp_month"):
    EMPN = ME.name if act == "me_home" and ME else (fd.get("employee") or "")
    if not EMPN:
        frappe.throw("Your login is not linked to an employee. Ask HR to put your login in your Employee record.")
    einfo = frappe.db.get_value("Employee", EMPN, ["name", "employee_name", "employee_number", "designation", "department", "company", "image",
        "cell_number", "date_of_joining", "status", "user_id", "holiday_list"], as_dict=1)
    if not einfo:
        frappe.throw("Employee " + EMPN + " not found.")
    if EMETA.has_field("sbi_face_front"):
        for k in ["sbi_face_front", "sbi_face_left", "sbi_face_right"]:
            einfo[k] = frappe.db.get_value("Employee", EMPN, k) or ""
    inn = ""
    if frappe.get_meta("HR Settings").has_field("sbi_office_in_time"):
        tv = str(frappe.db.get_single_value("HR Settings", "sbi_office_in_time") or "").split(":")
        if tv[0]:
            inn = ("0" + tv[0])[-2:] + ":" + (tv[1] if len(tv) > 1 else "00")[:2]
    grace = frappe.utils.cint(frappe.db.get_single_value("HR Settings", "sbi_late_grace")) if frappe.get_meta("HR Settings").has_field("sbi_late_grace") else 0
    punches = sql("select " + CK_COLS + " from `tabEmployee Checkin` where employee=%s and date(time) between %s and %s order by time", (EMPN, SAL_FROM, SAL_TO), as_dict=1)
    days = {}
    order = []
    for p in punches:
        dkey = str(p.time)[:10]
        if dkey not in days:
            days[dkey] = {"d": dkey, "first_in": "", "last_out": "", "hours": 0.0, "late": 0, "outside": 0, "punches": []}
            order.append(dkey)
        dd = days[dkey]
        t5 = str(p.time)[11:16]
        if p.log_type == "IN" and not dd["first_in"]:
            dd["first_in"] = t5
            if inn and str(p.time)[11:16] > str(frappe.utils.add_to_date(frappe.utils.get_datetime(dkey + " " + inn + ":00"), minutes=grace))[11:16]:
                dd["late"] = 1
        if p.log_type == "OUT":
            dd["last_out"] = t5
        if p.get("within") == 0:
            dd["outside"] = dd["outside"] + 1
        p["t"] = t5
        p["time"] = str(p.time)
        dd["punches"].append(p)
    tot_h = 0.0
    late_n = 0
    for dkey in order:
        dd = days[dkey]
        if dd["first_in"] and dd["last_out"] and dd["last_out"] > dd["first_in"]:
            dd["hours"] = round(frappe.utils.time_diff_in_hours(dkey + " " + dd["last_out"] + ":00", dkey + " " + dd["first_in"] + ":00"), 2)
            tot_h = tot_h + dd["hours"]
        late_n = late_n + dd["late"]
    att = sql("""select attendance_date d, status, ifnull(leave_type, '') leave_type from `tabAttendance` where employee=%s and docstatus=1
        and attendance_date between %s and %s""", (EMPN, SAL_FROM, SAL_TO), as_dict=1)
    for a in att:
        dkey = str(a.d)
        if dkey not in days:
            days[dkey] = {"d": dkey, "first_in": "", "last_out": "", "hours": 0.0, "late": 0, "outside": 0, "punches": []}
            order.append(dkey)
        days[dkey]["att"] = a.status + ((" – " + a.leave_type) if a.leave_type else "")
    hols = []
    hl = einfo.holiday_list or frappe.db.get_value("Company", einfo.company, "default_holiday_list")
    if hl:
        for h in sql("select holiday_date, description from `tabHoliday` where parent=%s and holiday_date between %s and %s", (hl, SAL_FROM, SAL_TO), as_dict=1):
            hols.append({"d": str(h.holiday_date), "description": frappe.utils.strip_html(h.description or "").strip()})
    order.sort()
    order.reverse()
    out["employee"] = einfo
    out["from_date"] = SAL_FROM
    out["to_date"] = SAL_TO
    day_rows = []
    n_present = 0
    for k in order:
        day_rows.append(days[k])
        if days[k]["first_in"] or (days[k].get("att") or "").startswith("Present") or (days[k].get("att") or "").startswith("Work"):
            n_present = n_present + 1
    out["days"] = day_rows
    out["holidays"] = hols
    out["summary"] = {"present": n_present, "hours": round(tot_h, 2), "late": late_n}
    out["leaves"] = sql("""select name, leave_type, from_date, to_date, total_leave_days, status, docstatus, ifnull(description, '') description, posting_date
        from `tabLeave Application` where employee=%s and docstatus < 2 order by from_date desc limit 30""", EMPN, as_dict=1)
    arm = frappe.get_meta("Attendance Request")
    out["att_requests"] = sql("""select name, from_date, to_date, reason, ifnull(explanation, '') explanation, half_day, docstatus""" +
        (", ifnull(sbi_status, '') sbi_status, ifnull(sbi_hr_remarks, '') hr_remarks" if arm.has_field("sbi_status") else ", '' sbi_status, '' hr_remarks") +
        """ from `tabAttendance Request` where employee=%s and docstatus < 2 order by from_date desc limit 30""", EMPN, as_dict=1)
    out["changes"] = sql("select name, status, summary, creation, ifnull(hr_remarks, '') hr_remarks from `tab" + CR_DT +
        "` where employee=%s order by creation desc limit 10", EMPN, as_dict=1) if frappe.db.exists("DocType", CR_DT) else []
    out["slips"] = sql("""select name, start_date, end_date, net_pay, status from `tabSalary Slip` where employee=%s and docstatus=1
        order by start_date desc limit 6""", EMPN, as_dict=1) if frappe.db.exists("DocType", "Salary Slip") else []
    out["leave_types"] = frappe.get_all("Leave Type", pluck="name", order_by="name asc") if frappe.db.exists("DocType", "Leave Type") else []
    reasons = []
    rdf = arm.get_field("reason")
    if rdf and rdf.options:
        for o in rdf.options.split("\n"):
            if o.strip():
                reasons.append(o.strip())
    out["att_reasons"] = reasons
    lb = []
    if frappe.db.exists("DocType", "Leave Allocation"):
        for la in sql("""select leave_type, sum(total_leaves_allocated) alloc from `tabLeave Allocation` where employee=%s and docstatus=1
                and %s between from_date and to_date group by leave_type""", (EMPN, frappe.utils.nowdate()), as_dict=1):
            used = sql("""select ifnull(sum(total_leave_days), 0) from `tabLeave Application` where employee=%s and leave_type=%s and docstatus=1
                and status='Approved' and from_date >= (select min(from_date) from `tabLeave Allocation` where employee=%s and leave_type=%s and docstatus=1
                and %s between from_date and to_date)""", (EMPN, la.leave_type, EMPN, la.leave_type, frappe.utils.nowdate()))[0][0]
            lb.append({"leave_type": la.leave_type, "allocated": frappe.utils.flt(la.alloc), "used": frappe.utils.flt(used),
                "left": frappe.utils.flt(la.alloc) - frappe.utils.flt(used)})
    out["leave_balance"] = lb
    done = True

if act == "me_att_req":
    if not ME:
        frappe.throw("Your login is not linked to an employee.")
    fdt = fd.get("from_date") or ""
    tdt = fd.get("to_date") or fdt
    if not fdt:
        frappe.throw("Choose the date.")
    if tdt < fdt:
        frappe.throw("The To date is before the From date.")
    reason = fd.get("reason") or "On Duty"
    if not (fd.get("explanation") or "").strip():
        frappe.throw("Write a short reason (what work, where).")
    doc = frappe.get_doc({"doctype": "Attendance Request", "employee": ME.name, "company": ME.company, "from_date": fdt, "to_date": tdt,
        "reason": reason, "explanation": (fd.get("explanation") or "")[:1000], "half_day": 1 if fd.get("half_day") in ("1", 1, "true") else 0})
    if doc.half_day:
        doc.half_day_date = fdt
    if frappe.get_meta("Attendance Request").has_field("sbi_status"):
        doc.sbi_status = "Pending"
    doc.insert(ignore_permissions=True)
    out = {"name": doc.name}
    done = True

if act == "me_leave_req":
    if not ME:
        frappe.throw("Your login is not linked to an employee.")
    fdt = fd.get("from_date") or ""
    tdt = fd.get("to_date") or fdt
    if not fdt or not fd.get("leave_type"):
        frappe.throw("Choose the leave type and the date.")
    if tdt < fdt:
        frappe.throw("The To date is before the From date.")
    doc = frappe.get_doc({"doctype": "Leave Application", "employee": ME.name, "company": ME.company, "leave_type": fd.get("leave_type"),
        "from_date": fdt, "to_date": tdt, "description": (fd.get("description") or "")[:1000], "status": "Open",
        "half_day": 1 if fd.get("half_day") in ("1", 1, "true") else 0, "posting_date": frappe.utils.nowdate()})
    if doc.half_day:
        doc.half_day_date = fdt
    appr = frappe.db.get_value("Employee", ME.name, "leave_approver")
    if not appr:
        ha = sql("""select hr.parent from `tabHas Role` hr join `tabUser` u on u.name = hr.parent where hr.parenttype='User'
            and hr.role='HR Manager' and u.enabled=1 and u.name not in ('Administrator', %s) order by u.creation limit 1""", user)
        appr = ha[0][0] if ha else ""
    if appr:
        doc.leave_approver = appr
    doc.insert(ignore_permissions=True)
    out = {"name": doc.name}
    done = True

if act == "me_cancel_req":
    if not ME:
        frappe.throw("Your login is not linked to an employee.")
    kind = fd.get("kind")
    nm = fd.get("name")
    dt_ = "Attendance Request" if kind == "att" else ("Leave Application" if kind == "leave" else CR_DT)
    row = frappe.db.get_value(dt_, nm, ["employee", "docstatus"], as_dict=1)
    if not row or row.employee != ME.name:
        frappe.throw("This request is not yours.")
    if row.docstatus:
        frappe.throw("Already approved or rejected – it cannot be withdrawn.")
    if dt_ == CR_DT and frappe.db.get_value(CR_DT, nm, "status") != "Pending":
        frappe.throw("Already approved or rejected – it cannot be withdrawn.")
    frappe.delete_doc(dt_, nm, ignore_permissions=True)
    out = {"deleted": nm}
    done = True

if act == "me_profile":
    if not ME:
        frappe.throw("Your login is not linked to an employee.")
    flds = []
    fdefs = []
    for f in SELF_FIELDS:
        if EMETA.has_field(f):
            flds.append(f)
            df = EMETA.get_field(f)
            fdefs.append({"fieldname": f, "label": df.label, "fieldtype": df.fieldtype, "options": df.options or ""})
    out["employee"] = frappe.db.get_value("Employee", ME.name, ["name", "employee_name", "employee_number", "image", "designation", "department"] + flds, as_dict=1)
    out["fields"] = fdefs
    out["pending"] = frappe.db.exists(CR_DT, {"employee": ME.name, "status": "Pending"}) if frappe.db.exists("DocType", CR_DT) else None
    done = True

if act == "me_profile_save":
    if not ME:
        frappe.throw("Your login is not linked to an employee.")
    if not frappe.db.exists("DocType", CR_DT):
        frappe.throw("Run the Lite ERP installer again (change requests are not set up).")
    vals = json.loads(fd.get("values") or "{}")
    selfs = []
    for f in SELF_FIELDS:
        if EMETA.has_field(f):
            selfs.append(f)
    cur = frappe.db.get_value("Employee", ME.name, selfs, as_dict=1) or {}
    changes = {}
    for k in vals:
        if k in SELF_FIELDS and EMETA.has_field(k) and str(vals[k] or "").strip() != str(cur.get(k) or "").strip():
            changes[k] = str(vals[k] or "").strip()
    photo = fd.get("photo") or ""
    if not changes and not photo:
        frappe.throw("Nothing was changed.")
    labels = []
    for k in changes:
        labels.append(EMETA.get_field(k).label)
    if photo:
        labels.append("Photo")
    cr = frappe.get_doc({"doctype": CR_DT, "employee": ME.name, "employee_name": ME.employee_name, "status": "Pending",
        "changes": json.dumps(changes), "summary": "Change: " + ", ".join(labels)})
    cr.insert(ignore_permissions=True)
    if photo and "," in photo:
        pf_ = frappe.get_doc({"doctype": "File", "file_name": ME.name + "-photo-request.jpg", "attached_to_doctype": CR_DT, "attached_to_name": cr.name,
            "content": photo.split(",", 1)[1], "decode": True, "is_private": 1})
        pf_.flags.ignore_permissions = True
        pf_.insert(ignore_permissions=True)
        frappe.db.set_value(CR_DT, cr.name, "new_photo", pf_.file_url)
    out = {"name": cr.name}
    done = True

if act == "set_password":
    pw = fd.get("new_password") or ""
    if len(pw) < 8:
        frappe.throw("The new password must have at least 8 letters / numbers.")
    if pw == DEFAULT_PW:
        frappe.throw("Choose a new password, not the default one.")
    hasd = False
    hasa = False
    for ch in pw:
        if ch.isdigit():
            hasd = True
        if ch.isalpha():
            hasa = True
    if not (hasd and hasa):
        frappe.throw("Use letters and numbers in the password (for example Ravi@4521).")
    u = frappe.get_doc("User", user)
    u.new_password = pw
    if u.meta.has_field("sbi_must_change_password"):
        u.sbi_must_change_password = 0
    u.flags.ignore_password_policy = True
    u.save(ignore_permissions=True)
    out = {"changed": 1}
    done = True

# ---------------------------------------------------------------- HR: employees
if act == "emp_list":
    qq = "%" + (fd.get("q") or "") + "%"
    out["employees"] = sql("""select name, employee_name, ifnull(employee_number, '') employee_number, ifnull(designation, '') designation,
        ifnull(department, '') department, status, ifnull(user_id, '') user_id, ifnull(image, '') image, ifnull(cell_number, '') cell_number,
        date_of_joining, company from `tabEmployee` where (employee_name like %s or name like %s or ifnull(employee_number, '') like %s
        or ifnull(cell_number, '') like %s) order by status='Active' desc, employee_name limit 500""", (qq, qq, qq, qq), as_dict=1)
    today = frappe.utils.nowdate()
    tk = {}
    for t in sql("""select employee, min(case when log_type='IN' then time end) first_in, max(case when log_type='OUT' then time end) last_out,
            substring_index(group_concat(log_type order by time desc separator '|'), '|', 1) last_type, count(name) n
            from `tabEmployee Checkin` where date(time)=%s group by employee""", today, as_dict=1):
        tk[t.employee] = t
    lv = {}
    for l in sql("""select employee, leave_type, status from `tabLeave Application` where docstatus < 2 and status in ('Open', 'Approved')
            and %s between from_date and to_date""", today, as_dict=1):
        lv[l.employee] = l
    for l in sql("""select employee, reason from `tabAttendance Request` where docstatus = 1 and %s between from_date and to_date""", today, as_dict=1):
        if l.employee not in lv:
            lv[l.employee] = {"leave_type": l.reason, "status": "Request"}
    inn = ""
    if frappe.get_meta("HR Settings").has_field("sbi_office_in_time"):
        tv = str(frappe.db.get_single_value("HR Settings", "sbi_office_in_time") or "").split(":")
        if tv[0]:
            gr = frappe.utils.cint(frappe.db.get_single_value("HR Settings", "sbi_late_grace"))
            inn = str(frappe.utils.add_to_date(frappe.utils.get_datetime(today + " " + ("0" + tv[0])[-2:] + ":" + (tv[1] if len(tv) > 1 else "00")[:2] + ":00"), minutes=gr))[11:16]
    for e in out["employees"]:
        e["username"] = frappe.db.get_value("User", e.user_id, "username") if e.user_id else ""
        t = tk.get(e.name)
        e["first_in"] = str(t.first_in or "")[11:16] if t else ""
        e["last_out"] = str(t.last_out or "")[11:16] if t else ""
        e["last_type"] = t.last_type if t else ""
        e["late"] = 1 if (inn and e["first_in"] and e["first_in"] > inn) else 0
        e["leave"] = (lv[e.name]["leave_type"] + (" (to approve)" if lv[e.name]["status"] == "Open" else "")) if e.name in lv else ""
    arm = frappe.get_meta("Attendance Request")
    att_pend = sql("select count(*) from `tabAttendance Request` where docstatus=0" + (" and ifnull(sbi_status, '') != 'Rejected'" if arm.has_field("sbi_status") else ""))[0][0]
    out["pending"] = {"att": att_pend, "leave": frappe.db.count("Leave Application", {"docstatus": 0, "status": "Open"}),
        "change": frappe.db.count(CR_DT, {"status": "Pending"}) if frappe.db.exists("DocType", CR_DT) else 0}
    done = True

if act == "emp_get":
    en = fd.get("employee") or ""
    flds = []
    for f in HR_FIELDS:
        if EMETA.has_field(f):
            flds.append(f)
    out["employee"] = frappe.db.get_value("Employee", en, ["name", "employee_name", "image", "user_id"] + flds, as_dict=1) if en else {}
    out["fields"] = flds
    out["companies"] = frappe.get_all("Company", pluck="name")
    out["designations"] = frappe.get_all("Designation", pluck="name", order_by="name asc", limit_page_length=500)
    out["departments"] = frappe.get_all("Department", pluck="name", order_by="name asc", limit_page_length=500)
    out["genders"] = frappe.get_all("Gender", pluck="name")
    out["login"] = {}
    if en and out["employee"] and out["employee"].user_id:
        uid = out["employee"].user_id
        roles = [r[0] for r in sql("select role from `tabHas Role` where parenttype='User' and parent=%s", uid)]
        mods = []
        for m in MOD_ROLES:
            if MOD_ROLES[m] and MOD_ROLES[m][0] in roles:
                mods.append(m)
        out["login"] = {"user": uid, "username": frappe.db.get_value("User", uid, "username") or "", "enabled": frappe.db.get_value("User", uid, "enabled"),
            "modules": mods, "must_change": frappe.db.get_value("User", uid, "sbi_must_change_password") if frappe.get_meta("User").has_field("sbi_must_change_password") else 0}
    done = True

if act == "emp_save":
    v = json.loads(fd.get("values") or "{}")
    en = fd.get("employee") or ""
    if not (v.get("employee_number") or "").strip():
        frappe.throw("Employee ID No. is needed.")
    if not (v.get("first_name") or "").strip():
        frappe.throw("Employee name is needed.")
    for need in [["gender", "Gender"], ["date_of_birth", "Date of birth"], ["date_of_joining", "Date of joining"], ["company", "Company"]]:
        if not v.get(need[0]):
            frappe.throw(need[1] + " is needed.")
    dup = frappe.db.get_value("Employee", {"employee_number": v.get("employee_number").strip(), "name": ["!=", en or "x"]}, "employee_name")
    if dup:
        frappe.throw("Employee ID No. " + v.get("employee_number") + " is already used by " + dup + ".")
    photo = fd.get("photo") or ""
    if not en and not photo:
        frappe.throw("Add the employee photo.")
    if en:
        emp = frappe.get_doc("Employee", en)
    else:
        emp = frappe.new_doc("Employee")
        emp.status = "Active"
    for k in HR_FIELDS:
        if k == "status" and not v.get(k):
            continue
        if k in v and EMETA.has_field(k):
            emp.set(k, v.get(k) if v.get(k) not in ("",) else None)
    emp.employee_number = v.get("employee_number").strip()
    if emp.status == "Left" and not emp.relieving_date:
        frappe.throw("Give the relieving date for an employee who has left.")
    emp.flags.ignore_permissions = True
    if en:
        emp.save(ignore_permissions=True)
    else:
        emp.insert(ignore_permissions=True)
    if photo and "," in photo:
        pf_ = frappe.get_doc({"doctype": "File", "file_name": emp.name + "-photo.jpg", "attached_to_doctype": "Employee", "attached_to_name": emp.name,
            "attached_to_field": "image", "content": photo.split(",", 1)[1], "decode": True, "is_private": 0})
        pf_.flags.ignore_permissions = True
        pf_.insert(ignore_permissions=True)
        frappe.db.set_value("Employee", emp.name, "image", pf_.file_url)
    out = {"employee": emp.name}
    # login with a user id (not an e-mail): default password, must change at first login
    if fd.get("create_login") in ("1", 1, "true"):
        uname = (fd.get("username") or "").strip().lower()
        mods = json.loads(fd.get("modules") or "[]")
        if not uname:
            frappe.throw("Type the user id for the login.")
        for ch in uname:
            if not (ch.isalnum() or ch in "._-"):
                frappe.throw("User id can have only letters, numbers, dot, dash and underscore.")
        if not mods:
            frappe.throw("Choose at least one area this person may use (Sales, Purchase, Projects, HR, Accounts or Attendance only).")
        uid = emp.user_id or frappe.db.get_value("User", {"username": uname}, "name")
        other = frappe.db.get_value("User", {"username": uname}, "name")
        if other and other != uid:
            frappe.throw("User id " + uname + " is already taken.")
        if other and frappe.db.get_value("Employee", {"user_id": other, "name": ["!=", emp.name]}, "name"):
            frappe.throw("User id " + uname + " already belongs to another employee.")
        if uid:
            u = frappe.get_doc("User", uid)
        else:
            u = frappe.new_doc("User")
            u.email = uname + "@staff.shiv-bharat.com"
            u.flags.is_new_doc = True
        u.first_name = emp.first_name
        u.last_name = emp.last_name or ""
        u.username = uname
        u.enabled = 1
        u.user_type = "System User"
        u.send_welcome_email = 0
        if frappe.db.exists("Workspace", "Lite ERP") and u.meta.has_field("default_workspace"):
            u.default_workspace = "Lite ERP"
        if u.flags.is_new_doc or fd.get("reset_password") in ("1", 1, "true"):
            u.new_password = DEFAULT_PW
            if u.meta.has_field("sbi_must_change_password"):
                u.sbi_must_change_password = 1
        want = ["Employee", "SBI Staff"]
        for m in mods:
            for rl in MOD_ROLES.get(m, []):
                if rl not in want:
                    want.append(rl)
        managed = []
        for m in MOD_ROLES:
            for rl in MOD_ROLES[m]:
                managed.append(rl)
        keep = []
        for r in u.get("roles") or []:
            if r.role not in managed or r.role in want:
                keep.append(r.role)
        u.set("roles", [])
        for w in want:
            if w not in keep:
                keep.append(w)
        for rl in keep:
            if frappe.db.exists("Role", rl):
                u.append("roles", {"role": rl})
        u.flags.ignore_password_policy = True
        if u.flags.is_new_doc:
            u.insert(ignore_permissions=True)
        else:
            u.save(ignore_permissions=True)
        if emp.user_id != u.name:
            emp.reload()
            emp.user_id = u.name
            emp.flags.ignore_permissions = True
            emp.save(ignore_permissions=True)
        if frappe.db.exists("DocType", "Notification Settings"):
            if frappe.db.exists("Notification Settings", u.name):
                frappe.db.set_value("Notification Settings", u.name, "enable_email_notifications", 0)
            else:
                frappe.get_doc({"doctype": "Notification Settings", "name": u.name, "enable_email_notifications": 0}).insert(ignore_permissions=True)
        out["login"] = {"user": u.name, "username": uname, "password": DEFAULT_PW if (u.flags.is_new_doc or fd.get("reset_password") in ("1", 1, "true")) else ""}
    elif fd.get("disable_login") in ("1", 1, "true") and emp.user_id:
        frappe.db.set_value("User", emp.user_id, "enabled", 0)
        out["login"] = {"disabled": 1}
    done = True

# ---------------------------------------------------------------- requests to approve (HR / owner)
if act == "req_list":
    arm = frappe.get_meta("Attendance Request")
    xs = ", ifnull(r.sbi_status, '') sbi_status, ifnull(r.sbi_hr_remarks, '') hr_remarks" if arm.has_field("sbi_status") else ", '' sbi_status, '' hr_remarks"
    out["att"] = sql("""select r.name, r.employee, r.employee_name, r.from_date, r.to_date, r.reason, ifnull(r.explanation, '') explanation, r.half_day,
        r.docstatus, r.creation""" + xs + """ from `tabAttendance Request` r where r.docstatus < 2 order by r.docstatus asc, r.creation desc limit 60""", as_dict=1)
    out["leave"] = sql("""select name, employee, employee_name, leave_type, from_date, to_date, total_leave_days, status, docstatus,
        ifnull(description, '') description, creation from `tabLeave Application` where docstatus < 2 order by docstatus asc, (status='Open') desc,
        creation desc limit 60""", as_dict=1)
    out["change"] = sql("select name, employee, employee_name, status, summary, changes, ifnull(new_photo, '') new_photo, creation, ifnull(hr_remarks, '') hr_remarks from `tab" + CR_DT +
        "` order by (status='Pending') desc, creation desc limit 40", as_dict=1) if frappe.db.exists("DocType", CR_DT) else []
    for c in out["change"]:
        lab = []
        ch = json.loads(c.changes or "{}")
        for k in ch:
            df = EMETA.get_field(k)
            lab.append({"label": df.label if df else k, "new": ch[k], "old": str(frappe.db.get_value("Employee", c.employee, k) or "") if df else ""})
        c["items"] = lab
    done = True

if act == "req_action":
    kind = fd.get("kind")
    nm = fd.get("name")
    action = fd.get("do")
    rem = (fd.get("remarks") or "")[:500]
    if action not in ("approve", "reject"):
        frappe.throw("Unknown action.")
    if kind == "att":
        doc = frappe.get_doc("Attendance Request", nm)
        if doc.docstatus != 0:
            frappe.throw("This request is already done.")
        has_st = doc.meta.has_field("sbi_status")
        if action == "approve":
            if has_st:
                doc.sbi_status = "Approved"
                doc.sbi_hr_remarks = rem
            doc.flags.ignore_permissions = True
            doc.submit()
        else:
            if not has_st:
                frappe.throw("Run the Lite ERP installer again to allow rejecting.")
            frappe.db.set_value("Attendance Request", nm, {"sbi_status": "Rejected", "sbi_hr_remarks": rem})
    elif kind == "leave":
        doc = frappe.get_doc("Leave Application", nm)
        if doc.docstatus != 0:
            frappe.throw("This leave is already done.")
        doc.status = "Approved" if action == "approve" else "Rejected"
        if rem:
            doc.description = ((doc.description or "") + "\nHR: " + rem).strip()
        doc.flags.ignore_permissions = True
        doc.submit()
    elif kind == "change":
        cr = frappe.get_doc(CR_DT, nm)
        if cr.status != "Pending":
            frappe.throw("This change is already done.")
        if action == "approve":
            ch = json.loads(cr.changes or "{}")
            for k in ch:
                if k in SELF_FIELDS and EMETA.has_field(k):
                    frappe.db.set_value("Employee", cr.employee, k, ch[k] or None)
            if cr.new_photo:
                frappe.db.set_value("Employee", cr.employee, "image", cr.new_photo)
        frappe.db.set_value(CR_DT, nm, {"status": "Approved" if action == "approve" else "Rejected", "hr_remarks": rem,
            "reviewed_by": user, "reviewed_on": frappe.utils.now_datetime()})
    else:
        frappe.throw("Unknown request type.")
    out = {"ok": 1}
    done = True

if not done:
    frappe.throw("Unknown action: " + str(act))

frappe.response["message"] = out'''

BLOCK_HTML = r'''<div class="lx" id="lx">
  <header class="lx-top">
    <div class="lx-brand"><img id="lx-logo" class="lx-logo hide" alt="Shiv Bharat" title="Back to ERPNext" data-act="desk"><span data-go="home" data-m="home" title="Lite ERP home">Lite ERP</span></div>
    <nav class="lx-menu" id="menu"></nav>
    <select id="company" title="Company"></select>
    <button class="lx-help" id="helpbtn" data-go="help" data-m="help" title="How to use Lite ERP">?</button>
    <button class="lx-burger" id="burger" title="Menu" aria-label="Menu"><span></span><span></span><span></span></button>
  </header>
  <nav class="mnav" id="mnav"></nav>
  <div class="lx-crumbs" id="crumbs"></div>
  <main class="lx-main">
    <div class="lx-view" id="view"></div>
    <div class="lx-frame hide" id="framewrap">
      <iframe id="frame" title="ERPNext form" allow="camera; geolocation"></iframe>
    </div>
  </main>
</div>'''

BLOCK_CSS = r'''.lx, .lx * { box-sizing: border-box; }
.lx { --sb-red: #c8102e; --sb-red-dark: #8f0b20; --sb-red-soft: #fdecee;
  display: flex; flex-direction: column; height: 80vh; min-height: 480px; font-size: 13px; color: var(--text-color);
  background: var(--bg-color, #f7f7f7); border: 1px solid var(--border-color); border-radius: 10px; overflow: hidden; }
/* full screen: fixed beside the desk's icon rail (position set by the script) */
.lx.full { position: fixed; z-index: 40; border: 0; border-radius: 0; height: auto; min-height: 0; }
.hide { display: none !important; }

/* ---------- fixed top menu ---------- */
.lx-top { flex: none; display: flex; flex-wrap: nowrap; align-items: stretch; gap: 4px; background: linear-gradient(90deg, var(--sb-red-dark), var(--sb-red)); color: #fff; padding: 0 12px; height: 48px; position: relative; z-index: 20; box-shadow: 0 2px 6px rgba(143,11,32,.25); }
.lx-brand { flex: none; display: flex; align-items: center; font-weight: 700; font-size: 15px; letter-spacing: .02em; padding-right: 14px; margin-right: 4px; border-right: 1px solid rgba(255,255,255,.25); white-space: nowrap; }
.lx-menu { display: flex; align-items: stretch; flex: 1 1 auto; flex-wrap: nowrap; min-width: 0; }
.m { position: relative; display: flex; flex: none; }
.m-btn { background: none; border: 0; color: rgba(255,255,255,.92); font-size: 13px; font-weight: 500; padding: 0 14px; cursor: pointer; display: flex; align-items: center; gap: 5px; white-space: nowrap; }
.m-btn .car { font-size: 9px; opacity: .7; }
.m:hover .m-btn, .m.open .m-btn, .m.active .m-btn { background: rgba(0,0,0,.18); color: #fff; }
.m.active .m-btn { box-shadow: inset 0 -3px 0 #fff; }
.m-sub { display: none; position: absolute; top: 100%; left: 0; min-width: 220px; background: var(--card-bg, #fff); color: var(--text-color);
  border: 1px solid var(--border-color); border-top: 3px solid var(--sb-red); border-radius: 0 0 8px 8px; box-shadow: 0 8px 24px rgba(0,0,0,.18); padding: 6px 0; }
.m:hover .m-sub, .m.open .m-sub { display: block; }
.m-sub a { display: block; padding: 8px 16px; color: var(--text-color); text-decoration: none; cursor: pointer; white-space: nowrap; }
.m-sub a:hover { background: var(--sb-red-soft); color: var(--sb-red-dark); }
.m-sub a .d { display: block; font-size: 11px; color: var(--text-muted); }
#company { flex: 0 1 240px; min-width: 120px; align-self: center; height: 30px; max-width: 260px; border-radius: 6px; border: 0; padding: 0 8px; font-size: 12px; background: rgba(255,255,255,.16); color: #fff; }
#company option { color: #111; }

/* ---------- breadcrumb ---------- */
.lx-crumbs { flex: none; display: flex; align-items: center; gap: 6px; padding: 8px 14px; background: var(--card-bg, #fff); border-bottom: 1px solid var(--border-color); min-height: 38px; flex-wrap: wrap; }
.lx-crumbs a { color: var(--sb-red); cursor: pointer; text-decoration: none; }
.lx-crumbs .sep { color: var(--text-muted); }
.lx-crumbs b { font-weight: 600; }
.lx-crumbs .right { margin-left: auto; display: flex; gap: 10px; align-items: center; }

/* ---------- content ---------- */
.lx-main { flex: 1; min-height: 0; position: relative; }
.lx-view { position: absolute; inset: 0; overflow: auto; padding: 16px; }
.lx-frame { position: absolute; inset: 0; background: var(--card-bg, #fff); }
.lx-frame iframe { width: 100%; height: 100%; border: 0; display: block; }
h2.t { font-size: 17px; font-weight: 600; margin: 0 0 4px; }
.sub { color: var(--text-muted); margin-bottom: 14px; }
.hint { color: var(--text-muted); padding: 8px 0; }
.warn { color: var(--orange-600, #c2410c); font-size: 12px; margin: 6px 0; }
.neg { color: var(--red-600, #dc2626); }
.muted { color: var(--text-muted); }
.search { width: 100%; max-width: 420px; height: 34px; border: 1px solid var(--border-color); border-radius: 8px; padding: 0 12px; margin-bottom: 14px; background: var(--card-bg); color: var(--text-color); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.card { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 14px; cursor: pointer; transition: border-color .1s, box-shadow .1s; }
.card:hover { border-color: var(--sb-red); box-shadow: 0 2px 10px rgba(0,0,0,.06); }
.card .n { font-weight: 600; font-size: 14px; }
.card .c { color: var(--text-muted); font-size: 12px; margin-top: 2px; }
.card .f { display: flex; justify-content: space-between; margin-top: 8px; font-size: 12px; }
.card .f span { color: var(--text-muted); }
.card.done { opacity: .75; }
.card .acts { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
.pill { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; background: var(--bg-gray, #eee); white-space: nowrap; }
.pill.green { background: var(--bg-green, #dcfce7); color: var(--text-on-green, #166534); }
.pill.orange { background: var(--bg-orange, #ffedd5); color: var(--text-on-orange, #9a3412); }
.pill.red { background: var(--bg-red, #fee2e2); color: var(--text-on-red, #991b1b); }
.pill.blue { background: var(--bg-blue, #dbeafe); color: var(--text-on-blue, #1e40af); }
.box { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px 14px; margin-bottom: 12px; }
.box h3 { font-size: 13px; font-weight: 600; margin: 0 0 8px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; font-weight: 500; color: var(--text-muted); font-size: 11px; border-bottom: 1px solid var(--border-color); padding: 6px; white-space: nowrap; }
td { padding: 7px 6px; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
td.r, th.r { text-align: right; white-space: nowrap; }
tr.click { cursor: pointer; }
tr.click:hover td { background: var(--bg-light-gray, #f6f7f9); }
tr.total td { font-weight: 600; }
tr.off td { color: var(--text-muted); }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 12px; }
.tile { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-radius: 8px; padding: 8px 12px; }
.tile .l { font-size: 11px; color: var(--text-muted); }
.tile .v { font-size: 17px; font-weight: 600; }
.bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 4px 0 12px; }
.bar select, .bar input, .fm input, .fm select, td input, td select {
  height: 30px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 8px; background: var(--card-bg); color: var(--text-color); font-size: 13px; }
td input.q { width: 90px; text-align: right; }
.forms { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 10px; margin-bottom: 12px; }
.fm { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; }
.fm.hl { border-color: var(--sb-red); box-shadow: 0 0 0 2px rgba(200,16,46,.12); }
.fm .t { font-weight: 600; margin-bottom: 8px; }
.fm .g { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.fm .g .full { grid-column: 1 / -1; }
.fm input, .fm select { width: 100%; }
.fm .btn { margin-top: 10px; }
.btn { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--border-color); background: var(--card-bg, #fff); color: var(--text-color);
  border-radius: 6px; padding: 4px 12px; font-size: 12px; cursor: pointer; height: 30px; }
.btn:hover { border-color: var(--text-muted); }
.btn.pri { background: var(--sb-red); color: #fff; border-color: var(--sb-red); }
.btn.pri:hover { background: var(--sb-red-dark); border-color: var(--sb-red-dark); }
.btn.sm { height: 24px; padding: 2px 8px; font-size: 11px; }
.btn[disabled] { opacity: .5; pointer-events: none; }
details summary { cursor: pointer; color: var(--text-muted); margin: 8px 0; }
a { color: var(--sb-red); }
h2.t { color: var(--sb-red-dark); }
@media (max-width: 1180px) {
  .m-btn { padding: 0 9px; font-size: 12px; }
  .lx-brand { font-size: 14px; padding-right: 10px; }
  #company { flex-basis: 170px; }
}
@media (max-width: 900px) {
  .m-btn .car { display: none; }
  .m-btn { padding: 0 7px; }
}
.tile.go { cursor: pointer; }
.tile.go:hover { border-color: var(--sb-red); }
.tile .s { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.tiles.home { grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.qa { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 14px; }
.qa-i { display: inline-flex; align-items: center; padding: 8px 14px; border-radius: 20px; background: var(--sb-red-soft); color: var(--sb-red-dark);
  font-weight: 500; cursor: pointer; text-decoration: none; border: 1px solid rgba(200,16,46,.15); }
.qa-i:hover { background: var(--sb-red); color: #fff; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 1050px) { .two { grid-template-columns: 1fr; } }
.lx-brand { cursor: pointer; }
.lx-logo { height: 36px; max-width: 120px; object-fit: contain; background: #fff; border-radius: 6px; padding: 2px 6px; margin-right: 10px; cursor: pointer; }
.lx-brand span { cursor: pointer; }
.bt { background: var(--card-bg, #fff); border: 1px solid var(--border-color); border-left: 4px solid #f59e0b; border-radius: 8px; margin-bottom: 8px; }
.bt.ok { border-left-color: #16a34a; }
.bt.nb { border-left-color: #9ca3af; }
.bt-h { display: flex; gap: 14px; align-items: flex-start; padding: 10px 12px 6px; }
.bt-d { flex: none; width: 86px; color: var(--text-muted); }
.bt-n { flex: 1; min-width: 0; word-break: break-word; }
.bt-m { flex: none; text-align: right; font-weight: 600; font-size: 14px; }
.bt-m span { display: block; font-size: 10px; font-weight: 400; color: var(--text-muted); }
.bt-m.in { color: #15803d; }
.bt-m.outm { color: var(--sb-red-dark); }
.bt-a { padding: 0 12px 10px 112px; display: flex; flex-direction: column; gap: 6px; }
.bt.ok .bt-a, .bt.nb .bt-a { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 8px; }
.bt-c { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.cand { border: 1px solid #bbf7d0; background: #f0fdf4; border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer; color: var(--text-color); text-align: left; }
.cand:hover { border-color: #16a34a; background: #dcfce7; }
.cand .ex { color: #15803d; font-weight: 600; margin-left: 4px; }
.cand .nx { color: #b45309; margin-left: 4px; }
.bt-f { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.bt-f input, .bt-f select { height: 28px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 8px; font-size: 12px; background: var(--card-bg); color: var(--text-color); }
.bt-f .bk-inv { width: 150px; }
.bt-f .bk-rem { flex: 1; min-width: 200px; }
.sep2 { color: var(--text-muted); font-size: 11px; padding: 0 4px; }
.mapgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
.mapgrid label { display: flex; flex-direction: column; gap: 3px; font-size: 11px; color: var(--text-muted); margin: 0; }
.mapgrid select { height: 30px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 6px; background: var(--card-bg); color: var(--text-color); font-size: 12px; }
@media (max-width: 1500px) { .m-btn { padding: 0 10px; } #company { flex-basis: 200px; } }
@media (max-width: 1320px) { .m-btn { padding: 0 7px; font-size: 12px; } .m-btn .car { display: none; } .lx-logo { height: 30px; } #company { flex-basis: 160px; } }
@media (max-width: 900px) { .bt-a { padding-left: 12px; } .bt-h { flex-wrap: wrap; } }

/* =================================================================== polish */
.ic { width: 16px; height: 16px; vertical-align: -3px; flex: none; }
.lx { --tone-blue: #2563eb; --tone-green: #16a34a; --tone-amber: #d97706; --tone-red: #c8102e; --tone-violet: #7c3aed; --tone-teal: #0d9488;
  --sb-red-txt: #b40e29; --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08); }
.lx-view { padding: 18px 22px 40px; }
.m-btn { gap: 6px; }
.m-btn .mi { width: 15px; height: 15px; opacity: .9; }
.lx-crumbs { font-size: 12.5px; }
h2.t { display: flex; align-items: center; gap: 10px; color: var(--text-color); font-size: 18px; font-weight: 700; margin: 0 0 4px; letter-spacing: -.01em; }
h2.t .ti { display: inline-flex; width: 32px; height: 32px; border-radius: 9px; align-items: center; justify-content: center;
  background: var(--sb-red-soft); color: var(--sb-red); }
h2.t .ti .ic { width: 18px; height: 18px; }
.sub { margin-left: 42px; }
a { color: var(--sb-red-txt); }

/* home banner */
.hero { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; padding: 20px 24px; margin-bottom: 16px;
  border-radius: 14px; color: #fff; background: radial-gradient(circle at 85% -20%, rgba(255,255,255,.18), transparent 45%), linear-gradient(115deg, #7a0a1c, #c8102e 60%, #e0344f);
  box-shadow: 0 6px 20px rgba(143,11,32,.25); }
.hero-hi { font-size: 22px; font-weight: 700; letter-spacing: -.01em; }
.hero-sub { opacity: .85; margin-top: 2px; }
.hero-acts { display: flex; gap: 8px; flex-wrap: wrap; }
.hero-btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px; border-radius: 999px; background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.3); color: #fff !important; text-decoration: none; cursor: pointer; font-weight: 500; backdrop-filter: blur(2px); }
.hero-btn:hover { background: rgba(255,255,255,.26); }
.hero-btn.warnb { background: #fff; color: #9a3412 !important; border-color: #fff; animation: lxpulse 2s ease-in-out infinite; }
@keyframes lxpulse { 50% { box-shadow: 0 0 0 5px rgba(255,255,255,.25); } }

/* tiles */
.tile { border-radius: 12px; padding: 12px 14px; box-shadow: var(--shadow); transition: transform .12s, box-shadow .12s, border-color .12s; }
.tile .v { font-size: 19px; font-weight: 700; letter-spacing: -.01em; margin-top: 1px; }
.tile.go:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(16,24,40,.1); }
.tile[class*="ti-"] { display: flex; gap: 12px; align-items: flex-start; }
.tic { flex: none; width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }
.tic .ic { width: 19px; height: 19px; }
.tbody { min-width: 0; }
.ti-blue .tic { background: rgba(37,99,235,.12); color: var(--tone-blue); }
.ti-green .tic { background: rgba(22,163,74,.12); color: var(--tone-green); }
.ti-amber .tic { background: rgba(217,119,6,.13); color: var(--tone-amber); }
.ti-red .tic { background: rgba(200,16,46,.11); color: var(--tone-red); }
.ti-violet .tic { background: rgba(124,58,237,.12); color: var(--tone-violet); }
.ti-teal .tic { background: rgba(13,148,136,.12); color: var(--tone-teal); }
.tiles:not(.home) .tile { border-top: 3px solid transparent; }
.tiles:not(.home) .tile:nth-child(6n+1) { border-top-color: var(--tone-red); }
.tiles:not(.home) .tile:nth-child(6n+2) { border-top-color: var(--tone-blue); }
.tiles:not(.home) .tile:nth-child(6n+3) { border-top-color: var(--tone-green); }
.tiles:not(.home) .tile:nth-child(6n+4) { border-top-color: var(--tone-amber); }
.tiles:not(.home) .tile:nth-child(6n+5) { border-top-color: var(--tone-violet); }
.tiles:not(.home) .tile:nth-child(6n+6) { border-top-color: var(--tone-teal); }

/* boxes, cards, tables */
.box { border-radius: 12px; box-shadow: var(--shadow); padding: 14px 16px; }
.box h3 { align-items: center; font-size: 13.5px; }
.box h3 .ic { color: var(--sb-red); }
.card { border-radius: 12px; box-shadow: var(--shadow); transition: transform .12s, box-shadow .12s, border-color .12s; }
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(16,24,40,.1); }
.card .f.small { font-size: 11px; margin-top: 4px; }
.card.ms { border-top: 3px solid var(--tone-blue); }
.card.ms-draft { border-top-color: var(--tone-amber); }
.card.ms-done { border-top-color: var(--tone-green); }
th { text-transform: uppercase; letter-spacing: .04em; font-size: 10.5px; }
tbody tr:hover td { background: rgba(127,127,127,.06); }
.qa-i { background: rgba(200,16,46,.07); color: var(--sb-red-txt); border-color: rgba(200,16,46,.18); }

/* progress */
.prog { height: 6px; border-radius: 99px; background: rgba(127,127,127,.18); overflow: hidden; margin-top: 8px; }
.prog > div { height: 100%; border-radius: 99px; background: linear-gradient(90deg, #e0344f, #c8102e); }
.prog.over > div { background: linear-gradient(90deg, #f59e0b, #ea580c); }
.prog.thin { height: 4px; margin-top: 4px; min-width: 70px; margin-left: auto; }

/* charts */
.chart { width: 100%; height: auto; display: block; }
.chart .gl { stroke: var(--border-color); stroke-width: 1; }
.chart .ax { fill: var(--text-muted); font-size: 11px; }
.chart rect:hover { opacity: .8; }
.legend { display: flex; gap: 16px; justify-content: center; font-size: 12px; color: var(--text-muted); margin-top: 4px; }
.legend i, .age-l i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 5px; vertical-align: -1px; }
.age { padding: 8px 0 14px; cursor: pointer; }
.age + .age { border-top: 1px solid var(--border-color); padding-top: 14px; }
.age-h { display: flex; justify-content: space-between; margin-bottom: 8px; }
.age-h span { font-weight: 700; font-size: 16px; }
.age-bar { display: flex; height: 14px; border-radius: 99px; overflow: hidden; background: rgba(127,127,127,.14); gap: 2px; }
.age-empty { font-size: 11px; color: var(--text-muted); padding-left: 8px; line-height: 14px; }
.age-l { display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 8px; font-size: 11.5px; color: var(--text-muted); }
.age-l b { color: var(--text-color); font-weight: 600; }

/* upload */
.upgrid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 12px; margin-bottom: 12px; }
@media (max-width: 1000px) { .upgrid { grid-template-columns: 1fr; } }
.drop { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; text-align: center; min-height: 170px;
  border: 2px dashed rgba(200,16,46,.35); border-radius: 14px; background: rgba(200,16,46,.03); cursor: pointer; color: var(--text-color); margin: 0; transition: background .12s, border-color .12s; }
.drop:hover, .drop.over { background: rgba(200,16,46,.08); border-color: var(--sb-red); }
.drop .ic { width: 34px; height: 34px; color: var(--sb-red); }
.drop b { font-size: 15px; }
.drop span { color: var(--text-muted); font-size: 12px; }
.drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.howto ol { margin: 4px 0 12px; padding-left: 18px; color: var(--text-muted); line-height: 1.6; }
.howto ol b { color: var(--text-color); }

/* loading shimmer */
.skel { padding: 4px 0; }
.sk { border-radius: 10px; background: linear-gradient(90deg, rgba(127,127,127,.10) 25%, rgba(127,127,127,.20) 37%, rgba(127,127,127,.10) 63%);
  background-size: 400% 100%; animation: lxshim 1.3s ease infinite; margin-bottom: 12px; }
.sk-t { height: 24px; width: 260px; } .sk-s { height: 12px; width: 420px; }
.sk-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; } .sk-c { height: 82px; }
.sk-b { height: 170px; } .sk-b.short { height: 90px; width: 70%; }
@keyframes lxshim { 0% { background-position: 100% 50%; } 100% { background-position: 0 50%; } }

/* dark theme (follows the desk's theme) */
.lx.dark { --sb-red-soft: rgba(239,68,68,.16); --sb-red-txt: #f87171; --shadow: 0 1px 2px rgba(0,0,0,.4); }
.lx.dark h2.t .ti { color: #f87171; }
.lx.dark .box h3 .ic, .lx.dark .drop .ic { color: #f87171; }
.lx.dark .neg { color: #f87171; }
.lx.dark .warn { color: #fb923c; }
.lx.dark .lx-crumbs a, .lx.dark a { color: #f87171; }
.lx.dark .m-sub a:hover { color: #fecaca; background: rgba(239,68,68,.14); }
.lx.dark .bt-m.in { color: #4ade80; }
.lx.dark .bt-m.outm { color: #f87171; }
.lx.dark .cand { background: rgba(22,163,74,.12); border-color: rgba(74,222,128,.35); }
.lx.dark .cand .ex { color: #4ade80; } .lx.dark .cand .nx { color: #fbbf24; }
.lx.dark .qa-i { background: rgba(239,68,68,.12); color: #fca5a5; border-color: rgba(239,68,68,.3); }
.lx.dark .qa-i:hover { background: #c8102e; color: #fff; }
.lx.dark .card:hover, .lx.dark .tile.go:hover { box-shadow: 0 8px 20px rgba(0,0,0,.45); }
.lx.dark .hero-btn.warnb { color: #9a3412 !important; }
@media (max-width: 1320px) { .m-btn .mi { display: none; } }

/* BOQ editor */
.boqbox { padding: 6px 8px 12px; overflow-x: auto; }
.boqg td { padding: 3px 4px; }
.boqg .bg { width: 100%; height: 30px; border: 1px solid transparent; border-radius: 6px; padding: 0 7px; background: transparent; color: var(--text-color); font-size: 13px; }
.boqg .bg:hover { border-color: var(--border-color); }
.boqg .bg:focus { outline: none; border-color: var(--sb-red); background: var(--card-bg); box-shadow: 0 0 0 2px rgba(200,16,46,.12); }
.boqg .bg.r { text-align: right; }
.boqg select.bg { border-color: var(--border-color); font-weight: 500; }
.boqg select.ty-blue { color: var(--tone-blue); } .boqg select.ty-green { color: var(--tone-green); } .boqg select.ty-amber { color: var(--tone-amber); }
.boqg select.ty-teal { color: var(--tone-teal); } .boqg select.ty-violet { color: var(--tone-violet); } .boqg select.ty-red { color: var(--tone-red); }
.boqg td.amt { color: var(--text-muted); font-variant-numeric: tabular-nums; }
.xbtn { border: 0; background: none; color: var(--text-muted); font-size: 18px; line-height: 1; cursor: pointer; border-radius: 6px; width: 26px; height: 26px; }
.xbtn:hover { background: rgba(200,16,46,.1); color: var(--sb-red); }
.tiles.boqt { grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
.tiles.boqt .tile[class*="ti-"] { display: block; border-top: 3px solid transparent; }
.tiles.boqt .ti-blue { border-top-color: var(--tone-blue); } .tiles.boqt .ti-green { border-top-color: var(--tone-green); }
.tiles.boqt .ti-amber { border-top-color: var(--tone-amber); } .tiles.boqt .ti-teal { border-top-color: var(--tone-teal); }
.tiles.boqt .ti-violet { border-top-color: var(--tone-violet); } .tiles.boqt .ti-red { border-top-color: var(--tone-red); }
.card.newstage { cursor: default; display: flex; flex-direction: column; gap: 8px; border-style: dashed; }
.card.newstage:hover { transform: none; }
.card.newstage select, .card.newstage input { height: 30px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 8px; background: var(--card-bg); color: var(--text-color); font-size: 12px; }
label.btn { margin: 0; }

.lx-brand span { padding: 4px 10px; border-radius: 8px; transition: background .12s; }
.lx-brand span:hover, .lx-brand span.on { background: rgba(0,0,0,.18); }
.lx-brand span.on { box-shadow: inset 0 -3px 0 #fff; }

/* help */
.lx-help { flex: none; align-self: center; width: 30px; height: 30px; margin-left: 8px; border-radius: 50%; border: 1px solid rgba(255,255,255,.4);
  background: rgba(255,255,255,.12); color: #fff; font-weight: 700; cursor: pointer; }
.lx-help:hover, .lx-help.on { background: #fff; color: var(--sb-red); }
.help-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 12px; }
.box.help h3 { gap: 8px; }
.box.help h3 .ti { display: inline-flex; width: 26px; height: 26px; border-radius: 7px; align-items: center; justify-content: center; background: var(--sb-red-soft); }
.box.help ul, .help-daily ol { margin: 4px 0 10px; padding-left: 18px; color: var(--text-muted); line-height: 1.6; }
.box.help li, .help-daily li { margin-bottom: 4px; }
.help-daily { border-left: 4px solid var(--sb-red); }
.help-daily b { color: var(--text-color); }

/* phone menu */
.lx-burger { display: none; flex: none; align-self: center; width: 36px; height: 32px; margin-left: 6px; border: 0; border-radius: 6px;
  background: rgba(255,255,255,.14); cursor: pointer; flex-direction: column; justify-content: center; align-items: center; gap: 4px; }
.lx-burger span { display: block; width: 18px; height: 2px; background: #fff; border-radius: 2px; }
.mnav { display: none; position: absolute; top: 48px; left: 0; right: 0; max-height: calc(100% - 48px); overflow: auto; z-index: 30;
  background: var(--card-bg, #fff); border-bottom: 3px solid var(--sb-red); box-shadow: 0 12px 30px rgba(0,0,0,.25); padding: 6px 0 10px; }
.lx { position: relative; }
.lx.full { position: fixed; }
.lx.mn-open .mnav { display: block; }
.mnav a { display: block; padding: 9px 18px 9px 42px; color: var(--text-color); text-decoration: none; cursor: pointer; }
.mnav a:hover { background: var(--sb-red-soft); }
.mnav .mn-home { padding-left: 18px; font-weight: 600; display: flex; align-items: center; gap: 10px; }
.mn-sec { border-top: 1px solid var(--border-color); padding-top: 4px; margin-top: 4px; }
.mn-h { display: flex; align-items: center; gap: 10px; padding: 8px 18px 4px; font-weight: 600; color: var(--sb-red); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.lx.dark .mn-h { color: #f87171; }
@media (max-width: 860px) {
  .lx-menu { display: none; }
  .lx-burger { display: flex; }
  .lx-top { justify-content: space-between; }
  .lx-brand { border-right: 0; flex: 1; }
  .lx-logo { height: 28px; }
  #company { flex: 0 1 140px; min-width: 90px; font-size: 11px; }
  .lx-view { padding: 12px; }
  .sub { margin-left: 0; }
  .tiles, .tiles.home { grid-template-columns: repeat(2, 1fr); }
  .two, .forms, .upgrid, .help-grid { grid-template-columns: 1fr; }
  .hero { padding: 16px; } .hero-hi { font-size: 18px; }
  .box { overflow-x: auto; }
  .sk-row { grid-template-columns: repeat(2, 1fr); }
}
.lx.dark .mnav a { color: var(--text-color); }
.lx.dark .mnav a:hover { color: #fecaca; }

/* ---------- help: dropdown link, screen pill, drawer, help center */
.m-sub a.m-help { margin-top: 4px; border-top: 1px solid var(--border-color); color: var(--sb-red-txt); font-weight: 500; display: flex; align-items: center; gap: 8px; }
.m-sub a.m-help .ic { width: 15px; height: 15px; }
.hpill { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 99px; background: var(--sb-red-soft); color: var(--sb-red-txt) !important; font-weight: 500; cursor: pointer; }
.hpill:hover { background: var(--sb-red); color: #fff !important; }
.hpill .ic { width: 14px; height: 14px; }
.mn-q { margin-left: auto; width: 22px; height: 22px; border-radius: 50%; display: inline-flex !important; align-items: center; justify-content: center; padding: 0 !important;
  background: var(--sb-red-soft); color: var(--sb-red-txt) !important; font-weight: 700; }

.hshade { position: absolute; inset: 0; background: rgba(15,15,20,.35); opacity: 0; pointer-events: none; transition: opacity .2s; z-index: 40; }
.hdrawer { position: absolute; top: 0; right: 0; bottom: 0; width: min(440px, 92%); background: var(--card-bg, #fff); z-index: 41; transform: translateX(105%);
  transition: transform .25s ease; box-shadow: -12px 0 32px rgba(0,0,0,.25); display: flex; flex-direction: column; }
.lx.hd-open .hshade { opacity: 1; pointer-events: auto; }
.lx.hd-open .hdrawer { transform: none; }
.hd-head { display: flex; gap: 12px; align-items: center; padding: 18px 18px 16px; color: #fff; background-image: linear-gradient(135deg, rgba(255,255,255,.18), transparent 60%) !important; }
.hd-head .hc-ic { background: rgba(255,255,255,.2) !important; }
.hd-t { font-size: 17px; font-weight: 700; } .hd-w { opacity: .85; font-size: 12px; }
.hd-x { margin-left: auto; border: 0; background: rgba(255,255,255,.18); color: #fff; width: 30px; height: 30px; border-radius: 50%; font-size: 20px; line-height: 1; cursor: pointer; }
.hd-body { padding: 16px 18px 24px; overflow: auto; }
.hd-all { display: inline-block; margin-top: 12px; font-size: 12px; cursor: pointer; }

.hc-ic { flex: none; width: 40px; height: 40px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; color: #fff; }
.hc-ic .ic { width: 20px; height: 20px; }
.hc-i { color: var(--text-muted); margin: 2px 0 12px; }
.hsteps { list-style: none; margin: 0 0 12px; padding: 0; position: relative; }
.hsteps li { display: flex; gap: 12px; position: relative; padding-bottom: 14px; }
.hsteps li:not(:last-child)::before { content: ""; position: absolute; left: 13px; top: 28px; bottom: 0; width: 2px; background: var(--border-color); }
.hn { flex: none; width: 28px; height: 28px; border-radius: 50%; color: #fff; font-weight: 700; font-size: 13px; display: inline-flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 6px rgba(0,0,0,.18); position: relative; z-index: 1; }
.hsteps b { display: block; margin-top: 4px; }
.hsteps p { margin: 2px 0 0; color: var(--text-muted); line-height: 1.5; font-size: 12.5px; }
.htips { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.htips div { display: flex; gap: 8px; align-items: flex-start; padding: 8px 10px; border-radius: 8px; background: rgba(234,179,8,.10); border: 1px solid rgba(234,179,8,.28); font-size: 12px; }
.htips .ic { color: #ca8a04; margin-top: 1px; }

.hhero { display: flex; justify-content: space-between; align-items: center; gap: 18px; flex-wrap: wrap; padding: 22px 24px; border-radius: 14px; margin-bottom: 14px; color: #fff;
  background: radial-gradient(circle at 90% -30%, rgba(255,255,255,.2), transparent 45%), linear-gradient(115deg, #7a0a1c, #c8102e 60%, #e0344f); box-shadow: 0 6px 20px rgba(143,11,32,.25); }
.hh-t { font-size: 22px; font-weight: 700; display: flex; align-items: center; gap: 10px; } .hh-t .ic { width: 24px; height: 24px; }
.hh-s { opacity: .88; margin-top: 4px; max-width: 640px; }
.hsearch { flex: 0 1 380px; height: 40px; border-radius: 99px; border: 0; padding: 0 18px; font-size: 14px; color: #1f272e; box-shadow: 0 4px 14px rgba(0,0,0,.15); }
.hday { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 14px 16px; margin-bottom: 14px; box-shadow: var(--shadow); }
.hday-t { font-weight: 700; display: flex; align-items: center; gap: 8px; margin-bottom: 10px; } .hday-t .ic { color: var(--sb-red); }
.hday-g { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 8px; }
.hday-g a { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-radius: 10px; background: rgba(200,16,46,.06); border: 1px solid rgba(200,16,46,.14);
  color: var(--text-color) !important; text-decoration: none; cursor: pointer; font-weight: 500; }
.hday-g a:hover { border-color: var(--sb-red); }
.hday-g span { flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--sb-red); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
.hgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 14px; }
.hcard { background: var(--card-bg); border: 1px solid var(--border-color); border-top: 4px solid var(--hc); border-radius: 12px; padding: 16px; box-shadow: var(--shadow); }
.hcard.focus { box-shadow: 0 0 0 3px color-mix(in srgb, var(--hc) 35%, transparent), var(--shadow); }
.hc-top { display: flex; gap: 12px; align-items: center; margin-bottom: 6px; }
.hc-t { font-size: 16px; font-weight: 700; } .hc-w { color: var(--text-muted); font-size: 12px; }
@media (max-width: 860px) { .hgrid { grid-template-columns: 1fr; } .hsearch { flex-basis: 100%; } }

/* help for first-time users */
.hstart { background: var(--card-bg); border: 1px solid var(--border-color); border-left: 5px solid var(--sb-red); border-radius: 12px; padding: 16px 18px; margin-bottom: 14px; box-shadow: var(--shadow); }
.hs-t { font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 8px; } .hs-t .ic { color: var(--sb-red); width: 18px; height: 18px; }
.hstart p { margin: 8px 0 12px; line-height: 1.65; font-size: 14px; }
.hs-rules { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
.hs-rules div { display: flex; gap: 10px; align-items: flex-start; padding: 10px 12px; border-radius: 10px; background: rgba(127,127,127,.07); line-height: 1.5; font-size: 13px; }
.hs-rules span { flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--sb-red); color: #fff; display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
.hs-rules b { display: block; }
.hcard .hc-i { font-size: 13.5px; line-height: 1.55; color: var(--text-color); }
.hsteps p { font-size: 13px; }
.hex { border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; background: rgba(22,163,74,.08); border: 1px solid rgba(22,163,74,.25); }
.hex p { margin: 4px 0 0; line-height: 1.55; font-size: 13px; }
.hex-t { font-weight: 700; font-size: 12px; display: flex; align-items: center; gap: 6px; text-transform: uppercase; letter-spacing: .04em; }
.hex .hex-t { color: #15803d; }
.hwords { border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; background: rgba(37,99,235,.06); border: 1px solid rgba(37,99,235,.2); }
.hwords .hex-t { color: var(--tone-blue); margin-bottom: 4px; }
.hwords div:not(.hex-t) { font-size: 12.5px; line-height: 1.5; padding: 3px 0; }
.hwords b { margin-right: 6px; }
.hwords span, .hg-i span { color: var(--text-muted); }
.hgloss { margin-top: 14px; }
.hg-g { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 8px 18px; }
.hg-i { padding: 8px 0; border-bottom: 1px dashed var(--border-color); line-height: 1.5; }
.hg-i b { display: block; color: var(--text-color); }
.lx.dark .hex .hex-t { color: #4ade80; } .lx.dark .hwords .hex-t { color: #93c5fd; }
.hs-rules p { margin: 0; } .hs-rules p b { display: block; margin-bottom: 2px; }
.chart-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; min-height: 200px; text-align: center; color: var(--text-muted); line-height: 1.5; }
.chart-empty .ic { width: 34px; height: 34px; opacity: .5; }

/* create milestones */
.btn.big { height: 38px; padding: 6px 18px; font-size: 14px; }
.btn.ghost { background: transparent; border-color: transparent; color: var(--text-muted); }
.btn.ghost:hover { color: var(--sb-red); }
.bar.c { justify-content: center; }
.small { font-size: 11.5px; margin-top: 6px; }
.msempty { text-align: center; padding: 26px 16px; background: linear-gradient(180deg, rgba(200,16,46,.05), transparent); }
.msempty .ico, .mswait .ico { font-size: 34px; line-height: 1; }
.msempty h3 { display: block; text-align: center; margin: 8px 0 4px; }
.msempty .bar { margin-top: 14px; gap: 10px; }
.mswait { display: flex; align-items: center; gap: 14px; border-left: 4px solid #f59e0b; }
.mswait > div:nth-child(2) { flex: 1; }
.msform { display: grid; grid-template-columns: minmax(280px, 1fr) minmax(420px, 1.6fr); gap: 12px; margin-bottom: 12px; }
.msform label { display: flex; flex-direction: column; gap: 3px; font-size: 11.5px; color: var(--text-muted); }
.msform .num { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--sb-red); color: #fff; font-size: 12px; margin-right: 6px; }
.presets { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
.mst { width: 100%; }
.mst td input { width: 100%; }
.mst td input.q { max-width: 90px; text-align: right; }
.mst td:first-child { color: var(--text-muted); width: 24px; }
.mstot { margin-left: auto; font-weight: 600; padding: 4px 10px; border-radius: 999px; }
.mstot.ok { background: rgba(22,163,74,.12); color: #15803d; }
.mstot.bad { background: rgba(200,16,46,.10); color: var(--sb-red); }
@media (max-width: 860px) { .msform { grid-template-columns: 1fr; } .mswait { flex-wrap: wrap; } }

.presets.imps { padding: 8px; border-radius: 8px; background: rgba(200,16,46,.05); border: 1px dashed rgba(200,16,46,.3); }
.btn.imp.on { border-color: var(--sb-red); color: var(--sb-red); box-shadow: 0 0 0 2px rgba(200,16,46,.12); }
.btn.imp .pill { margin-left: 4px; font-size: 10px; padding: 0 6px; }

/* orders: lines + MS */
.seg { display: inline-flex; border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; margin-right: auto; }
.seg a { padding: 6px 12px; cursor: pointer; font-size: 12.5px; color: var(--text-muted); }
.seg a.on { background: var(--sb-red); color: #fff; }
.chips { display: flex; gap: 6px; margin: -2px 0 8px; flex-wrap: wrap; }
.chip { font-size: 11.5px; padding: 2px 9px; border-radius: 999px; background: rgba(0,0,0,.05); }
.chip.ms { background: rgba(37,99,235,.10); color: #1d4ed8; }
.chip.non { background: rgba(217,119,6,.12); color: #b45309; }
.lx.dark .chip.ms { color: #93c5fd; } .lx.dark .chip.non { color: #fcd34d; }
.otot { margin-left: auto; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.fm .g.g4 { grid-template-columns: repeat(4, 1fr); }
.fm .g label, .fm label { display: flex; flex-direction: column; gap: 3px; font-size: 11.5px; color: var(--text-muted); }
.fm + .fm { margin-top: 12px; }
.fm .num { display: inline-grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: var(--sb-red); color: #fff; font-size: 12px; margin-right: 6px; }
.olt { width: 100%; }
.olt td input, .olt td select { width: 100%; }
.olt td input.sl { width: 56px; }
.olt td input.q { max-width: 110px; text-align: right; }
.olt td:nth-child(2) { min-width: 260px; }
.olt td .msel { width: 64px; font-weight: 600; }
.olt tr.nonms td { background: rgba(217,119,6,.06); }
.olt tr.nonms .msel { color: #b45309; }
#ms-box.dim { opacity: .45; }
#ms-box.dim::after { content: "No MS = Yes lines, so no milestones are needed."; display: block; font-size: 12px; margin-top: 6px; }
@media (max-width: 860px) { .fm .g.g4 { grid-template-columns: 1fr 1fr; } .olt { display: block; overflow-x: auto; } }

/* HR period bar + office punches */
.hrbar { flex-wrap: wrap; gap: 8px; align-items: center; }
.hrbar .seg { margin-right: 0; }
.hrbar > a.muted { margin-left: auto; cursor: pointer; }
.hrbar input[type=date] { height: 32px; }
img.thumb { width: 46px; height: 34px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color); vertical-align: middle; }

.fm label.chk { flex-direction: row; align-items: center; gap: 8px; margin-top: 10px; font-size: 13px; color: var(--text-color); }
.fm label.chk input { width: auto; }

/* ---------- My work / HR employees */
.av { width: 34px; height: 34px; border-radius: 50%; object-fit: cover; display: inline-grid; place-items: center; flex: none;
  background: rgba(200,16,46,.10); color: var(--sb-red); font-weight: 700; font-size: 14px; border: 1px solid var(--border-color); }
.av.big { width: 72px; height: 72px; font-size: 26px; }
.av.big .ic { width: 26px; height: 26px; }
.emp-head { display: flex; align-items: center; gap: 14px; margin-bottom: 10px; flex-wrap: wrap; }
.emp-head h2.t { margin: 0; }
.emp-mon { margin-left: auto; display: flex; align-items: center; gap: 8px; }
.emp-cell { display: flex; align-items: center; gap: 10px; }
.ph-pick { display: flex; flex-direction: column; align-items: center; gap: 4px; cursor: pointer; }
.faces { display: flex; gap: 10px; flex-wrap: wrap; }
.faces img { width: 110px; height: 110px; object-fit: cover; border-radius: 10px; border: 1px solid var(--border-color); }
.mpun td { background: var(--bg-light-gray, #f6f7f9); }
.pun { display: flex; gap: 12px; align-items: flex-start; padding: 8px 0; border-bottom: 1px dashed var(--border-color); }
.pun:last-child { border-bottom: 0; }
.pun img { width: 96px; height: 96px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border-color); }
.nophoto { width: 96px; height: 96px; display: grid; place-items: center; border-radius: 8px; border: 1px dashed var(--border-color); color: var(--text-muted); font-size: 11px; flex: none; }
.opts { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; margin-bottom: 10px; }
.opt { display: flex !important; flex-direction: column; gap: 2px; padding: 9px 10px 9px 32px !important; border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer;
  position: relative; color: var(--text-color) !important; font-size: 12.5px !important; }
.opt input { position: absolute; left: 10px; top: 11px; width: auto !important; height: auto !important; }
.opt span { color: var(--text-muted); font-size: 11.5px; }
.opt:has(input:checked) { border-color: var(--sb-red); box-shadow: 0 0 0 2px rgba(200,16,46,.12); }
.fm .g.g3 { grid-template-columns: repeat(3, 1fr); }
.fm textarea { width: 100%; border: 1px solid var(--border-color); border-radius: 6px; padding: 6px 8px; background: var(--card-bg); color: var(--text-color); font: inherit; font-size: 13px; }
.req-act { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
.req-act input { height: 28px; min-width: 150px; border: 1px solid var(--border-color); border-radius: 6px; padding: 0 8px; background: var(--card-bg); color: var(--text-color); }
.pw-cover { position: absolute; inset: 0; z-index: 50; background: var(--bg-color, #f7f7f7); display: grid; place-items: center; padding: 16px; overflow: auto; }
.pw-box { width: 100%; max-width: 420px; }
.pw-box .fm label { margin-bottom: 8px; }
@media (max-width: 860px) { .fm .g.g3 { grid-template-columns: 1fr; } .emp-mon { margin-left: 0; } .pun img, .nophoto { width: 72px; height: 72px; } }
a.btn, a.btn:hover { text-decoration: none !important; }
.emp-head .sub { padding-left: 0 !important; margin-left: 0 !important; }
.pw-box .sub { margin-left: 0 !important; }
.mday td:first-child b { white-space: nowrap; }'''

BLOCK_JS = r'''// SBI Lite ERP - single page: fixed top menu, drill-down screens, ERPNext forms open inside the page.
// root_element is the block's shadow root (given by Frappe).
const R = root_element;
const q = (s) => R.querySelector(s);
const API = "sbi_lite_erp";
// v16 desk lives at /desk (older sites use /app)
const BASE = window.location.pathname.indexOf("/app") === 0 ? "/app" : "/desk";

// ------------------------------------------------------------------ helpers
const esc = (v) => frappe.utils.escape_html(v === null || v === undefined ? "" : String(v));
const money = (v) => {
	const n = Number(v || 0);
	return (n < 0 ? "-" : "") + "₹ " + Math.abs(Math.round(n)).toLocaleString("en-IN");
};
const num = (v) => {
	const n = Math.round(Number(v || 0) * 1000) / 1000;
	return n.toLocaleString("en-IN");
};
const dt = (d) => (d ? frappe.datetime.str_to_user(String(d).slice(0, 10)) : "");
const slug = (doctype) => doctype.toLowerCase().replace(/ /g, "-");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const call = (action, args) =>
	frappe.call({ method: API, args: Object.assign({ action: action, company: S.company }, args || {}) })
		.then((r) => (r && r.message) || {});
const statusPill = (s, docstatus) => {
	if (docstatus === 0) return `<span class="pill orange">Draft</span>`;
	const t = String(s || "");
	const cls = /paid|completed|fully|submitted/i.test(t) ? "green" : /overdue|unpaid|cancel/i.test(t) ? "red" : /partly|partial|draft/i.test(t) ? "orange" : "";
	return `<span class="pill ${cls}">${esc(t || "-")}</span>`;
};
async function waitFor(fn, ms) {
	const end = Date.now() + (ms || 15000);
	while (Date.now() < end) {
		let v = null;
		try { v = fn(); } catch (e) { v = null; }
		if (v) return v;
		await sleep(150);
	}
	throw new Error("Timed out");
}

// ------------------------------------------------------------------ icons (simple stroke icons)
const ICON_PATHS = {
	home: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
	folder: "M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
	receipt: "M6 2h12v20l-3-2-3 2-3-2-3 2zM9 7h6M9 11h6M9 15h4",
	cart: "M3 4h2l2.5 11h11L21 7H7M9 20h.01M18 20h.01",
	wallet: "M20 7V5a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H5a2 2 0 0 1-2-2V6M16 13h.01",
	bank: "M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 21h18",
	map: "M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.5-7 12-7 12zM12 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
	users: "M16 20v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 20v-1a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8",
	percent: "M19 5L5 19M7 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
	upload: "M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
	download: "M12 4v12M7 11l5 5 5-5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3",
	info: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 16v-4M12 8h.01",
	trend: "M3 17l6-6 4 4 8-8M15 7h6v6",
	inbox: "M22 12h-6l-2 3h-4l-2-3H2M5.5 5h13l3.5 7v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-6z",
	outbox: "M12 3v10M8 7l4-4 4 4M2 13h6l2 3h4l2-3h6v5a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2z",
	clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM12 6v6l4 2",
	check: "M20 6L9 17l-5-5",
	alert: "M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z",
	calendar: "M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM3 10h18M8 2v4M16 2v4",
	plus: "M12 5v14M5 12h14",
	search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
	user: "M20 21v-1a5 5 0 0 0-5-5H9a5 5 0 0 0-5 5v1M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
};
const ICON = (n, cls) => `<svg class="ic ${cls || ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICON_PATHS[n] || ICON_PATHS.info}"/></svg>`;
const MENU_ICON = { me: "user", home: "home", projects: "folder", sales: "receipt", purchase: "cart", cash: "wallet", bank: "bank", site: "map", hr: "users", gst: "percent" };

// ------------------------------------------------------------------ small charts (plain SVG, no library)
function barChart(rows, keys, colors, names) {
	const W = 640, H = 230, L = 64, B = 30, T = 14;
	const realMax = Math.max(0, ...rows.map((r) => Math.max(...keys.map((k) => Number(r[k] || 0)))));
	if (!realMax) return `<div class="chart-empty">${ICON("trend")}<span>No sales or purchase bills in the last 6 months yet.<br>The chart fills in as bills are submitted.</span></div>`;
	const max = realMax;
	const step = Math.pow(10, Math.floor(Math.log10(max)));
	const top = Math.ceil(max / step) * step;
	const gw = (W - L - 10) / rows.length, bw = Math.min(26, (gw - 16) / keys.length);
	const short = (v) => v >= 1e7 ? (v / 1e7).toFixed(v >= 1e8 ? 0 : 1) + " Cr" : v >= 1e5 ? (v / 1e5).toFixed(v >= 1e6 ? 0 : 1) + " L" : v >= 1e3 ? Math.round(v / 1e3) + " K" : String(Math.round(v));
	let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
	for (let i = 0; i <= 4; i++) {
		const y = T + (H - T - B) * (1 - i / 4);
		s += `<line x1="${L}" x2="${W - 6}" y1="${y}" y2="${y}" class="gl"/><text x="${L - 8}" y="${y + 4}" text-anchor="end" class="ax">${short(top * i / 4)}</text>`;
	}
	rows.forEach((r, i) => {
		const x0 = L + i * gw + (gw - bw * keys.length - 4 * (keys.length - 1)) / 2;
		keys.forEach((k, j) => {
			const v = Number(r[k] || 0), h = (H - T - B) * v / top;
			s += `<rect x="${x0 + j * (bw + 4)}" y="${H - B - h}" width="${bw}" height="${Math.max(h, v ? 2 : 0)}" rx="3" fill="${colors[j]}"><title>${names[j]} ${money(v)}</title></rect>`;
		});
		s += `<text x="${L + i * gw + gw / 2}" y="${H - 9}" text-anchor="middle" class="ax">${moment(r.month + "-01").format("MMM")}</text>`;
	});
	s += `</svg><div class="legend">${names.map((n, j) => `<span><i style="background:${colors[j]}"></i>${n}</span>`).join("")}</div>`;
	return s;
}

const AGE = [["not_due", "Not yet due", "#16a34a"], ["d30", "1–30 days late", "#eab308"], ["d60", "31–60", "#f97316"], ["d90", "61–90", "#ef4444"], ["d90p", "Over 90", "#991b1b"]];
function ageBar(label, a, go) {
	const tot = AGE.reduce((s, x) => s + Number(a[x[0]] || 0), 0);
	let h = `<div class="age" ${go ? `data-go="${go}"` : ""}><div class="age-h"><b>${label}</b><span>${money(tot)}</span></div><div class="age-bar">`;
	if (!tot) h += `<div class="age-empty">nothing outstanding</div>`;
	AGE.forEach((x) => { const v = Number(a[x[0]] || 0); if (v > 0) h += `<div style="width:${Math.max(2, v * 100 / tot)}%;background:${x[2]}" title="${x[1]}: ${money(v)}"></div>`; });
	h += `</div><div class="age-l">${AGE.map((x) => Number(a[x[0]] || 0) > 0 ? `<span><i style="background:${x[2]}"></i>${x[1]} <b>${money(a[x[0]])}</b></span>` : "").join("")}</div></div>`;
	return h;
}
const progress = (part, whole, cls) => {
	const p = whole > 0 ? Math.max(0, Math.min(100, part * 100 / whole)) : 0;
	return `<div class="prog ${cls || ""}"><div style="width:${p.toFixed(1)}%"></div></div>`;
};

const S = { companies: [], projects: [], company: "", period: "fy", from: "", to: "", includeBank: false, crumbs: [], menu: "" };

// ------------------------------------------------------------------ menu
const MENUS = [
	{ id: "me", label: "My work", items: [
		["me", "My attendance", "This month: punches, hours, leave"],
		["punch", "Punch IN / OUT", "SBI Office – GPS + selfie"],
		["me-att", "Attendance request", "Forgot punch, on duty, work from home…"],
		["me-leave", "Leave request", "Apply leave, see leave left"],
		["me-profile", "My details", "Phone, address, bank, photo – HR approves"],
		["me-slips", "My salary slips", ""],
		["me-pw", "Change password", ""],
	] },
	{ id: "projects", label: "Projects", items: [
		["projects", "All projects", "Money in and out for each project"],
		["new:Project", "New project", ""],
		["boq", "Project BOQ", "Project \u2192 stage \u2192 type or upload the BOQ"],
		["list:Project BOQ", "All BOQ records", ""],
	] },
	{ id: "sales", label: "Sales", items: [
		["sales", "Bill a milestone", "Project \u2192 order \u2192 milestone (MS lines)"],
		["sales-nonms", "Non-MS bill", "Lines not in any milestone (MS = No)"],
		["so-new", "New sales order", "Sl, description, area, unit, cost, MS"],
		["list:Sales Order", "All sales orders", ""],
		["sales-direct", "Direct invoice", "Bill without a sales order"],
		["list:Sales Invoice", "All sales invoices", ""],
		["receive", "Receive payment", ""],
	] },
	{ id: "purchase", label: "Purchase", items: [
		["po-bill", "Bill a milestone", "Project \u2192 purchase order \u2192 milestone"],
		["po-nonms", "Non-MS bill", "Purchase order lines not in milestones"],
		["po-new", "New purchase order", "Sl, description, area, unit, cost, MS"],
		["list:Purchase Order", "All purchase orders", ""],
		["purchase", "Purchase from BOQ", "Project \u2192 stage \u2192 BOQ items not yet bought"],
		["purchase-direct", "Direct purchase bill", "Project \u2192 stage \u2192 blank bill"],
		["list:Purchase Invoice", "All purchase invoices", ""],
		["pay", "Pay supplier", ""],
	] },
	{ id: "cash", label: "Cash Flow", items: [
		["cash-give", "Give cash to site", ""],
		["cash-expense", "Site expense", ""],
		["cash-tally", "Import from Tally", "Tally cash payments → site"],
		["page:cash-flow", "Owner dashboard", "Charts and reports"],
	] },
	{ id: "bank", label: "Bank", items: [
		["bank", "Daily bank check", "Match each entry to a GST invoice, or remark it"],
		["bank-upload", "Upload bank statement", "Excel or CSV from the bank, every day"],
		["bank-accounts", "Bank accounts", "Last statement and what is left to check"],
		["new:Bank Account", "Add bank account", ""],
		["bank-noinv", "Entries without invoice", "Reasons and remarks given"],
		["route:bank-reconciliation-tool", "ERPNext reconciliation tool", "For the accounts team"],
	] },
	{ id: "site", label: "Site Summary", items: [
		["sites", "All sites", "Billed, received, spent, margin"],
		["cash-position", "Cash with each site", ""],
	] },
	{ id: "hr", label: "HR", items: [
		["hr-dash", "HR dashboard", "Today's attendance; tap a person for the month"],
		["hr-emps", "Add / edit employee", "ID No., photo, login and allowed areas"],
		["hr-req", "Requests to approve", "Attendance, leave and detail changes"],
		["hr", "Attendance", "Day, salary month or custom dates"],
		["report:Monthly Attendance Sheet", "Attendance report", "Month sheet for all staff"],
		["letter:SBI Appointment Order", "Appointment order", "Print for an employee"],
		["letter:SBI Relieving Order", "Relieving order", "Print for an employee who leaves"],
		["list:Appointment Letter", "Appointment letters (HRMS)", ""],
		["list:Salary Structure Assignment", "Payroll details", "Salary of each employee"],
		["list:Salary Structure", "Salary structures", ""],
		["ext:/sbi_office", "SBI Office – staff punch app", "Opens the punch app (GPS + selfie)"],
		["hr-settings", "Salary month & office settings", "Month start day, office time, GPS area, reminders"],
		["list:Employee Checkin", "Office punches", "Every office punch"],
		["list:Labour", "Labour register", "Site labour, wages, face enrolment"],
		["list:Labour Attendance Log", "Labour punches", "Every punch from the site app"],
		["list:Employee", "Employees", ""],
		["list:Attendance", "Staff attendance", ""],
		["list:Leave Application", "Leave applications", ""],
		["list:Expense Claim", "Expense claims", ""],
		["list:Employee Advance", "Employee advances", ""],
		["new:Payroll Entry", "Run payroll", ""],
		["list:Salary Slip", "Salary slips", ""],
		["report:Salary Register", "Salary register", ""],
		["list:Leave Allocation", "Leave allocation", "Leave given to each employee"],
		["list:Holiday List", "Holidays", ""],
	] },
	{ id: "gst", label: "GST", items: [
		["gst", "GST to pay", "Output, input credit, paid, balance"],
		["report:Sales Register", "Sales register", ""],
		["report:Purchase Register", "Purchase register", ""],
		["list:e-Waybill Log", "e-Way bills", ""],
		["route:gst-india", "GST returns", "India Compliance (GSTR-1, 3B)"],
	] },
];

const NO_COMPANY = ["Project BOQ", "e-Waybill Log", "Labour", "Labour Attendance Log"];

function drawMenu() {
	q("#menu").innerHTML = MENUS.map((m) => `
		<div class="m ${S.menu === m.id ? "active" : ""}" data-menu="${m.id}">
			<button class="m-btn" data-go="${m.items[0][0]}" data-m="${m.id}">${ICON(MENU_ICON[m.id] || "info", "mi")}<span>${esc(m.label)}</span>${m.items.length > 1 ? ` <span class="car">\u25bc</span>` : ""}</button>
			${m.items.length > 1 ? `<div class="m-sub">${m.items.map((i) => `<a data-go="${esc(i[0])}" data-m="${m.id}">${esc(i[1])}${i[2] ? `<span class="d">${esc(i[2])}</span>` : ""}</a>`).join("")}
				<a class="m-help" data-act="help-drawer" data-h="${m.id}">${ICON("info")} How to use ${esc(m.label)}</a></div>` : ""}
		</div>`).join("");
}

function setMenu(id) {
	S.menu = id;
	R.querySelectorAll(".m").forEach((el) => el.classList.toggle("active", el.dataset.menu === id));
	const hb = q("#helpbtn");
	if (hb) hb.classList.toggle("on", id === "help");
	const brand = q(".lx-brand span");
	if (brand) brand.classList.toggle("on", id === "home");
	R.querySelectorAll(".m.open").forEach((el) => el.classList.remove("open"));
}

// crumbs: [[label, fn|null], ...]; right: extra html on the right
function crumbs(list, right) {
	S.crumbs = list;
	q("#crumbs").innerHTML = list.map((c, i) => (i ? `<span class="sep">›</span>` : "") +
		(c[1] && i < list.length - 1 ? `<a data-crumb="${i}">${esc(c[0])}</a>` : `<b>${esc(c[0])}</b>`)).join("") +
		`<span class="right">${right || ""}${S.menu !== "help" ? `<a class="hpill" data-act="help-drawer">${ICON("info")} How this works</a>` : ""}</span>`;
}

function showView(html) {
	q("#framewrap").classList.add("hide");
	q("#view").classList.remove("hide");
	if (html !== undefined) q("#view").innerHTML = html;
	const h2 = q("#view h2.t");
	if (h2 && !h2.querySelector("svg") && !h2.closest(".emp-head")) h2.insertAdjacentHTML("afterbegin", `<span class="ti">${ICON(MENU_ICON[S.menu] || "info")}</span>`);
	q("#view").scrollTop = 0;
}
const loading = () => showView(`<div class="skel"><div class="sk sk-t"></div><div class="sk sk-s"></div>
	<div class="sk-row">${"<div class='sk sk-c'></div>".repeat(4)}</div><div class="sk sk-b"></div><div class="sk sk-b short"></div></div>`);

// ------------------------------------------------------------------ embedded ERPNext (forms, lists, reports)
const FRAME_CSS = `
	header.navbar, .navbar.navbar-expand, .body-sidebar-container, .body-sidebar, .layout-side-section,
	.desk-sidebar, .sidebar-toggle-btn, .page-head .sidebar-toggle-btn { display: none !important; }
	.page-head { top: 0 !important; }
	body { padding-top: 0 !important; }
	.main-section, .page-container, .layout-main-section-wrapper { margin-left: 0 !important; }
	.page-body, .container.page-body { max-width: 100% !important; width: 100% !important; }`;

function frameStyle() {
	try {
		const d = q("#frame").contentDocument;
		if (d && d.head && !d.getElementById("lx-frame-css")) {
			const st = d.createElement("style");
			st.id = "lx-frame-css";
			st.textContent = FRAME_CSS;
			d.head.appendChild(st);
		}
	} catch (e) { /* not same origin yet */ }
}

function frameReady() {
	try {
		const w = q("#frame").contentWindow;
		if (w && w.frappe && w.frappe.set_route && w.frappe.model && w.frappe.model.get_new_doc &&
			w.frappe.boot && w.frappe.boot.user && w.document.readyState === "complete") {
			frameStyle();
			return w;
		}
	} catch (e) { /* loading */ }
	return null;
}

function frameWin() {
	const w = frameReady();
	if (w) return Promise.resolve(w);
	const f = q("#frame");
	if (!f.getAttribute("src")) f.setAttribute("src", BASE + "/sales-invoice");
	return waitFor(frameReady, 40000).then(async (w2) => { await sleep(400); return w2; });
}

function showFrame() {
	q("#view").classList.add("hide");
	q("#framewrap").classList.remove("hide");
}

function openTabLink() {
	return `<a data-act="newtab" title="Open the same page in a new browser tab">Open in new tab ↗</a>`;
}

// go to a desk route inside the page: args for frappe.set_route, url for a cold start
// args are plain route parts ("List", "Project BOQ"); opts become list / report filters
async function frameGo(args, url, opts) {
	showFrame();
	const w = frameReady();
	const has = opts && Object.keys(opts).length;
	if (w) {
		w.frappe.route_options = has ? Object.assign({}, opts) : null;
		w.frappe.set_route.apply(w.frappe, args);
		return w;
	}
	const qs = has ? "?" + Object.keys(opts).map((k) => encodeURIComponent(k) + "=" + encodeURIComponent(opts[k])).join("&") : "";
	q("#frame").setAttribute("src", url + qs);
	return frameWin();
}

function frameForm(doctype, name, back) {
	crumbs((back || []).concat([[doctype + " " + name, null]]), openTabLink());
	return frameGo(["Form", doctype, name], BASE + "/" + slug(doctype) + "/" + encodeURIComponent(name));
}

function frameList(doctype, filters, label) {
	crumbs([[label || doctype, null]], openTabLink());
	return frameGo(["List", doctype], BASE + "/" + slug(doctype), filters || {});
}

// new form inside the page, values set through the form so ERPNext's own triggers run
async function frameNew(doctype, values, after, back) {
	crumbs((back || []).concat([["New " + doctype, null]]), openTabLink());
	showFrame();
	const fz = frappe.dom.freeze(__("Opening {0}…", [__(doctype)]));
	try {
		const w = await frameWin();
		await new Promise((res) => w.frappe.model.with_doctype(doctype, res));
		const d = w.frappe.model.get_new_doc(doctype);
		w.frappe.set_route("Form", doctype, d.name);
		const frm = await waitFor(() => (w.cur_frm && w.cur_frm.doctype === doctype && w.cur_frm.docname === d.name ? w.cur_frm : null), 20000);
		await sleep(300);
		for (const k of Object.keys(values || {})) {
			if (values[k] === undefined || values[k] === null || values[k] === "") continue;
			if (!frm.fields_dict[k]) continue;
			await frm.set_value(k, values[k]);
		}
		if (after) await after(frm, w);
		return frm;
	} catch (e) {
		frappe.msgprint(__("Could not open the form inside the page. Please try again."));
		throw e;
	} finally {
		frappe.dom.unfreeze();
	}
}

// ------------------------------------------------------------------ project picker
function projectsForCompany() {
	return S.projects.filter((p) => !S.company || !p.company || p.company === S.company);
}
function pLabel(p) {
	return p.project_name && p.project_name !== p.name ? p.project_name : p.name;
}
function findProject(name) {
	return S.projects.find((p) => p.name === name) || { name: name, project_name: name };
}

function pickProject(title, sub, back, next) {
	crumbs(back.concat([["Pick a project", null]]));
	const list = projectsForCompany().slice().sort((a, b) => (a.status === "Open" ? 0 : 1) - (b.status === "Open" ? 0 : 1));
	showView(`<h2 class="t">${esc(title)}</h2><div class="sub">${esc(sub)}</div>
		<input class="search" id="psearch" placeholder="Search project or customer…" autocomplete="off">
		<div class="cards" id="pcards">${list.map((p) => `
			<div class="card ${p.status !== "Open" ? "done" : ""}" data-pick="${esc(p.name)}" data-s="${esc((p.name + " " + (p.project_name || "") + " " + (p.customer || "")).toLowerCase())}">
				<div class="n">${esc(pLabel(p))}</div>
				<div class="c">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""}</div>
				${p.status !== "Open" ? `<div class="c"><span class="pill">${esc(p.status)}</span></div>` : ""}
			</div>`).join("") || `<div class="hint">No projects for this company.</div>`}</div>`);
	S.onPick = next;
	const s = q("#psearch");
	s.focus();
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		R.querySelectorAll("#pcards .card").forEach((c) => c.classList.toggle("hide", !!t && c.dataset.s.indexOf(t) < 0));
	});
}

// ------------------------------------------------------------------ router
function go(key, menuId) {
	if (S.scope !== "all" && S.scope && key === "home") { key = S.homeKey || "me"; menuId = S.homeMenu || "me"; }
	helpClose();
	if (menuId) setMenu(menuId);
	const [kind, arg] = key.indexOf(":") > 0 ? [key.slice(0, key.indexOf(":")), key.slice(key.indexOf(":") + 1)] : [key, ""];
	if (kind === "ext") { window.open(arg, "_blank"); return; }
	if (kind === "letter") return pickEmployee(arg.replace("SBI ", ""), (emp) => openLetter(arg, emp));
	if (kind === "new") return frameNew(arg, { company: S.company });
	if (kind === "list") return frameList(arg, S.company && NO_COMPANY.indexOf(arg) < 0 ? { company: S.company } : {}, arg);
	if (kind === "report") {
		crumbs([[arg, null]], openTabLink());
		return frameGo(["query-report", arg], BASE + "/query-report/" + encodeURIComponent(arg), S.company ? { company: S.company } : {});
	}
	if (kind === "page" || kind === "route") {
		let lbl = arg;
		MENUS.forEach((mm) => mm.items.forEach((it) => { if (it[0] === key) lbl = it[1]; }));
		crumbs([[lbl, null]], openTabLink());
		return frameGo([arg], BASE + "/" + arg);
	}
	const V = {
		home: viewHome,
		help: () => viewHelp(),
		"hr-settings": () => viewHrSettings(),
		me: () => { S.mBack = 0; return viewMe(); },
		punch: () => { window.location.href = "/sbi_office"; },
		"me-att": viewMeAtt,
		"me-leave": viewMeLeave,
		"me-profile": viewMeProfile,
		"me-slips": viewMeSlips,
		"me-pw": () => viewChangePw(false),
		"hr-dash": viewHrDash,
		"hr-emps": viewHrDash,
		"hr-req": () => viewReqs(),
		boq: () => pickProject("Project BOQ", "Pick the project for the BOQ.", [["Project BOQ", () => go("boq", "projects")]], (p) => viewBoqStages(p)),
		bank: () => bankGo("check"),
		"bank-upload": () => bankGo("upload"),
		"bank-accounts": () => viewBankAccounts("overview"),
		"bank-noinv": viewBankNoInv,
		hr: () => viewHr(),
		projects: viewProjects,
		sites: viewSites,
		"cash-position": viewCashPosition,
		gst: viewGst,
		"cash-tally": viewTally,
		sales: () => pickProject("Bill a milestone", "Pick the project to bill.", [["Sales", () => go("sales", "sales")]], (p) => viewOrders(p, "sales", "ms")),
		"sales-nonms": () => pickProject("Non-MS bill", "Pick the project.", [["Sales", () => go("sales-nonms", "sales")]], (p) => viewOrders(p, "sales", "nonms")),
		"so-new": () => pickProject("New sales order", "Pick the project for the sales order.", [["Sales", () => go("sales", "sales")]], (p) => viewOrderForm(p, "sales")),
		"po-bill": () => pickProject("Bill a milestone (purchase)", "Pick the project.", [["Purchase", () => go("po-bill", "purchase")]], (p) => viewOrders(p, "purchase", "ms")),
		"po-nonms": () => pickProject("Non-MS purchase bill", "Pick the project.", [["Purchase", () => go("po-nonms", "purchase")]], (p) => viewOrders(p, "purchase", "nonms")),
		"po-new": () => pickProject("New purchase order", "Pick the project for the purchase order.", [["Purchase", () => go("po-bill", "purchase")]], (p) => viewOrderForm(p, "purchase")),
		"sales-direct": () => pickProject("Direct invoice", "Pick the project. The invoice opens with the project filled in.", [["Sales", () => go("sales", "sales")]],
			(p) => directSales(p)),
		receive: () => frameNew("Payment Entry", { payment_type: "Receive", company: S.company }, null, [["Sales", () => go("sales", "sales")]]),
		purchase: () => pickProject("Purchase Invoice", "Pick the project you are buying for.", [["Purchase", () => go("purchase", "purchase")]], (p) => viewStages(p, false)),
		"purchase-direct": () => pickProject("Direct purchase bill", "Pick the project, then the stage.", [["Purchase", () => go("purchase", "purchase")]], (p) => viewStages(p, true)),
		pay: () => frameNew("Payment Entry", { payment_type: "Pay", company: S.company }, null, [["Purchase", () => go("purchase", "purchase")]]),
		"cash-give": () => pickProject("Give cash to site", "Pick the site.", [["Cash Flow", () => go("cash-give", "cash")]], (p) => viewCash(p, "give")),
		"cash-expense": () => pickProject("Site expense", "Pick the site.", [["Cash Flow", () => go("cash-give", "cash")]], (p) => viewCash(p, "expense")),
	};
	S.current = () => go(key, menuId);
	return (V[kind] || viewHome)();
}

// ------------------------------------------------------------------ SALES + PURCHASE: orders with MS lines, milestone bills, non-MS bills
const KD = {
	sales: { title: "Sales", menu: "sales", order: "Sales Order", inv: "Sales Invoice", party: "Customer", who: "customer",
		msKey: "sales", nonKey: "sales-nonms", newKey: "so-new", word: "sales order", bill: "invoice" },
	purchase: { title: "Purchase", menu: "purchase", order: "Purchase Order", inv: "Purchase Invoice", party: "Supplier", who: "supplier",
		msKey: "po-bill", nonKey: "po-nonms", newKey: "po-new", word: "purchase order", bill: "purchase bill" },
};
const UOM_LABEL = { "Square Foot": "sq.ft", "Square Meter": "sq.m", "Running Meter": "rmt", "Cubic Meter": "cu.m", "Lump Sum": "LS", "Sq Feet": "sq.ft (Sq Feet)", "Sqm": "sq.m (Sqm)" };
function ordersBack(p, kind, mode) {
	const k = KD[kind];
	return [[k.title, () => go(mode === "nonms" ? k.nonKey : k.msKey, k.menu)], [pLabel(p), () => viewOrders(p, kind, mode || "ms")]];
}
// old name kept for the other screens that link back to billing
function salesBack(p) { return ordersBack(p, "sales", "ms"); }
function viewMilestones(p) { return viewOrders(p, "sales", "ms"); }

function directSales(p) {
	setMenu("sales");
	return frameNew("Sales Invoice", { company: p.company || S.company, project: p.name, sbi_direct_invoice: 1 }, null, ordersBack(p, "sales", "ms"));
}

async function viewOrders(p, kind, mode) {
	const k = KD[kind];
	S.here = () => viewOrders(p, kind, mode);
	setMenu(k.menu);
	crumbs([[k.title, () => go(mode === "nonms" ? k.nonKey : k.msKey, k.menu)], [pLabel(p), null]]);
	loading();
	const d = await call("orders", { kind: kind, project: p.name });
	const orders = d.orders || [];
	let h = `<h2 class="t">${esc(pLabel(p))}</h2>
		<div class="sub">${mode === "nonms" ? `Lines with <b>MS = No</b> are not part of any milestone. Bill them here whenever the work is done.`
			: `Lines with <b>MS = Yes</b> are billed by milestone. Click a milestone card to make its ${k.bill}.`}</div>
		<div class="bar"><div class="seg">
			<a class="${mode !== "nonms" ? "on" : ""}" data-act="o-mode" data-kind="${kind}" data-mode="ms" data-p="${esc(p.name)}">Milestone (MS) bills</a>
			<a class="${mode === "nonms" ? "on" : ""}" data-act="o-mode" data-kind="${kind}" data-mode="nonms" data-p="${esc(p.name)}">Non-MS bills</a></div>
			<button class="btn" data-act="o-new" data-kind="${kind}" data-p="${esc(p.name)}">＋ New ${k.word}</button></div>`;
	if (!orders.length) {
		h += `<div class="box msempty"><div class="ico">🧾</div><h3>This project has no ${k.word} yet</h3>
			<div class="muted">Make the ${k.word} once: one line per item with area, unit, cost per unit, and <b>MS</b> Yes / No.<br>
			MS = Yes lines are billed by milestones. MS = No lines are billed separately as non-MS bills.</div>
			<div class="bar c"><button class="btn pri big" data-act="o-new" data-kind="${kind}" data-p="${esc(p.name)}">＋ Create ${k.word}</button>
			${kind === "sales" ? `<button class="btn" data-act="direct-si" data-p="${esc(p.name)}">Make a direct invoice instead</button>`
				: `<button class="btn" data-act="p-buy" data-p="${esc(p.name)}">Purchase from BOQ instead</button>`}</div></div>`;
	}
	orders.forEach((o) => {
		const head = `<h3>${esc(o.name)} <span class="muted">${esc(o.party)} · ${money(o.grand_total)} with GST · billed ${Math.round(o.per_billed || 0)}%</span>
			<a class="muted" data-act="open" data-dt="${k.order}" data-name="${esc(o.name)}">open order</a></h3>
			<div class="chips"><span class="chip ms">MS work ${money(o.ms_net)}</span><span class="chip non">Non-MS ${money(o.non_net)}</span></div>`;
		if (o.docstatus === 0) {
			h += `<div class="box mswait"><div class="ico">⏳</div><div><b>${esc(o.name)} is waiting for your “Submit”.</b>
				<div class="muted">${esc(o.party)} · ${money(o.grand_total)} · ${o.lines.length} line(s). Open it, check it, then click <b>Submit</b>. Billing starts after that.</div></div>
				<button class="btn pri" data-act="open" data-dt="${k.order}" data-name="${esc(o.name)}">Open and submit</button></div>`;
			return;
		}
		h += `<div class="box">${head}`;
		if (mode === "nonms") {
			const non = o.lines.filter((l) => Number(l.ms) === 0);
			if (!non.length) { h += `<div class="hint">No MS = No lines in this order. Everything is billed by milestone.</div></div>`; return; }
			let pend = 0;
			h += `<table><thead><tr><th>Sl</th><th>Description</th><th class="r">Area / Qty</th><th>Unit</th><th class="r">Cost / unit</th><th class="r">Total</th><th class="r">Billed</th><th class="r">To bill</th></tr></thead><tbody>`;
			non.forEach((l) => {
				const left = Math.max(0, (l.amount || 0) - (l.billed || 0));
				pend += left;
				h += `<tr><td>${esc(l.sl || l.idx)}</td><td>${esc(l.description)}</td><td class="r">${Number(l.qty)}</td><td>${esc(UOM_LABEL[l.uom] || l.uom)}</td>
					<td class="r">${money(l.rate)}</td><td class="r">${money(l.amount)}</td><td class="r">${money(l.billed)}</td><td class="r"><b>${money(left)}</b></td></tr>`;
			});
			h += `</tbody></table><div class="bar">`;
			const dr = (o.nonms_invoices || []).filter((x) => x.docstatus === 0);
			if (dr.length) h += `<button class="btn pri" data-act="open" data-dt="${k.inv}" data-name="${esc(dr[0].name)}">Open draft non-MS bill ${esc(dr[0].name)}</button>`;
			else if (pend > 0.5) h += `<button class="btn pri" data-act="o-nonms" data-kind="${kind}" data-o="${esc(o.name)}" data-p="${esc(p.name)}">Make non-MS ${k.bill} (${money(pend)} before GST)</button>`;
			else h += `<span class="pill green">All non-MS lines billed</span>`;
			(o.nonms_invoices || []).filter((x) => x.docstatus === 1).forEach((x) => { h += ` <a class="pill" data-act="open" data-dt="${k.inv}" data-name="${esc(x.name)}">${esc(x.name)}</a>`; });
			h += `</div><div class="muted small">The bill opens with what is left. You can lower the quantity if only part of the work is done.</div></div>`;
			return;
		}
		const terms = (o.terms || []).filter((t) => !t.non_ms);
		if (!o.ms_net) { h += `<div class="hint">No MS = Yes lines in this order. Use “Non-MS bills”.</div></div>`; return; }
		if (!terms.length) { h += `<div class="warn">This order has no milestones (payment terms). Make a new ${k.word} from Lite ERP, or add a Payment Terms Template to it.</div></div>`; return; }
		h += `<div class="cards">`;
		terms.forEach((t) => {
			const inv = t.invoice || t.draft_invoice;
			const state = t.invoice ? `<span class="pill green">Billed</span>` : t.draft_invoice ? `<span class="pill orange">Draft bill</span>` : `<span class="pill blue">Ready to bill</span>`;
			h += `<div class="card ms ${t.invoice ? "done ms-done" : t.draft_invoice ? "ms-draft" : "ms-ready"}" data-act="${inv ? "open" : "o-bill"}" data-dt="${k.inv}" data-name="${esc(inv || "")}"
					data-kind="${kind}" data-o="${esc(o.name)}" data-row="${esc(t.row_name)}" data-p="${esc(p.name)}">
				<div class="n">${t.idx}. ${esc(t.stage || t.payment_term || t.description)}</div>
				<div class="c">${t.pct}% of MS work${t.due_date ? " · bill on " + dt(t.due_date) : ""}</div>
				<div class="f"><b>${money(t.amount)}</b><span>before GST</span></div>
				<div class="f">${state}<span>${inv ? esc(inv) : "click to create"}</span></div>
				${t.received ? `<div class="c">received ${money(t.received)}</div>` : ""}
			</div>`;
		});
		h += `</div></div>`;
	});
	if (kind === "sales" && orders.length) h += `<div class="bar"><button class="btn" data-act="direct-si" data-p="${esc(p.name)}">+ Direct invoice for this project</button></div>`;
	if ((d.invoices || []).length) {
		h += `<div class="box"><h3>${k.inv}s of this project</h3><table><thead><tr><th>Bill</th><th>Date</th><th>${k.party}</th><th>Milestone</th>
			<th class="r">Amount</th><th class="r">Outstanding</th><th>Status</th></tr></thead><tbody>`;
		d.invoices.forEach((i) => {
			h += `<tr class="click" data-act="open" data-dt="${k.inv}" data-name="${esc(i.name)}"><td>${esc(i.name)}</td><td>${dt(i.posting_date)}</td><td>${esc(i.party)}</td>
				<td>${esc(i.stage)}</td><td class="r">${money(i.grand_total)}</td><td class="r">${money(i.outstanding_amount)}</td><td>${statusPill(i.status, i.docstatus)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
}

async function orderBill(el, act) {
	const p = findProject(el.dataset.p);
	const kind = el.dataset.kind;
	frappe.dom.freeze(__("Making the bill…"));
	try {
		const r = await call(act, { kind: kind, order: el.dataset.o, row: el.dataset.row || "" });
		frappe.dom.unfreeze();
		if (r.existing) frappe.show_alert({ message: __("A bill was already started: {0}", [r.name]), indicator: "orange" }, 5);
		frameForm(r.doctype, r.name, ordersBack(p, kind, act === "nonms_bill" ? "nonms" : "ms"));
	} catch (e) { frappe.dom.unfreeze(); }
}

// ---- new order form: lines (Sl, description, area, unit, cost/unit, total, MS) + milestones of the MS work
const MS_PRESETS = {
	a: [["Advance", 10], ["Foundation", 30], ["Structure", 40], ["Handover", 20]],
	b: [["Foundation", 30], ["Structure", 40], ["Finishing", 30]],
	c: [["Part 1", 25], ["Part 2", 25], ["Part 3", 25], ["Part 4", 25]],
	d: [["Full work", 100]],
};
function msDates(n) { return Array.from({ length: n }, (_, i) => frappe.datetime.add_days(frappe.datetime.get_today(), 30 * (i + 1))); }
function msPreset(k) {
	const P = MS_PRESETS[k] || MS_PRESETS.b;
	const dd = msDates(P.length);
	S.ms.rows = P.map((x, i) => ({ name: x[0], percent: x[1], due_date: dd[i] }));
	R.querySelectorAll(".imp").forEach((b) => b.classList.remove("on"));
	msRender();
}
function uomOptions(sel) {
	const d = S.ms.d;
	const opt = (u) => `<option value="${esc(u)}" ${u === sel ? "selected" : ""}>${esc(UOM_LABEL[u] || u)}</option>`;
	return (d.uoms || []).map(opt).join("") + ((d.uoms_more || []).length ? `<optgroup label="Other units">${d.uoms_more.map(opt).join("")}</optgroup>` : "");
}
function olBlank() { return { sl: "", description: "", qty: "", uom: (S.ms.d.uoms || [])[0] || "Nos", rate: "", ms: 1 }; }

async function viewOrderForm(p, kind) {
	const k = KD[kind];
	S.here = () => viewOrderForm(p, kind);
	setMenu(k.menu);
	crumbs([[k.title, () => go(k.msKey, k.menu)], [pLabel(p), () => viewOrders(p, kind, "ms")], ["New " + k.word, null]]);
	loading();
	const d = await call("order_setup", { kind: kind, project: p.name });
	S.ms = { p: p, kind: kind, d: d, rows: [], lines: [] };
	for (let i = 0; i < 3; i++) S.ms.lines.push(olBlank());
	S.ms.lines.forEach((l, i) => (l.sl = String(i + 1)));
	const partyOpts = (d.parties || []).map((c) => `<option ${c === d.default_party ? "selected" : ""}>${esc(c)}</option>`).join("");
	const itemOpts = (d.items || []).map((i) => `<option value="${esc(i.name)}" ${i.name === d.default_item ? "selected" : ""}>${esc(i.item_name || i.name)}${i.hsn ? " · HSN " + esc(i.hsn) : ""}</option>`).join("");
	const taxOpts = `<option value="">No GST</option>` + (d.templates || []).map((t) => `<option ${t === d.default_template ? "selected" : ""}>${esc(t)}</option>`).join("");
	const imps = d.imports || [];
	const impBtns = imps.map((m, i) => `<button class="btn sm imp" data-act="ms-import" data-i="${i}">${esc(m.label)} <span class="pill">${m.items.length}</span></button>`).join("");
	showView(`<h2 class="t">New ${k.word} · ${esc(pLabel(p))}</h2>
		<div class="sub">Write one line per item. Mark <b>MS = Yes</b> if the line is billed by milestones, <b>No</b> if it is billed separately.</div>
		<div class="fm"><div class="t"><span class="num">1</span> ${k.party} and GST</div><div class="g g4">
			<label>${k.party}<select id="o-party"><option value="">— choose —</option>${partyOpts}</select></label>
			<label>Item code (HSN for GST)<select id="o-item"><option value="">— choose —</option>${itemOpts}</select></label>
			<label>GST<select id="o-tax">${taxOpts}</select></label>
			<label>Company<input value="${esc(d.company || "")}" disabled></label></div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Lines</div>
			<table class="olt"><thead><tr><th>Sl. No.</th><th>Description</th><th class="r">Area / Qty</th><th>Unit</th><th class="r">Cost per unit (₹)</th><th class="r">Total cost</th><th>MS</th><th></th></tr></thead>
			<tbody id="o-lines"></tbody></table>
			<div class="bar"><button class="btn sm" data-act="ol-add">＋ Add line</button>
				${(d.boq_lines || []).length ? `<button class="btn sm" data-act="ol-boq">Bring ${d.boq_lines.length} line(s) from the project BOQ</button>` : ""}
				<span id="o-tot" class="otot"></span></div></div>
		<div class="fm" id="ms-box"><div class="t"><span class="num">3</span> Milestones of the MS work (saved as payment terms)</div>
			${imps.length ? `<div class="presets imps"><span class="muted">Bring in from:</span>${impBtns}</div>` : ""}
			<div class="presets"><span class="muted">Or quick start:</span>
				<button class="btn sm" data-act="ms-preset" data-k="a">Advance + 3 parts</button>
				<button class="btn sm" data-act="ms-preset" data-k="b">3 parts 30/40/30</button>
				<button class="btn sm" data-act="ms-preset" data-k="c">4 equal parts</button>
				<button class="btn sm" data-act="ms-preset" data-k="d">One bill (100%)</button></div>
			<datalist id="ms-stages">${(d.stages || []).map((s) => `<option value="${esc(s)}">`).join("")}</datalist>
			<table class="mst"><thead><tr><th>#</th><th>Milestone name</th><th class="r">% of MS work</th><th class="r">Amount (before GST)</th><th>Bill on date</th><th></th></tr></thead>
			<tbody id="ms-rows"></tbody></table>
			<div class="bar"><button class="btn sm" data-act="ms-add">＋ Add milestone</button><span id="ms-total" class="mstot"></span></div></div>
		<div class="bar"><button class="btn pri big" data-act="o-save">Create ${k.word}</button>
			<button class="btn" data-act="o-mode" data-kind="${kind}" data-mode="ms" data-p="${esc(p.name)}">Cancel</button></div>
		<div class="hint">After you click <b>Create</b>, the order opens below. Check it and click <b>Submit</b> once. Then MS lines are billed by milestone cards and MS = No lines by “Non-MS bills”.</div>`);
	olRender();
	if (imps.length) msImport(0); else msPreset("b");
}
function olRead() {
	R.querySelectorAll("#o-lines tr").forEach((tr) => {
		const l = S.ms.lines[Number(tr.dataset.i)];
		if (!l) return;
		tr.querySelectorAll("[data-f]").forEach((x) => { l[x.dataset.f] = x.value; });
	});
}
function olRender() {
	const b = q("#o-lines");
	if (!b) return;
	b.innerHTML = S.ms.lines.map((l, i) => `<tr data-i="${i}" class="${String(l.ms) === "0" ? "nonms" : ""}">
		<td><input class="ol-in sl" data-f="sl" value="${esc(l.sl)}"></td>
		<td><input class="ol-in" data-f="description" value="${esc(l.description)}" placeholder="e.g. PEB shed erection"></td>
		<td class="r"><input class="ol-in q" data-f="qty" type="number" min="0" step="any" value="${esc(l.qty)}"></td>
		<td><select class="ol-in" data-f="uom">${uomOptions(l.uom)}</select></td>
		<td class="r"><input class="ol-in q" data-f="rate" type="number" min="0" step="any" value="${esc(l.rate)}"></td>
		<td class="r ol-t">–</td>
		<td><select class="ol-in msel" data-f="ms"><option value="1" ${String(l.ms) !== "0" ? "selected" : ""}>Yes</option><option value="0" ${String(l.ms) === "0" ? "selected" : ""}>No</option></select></td>
		<td><button class="btn sm ghost" data-act="ol-del" data-i="${i}" title="Remove">✕</button></td></tr>`).join("");
	olTotals();
}
function olTotals() {
	let msn = 0, non = 0;
	R.querySelectorAll("#o-lines tr").forEach((tr) => {
		const v = (f) => (tr.querySelector(`[data-f="${f}"]`) || {}).value;
		const t = Number(v("qty") || 0) * Number(v("rate") || 0);
		const isMs = v("ms") !== "0";
		tr.classList.toggle("nonms", !isMs);
		tr.querySelector(".ol-t").textContent = t ? money(t) : "–";
		if (isMs) msn += t; else non += t;
	});
	S.ms.msNet = msn;
	const el = q("#o-tot");
	if (el) el.innerHTML = `<span class="chip ms">MS work ${money(msn)}</span><span class="chip non">Non-MS ${money(non)}</span><b>Order ${money(msn + non)}</b> <span class="muted">before GST</span>`;
	const box = q("#ms-box");
	if (box) box.classList.toggle("dim", !msn);
	msTotals();
}
function olFromBoq() {
	olRead();
	const keep = S.ms.lines.filter((l) => (l.description || "").trim() || Number(l.qty) || Number(l.rate));
	const add = (S.ms.d.boq_lines || []).map((b, i) => ({ sl: b.sl || String(keep.length + i + 1), description: b.description, qty: b.qty, uom: b.uom, rate: b.rate, ms: 1 }));
	S.ms.lines = keep.concat(add);
	olRender();
	frappe.show_alert({ message: __("{0} line(s) added from the BOQ. Set MS = No for lines billed separately.", [add.length]), indicator: "blue" }, 6);
}
function msImport(i) {
	const m = (S.ms.d.imports || [])[i];
	if (!m || !m.items.length) return;
	const today = frappe.datetime.get_today();
	const tot = m.items.reduce((a, x) => a + (Number(x.weight) || 0), 0);
	let used = 0;
	S.ms.rows = m.items.map((x, k) => {
		let pc = tot > 0 ? Math.round((Number(x.weight) || 0) / tot * 10000) / 100 : Math.round(10000 / m.items.length) / 100;
		if (k === m.items.length - 1) pc = Math.round((100 - used) * 100) / 100;
		used += pc;
		const due = x.due_date && x.due_date >= today ? x.due_date : frappe.datetime.add_days(today, 30 * (k + 1));
		return { name: x.name, percent: pc, due_date: due };
	});
	R.querySelectorAll(".imp").forEach((b) => b.classList.toggle("on", b.dataset.i === String(i)));
	msRender();
}
function msRead() {
	R.querySelectorAll("#ms-rows tr").forEach((tr) => {
		const r = S.ms.rows[Number(tr.dataset.i)];
		if (!r) return;
		r.name = tr.querySelector(".ms-n").value;
		r.percent = Number(tr.querySelector(".ms-p").value || 0);
		r.due_date = tr.querySelector(".ms-d").value;
	});
}
function msTotals() {
	const v = Number(S.ms.msNet || 0);
	let tot = 0;
	R.querySelectorAll("#ms-rows tr").forEach((tr) => {
		const pc = Number(tr.querySelector(".ms-p").value || 0);
		tot += pc;
		tr.querySelector(".ms-a").textContent = v ? money(v * pc / 100) : "–";
	});
	tot = Math.round(tot * 100) / 100;
	const el = q("#ms-total");
	if (!el) return tot;
	const ok = Math.abs(tot - 100) < 0.01;
	el.className = "mstot " + (ok ? "ok" : "bad");
	el.innerHTML = ok ? `✔ Total 100% · ${money(v)}` : `Total ${tot}% – must be 100% (${tot < 100 ? "add " + Math.round((100 - tot) * 100) / 100 + "% more" : "remove " + Math.round((tot - 100) * 100) / 100 + "%"})`;
	return tot;
}
function msRender() {
	const b = q("#ms-rows");
	if (!b) return;
	b.innerHTML = S.ms.rows.map((r, i) => `<tr data-i="${i}"><td>${i + 1}</td>
		<td><input class="ms-in ms-n" list="ms-stages" value="${esc(r.name)}" placeholder="e.g. Foundation"></td>
		<td class="r"><input class="ms-in ms-p q" type="number" min="0" max="100" step="0.01" value="${r.percent || ""}"></td>
		<td class="r ms-a">–</td>
		<td><input class="ms-in ms-d" type="date" min="${frappe.datetime.get_today()}" value="${esc(r.due_date || "")}"></td>
		<td><button class="btn sm ghost" data-act="ms-del" data-i="${i}" title="Remove">✕</button></td></tr>`).join("");
	msTotals();
}
async function orderSave(btn) {
	olRead(); msRead(); olTotals();
	const { p, kind } = S.ms;
	const k = KD[kind];
	const lines = S.ms.lines.filter((l) => (l.description || "").trim() || Number(l.qty) || Number(l.rate));
	const args = { kind: kind, project: p.name, party: q("#o-party").value, item: q("#o-item").value, template: q("#o-tax").value,
		lines: JSON.stringify(lines), rows: JSON.stringify(S.ms.msNet ? S.ms.rows : []) };
	if (!args.party) return frappe.msgprint(__("Step 1: choose the {0}.", [k.who]));
	if (!args.item) return frappe.msgprint(__("Step 1: choose the item code (it carries the HSN for GST)."));
	if (!lines.length) return frappe.msgprint(__("Step 2: add at least one line."));
	const bad = lines.find((l) => !(l.description || "").trim() || !(Number(l.qty) > 0));
	if (bad) return frappe.msgprint(__("Step 2: every line needs a description and an area / quantity."));
	if (S.ms.msNet && Math.abs(msTotals() - 100) > 0.01) return frappe.msgprint(__("Step 3: the milestones must add up to 100% of the MS work."));
	btn.disabled = true;
	try {
		const r = await call("order_create", args);
		frappe.show_alert({ message: __("{0} made with {1} line(s) and {2} milestone(s). Check it and click Submit.", [r.name, r.lines, r.milestones]), indicator: "green" }, 8);
		frameForm(r.doctype, r.name, ordersBack(p, kind, "ms"));
	} catch (x) { btn.disabled = false; }
}

// ------------------------------------------------------------------ PURCHASE: project -> stage -> BOQ items -> bill
function purchaseBack(p, direct) {
	return [["Purchase", () => go(direct ? "purchase-direct" : "purchase", "purchase")], [pLabel(p), () => viewStages(p, direct)]];
}

async function viewStages(p, direct) {
	S.here = () => viewStages(p, direct);
	setMenu("purchase");
	crumbs([["Purchase", () => go(direct ? "purchase-direct" : "purchase", "purchase")], [pLabel(p), null]]);
	loading();
	const d = await call("purchase_stages", { project: p.name });
	const stages = d.stages || [];
	let h = `<h2 class="t">${esc(pLabel(p))} — pick the stage</h2>
		<div class="sub">${direct ? "A blank purchase bill opens with project and stage filled in." :
			d.boq ? "Click a stage to see its BOQ items not yet bought. Use “Direct bill” for anything outside the BOQ." :
			"This project has no Project BOQ yet, so bills open blank with project and stage filled in."}</div>`;
	h += `<div class="cards">`;
	if (!direct && d.boq) {
		h += `<div class="card" data-act="boq" data-p="${esc(p.name)}" data-stage=""><div class="n">All stages</div><div class="c">Whole BOQ ${esc(d.boq)}</div></div>`;
	}
	stages.forEach((s) => {
		const useBoq = !direct && s.from_boq;
		h += `<div class="card" data-act="${useBoq ? "boq" : "direct-pi"}" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">
			<div class="n">${esc(s.stage)}</div>
			<div class="c">${s.from_boq ? s.lines + " BOQ line(s) · material " + money(s.material) : "not in BOQ"}</div>
			<div class="f"><span>bought</span><b>${money(s.purchased)}</b></div>
			${s.material ? progress(s.purchased, s.material, s.purchased > s.material ? "over" : "") : ""}
			<div class="f"><span>${s.bills} bill(s)</span>${useBoq ? `<a data-act="direct-pi" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">Direct bill</a>` : `<span class="pill blue">blank bill</span>`}</div>
		</div>`;
	});
	h += `<div class="card" data-act="direct-pi" data-p="${esc(p.name)}" data-stage=""><div class="n">No stage</div>
		<div class="c">General purchase for this project</div>
		<div class="f"><span>${(d.no_stage || {}).bills || 0} bill(s)</span><b>${money((d.no_stage || {}).purchased)}</b></div></div>`;
	h += `</div>`;
	if (!stages.length) h += `<div class="hint">No stages found for this project (from its BOQ or tasks).</div>`;
	showView(h);
}

async function viewBoq(p, stage) {
	S.here = () => viewBoq(p, stage);
	setMenu("purchase");
	const back = purchaseBack(p, false);
	crumbs(back.concat([[stage || "All stages", null]]));
	loading();
	const d = await call("boq_pending", { project: p.name, stage: stage });
	S.boq = { p: p, stage: stage, cc: d.cost_center, company: d.company || p.company || S.company, rows: d.rows || [] };
	const open = S.boq.rows.filter((r) => r.pending > 0.0005);
	const closed = S.boq.rows.filter((r) => r.pending <= 0.0005);
	const row = (r, i, on) => `<tr class="${on ? "" : "off"}">
		<td><input type="checkbox" class="b-pick" data-i="${i}" ${on ? "checked" : ""}></td>
		<td><b>${esc(r.item_name)}</b><div class="muted">${esc(r.item_code)}${r.activities ? " · " + esc(r.activities).slice(0, 80) : ""}</div></td>
		<td>${esc(r.uom)}</td><td class="r">${num(r.required)}</td><td class="r">${num(r.purchased)}</td>
		<td class="r">${r.in_draft ? `<span class="pill orange">${num(r.in_draft)}</span>` : "0"}</td><td class="r"><b>${num(r.pending)}</b></td>
		<td class="r"><input class="q b-qty" data-i="${i}" type="number" step="any" min="0" value="${on ? Math.round(r.pending * 1000) / 1000 : ""}"></td>
		<td class="r"><input class="q b-rate" data-i="${i}" type="number" step="any" min="0" value="${r.rate || ""}"></td></tr>`;
	let h = `<h2 class="t">${esc(pLabel(p))} · ${esc(stage || "All stages")}</h2>
		<div class="sub">BOQ materials still to buy (needed − already on purchase bills). Tick, adjust quantity or rate, then create the bill.
		The supplier and bill number are filled in on the bill.</div>
		<div class="bar"><button class="btn pri" data-act="make-pi">Create purchase bill with ticked items</button>
		<button class="btn" data-act="direct-pi" data-p="${esc(p.name)}" data-stage="${esc(stage)}">Direct bill (not from BOQ)</button>
		<span class="muted" id="b-total"></span></div>`;
	if (!d.boq) h += `<div class="warn">No Project BOQ for this project. Import the BOQ, or use Direct bill.</div>`;
	if (S.boq.rows.length) {
		h += `<div class="box"><table><thead><tr><th><input type="checkbox" id="b-all" checked></th><th>Item</th><th>Unit</th><th class="r">Needed</th><th class="r">Bought</th>
			<th class="r">In draft bills</th><th class="r">To buy</th><th class="r">Qty on this bill</th><th class="r">Rate</th></tr></thead><tbody>`;
		S.boq.rows.forEach((r, i) => { if (r.pending > 0.0005) h += row(r, i, true); });
		h += `</tbody></table>${!open.length ? `<div class="hint">Everything in the BOQ for this stage is already on purchase bills.</div>` : ""}</div>`;
		if (closed.length) {
			h += `<details><summary>${closed.length} item(s) already fully bought</summary><div class="box"><table><tbody>`;
			S.boq.rows.forEach((r, i) => { if (r.pending <= 0.0005) h += row(r, i, false); });
			h += `</tbody></table></div></details>`;
		}
	} else if (d.boq) {
		h += `<div class="hint">No material items are linked to the BOQ activities for this stage (Site Activity → resources → item).</div>`;
	}
	if ((d.other || []).length) {
		h += `<details><summary>${d.other.length} other BOQ line(s) (typed lines, subcontract, labour, equipment) \u2014 buy these with a direct bill</summary><div class="box"><table>
			<thead><tr><th>Activity</th><th>Unit</th><th class="r">Qty</th><th class="r">Subcontract</th><th class="r">Labour</th><th class="r">Equipment</th><th class="r">Amount</th></tr></thead><tbody>`;
		d.other.forEach((o) => {
			h += `<tr><td>${esc(o.description || o.activity)}${o.type ? ` <span class="pill">${esc(o.type)}</span>` : ""}</td><td>${esc(o.unit)}</td><td class="r">${num(o.qty)}</td><td class="r">${money(o.subcontract_amount)}</td>
				<td class="r">${money(o.labour_amount)}</td><td class="r">${money(o.equipment_amount)}</td><td class="r">${money(o.amount)}</td></tr>`;
		});
		h += `</tbody></table></div></details>`;
	}
	showView(h);
	boqTotal();
}

function boqTotal() {
	let t = 0, n = 0;
	R.querySelectorAll(".b-pick:checked").forEach((c) => {
		const i = c.dataset.i;
		const qv = Number((R.querySelector(`.b-qty[data-i="${i}"]`) || {}).value || 0);
		const rv = Number((R.querySelector(`.b-rate[data-i="${i}"]`) || {}).value || 0);
		if (qv > 0) { t += qv * rv; n++; }
	});
	const el = q("#b-total");
	if (el) el.textContent = n ? n + " item(s), about " + money(t) + " before tax" : "";
}

function purchaseValues(p, stage, company) {
	const v = { company: company || p.company || S.company, project: p.name, sbi_stage: stage };
	return v;
}

async function makePurchaseFromBoq() {
	const b = S.boq;
	const items = [];
	R.querySelectorAll(".b-pick:checked").forEach((c) => {
		const i = Number(c.dataset.i);
		const qv = Number((R.querySelector(`.b-qty[data-i="${i}"]`) || {}).value || 0);
		const rv = Number((R.querySelector(`.b-rate[data-i="${i}"]`) || {}).value || 0);
		if (qv > 0) items.push({ item_code: b.rows[i].item_code, qty: qv, rate: rv });
	});
	if (!items.length) { frappe.msgprint(__("Tick at least one item with a quantity.")); return; }
	await frameNew("Purchase Invoice", purchaseValues(b.p, b.stage, b.company), async (frm, w) => {
		if (b.stage && frm.fields_dict.sbi_project_stage) {
			const ok = await w.frappe.db.exists("Project Stage", b.stage);
			if (ok) await frm.set_value("sbi_project_stage", b.stage);
		}
		frm.clear_table("items");
		frm.refresh_field("items");
		for (const it of items) {
			const row = frm.add_child("items");
			await w.frappe.model.set_value(row.doctype, row.name, "item_code", it.item_code);
			try { await waitFor(() => row.item_name && row.uom, 6000); } catch (e) { /* carry on */ }
			const vals = { qty: it.qty, project: b.p.name };
			if (it.rate) vals.rate = it.rate;
			if (b.cc) vals.cost_center = b.cc;
			await w.frappe.model.set_value(row.doctype, row.name, vals);
		}
		frm.refresh_field("items");
		frm.scroll_to_field && frm.scroll_to_field("supplier");
		w.frappe.show_alert({ message: __("Fill in the supplier and bill number, then Save."), indicator: "blue" }, 6);
	}, purchaseBack(b.p, false).concat([[b.stage || "All stages", () => viewBoq(b.p, b.stage)]]));
}

async function directPurchase(p, stage, direct) {
	setMenu("purchase");
	await frameNew("Purchase Invoice", purchaseValues(p, stage), async (frm, w) => {
		if (stage && frm.fields_dict.sbi_project_stage) {
			const ok = await w.frappe.db.exists("Project Stage", stage);
			if (ok) await frm.set_value("sbi_project_stage", stage);
		}
		(frm.doc.items || []).forEach((r) => { if (!r.project) r.project = p.name; });
		frm.refresh_field("items");
	}, purchaseBack(p, direct));
}

// ------------------------------------------------------------------ CASH FLOW
async function viewCash(p, mode) {
	S.here = () => viewCash(p, mode);
	setMenu("cash");
	crumbs([["Cash Flow", () => go("cash-give", "cash")], [pLabel(p), null]]);
	loading();
	const s = await call("project_cash", { project: p.name });
	const today = frappe.datetime.get_today();
	let h = `<h2 class="t">${esc(pLabel(p))} — site cash</h2><div class="sub">&nbsp;</div>
		<div class="tiles">
			<div class="tile"><div class="l">Cash given to site</div><div class="v">${money(s.given)}</div></div>
			<div class="tile"><div class="l">Spent from site cash</div><div class="v">${money(s.spent)}</div></div>
			<div class="tile"><div class="l">Cash with site</div><div class="v ${s.balance < 0 ? "neg" : ""}">${money(s.balance)}</div></div>
			<div class="tile"><div class="l">Expenses paid by office</div><div class="v">${money(s.office)}</div></div>
			<div class="tile"><div class="l">Petty cash vouchers</div><div class="v">${money(s.petty)}</div></div></div>
		<div class="forms">
			<div class="fm ${mode === "give" ? "hl" : ""}"><div class="t">Give cash to site</div><div class="g">
				<input type="date" id="c-date" value="${today}"><input type="number" id="c-amount" placeholder="Amount" min="0" step="0.01">
				<input type="text" id="c-who" placeholder="Received by" class="full"><input type="text" id="c-remarks" placeholder="Remarks" class="full"></div>
				<button class="btn pri" data-act="add-cash" data-p="${esc(p.name)}">Save</button></div>
			<div class="fm ${mode === "expense" ? "hl" : ""}"><div class="t">Site expense</div><div class="g">
				<input type="date" id="e-date" value="${today}"><input type="number" id="e-amount" placeholder="Amount" min="0" step="0.01">
				<select id="e-cat"><option>Transport</option><option>Equipment</option><option>Subcontract</option><option>Other</option></select>
				<select id="e-src"><option value="Site Cash">Paid from site cash</option><option value="Office">Paid by office</option></select>
				<input type="text" id="e-party" placeholder="Paid to" class="full"><input type="text" id="e-desc" placeholder="What for" class="full"></div>
				<button class="btn pri" data-act="add-expense" data-p="${esc(p.name)}">Save</button></div></div>`;
	if ((s.recent || []).length) {
		h += `<div class="box"><h3>Latest entries</h3><table><thead><tr><th>Date</th><th>Entry</th><th>Type</th><th>Person / party</th><th>Note</th><th class="r">Amount</th></tr></thead><tbody>`;
		s.recent.forEach((r) => {
			h += `<tr class="click" data-act="open" data-dt="${esc(r.dt)}" data-name="${esc(r.name)}"><td>${dt(r.d)}</td><td>${esc(r.name)}${r.je ? ` <span class="pill">Tally</span>` : ""}</td>
				<td>${esc(r.kind)}</td><td>${esc(r.who)}</td><td>${esc((r.note || "").split("\n")[0].slice(0, 80))}</td><td class="r">${money(r.amount)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
	const f = q(mode === "expense" ? "#e-amount" : "#c-amount");
	if (f) f.focus();
}

function periodRange(p) {
	const t = new Date();
	const y = t.getFullYear(), m = t.getMonth();
	const d = (Y, M, D) => frappe.datetime.obj_to_str(new Date(Y, M, D));
	const fy = m >= 3 ? y : y - 1;
	const qs = Math.floor(m / 3) * 3;
	if (p === "month") return [d(y, m, 1), d(y, m + 1, 0)];
	if (p === "last_month") return [d(y, m - 1, 1), d(y, m, 0)];
	if (p === "quarter") return [d(y, qs, 1), d(y, qs + 3, 0)];
	if (p === "last_quarter") return [d(y, qs - 3, 1), d(y, qs, 0)];
	if (p === "last_fy") return [d(fy - 1, 3, 1), d(fy, 3, 0)];
	if (p === "custom") return [S.from || d(fy, 3, 1), S.to || d(fy + 1, 3, 0)];
	return [d(fy, 3, 1), d(fy + 1, 3, 0)];
}

function periodBar(extra) {
	const opts = [["month", "This month"], ["last_month", "Last month"], ["quarter", "This quarter"], ["last_quarter", "Last quarter"],
		["fy", "This financial year"], ["last_fy", "Last financial year"], ["custom", "Custom dates"]];
	const r = periodRange(S.period);
	return `<div class="bar"><select id="period">${opts.map((o) => `<option value="${o[0]}" ${S.period === o[0] ? "selected" : ""}>${o[1]}</option>`).join("")}</select>
		<span class="${S.period === "custom" ? "" : "hide"}" id="pcustom"><input type="date" id="pfrom" value="${r[0]}"> to <input type="date" id="pto" value="${r[1]}"></span>
		${extra || ""}</div>`;
}

async function viewTally() {
	S.here = viewTally;
	setMenu("cash");
	crumbs([["Cash Flow", () => go("cash-give", "cash")], ["Import from Tally", null]]);
	S.current = viewTally;
	loading();
	const r = periodRange(S.period);
	const d = await call("tally_cash", { from_date: r[0], to_date: r[1], include_bank: S.includeBank ? 1 : 0 });
	const rows = d.rows || [];
	const plist = projectsForCompany();
	let h = `<h2 class="t">Import from Tally</h2><div class="sub">Tally cash payments that are not yet on a site. Tick them, pick the site, and add.</div>
		${periodBar(`<label class="muted"><input type="checkbox" id="t-bank" ${S.includeBank ? "checked" : ""}> include bank payments</label>`)}
		<div class="bar"><select id="t-project"><option value="">— site / project —</option>${plist.map((p) => `<option value="${esc(p.name)}">${esc(pLabel(p))} (${esc(p.name)})</option>`).join("")}</select>
		<button class="btn pri" data-act="import-tally">Add ticked to this site</button><span class="muted">${rows.length} payment(s)</span></div>`;
	if (rows.length) {
		h += `<div class="box"><table><thead><tr><th><input type="checkbox" id="t-all"></th><th>Date</th><th>Tally voucher</th><th>Paid to</th><th>Narration</th><th class="r">Amount</th><th>Add as</th></tr></thead><tbody>`;
		rows.forEach((x) => {
			h += `<tr><td><input type="checkbox" class="t-pick" data-je="${esc(x.name)}"></td><td>${dt(x.posting_date)}</td>
				<td><a data-act="open" data-dt="Journal Entry" data-name="${esc(x.name)}">${esc(x.tally_voucher || x.name)}</a></td><td>${esc(x.paid_to)}</td>
				<td>${esc((x.remark || "").slice(0, 90))}</td><td class="r">${money(x.amount)}</td>
				<td><select class="t-kind" data-je="${esc(x.name)}"><option value="Cash">Cash given to site</option><option value="Transport">Expense: Transport</option>
				<option value="Equipment">Expense: Equipment</option><option value="Subcontract">Expense: Subcontract</option><option value="Other">Expense: Other</option></select></td></tr>`;
		});
		h += `</tbody></table></div>`;
	} else {
		h += `<div class="hint">No Tally cash payments waiting in this period.</div>`;
	}
	showView(h);
}

// ------------------------------------------------------------------ PROJECTS / SITE SUMMARY
async function summary() {
	const d = await call("projects_summary", {});
	S.summary = d.projects || [];
	return S.summary;
}

async function viewProjects() {
	S.here = viewProjects;
	setMenu("projects");
	crumbs([["Projects", null]], `<a data-act="go" data-go="new:Project">+ New project</a>`);
	S.current = viewProjects;
	loading();
	const list = await summary();
	let h = `<h2 class="t">Projects</h2><div class="sub">Click a project for its full picture and quick actions.</div>
		<input class="search" id="psearch2" placeholder="Search project or customer…"><div class="cards" id="pcards2">`;
	list.forEach((p) => {
		h += `<div class="card ${p.status !== "Open" ? "done" : ""}" data-act="project" data-p="${esc(p.name)}"
				data-s="${esc((p.name + " " + (p.project_name || "") + " " + (p.customer || "")).toLowerCase())}">
			<div class="n">${esc(pLabel(p))}</div><div class="c">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""}${p.current_stage ? " · " + esc(p.current_stage) : ""}</div>
			<div class="f"><span>Value</span><b>${money(p.value)}</b></div>
			${progress(p.billed, p.value)}<div class="f small"><span>billed ${p.value ? Math.round((p.billed || 0) * 100 / p.value) : 0}%</span><span>received ${money(p.received)}</span></div>
			<div class="f"><span>Billed</span><b>${money(p.billed)}</b></div>
			<div class="f"><span>Spent</span><b>${money(p.spent)}</b></div>
			<div class="f"><span>Cash with site</span><b class="${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</b></div>
		</div>`;
	});
	h += `</div>${list.length ? "" : `<div class="hint">No projects.</div>`}`;
	showView(h);
	const s = q("#psearch2");
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		R.querySelectorAll("#pcards2 .card").forEach((c) => c.classList.toggle("hide", !!t && c.dataset.s.indexOf(t) < 0));
	});
}

async function viewProject(name) {
	S.here = () => viewProject(name);
	setMenu("projects");
	const list = S.summary || (await summary());
	const p = list.find((x) => x.name === name) || findProject(name);
	crumbs([["Projects", () => go("projects", "projects")], [pLabel(p), null]]);
	const margin = (p.billed || 0) - (p.spent || 0);
	showView(`<h2 class="t">${esc(pLabel(p))}</h2><div class="sub">${esc(p.name)}${p.customer ? " · " + esc(p.customer) : ""} · ${esc(p.status || "")}</div>
		<div class="tiles">
			<div class="tile"><div class="l">Contract / order value</div><div class="v">${money(p.value)}</div></div>
			<div class="tile"><div class="l">Billed</div><div class="v">${money(p.billed)}</div></div>
			<div class="tile"><div class="l">Received</div><div class="v">${money(p.received)}</div></div>
			<div class="tile"><div class="l">To receive</div><div class="v">${money(p.outstanding)}</div></div>
			<div class="tile"><div class="l">Purchases</div><div class="v">${money(p.purchased)}</div></div>
			<div class="tile"><div class="l">Site + office expenses</div><div class="v">${money((p.site_spent || 0) + (p.office_spent || 0))}</div></div>
			<div class="tile"><div class="l">Cash with site</div><div class="v ${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</div></div>
			<div class="tile"><div class="l">Billed − spent</div><div class="v ${margin < 0 ? "neg" : ""}">${money(margin)}</div></div></div>
		<div class="cards">
			<div class="card" data-act="p-so" data-p="${esc(p.name)}"><div class="n">New sales order</div><div class="c">Lines with area, rate and MS Yes / No</div></div>
			<div class="card" data-act="p-bill" data-p="${esc(p.name)}"><div class="n">Bill a milestone</div><div class="c">Sales invoice from the order’s milestones</div></div>
			<div class="card" data-act="p-po" data-p="${esc(p.name)}"><div class="n">New purchase order</div><div class="c">Supplier / subcontractor order with MS lines</div></div>
			<div class="card" data-act="p-buy" data-p="${esc(p.name)}"><div class="n">Purchase from BOQ</div><div class="c">Stage → items not yet bought</div></div>
			<div class="card" data-act="p-cash" data-p="${esc(p.name)}"><div class="n">Site cash</div><div class="c">Give cash, record expenses</div></div>
			<div class="card" data-act="open" data-dt="Project" data-name="${esc(p.name)}"><div class="n">Open project</div><div class="c">Project form, tasks, stages</div></div>
		</div>`);
}

async function viewSites() {
	S.here = viewSites;
	setMenu("site");
	crumbs([["Site Summary", null]]);
	S.current = viewSites;
	loading();
	const list = await summary();
	const tot = { value: 0, billed: 0, received: 0, outstanding: 0, purchased: 0, other: 0, cash: 0 };
	let h = `<h2 class="t">Site summary</h2><div class="sub">All projects of ${esc(S.company || "all companies")}. Click a row for that site.</div>
		<div class="box"><table><thead><tr><th>Project</th><th>Customer</th><th class="r">Value</th><th class="r">Billed</th><th class="r">Received</th>
		<th class="r">To receive</th><th class="r">Purchases</th><th class="r">Site + office exp.</th><th class="r">Cash with site</th><th class="r">Billed − spent</th></tr></thead><tbody>`;
	list.forEach((p) => {
		const other = (p.site_spent || 0) + (p.office_spent || 0);
		const m = (p.billed || 0) - (p.spent || 0);
		tot.value += p.value || 0; tot.billed += p.billed || 0; tot.received += p.received || 0; tot.outstanding += p.outstanding || 0;
		tot.purchased += p.purchased || 0; tot.other += other; tot.cash += p.cash_balance || 0;
		h += `<tr class="click" data-act="project" data-p="${esc(p.name)}"><td><b>${esc(pLabel(p))}</b><div class="muted">${esc(p.name)}</div></td><td>${esc(p.customer)}</td>
			<td class="r">${money(p.value)}</td><td class="r">${money(p.billed)}${p.value ? progress(p.billed, p.value, "thin") : ""}</td><td class="r">${money(p.received)}</td><td class="r">${money(p.outstanding)}</td>
			<td class="r">${money(p.purchased)}</td><td class="r">${money(other)}</td><td class="r ${p.cash_balance < 0 ? "neg" : ""}">${money(p.cash_balance)}</td>
			<td class="r ${m < 0 ? "neg" : ""}">${money(m)}</td></tr>`;
	});
	const tm = tot.billed - tot.purchased - tot.other;
	h += `<tr class="total"><td>Total</td><td></td><td class="r">${money(tot.value)}</td><td class="r">${money(tot.billed)}</td><td class="r">${money(tot.received)}</td>
		<td class="r">${money(tot.outstanding)}</td><td class="r">${money(tot.purchased)}</td><td class="r">${money(tot.other)}</td><td class="r">${money(tot.cash)}</td>
		<td class="r ${tm < 0 ? "neg" : ""}">${money(tm)}</td></tr></tbody></table></div>`;
	showView(h);
}

async function viewCashPosition() {
	S.here = viewCashPosition;
	setMenu("site");
	crumbs([["Site Summary", () => go("sites", "site")], ["Cash with each site", null]]);
	S.current = viewCashPosition;
	loading();
	const d = await call("cash_position", {});
	let h = `<h2 class="t">Cash with each site</h2><div class="sub">Cash given to the site less expenses paid from site cash.</div>
		<div class="box"><table><thead><tr><th>Project</th><th class="r">Given</th><th class="r">Spent from site cash</th><th class="r">Paid by office</th><th class="r">Cash with site</th></tr></thead><tbody>`;
	let t = 0;
	(d.projects || []).forEach((r) => {
		t += r.balance;
		h += `<tr class="click" data-act="p-cash" data-p="${esc(r.project)}"><td>${esc(pLabel(findProject(r.project)))}</td><td class="r">${money(r.given)}</td>
			<td class="r">${money(r.spent)}</td><td class="r">${money(r.office)}</td><td class="r ${r.balance < 0 ? "neg" : ""}">${money(r.balance)}</td></tr>`;
	});
	h += `<tr class="total"><td>Total</td><td></td><td></td><td></td><td class="r">${money(t)}</td></tr></tbody></table></div>`;
	showView(h);
}

// ------------------------------------------------------------------ GST
async function viewGst() {
	S.here = viewGst;
	setMenu("gst");
	crumbs([["GST", null], ["GST to pay", null]]);
	S.current = viewGst;
	if (!S.company) { showView(`<div class="hint">Pick a company (top right). GST is worked out per GSTIN.</div>`); return; }
	loading();
	const r = periodRange(S.period);
	const g = await call("gst", { from_date: r[0], to_date: r[1] });
	let h = `<h2 class="t">GST — ${esc(S.company)}</h2>${periodBar()}`;
	if (!g.accounts) {
		h += `<div class="warn">No GST accounts found for this company. Add them in GST Settings → GST Accounts.</div>
			<button class="btn" data-act="open" data-dt="GST Settings" data-name="GST Settings">Open GST Settings</button>`;
		showView(h);
		return;
	}
	const t = g.total || {};
	h += `<div class="tiles">
		<div class="tile"><div class="l">Output GST (on sales)</div><div class="v">${money(t.output)}</div></div>
		<div class="tile"><div class="l">Input credit (on purchases)</div><div class="v">${money(t.itc)}</div></div>
		<div class="tile"><div class="l">Net GST for the period</div><div class="v ${t.net < 0 ? "neg" : ""}">${money(t.net)}</div></div>
		<div class="tile"><div class="l">GST paid in cash</div><div class="v">${money(t.cash)}</div></div>
		<div class="tile"><div class="l">${g.to_pay >= 0 ? "Balance GST to pay" : "Input credit carried forward"}</div><div class="v ${g.to_pay > 0 ? "neg" : ""}">${money(Math.abs(g.to_pay || 0))}</div></div></div>
		<div class="muted">Balance as on ${dt(r[1])}: output GST ledgers ${money(g.output_balance)} less input credit ${money(g.itc_balance)}.</div>`;
	if ((g.draft_si || 0) + (g.draft_pi || 0)) {
		h += `<div class="warn">${g.draft_si} sales and ${g.draft_pi} purchase invoice(s) in this period are still draft and not counted until submitted.</div>`;
	}
	if ((g.months || []).length) {
		h += `<div class="box" style="margin-top:12px"><h3>Month by month</h3><table><thead><tr><th>Month</th><th class="r">Output GST</th><th class="r">Input credit</th><th class="r">Net</th>
			<th class="r">Set off from credit</th><th class="r">Paid in cash</th></tr></thead><tbody>`;
		g.months.forEach((m) => {
			h += `<tr><td>${moment(m.month + "-01").format("MMM YYYY")}</td><td class="r">${money(m.output)}</td><td class="r">${money(m.itc)}</td>
				<td class="r ${m.net < 0 ? "neg" : ""}">${money(m.net)}</td><td class="r">${money(m.setoff)}</td><td class="r">${money(m.cash)}</td></tr>`;
		});
		h += `<tr class="total"><td>Total</td><td class="r">${money(t.output)}</td><td class="r">${money(t.itc)}</td><td class="r">${money(t.net)}</td>
			<td class="r">${money(t.setoff)}</td><td class="r">${money(t.cash)}</td></tr></tbody></table></div>`;
	} else {
		h += `<div class="hint">No GST postings in this period.</div>`;
	}
	if ((g.heads || []).length) {
		h += `<div class="box"><h3>By tax head</h3><table><thead><tr><th>Head</th><th class="r">Output</th><th class="r">Input credit</th><th class="r">Net</th></tr></thead><tbody>`;
		g.heads.forEach((x) => {
			h += `<tr><td>${esc(x.head)}</td><td class="r">${money(x.output)}</td><td class="r">${money(x.itc)}</td><td class="r ${x.net < 0 ? "neg" : ""}">${money(x.net)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	}
	showView(h);
}

// ------------------------------------------------------------------ HOME
function greet() {
	const h = new Date().getHours();
	return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

async function viewHome() {
	S.here = viewHome;
	S.current = viewHome;
	setMenu("home");
	crumbs([["Home", null]], `<span class="muted">${esc(frappe.datetime.str_to_user(frappe.datetime.get_today()))}</span>`);
	if (!S.company) { showView(`<div class="hint">Pick a company (top right).</div>`); return; }
	loading();
	const fy = periodRange("fy");
	const d = await call("home", { fy_from: fy[0] });
	const k = d.kpi || {};
	const name = (frappe.session.user_fullname || "").split(" ")[0];
	const tile = (label, value, sub, go, cls, icon, tone) => `<div class="tile ti-${tone || "blue"} ${go ? "go" : ""}" ${go ? `data-go="${go}"` : ""}>
		<div class="tic">${ICON(icon || "info")}</div><div class="tbody"><div class="l">${label}</div><div class="v ${cls || ""}">${value}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div></div>`;
	const bankStale = !k.bank_last || k.bank_last < frappe.datetime.get_today();
	let h = `<div class="hero"><div><div class="hero-hi">${greet()}${name ? ", " + esc(name) : ""}</div>
			<div class="hero-sub">${esc(S.company)} \u00b7 ${esc(moment().format ? frappe.datetime.str_to_user(frappe.datetime.get_today()) : "")}</div></div>
			<div class="hero-acts"><a class="hero-btn" data-go="sales" data-m="sales">${ICON("receipt")} Bill a milestone</a>
			<a class="hero-btn" data-go="purchase" data-m="purchase">${ICON("cart")} Purchase from BOQ</a>
			<a class="hero-btn ${bankStale ? "warnb" : ""}" data-go="bank-upload" data-m="bank">${ICON("upload")} Upload bank statement</a></div></div>
		<div class="tiles home">
			${tile("Sales billed this month", money(k.billed_month), "this year " + money(k.billed_fy), "list:Sales Invoice", "", "trend", "blue")}
			${tile("Received this month", money(k.received_month), "from customers", "receive", "", "inbox", "green")}
			${tile("To receive from customers", money(k.receivable), k.receivable_overdue ? `<span class="neg">overdue ${money(k.receivable_overdue)}</span>` : "nothing overdue", "report:Accounts Receivable", "", "clock", "amber")}
			${tile("Purchases this month", money(k.purchased_month), "paid " + money(k.paid_month), "list:Purchase Invoice", "", "cart", "violet")}
			${tile("To pay suppliers", money(k.payable), k.payable_overdue ? `<span class="neg">overdue ${money(k.payable_overdue)}</span>` : "nothing overdue", "report:Accounts Payable", "", "outbox", "red")}
			${tile("Bank and cash balance", money(k.bank_cash), "all bank and cash ledgers", "report:General Ledger", "", "bank", "teal")}
			${tile("Cash with sites", money(k.cash_sites), "given less spent", "cash-position", k.cash_sites < 0 ? "neg" : "", "wallet", "amber")}
			<div class="tile ti-red go" data-go="gst" id="home-gst"><div class="tic">${ICON("percent")}</div><div class="tbody"><div class="l">GST to pay</div><div class="v muted">\u2026</div><div class="s">as on today</div></div></div>
			${tile("Site labour today", String(k.labour_today || 0), "punched in", "hr", "", "users", "teal")}
			${tile("Bank statement uploaded", k.bank_last ? dt(k.bank_last) : "never", (k.bank_to_check || 0) + " entries to check", "bank",
				bankStale ? "neg" : "", bankStale ? "alert" : "check", bankStale ? "red" : "green")}
		</div>
		<div class="two"><div class="box"><h3>${ICON("trend")} Sales vs purchases <span class="muted">last 6 months, before tax</span></h3>
			${barChart(d.months || [], ["sales", "purchases"], ["#c8102e", "#64748b"], ["Sales", "Purchases"])}</div>
		<div class="box"><h3>${ICON("clock")} Money owed, by how late</h3>
			${ageBar("To receive from customers", (d.ageing || {}).receive || {}, "report:Accounts Receivable")}
			${ageBar("To pay suppliers", (d.ageing || {}).pay || {}, "report:Accounts Payable")}</div></div>`;
	if ((k.draft_si || 0) + (k.draft_pi || 0)) {
		h += `<div class="warn">${k.draft_si} sales and ${k.draft_pi} purchase invoice(s) are still draft (for example from Tally) and are not in these figures until submitted.</div>`;
	}
	h += `<div class="qa">${[["cash-give", "Give cash to site", "cash"],
		["cash-expense", "Site expense", "cash"], ["receive", "Receive payment", "sales"], ["pay", "Pay supplier", "purchase"],
		["bank", "Daily bank check", "bank"], ["hr", "Today’s attendance", "hr"], ["sites", "Site summary", "site"]]
		.map((x) => `<a class="qa-i" data-go="${x[0]}" data-m="${x[2]}">${esc(x[1])}</a>`).join("")}</div>`;
	h += `<div class="two"><div class="box"><h3>Milestones to bill <span class="muted">due in the next 30 days or overdue</span></h3>`;
	if ((d.milestones || []).length) {
		const today = frappe.datetime.get_today();
		h += `<table><thead><tr><th>Due</th><th>Project</th><th>Milestone</th><th class="r">Amount</th></tr></thead><tbody>`;
		d.milestones.forEach((m) => {
			const late = String(m.due_date) < today;
			h += `<tr class="click" data-act="p-bill" data-p="${esc(m.project || "")}"><td class="${late ? "neg" : ""}">${dt(m.due_date)}</td>
				<td>${esc(pLabel(findProject(m.project || "")))}<div class="muted">${esc(m.customer)}</div></td>
				<td>${esc(m.stage || m.payment_term)}</td><td class="r">${money(m.payment_amount)}</td></tr>`;
		});
		h += `</tbody></table>`;
	} else {
		h += `<div class="hint">No milestones due in the next 30 days.</div>`;
	}
	h += `</div><div class="box"><h3>Latest invoices</h3><table><thead><tr><th>Invoice</th><th>Party</th><th class="r">Amount</th><th>Status</th></tr></thead><tbody>`;
	const rows = (d.sales || []).map((x) => Object.assign({ dt: "Sales Invoice" }, x))
		.concat((d.purchases || []).map((x) => Object.assign({ dt: "Purchase Invoice" }, x)));
	rows.forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="${x.dt}" data-name="${esc(x.name)}"><td>${esc(x.name)}<div class="muted">${x.dt === "Sales Invoice" ? "Sales" : "Purchase"} · ${dt(x.posting_date)}</div></td>
			<td>${esc(x.party)}${x.project ? `<div class="muted">${esc(pLabel(findProject(x.project)))}</div>` : ""}</td>
			<td class="r">${money(x.grand_total)}</td><td>${statusPill(x.status, x.docstatus)}</td></tr>`;
	});
	if (!rows.length) h += `<tr><td colspan="4" class="hint">No invoices yet.</td></tr>`;
	h += `</tbody></table></div></div>`;
	showView(h);
	// the GST balance is a heavier query - fill it in once the page is showing
	const today = frappe.datetime.get_today();
	call("gst", { from_date: today, to_date: today }).then((g) => {
		const el = q("#home-gst");
		if (!el) return;
		const v = el.querySelector(".v");
		if (!g.accounts) { v.textContent = "not set up"; v.classList.add("muted"); el.querySelector(".s").textContent = "add GST accounts in GST Settings"; return; }
		const tp = g.to_pay || 0;
		el.querySelector(".l").textContent = tp >= 0 ? "GST to pay" : "Input credit carried forward";
		v.className = "v " + (tp > 0 ? "neg" : "");
		v.textContent = money(Math.abs(tp));
	}).catch(() => {});
}

// ------------------------------------------------------------------ HR: attendance for today, a salary month or any dates
const hm = (v) => (v ? String(v).slice(11, 16) : "");
const kmTxt = (m) => (!m ? "" : m >= 1000 ? (Number(m) / 1000).toFixed(2) + " km" : Math.round(m) + " m");
function salaryMonth(startDay, ref, back) {
	// the salary month that contains ref (back = 1 for the month before)
	const sd = Math.min(28, Math.max(1, Number(startDay) || 1));
	const r = frappe.datetime.str_to_obj(ref || frappe.datetime.get_today());
	let y = r.getFullYear(), m = r.getMonth();
	if (sd > 1 && r.getDate() < sd) m -= 1;
	m -= back || 0;
	const s = new Date(y, m, sd);
	const e = new Date(y, m + 1, sd - 1);
	const f = (d) => d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
	return [f(s), f(e)];
}
function hrRange() {
	const P = S.hrP || (S.hrP = { mode: "day", day: frappe.datetime.get_today() });
	const sd = (S.hrSet && S.hrSet.start_day) || 1;
	if (P.mode === "month") return salaryMonth(sd, frappe.datetime.get_today(), 0);
	if (P.mode === "prev") return salaryMonth(sd, frappe.datetime.get_today(), 1);
	if (P.mode === "custom" && P.from && P.to) return [P.from, P.to];
	return [P.day || frappe.datetime.get_today(), P.day || frappe.datetime.get_today()];
}
function hrBar() {
	const P = S.hrP;
	const r = hrRange();
	const sd = (S.hrSet && S.hrSet.start_day) || 1;
	const seg = [["day", "Day"], ["month", "This salary month"], ["prev", "Last salary month"], ["custom", "Custom dates"]]
		.map((x) => `<a class="${P.mode === x[0] ? "on" : ""}" data-act="hr-mode" data-mode="${x[0]}">${x[1]}</a>`).join("");
	let extra = "";
	if (P.mode === "day") extra = `<input type="date" id="hr-date" value="${esc(P.day)}"><button class="btn sm" data-act="hr-today">Today</button>`;
	else if (P.mode === "custom") extra = `<input type="date" id="hr-from" value="${esc(P.from || r[0])}"><span class="muted">to</span><input type="date" id="hr-to" value="${esc(P.to || r[1])}">`;
	else extra = `<span class="pill">${dt(r[0])} – ${dt(r[1])}</span>`;
	return `<div class="bar hrbar"><div class="seg">${seg}</div>${extra}
		<a class="muted" data-act="hr-settings" title="Salary month start day, full / half day hours, office location">⚙ Month settings (starts on day ${sd})</a></div>`;
}

async function viewHr(day) {
	if (day) S.hrP = { mode: "day", day: day };
	if (!S.hrP) S.hrP = { mode: "day", day: frappe.datetime.get_today() };
	S.here = () => viewHr();
	S.current = () => viewHr();
	setMenu("hr");
	crumbs([["HR", null], ["Attendance", null]]);
	loading();
	let r = hrRange();
	let d = await call("hr", { from_date: r[0], to_date: r[1] });
	if (!S.hrSet || Number(S.hrSet.start_day) !== Number((d.settings || {}).start_day)) {
		S.hrSet = d.settings || {};
		const r2 = hrRange();
		if (r2[0] !== r[0] || r2[1] !== r[1]) { r = r2; d = await call("hr", { from_date: r[0], to_date: r[1] }); }
	}
	S.hrSet = d.settings || S.hrSet || {};
	const one = r[0] === r[1];
	const e = d.employees || { status: [] };
	const st = {};
	(e.status || []).forEach((s) => (st[s.status] = s.n));
	const sites = d.sites || [];
	const present = sites.reduce((a, s) => a + (s.present || 0), 0);
	const wage = sites.reduce((a, s) => a + Number(s.wage || 0), 0);
	const outside = sites.reduce((a, s) => a + Number(s.outside || 0), 0);
	const office = d.office || [];
	const offDays = office.reduce((a, o) => a + (o.days || 0), 0);
	const offOut = office.reduce((a, o) => a + (o.outside || 0), 0);
	const inNow = office.filter((o) => o.last_type === "IN").length;
	const p = d.pending || {};
	const period = one ? dt(r[0]) : dt(r[0]) + " – " + dt(r[1]);
	let h = `<h2 class="t">Attendance <span class="muted">${period}</span></h2>${hrBar()}
		<div class="tiles">
			<div class="tile"><div class="l">${one ? "Site labour present" : "Site labour-days"}</div><div class="v">${present}</div><div class="s">${one ? "of " + (d.labour_total || 0) + " active labour" : "worker × days, " + (d.labour_total || 0) + " active labour"}</div></div>
			<div class="tile"><div class="l">Labour wages</div><div class="v">${money(wage)}</div><div class="s">daily wage × days present</div></div>
			<div class="tile"><div class="l">Punched outside the site</div><div class="v ${outside ? "neg" : ""}">${outside}</div><div class="s">outside the geofence</div></div>
			<div class="tile go" data-act="hr-office-all"><div class="l">${one ? "Office staff punched" : "Office staff-days"}</div><div class="v">${offDays}</div>
				<div class="s">of ${e.active || 0} staff${one ? " · in office now " + inNow : ""}${offOut ? ` · <b class="neg">${offOut} outside</b>` : ""}</div></div>
			<div class="tile"><div class="l">Staff attendance marked</div><div class="v">${(st["Present"] || 0) + (st["Work From Home"] || 0)}</div>
				<div class="s">half day ${st["Half Day"] || 0} · leave ${st["On Leave"] || 0} · absent ${st["Absent"] || 0}</div></div>
			<div class="tile go" data-go="list:Leave Application" data-m="hr"><div class="l">Leave to approve</div><div class="v">${p.leave || 0}</div></div>
			<div class="tile go" data-go="list:Expense Claim" data-m="hr"><div class="l">Expense claims open</div><div class="v">${p.expense || 0}</div></div>
			<div class="tile go" data-go="list:Employee Advance" data-m="hr"><div class="l">Advances open</div><div class="v">${p.advance || 0}</div></div>
		</div>`;
	// office staff
	h += `<div class="box"><h3>Office staff <span class="muted">punch IN / OUT with GPS and photo · click a name for every punch</span>
		<a class="muted" data-go="ext:/sbi_office" data-m="hr">Open SBI Office app ↗</a></h3>`;
	if (!d.office_ready) h += `<div class="warn">Run the latest Lite ERP installer once to add the office punch fields.</div>`;
	if (!office.length) h += `<div class="hint">No active employees for this company.</div>`;
	else {
		h += `<table><thead><tr><th>Employee</th>${one ? "<th>In</th><th>Out</th><th>Status</th>" : `<th class="r">Days</th><th class="r">Full</th><th class="r">Half</th><th class="r">Late</th><th class="r">No OUT</th>`}
			<th class="r">Hours</th><th>Location</th></tr></thead><tbody>`;
		office.forEach((o) => {
			const status = !o.punches ? (o.no_login ? `<span class="pill orange">no login</span>` : `<span class="pill">not punched</span>`)
				: o.last_type === "IN" ? `<span class="pill green">in office</span>` : `<span class="pill">left</span>`;
			h += `<tr class="click" data-act="hr-emp" data-e="${esc(o.employee)}"><td><b>${esc(o.employee_name || o.employee)}</b><div class="muted">${esc(o.designation || o.employee)}</div></td>
				${one ? `<td>${esc(o.first_in || "–")}${o.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(o.last_out || "–")}</td><td>${status}</td>`
					: `<td class="r"><b>${o.days || 0}</b></td><td class="r">${o.full || 0}</td><td class="r">${o.half || 0}</td><td class="r ${o.late ? "neg" : ""}">${o.late || 0}</td><td class="r ${o.no_out ? "neg" : ""}">${o.no_out || 0}</td>`}
				<td class="r">${o.hours ? Number(o.hours).toFixed(2) : "–"}</td>
				<td>${o.outside ? `<span class="pill red">${o.outside} outside</span>` : o.punches ? `<span class="pill green">inside</span>` : ""} <span class="muted">${kmTxt(o.max_dist)}</span></td></tr>`;
		});
		h += `</tbody></table>`;
	}
	const sm = salaryMonth((S.hrSet || {}).start_day, r[1], 0);
	h += `<div class="bar"><button class="btn" data-act="hr-mark" data-f="${r[0]}" data-t="${r[1]}" title="Make Attendance records from the punches">Mark staff attendance from punches (${period})</button>
		<button class="btn" data-act="hr-payroll" data-f="${sm[0]}" data-t="${sm[1]}">Run payroll for ${dt(sm[0])} – ${dt(sm[1])}</button></div>
		<div class="muted small">Full day = ${S.hrSet.full_hours || 8} h or more between first IN and last OUT, half day = ${S.hrSet.half_hours || 4} h or more. Days that already have attendance are left alone.</div></div>`;
	// site labour
	if (sites.length) {
		h += `<div class="box"><h3>Site labour ${period} <span class="muted">click a site to see who came</span></h3><table><thead><tr><th>Site</th>
			${one ? "" : `<th class="r">Workers</th>`}<th class="r">${one ? "Present" : "Labour-days"}</th><th class="r">Outside geofence</th><th class="r">Wages</th></tr></thead><tbody>`;
		sites.forEach((s) => {
			h += `<tr class="click" data-act="hr-site" data-p="${esc(s.project || "")}"><td>${esc(pLabel(findProject(s.project || "")))}<div class="muted">${esc(s.project || "No site")}</div></td>
				${one ? "" : `<td class="r">${s.labour || 0}</td>`}<td class="r"><b>${s.present}</b></td><td class="r ${s.outside ? "neg" : ""}">${s.outside || 0}</td><td class="r">${money(s.wage)}</td></tr>`;
		});
		h += `</tbody></table></div>`;
	} else {
		h += `<div class="hint">No site labour punched in for ${period}.</div>`;
	}
	h += `<div class="qa">${[["ext:/sbi_office", "SBI Office punch app"], ["list:Employee Checkin", "Office punches"], ["list:Labour", "Labour register"], ["list:Labour Attendance Log", "Labour punches"],
		["list:Employee", "Employees"], ["list:Attendance", "Staff attendance"], ["list:Salary Slip", "Salary slips"]]
		.map((x) => `<a class="qa-i" data-go="${x[0]}" data-m="hr">${esc(x[1])}</a>`).join("")}</div>`;
	showView(h);
}

async function viewHrSite(projectName) {
	const p = findProject(projectName);
	const r = hrRange();
	const one = r[0] === r[1];
	S.here = () => viewHrSite(projectName);
	setMenu("hr");
	crumbs([["HR", () => viewHr()], ["Attendance", () => viewHr()], [pLabel(p), null]]);
	loading();
	const d = await call("hr_site", { project: projectName, from_date: r[0], to_date: r[1] });
	let h = `<h2 class="t">${esc(pLabel(p))} — ${one ? dt(r[0]) : dt(r[0]) + " – " + dt(r[1])}</h2><div class="sub">${(d.rows || []).length} labour punched.</div>
		<div class="box"><table><thead><tr><th>Labour</th><th>Skill</th>${one ? "" : `<th class="r">Days</th>`}<th>First in</th><th>Last punch</th><th class="r">Punches</th>
		<th>Checked by</th><th>Geofence</th><th class="r">${one ? "Daily wage" : "Wages"}</th></tr></thead><tbody>`;
	(d.rows || []).forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="Labour" data-name="${esc(x.labour)}"><td><b>${esc(x.labour_name || x.labour)}</b><div class="muted">${esc(x.labour)}</div></td>
			<td>${esc(x.skill)}</td>${one ? "" : `<td class="r"><b>${x.days}</b></td>`}<td>${one ? hm(x.first_in) : dt(x.first_in) + " " + hm(x.first_in)}</td><td>${one ? hm(x.last_punch) : dt(x.last_punch) + " " + hm(x.last_punch)} <span class="muted">${esc(x.last_type)}</span></td><td class="r">${x.punches}</td>
			<td>${esc(x.method)}</td><td>${x.in_fence ? `<span class="pill green">inside</span>` : `<span class="pill red">outside</span>`}</td><td class="r">${money((x.wage || 0) * (one ? 1 : x.days || 0))}</td></tr>`;
	});
	h += `</tbody></table></div>`;
	showView(h);
}

async function viewHrEmp(emp) {
	const r = hrRange();
	S.here = () => viewHrEmp(emp);
	setMenu("hr");
	loading();
	const d = await call("hr_office", { employee: emp, from_date: r[0], to_date: r[1] });
	const e = d.employee || { name: emp };
	crumbs([["HR", () => viewHr()], ["Attendance", () => viewHr()], [e.employee_name || emp, null]]);
	const att = {};
	(d.attendance || []).forEach((a) => (att[String(a.attendance_date)] = a));
	const byDay = {};
	(d.punches || []).forEach((x) => { const k = String(x.time).slice(0, 10); (byDay[k] = byDay[k] || []).push(x); });
	const daysList = Object.keys(byDay).sort();
	let h = `<h2 class="t">${esc(e.employee_name || emp)} <span class="muted">${esc(e.designation || "")}</span></h2>
		<div class="sub">${dt(r[0])}${r[0] !== r[1] ? " – " + dt(r[1]) : ""} · ${daysList.length} day(s) with punches · <a data-act="open" data-dt="Employee" data-name="${esc(emp)}">open employee</a></div>`;
	if (!daysList.length) h += `<div class="hint">No punches in this period.</div>`;
	daysList.forEach((k) => {
		const L = byDay[k];
		const fi = L.find((x) => x.log_type === "IN");
		const lo = [...L].reverse().find((x) => x.log_type === "OUT");
		const hrs = fi && lo && lo.time > fi.time ? ((new Date(String(lo.time).replace(" ", "T")) - new Date(String(fi.time).replace(" ", "T"))) / 3600000) : 0;
		const a = att[k];
		h += `<div class="box"><h3>${dt(k)} <span class="muted">${hrs ? hrs.toFixed(2) + " h" : lo ? "" : "no OUT punch"}</span>
			${a ? `<span class="pill ${a.status === "Present" ? "green" : a.status === "Absent" ? "red" : "orange"}">${esc(a.status)}${a.docstatus === 0 ? " (draft)" : ""}</span>` : `<span class="pill">attendance not marked</span>`}</h3>
			<table><thead><tr><th>Punch</th><th>Time</th><th>Distance</th><th>GPS</th><th>Photo</th><th>Note</th></tr></thead><tbody>
			${L.map((x) => `<tr><td><span class="pill ${x.log_type === "IN" ? "green" : "red"}">${esc(x.log_type)}</span></td><td><b>${hm(x.time)}</b></td>
				<td>${x.distance ? kmTxt(x.distance) : "–"} ${x.within === 0 ? `<span class="pill red">outside</span>` : ""}</td>
				<td>${x.address ? `<div>${esc(x.address)}</div>` : ""}${x.latitude ? `<a href="https://maps.google.com/?q=${x.latitude},${x.longitude}" target="_blank">map</a> <span class="muted">±${Math.round(x.accuracy || 0)} m</span>` : (x.address ? "" : "–")}</td>
				<td>${x.photo ? `<a href="${esc(x.photo)}" target="_blank"><img class="thumb" src="${esc(x.photo)}" alt=""></a>` : "–"}</td><td class="muted">${esc(x.remarks || "")}</td></tr>`).join("")}
			</tbody></table></div>`;
	});
	showView(h);
}

async function viewHrSettings() {
	S.here = viewHrSettings;
	setMenu("hr");
	crumbs([["HR", () => viewHr()], ["Month & office settings", null]]);
	loading();
	const d = await call("hr", { from_date: frappe.datetime.get_today(), to_date: frappe.datetime.get_today() });
	const s = d.settings || {};
	S.hrSet = s;
	const sd = Number(s.start_day) || 1;
	const ex = salaryMonth(sd, frappe.datetime.get_today(), 0);
	showView(`<h2 class="t">Salary month &amp; office settings</h2>
		<div class="sub">Used for “This salary month” on the attendance page, for marking staff attendance from punches, and for the office punch area.</div>
		<div class="fm"><div class="t"><span class="num">1</span> Salary month</div><div class="g g4">
			<label>Month starts on day<input type="number" id="hs-start" min="1" max="28" value="${sd}"></label>
			<label>Month ends on<input id="hs-end" disabled value="${sd === 1 ? "last day of the month" : "day " + (sd - 1) + " of next month"}"></label>
			<label>Full day (hours)<input type="number" id="hs-full" min="1" step="0.5" value="${s.full_hours || 8}"></label>
			<label>Half day (hours)<input type="number" id="hs-half" min="0.5" step="0.5" value="${s.half_hours || 4}"></label></div>
			<div class="muted small" id="hs-ex">This salary month: ${dt(ex[0])} – ${dt(ex[1])}. Use 1 for the calendar month (1st to last day), or for example 26 for 26th to 25th.</div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Office location (for office staff punch)</div><div class="g g4">
			<label>Office name<input id="hs-oname" value="${esc(s.office_name || "")}" placeholder="e.g. Head office, Chennai"></label>
			<label>Latitude<input id="hs-lat" type="number" step="any" value="${s.office_lat || ""}"></label>
			<label>Longitude<input id="hs-lng" type="number" step="any" value="${s.office_lng || ""}"></label>
			<label>Allowed area (metres)<input id="hs-rad" type="number" min="20" step="10" value="${s.office_radius || 200}"></label></div>
			<div class="bar"><button class="btn sm" data-act="hs-here">📍 Use my current location</button>
			${s.office_lat ? `<a class="muted" href="https://maps.google.com/?q=${s.office_lat},${s.office_lng}" target="_blank">See on map ↗</a>` : ""}
			<span class="muted" id="hs-gps"></span></div>
			<div class="muted small">Stand inside the office when you press “Use my current location”.</div></div>
		<div class="fm"><div class="t"><span class="num">3</span> Office time, punch rules and reminders</div><div class="g g4">
			<label>Office starts at<input id="hs-in" type="time" value="${esc(s.in_time || "09:30")}"></label>
			<label>Office ends at<input id="hs-out" type="time" value="${esc(s.out_time || "18:30")}"></label>
			<label>Late after (minutes of grace)<input id="hs-grace" type="number" min="0" max="240" value="${s.late_grace === undefined ? 10 : s.late_grace}"></label>
			<label>Reminder before (minutes)<input id="hs-rem" type="number" min="0" max="120" value="${s.reminder === undefined ? 15 : s.reminder}"></label></div>
			<label class="chk"><input type="checkbox" id="hs-block" ${Number(s.block_outside) !== 0 ? "checked" : ""}> Allow punch only inside the office area (GPS limit above)</label>
			<div class="muted small">Staff get a reminder ${"<b>"}before office starts and before it ends${"</b>"} if they have not punched yet. Field staff who work outside: tick “Can punch anywhere (SBI Office)” on their Employee record.</div></div>
		<div class="bar"><button class="btn pri big" data-act="hs-save">Save settings</button><button class="btn" data-act="hr-back">Back</button></div>`);
}
function hsExample() {
	const sd = Math.min(28, Math.max(1, Number((q("#hs-start") || {}).value) || 1));
	const ex = salaryMonth(sd, frappe.datetime.get_today(), 0);
	if (q("#hs-end")) q("#hs-end").value = sd === 1 ? "last day of the month" : "day " + (sd - 1) + " of next month";
	if (q("#hs-ex")) q("#hs-ex").innerHTML = `This salary month: ${dt(ex[0])} – ${dt(ex[1])}. Use 1 for the calendar month (1st to last day), or for example 26 for 26th to 25th.`;
}
async function hsSave(btn) {
	btn.disabled = true;
	try {
		await call("hr_settings_save", { start_day: q("#hs-start").value, full_hours: q("#hs-full").value, half_hours: q("#hs-half").value,
			office_name: q("#hs-oname").value, office_lat: q("#hs-lat").value, office_lng: q("#hs-lng").value, office_radius: q("#hs-rad").value,
			in_time: q("#hs-in").value, out_time: q("#hs-out").value, late_grace: q("#hs-grace").value, reminder: q("#hs-rem").value,
			block_outside: q("#hs-block").checked ? 1 : 0 });
		S.hrSet = null;
		frappe.show_alert({ message: __("Settings saved"), indicator: "green" }, 4);
		viewHr();
	} catch (e) { btn.disabled = false; }
}
function hsHere() {
	const el = q("#hs-gps");
	if (!navigator.geolocation) { el.textContent = "No GPS in this browser."; return; }
	el.textContent = "Getting location…";
	navigator.geolocation.getCurrentPosition((p) => {
		q("#hs-lat").value = p.coords.latitude.toFixed(7);
		q("#hs-lng").value = p.coords.longitude.toFixed(7);
		el.textContent = "Location filled (±" + Math.round(p.coords.accuracy) + " m). Click Save settings.";
	}, (e) => { el.textContent = "Could not get location: " + e.message; }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 });
}
async function hrMark(el) {
	const f = el.dataset.f, t = el.dataset.t;
	frappe.confirm(__("Make staff Attendance from office punches for {0} to {1}? Days that already have attendance are skipped.", [dt(f), dt(t)]), async () => {
		frappe.dom.freeze(__("Marking attendance…"));
		try {
			const r = await call("hr_mark_att", { from_date: f, to_date: t });
			frappe.dom.unfreeze();
			frappe.msgprint({ title: __("Attendance marked"), indicator: r.errors && r.errors.length ? "orange" : "green",
				message: `<b>${r.made}</b> made (present ${r.present}, half day ${r.half}). Already marked: ${r.skipped}. No OUT punch: ${r.no_out}. Too short: ${r.short}.`
					+ (r.errors && r.errors.length ? `<br><br>Could not mark:<br>${r.errors.map(esc).join("<br>")}` : "") });
			viewHr();
		} catch (e) { frappe.dom.unfreeze(); }
	});
}

// ------------------------------------------------------------------ MY WORK (every employee) + HR employees / approvals
const ATT_REASON_HINT = {
	"Work From Home": "Worked from home all day",
	"On Duty": "Worked outside the office for the company (site, client, bank…)",
	"Forgot to Punch": "Came to office but missed the punch",
	"Client / Site Visit": "At a client or site the whole day",
	"Official Travel": "Travelling for company work",
	"Training / Meeting Outside": "Training, meeting or exam outside the office",
	"Mobile / GPS Problem": "Phone, camera or GPS did not work",
	"Other": "Write the reason below",
};
const reqPill = (r) => {
	if (r.docstatus === 1) return `<span class="pill green">Approved</span>`;
	if ((r.sbi_status || r.status) === "Rejected") return `<span class="pill red">Rejected</span>`;
	if (r.status === "Approved") return `<span class="pill green">Approved</span>`;
	return `<span class="pill orange">Waiting for HR</span>`;
};
function fileToJpeg(file, max) {
	return new Promise((ok, bad) => {
		const rd = new FileReader();
		rd.onerror = () => bad(new Error("Could not read the photo"));
		rd.onload = () => {
			const img = new Image();
			img.onerror = () => bad(new Error("This file is not a photo"));
			img.onload = () => {
				const k = Math.min(1, (max || 900) / Math.max(img.width, img.height));
				const c = document.createElement("canvas");
				c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
				c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
				ok(c.toDataURL("image/jpeg", 0.85));
			};
			img.src = rd.result;
		};
		rd.readAsDataURL(file);
	});
}
const val = (s) => ((q(s) || {}).value || "").trim();
const avatar = (img, name, cls) => img ? `<img class="av ${cls || ""}" src="${esc(img)}" alt="">`
	: `<span class="av ${cls || ""}">${esc(String(name || "?").trim().slice(0, 1).toUpperCase())}</span>`;

// one month of attendance for an employee (used by "My attendance" and by HR)
function monthHtml(d, hr) {
	const e = d.employee || {};
	const sm = d.summary || {};
	const hol = {};
	(d.holidays || []).forEach((x) => (hol[x.d] = x.description || "Holiday"));
	const lb = d.leave_balance || [];
	const back = Number(S.mBack || 0);
	let h = `<div class="emp-head">${avatar(e.image, e.employee_name, "big")}<div><h2 class="t">${esc(e.employee_name || "")}</h2>
		<div class="sub">${esc([e.employee_number ? "ID " + e.employee_number : "", e.designation, e.department].filter(Boolean).join(" · "))}</div></div>
		<div class="emp-mon"><button class="btn sm" data-act="m-back" data-b="${back + 1}">‹</button><b>${dt(d.from_date)} – ${dt(d.to_date)}</b>
		<button class="btn sm" data-act="m-back" data-b="${Math.max(0, back - 1)}" ${back ? "" : "disabled"}>›</button></div></div>
		<div class="tiles">
			<div class="tile"><div class="l">Days present</div><div class="v">${sm.present || 0}</div><div class="s">punched or marked present</div></div>
			<div class="tile"><div class="l">Hours worked</div><div class="v">${Number(sm.hours || 0).toFixed(1)}</div><div class="s">first IN to last OUT</div></div>
			<div class="tile"><div class="l">Late days</div><div class="v ${sm.late ? "neg" : ""}">${sm.late || 0}</div><div class="s">after start time + grace</div></div>
			<div class="tile"><div class="l">Leave left</div><div class="v">${lb.reduce((a, x) => a + Number(x.left || 0), 0)}</div>
				<div class="s">${lb.length ? lb.map((x) => esc(x.leave_type) + " " + Number(x.left)).join(" · ") : "no leave allocated"}</div></div>
		</div>`;
	if (!hr) h += `<div class="bar"><a class="btn pri" href="/sbi_office">${ICON("clock")} Punch IN / OUT</a>
		<button class="btn" data-go="me-att" data-m="me">Attendance request</button><button class="btn" data-go="me-leave" data-m="me">Leave request</button></div>`;
	if (hr && e.sbi_face_front) h += `<div class="box"><h3>Face record <span class="muted">taken in SBI Office at the first punch</span></h3><div class="faces">
		${["sbi_face_front", "sbi_face_left", "sbi_face_right"].map((k) => e[k] ? `<a href="${esc(e[k])}" target="_blank"><img src="${esc(e[k])}" alt=""></a>` : "").join("")}</div></div>`;
	// day by day
	h += `<div class="box"><h3>Day by day <span class="muted">tap a day to see each punch with photo and place</span></h3>`;
	const days = d.days || [];
	if (!days.length) h += `<div class="hint">No punches or attendance in this month yet.</div>`;
	else {
		h += `<table class="mday"><thead><tr><th>Date</th><th>In</th><th>Out</th><th class="r">Hours</th><th>Status</th></tr></thead><tbody>`;
		days.forEach((x, i) => {
			const st = x.att ? `<span class="pill ${/Present|Work/.test(x.att) ? "green" : /Absent/.test(x.att) ? "red" : "orange"}">${esc(x.att)}</span>`
				: x.first_in ? (x.last_out ? `<span class="pill">punched</span>` : `<span class="pill orange">no OUT</span>`) : "";
			h += `<tr class="click" data-act="m-day" data-i="${i}"><td><b>${dt(x.d)}</b> <span class="muted">${esc(frappe.datetime.str_to_obj(x.d).toLocaleDateString("en-IN", { weekday: "short" }))}</span>
				${hol[x.d] ? `<div class="muted">${esc(hol[x.d])}</div>` : ""}</td>
				<td>${esc(x.first_in || "–")}${x.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(x.last_out || "–")}</td>
				<td class="r">${x.hours ? Number(x.hours).toFixed(2) : "–"}</td><td>${st}${x.outside ? ` <span class="pill red">${x.outside} outside</span>` : ""}</td></tr>
				<tr class="mpun hide" data-day="${i}"><td colspan="5">${(x.punches || []).map((p) => `<div class="pun">
					${p.photo ? `<a href="${esc(p.photo)}" target="_blank"><img src="${esc(p.photo)}" alt=""></a>` : `<span class="nophoto">no photo</span>`}
					<div><span class="pill ${p.log_type === "IN" ? "green" : "red"}">${esc(p.log_type)}</span> <b>${esc(p.t)}</b>
					${p.distance ? ` <span class="muted">${kmTxt(p.distance)} from office</span>` : ""}${p.within === 0 ? ` <span class="pill red">outside</span>` : ""}
					<div class="muted">${esc(p.address || "")}</div>
					${p.latitude ? `<a href="https://maps.google.com/?q=${p.latitude},${p.longitude}" target="_blank">See on map ↗</a> <span class="muted">±${Math.round(p.accuracy || 0)} m</span>` : ""}
					${p.remarks ? `<div class="muted">Reason: ${esc(p.remarks)}</div>` : ""}</div></div>`).join("") || `<span class="muted">No punches – ${esc(x.att || "")}</span>`}</td></tr>`;
		});
		h += `</tbody></table>`;
	}
	h += `</div>`;
	h += reqTables(d, !hr);
	if ((d.slips || []).length) {
		h += `<div class="box"><h3>Salary slips</h3><table><thead><tr><th>Month</th><th class="r">Net pay</th><th></th></tr></thead><tbody>
			${d.slips.map((s) => `<tr><td>${dt(s.start_date)} – ${dt(s.end_date)}</td><td class="r"><b>${money(s.net_pay)}</b></td>
				<td class="r"><a href="/printview?doctype=Salary%20Slip&name=${encodeURIComponent(s.name)}&trigger_print=0" target="_blank">View / print ↗</a></td></tr>`).join("")}</tbody></table></div>`;
	}
	return h;
}
function attTable(ar, mine) {
	let h = `<div class="box"><h3>Attendance requests ${mine ? `<a class="muted" data-go="me-att" data-m="me">+ New request</a>` : ""}</h3>`;
	h += ar.length ? `<table><thead><tr><th>Dates</th><th>Reason</th><th>Status</th>${mine ? "<th></th>" : ""}</tr></thead><tbody>${ar.map((r) => `<tr>
		<td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}${r.half_day ? " <span class='muted'>(half day)</span>" : ""}</td>
		<td><b>${esc(r.reason)}</b><div class="muted">${esc(r.explanation)}</div>${r.hr_remarks ? `<div class="muted">HR: ${esc(r.hr_remarks)}</div>` : ""}</td><td>${reqPill(r)}</td>
		${mine ? `<td class="r">${r.docstatus === 0 && r.sbi_status !== "Rejected" ? `<a data-act="me-withdraw" data-k="att" data-n="${esc(r.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table>`
		: `<div class="hint">No attendance requests.</div>`;
	return h + `</div>`;
}
function leaveTable(lv, mine) {
	let h = `<div class="box"><h3>Leave requests ${mine ? `<a class="muted" data-go="me-leave" data-m="me">+ New leave</a>` : ""}</h3>`;
	h += lv.length ? `<table><thead><tr><th>Dates</th><th>Leave</th><th class="r">Days</th><th>Status</th>${mine ? "<th></th>" : ""}</tr></thead><tbody>${lv.map((r) => `<tr>
		<td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}</td><td><b>${esc(r.leave_type)}</b><div class="muted">${esc(r.description)}</div></td>
		<td class="r">${Number(r.total_leave_days || 0)}</td><td>${reqPill(r)}</td>
		${mine ? `<td class="r">${r.docstatus === 0 && r.status === "Open" ? `<a data-act="me-withdraw" data-k="leave" data-n="${esc(r.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table>`
		: `<div class="hint">No leave requests.</div>`;
	return h + `</div>`;
}
function reqTables(d, mine) {
	let h = attTable(d.att_requests || [], mine) + leaveTable(d.leaves || [], mine);
	const ch = d.changes || [];
	if (ch.length) h += `<div class="box"><h3>Changes to details</h3><table><tbody>${ch.map((c) => `<tr><td>${dt(c.creation)}</td><td>${esc(c.summary)}${c.hr_remarks ? `<div class="muted">HR: ${esc(c.hr_remarks)}</div>` : ""}</td>
		<td>${c.status === "Pending" ? `<span class="pill orange">Waiting for HR</span>` : c.status === "Approved" ? `<span class="pill green">Approved</span>` : `<span class="pill red">Rejected</span>`}</td>
		${mine ? `<td class="r">${c.status === "Pending" ? `<a data-act="me-withdraw" data-k="change" data-n="${esc(c.name)}">Withdraw</a>` : ""}</td>` : ""}</tr>`).join("")}</tbody></table></div>`;
	return h;
}

async function viewMe() {
	S.here = viewMe; S.current = viewMe;
	setMenu("me");
	crumbs([["My work", null], ["My attendance", null]]);
	loading();
	S.mData = await call("me_home", { back: S.mBack || 0 });
	showView(monthHtml(S.mData, false));
}
async function meData() {
	if (!S.mData) S.mData = await call("me_home", { back: 0 });
	return S.mData;
}
async function viewMeAtt() {
	S.here = viewMeAtt; S.current = viewMeAtt;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["Attendance request", null]]);
	loading();
	S.mBack = 0; S.mData = null;
	const d = await meData();
	const reasons = d.att_reasons || ["Work From Home", "On Duty"];
	const today = frappe.datetime.get_today();
	showView(`<h2 class="t">Attendance request</h2>
		<div class="sub">Use this when you could not punch in SBI Office – HR will check and approve. Approved days count as present.</div>
		<div class="fm"><div class="t"><span class="num">1</span> Which day(s)</div><div class="g g4">
			<label>From<input type="date" id="ar-from" value="${today}" max="${frappe.datetime.add_days(today, 30)}"></label>
			<label>To<input type="date" id="ar-to" value="${today}"></label>
			<label class="chk"><input type="checkbox" id="ar-half"> Half day only</label></div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Why</div><div class="opts">${reasons.map((r, i) => `<label class="opt"><input type="radio" name="ar-reason" value="${esc(r)}" ${i === 0 ? "checked" : ""}>
			<b>${esc(r)}</b><span>${esc(ATT_REASON_HINT[r] || "")}</span></label>`).join("")}</div>
			<label>Details (where you were, what work)<textarea id="ar-exp" rows="3" placeholder="e.g. At Velachery site for slab casting with the site engineer"></textarea></label></div>
		<div class="bar"><button class="btn pri big" data-act="ar-save">Send to HR</button></div>
		${attTable(d.att_requests || [], true)}`);
}
async function viewMeLeave() {
	S.here = viewMeLeave; S.current = viewMeLeave;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["Leave request", null]]);
	loading();
	S.mBack = 0; S.mData = null;
	const d = await meData();
	const lb = d.leave_balance || [];
	const types = d.leave_types || [];
	const today = frappe.datetime.get_today();
	showView(`<h2 class="t">Leave request</h2>
		<div class="sub">HR approves your leave. You can withdraw it until it is approved.</div>
		${lb.length ? `<div class="tiles">${lb.map((x) => `<div class="tile"><div class="l">${esc(x.leave_type)}</div><div class="v">${Number(x.left)}</div><div class="s">of ${Number(x.allocated)} · used ${Number(x.used)}</div></div>`).join("")}</div>`
			: `<div class="hint">HR has not given you leave for this year yet. You can still ask for Leave Without Pay.</div>`}
		<div class="fm"><div class="g g4">
			<label>Leave type<select id="lv-type">${types.map((t) => `<option ${lb.length && lb[0].leave_type === t ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>
			<label>From<input type="date" id="lv-from" value="${today}"></label>
			<label>To<input type="date" id="lv-to" value="${today}"></label>
			<label class="chk"><input type="checkbox" id="lv-half"> Half day</label></div>
			<label>Reason<textarea id="lv-desc" rows="2" placeholder="e.g. Family function at native place"></textarea></label></div>
		<div class="bar"><button class="btn pri big" data-act="lv-save">Send to HR</button></div>
		${leaveTable(d.leaves || [], true)}`);
}
async function viewMeProfile() {
	S.here = viewMeProfile; S.current = viewMeProfile;
	setMenu("me");
	crumbs([["My work", () => go("me", "me")], ["My details", null]]);
	loading();
	const d = await call("me_profile");
	const e = d.employee || {};
	S.meNewPhoto = "";
	const inp = (f) => {
		const v = e[f.fieldname] === null || e[f.fieldname] === undefined ? "" : String(e[f.fieldname]);
		if (f.fieldtype === "Select") return `<select data-f="${f.fieldname}"><option></option>${String(f.options).split("\n").filter(Boolean).map((o) => `<option ${o === v ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`;
		if (f.fieldtype === "Date") return `<input type="date" data-f="${f.fieldname}" value="${esc(v)}">`;
		if (/Text/.test(f.fieldtype)) return `<textarea data-f="${f.fieldname}" rows="2">${esc(v)}</textarea>`;
		return `<input data-f="${f.fieldname}" value="${esc(v)}">`;
	};
	showView(`<div class="emp-head">${avatar(e.image, e.employee_name, "big")}<div><h2 class="t">My details</h2>
		<div class="sub">${esc([e.employee_name, e.employee_number ? "ID " + e.employee_number : "", e.designation].filter(Boolean).join(" · "))}</div></div></div>
		${d.pending ? `<div class="warn">You already sent changes that HR has not checked yet. A new change is sent as another request.</div>` : ""}
		<div class="sub">Change what is wrong and press <b>Send to HR</b>. Your details change only after HR approves.</div>
		<div class="fm"><div class="t">Photo</div><div class="bar"><label class="btn">${ICON("upload")} Choose new photo<input type="file" id="me-photo" accept="image/*" class="hide"></label>
			<img id="me-photo-prev" class="av big hide" alt=""></div></div>
		<div class="fm"><div class="g g3">${(d.fields || []).map((f) => `<label>${esc(f.label)}${inp(f)}</label>`).join("")}</div></div>
		<div class="bar"><button class="btn pri big" data-act="me-prof-save">Send to HR</button></div>`);
	S.meOrig = {};
	R.querySelectorAll("[data-f]").forEach((x) => (S.meOrig[x.dataset.f] = x.value));
}
function viewMeSlips() {
	S.mBack = 0;
	viewMe().then(() => { const b = R.querySelectorAll("#view .box h3"); b.forEach((h) => { if (/Salary slips/.test(h.textContent)) h.scrollIntoView({ behavior: "smooth" }); }); });
}
function viewChangePw(first) {
	S.here = () => viewChangePw(first);
	if (!first) { setMenu("me"); crumbs([["My work", () => go("me", "me")], ["Change password", null]]); }
	const html = `<div class="pw-box"><h2 class="t">${first ? "Welcome! Set your own password" : "Change password"}</h2>
		<div class="sub">${first ? "You logged in with the default password. Choose a new one that only you know. After saving you will log in again with your user id and the new password." : "After saving you will log in again with the new password."}</div>
		<div class="fm"><label>New password<input type="password" id="pw1" autocomplete="new-password" placeholder="at least 8 letters and numbers"></label>
		<label>Type it again<input type="password" id="pw2" autocomplete="new-password"></label>
		<label class="chk"><input type="checkbox" id="pw-show"> Show password</label></div>
		<div class="bar"><button class="btn pri big" data-act="pw-save">Save new password</button></div>
		<div class="muted small">Use letters and numbers, for example Ravi@4521. Do not use SBI@2026 again.</div></div>`;
	if (first) {
		q("#lx").insertAdjacentHTML("beforeend", `<div class="pw-cover" id="pw-cover">${html}</div>`);
	} else showView(html);
}
async function pwSave(btn) {
	const a = (q("#pw1") || {}).value || "", b = (q("#pw2") || {}).value || "";
	if (a.length < 8) { frappe.msgprint(__("The new password must have at least 8 letters / numbers.")); return; }
	if (a !== b) { frappe.msgprint(__("The two passwords are not the same.")); return; }
	btn.disabled = true;
	try {
		await call("set_password", { new_password: a });
		frappe.msgprint({ title: __("Password changed"), indicator: "green", message: __("Please log in again with your user id and the new password.") });
		setTimeout(() => {
			frappe.call({ method: "logout" }).always(() => { window.location.href = "/login"; });
		}, 1800);
	} catch (e) { btn.disabled = false; }
}

// ---- HR: dashboard, employees, requests, letters
async function viewHrDash() {
	S.here = viewHrDash; S.current = viewHrDash;
	setMenu("hr");
	crumbs([["HR", null], ["HR dashboard", null]]);
	loading();
	const d = await call("emp_list", { q: "" });
	S.emps = d.employees || [];
	const act = S.emps.filter((e) => e.status === "Active");
	const punched = act.filter((e) => e.first_in || e.last_type);
	const inNow = act.filter((e) => e.last_type === "IN");
	const late = act.filter((e) => e.late);
	const onLeave = act.filter((e) => e.leave);
	const notYet = act.filter((e) => !e.first_in && !e.last_type && !e.leave);
	const p = d.pending || {};
	const pend = (p.att || 0) + (p.leave || 0) + (p.change || 0);
	let h = `<h2 class="t">HR dashboard <span class="muted">${dt(frappe.datetime.get_today())}</span></h2>
		<div class="tiles">
			<div class="tile go" data-act="hd-filter" data-f="all"><div class="l">Total employees</div><div class="v">${act.length}</div><div class="s">active · ${S.emps.length - act.length} left</div></div>
			<div class="tile go" data-act="hd-filter" data-f="present"><div class="l">Present today</div><div class="v">${punched.length}</div><div class="s">in office now ${inNow.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="late"><div class="l">Late today</div><div class="v ${late.length ? "neg" : ""}">${late.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="leave"><div class="l">On leave / request</div><div class="v">${onLeave.length}</div></div>
			<div class="tile go" data-act="hd-filter" data-f="absent"><div class="l">Not punched yet</div><div class="v ${notYet.length ? "neg" : ""}">${notYet.length}</div></div>
			<div class="tile go" data-go="hr-req" data-m="hr"><div class="l">Requests to approve</div><div class="v ${pend ? "neg" : ""}">${pend}</div>
				<div class="s">attendance ${p.att || 0} · leave ${p.leave || 0} · details ${p.change || 0}</div></div>
		</div>
		<div class="bar"><input id="hd-q" placeholder="Search name, ID No. or phone" style="max-width:280px">
			<button class="btn pri" data-act="emp-new">${ICON("plus")} Add employee</button><button class="btn" data-go="hr" data-m="hr">Attendance (day / month)</button>
			<button class="btn" data-go="report:Monthly Attendance Sheet" data-m="hr">Attendance report</button></div>
		<div class="box"><h3>Employees today <span class="muted" id="hd-lbl">all</span> <span class="muted">· tap a name for the month: punches with photo &amp; GPS, leave, requests</span></h3><div id="hd-list"></div></div>`;
	showView(h);
	S.hdFilter = "all";
	hdList();
}
function hdList() {
	const f = S.hdFilter || "all";
	const qq = ((q("#hd-q") || {}).value || "").toLowerCase();
	const L = (S.emps || []).filter((e) => {
		if (qq && (e.employee_name + " " + e.employee_number + " " + e.cell_number + " " + e.name).toLowerCase().indexOf(qq) < 0) return false;
		if (f === "all") return e.status === "Active" || qq;
		if (e.status !== "Active") return false;
		if (f === "present") return e.first_in || e.last_type;
		if (f === "late") return e.late;
		if (f === "leave") return e.leave;
		if (f === "absent") return !e.first_in && !e.last_type && !e.leave;
		return true;
	});
	const lbl = { all: "all", present: "present today", late: "late today", leave: "on leave", absent: "not punched yet" };
	if (q("#hd-lbl")) q("#hd-lbl").textContent = lbl[f] + " (" + L.length + ")";
	q("#hd-list").innerHTML = L.length ? `<table><thead><tr><th>Employee</th><th>ID No.</th><th>In</th><th>Out</th><th>Today</th><th>Login</th><th></th></tr></thead><tbody>
		${L.map((e) => `<tr class="click" data-act="emp-month" data-e="${esc(e.name)}"><td><div class="emp-cell">${avatar(e.image, e.employee_name)}<div><b>${esc(e.employee_name)}</b>
			<div class="muted">${esc(e.designation || "")}${e.status !== "Active" ? " · " + esc(e.status) : ""}</div></div></div></td>
			<td>${esc(e.employee_number || "–")}</td><td>${esc(e.first_in || "–")}${e.late ? ` <span class="pill orange">late</span>` : ""}</td><td>${esc(e.last_out || "–")}</td>
			<td>${e.leave ? `<span class="pill orange">${esc(e.leave)}</span>` : e.last_type === "IN" ? `<span class="pill green">in office</span>` : e.last_type ? `<span class="pill">left</span>` : `<span class="pill red">not punched</span>`}</td>
			<td>${e.username ? `<span class="muted">${esc(e.username)}</span>` : e.user_id ? `<span class="muted">${esc(e.user_id)}</span>` : `<span class="pill orange">no login</span>`}</td>
			<td class="r"><a data-act="emp-edit" data-e="${esc(e.name)}">Edit</a></td></tr>`).join("")}</tbody></table>` : `<div class="hint">Nobody here.</div>`;
}
async function viewEmpMonth(emp) {
	S.here = () => viewEmpMonth(emp); S.current = S.here;
	setMenu("hr");
	loading();
	const d = await call("emp_month", { employee: emp, back: S.mBack || 0 });
	S.mData = d;
	const e = d.employee || {};
	crumbs([["HR", () => viewHrDash()], ["HR dashboard", () => viewHrDash()], [e.employee_name || emp, null]],
		`<a class="hpill" data-act="emp-edit" data-e="${esc(emp)}">Edit employee</a>`);
	showView(monthHtml(d, true));
}
async function viewEmpForm(name) {
	S.here = () => viewEmpForm(name); S.current = S.here;
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], ["Employees", () => viewHrDash()], [name ? "Edit employee" : "Add employee", null]]);
	loading();
	const d = await call("emp_get", { employee: name || "" });
	const e = d.employee || {};
	const L = d.login || {};
	S.empPhoto = "";
	const has = (f) => (d.fields || []).indexOf(f) >= 0;
	const v = (f) => esc(e[f] === null || e[f] === undefined ? "" : e[f]);
	const sel = (f, opts, label, req) => has(f) ? `<label>${label}${req ? " *" : ""}<select id="ef-${f}"><option></option>${opts.map((o) => `<option ${String(e[f] || "") === o ? "selected" : ""}>${esc(o)}</option>`).join("")}</select></label>` : "";
	const inp = (f, label, type, req, ph) => has(f) ? `<label>${label}${req ? " *" : ""}<input id="ef-${f}" type="${type || "text"}" value="${v(f)}" placeholder="${esc(ph || "")}"></label>` : "";
	const ta = (f, label) => has(f) ? `<label>${label}<textarea id="ef-${f}" rows="2">${v(f)}</textarea></label>` : "";
	const mods = [["attendance", "Attendance only", "Punch, my attendance, leave and requests (everyone gets this)"], ["hr", "HR", "Employees, attendance, leave, payroll"],
		["sales", "Sales", "Sales orders and invoices"], ["purchase", "Purchase", "Purchase orders and bills"], ["projects", "Projects", "Projects, BOQ, site cash"],
		["accounts", "Accounts", "Full accounts: cash, bank, GST, Tally"]];
	const on = L.modules || [];
	S.empFields = d.fields || [];
	showView(`<div class="emp-head"><label class="ph-pick">${e.image ? `<img id="ef-prev" class="av big" src="${esc(e.image)}" alt="">` : `<img id="ef-prev" class="av big hide" alt=""><span class="av big" id="ef-noph">${ICON("upload")}</span>`}
		<input type="file" id="ef-photo" accept="image/*" class="hide"><span class="muted small">${e.image ? "Change photo" : "Add photo *"}</span></label>
		<div><h2 class="t">${name ? esc(e.employee_name || name) : "Add employee"}</h2><div class="sub">${name ? esc(name) : "Fill the details, add the photo, and give a login if this person will use the app."}</div></div></div>
		<div class="fm"><div class="t"><span class="num">1</span> Employee</div><div class="g g4">
			${inp("employee_number", "Employee ID No.", "text", 1, "e.g. SBI-045")}${inp("first_name", "First name", "text", 1)}${inp("middle_name", "Middle name")}${inp("last_name", "Last name")}
			${sel("gender", d.genders || ["Male", "Female"], "Gender", 1)}${inp("date_of_birth", "Date of birth", "date", 1)}${inp("date_of_joining", "Date of joining", "date", 1)}
			${sel("company", d.companies || [], "Company", 1)}${sel("designation", d.designations || [], "Designation")}${sel("department", d.departments || [], "Department")}
			${inp("cell_number", "Mobile", "tel")}${inp("personal_email", "Personal e-mail", "email")}${sel("status", ["Active", "Inactive", "Suspended", "Left"], "Status")}
			${inp("relieving_date", "Relieving date", "date")}${inp("reason_for_leaving", "Reason for leaving")}</div></div>
		<div class="fm"><div class="t"><span class="num">2</span> Address, contact &amp; bank</div><div class="g g3">
			${ta("current_address", "Current address")}${ta("permanent_address", "Permanent address")}${sel("blood_group", ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"], "Blood group")}
			${inp("person_to_be_contacted", "Emergency contact name")}${inp("emergency_phone_number", "Emergency phone", "tel")}${inp("relation", "Relation")}
			${inp("bank_name", "Bank name")}${inp("bank_ac_no", "Bank A/c No.")}${inp("ifsc_code", "IFSC")}${inp("ctc", "CTC (yearly)", "number")}</div></div>
		<div class="fm"><div class="t"><span class="num">3</span> Login for Lite ERP and SBI Office</div>
			${L.user ? `<div class="hint">Login: <b>${esc(L.username || L.user)}</b> ${L.enabled ? `<span class="pill green">active</span>` : `<span class="pill red">disabled</span>`}
				${L.must_change ? `<span class="pill orange">must change password at next login</span>` : ""}</div>` : ""}
			<label class="chk"><input type="checkbox" id="ef-login" ${L.user ? "checked" : ""}> ${L.user ? "Keep / update the login" : "Give this employee a login"}</label>
			<div id="ef-login-box" class="${L.user ? "" : "hide"}"><div class="g g4"><label>User id * <input id="ef-uname" value="${esc(L.username || "")}" placeholder="e.g. ravi or sbi045" autocapitalize="off"></label>
				<label>Password<input disabled value="${L.user ? "unchanged" : "SBI@2026 (first login only)"}"></label>
				${L.user ? `<label class="chk"><input type="checkbox" id="ef-reset"> Reset password to SBI@2026</label><label class="chk"><input type="checkbox" id="ef-disable"> Disable login</label>` : ""}</div>
				<div class="t" style="margin-top:8px">Allowed areas * <span class="muted small">choose at least one</span></div>
				<div class="opts">${mods.map((m) => `<label class="opt"><input type="checkbox" class="ef-mod" value="${m[0]}" ${m[0] === "attendance" ? "checked disabled" : on.indexOf(m[0]) >= 0 ? "checked" : ""}><b>${m[1]}</b><span>${m[2]}</span></label>`).join("")}</div>
				<div class="muted small">The person logs in with the user id (not e-mail) and SBI@2026, must set a new password, then logs in again. Lite ERP opens by itself.</div></div></div>
		<div class="bar"><button class="btn pri big" data-act="emp-save" data-e="${esc(name || "")}">Save employee</button>
			${name ? `<button class="btn" data-act="letter" data-f="SBI Appointment Order" data-e="${esc(name)}">Appointment order</button>
			<button class="btn" data-act="letter" data-f="SBI Relieving Order" data-e="${esc(name)}">Relieving order</button>
			<button class="btn" data-act="emp-month" data-e="${esc(name)}">Month attendance</button>
			<button class="btn" data-act="open" data-dt="Employee" data-name="${esc(name)}">Full employee form</button>` : ""}</div>`);
}
async function empSave(btn) {
	const name = btn.dataset.e || "";
	const vals = {};
	(S.empFields || []).forEach((f) => { const x = q("#ef-" + f); if (x) vals[f] = x.value.trim(); });
	const login = q("#ef-login") && q("#ef-login").checked;
	const mods = Array.from(R.querySelectorAll(".ef-mod:checked")).map((x) => x.value);
	if (!vals.employee_number) { frappe.msgprint(__("Employee ID No. is needed.")); return; }
	if (!name && !S.empPhoto) { frappe.msgprint(__("Add the employee photo (tap the round picture).")); return; }
	if (login && !val("#ef-uname")) { frappe.msgprint(__("Type the user id for the login.")); return; }
	if (login && !mods.length) { frappe.msgprint(__("Choose at least one allowed area.")); return; }
	btn.disabled = true;
	try {
		const r = await call("emp_save", { employee: name, values: JSON.stringify(vals), photo: S.empPhoto || "",
			create_login: login ? 1 : 0, username: val("#ef-uname"), modules: JSON.stringify(mods),
			reset_password: q("#ef-reset") && q("#ef-reset").checked ? 1 : 0, disable_login: q("#ef-disable") && q("#ef-disable").checked ? 1 : 0 });
		const L = r.login || {};
		frappe.msgprint({ title: __("Employee saved"), indicator: "green", message: `<b>${esc(r.employee)}</b> saved.` +
			(L.password ? `<br><br>Login user id: <b>${esc(L.username)}</b><br>Password: <b>${esc(L.password)}</b><br>Site: ${esc(window.location.origin)}<br>They must set their own password at the first login.` : "") +
			(L.disabled ? "<br>Login disabled." : "") });
		viewEmpForm(r.employee);
	} catch (e) { btn.disabled = false; }
}
async function viewReqs(tab) {
	S.reqTab = tab || S.reqTab || "att";
	S.here = () => viewReqs(); S.current = S.here;
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], ["Requests to approve", null]]);
	loading();
	const d = await call("req_list");
	const att = d.att || [], lv = d.leave || [], ch = d.change || [];
	const pa = att.filter((r) => r.docstatus === 0 && r.sbi_status !== "Rejected").length;
	const pl = lv.filter((r) => r.docstatus === 0 && r.status === "Open").length;
	const pc = ch.filter((r) => r.status === "Pending").length;
	const tabs = [["att", "Attendance requests", pa], ["leave", "Leave requests", pl], ["change", "Detail changes", pc]];
	let h = `<h2 class="t">Requests to approve</h2><div class="seg">${tabs.map((t) => `<a class="${S.reqTab === t[0] ? "on" : ""}" data-act="req-tab" data-t="${t[0]}">${t[1]}${t[2] ? ` <span class="pill orange">${t[2]}</span>` : ""}</a>`).join("")}</div>`;
	const btns = (k, n, open) => open ? `<div class="req-act"><input class="req-rem" data-n="${esc(n)}" placeholder="Remark (optional)">
		<button class="btn sm pri" data-act="req-do" data-k="${k}" data-n="${esc(n)}" data-do="approve">${ICON("check")} Approve</button>
		<button class="btn sm" data-act="req-do" data-k="${k}" data-n="${esc(n)}" data-do="reject">Reject</button></div>` : "";
	const who = (r) => `<a data-act="emp-month" data-e="${esc(r.employee)}"><b>${esc(r.employee_name || r.employee)}</b></a>`;
	if (S.reqTab === "att") {
		h += att.length ? `<div class="box"><table><thead><tr><th>Employee</th><th>Dates</th><th>Reason</th><th>Status</th><th></th></tr></thead><tbody>${att.map((r) => `<tr>
			<td>${who(r)}<div class="muted">${dt(r.creation)}</div></td><td>${dt(r.from_date)}${r.to_date !== r.from_date ? " – " + dt(r.to_date) : ""}${r.half_day ? " (half)" : ""}</td>
			<td><b>${esc(r.reason)}</b><div class="muted">${esc(r.explanation)}</div>${r.hr_remarks ? `<div class="muted">HR: ${esc(r.hr_remarks)}</div>` : ""}</td><td>${reqPill(r)}</td>
			<td>${btns("att", r.name, r.docstatus === 0 && r.sbi_status !== "Rejected")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="hint">No attendance requests.</div>`;
	} else if (S.reqTab === "leave") {
		h += lv.length ? `<div class="box"><table><thead><tr><th>Employee</th><th>Dates</th><th>Leave</th><th class="r">Days</th><th>Status</th><th></th></tr></thead><tbody>${lv.map((r) => `<tr>
			<td>${who(r)}<div class="muted">${dt(r.creation)}</div></td><td>${dt(r.from_date)}${String(r.to_date) !== String(r.from_date) ? " – " + dt(r.to_date) : ""}</td>
			<td><b>${esc(r.leave_type)}</b><div class="muted">${esc(r.description)}</div></td><td class="r">${Number(r.total_leave_days || 0)}</td><td>${reqPill(r)}</td>
			<td>${btns("leave", r.name, r.docstatus === 0 && r.status === "Open")}</td></tr>`).join("")}</tbody></table></div>` : `<div class="hint">No leave requests.</div>`;
	} else {
		h += ch.length ? ch.map((c) => `<div class="box"><h3>${who(c)} <span class="muted">${dt(c.creation)}</span>
			${c.status === "Pending" ? `<span class="pill orange">Waiting</span>` : c.status === "Approved" ? `<span class="pill green">Approved</span>` : `<span class="pill red">Rejected</span>`}</h3>
			<table><thead><tr><th>Detail</th><th>Now</th><th>New</th></tr></thead><tbody>${(c.items || []).map((x) => `<tr><td>${esc(x.label)}</td><td class="muted">${esc(x.old || "–")}</td><td><b>${esc(x.new || "–")}</b></td></tr>`).join("")}
			${c.new_photo ? `<tr><td>Photo</td><td></td><td><a href="${esc(c.new_photo)}" target="_blank"><img class="thumb" src="${esc(c.new_photo)}" alt=""></a></td></tr>` : ""}</tbody></table>
			${c.hr_remarks ? `<div class="muted">HR: ${esc(c.hr_remarks)}</div>` : ""}${btns("change", c.name, c.status === "Pending")}</div>`).join("") : `<div class="hint">No detail changes.</div>`;
	}
	showView(h);
}
async function reqDo(el) {
	const rem = (R.querySelector(`.req-rem[data-n="${CSS.escape(el.dataset.n)}"]`) || {}).value || "";
	if (el.dataset.do === "reject" && !rem.trim()) { frappe.msgprint(__("Write a remark saying why it is rejected.")); return; }
	el.disabled = true;
	try {
		await call("req_action", { kind: el.dataset.k, name: el.dataset.n, do: el.dataset.do, remarks: rem.trim() });
		frappe.show_alert({ message: el.dataset.do === "approve" ? __("Approved") : __("Rejected"), indicator: el.dataset.do === "approve" ? "green" : "orange" });
		viewReqs();
	} catch (e) { el.disabled = false; }
}
async function pickEmployee(title, next) {
	S.here = () => pickEmployee(title, next);
	setMenu("hr");
	crumbs([["HR", () => viewHrDash()], [title, null]]);
	loading();
	const d = await call("emp_list", { q: "" });
	S.emps = d.employees || [];
	S.onEmp = next;
	showView(`<h2 class="t">${esc(title)}</h2><div class="sub">Pick the employee.</div>
		<div class="bar"><input id="pe-q" placeholder="Search name or ID No." style="max-width:280px"></div><div class="box" id="pe-list"></div>`);
	peList();
}
function peList() {
	const qq = ((q("#pe-q") || {}).value || "").toLowerCase();
	const L = (S.emps || []).filter((e) => !qq || (e.employee_name + " " + e.employee_number + " " + e.name).toLowerCase().indexOf(qq) >= 0);
	q("#pe-list").innerHTML = `<table><tbody>${L.map((e) => `<tr class="click" data-act="pe-pick" data-e="${esc(e.name)}"><td><div class="emp-cell">${avatar(e.image, e.employee_name)}
		<div><b>${esc(e.employee_name)}</b><div class="muted">${esc([e.employee_number, e.designation, e.status !== "Active" ? e.status : ""].filter(Boolean).join(" · "))}</div></div></div></td></tr>`).join("")}</tbody></table>`;
}
function openLetter(fmt, emp) {
	window.open("/printview?doctype=Employee&name=" + encodeURIComponent(emp) + "&format=" + encodeURIComponent(fmt) + "&no_letterhead=0&trigger_print=0", "_blank");
}

// ------------------------------------------------------------------ BANK
const BANK_SHOW = [["check", "To check"], ["matched", "Matched to invoice"], ["noinv", "No invoice (remarked)"], ["all", "All entries"]];

async function bankAccounts() {
	const d = await call("bank_accounts", {});
	S.bankAccounts = d.accounts || [];
	S.bankReasons = d.reasons || [];
	return S.bankAccounts;
}
function accLabel(a) {
	return (a.account_name || a.name) + (a.bank_account_no ? " · " + String(a.bank_account_no).slice(-4).padStart(8, "•") : "");
}

async function viewBankAccounts(mode) {
	mode = mode || "overview";
	S.here = () => viewBankAccounts(mode);
	S.current = () => viewBankAccounts(mode);
	setMenu("bank");
	crumbs([["Bank", null], [mode === "upload" ? "Upload statement — pick the account" : mode === "check" ? "Daily check — pick the account" : "Bank accounts", null]],
		`<a data-act="go" data-go="new:Bank Account">+ Add bank account</a>`);
	loading();
	const list = await bankAccounts();
	const today = frappe.datetime.get_today();
	let h = `<h2 class="t">${mode === "upload" ? "Upload bank statement" : mode === "check" ? "Daily bank check" : "Bank accounts"}</h2>
		<div class="sub">Upload each account’s statement every day, then check every entry against a GST sales or purchase invoice.</div><div class="cards">`;
	list.forEach((a) => {
		const stale = !a.last_upload || String(a.last_upload) < today;
		h += `<div class="card" data-act="${mode === "upload" ? "bank-up" : "bank-chk"}" data-acc="${esc(a.name)}">
			<div class="n">${esc(a.account_name || a.name)}</div><div class="c">${esc(a.bank || "")}${a.bank_account_no ? " · A/c " + esc(a.bank_account_no) : ""}</div>
			<div class="f"><span>Statement up to</span><b>${a.last_date ? dt(a.last_date) : "—"}</b></div>
			<div class="f"><span>Last upload</span><b class="${stale ? "neg" : ""}">${a.last_upload ? dt(a.last_upload) : "never"}</b></div>
			<div class="f"><span>To check</span><b class="${a.to_check ? "neg" : ""}">${a.to_check || 0}</b></div>
			<div class="f"><span>Matched / no invoice</span><b>${a.matched || 0} / ${a.no_invoice || 0}</b></div>
			<div class="acts"><button class="btn sm pri" data-act="bank-up" data-acc="${esc(a.name)}">Upload statement</button>
				<button class="btn sm" data-act="bank-chk" data-acc="${esc(a.name)}">Check entries</button></div>
		</div>`;
	});
	h += `<div class="card" data-act="go" data-go="new:Bank Account"><div class="n">+ Add bank account</div>
		<div class="c">Bank, account number, IFSC and the ledger it posts to</div></div></div>`;
	if (!list.length) h += `<div class="hint">No company bank accounts yet. Add one first (tick “Is Company Account” and pick its bank ledger).</div>`;
	showView(h);
}

function bankGo(mode) {
	return bankAccounts().then((list) => {
		if (list.length === 1) return mode === "upload" ? viewBankUpload(list[0].name) : viewBankCheck(list[0].name);
		return viewBankAccounts(mode);
	});
}

// ---------- reading the statement file
function loadXlsx() {
	if (window.XLSX) return Promise.resolve(window.XLSX);
	const urls = ["https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js",
		"https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"];
	return urls.reduce((p, u) => p.catch(() => new Promise((res, rej) => {
		const s = document.createElement("script");
		s.src = u;
		s.onload = () => (window.XLSX ? res(window.XLSX) : rej(new Error("no XLSX")));
		s.onerror = () => rej(new Error("blocked"));
		document.head.appendChild(s);
	})), Promise.reject(new Error("start")));
}

function parseCsv(text) {
	const rows = [];
	let row = [], cell = "", qd = false;
	for (let i = 0; i < text.length; i++) {
		const ch = text[i];
		if (qd) {
			if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
			else if (ch === '"') qd = false;
			else cell += ch;
		} else if (ch === '"') qd = true;
		else if (ch === "," || ch === "\t" || ch === ";") { row.push(cell); cell = ""; }
		else if (ch === "\n" || ch === "\r") {
			if (ch === "\r" && text[i + 1] === "\n") i++;
			row.push(cell); rows.push(row); row = []; cell = "";
		} else cell += ch;
	}
	if (cell || row.length) { row.push(cell); rows.push(row); }
	return rows;
}

async function readStatement(file) {
	const name = file.name.toLowerCase();
	if (name.endsWith(".csv") || name.endsWith(".txt")) return parseCsv(await file.text());
	let X;
	try { X = await loadXlsx(); }
	catch (e) { throw new Error(__("Could not load the Excel reader. Save the statement as CSV and upload that instead.")); }
	const wb = X.read(await file.arrayBuffer(), { type: "array", cellDates: false });
	let best = [];
	wb.SheetNames.forEach((n) => {
		const rows = X.utils.sheet_to_json(wb.Sheets[n], { header: 1, raw: true, defval: "" });
		if (rows.length > best.length) best = rows;
	});
	return best;
}

const pad2 = (n) => String(n).padStart(2, "0");
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
function parseDate(v) {
	if (v === null || v === undefined || v === "") return "";
	if (typeof v === "number") {
		if (v < 20000 || v > 80000) return "";
		const d = new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000);
		return d.getUTCFullYear() + "-" + pad2(d.getUTCMonth() + 1) + "-" + pad2(d.getUTCDate());
	}
	const s = String(v).trim();
	let m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
	if (m) return m[1] + "-" + pad2(m[2]) + "-" + pad2(m[3]);
	let d, mo, y;
	m = s.match(/^(\d{1,2})[\/\-. ](\d{1,2})[\/\-. ](\d{2,4})/);
	if (m) { d = +m[1]; mo = +m[2]; y = +m[3]; }
	else {
		m = s.match(/^(\d{1,2})[\/\-. ]?([A-Za-z]{3})[A-Za-z]*[\/\-., ]*(\d{2,4})/);
		if (!m) return "";
		d = +m[1]; mo = MONTHS[m[2].toLowerCase()] || 0; y = +m[3];
	}
	if (y < 100) y += 2000;
	if (!mo || mo > 12 || !d || d > 31 || y < 2000 || y > 2100) return "";
	return y + "-" + pad2(mo) + "-" + pad2(d);
}
function parseAmt(v) {
	if (v === null || v === undefined || v === "") return { n: 0, side: "" };
	if (typeof v === "number") return { n: v, side: "" };
	const s = String(v).toLowerCase();
	const side = /\bdr\b|debit/.test(s) ? "dr" : /\bcr\b|credit/.test(s) ? "cr" : "";
	const n = parseFloat(s.replace(/[^0-9.\-]/g, "")) || 0;
	return { n: n, side: side };
}

function findHeader(rows) {
	for (let i = 0; i < Math.min(rows.length, 40); i++) {
		const j = rows[i].map((c) => String(c).toLowerCase()).join("|");
		if (/date/.test(j) && /(withdraw|debit|deposit|credit|amount|\bdr\b|\bcr\b)/.test(j)) return i;
	}
	return 0;
}
function guessMap(head) {
	const H = head.map((x) => String(x).toLowerCase().replace(/\s+/g, " ").trim());
	const find = (re, not) => H.findIndex((x) => re.test(x) && !(not && not.test(x)));
	const first = (...ix) => { for (const i of ix) if (i >= 0) return i; return -1; };
	const m = {
		date: first(find(/(txn|tran|transaction|posting).*date/), find(/^date$/), find(/date/, /value/), find(/date/)),
		description: find(/narration|description|particular|remark|details/),
		reference: find(/ref|chq|cheque|utr|instrument/),
		withdrawal: find(/withdraw|debit|^dr\.?$|dr amount|dr\.? amt/, /dr.?\/.?cr|cr.?\/.?dr/),
		deposit: find(/deposit|credit|^cr\.?$|cr amount|cr\.? amt/, /dr.?\/.?cr|cr.?\/.?dr/),
		amount: find(/^amount|txn amount|transaction amount|^amt/),
		drcr: find(/dr.?\/.?cr|cr.?\/.?dr|^type$|^dr\/cr$/),
		balance: find(/balance|^bal\.?$/),
	};
	if (m.reference === m.description) m.reference = -1;
	return m;
}

// reference number inside the narration (UPI id, NEFT/RTGS UTR, IMPS id) when the bank leaves the ref column empty
function refFromNarration(s) {
	const t = String(s || "");
	const m = t.match(/UPI\/(?:DR|CR)\/(\d{6,})/i) || t.match(/UTR[:\s\-]*([A-Z0-9]{8,})/i) || t.match(/IMPS[A-Z]*[\/\-\s:]*(?:[A-Z0-9]{1,4}[\/\-\s:]+)?(\d{9,})/i) || t.match(/IMPS[A-Z0-9]{0,4}?(\d{9,})/i)
		|| t.match(/(?:NEFT|RTGS)[\/\s\-:]*([A-Z]{4}[A-Z0-9]{8,})/i);
	return m ? m[1] : "";
}

function buildRows(raw, hi, m) {
	const out = [];
	for (let i = hi + 1; i < raw.length; i++) {
		const r = raw[i] || [];
		const date = m.date >= 0 ? parseDate(r[m.date]) : "";
		if (!date) continue;
		let wd = 0, dp = 0;
		if (m.withdrawal >= 0 || m.deposit >= 0) {
			wd = m.withdrawal >= 0 ? Math.abs(parseAmt(r[m.withdrawal]).n) : 0;
			dp = m.deposit >= 0 ? Math.abs(parseAmt(r[m.deposit]).n) : 0;
		} else if (m.amount >= 0) {
			const a = parseAmt(r[m.amount]);
			const t = m.drcr >= 0 ? String(r[m.drcr]).toLowerCase() : a.side;
			if (/dr|debit|withdraw/.test(t) || a.n < 0) wd = Math.abs(a.n); else dp = Math.abs(a.n);
		}
		if (!wd && !dp) continue;
		const desc = m.description >= 0 ? String(r[m.description]).replace(/\s+/g, " ").trim() : "";
		let ref = m.reference >= 0 ? String(r[m.reference]).trim() : "";
		if (!ref || ref === "-" || ref === "0") ref = refFromNarration(desc);
		const balTxt = m.balance >= 0 ? String(r[m.balance]).trim() : "";
		out.push({ date: date, description: desc, reference: ref, withdrawal: Math.round(wd * 100) / 100,
			deposit: Math.round(dp * 100) / 100, balance: balTxt, _bal: balTxt ? parseAmt(balTxt).n : null });
	}
	// Trust the running balance over the Debit/Credit columns (as for City Union Bank):
	// only for a statement in date order, and only where one side is filled in.
	const ordered = out.every((x, i) => !i || out[i - 1].date <= x.date);
	if (ordered && out.filter((x) => x._bal !== null).length > 1) {
		for (let i = 1; i < out.length; i++) {
			const a = out[i - 1], b = out[i];
			if (a._bal === null || b._bal === null || (b.withdrawal && b.deposit)) continue;
			const amt = b.withdrawal || b.deposit;
			const move = Math.round((b._bal - a._bal) * 100) / 100;
			if (Math.abs(Math.abs(move) - amt) > 0.01) continue;
			if (move < 0) { b.withdrawal = amt; b.deposit = 0; } else { b.deposit = amt; b.withdrawal = 0; }
		}
	}
	out.forEach((x) => delete x._bal);
	return out;
}

// A sample statement laid out like City Union Bank's net-banking Excel download
function sampleStatement(a) {
	const t = new Date();
	const d = (k) => { const x = new Date(t.getFullYear(), t.getMonth(), t.getDate() - k); return pad2(x.getDate()) + "/" + pad2(x.getMonth() + 1) + "/" + x.getFullYear(); };
	const lines = [
		[d(3), "NEFT CR-SBIN0001234-ASHOK LEYLAND LTD-UTR:SBIN226313456789", "", "", "3469200.00"],
		[d(3), "UPI/DR/431298765412/SRI BALAJI CEMENT/HDFC/Payment", "", "38500.00", ""],
		[d(2), "CHQ PAID-RK TRANSPORTS", "001234", "17640.00", ""],
		[d(2), "IMPS/P2A/431511223344/RAMESH KUMAR/SITE WAGES", "", "25000.00", ""],
		[d(1), "RTGS CR-HDFC0000060-TVS LOGISTICS PVT LTD-UTR:HDFCR52026111100123", "", "", "490000.00"],
		[d(1), "SMS CHARGES QTR", "", "118.00", ""],
		[d(0), "CASH WITHDRAWAL - SITE PETTY CASH", "", "50000.00", ""],
	];
	let bal = 1250000;
	const rows = lines.map((l) => { bal = bal - (+l[3] || 0) + (+l[4] || 0); return l.concat([bal.toFixed(2)]); });
	const dr = lines.reduce((s, l) => s + (+l[3] || 0), 0), cr = lines.reduce((s, l) => s + (+l[4] || 0), 0);
	return [["CITY UNION BANK LTD"], ["STATEMENT OF ACCOUNT"], [], ["Account Number", String((a && a.bank_account_no) || "510909010012345")],
		["Account Name", String(S.company || "SHIV BHARAT INFRASTRUCTURES")], ["Branch", "CHENNAI"], ["Period", d(3) + " to " + d(0)],
		["Opening Balance", "1250000.00"], [], ["DATE", "DESCRIPTION", "CHEQUE NO", "DEBIT", "CREDIT", "BALANCE"]]
		.concat(rows).concat([["TOTAL", "", "", dr.toFixed(2), cr.toFixed(2), ""]]);
}

async function downloadSample(accName) {
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || {};
	const aoa = sampleStatement(a);
	try {
		const X = await loadXlsx();
		const wb = X.utils.book_new();
		const ws = X.utils.aoa_to_sheet(aoa);
		ws["!cols"] = [{ wch: 12 }, { wch: 62 }, { wch: 12 }, { wch: 14 }, { wch: 14 }, { wch: 16 }];
		X.utils.book_append_sheet(wb, ws, "Statement");
		X.writeFile(wb, "Bank_statement_sample.xlsx");
	} catch (e) {
		const csv = aoa.map((r) => r.map((c) => /[",]/.test(String(c)) ? '"' + String(c).replace(/"/g, '""') + '"' : c).join(",")).join("\n");
		const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
		const link = document.createElement("a");
		link.href = url; link.download = "Bank_statement_sample.csv"; document.body.appendChild(link); link.click(); link.remove();
		setTimeout(() => URL.revokeObjectURL(url), 2000);
	}
}

async function viewBankUpload(accName) {
	S.here = () => viewBankUpload(accName);
	setMenu("bank");
	if (!S.bankAccounts) await bankAccounts();
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || { name: accName };
	crumbs([["Bank", () => viewBankAccounts("overview")], [a.account_name || accName, () => viewBankCheck(accName)], ["Upload statement", null]]);
	S.bu = { acc: accName, raw: null };
	showView(`<h2 class="t">Upload statement — ${esc(a.account_name || accName)}</h2>
		<div class="sub">Download today’s statement from the bank (Excel .xls / .xlsx, or CSV) and choose it here. Entries already uploaded are skipped, so overlapping dates are fine.
		${a.last_date ? " Last statement entry: <b>" + dt(a.last_date) + "</b>." : ""}</div>
		<div class="upgrid">
			<label class="drop" for="bu-file">${ICON("upload")}<b>Choose the statement file</b><span>Excel (.xls, .xlsx) or CSV — or drop it here</span>
				<input type="file" id="bu-file" accept=".xls,.xlsx,.csv,.txt"></label>
			<div class="box howto"><h3>${ICON("info")} Getting the Excel from the bank</h3>
				<ol><li><b>City Union Bank:</b> Net Banking → Accounts → Account Statement → pick the account and dates → Format <b>Excel</b> → Download.</li>
				<li>Other banks: download the statement as Excel or CSV, not PDF.</li>
				<li>Upload it as it is — the bank’s title lines and the TOTAL line are skipped by themselves.</li></ol>
				<button class="btn" data-act="bu-sample" data-acc="${esc(accName)}">${ICON("download")} Download sample Excel</button></div>
		</div>
		<div id="bu-out"></div>`);
}

function buRender() {
	const b = S.bu;
	const head = (b.raw[b.hi] || []).map((h, i) => String(h || "Column " + (i + 1)));
	const fields = [["date", "Date *"], ["description", "Narration"], ["reference", "Cheque / ref no"], ["withdrawal", "Withdrawal (debit)"],
		["deposit", "Deposit (credit)"], ["amount", "Single amount column"], ["drcr", "Dr / Cr column"], ["balance", "Balance"]];
	const sel = (f) => `<select class="bu-map" data-f="${f}"><option value="-1">— none —</option>${head.map((h, i) =>
		`<option value="${i}" ${b.map[f] === i ? "selected" : ""}>${esc(h).slice(0, 40)}</option>`).join("")}</select>`;
	b.rows = buildRows(b.raw, b.hi, b.map);
	const dep = b.rows.reduce((s, r) => s + r.deposit, 0), wd = b.rows.reduce((s, r) => s + r.withdrawal, 0);
	const dates = b.rows.map((r) => r.date).sort();
	let h = `<div class="box"><h3>Columns <span class="muted">found automatically — change any that are wrong</span></h3>
		<div class="bar"><label class="muted">Heading row <input type="number" id="bu-hi" min="1" value="${b.hi + 1}" style="width:70px"></label></div>
		<div class="mapgrid">${fields.map((f) => `<label><span>${f[1]}</span>${sel(f[0])}</label>`).join("")}</div></div>`;
	h += `<div class="tiles"><div class="tile"><div class="l">Entries</div><div class="v">${b.rows.length}</div><div class="s">${dates.length ? dt(dates[0]) + " – " + dt(dates[dates.length - 1]) : ""}</div></div>
		<div class="tile"><div class="l">Money in (deposits)</div><div class="v">${money(dep)}</div></div>
		<div class="tile"><div class="l">Money out (withdrawals)</div><div class="v">${money(wd)}</div></div></div>`;
	if (b.rows.length) {
		h += `<div class="bar"><button class="btn pri" data-act="bu-save">Save ${b.rows.length} entries to ${esc(b.accLabel)}</button></div>
			<div class="box"><table><thead><tr><th>Date</th><th>Narration</th><th>Ref</th><th class="r">Withdrawal</th><th class="r">Deposit</th><th class="r">Balance</th></tr></thead><tbody>`;
		b.rows.slice(0, 25).forEach((r) => {
			h += `<tr><td>${dt(r.date)}</td><td>${esc(r.description).slice(0, 90)}</td><td>${esc(r.reference)}</td>
				<td class="r">${r.withdrawal ? money(r.withdrawal) : ""}</td><td class="r">${r.deposit ? money(r.deposit) : ""}</td><td class="r muted">${esc(r.balance)}</td></tr>`;
		});
		h += `</tbody></table>${b.rows.length > 25 ? `<div class="hint">… and ${b.rows.length - 25} more</div>` : ""}</div>`;
	} else {
		h += `<div class="warn">No entries read. Check the Date column and the Withdrawal / Deposit (or Amount) columns above, and the heading row number.</div>`;
	}
	q("#bu-out").innerHTML = h;
}

async function buFile(file) {
	q("#bu-out").innerHTML = `<div class="hint">Reading ${esc(file.name)}…</div>`;
	try {
		const raw = (await readStatement(file)).filter((r) => r && r.some((c) => String(c).trim() !== ""));
		const hi = findHeader(raw);
		const a = (S.bankAccounts || []).find((x) => x.name === S.bu.acc) || {};
		Object.assign(S.bu, { raw: raw, hi: hi, map: guessMap(raw[hi] || []), accLabel: a.account_name || S.bu.acc });
		buRender();
	} catch (e) {
		q("#bu-out").innerHTML = `<div class="warn">${esc(e.message || e)}</div>`;
	}
}

async function buSave(el) {
	const b = S.bu;
	el.disabled = true;
	frappe.dom.freeze(__("Saving {0} bank entries…", [b.rows.length]));
	try {
		const r = await call("bank_upload", { bank_account: b.acc, rows: JSON.stringify(b.rows) });
		frappe.dom.unfreeze();
		frappe.show_alert({ message: __("{0} new entries saved, {1} already there", [r.made, r.skipped]), indicator: "green" }, 6);
		S.bankAccounts = null;
		viewBankCheck(b.acc);
	} catch (e) {
		frappe.dom.unfreeze();
		el.disabled = false;
	}
}

// ---------- the daily check
async function viewBankCheck(accName, show) {
	show = show || (S.bankShow || "check");
	S.bankShow = show;
	S.bankAcc = accName;
	S.here = () => viewBankCheck(accName, show);
	S.current = () => viewBankCheck(accName, show);
	setMenu("bank");
	if (!S.bankAccounts) await bankAccounts();
	const a = (S.bankAccounts || []).find((x) => x.name === accName) || { name: accName };
	crumbs([["Bank", () => viewBankAccounts("overview")], [a.account_name || accName, null]],
		`<a data-act="bank-up" data-acc="${esc(accName)}">↑ Upload statement</a>`);
	const keepScroll = q("#view").scrollTop;
	if (!S.bankKeep) loading();
	const r = periodRange(S.period);
	const d = await call("bank_list", { bank_account: accName, show: show, from_date: r[0], to_date: r[1] });
	const c = d.counts || {};
	const reasons = d.reasons || S.bankReasons || [];
	let h = `<h2 class="t">Bank check — ${esc(a.account_name || accName)}</h2>
		<div class="sub">For each entry pick the GST invoice it belongs to. If there is no invoice, choose why and write a remark.</div>
		${periodBar(`<select id="bk-acc">${(S.bankAccounts || []).map((x) => `<option value="${esc(x.name)}" ${x.name === accName ? "selected" : ""}>${esc(accLabel(x))}</option>`).join("")}</select>
		<select id="bk-show">${BANK_SHOW.map((s) => `<option value="${s[0]}" ${s[0] === show ? "selected" : ""}>${s[1]}</option>`).join("")}</select>`)}
		<div class="tiles"><div class="tile go" data-act="bk-show" data-show="check"><div class="l">To check</div><div class="v ${c.to_check ? "neg" : ""}">${c.to_check || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="matched"><div class="l">Matched to invoice</div><div class="v">${c.matched || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="noinv"><div class="l">No invoice, remarked</div><div class="v">${c.no_invoice || 0}</div></div>
			<div class="tile go" data-act="bk-show" data-show="all"><div class="l">All entries in period</div><div class="v">${c.total || 0}</div></div></div>`;
	const rows = d.rows || [];
	if (!rows.length) {
		h += `<div class="hint">${show === "check" ? "Nothing left to check in this period. ✔" : "No entries here."}
			${!c.total ? ` <a data-act="bank-up" data-acc="${esc(accName)}">Upload a statement</a>` : ""}</div>`;
	}
	rows.forEach((t) => {
		const inn = Number(t.deposit || 0) > 0;
		const amt = inn ? t.deposit : t.withdrawal;
		h += `<div class="bt ${t.st === "Matched" ? "ok" : t.st ? "nb" : ""}">
			<div class="bt-h"><div class="bt-d">${dt(t.date)}</div>
				<div class="bt-n">${esc(t.description || "(no narration)")}${t.ref ? `<span class="muted"> · ref ${esc(t.ref)}</span>` : ""}</div>
				<div class="bt-m ${inn ? "in" : "outm"}">${inn ? "+ " : "− "}${money(amt)}<span>${inn ? "money in → sales invoice" : "money out → purchase invoice"}</span></div></div>
			<div class="bt-a">`;
		if (t.st === "Matched") {
			const mi = (t.minfo || [])[0] || {};
			h += `<span class="pill green">✔ Matched</span> <a data-act="open" data-dt="${esc(t.mdt)}" data-name="${esc(t.mname)}">${esc(t.mname)}</a>
				<span class="muted">${esc(mi.party || "")}${mi.g ? " · " + money(mi.g) : ""}${mi.project ? " · " + esc(pLabel(findProject(mi.project))) : ""}</span>
				${t.remarks ? `<span class="muted"> · ${esc(t.remarks)}</span>` : ""}
				<button class="btn sm" data-act="bk-undo" data-txn="${esc(t.name)}">Undo</button>`;
		} else if (t.st === "No Invoice") {
			h += `<span class="pill orange">No invoice</span> <b>${esc(t.reason || "")}</b> — ${esc(t.remarks || "")}
				<span class="muted">${t.checked_by ? " · " + esc(t.checked_by) : ""}</span>
				<button class="btn sm" data-act="bk-undo" data-txn="${esc(t.name)}">Undo</button>`;
		} else {
			if ((t.cands || []).length) {
				h += `<div class="bt-c"><span class="muted">Possible invoice:</span>${t.cands.map((x) => `
					<button class="cand" data-act="bk-match" data-txn="${esc(t.name)}" data-dt="${esc(x.doctype)}" data-name="${esc(x.name)}"
						title="${esc(x.note)}"><b>${esc(x.name)}</b> ${esc(x.party || "")} · ${money(x.amount)} · ${dt(x.date)}
						<span class="${x.note.indexOf("exact") === 0 ? "ex" : "nx"}">${esc(x.note)}</span></button>`).join("")}</div>`;
			} else {
				h += `<div class="bt-c"><span class="warn">No ${inn ? "sales" : "purchase"} invoice with this amount.</span></div>`;
			}
			h += `<div class="bt-f">
				<input class="bk-inv" data-txn="${esc(t.name)}" placeholder="Other invoice no.">
				<button class="btn sm" data-act="bk-other" data-txn="${esc(t.name)}">Match</button>
				<span class="sep2">or</span>
				<select class="bk-rsn" data-txn="${esc(t.name)}"><option value="">No invoice — why?</option>${reasons.map((x) => `<option>${esc(x)}</option>`).join("")}</select>
				<input class="bk-rem" data-txn="${esc(t.name)}" placeholder="Remark (what is this entry?)">
				<button class="btn sm pri" data-act="bk-noinv" data-txn="${esc(t.name)}">Save remark</button></div>`;
		}
		h += `</div></div>`;
	});
	showView(h);
	if (S.bankKeep) { q("#view").scrollTop = keepScroll; S.bankKeep = false; }
}

async function bankSet(args) {
	await call("bank_set", args);
	S.bankKeep = true;
	S.bankAccounts = null;
	viewBankCheck(S.bankAcc, S.bankShow);
}

async function viewBankNoInv() {
	S.here = viewBankNoInv;
	S.current = viewBankNoInv;
	setMenu("bank");
	crumbs([["Bank", () => viewBankAccounts("overview")], ["Entries without invoice", null]]);
	loading();
	const r = periodRange(S.period);
	const d = await call("bank_noinv", { from_date: r[0], to_date: r[1] });
	const rows = d.rows || [];
	const tin = rows.reduce((s, x) => s + Number(x.deposit || 0), 0), tout = rows.reduce((s, x) => s + Number(x.withdrawal || 0), 0);
	let h = `<h2 class="t">Bank entries without a GST invoice</h2><div class="sub">Every entry marked “no invoice”, with the reason and remark given.</div>
		${periodBar()}
		<div class="tiles"><div class="tile"><div class="l">Entries</div><div class="v">${rows.length}</div></div>
			<div class="tile"><div class="l">Money in without invoice</div><div class="v">${money(tin)}</div></div>
			<div class="tile"><div class="l">Money out without invoice</div><div class="v">${money(tout)}</div></div></div>
		<div class="box"><table><thead><tr><th>Date</th><th>Bank</th><th>Narration</th><th class="r">In</th><th class="r">Out</th><th>Reason</th><th>Remark</th><th>By</th></tr></thead><tbody>`;
	rows.forEach((x) => {
		h += `<tr class="click" data-act="open" data-dt="Bank Transaction" data-name="${esc(x.name)}"><td>${dt(x.date)}</td><td>${esc(x.bank_account)}</td>
			<td>${esc((x.description || "").slice(0, 70))}</td><td class="r">${x.deposit ? money(x.deposit) : ""}</td><td class="r">${x.withdrawal ? money(x.withdrawal) : ""}</td>
			<td>${esc(x.reason)}</td><td>${esc(x.remarks)}</td><td class="muted">${esc(x.checked_by)}</td></tr>`;
	});
	if (!rows.length) h += `<tr><td colspan="8" class="hint">None in this period.</td></tr>`;
	h += `</tbody></table></div>`;
	showView(h);
}

// ------------------------------------------------------------------ PROJECT BOQ (type or upload, per stage)
const BOQ_TYPES = ["Material", "Manpower", "Equipment", "Transport", "Subcontract", "Other"];
const BOQ_TONE = { Material: "blue", Manpower: "green", Equipment: "amber", Transport: "teal", Subcontract: "violet", Other: "red" };

function boqBack(p) {
	return [["Project BOQ", () => go("boq", "projects")], [pLabel(p), () => viewBoqStages(p)]];
}

async function viewBoqStages(p) {
	S.here = () => viewBoqStages(p);
	setMenu("projects");
	crumbs([["Project BOQ", () => go("boq", "projects")], [pLabel(p), null]]);
	loading();
	const d = await call("boq_stages", { project: p.name });
	const stages = d.stages || [];
	const master = (d.master || []).filter((m) => !stages.some((s) => s.stage === m));
	let h = `<h2 class="t">Project BOQ — ${esc(pLabel(p))}</h2>
		<div class="sub">Pick the milestone / stage, then type the BOQ lines or upload them from Excel.${d.boq ? " BOQ record: " + esc(d.boq) + "." : ""}</div>`;
	if (!stages.length) h += `<div class="warn">This project has no stages yet. Create the first stage below.</div>`;
	h += `<div class="cards">`;
	stages.forEach((s) => {
		h += `<div class="card" data-act="boq-edit" data-p="${esc(p.name)}" data-stage="${esc(s.stage)}">
			<div class="n">${esc(s.stage)}</div><div class="c">${esc(s.source)}</div>
			<div class="f"><span>BOQ lines</span><b>${s.lines}</b></div>
			<div class="f"><span>BOQ value</span><b>${money(s.amount)}</b></div>
			<div class="f"><span></span>${s.lines ? `<span class="pill green">has BOQ</span>` : `<span class="pill orange">no BOQ yet</span>`}</div></div>`;
	});
	h += `<div class="card newstage"><div class="n">${ICON("plus")} New stage</div>
		<div class="c">Pick a standard stage or type a new name</div>
		<select id="ns-pick"><option value="">— standard stages —</option>${master.map((m) => `<option>${esc(m)}</option>`).join("")}</select>
		<input id="ns-name" placeholder="or type a new stage name">
		<button class="btn pri sm" data-act="boq-newstage" data-p="${esc(p.name)}">Create and open</button></div>`;
	h += `</div>`;
	showView(h);
}

async function boqNewStage(el) {
	const p = findProject(el.dataset.p);
	const typed = ((q("#ns-name") || {}).value || "").trim();
	const picked = (q("#ns-pick") || {}).value || "";
	if (!typed && !picked) { frappe.msgprint(__("Pick a standard stage or type a new stage name.")); return; }
	let stage = picked;
	if (typed) {
		const r = await call("boq_add_stage", { stage_name: typed });
		stage = r.stage;
	}
	viewBoqEdit(p, stage);
}

async function viewBoqEdit(p, stage) {
	S.here = () => viewBoqEdit(p, stage);
	setMenu("projects");
	crumbs(boqBack(p).concat([[stage, null]]));
	loading();
	const d = await call("boq_get", { project: p.name, stage: stage });
	S.boqEd = { p: p, stage: stage, boq: d.boq, rows: (d.rows || []).map((r) => Object.assign({}, r)), dirty: false };
	if (!S.boqEd.rows.length) S.boqEd.rows = [boqBlank(1), boqBlank(2), boqBlank(3)];
	boqRender();
}

function boqBlank(n) {
	return { sl: String(n), description: "", type: "Material", unit: "", qty: "", rate: "", remarks: "" };
}

function boqRender() {
	const b = S.boqEd;
	let h = `<h2 class="t">BOQ — ${esc(pLabel(b.p))} · ${esc(b.stage)}</h2>
		<div class="sub">One line per item. Type tells where the cost belongs (material, manpower, equipment, transport, subcontract, other). Rate is optional — with it, the budget by type is worked out.</div>
		<div class="bar">
			<label class="btn">${ICON("upload")} Upload Excel<input type="file" id="boq-file" accept=".xls,.xlsx,.csv,.txt" hidden></label>
			<button class="btn" data-act="boq-sample">${ICON("download")} Download sample Excel</button>
			<button class="btn" data-act="boq-add">${ICON("plus")} Add line</button>
			<button class="btn pri" data-act="boq-save">${ICON("check")} Save BOQ</button>
			<span class="muted" id="boq-state">${b.dirty ? "unsaved changes" : ""}</span>
		</div>
		<div class="tiles boqt" id="boq-tot"></div>
		<div class="box boqbox"><table class="boqg"><thead><tr><th style="width:62px">Sl. No.</th><th>Item description</th><th style="width:130px">Type</th>
			<th style="width:84px">Unit</th><th class="r" style="width:100px">Quantity</th><th class="r" style="width:110px">Rate</th><th class="r" style="width:120px">Amount</th>
			<th style="width:200px">Remarks</th><th style="width:34px"></th></tr></thead><tbody>`;
	b.rows.forEach((r, i) => {
		h += `<tr><td><input class="bg" data-i="${i}" data-f="sl" value="${esc(r.sl)}"></td>
			<td><input class="bg wide" data-i="${i}" data-f="description" value="${esc(r.description)}" placeholder="e.g. RCC M25 footings"></td>
			<td><select class="bg ty-${BOQ_TONE[r.type] || "red"}" data-i="${i}" data-f="type">${BOQ_TYPES.map((t) => `<option ${t === r.type ? "selected" : ""}>${t}</option>`).join("")}</select></td>
			<td><input class="bg" data-i="${i}" data-f="unit" value="${esc(r.unit)}" placeholder="Cu.m"></td>
			<td><input class="bg r" type="number" step="any" data-i="${i}" data-f="qty" value="${r.qty === "" ? "" : esc(r.qty)}"></td>
			<td><input class="bg r" type="number" step="any" data-i="${i}" data-f="rate" value="${r.rate === "" || r.rate === 0 ? "" : esc(r.rate)}" placeholder="optional"></td>
			<td class="r amt" id="boq-amt-${i}">${Number(r.qty || 0) * Number(r.rate || 0) ? money(Number(r.qty || 0) * Number(r.rate || 0)) : "—"}</td>
			<td><input class="bg" data-i="${i}" data-f="remarks" value="${esc(r.remarks)}"></td>
			<td><button class="xbtn" data-act="boq-del" data-i="${i}" title="Remove line">×</button></td></tr>`;
	});
	h += `</tbody></table><div class="bar" style="margin:10px 0 0"><button class="btn sm" data-act="boq-add">${ICON("plus")} Add line</button>
		<span class="muted">${b.rows.filter((r) => (r.description || "").trim()).length} line(s)</span></div></div>`;
	const keep = q("#view").scrollTop;
	showView(h);
	q("#view").scrollTop = keep;
	boqTotals();
}

function boqTotals() {
	const b = S.boqEd;
	const t = {};
	BOQ_TYPES.forEach((x) => (t[x] = 0));
	let all = 0;
	b.rows.forEach((r) => { const a = Number(r.qty || 0) * Number(r.rate || 0); t[r.type] = (t[r.type] || 0) + a; all += a; });
	const el = q("#boq-tot");
	if (el) el.innerHTML = BOQ_TYPES.map((x) => `<div class="tile ti-${BOQ_TONE[x]}"><div class="tbody"><div class="l">${x}</div><div class="v">${money(t[x])}</div></div></div>`).join("") +
		`<div class="tile"><div class="tbody"><div class="l">Total BOQ (this stage)</div><div class="v">${money(all)}</div></div></div>`;
}

function boqInput(el) {
	const b = S.boqEd;
	const i = Number(el.dataset.i), f = el.dataset.f;
	b.rows[i][f] = el.value;
	b.dirty = true;
	const st = q("#boq-state");
	if (st) st.textContent = "unsaved changes";
	if (f === "qty" || f === "rate") {
		const a = Number(b.rows[i].qty || 0) * Number(b.rows[i].rate || 0);
		const c = q("#boq-amt-" + i);
		if (c) c.textContent = a ? money(a) : "—";
	}
	if (f === "type") el.className = "bg ty-" + (BOQ_TONE[el.value] || "red");
	boqTotals();
}

// ---------- BOQ Excel
function boqType(v) {
	const s = String(v || "").toLowerCase();
	if (!s) return "Material";
	if (/man ?power|labou?r|worker|mason|helper/.test(s)) return "Manpower";
	if (/equip|machine|crane|jcb|hire|rent/.test(s)) return "Equipment";
	if (/transport|freight|lorry|truck|shifting|carting/.test(s)) return "Transport";
	if (/sub.?contract|contractor|job ?work/.test(s)) return "Subcontract";
	if (/material|mat\b|supply|steel|cement/.test(s)) return "Material";
	return "Other";
}

function boqFromSheet(raw) {
	let hi = 0;
	for (let i = 0; i < Math.min(raw.length, 30); i++) {
		const j = raw[i].map((c) => String(c).toLowerCase()).join("|");
		if (/desc|item|particular|work/.test(j) && /qty|quantity/.test(j)) { hi = i; break; }
	}
	const H = (raw[hi] || []).map((x) => String(x).toLowerCase().replace(/\s+/g, " ").trim());
	const f = (re, not) => H.findIndex((x) => re.test(x) && !(not && not.test(x)));
	const m = { sl: f(/^s\.? ?l|^sl|^s\.? ?no|^sr|^#$|^no\.?$/), description: f(/desc|item|particular|work/, /^s\.? ?l|^sl|no\.?$/), type: f(/type|category|head|nature/),
		unit: f(/^unit|uom/), qty: f(/qty|quantity/), rate: f(/rate|price/), remarks: f(/remark|note|comment/) };
	if (m.description < 0) throw new Error(__("Could not find the Item description column. Use the sample Excel layout."));
	const rows = [];
	for (let i = hi + 1; i < raw.length; i++) {
		const r = raw[i] || [];
		const desc = String(r[m.description] || "").replace(/\s+/g, " ").trim();
		if (!desc || /^total/i.test(desc)) continue;
		const num = (k) => (m[k] >= 0 ? parseAmt(r[m[k]]).n : 0) || "";
		rows.push({ sl: m.sl >= 0 && String(r[m.sl]).trim() ? String(r[m.sl]).trim() : String(rows.length + 1), description: desc,
			type: m.type >= 0 ? boqType(r[m.type]) : boqType(desc), unit: m.unit >= 0 ? String(r[m.unit] || "").trim() : "",
			qty: num("qty"), rate: num("rate"), remarks: m.remarks >= 0 ? String(r[m.remarks] || "").trim() : "" });
	}
	return rows;
}

async function boqFile(file) {
	try {
		const raw = (await readStatement(file)).filter((r) => r && r.some((c) => String(c).trim() !== ""));
		const rows = boqFromSheet(raw);
		if (!rows.length) { frappe.msgprint(__("No BOQ lines found in this file.")); return; }
		const b = S.boqEd;
		const has = b.rows.some((r) => (r.description || "").trim());
		const apply = (replace) => {
			b.rows = replace ? rows : b.rows.filter((r) => (r.description || "").trim()).concat(rows);
			b.dirty = true;
			boqRender();
			frappe.show_alert({ message: __("{0} line(s) read from {1}. Check them, then Save BOQ.", [rows.length, file.name]), indicator: "blue" }, 6);
		};
		if (!has) apply(true);
		else frappe.confirm(__("Replace the {0} line(s) on screen with the {1} from the file? (No = add them below)", [b.rows.length, rows.length]), () => apply(true), () => apply(false));
	} catch (e) {
		frappe.msgprint(esc(e.message || e));
	}
}

function boqSampleAoa() {
	return [["Sl. No.", "Item description", "Type", "Unit", "Quantity", "Rate (optional)", "Remarks"],
		[1, "Excavation in ordinary soil for footings", "Manpower", "Cu.m", 420, 350, ""],
		[2, "PCC 1:4:8 below footings", "Material", "Cu.m", 38, 5200, ""],
		[3, "RCC M25 for footings and pedestals", "Material", "Cu.m", 96, 7800, "Ready-mix"],
		[4, "TMT reinforcement steel Fe500D", "Material", "MT", 9.6, 68000, ""],
		[5, "Bar bending and fixing labour", "Manpower", "MT", 9.6, 6500, ""],
		[6, "JCB hire for excavation", "Equipment", "Hrs", 60, 1200, "With operator and diesel"],
		[7, "Hydra crane for steel erection", "Equipment", "Days", 12, 9000, ""],
		[8, "Steel structure erection", "Subcontract", "MT", 85, 4500, "Erection contractor"],
		[9, "Material shifting from yard to site", "Transport", "Trips", 25, 3500, ""],
		[10, "Site safety and housekeeping", "Other", "LS", 1, 25000, ""]];
}

async function boqSample() {
	const aoa = boqSampleAoa();
	const types = [["Type", "Use for"], ["Material", "Cement, steel, sheets, bolts, paint, any supply"], ["Manpower", "Labour, masons, helpers, bar benders"],
		["Equipment", "JCB, crane, mixer, scaffolding - hire or own"], ["Transport", "Lorry, trips, material shifting, freight"],
		["Subcontract", "Work given to a contractor (erection, roofing, painting)"], ["Other", "Anything else"]];
	try {
		const X = await loadXlsx();
		const wb = X.utils.book_new();
		const ws = X.utils.aoa_to_sheet(aoa);
		ws["!cols"] = [{ wch: 8 }, { wch: 46 }, { wch: 14 }, { wch: 8 }, { wch: 11 }, { wch: 15 }, { wch: 30 }];
		X.utils.book_append_sheet(wb, ws, "BOQ");
		const wt = X.utils.aoa_to_sheet(types);
		wt["!cols"] = [{ wch: 14 }, { wch: 60 }];
		X.utils.book_append_sheet(wb, wt, "Types");
		X.writeFile(wb, "BOQ_sample.xlsx");
	} catch (e) {
		const csv = aoa.map((r) => r.map((c) => /[",]/.test(String(c)) ? '"' + String(c).replace(/"/g, '""') + '"' : c).join(",")).join("\n");
		const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
		const a = document.createElement("a");
		a.href = url; a.download = "BOQ_sample.csv"; document.body.appendChild(a); a.click(); a.remove();
		setTimeout(() => URL.revokeObjectURL(url), 2000);
	}
}

async function boqSave(el) {
	const b = S.boqEd;
	const rows = b.rows.filter((r) => (r.description || "").trim());
	const noQty = rows.filter((r) => !(Number(r.qty) > 0)).length;
	const go2 = async () => {
		el.disabled = true;
		try {
			const r = await call("boq_save", { project: b.p.name, stage: b.stage, rows: JSON.stringify(rows) });
			frappe.show_alert({ message: __("BOQ saved: {0} line(s) for {1}", [r.lines, b.stage]), indicator: "green" }, 5);
			viewBoqEdit(b.p, b.stage);
		} catch (e) { el.disabled = false; }
	};
	if (!rows.length) {
		frappe.confirm(__("No lines with a description. Save an empty BOQ for this stage (removes its lines)?"), go2);
	} else if (noQty) {
		frappe.confirm(__("{0} line(s) have no quantity. Save anyway?", [noQty]), go2);
	} else go2();
}

// ------------------------------------------------------------------ HELP (written for someone new to computers and ERP)
const HELP = {
	home: { title: "Home", where: "Click “Lite ERP” at the top left", color: "#c8102e",
		intro: "Home is like the front page of a newspaper. It tells you, in one look, how the company is doing today.",
		steps: [["Look at the boxes", "Each box shows one number. For example “To receive from customers” is the money customers still have to pay you."],
			["Red means “please look”", "If a number is red, something needs your attention. Example: money that is late, or today’s bank statement not uploaded."],
			["Click a box to see more", "Clicking a box opens the full list behind that number. To come back, click “Lite ERP” at the top left."],
			["See the chart", "Red bars are sales (money you billed). Grey bars are purchases (money you spent). Taller red bars are good news."],
			["Bill what is due", "“Milestones to bill” shows work that is finished and ready for billing. Click one to make its bill."]],
		example: "Today the box “To receive from customers” shows ₹ 69 lakh and “overdue ₹ 23 lakh” in red. That means customers owe you ₹ 69 lakh, and ₹ 23 lakh of it should already have been paid. You can call those customers.",
		words: [["Overdue", "Late. The last date to pay has passed."], ["Balance", "What is left after adding and subtracting."]],
		links: [["home", "Open Home"]] },
	projects: { title: "Projects & BOQ", where: "Projects menu", color: "#2563eb",
		intro: "A project is one building work (one site). A BOQ is the shopping list for that work: what is needed, how much, and roughly what it costs.",
		steps: [["Open Project BOQ", "Click Projects at the top, then “Project BOQ”."],
			["Choose the project", "You will see all projects as cards. Type a few letters in the search box to find one quickly, then click it."],
			["Choose the stage", "Work happens in stages, like Foundation, Steel Structure, Roofing. Click the stage. If there is no stage, type a name in “New stage” and click “Create and open”."],
			["Write the list", "Fill one line for each item: what it is, its type, unit (bags, kg, trips), and how many. Rate (price for one) is optional."],
			["Or upload from Excel", "If the list is already in Excel, click “Upload Excel”. Not sure how the Excel should look? Click “Download sample Excel” and copy that layout."],
			["Save", "Click the red “Save BOQ” button. If you forget and try to leave, the screen will remind you."]],
		example: "For the Foundation stage you write: “Cement – Material – Bags – 500”, “JCB – Equipment – Hours – 60”, “Masons – Manpower – Days – 30”. Later, when you buy cement, the app knows cement belongs to this stage.",
		words: [["Project", "One building job at one site."], ["Stage / milestone", "One part of the job, like Foundation or Roofing."],
			["BOQ", "Bill of Quantities – the list of items and quantities needed for the work."],
			["Type", "What kind of cost: Material (things you buy), Manpower (workers), Equipment (machines), Transport (lorries), Subcontract (work given to another contractor), Other."]],
		links: [["boq", "Open Project BOQ"], ["projects", "See all projects"]] },
	sales: { title: "Sales (orders and bills to the customer)", where: "Sales menu", color: "#16a34a",
		intro: "First you write the customer’s order (sales order). Then you bill it. Lines marked MS = Yes are billed in parts, one bill for each finished milestone. Lines marked MS = No are billed separately whenever they are done.",
		steps: [["Make the sales order", "Click Sales → “New sales order” (or open a project and click “New sales order”). Choose the customer, the item code and GST."],
			["Write the lines", "One line for each item: Sl. No., Description, Area (or quantity), Unit (sq.ft, sq.m, Nos …) and Cost per unit. The total is worked out for you. Click “Bring lines from the project BOQ” to fill them quickly."],
			["Say MS Yes or No", "MS means milestone. Yes = this line is billed part by part with the milestones. No = this line is billed on its own (for example an extra gate)."],
			["Make the milestones", "In step 3, click “Project stages” or a quick start like 30/40/30. The % is of the MS work only. They must add up to 100%."],
			["Create and Submit", "Click “Create sales order”. The order opens below – check it and click Submit once."],
			["Bill a milestone", "Sales → “Bill a milestone” → the project. Blue card = ready to bill, yellow = draft bill, green = billed. Click a blue card: the bill opens with every MS line at that %."],
			["Non-MS bill", "Sales → “Non-MS bill” → the project. You see the MS = No lines and what is left to bill. Click “Make non-MS invoice”. You can lower the quantity if only part is done."],
			["Finish the bill", "Check it, Save, Submit. Then Print, or make the e-way bill if goods move by lorry."]],
		example: "Hosur shed order: 12,000 sq.ft PEB erection at ₹ 150 = ₹ 18 lakh (MS = Yes) and one extra gate ₹ 2 lakh (MS = No). Milestones: Foundation 30%, Structure 70%. When the foundation is done, the Foundation card makes a bill of ₹ 5.4 lakh (30% of ₹ 18 lakh). When the gate is fixed, “Non-MS bill” makes a bill of ₹ 2 lakh.",
		words: [["Sales order", "The customer’s full order with all its lines."], ["MS", "Milestone. MS = Yes lines are billed in parts by milestone."],
			["Non-MS bill", "A bill for lines with MS = No – not part of any milestone."], ["Area / Qty", "How much: square feet, square metres, numbers …"],
			["Cost per unit", "Price for one sq.ft / one sq.m / one piece."], ["Milestone", "One part of the work that you bill separately. All parts together make 100% of the MS work."],
			["Payment term", "One milestone line inside the order: “pay this % on this stage”."], ["Draft", "Saved but not final – you can still change it."],
			["Submit", "Make it final. After this it cannot be changed, only cancelled."], ["e-way bill", "A government slip needed when goods travel by lorry."]],
		links: [["so-new", "New sales order"], ["sales", "Bill a milestone"], ["sales-nonms", "Non-MS bill"], ["receive", "Record money received"]] },
	purchase: { title: "Purchase (orders and supplier bills)", where: "Purchase menu", color: "#7c3aed",
		intro: "Purchase works just like Sales, but for what you buy or give to a subcontractor. Write a purchase order, mark each line MS Yes or No, then enter the supplier’s bills by milestone or as non-MS bills. You can still buy straight from the BOQ.",
		steps: [["Make the purchase order", "Click Purchase → “New purchase order”. Choose the supplier, item code and GST. Write the lines: Sl. No., Description, Area, Unit, Cost per unit, and MS Yes / No."],
			["Milestones", "Give the milestones of the MS work (for example Fabrication 40%, Erection 60%). Create, check and Submit the order."],
			["Bill a milestone", "Purchase → “Bill a milestone” → the project. Click the stage the supplier has billed. The bill opens with the MS lines at that %. Type the supplier’s bill number, Save, Submit."],
			["Non-MS bill", "Purchase → “Non-MS bill” for the MS = No lines."],
			["Buy from the BOQ", "No order? Use “Purchase from BOQ”: project → stage → tick the items still to buy → Create purchase bill."],
			["Not in the BOQ?", "Use “Direct purchase bill”. It opens an empty bill already marked with the project and stage."]],
		example: "Subcontract order to Apvk Infra: 12,000 sq.ft erection at ₹ 40 (MS = Yes) and crane hire ₹ 60,000 (MS = No). After fabrication, click the “Fabrication 40%” card – a bill of ₹ 1.92 lakh opens. Type Apvk’s bill number, Save, Submit.",
		words: [["Supplier", "The shop, company or subcontractor you buy from."], ["Purchase order", "Your written order to the supplier."],
			["Purchase bill", "The supplier’s bill to you."], ["MS", "Milestone. MS = Yes lines are billed in parts."], ["Rate", "Price for one unit."]],
		links: [["po-new", "New purchase order"], ["po-bill", "Bill a milestone"], ["purchase", "Purchase from BOQ"], ["pay", "Record a payment to a supplier"]] },
	cash: { title: "Cash Flow (site cash)", where: "Cash Flow menu", color: "#d97706",
		intro: "Sites need cash for small daily costs. Here you write down cash given to a site and what the site spent, so you always know how much cash is still at the site.",
		steps: [["Give cash", "Click Cash Flow → “Give cash to site”. Choose the site, type the amount and the name of the person who received it, and click Save."],
			["Write an expense", "Click “Site expense”. Choose the site, what it was for (Transport, Equipment, Subcontract, Other), the amount, and who paid – site cash or office."],
			["Check the balance", "The site page shows Cash given – Spent = Cash still with the site."],
			["From Tally", "If the accounts team already entered cash payments in Tally, “Import from Tally” shows them. Tick them, choose the site and click Add."]],
		example: "You give ₹ 50,000 to Murugan at Hosur. He spends ₹ 6,500 on JCB and ₹ 3,000 on a lorry. The site page shows ₹ 40,500 still with the site.",
		words: [["Site cash", "Cash kept at the site for small expenses."], ["Expense", "Money spent."]],
		links: [["cash-give", "Give cash to site"], ["cash-expense", "Write a site expense"]] },
	bank: { title: "Bank (do this every day)", where: "Bank menu", color: "#0d9488",
		intro: "Every rupee that comes into or goes out of the bank should match a bill. This screen helps you check each bank entry one by one.",
		steps: [["Get the statement", "Open the bank’s net banking. Go to Account Statement, choose the dates and download it as Excel (not PDF). City Union Bank: Accounts → Account Statement → Format Excel."],
			["Upload it", "In Lite ERP click Bank → “Upload bank statement”, choose the account, and choose the file you downloaded. Do not change the file. Entries already uploaded are skipped."],
			["Check each entry", "Click Bank → “Daily bank check”. Money that came in (green) should match a sales bill. Money that went out (red) should match a purchase bill."],
			["Click the right bill", "The app shows likely bills in green boxes. Click the correct one. Done for that entry."],
			["No bill? Explain it", "Some entries have no bill, like a loan, salary or bank charges. Choose the reason from the list, type a short note, and click “Save remark”."]],
		example: "The bank shows “+ ₹ 34,69,200 from Ashok Leyland”. The app suggests bill SINV-0041 for ₹ 35,40,000 and says “less 2% (TDS)”. The customer kept 2% as tax (TDS), so this is the right bill. Click it.",
		words: [["Bank statement", "The bank’s list of all money in and out of your account."], ["TDS", "Tax the customer keeps back and pays to the government for you. So you receive a little less than the bill."],
			["Remark", "A short note explaining something."]],
		links: [["bank-upload", "Upload bank statement"], ["bank", "Daily bank check"]] },
	site: { title: "Site Summary", where: "Site Summary menu", color: "#2563eb",
		intro: "One table that shows, for every site, how much you billed, how much came in, and how much you spent.",
		steps: [["Open All sites", "Click Site Summary → “All sites”."],
			["Read one row", "Each row is one site. Billed = money asked from the customer. Received = money that came in. Spent = purchases plus site expenses."],
			["Watch the last column", "“Billed − spent” is like profit so far. Red means you have spent more than you billed."],
			["Click a site", "Click any row to see that site’s details and quick buttons."]],
		example: "Hosur: Billed ₹ 35 lakh, Spent ₹ 32 lakh, Billed − spent ₹ 3 lakh. The site is so far making a small profit.",
		words: [["Received", "Money that has actually come into the bank."], ["Spent", "Money paid out for this site."]],
		links: [["sites", "All sites"], ["cash-position", "Cash with each site"]] },
	me: { title: "My work (every employee)", where: "My work menu", color: "#c8102e",
		intro: "Your own attendance, leave and details in one place. Lite ERP opens by itself when you log in, and around office start and end time it takes you straight to the punch page.",
		steps: [["Punch every day", "Tap “Punch IN / OUT”. The first time, it asks you to take your face photo from the front, left and right. After that each punch takes a selfie with the time and GPS place."],
			["See your month", "“My attendance” shows each day: IN, OUT, hours and late. Tap a day to see each punch with photo and place."],
			["Could not punch?", "Use “Attendance request”: forgot to punch, on duty, client / site visit, travel, work from home, phone problem or other. Write where you were. HR approves it."],
			["Leave", "Use “Leave request”. You see how much leave is left. You can withdraw a request until HR approves it."],
			["Your details", "“My details” – change phone, address, bank or photo. The change happens only after HR approves."],
			["Password", "The first login uses SBI@2026. You must set your own password, then log in again with your user id and the new password."]],
		example: "On Monday you went straight to the Velachery site. Open “Attendance request”, choose “Client / Site Visit”, write “Velachery site – slab casting”, and send. When HR approves, Monday counts as present.",
		words: [["Attendance request", "Asking HR to mark you present for a day you could not punch."], ["Withdraw", "Take back a request before HR answers it."]],
		links: [["me", "My attendance"], ["punch", "Punch IN / OUT"], ["me-att", "Attendance request"], ["me-leave", "Leave request"]] },
	hr: { title: "HR (workers and staff)", where: "HR menu", color: "#16a34a",
		intro: "See who came to work – site workers (they punch with the site app) and office staff (they punch with the SBI Office app on their phone). Look at one day, the whole salary month, or any dates you choose.",
		steps: [["Open attendance", "Click HR → “Attendance”. It opens on today."],
			["Pick the period", "Click Day, This salary month, Last salary month, or Custom dates (choose From and To)."],
			["Set the salary month once", "Click “⚙ Month settings”. If salary is from the 1st to the last day, keep 1. If it is from the 26th to the 25th, type 26. Also set how many hours make a full day and a half day."],
			["Set the office place once", "In the same settings, stand inside the office and click “Use my current location”, then Save. Or open the SBI Office app and click “Set office here”. Also set office start / end time, grace minutes and the reminder."],
			["Office staff punch", "Each staff member opens the “SBI Office” app on their phone (add it to the home screen once) and taps Punch. The camera opens, they take a selfie, and the time and GPS location are saved. 15 minutes before office time they get a reminder."],
			["Check the office list", "The Office staff table shows IN time, OUT time and hours. Red “outside” means they punched away from the office. Click a name to see every punch with photo and map."],
			["Mark attendance and pay salary", "At month end, choose This salary month and click “Mark staff attendance from punches”. Then click “Run payroll” – the month dates fill in by themselves."],
			["HR dashboard", "HR → “HR dashboard” shows total employees, present, late, on leave and not punched today. Tap a box to filter, tap a name to see the month with every punch photo and GPS place, leave and requests."],
			["Add an employee and a login", "HR → “Add / edit employee”: Employee ID No., name, photo and dates. Tick “Give this employee a login”, type a user id (not e-mail) and tick the allowed areas. The password is SBI@2026 for the first login only."],
			["Approve requests", "HR → “Requests to approve” has three tabs: attendance requests, leave and detail changes. Approve, or write a remark and Reject."],
			["Letters", "HR → “Appointment order” or “Relieving order”, pick the employee, and print. For a relieving order first set Status = Left and the relieving date."]],
		example: "Salary month starts on the 26th. On 25 November choose “This salary month” (26 Oct – 25 Nov). Priya has 24 days, 2 of them half days. Click “Mark staff attendance from punches”, then “Run payroll for 26-10-2026 – 25-11-2026”.",
		words: [["Punch", "Marking IN or OUT with the phone (photo and location)."], ["Geofence / office area", "The allowed area around a site or the office. Punching outside it shows in red."],
			["Salary month", "The days one salary covers, for example 26th to 25th."], ["Full day / half day", "Enough hours between first IN and last OUT to count as a full or a half day."],
			["No OUT", "The person forgot to punch OUT – that day is not marked automatically."]],
		links: [["hr-dash", "HR dashboard"], ["hr", "Attendance"], ["hr-req", "Requests to approve"], ["ext:/sbi_office", "SBI Office punch app"], ["hr-settings", "Month & office settings"]] },
	gst: { title: "GST", where: "GST menu", color: "#c8102e",
		intro: "GST is a tax. You collect GST from customers on your bills and pay GST to suppliers on their bills. The difference is paid to the government.",
		steps: [["Open GST", "Click GST → “GST to pay”."],
			["Choose the period", "Pick This month, This quarter, This year or your own dates."],
			["Read the boxes", "Output GST = GST you collected on sales. Input credit = GST you paid on purchases. Net = Output minus Input."],
			["Balance to pay", "The last box shows how much GST you still owe the government. If it is green and says “carried forward”, you have extra credit."]],
		example: "This month you collected ₹ 5,00,000 GST on sales and paid ₹ 2,72,000 GST on purchases. So you owe ₹ 2,28,000 GST to the government.",
		words: [["Output GST", "GST you collected from customers."], ["Input credit (ITC)", "GST you paid to suppliers. It reduces the GST you have to pay."]],
		links: [["gst", "GST to pay"]] },
};
const HELP_ORDER = ["me", "home", "projects", "sales", "purchase", "cash", "bank", "site", "hr", "gst"];
const GLOSSARY = [
	["ERP", "Software that keeps all company records – bills, money, stock, workers – in one place."],
	["Company", "Shiv Bharat has two companies (two GST numbers). The box at the top right chooses which one you are looking at."],
	["Customer", "The person or company who pays you for the work."], ["Supplier", "The shop or company you buy from."],
	["Invoice / bill", "A paper asking someone to pay. Sales invoice = your bill to a customer. Purchase invoice = a supplier’s bill to you."],
	["Project", "One building job at one site."], ["Stage / milestone", "One part of a job, like Foundation or Roofing. Bills are often made per stage."],
	["BOQ", "Bill of Quantities – the list of items and quantities needed for the work."],
	["Draft", "Saved but not final. You can still change it."], ["Submit", "Make it final. After this it is counted in the accounts and cannot be changed."],
	["Outstanding", "Money still not paid."], ["Overdue", "Late – the last date to pay has passed."],
	["GST", "A tax added to bills. Output GST is collected from customers; input credit is GST paid to suppliers."],
	["TDS", "Tax a customer keeps back from your payment and pays to the government for you."],
	["Bank statement", "The bank’s list of all money in and out of the account."], ["Site cash", "Cash kept at a site for small daily expenses."],
];

function helpSteps(x) {
	return `<ol class="hsteps">${x.steps.map((s, i) => `<li><span class="hn" style="background:${x.color}">${i + 1}</span>
		<div><b>${esc(s[0])}</b><p>${esc(s[1])}</p></div></li>`).join("")}</ol>`;
}
function helpExtra(x) {
	let h = "";
	if (x.example) h += `<div class="hex"><div class="hex-t">${ICON("check")} Example</div><p>${esc(x.example)}</p></div>`;
	if (x.words && x.words.length) h += `<div class="hwords"><div class="hex-t">${ICON("info")} Words you will see</div>${x.words.map((w) =>
		`<div><b>${esc(w[0])}</b><span>${esc(w[1])}</span></div>`).join("")}</div>`;
	return h;
}

function viewHelp(focus) {
	S.here = () => viewHelp(focus);
	S.current = () => viewHelp(focus);
	setMenu("help");
	crumbs([["Help", null]]);
	let h = `<div class="hhero"><div><div class="hh-t">${ICON("info")} Learn Lite ERP</div>
			<div class="hh-s">Simple steps for every screen, with examples. No computer or accounts knowledge needed.</div></div>
			<input class="hsearch" id="hsearch" placeholder="Search – e.g. bank, BOQ, GST, cash" autocomplete="off"></div>
		<div class="hstart"><div class="hs-t">${ICON("home")} Start here – what is Lite ERP?</div>
			<p>Think of Lite ERP as the <b>company’s notebook on the computer</b>. Every bill, every payment, every bag of cement bought and every worker’s attendance is written in it. Because everything is written in one place, it can add things up for you and show you the answers.</p>
			<div class="hs-rules">
				<div><span>1</span><p><b>The red bar at the top is the menu.</b> Move the mouse on a word (like “Bank”) to see its choices. Click a choice.</p></div>
				<div><span>2</span><p><b>The screen changes below the red bar.</b> You never leave this page. The line under the red bar shows where you are – click a word there to go back.</p></div>
				<div><span>3</span><p><b>Save, then Submit.</b> Save keeps your work as a draft (can still change). Submit makes it final.</p></div>
				<div><span>4</span><p><b>Red = please look.</b> Red numbers mean something is late or missing.</p></div>
				<div><span>5</span><p><b>Stuck?</b> Click “How this works” at the top right of any screen to see its steps.</p></div>
			</div></div>
		<div class="hday"><div class="hday-t">${ICON("calendar")} Your work every day (about 15 minutes)</div><div class="hday-g">
			<a data-go="bank-upload" data-m="bank"><span>1</span>Upload the bank statement and check each entry</a>
			<a data-go="purchase" data-m="purchase"><span>2</span>Enter supplier bills for the right project and stage</a>
			<a data-go="cash-give" data-m="cash"><span>3</span>Write cash given to sites and site expenses</a>
			<a data-go="home" data-m="home"><span>4</span>Look at Home – anything in red?</a></div></div>
		<div class="hgrid" id="hgrid">`;
	HELP_ORDER.forEach((k) => {
		const x = HELP[k];
		const words = (x.title + " " + x.intro + " " + x.steps.map((s) => s.join(" ")).join(" ") + " " + (x.example || "") + " " +
			(x.words || []).map((w) => w.join(" ")).join(" ")).toLowerCase();
		h += `<div class="hcard ${focus === k ? "focus" : ""}" id="help-${k}" data-s="${esc(words)}" style="--hc:${x.color}">
			<div class="hc-top"><span class="hc-ic" style="background:${x.color}">${ICON(MENU_ICON[k] || "home")}</span>
				<div><div class="hc-t">${esc(x.title)}</div><div class="hc-w">${esc(x.where)}</div></div></div>
			<div class="hc-i">${esc(x.intro)}</div>${helpSteps(x)}${helpExtra(x)}
			<div class="bar">${x.links.map((g) => `<a class="qa-i" data-go="${g[0]}" data-m="${k}">${esc(g[1])} →</a>`).join("")}</div></div>`;
	});
	h += `</div><div class="hint" id="hnone" style="display:none">Nothing found. Try another word.</div>
		<div class="box hgloss" id="hgloss"><h3>${ICON("info")} Words you will see – in simple language</h3><div class="hg-g">${GLOSSARY.map((g) =>
			`<div class="hg-i" data-s="${esc((g[0] + " " + g[1]).toLowerCase())}"><b>${esc(g[0])}</b><span>${esc(g[1])}</span></div>`).join("")}</div></div>`;
	showView(h);
	const s = q("#hsearch");
	s.addEventListener("input", () => {
		const t = s.value.toLowerCase().trim();
		let n = 0;
		R.querySelectorAll(".hcard, .hg-i").forEach((c) => { const ok = !t || c.dataset.s.indexOf(t) >= 0; c.classList.toggle("hide", !ok); if (ok) n++; });
		q("#hnone").style.display = n ? "none" : "block";
	});
	if (focus && q("#help-" + focus)) setTimeout(() => q("#help-" + focus).scrollIntoView({ behavior: "smooth", block: "start" }), 80);
}

// slide-in help for the screen you are on
function helpDrawer(key) {
	key = HELP[key] ? key : (HELP[S.menu] ? S.menu : "home");
	const x = HELP[key];
	let d = q("#hdrawer");
	if (!d) {
		q("#lx").insertAdjacentHTML("beforeend", `<div class="hshade" id="hshade" data-act="help-close"></div><aside class="hdrawer" id="hdrawer"></aside>`);
		d = q("#hdrawer");
	}
	d.innerHTML = `<div class="hd-head" style="background:${x.color}"><span class="hc-ic">${ICON(MENU_ICON[key] || "home")}</span>
			<div><div class="hd-t">${esc(x.title)}</div><div class="hd-w">${esc(x.where)}</div></div>
			<button class="hd-x" data-act="help-close" title="Close">×</button></div>
		<div class="hd-body"><div class="hc-i">${esc(x.intro)}</div>${helpSteps(x)}${helpExtra(x)}
			<div class="bar">${x.links.map((g) => `<a class="qa-i" data-go="${g[0]}" data-m="${key}">${esc(g[1])} →</a>`).join("")}</div>
			<a class="hd-all" data-go="help" data-m="help">All help topics and word meanings</a></div>`;
	requestAnimationFrame(() => q("#lx").classList.add("hd-open"));
}
function helpClose() { const lx = q("#lx"); if (lx) lx.classList.remove("hd-open"); }

// ------------------------------------------------------------------ phone menu (one list instead of the top row)
function drawPhoneMenu() {
	const p = q("#mnav");
	if (!p) return;
	p.innerHTML = `<a class="mn-home" data-go="home" data-m="home">${ICON("home")} Home</a>` + MENUS.map((m) => `
		<div class="mn-sec"><div class="mn-h">${ICON(MENU_ICON[m.id] || "info")} ${esc(m.label)}<a class="mn-q" data-act="help-drawer" data-h="${m.id}">?</a></div>
		${m.items.map((i) => `<a data-go="${esc(i[0])}" data-m="${m.id}">${esc(i[1])}</a>`).join("")}</div>`).join("") +
		`<a class="mn-home" data-go="help" data-m="help">${ICON("info")} Help</a>`;
}

// ------------------------------------------------------------------ unsaved BOQ guard
function boqDirty() {
	return !!(S.boqEd && S.boqEd.dirty && q(".boqg"));
}
function leaveGuard(fn) {
	if (!boqDirty()) { fn(); return; }
	frappe.confirm(__("You have unsaved BOQ changes. Leave without saving?"), () => { S.boqEd.dirty = false; fn(); });
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") helpClose(); });
window.addEventListener("beforeunload", (e) => { if (boqDirty()) { e.preventDefault(); e.returnValue = ""; } });

// ------------------------------------------------------------------ events
R.addEventListener("click", async (e) => {
	const m = e.target.closest(".m-btn");
	if (m && window.matchMedia("(hover: none)").matches && m.parentElement.querySelector(".m-sub")) {
		// touch screens: first tap opens the submenu
		const box = m.parentElement;
		if (!box.classList.contains("open")) { R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open")); box.classList.add("open"); return; }
	}
	const g = e.target.closest("[data-go]");
	if (g) {
		e.preventDefault();
		R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open"));
		q("#lx").classList.remove("mn-open");
		leaveGuard(() => go(g.dataset.go, g.dataset.m || S.menu));
		return;
	}
	if (e.target.closest("#burger")) { q("#lx").classList.toggle("mn-open"); return; }
	if (q("#lx").classList.contains("mn-open") && !e.target.closest("#mnav")) q("#lx").classList.remove("mn-open");
	const c = e.target.closest("[data-crumb]");
	if (c) { const fn = S.crumbs[Number(c.dataset.crumb)][1]; if (fn) leaveGuard(fn); return; }
	if (e.target.closest(".newstage") && !e.target.closest("[data-act]")) return;
	const pick = e.target.closest("[data-pick]");
	if (pick) { if (S.onPick) S.onPick(findProject(pick.dataset.pick)); return; }
	const el = e.target.closest("[data-act]");
	if (!el) return;
	const a = el.dataset.act;
	if (a !== "open" && el.tagName === "A") e.preventDefault();
	if (a === "open") {
		e.preventDefault(); e.stopPropagation();
		const last = S.crumbs[S.crumbs.length - 1] || ["Back", null];
		frameForm(el.dataset.dt, el.dataset.name, S.crumbs.slice(0, -1).concat([[last[0], S.here || null]]));
	}
	else if (a === "newtab") {
		let url = BASE;
		try { url = q("#frame").contentWindow.location.href; } catch (x) { /* ignore */ }
		window.open(url, "_blank");
	}
	else if (a === "go") go(el.dataset.go, S.menu);
	else if (a === "o-bill") orderBill(el, "ms_bill");
	else if (a === "o-nonms") orderBill(el, "nonms_bill");
	else if (a === "o-new") viewOrderForm(findProject(el.dataset.p), el.dataset.kind);
	else if (a === "o-mode") viewOrders(findProject(el.dataset.p), el.dataset.kind, el.dataset.mode);
	else if (a === "o-save") orderSave(el);
	else if (a === "ol-add") { olRead(); const l = olBlank(); l.sl = String(S.ms.lines.length + 1); S.ms.lines.push(l); olRender(); }
	else if (a === "ol-del") { olRead(); S.ms.lines.splice(Number(el.dataset.i), 1); olRender(); }
	else if (a === "ol-boq") olFromBoq();
	else if (a === "p-so") viewOrderForm(findProject(el.dataset.p), "sales");
	else if (a === "p-po") viewOrderForm(findProject(el.dataset.p), "purchase");
	else if (a === "direct-si") directSales(findProject(el.dataset.p));
	else if (a === "ms-preset") msPreset(el.dataset.k);
	else if (a === "ms-import") msImport(Number(el.dataset.i));
	else if (a === "ms-add") { msRead(); S.ms.rows.push({ name: "", percent: Math.max(0, Math.round((100 - msTotals()) * 100) / 100), due_date: frappe.datetime.add_days(frappe.datetime.get_today(), 30 * (S.ms.rows.length + 1)) }); msRender(); }
	else if (a === "ms-del") { msRead(); S.ms.rows.splice(Number(el.dataset.i), 1); msRender(); }
	else if (a === "boq") { e.stopPropagation(); viewBoq(findProject(el.dataset.p), el.dataset.stage); }
	else if (a === "direct-pi") { e.stopPropagation(); directPurchase(findProject(el.dataset.p), el.dataset.stage, true); }
	else if (a === "make-pi") makePurchaseFromBoq();
	else if (a === "project") viewProject(el.dataset.p);
	else if (a === "p-bill") viewMilestones(findProject(el.dataset.p));
	else if (a === "p-buy") viewStages(findProject(el.dataset.p), false);
	else if (a === "p-cash") viewCash(findProject(el.dataset.p), "give");
	else if (a === "hr-site") viewHrSite(el.dataset.p);
	else if (a === "hr-today") viewHr(frappe.datetime.get_today());
	else if (a === "hr-mode") { const P = S.hrP || {}; S.hrP = { mode: el.dataset.mode, day: P.day || frappe.datetime.get_today(), from: P.from, to: P.to };
		if (el.dataset.mode === "custom" && !(P.from && P.to)) { const m = salaryMonth((S.hrSet || {}).start_day, frappe.datetime.get_today(), 0); S.hrP.from = m[0]; S.hrP.to = frappe.datetime.get_today(); }
		viewHr(); }
	else if (a === "hr-emp") viewHrEmp(el.dataset.e);
	else if (a === "m-day") { const r = R.querySelector(`.mpun[data-day="${el.dataset.i}"]`); if (r) r.classList.toggle("hide"); }
	else if (a === "m-back") { S.mBack = Number(el.dataset.b) || 0; if (S.current) S.current(); }
	else if (a === "ar-save") {
		const rs = R.querySelector('input[name="ar-reason"]:checked');
		if (!val("#ar-exp")) { frappe.msgprint(__("Write the details: where you were and what work.")); return; }
		el.disabled = true;
		try {
			await call("me_att_req", { from_date: val("#ar-from"), to_date: val("#ar-to") || val("#ar-from"), half_day: q("#ar-half").checked ? 1 : 0,
				reason: rs ? rs.value : "On Duty", explanation: val("#ar-exp") });
			frappe.show_alert({ message: __("Sent to HR"), indicator: "green" });
			viewMeAtt();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "lv-save") {
		el.disabled = true;
		try {
			await call("me_leave_req", { leave_type: val("#lv-type"), from_date: val("#lv-from"), to_date: val("#lv-to") || val("#lv-from"),
				half_day: q("#lv-half").checked ? 1 : 0, description: val("#lv-desc") });
			frappe.show_alert({ message: __("Leave sent to HR"), indicator: "green" });
			viewMeLeave();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "me-withdraw") {
		frappe.confirm(__("Withdraw this request?"), async () => {
			await call("me_cancel_req", { kind: el.dataset.k, name: el.dataset.n });
			S.mData = null;
			if (S.current) S.current();
		});
	}
	else if (a === "me-prof-save") {
		const vals = {};
		R.querySelectorAll("#view [data-f]").forEach((x) => { if (x.value !== (S.meOrig || {})[x.dataset.f]) vals[x.dataset.f] = x.value; });
		if (!Object.keys(vals).length && !S.meNewPhoto) { frappe.msgprint(__("Nothing was changed.")); return; }
		el.disabled = true;
		try {
			await call("me_profile_save", { values: JSON.stringify(vals), photo: S.meNewPhoto || "" });
			frappe.msgprint({ title: __("Sent to HR"), indicator: "green", message: __("Your details change after HR approves.") });
			S.mData = null;
			viewMe();
		} catch (x) { el.disabled = false; }
	}
	else if (a === "pw-save") pwSave(el);
	else if (a === "hd-filter") { S.hdFilter = el.dataset.f; hdList(); }
	else if (a === "emp-month") { e.stopPropagation(); S.mBack = 0; viewEmpMonth(el.dataset.e); }
	else if (a === "emp-edit") { e.stopPropagation(); viewEmpForm(el.dataset.e); }
	else if (a === "emp-new") viewEmpForm("");
	else if (a === "emp-save") empSave(el);
	else if (a === "req-tab") viewReqs(el.dataset.t);
	else if (a === "req-do") reqDo(el);
	else if (a === "pe-pick") { if (S.onEmp) S.onEmp(el.dataset.e); }
	else if (a === "letter") openLetter(el.dataset.f, el.dataset.e);
	else if (a === "hr-office-all") { const b = R.querySelector('[data-act="hr-emp"]'); if (b) b.scrollIntoView({ behavior: "smooth", block: "center" }); }
	else if (a === "hr-settings") viewHrSettings();
	else if (a === "hr-back") viewHr();
	else if (a === "hs-save") hsSave(el);
	else if (a === "hs-here") hsHere();
	else if (a === "hr-mark") hrMark(el);
	else if (a === "hr-payroll") frameNew("Payroll Entry", { company: S.company, start_date: el.dataset.f, end_date: el.dataset.t, posting_date: el.dataset.t > frappe.datetime.get_today() ? frappe.datetime.get_today() : el.dataset.t, payroll_frequency: "Monthly" }, null, [["HR", () => viewHr()]]);
	else if (a === "desk") window.location.href = BASE;
	else if (a === "bank-up") { e.stopPropagation(); viewBankUpload(el.dataset.acc); }
	else if (a === "bank-chk") { e.stopPropagation(); viewBankCheck(el.dataset.acc, "check"); }
	else if (a === "bk-show") viewBankCheck(S.bankAcc, el.dataset.show);
	else if (a === "bu-save") buSave(el);
	else if (a === "bu-sample") downloadSample(el.dataset.acc);
	else if (a === "help-drawer") { R.querySelectorAll(".m.open").forEach((x) => x.classList.remove("open")); el.blur && el.blur(); helpDrawer(el.dataset.h || S.menu); }
	else if (a === "help-close") helpClose();
	else if (a === "boq-edit") viewBoqEdit(findProject(el.dataset.p), el.dataset.stage);
	else if (a === "boq-newstage") { e.stopPropagation(); boqNewStage(el); }
	else if (a === "boq-add") { const b = S.boqEd; b.rows.push(boqBlank(b.rows.length + 1)); b.dirty = true; boqRender();
		const ins = R.querySelectorAll('input[data-f="description"]'); if (ins.length) ins[ins.length - 1].focus(); }
	else if (a === "boq-del") { const b = S.boqEd; b.rows.splice(Number(el.dataset.i), 1); b.dirty = true; boqRender(); }
	else if (a === "boq-save") boqSave(el);
	else if (a === "boq-sample") boqSample();
	else if (a === "bk-match") { el.disabled = true; bankSet({ txn: el.dataset.txn, status: "Matched", doctype: el.dataset.dt, name: el.dataset.name }).catch(() => (el.disabled = false)); }
	else if (a === "bk-other") {
		const inv = (R.querySelector(`.bk-inv[data-txn="${CSS.escape(el.dataset.txn)}"]`) || {}).value || "";
		if (!inv.trim()) { frappe.msgprint(__("Type the sales or purchase invoice number.")); return; }
		bankSet({ txn: el.dataset.txn, status: "Matched", name: inv.trim() });
	}
	else if (a === "bk-noinv") {
		const t = CSS.escape(el.dataset.txn);
		const rsn = (R.querySelector(`.bk-rsn[data-txn="${t}"]`) || {}).value || "";
		const rem = (R.querySelector(`.bk-rem[data-txn="${t}"]`) || {}).value || "";
		if (!rsn) { frappe.msgprint(__("Choose why there is no invoice.")); return; }
		if (!rem.trim()) { frappe.msgprint(__("Write a remark saying what this entry is.")); return; }
		bankSet({ txn: el.dataset.txn, status: "No Invoice", reason: rsn, remarks: rem.trim() });
	}
	else if (a === "bk-undo") bankSet({ txn: el.dataset.txn, status: "" });
	else if (a === "add-cash" || a === "add-expense") {
		const p = findProject(el.dataset.p);
		const v = (s) => (q(s) || {}).value || "";
		const args = a === "add-cash"
			? { project: p.name, date: v("#c-date"), amount: v("#c-amount"), received_by: v("#c-who"), remarks: v("#c-remarks") }
			: { project: p.name, date: v("#e-date"), amount: v("#e-amount"), category: v("#e-cat"), payment_source: v("#e-src"), party: v("#e-party"), description: v("#e-desc") };
		el.disabled = true;
		try {
			const r = await call(a === "add-cash" ? "add_cash" : "add_expense", args);
			frappe.show_alert({ message: __("Saved {0}", [r.name]), indicator: "green" });
			viewCash(p, a === "add-cash" ? "give" : "expense");
		} catch (x) { el.disabled = false; }
	}
	else if (a === "import-tally") {
		const prj = (q("#t-project") || {}).value;
		const picks = Array.from(R.querySelectorAll(".t-pick:checked")).map((x) => x.dataset.je);
		if (!picks.length) { frappe.msgprint(__("Tick the Tally payments to add.")); return; }
		if (!prj) { frappe.msgprint(__("Pick the site these payments belong to.")); return; }
		const kinds = picks.map((je) => { const s = R.querySelector(`.t-kind[data-je="${CSS.escape(je)}"]`); return s ? s.value : "Cash"; });
		el.disabled = true;
		try {
			const r = await call("import_tally", { jes: picks.join(","), kinds: kinds.join(","), projects: picks.map(() => prj).join(",") });
			frappe.show_alert({ message: __("{0} added, {1} skipped", [(r.made || []).length, r.skipped || 0]), indicator: "green" });
			viewTally();
		} catch (x) { el.disabled = false; }
	}
});

R.addEventListener("change", (e) => {
	const id = e.target.id;
	if (id === "company") {
		S.company = e.target.value;
		try { localStorage.setItem("lite_erp_company", S.company); } catch (x) { /* ignore */ }
		S.summary = null;
		if (S.current) S.current();
	}
	else if (id === "period") {
		S.period = e.target.value;
		if (S.period === "custom") { q("#pcustom").classList.remove("hide"); return; }
		if (S.current) S.current();
	}
	else if (id === "pfrom" || id === "pto") {
		S.from = (q("#pfrom") || {}).value; S.to = (q("#pto") || {}).value;
		if (S.from && S.to && S.current) S.current();
	}
	else if (id === "t-bank") { S.includeBank = e.target.checked; viewTally(); }
	else if (id === "hr-date") { if (e.target.value) viewHr(e.target.value); }
	else if (id === "hr-from" || id === "hr-to") { const f = q("#hr-from").value, t = q("#hr-to").value; if (f && t) { S.hrP = { mode: "custom", from: f, to: t, day: (S.hrP || {}).day }; viewHr(); } }
	else if (id === "hs-start") hsExample();
	else if (id === "ef-login") { const b = q("#ef-login-box"); if (b) b.classList.toggle("hide", !e.target.checked); }
	else if (id === "pw-show") ["#pw1", "#pw2"].forEach((s) => { const x = q(s); if (x) x.type = e.target.checked ? "text" : "password"; });
	else if ((id === "ef-photo" || id === "me-photo") && e.target.files && e.target.files[0]) {
		fileToJpeg(e.target.files[0], 900).then((u) => {
			if (id === "ef-photo") { S.empPhoto = u; const p = q("#ef-prev"); p.src = u; p.classList.remove("hide"); const n = q("#ef-noph"); if (n) n.classList.add("hide"); }
			else { S.meNewPhoto = u; const p = q("#me-photo-prev"); p.src = u; p.classList.remove("hide"); }
		}).catch((x) => frappe.msgprint(x.message));
	}
	else if (id === "bu-file") { if (e.target.files && e.target.files[0]) buFile(e.target.files[0]); }
	else if (id === "boq-file") { if (e.target.files && e.target.files[0]) boqFile(e.target.files[0]); e.target.value = ""; }
	else if (id === "bu-hi") { const v = Math.max(1, Number(e.target.value || 1)) - 1; S.bu.hi = v; S.bu.map = guessMap(S.bu.raw[v] || []); buRender(); }
	else if (e.target.classList.contains("bu-map")) { S.bu.map[e.target.dataset.f] = Number(e.target.value); buRender(); }
	else if (id === "bk-acc") viewBankCheck(e.target.value, S.bankShow);
	else if (id === "bk-show") viewBankCheck(S.bankAcc, e.target.value);
	else if (id === "t-all") R.querySelectorAll(".t-pick").forEach((x) => (x.checked = e.target.checked));
	else if (id === "b-all") { R.querySelectorAll(".b-pick").forEach((x) => { if (!x.closest("details")) x.checked = e.target.checked; }); boqTotal(); }
	else if (e.target.classList.contains("b-pick")) boqTotal();
});
R.addEventListener("dragover", (e) => { const d = e.target.closest && e.target.closest(".drop"); if (d) { e.preventDefault(); d.classList.add("over"); } });
R.addEventListener("dragleave", (e) => { const d = e.target.closest && e.target.closest(".drop"); if (d) d.classList.remove("over"); });
R.addEventListener("drop", (e) => {
	const d = e.target.closest && e.target.closest(".drop");
	if (!d) return;
	e.preventDefault();
	d.classList.remove("over");
	if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) buFile(e.dataTransfer.files[0]);
});
R.addEventListener("input", (e) => {
	if (e.target.id === "hd-q") { hdList(); return; }
	if (e.target.id === "pe-q") { peList(); return; }
	if (e.target.classList && e.target.classList.contains("bg")) { boqInput(e.target); return; }
	if (e.target.classList.contains("b-qty") || e.target.classList.contains("b-rate")) boqTotal();
	if (e.target.classList.contains("ms-p")) msTotals();
	if (e.target.classList.contains("ol-in")) olTotals();
});

// ------------------------------------------------------------------ full-screen layout
// Lite ERP fills the screen beside the desk's own icon rail / top bar.
function deskEdges() {
	const host = R.host;
	const at = (x, y) => (document.elementsFromPoint(x, y) || []).filter((el) =>
		el !== host && !host.contains(el) && el !== document.body && el !== document.documentElement);
	let L = 0, T = 0;
	at(2, Math.round(window.innerHeight / 2)).forEach((el) => {
		const r = el.getBoundingClientRect();
		if (r.left <= 2 && r.width < 260 && r.height > window.innerHeight * 0.5) L = Math.max(L, r.right);
	});
	at(Math.round(window.innerWidth / 2), 2).forEach((el) => {
		const r = el.getBoundingClientRect();
		const pos = getComputedStyle(el).position;
		const bar = pos === "fixed" || pos === "sticky" || el.tagName === "HEADER" || el.classList.contains("navbar");
		if (bar && r.top <= 2 && r.height > 20 && r.height < 90 && r.width > window.innerWidth * 0.5) T = Math.max(T, r.bottom);
	});
	return { L: Math.round(L), T: Math.round(T) };
}

function fit() {
	const lx = q("#lx");
	if (!lx) return;
	const on = /^\/(desk|app)\/lite-erp/.test(window.location.pathname);
	if (on) {
		const e = deskEdges();
		lx.classList.add("full");
		Object.assign(lx.style, { top: e.T + "px", left: e.L + "px", right: "0px", bottom: "0px", height: "auto" });
		document.body.style.overflow = "hidden";
		// a transformed parent would break fixed positioning: fall back to a tall box
		const r = lx.getBoundingClientRect();
		if (Math.abs(r.left - e.L) > 4 || Math.abs(r.top - e.T) > 4) {
			lx.classList.remove("full");
			Object.assign(lx.style, { top: "", left: "", right: "", bottom: "" });
			lx.style.height = Math.max(480, window.innerHeight - Math.max(lx.getBoundingClientRect().top, 0) - 8) + "px";
		}
	} else {
		document.body.style.overflow = "";
	}
}
function outerChrome() {
	if (!document.getElementById("lx-outer-css")) {
		const st = document.createElement("style");
		st.id = "lx-outer-css";
		st.textContent = `body.lx-on .page-head, body.lx-on .layout-side-section { display: none !important; }
			body.lx-on .page-body, body.lx-on .container.page-body { max-width: 100% !important; width: 100% !important; padding-left: 8px !important; padding-right: 8px !important; }
			body.lx-on .layout-main-section-wrapper, body.lx-on .layout-main-section { padding: 0 !important; margin: 0 !important; }
			body.lx-on .custom-block-widget-box, body.lx-on .widget.custom-block-widget-box { padding: 0 !important; border: 0 !important; background: none !important; }
			body.lx-on .codex-editor__redactor { padding-bottom: 0 !important; }`;
		document.head.appendChild(st);
	}
	const check = () => {
		const on = /^\/(desk|app)\/lite-erp/.test(window.location.pathname);
		document.body.classList.toggle("lx-on", on);
		if (on) { setTimeout(fit, 50); setTimeout(fit, 500); } else document.body.style.overflow = "";
	};
	check();
	if (frappe.router && frappe.router.on && !window.__lx_router) { window.__lx_router = 1; frappe.router.on("change", check); }
	window.addEventListener("popstate", check);
}

// ------------------------------------------------------------------ start
outerChrome();
// follow the desk's light / dark theme
function syncTheme() { const lx = q("#lx"); if (lx) lx.classList.toggle("dark", document.documentElement.getAttribute("data-theme") === "dark"); }
syncTheme();
try { new MutationObserver(syncTheme).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] }); } catch (e) { /* ignore */ }
window.addEventListener("resize", fit);
q("#frame").addEventListener("load", () => { frameStyle(); setTimeout(frameStyle, 800); });
drawMenu();
drawPhoneMenu();
call("init").then((d) => {
	S.scope = d.scope || "all";
	S.areas = d.areas || [];
	S.me = d.me || null;
	if (!S.me) { const mi = MENUS.findIndex((m) => m.id === "me"); if (mi >= 0) MENUS.splice(mi, 1); const hi = HELP_ORDER.indexOf("me"); if (hi >= 0) HELP_ORDER.splice(hi, 1); }
	if (S.scope !== "all") {
		// limited login (HR, staff, sales…): keep only the menus this login may use
		for (let i = MENUS.length - 1; i >= 0; i--) if (S.areas.indexOf(MENUS[i].id) < 0) MENUS.splice(i, 1);
		for (let i = HELP_ORDER.length - 1; i >= 0; i--) if (S.areas.indexOf(HELP_ORDER[i]) < 0) HELP_ORDER.splice(i, 1);
		S.homeMenu = S.areas.indexOf("hr") >= 0 ? "hr" : S.me ? "me" : (MENUS[0] || { id: "me" }).id;
		S.homeKey = S.homeMenu === "hr" ? "hr-dash" : S.homeMenu === "me" ? "me" : ((MENUS[0] || { items: [["me"]] }).items[0][0]);
	}
	drawMenu();
	drawPhoneMenu();
	if (d.must_change) { viewChangePw(true); return; }
	// around office start / end time, staff land on the punch page
	if (d.punch_window && S.me) {
		const k = "sbi_punch_auto_" + frappe.datetime.get_today() + "_" + d.punch_window;
		let seen = "";
		try { seen = sessionStorage.getItem(k) || ""; } catch (x) { /* ignore */ }
		if (!seen) {
			try { sessionStorage.setItem(k, "1"); } catch (x) { /* ignore */ }
			window.location.href = "/sbi_office";
			return;
		}
	}
	S.companies = d.companies || [];
	S.projects = d.projects || [];
	const logo = (frappe.boot && frappe.boot.app_logo_url) || d.logo || "";
	const img = q("#lx-logo");
	if (logo && img) { img.onerror = () => img.classList.add("hide"); img.src = logo; img.classList.remove("hide"); }
	let saved = "";
	try { saved = localStorage.getItem("lite_erp_company") || ""; } catch (x) { /* ignore */ }
	const def = (saved && S.companies.indexOf(saved) >= 0 && saved) || frappe.defaults.get_user_default("Company") || d.default_company || S.companies[0] || "";
	q("#company").innerHTML = S.companies.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
	S.company = def;
	if (def) q("#company").value = def;
	go("home", "home");
	setTimeout(fit, 60);
	setTimeout(fit, 600);
	setTimeout(fit, 1500);
	// warm up the form area so the first invoice opens quickly
	setTimeout(() => { if (!q("#frame").getAttribute("src")) q("#frame").setAttribute("src", BASE + (S.scope === "all" ? "/sales-invoice" : "/employee")); }, 2500);
});'''

# SBI Office: office staff punch app (web page /sbi_office) - GPS + selfie, reminders before office time
OFFICE_LABEL = "SBI Office"
OFFICE_ROUTE = "/sbi_office"
OFFICE_API = "sbi_office_punch"
OFFICE_ROLES_WANTED = ["Employee", "Employee Self Service", "HR Manager", "HR User", "System Manager", "Business Owner", "Accounts Manager", "Accounts User"]
OFFICE_SERVER = r'''# SBI Office - office staff punch IN / OUT with GPS and a stamped selfie (Employee Checkin). App page: /sbi_office
# API method: sbi_office_punch   (any logged-in user; punches only for the Employee linked to that login)
fd = frappe.form_dict
act = fd.get("act") or "status"
user = frappe.session.user
if user == "Guest":
    frappe.throw("Please log in.")
MANAGER_ROLES = ["System Manager", "HR Manager", "HR User", "Business Owner", "Accounts Manager"]
my_roles = []
for r in frappe.db.sql("select role from `tabHas Role` where parenttype='User' and parent=%s", user):
    my_roles.append(r[0])
is_mgr = False
for r in MANAGER_ROLES:
    if r in my_roles:
        is_mgr = True
if user == "Administrator":
    is_mgr = True

# office location and day rules live in HR Settings (set from Lite ERP -> HR -> Salary month & office settings)
OFF = {"name": "", "lat": 0.0, "lng": 0.0, "radius": 200, "block": 1, "in_time": "", "out_time": "", "grace": 10, "reminder": 15}
hm = frappe.get_meta("HR Settings")
for pair in [["name", "sbi_office_name"], ["lat", "sbi_office_latitude"], ["lng", "sbi_office_longitude"], ["radius", "sbi_office_radius"],
        ["block", "sbi_block_outside"], ["in_time", "sbi_office_in_time"], ["out_time", "sbi_office_out_time"], ["grace", "sbi_late_grace"],
        ["reminder", "sbi_reminder_minutes"]]:
    if hm.has_field(pair[1]):
        v = frappe.db.get_single_value("HR Settings", pair[1])
        if v not in (None, ""):
            OFF[pair[0]] = v
OFF["lat"] = frappe.utils.flt(OFF["lat"])
OFF["lng"] = frappe.utils.flt(OFF["lng"])
OFF["radius"] = frappe.utils.cint(OFF["radius"]) or 200
OFF["set"] = 1 if (OFF["lat"] and OFF["lng"]) else 0
OFF["block"] = frappe.utils.cint(OFF["block"])
OFF["grace"] = frappe.utils.cint(OFF["grace"])
OFF["reminder"] = frappe.utils.cint(OFF["reminder"])
for k in ("in_time", "out_time"):
    tp = str(OFF[k] or "").split(":")
    OFF[k] = (("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2]) if tp[0] else ""
PLUS = frappe.get_meta("Employee Checkin").has_field("sbi_within")

ecols = ["name", "employee_name", "designation", "department", "company", "image"]
if frappe.get_meta("Employee").has_field("sbi_punch_anywhere"):
    ecols.append("sbi_punch_anywhere")
FACE = frappe.get_meta("Employee").has_field("sbi_face_front")
if FACE:
    ecols = ecols + ["sbi_face_front", "sbi_face_left", "sbi_face_right", "sbi_face_on"]
ADDR = frappe.get_meta("Employee Checkin").has_field("sbi_address")
by_hr = 0
emp = None
if is_mgr and fd.get("as_employee"):
    # HR / owner / Administrator can open any employee (to punch for them or check their day)
    emp = frappe.db.get_value("Employee", {"name": fd.get("as_employee"), "status": "Active"}, ecols, as_dict=1)
    if emp:
        by_hr = 1
if not emp:
    emp = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, ecols, as_dict=1)
if emp:
    emp["anywhere"] = frappe.utils.cint(emp.get("sbi_punch_anywhere"))
    emp["by_hr"] = by_hr
    emp["enrolled"] = 1 if (not FACE or (emp.get("sbi_face_front") and emp.get("sbi_face_left") and emp.get("sbi_face_right"))) else 0
    emp["sbi_face_on"] = str(emp.get("sbi_face_on") or "")[:16]
today = frappe.utils.nowdate()
logo = frappe.db.get_single_value("Navbar Settings", "app_logo") or frappe.db.get_single_value("Website Settings", "app_logo") or ""
out = {"user": user, "is_manager": 1 if is_mgr else 0, "office": OFF, "employee": emp, "server_time": str(frappe.utils.now_datetime())[:19], "logo": logo}

if act == "punch":
    if not emp:
        frappe.throw("Your login is not linked to an active Employee. Ask HR to put your login (User ID) on your Employee record.")
    lt = fd.get("log_type") or ""
    if lt not in ("IN", "OUT"):
        frappe.throw("Choose IN or OUT.")
    last = frappe.db.sql("select log_type, time from `tabEmployee Checkin` where employee=%s and date(time)=%s order by time desc limit 1", (emp.name, today), as_dict=1)
    expect = "OUT" if (last and last[0].log_type == "IN") else "IN"
    if lt != expect:
        frappe.throw("You are already punched " + lt + ". Your next punch is " + expect + ". Reload the page.")
    if last and frappe.utils.time_diff_in_seconds(frappe.utils.now_datetime(), last[0].time) < 60:
        frappe.throw("You punched less than a minute ago. Please wait a minute.")
    lat = frappe.utils.flt(fd.get("latitude"))
    lng = frappe.utils.flt(fd.get("longitude"))
    acc = frappe.utils.flt(fd.get("accuracy"))
    dist = 0.0
    within = 1
    if lat and lng and OFF["set"]:
        # short-distance (equirectangular) formula with a series for cos - no math module in server scripts
        k = 3.141592653589793 / 180.0
        mid = (lat + OFF["lat"]) / 2.0 * k
        c = 1 - mid ** 2 / 2 + mid ** 4 / 24 - mid ** 6 / 720 + mid ** 8 / 40320
        dx = (lng - OFF["lng"]) * k * c
        dy = (lat - OFF["lat"]) * k
        dist = round(6371000.0 * (dx * dx + dy * dy) ** 0.5, 1)
        within = 1 if dist <= OFF["radius"] + min(acc, 100) else 0
    if OFF["block"] and OFF["set"] and not emp.anywhere and not by_hr:
        if not (lat and lng):
            frappe.throw("Your location is needed to punch. Turn on location (GPS) and allow it for this app.")
        if not within:
            frappe.throw("You are " + str(int(dist)) + " m from " + (OFF["name"] or "the office") + ". Punch is allowed only within " + str(OFF["radius"]) + " m. Come inside the office and try again.")
    if FACE and not emp.enrolled:
        frappe.throw("Take the face photos (front, left and right) once before the first punch.")
    doc = {"doctype": "Employee Checkin", "employee": emp.name, "log_type": lt, "time": frappe.utils.now_datetime(),
        "device_id": ("Office Punch " + (fd.get("device") or "web"))[:120]}
    if lat and lng:
        doc["latitude"] = lat
        doc["longitude"] = lng
    if PLUS:
        doc["sbi_distance"] = dist
        doc["sbi_within"] = within
        doc["sbi_accuracy"] = acc
        doc["sbi_remarks"] = ((("Punched by " + user + ". ") if by_hr else "") + (fd.get("remarks") or ""))[:500]
        doc["sbi_source"] = "SBI Office (by HR)" if by_hr else "SBI Office"
    if ADDR:
        doc["sbi_address"] = (fd.get("address") or "")[:500]
    ck = frappe.get_doc(doc)
    ck.flags.ignore_permissions = True
    ck.insert(ignore_permissions=True)
    photo = fd.get("photo") or ""
    url = ""
    if photo and "," in photo:
        f = frappe.get_doc({"doctype": "File", "file_name": emp.name + "-" + lt + "-" + str(frappe.utils.now_datetime())[:19].replace(" ", "_").replace(":", "") + ".jpg",
            "attached_to_doctype": "Employee Checkin", "attached_to_name": ck.name, "content": photo.split(",", 1)[1], "decode": True, "is_private": 0})
        f.flags.ignore_permissions = True
        f.insert(ignore_permissions=True)
        url = f.file_url
        if PLUS:
            frappe.db.set_value("Employee Checkin", ck.name, "sbi_photo", url)
    late = 0
    if lt == "IN" and not last and OFF["in_time"]:
        lim = frappe.utils.add_to_date(frappe.utils.get_datetime(today + " " + OFF["in_time"] + ":00"), minutes=OFF["grace"])
        if ck.time > lim:
            late = int(frappe.utils.time_diff_in_seconds(ck.time, frappe.utils.get_datetime(today + " " + OFF["in_time"] + ":00")) / 60)
    early = 0
    if lt == "OUT" and OFF["out_time"]:
        endt = frappe.utils.get_datetime(today + " " + OFF["out_time"] + ":00")
        if ck.time < endt:
            early = int(frappe.utils.time_diff_in_seconds(endt, ck.time) / 60)
    out["punched"] = {"name": ck.name, "log_type": lt, "time": str(ck.time)[11:16], "distance": dist, "within": within, "photo": url, "late": late, "early": early}

if act == "set_office":
    if not is_mgr:
        frappe.throw("Only HR or the owner can set the office location.")
    la = frappe.utils.flt(fd.get("latitude"))
    lo = frappe.utils.flt(fd.get("longitude"))
    if not la or not lo:
        frappe.throw("No location from the phone yet.")
    if not hm.has_field("sbi_office_latitude"):
        frappe.throw("Run the Lite ERP installer again (office fields are missing).")
    frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_latitude", la)
    frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_longitude", lo)
    if fd.get("radius"):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_radius", max(20, frappe.utils.cint(fd.get("radius"))))
    if hm.has_field("sbi_block_outside") and fd.get("block") not in (None, ""):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_block_outside", 1 if str(fd.get("block")) in ("1", "true") else 0)
    if fd.get("office_name"):
        frappe.db.set_value("HR Settings", "HR Settings", "sbi_office_name", fd.get("office_name")[:140])
    OFF["name"] = fd.get("office_name") or OFF["name"]
    OFF["lat"] = la
    OFF["lng"] = lo
    OFF["radius"] = max(20, frappe.utils.cint(fd.get("radius") or OFF["radius"]))
    OFF["set"] = 1
    out["office"] = OFF

if act == "enroll":
    if not emp:
        frappe.throw("Your login is not linked to an employee.")
    if not FACE:
        frappe.throw("Run the Lite ERP installer again: Employee has no face photo fields yet.")
    if emp.enrolled and not is_mgr:
        frappe.throw("Your face photos are already saved. Ask HR if they must be taken again.")
    saved = {}
    stamp = str(frappe.utils.now_datetime())[:19].replace(" ", "_").replace(":", "")
    for side in ["front", "left", "right"]:
        ph = fd.get("photo_" + side) or ""
        if "," not in ph:
            frappe.throw("The " + side + " photo is missing. Take all three photos.")
        fdoc = frappe.get_doc({"doctype": "File", "file_name": emp.name + "-face-" + side + "-" + stamp + ".jpg", "attached_to_doctype": "Employee",
            "attached_to_name": emp.name, "attached_to_field": "sbi_face_" + side, "content": ph.split(",", 1)[1], "decode": True, "is_private": 1})
        fdoc.flags.ignore_permissions = True
        fdoc.insert(ignore_permissions=True)
        saved["sbi_face_" + side] = fdoc.file_url
    for k in saved:
        frappe.db.set_value("Employee", emp.name, k, saved[k])
    frappe.db.set_value("Employee", emp.name, "sbi_face_on", frappe.utils.now_datetime())
    emp["enrolled"] = 1
    emp["sbi_face_front"] = saved["sbi_face_front"]
    emp["sbi_face_left"] = saved["sbi_face_left"]
    emp["sbi_face_right"] = saved["sbi_face_right"]
    emp["sbi_face_on"] = str(frappe.utils.now_datetime())[:16]
    out["employee"] = emp
    out["enrolled"] = 1

if act == "reset_face":
    if not is_mgr:
        frappe.throw("Only HR, the owner or Administrator can reset face photos.")
    if emp and FACE:
        for k in ["sbi_face_front", "sbi_face_left", "sbi_face_right", "sbi_face_on"]:
            frappe.db.set_value("Employee", emp.name, k, None)
            emp[k] = ""
        emp["enrolled"] = 0
        out["employee"] = emp

if act == "save_settings":
    if not is_mgr:
        frappe.throw("Only HR, the owner or Administrator can change settings.")
    vals = {}
    if fd.get("start_day") not in (None, ""):
        sd = frappe.utils.cint(fd.get("start_day"))
        if sd < 1 or sd > 28:
            frappe.throw("The salary month must start on a day from 1 to 28.")
        vals["sbi_salary_start_day"] = sd
    for pair in [["in_time", "sbi_office_in_time"], ["out_time", "sbi_office_out_time"]]:
        tv = (fd.get(pair[0]) or "").strip()
        if tv:
            tp = tv.split(":")
            if len(tp) < 2 or not tp[0].isdigit() or not tp[1][:2].isdigit() or int(tp[0]) > 23 or int(tp[1][:2]) > 59:
                frappe.throw("Office time " + tv + " is not valid. Use HH:MM, for example 09:30.")
            vals[pair[1]] = ("0" + tp[0])[-2:] + ":" + tp[1][:2] + ":00"
    if vals.get("sbi_office_in_time") and vals.get("sbi_office_out_time") and vals["sbi_office_out_time"] <= vals["sbi_office_in_time"]:
        frappe.throw("Office end time must be after the start time.")
    if fd.get("grace") not in (None, ""):
        vals["sbi_late_grace"] = max(0, min(240, frappe.utils.cint(fd.get("grace"))))
    if fd.get("reminder") not in (None, ""):
        vals["sbi_reminder_minutes"] = max(0, min(120, frappe.utils.cint(fd.get("reminder"))))
    if fd.get("radius") not in (None, ""):
        vals["sbi_office_radius"] = max(20, frappe.utils.cint(fd.get("radius")))
    if fd.get("block") not in (None, ""):
        vals["sbi_block_outside"] = 1 if str(fd.get("block")) in ("1", "true") else 0
    if fd.get("office_name") not in (None, ""):
        vals["sbi_office_name"] = fd.get("office_name")[:140]
    for k in vals:
        if not hm.has_field(k):
            frappe.throw("Run the Lite ERP installer again: HR Settings has no field " + k + ".")
    for k in vals:
        frappe.db.set_value("HR Settings", "HR Settings", k, vals[k])
    m = {"sbi_office_in_time": "in_time", "sbi_office_out_time": "out_time", "sbi_late_grace": "grace", "sbi_reminder_minutes": "reminder",
        "sbi_office_radius": "radius", "sbi_block_outside": "block", "sbi_office_name": "name"}
    for k in vals:
        if m.get(k):
            OFF[m[k]] = vals[k] if k not in ("sbi_office_in_time", "sbi_office_out_time") else vals[k][:5]
    out["office"] = OFF
    out["saved"] = 1

# today's punches for me
cols = "name, log_type, time, latitude, longitude" + (", ifnull(sbi_distance, 0) distance, ifnull(sbi_within, 1) within, ifnull(sbi_photo, '') photo" if PLUS else "") + (", ifnull(sbi_address, '') address" if ADDR else "")
if emp:
    logs = frappe.db.sql("select " + cols + " from `tabEmployee Checkin` where employee=%s and date(time)=%s order by time", (emp.name, today), as_dict=1)
    for l in logs:
        l["t"] = str(l.time)[11:16]
    out["logs"] = logs
    out["next"] = "OUT" if (logs and logs[-1].log_type == "IN") else "IN"
    first_in = ""
    last_out = ""
    for l in logs:
        if l.log_type == "IN" and not first_in:
            first_in = l.time
        if l.log_type == "OUT":
            last_out = l.time
    out["hours"] = round(frappe.utils.time_diff_in_hours(last_out, first_in), 2) if (first_in and last_out and last_out > first_in) else 0
    out["is_holiday"] = 0
    hl = frappe.db.get_value("Employee", emp.name, "holiday_list") or frappe.db.get_value("Company", emp.company, "default_holiday_list")
    if hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": today}):
        out["is_holiday"] = 1
    out["tomorrow_holiday"] = 1 if (hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": frappe.utils.add_days(today, 1)})) else 0
    out["month"] = frappe.db.sql("""select count(distinct date(time)) days from `tabEmployee Checkin` where employee=%s and log_type='IN'
        and time >= %s""", (emp.name, frappe.utils.get_first_day(today)), as_dict=1)[0].days

# my salary month (start day from HR Settings)
if act == "month" and emp:
    sd = 1
    if hm.has_field("sbi_salary_start_day"):
        sd = frappe.utils.cint(frappe.db.get_single_value("HR Settings", "sbi_salary_start_day")) or 1
    sd = max(1, min(28, sd))
    back = frappe.utils.cint(fd.get("back"))
    base = frappe.utils.add_months(today, -back)
    if sd == 1:
        mf = str(frappe.utils.get_first_day(base))
    else:
        if frappe.utils.getdate(base).day < sd:
            base = frappe.utils.add_months(base, -1)
        mf = str(base)[:8] + ("0" + str(sd))[-2:]
    mt = str(frappe.utils.add_days(frappe.utils.add_months(mf, 1), -1))
    rows = frappe.db.sql("""select date(time) d, min(case when log_type='IN' then time end) first_in, max(case when log_type='OUT' then time end) last_out,
        count(*) punches""" + (", sum(case when ifnull(sbi_within, 1)=0 then 1 else 0 end) outside" if PLUS else ", 0 outside") + """
        from `tabEmployee Checkin` where employee=%s and date(time) between %s and %s group by date(time) order by d desc""", (emp.name, mf, mt), as_dict=1)
    tot = 0.0
    late = 0
    for r in rows:
        h = 0.0
        if r.first_in and r.last_out and r.last_out > r.first_in:
            h = round(frappe.utils.time_diff_in_hours(r.last_out, r.first_in), 2)
        r["hours"] = h
        tot = tot + h
        r["late"] = 0
        if OFF["in_time"] and r.first_in and r.first_in > frappe.utils.add_to_date(frappe.utils.get_datetime(str(r.d) + " " + OFF["in_time"] + ":00"), minutes=OFF["grace"]):
            r["late"] = 1
            late = late + 1
        r["first_in"] = str(r.first_in or "")[11:16]
        r["last_out"] = str(r.last_out or "")[11:16]
        r["d"] = str(r.d)
    out["month_view"] = {"from": mf, "to": mt, "days": rows, "hours": round(tot, 2), "late": late, "back": back}

# first login: the default password must be changed in Lite ERP before punching
if act == "status" and frappe.get_meta("User").has_field("sbi_must_change_password") and frappe.db.get_value("User", user, "sbi_must_change_password"):
    out["must_change"] = 1

# team today for HR / owner
if is_mgr:
    own = frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "employee_name")
    out["own_employee"] = own or ""
    sdv = frappe.db.get_single_value("HR Settings", "sbi_salary_start_day") if hm.has_field("sbi_salary_start_day") else 1
    out["start_day"] = frappe.utils.cint(sdv) or 1
    out["staff"] = frappe.db.sql("select name, employee_name, designation from `tabEmployee` where status='Active' order by employee_name", as_dict=1)
if is_mgr and act in ("status", "punch", "set_office", "save_settings"):
    team = frappe.db.sql("""select e.name employee, e.employee_name, e.designation, ifnull(e.user_id, '') user_id,
        min(case when c.log_type='IN' then c.time end) first_in, max(case when c.log_type='OUT' then c.time end) last_out,
        substring_index(group_concat(c.log_type order by c.time desc separator '|'), '|', 1) last_type, count(c.name) punches
        """ + (", sum(case when ifnull(c.sbi_within, 1)=0 then 1 else 0 end) outside, max(ifnull(c.sbi_distance, 0)) max_dist" if PLUS else ", 0 outside, 0 max_dist") + """
        from `tabEmployee` e left join `tabEmployee Checkin` c on c.employee = e.name and date(c.time)=%s
        where e.status='Active' group by e.name order by (count(c.name)=0), e.employee_name""", today, as_dict=1)
    for t in team:
        t["first_in"] = str(t.first_in or "")[11:16]
        t["last_out"] = str(t.last_out or "")[11:16]
    out["team"] = team

frappe.response["message"] = out'''
OFFICE_HTML = r'''<div id="sbo" class="sbo"><div class="sbo-boot"><div class="sbo-spin"></div><div>Opening SBI Office…</div></div></div>'''
OFFICE_CSS = r'''/* SBI Office - staff punch app (web page /sbi_office). Hides the website chrome so it looks like an app. */
body.sbo-body { background: #f3f4f6 !important; margin: 0; }
body.sbo-body .navbar, body.sbo-body header.navbar, body.sbo-body .web-footer, body.sbo-body footer, body.sbo-body .page-breadcrumbs,
body.sbo-body .page-header-wrapper, body.sbo-body .page-header, body.sbo-body .web-sidebar, body.sbo-body .banner { display: none !important; }
body.sbo-body .page-content-wrapper, body.sbo-body main, body.sbo-body .container, body.sbo-body .page_content, body.sbo-body .page-container,
body.sbo-body .web-page-content, body.sbo-body .from-markdown { max-width: 100% !important; width: 100% !important; padding: 0 !important; margin: 0 !important; }
.sbo { --red: #c8102e; --red-d: #8f0b20; --ink: #1f2937; --mut: #6b7280; --line: #e5e7eb; --card: #fff; --bg: #f3f4f6; --green: #16a34a; --amber: #d97706;
  font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; color: var(--ink); max-width: 560px; margin: 0 auto; min-height: 100vh;
  background: var(--bg); padding-bottom: 84px; font-size: 14px; -webkit-tap-highlight-color: transparent; }
.sbo * { box-sizing: border-box; }
.sbo-boot { min-height: 70vh; display: grid; place-items: center; align-content: center; gap: 12px; color: var(--mut); }
.sbo-spin { width: 34px; height: 34px; border-radius: 50%; border: 3px solid #fecdd3; border-top-color: var(--red); animation: sbospin 0.9s linear infinite; }
@keyframes sbospin { to { transform: rotate(360deg); } }
.sbo-top { position: sticky; top: 0; z-index: 5; display: flex; align-items: center; gap: 10px; padding: 12px 14px; color: #fff;
  background: linear-gradient(120deg, var(--red-d), var(--red) 65%, #e0485e); box-shadow: 0 4px 14px rgba(143,11,32,.25); }
.sbo-logo { width: 38px; height: 38px; border-radius: 10px; background: #fff; display: grid; place-items: center; overflow: hidden; flex: none; }
.sbo-logo img { max-width: 34px; max-height: 34px; }
.sbo-brand b { display: block; font-size: 17px; letter-spacing: .2px; }
.sbo-brand span { font-size: 11.5px; opacity: .9; }
.sbo-clock { margin-left: auto; text-align: right; font-variant-numeric: tabular-nums; }
.sbo-clock b { display: block; font-size: 20px; }
.sbo-clock span { font-size: 11px; opacity: .9; }
.sbo-wrap { padding: 12px; }
.sbo-card { background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 14px; margin-bottom: 12px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }
.sbo-card h3 { margin: 0 0 10px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
.sbo-card h3 .sbo-mut { font-weight: 400; margin-left: auto; }
.sbo-mut { color: var(--mut); font-size: 12.5px; }
.sbo-who { display: flex; align-items: center; gap: 12px; }
.sbo-av { width: 50px; height: 50px; border-radius: 50%; background: #fde2e6; color: var(--red); display: grid; place-items: center; font-weight: 800; font-size: 18px; overflow: hidden; flex: none; }
.sbo-av img { width: 100%; height: 100%; object-fit: cover; }
.sbo-name { font-weight: 800; font-size: 16px; }
.sbo-shift { display: flex; gap: 8px; margin-top: 12px; }
.sbo-shift div { flex: 1; background: var(--bg); border-radius: 12px; padding: 8px 10px; }
.sbo-shift b { display: block; font-size: 16px; font-variant-numeric: tabular-nums; }
.sbo-shift span { font-size: 11px; color: var(--mut); }
.sbo-gps { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border-radius: 12px; background: var(--bg); margin-top: 12px; font-size: 13px; line-height: 1.35; }
.sbo-dot { width: 10px; height: 10px; border-radius: 50%; background: #9ca3af; flex: none; }
.sbo-dot.ok { background: var(--green); box-shadow: 0 0 0 4px rgba(22,163,74,.15); } .sbo-dot.warn { background: var(--amber); } .sbo-dot.bad { background: var(--red); }
.sbo-punch { display: grid; place-items: center; padding: 18px 0 6px; }
.sbo-ring { width: 196px; height: 196px; border-radius: 50%; border: 0; cursor: pointer; color: #fff; display: grid; place-items: center; align-content: center; gap: 4px;
  background: radial-gradient(circle at 35% 30%, #4ade80, #16a34a 60%, #15803d); box-shadow: 0 12px 30px rgba(22,163,74,.35), inset 0 -6px 14px rgba(0,0,0,.15);
  font-family: inherit; transition: transform .12s; }
.sbo-ring:active { transform: scale(.96); }
.sbo-ring.out { background: radial-gradient(circle at 35% 30%, #f87171, #c8102e 60%, #8f0b20); box-shadow: 0 12px 30px rgba(200,16,46,.35), inset 0 -6px 14px rgba(0,0,0,.15); }
.sbo-ring.off span { opacity: 1; }
.sbo-ring.off { background: radial-gradient(circle at 35% 30%, #d1d5db, #9ca3af 60%, #6b7280); box-shadow: none; }
.sbo-ring svg { width: 46px; height: 46px; }
.sbo-ring b { font-size: 24px; letter-spacing: .5px; }
.sbo-ring span { font-size: 12px; opacity: .9; }
.sbo-note { text-align: center; margin-top: 8px; }
.sbo-toast.sbo-banner { font-size: 13.5px; }
.sbo-banner { display: flex; align-items: center; gap: 10px; border-radius: 12px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; }
.sbo-banner.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
.sbo-banner.warn { background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; }
.sbo-banner.ok { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.sbo-banner .sbo-btn { margin-left: auto; flex: none; }
.sbo-btn { border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 10px; padding: 9px 14px; font-size: 13.5px; cursor: pointer; font-family: inherit; }
.sbo-btn.pri { background: var(--red); border-color: var(--red); color: #fff; font-weight: 700; }
.sbo-btn.sm { padding: 6px 10px; font-size: 12px; }
.sbo input, .sbo select { width: 100%; border: 1px solid var(--line); border-radius: 10px; padding: 9px 10px; font-size: 14px; background: #fff; color: var(--ink); font-family: inherit; }
.sbo label { display: block; font-size: 12px; color: var(--mut); margin-top: 8px; }
.sbo-row { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; align-items: center; }
.sbo-tl { list-style: none; margin: 0; padding: 0; }
.sbo-tl li { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px dashed var(--line); }
.sbo-tl li:last-child { border-bottom: 0; }
.sbo-tag { font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 999px; background: #dcfce7; color: #166534; min-width: 42px; text-align: center; }
.sbo-tag.out { background: #fee2e2; color: #991b1b; }
.sbo-tl .t { font-weight: 800; font-variant-numeric: tabular-nums; }
.sbo-tl .m { margin-left: auto; font-size: 12px; color: var(--mut); text-align: right; }
.sbo a { color: var(--red); text-decoration: none; }
.sbo-tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.sbo-tbl th { text-align: left; font-size: 10.5px; color: var(--mut); text-transform: uppercase; letter-spacing: .4px; padding: 6px 4px; border-bottom: 1px solid var(--line); }
.sbo-tbl td { padding: 8px 4px; border-bottom: 1px solid var(--line); vertical-align: top; }
.sbo-tbl .r { text-align: right; }
.sbo-pill { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: var(--bg); white-space: nowrap; }
.sbo-pill.g { background: #dcfce7; color: #166534; } .sbo-pill.r { background: #fee2e2; color: #991b1b; } .sbo-pill.a { background: #fef3c7; color: #92400e; }
.sbo-sum { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 10px; }
.sbo-sum div { background: var(--bg); border-radius: 12px; padding: 8px 10px; }
.sbo-sum b { display: block; font-size: 17px; }
.sbo-sum span { font-size: 11px; color: var(--mut); }
.sbo-nav { position: fixed; bottom: 0; left: 0; right: 0; z-index: 6; display: flex; justify-content: center; background: #fff; border-top: 1px solid var(--line);
  padding: 6px 0 calc(6px + env(safe-area-inset-bottom)); }
.sbo-nav a { flex: 1; max-width: 186px; text-align: center; color: var(--mut); font-size: 11.5px; padding: 4px 0; cursor: pointer; }
.sbo-nav a svg { width: 22px; height: 22px; display: block; margin: 0 auto 2px; }
.sbo-nav a.on { color: var(--red); font-weight: 700; }
/* full-screen camera: whole picture shown (no zoom), controls below */
.sbo-cam, .sbo-done, .sbo-toast { font-family: Inter, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; -webkit-font-smoothing: antialiased; }
.sbo-cam { position: fixed; inset: 0; z-index: 50; background: #0b0b0c; display: flex; flex-direction: column; color: #fff; }
.sbo-cam-top { display: flex; align-items: center; gap: 10px; padding: 10px 14px; flex: none; }
.sbo-cam-top b { font-size: 16px; }
.sbo-stage { position: relative; flex: 1 1 auto; min-height: 0; display: grid; place-items: center; overflow: hidden; }
.sbo-stage video, .sbo-stage img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; display: block; background: #000; }
.sbo-stage video { transform: scaleX(-1); }
.sbo-oval { position: absolute; left: 50%; top: 47%; height: 84%; max-height: 640px; max-width: 86%; aspect-ratio: 3 / 4; transform: translate(-50%, -50%);
  border: 3px dashed rgba(255,255,255,.85); border-radius: 50%; pointer-events: none; box-shadow: 0 0 0 200vmax rgba(0,0,0,.22); }
.sbo-arrow { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 64px; color: #fde68a; text-shadow: 0 2px 10px rgba(0,0,0,.6);
  pointer-events: none; animation: sbopulse 1s ease-in-out infinite alternate; }
@keyframes sbopulse { from { opacity: .45; } to { opacity: 1; } }
.sbo-cam-msg { flex: none; text-align: center; font-size: 13.5px; padding: 8px 14px 4px; line-height: 1.4; }
.sbo-thumbs { flex: none; display: flex; justify-content: center; gap: 10px; padding: 6px 0; }
.sbo-th { width: 64px; height: 80px; border-radius: 10px; border: 2px dashed rgba(255,255,255,.4); display: grid; place-items: center; position: relative; overflow: hidden; cursor: pointer; font-size: 22px; }
.sbo-th.ok { border: 2px solid #22c55e; }
.sbo-th img { width: 100%; height: 100%; object-fit: cover; }
.sbo-th i { position: absolute; bottom: 0; left: 0; right: 0; font-style: normal; font-size: 10px; text-align: center; background: rgba(0,0,0,.55); text-transform: uppercase; letter-spacing: .5px; }
.sbo-cam-low { flex: none; padding: 0 12px calc(12px + env(safe-area-inset-bottom)); }
.sbo-cam-reason input { background: rgba(255,255,255,.95); margin-bottom: 6px; }
.sbo-cam-gps { background: rgba(255,255,255,.08); border-radius: 12px; padding: 8px 12px; font-size: 12.5px; display: flex; gap: 8px; align-items: flex-start; line-height: 1.4; }
.sbo-cam-gps .sbo-dot { margin-top: 4px; }
.sbo-cam-bar { display: flex; align-items: center; justify-content: space-around; padding: 12px 0 2px; }
.sbo-cam-bar .sbo-btn { background: rgba(255,255,255,.14); color: #fff; border-color: rgba(255,255,255,.3); min-width: 88px; }
.sbo-cam-bar .sbo-btn.pri { background: var(--green, #16a34a); border-color: transparent; }
.sbo-shutter { width: 74px; height: 74px; border-radius: 50%; border: 5px solid #fff; background: #16a34a; cursor: pointer; }
.sbo-shutter.out { background: #c8102e; }
.sbo-shutter.enroll { background: #2563eb; }
.sbo-shutter:disabled { opacity: .35; }
.sbo-faces { display: flex; gap: 8px; }
.sbo-faces a { position: relative; width: 33%; max-width: 120px; aspect-ratio: 3 / 4; border-radius: 12px; overflow: hidden; background: var(--bg); }
.sbo-faces img { width: 100%; height: 100%; object-fit: cover; }
.sbo-faces i { position: absolute; bottom: 0; left: 0; right: 0; font-style: normal; font-size: 10.5px; text-align: center; color: #fff; background: rgba(0,0,0,.5); text-transform: uppercase; }
@media (min-width: 900px) { .sbo-stage { margin: 0 8vw; } }
/* success */
.sbo-done { position: fixed; inset: 0; z-index: 60; display: grid; place-items: center; align-content: center; gap: 10px; color: #fff; text-align: center; padding: 20px;
  background: rgba(22,163,74,.96); animation: sbofade .2s ease-out; }
.sbo-done.out { background: rgba(200,16,46,.96); }
.sbo-done .tick { width: 96px; height: 96px; border-radius: 50%; background: #fff; color: var(--green); display: grid; place-items: center; font-size: 56px; font-weight: 900; }
.sbo-done.out .tick { color: var(--red); }
.sbo-done b { font-size: 26px; }
.sbo-done img { width: min(78vw, 420px); max-height: 52vh; border-radius: 14px; object-fit: contain; border: 4px solid #fff; background: #000; }
@keyframes sbofade { from { opacity: 0; transform: scale(1.04); } to { opacity: 1; transform: none; } }
.hide { display: none !important; }
@media (min-width: 700px) { .sbo { border-left: 1px solid var(--line); border-right: 1px solid var(--line); } }

/* camera zoom */
.sbo-zoombar { position: absolute; left: 50%; bottom: 10px; transform: translateX(-50%); z-index: 3; display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px;
  background: rgba(0,0,0,.6); border-radius: 18px; padding: 6px 12px; width: min(92%, 400px); }
.sbo-zp { display: flex; justify-content: center; gap: 6px; width: 100%; }
.sbo-zp button { width: auto !important; height: 28px !important; border-radius: 999px !important; padding: 0 10px; font-size: 12.5px !important; font-weight: 700; }
.sbo-zp button.on { background: #fde68a !important; color: #111 !important; border-color: #fde68a !important; }
.sbo-zoombar button { width: 34px; height: 34px; border-radius: 50%; border: 1px solid rgba(255,255,255,.45); background: rgba(255,255,255,.12); color: #fff;
  font-size: 20px; line-height: 1; cursor: pointer; flex: none; }
.sbo-zoombar input[type=range] { flex: 1; accent-color: #fff; width: auto; padding: 0; border: 0; background: transparent; }
.sbo-zoombar b { font-size: 12.5px; min-width: 34px; text-align: right; color: #fff; }
.sbo-stage video { transition: transform .08s linear; transform-origin: center center; }
.sbo-stage video { background: transparent; }

.sbo-lite { margin-left: 10px; padding: 6px 10px; border-radius: 999px; background: rgba(255,255,255,.18); color: #fff !important; font-size: 12px; font-weight: 600; text-decoration: none !important; white-space: nowrap; }'''
OFFICE_JS = r'''// SBI Office - office staff punch app (web page /sbi_office). Punch IN / OUT with GPS + selfie, reminders before office time.
(function () {
	const API = "sbi_office_punch", APP = "/sbi_office";
	const SW = "/files/sbi_office_sw.js", MANIFEST = "/files/sbi_office_manifest_v2.json", APPICON = "/files/sbi_office_icon_180.png", APK = "/files/SBI-Office-v1.0.apk";
	const S = { d: null, pos: null, gpsErr: "", stream: null, shot: "", watch: null, tab: "punch", csrf: "", month: null, back: 0, busy: false };
	const $ = (s) => document.querySelector(s);
	const esc = (v) => String(v === null || v === undefined ? "" : v).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
	const km = (m) => (m >= 1000 ? (m / 1000).toFixed(2) + " km" : Math.round(m) + " m");
	const pad = (n) => ("0" + n).slice(-2);
	const ymd = (d) => d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
	const dmy = (s) => (s ? s.slice(8, 10) + "-" + s.slice(5, 7) + "-" + s.slice(0, 4) : "");
	const ICON = {
		finger: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 11v3a8 8 0 0 1-1.5 4.7"/><path d="M8.5 9.5A4 4 0 0 1 16 11v2c0 2.4-.6 4.6-1.6 6.5"/><path d="M5.6 7.5A7 7 0 0 1 19 11v1.5"/><path d="M5 12v1a11 11 0 0 0 .9 4.4"/><path d="M8 12.5v.5a12 12 0 0 1-1 4.8"/></svg>`,
		home: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
		cal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
		team: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><circle cx="17" cy="9" r="2.5"/><path d="M16 14.2a5 5 0 0 1 5.5 4.8"/></svg>`,
	};

	// ---------------------------------------------------------------- login + page setup
	function cookie(n) { const m = document.cookie.match("(^|;)\\s*" + n + "=([^;]*)"); return m ? decodeURIComponent(m[2]) : ""; }
	const who = cookie("user_id");
	if (!who || who === "Guest") { window.location.href = "/login?redirect-to=" + encodeURIComponent(APP); return; }
	document.body.classList.add("sbo-body");
	document.title = "SBI Office";
	[["manifest", MANIFEST], ["apple-touch-icon", APPICON], ["icon", APPICON]].forEach((x) => {
		const l = document.createElement("link"); l.rel = x[0]; l.href = x[1]; document.head.appendChild(l);
	});
	const IOS = /iphone|ipad|ipod/i.test(navigator.userAgent || "") || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
	const STANDALONE = window.navigator.standalone === true || (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches);
	[["theme-color", "#c8102e"], ["mobile-web-app-capable", "yes"], ["apple-mobile-web-app-capable", "yes"], ["apple-mobile-web-app-title", "SBI Office"], ["apple-mobile-web-app-status-bar-style", "black-translucent"]].forEach((m) => {
		const t = document.createElement("meta"); t.name = m[0]; t.content = m[1]; document.head.appendChild(t);
	});
	let swReg = null;
	if ("serviceWorker" in navigator) {
		navigator.serviceWorker.register(SW, { scope: "/files/" }).then((r) => { swReg = r; }).catch(() => { /* reminders still work while the app is open */ });
	}

	// ---------------------------------------------------------------- server calls (CSRF-safe)
	async function token(fresh) {
		if (!fresh) {
			if (S.csrf) return S.csrf;
			if (window.frappe && window.frappe.csrf_token && window.frappe.csrf_token.indexOf("{") < 0) return window.frappe.csrf_token;
		}
		try {
			const t = await fetch(APP + "?_=" + Date.now(), { credentials: "same-origin", cache: "no-store" }).then((r) => r.text());
			const m = t.match(/csrf_token\s*[=:]\s*["']([^"'{}]+)["']/);
			S.csrf = m ? m[1] : "";
		} catch (e) { S.csrf = ""; }
		return S.csrf;
	}
	function serverMsg(j) {
		try {
			if (j._server_messages) return JSON.parse(j._server_messages).map((x) => { try { return JSON.parse(x).message; } catch (e) { return x; } }).join(" ").replace(/<[^>]+>/g, "");
		} catch (e) { /* ignore */ }
		return (j.exception || j.message || "Something went wrong").toString().replace(/^.*?Error:\s*/, "");
	}
	async function call(act, args, retried) {
		const base = { act: act };
		if (S.asEmp) base.as_employee = S.asEmp;
		const body = new URLSearchParams(Object.assign(base, args || {}));
		const r = await fetch("/api/method/" + API, { method: "POST", credentials: "same-origin", body: body,
			headers: { "Accept": "application/json", "X-Frappe-CSRF-Token": await token(retried), "X-Requested-With": "XMLHttpRequest" } });
		let j = {};
		try { j = await r.json(); } catch (e) { /* not json */ }
		if (!retried && r.status === 400 && /csrf/i.test(JSON.stringify(j))) return call(act, args, true);
		if (r.status === 401 || (r.status === 403 && /login|guest/i.test(JSON.stringify(j)))) { window.location.href = "/login?redirect-to=" + encodeURIComponent(APP); throw new Error("login"); }
		if (!r.ok) throw new Error(serverMsg(j));
		return j.message || {};
	}
	function toast(msg, kind) {
		const t = document.createElement("div");
		t.className = "sbo-toast sbo-banner " + (kind || "warn");
		t.style.cssText = "position:fixed;left:12px;right:12px;bottom:86px;z-index:70;max-width:536px;margin:0 auto;box-shadow:0 8px 24px rgba(0,0,0,.18)";
		t.innerHTML = esc(msg);
		document.body.appendChild(t);
		setTimeout(() => t.remove(), 6000);
	}

	// ---------------------------------------------------------------- GPS
	function distTo(o, p) {
		if (!o || !o.set || !p) return null;
		const k = Math.PI / 180, dLat = (p.lat - o.lat) * k, dLng = (p.lng - o.lng) * k;
		const a = Math.sin(dLat / 2) ** 2 + Math.cos(o.lat * k) * Math.cos(p.lat * k) * Math.sin(dLng / 2) ** 2;
		return 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
	}
	// street / area / city for the current location (OpenStreetMap, then BigDataCloud as a backup)
	const ADDR = { key: "", busy: false, at: null };
	const JUNK = /^(ward|zone|division|block)\s*(no\.?)?\s*\d+/i;
	const clean = (v) => String(v || "").replace(/^zone\s*\d+\s*/i, "").trim();
	const good = (v) => !!v && !JUNK.test(String(v).trim());
	function uniq(list) {
		const seen = {}, out = [];
		list.forEach((v) => { v = clean(v); const k = v.toLowerCase(); if (v && good(v) && !seen[k]) { seen[k] = 1; out.push(v); } });
		return out;
	}
	function addrText(a) {
		if (!a) return "";
		return uniq([a.place, a.street, a.area, a.locality, a.city]).join(", ") + (a.pin ? " – " + a.pin : "");
	}
	async function overpass(q) {
		for (const host of ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]) {
			const ctl = window.AbortController ? new AbortController() : null;
			const tm = setTimeout(() => { try { ctl && ctl.abort(); } catch (e) { /* ignore */ } }, 7000);
			try {
				const r = await fetch(host, { method: "POST", signal: ctl ? ctl.signal : undefined, body: "data=" + encodeURIComponent(q), headers: { "Content-Type": "application/x-www-form-urlencoded" } });
				clearTimeout(tm);
				if (r.ok) return await r.json();
			} catch (e) { clearTimeout(tm); /* slow or down: try the next server */ }
		}
		return null;
	}
	async function nearbyPlace(p) {
		// 1) the building you are standing INSIDE (its outline contains your GPS point)
		const ll = p.lat + "," + p.lng;
		const inside = await overpass("[out:json][timeout:8];is_in(" + ll + ")->.a;(way(pivot.a)[building][name];relation(pivot.a)[building][name];" +
			"way(pivot.a)[name][amenity];way(pivot.a)[name][office];way(pivot.a)[name][landuse=commercial];);out tags 5;");
		const own = ((inside && inside.elements) || []).find((e) => e.tags && e.tags.name && (e.tags.building || e.tags.office));
		const any = ((inside && inside.elements) || []).find((e) => e.tags && e.tags.name);
		if (own || any) return { name: (own || any).tags.name, inside: true };
		// 2) otherwise the closest named building / office within 25 m, shown as "near ..."
		const r = Math.max(15, Math.min(25, p.acc || 25));
		const j = await overpass("[out:json][timeout:8];(nwr(around:" + r + "," + ll + ")[name][building];nwr(around:" + r + "," + ll + ")[name][office];);out tags center 10;");
		let best = null, bd = 1e9;
		((j && j.elements) || []).forEach((e) => {
			const la = e.lat || (e.center && e.center.lat), lo = e.lon || (e.center && e.center.lon);
			if (!la || !e.tags || !e.tags.name) return;
			const dd = distTo({ set: 1, lat: la, lng: lo }, p);
			if (dd < bd) { bd = dd; best = e.tags.name; }
		});
		return best ? { name: best, inside: false } : null;
	}
	async function geocode(force) {
		const p = S.pos;
		if (!p || ADDR.busy) return;
		if (!force && ADDR.at && distTo({ set: 1, lat: ADDR.at.lat, lng: ADDR.at.lng }, p) < 40 && !(ADDR.at.acc > 60 && p.acc < ADDR.at.acc / 2)) return;
		ADDR.busy = true;
		let a = null;
		try {
			const u = "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=18&addressdetails=1&namedetails=1&accept-language=en&lat=" + p.lat + "&lon=" + p.lng;
			const ctl = window.AbortController ? new AbortController() : null;
			const tm = setTimeout(() => { try { ctl && ctl.abort(); } catch (e) { /* ignore */ } }, 8000);
			const j = await fetch(u, { headers: { "Accept": "application/json" }, signal: ctl ? ctl.signal : undefined }).then((r) => r.json()).finally(() => clearTimeout(tm));
			const x = j.address || {};
			let named = ["building", "amenity", "shop", "office", "tourism", "leisure", "healthcare", "craft"].indexOf(j.category) >= 0 ? j.name : "";
			const objD = j.lat ? distTo({ set: 1, lat: Number(j.lat), lng: Number(j.lon) }, p) : 0;
			if (named && objD > 20 && j.category !== "building") named = "";
			// pieces from the long name, without "Ward 178" / "Zone 13" parts
			const parts = String(j.display_name || "").split(",").map((s) => s.trim());
			a = {
				place: named || (objD <= 20 ? (x.building || x.office || x.amenity || "") : "") || x.residential || x.commercial || x.industrial || "",
				street: [x.house_number, x.road || x.pedestrian || x.footway || x.street].filter(Boolean).join(" "),
				area: [x.neighbourhood, x.quarter, x.residential, x.hamlet, x.village].find(good) || "",
				locality: [x.county, x.city_district, x.suburb, x.town].map(clean).find(good) || "",
				city: [x.city, x.town, x.municipality, x.state_district].map(clean).find(good) || "",
				state: x.state || "", pin: x.postcode || "", full: parts.filter(good).join(", "),
			};
			if (a.area && a.locality && a.area.toLowerCase() === a.locality.toLowerCase()) a.area = "";
		} catch (e) { a = null; }
		if (!a || !(a.street || a.area || a.locality || a.city)) {
			try {
				const j = await fetch("https://api.bigdatacloud.net/data/reverse-geocode-client?localityLanguage=en&latitude=" + p.lat + "&longitude=" + p.lng).then((r) => r.json());
				const adm = ((j.localityInfo && j.localityInfo.administrative) || []).map((x) => x.name).filter(good);
				a = { place: "", street: "", area: "", locality: (adm[adm.length - 1] || j.locality || "").replace(/ taluk$/i, ""), city: j.city || "", state: j.principalSubdivision || "", pin: j.postcode || "" };
			} catch (e) { /* offline */ }
		}
		const of = (S.d && S.d.office) || {};
		const din = distTo(of, p);
		if (a && of.name && din !== null && din <= (of.radius || 200) + Math.min(p.acc || 0, 100)) a.place = of.name;
		if (a) a.acc = p.acc;
		ADDR.busy = false;
		if (a && (a.place || a.street || a.area || a.locality || a.city)) {
			S.addr = a;
			ADDR.at = { lat: p.lat, lng: p.lng, acc: p.acc };
			gpsPaint();
			if (!a.place || a.place === (a.area || "") || /complex|nagar|colony/i.test(a.place)) {
				nearbyPlace(p).then((near) => {
					if (!near || S.addr !== a) return;
					if (near.inside) a.place = near.name;
					else if (!a.place) a.place = "Near " + near.name;
					gpsPaint();
				}).catch(() => {});
			}
		}
	}
	function startGps() {
		if (!navigator.geolocation) { S.gpsErr = "This phone / browser has no GPS."; gpsPaint(); return; }
		if (S.watch !== null) return;
		S.watch = navigator.geolocation.watchPosition((p) => {
			S.pos = { lat: p.coords.latitude, lng: p.coords.longitude, acc: Math.round(p.coords.accuracy || 0), at: Date.now() };
			S.gpsErr = "";
			gpsPaint();
			geocode(false);
		}, (e) => {
			S.gpsErr = e.code === 1 ? "Location is blocked. Allow location for this app in the phone settings, then reload." : "Finding your location… (" + e.message + ")";
			gpsPaint();
		}, { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 });
	}
	function gpsState() {
		const o = (S.d && S.d.office) || {}, e = (S.d && S.d.employee) || {};
		if (S.gpsErr && !S.pos) return { cls: "bad", txt: S.gpsErr, ok: !(o.block && o.set && !e.anywhere) };
		if (!S.pos) return { cls: "", txt: "Finding your location…", ok: !(o.block && o.set && !e.anywhere) };
		const d = distTo(o, S.pos);
		if (d === null) return { cls: "ok", txt: `Location found (±${S.pos.acc} m)${o.set ? "" : " · office place not set yet"}`, ok: true, d: null };
		const inside = d <= (o.radius || 200) + Math.min(S.pos.acc, 100);
		const strict = o.block && !e.anywhere;
		if (inside) return { cls: S.pos.acc > 150 ? "warn" : "ok", txt: `Inside ${esc(o.name || "the office")} · ${km(d)} away (±${S.pos.acc} m)`, ok: true, d: d, inside: true };
		return { cls: strict ? "bad" : "warn", d: d, inside: false, ok: !strict,
			txt: strict ? `You are ${km(d)} from ${esc(o.name || "the office")}. Punch works only within ${o.radius} m.`
				: `Outside ${esc(o.name || "the office")} · ${km(d)} away. The punch will be marked “outside”.` };
	}
	function gpsPaint() {
		const g = gpsState();
		const rough = S.pos && S.pos.acc > 60 ? `<br><span style="opacity:.8">⚠ Location is rough (±${S.pos.acc} m) – the building may be wrong. On a phone, turn on GPS / “precise location”; on a computer the place is only guessed from Wi-Fi.</span>` : "";
		const at = (S.addr ? `<br><b>📍 ${esc(addrText(S.addr))}</b>` : (S.pos ? `<br><span style="opacity:.75">📍 finding street name…</span>` : "")) + rough;
		document.querySelectorAll("[data-gps]").forEach((el) => { el.innerHTML = `<span class="sbo-dot ${g.cls}"></span><span>${g.txt}${at}</span>`; });
		const sh = $("#sbo-shutter");
		if (sh && !S.shot) sh.disabled = !g.ok;
		const ring = $(".sbo-ring");
		if (ring) {
			ring.classList.toggle("off", !g.ok);
			const sub = ring.querySelector("span");
			if (sub) sub.textContent = g.ok ? "tap \u00b7 selfie + location" : (S.pos ? "come inside the office" : "waiting for location\u2026");
		}
		const rw = $("#sbo-reason");
		if (rw) rw.classList.toggle("hide", !(g.d !== null && g.d !== undefined && g.inside === false && g.ok));
	}

	// ---------------------------------------------------------------- reminders (notifications)
	function remTargets() {
		const d = S.d || {}, o = d.office || {};
		const rem = Number(o.reminder || 0);
		if (!d.employee || !rem || d.is_holiday) return [];
		const today = ymd(new Date()), out = [];
		const at = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); const x = new Date(); x.setHours(h, m - rem, 0, 0); return x; };
		if (o.in_time && !(d.logs || []).length) out.push({ key: today + "-IN", when: at(o.in_time), title: "Punch IN in " + rem + " min", body: "Office starts at " + o.in_time + ". Open SBI Office and punch IN." });
		if (o.out_time && d.next === "OUT") out.push({ key: today + "-OUT", when: at(o.out_time), title: "Punch OUT in " + rem + " min", body: "Office ends at " + o.out_time + ". Punch OUT before you leave." });
		return out;
	}
	const NATIVE = window.SBIApp && typeof window.SBIApp.schedule === "function" ? window.SBIApp : null;
	function nativeSchedule() {
		// Android app: real phone alarms that ring even when the app is closed
		if (!NATIVE || !S.d || !S.d.employee || S.asEmp) return;
		const o = S.d.office || {}, rem = Number(o.reminder || 0);
		["IN-today", "OUT-today", "IN-next"].forEach((k) => { try { NATIVE.cancel(k); } catch (e) { /* ignore */ } });
		if (!rem) return;
		const now = Date.now();
		remTargets().forEach((t) => {
			if (t.when.getTime() > now) { try { NATIVE.schedule(t.key.slice(11) + "-today", String(t.when.getTime()), t.title, t.body); } catch (e) { /* ignore */ } }
		});
		if (o.in_time && !S.d.tomorrow_holiday) {
			const [h, m] = o.in_time.split(":").map(Number);
			const x = new Date(); x.setDate(x.getDate() + 1); x.setHours(h, m - rem, 0, 0);
			try { NATIVE.schedule("IN-next", String(x.getTime()), "Punch IN in " + rem + " min", "Office starts at " + o.in_time + ". Open SBI Office and punch IN."); } catch (e) { /* ignore */ }
		}
	}
	async function notify(t) {
		try { navigator.vibrate && navigator.vibrate([200, 100, 200]); } catch (e) { /* ignore */ }
		if (NATIVE) { try { NATIVE.notify(t.title, t.body); return; } catch (e) { /* fall back */ } }
		if (!("Notification" in window) || Notification.permission !== "granted") { toast(t.title + " – " + t.body, "info"); return; }
		const opt = { body: t.body, tag: "sbo-" + t.key, renotify: true, icon: (S.d && S.d.logo) || undefined, data: { url: APP } };
		try {
			const reg = swReg || (navigator.serviceWorker && await navigator.serviceWorker.getRegistration("/files/"));
			if (reg) { await reg.showNotification(t.title, opt); return; }
		} catch (e) { /* fall back */ }
		try { new Notification(t.title, opt); } catch (e) { toast(t.title + " – " + t.body, "info"); }
	}
	function remTick() {
		if (S.asEmp) return;
		const now = Date.now();
		remTargets().forEach((t) => {
			const due = t.when.getTime();
			let done = "";
			try { done = localStorage.getItem("sbo-rem-" + t.key) || ""; } catch (e) { /* private mode */ }
			if (!done && now >= due && now < due + 30 * 60000) {
				try { localStorage.setItem("sbo-rem-" + t.key, "1"); } catch (e) { /* ignore */ }
				notify(t);
			}
		});
	}
	async function askNotify() {
		if (!("Notification" in window)) { toast("This browser cannot show notifications.", "warn"); return; }
		const p = await Notification.requestPermission();
		if (p === "granted") { toast("Reminders are on. You will get a reminder before office time.", "ok"); notify({ key: "test", title: "SBI Office reminders are on", body: "You will be reminded before punch IN and punch OUT." }); }
		render();
	}

	// ---------------------------------------------------------------- screens
	function shell(inner) {
		const d = S.d || {};
		const tabs = [["punch", "Punch", ICON.home], ["month", "My month", ICON.cal]];
		if (d.is_manager) tabs.push(["team", "Team", ICON.team]);
		return `<div class="sbo-top"><div class="sbo-logo">${d.logo ? `<img src="${esc(d.logo)}" alt="">` : "⏱"}</div>
			<div class="sbo-brand"><b>SBI Office</b><span>Staff attendance</span></div>
			<div class="sbo-clock"><b id="sbo-time"></b><span id="sbo-date"></span></div>
			<a class="sbo-lite" href="/desk/lite-erp" title="Open Lite ERP">Lite ERP ›</a></div>
			<div class="sbo-wrap">${inner}</div>
			<nav class="sbo-nav">${tabs.map((t) => `<a data-a="tab" data-t="${t[0]}" class="${S.tab === t[0] ? "on" : ""}">${t[2]}${t[1]}</a>`).join("")}</nav>`;
	}
	function picker() {
		const d = S.d;
		if (!d.is_manager) return "";
		const staff = d.staff || [];
		return `<div class="sbo-card sbo-pick"><h3>👤 Employee <span class="sbo-mut">HR / owner / Administrator</span></h3>
			<select id="sbo-as" data-a="as">${d.own_employee ? `<option value="">Me – ${esc(d.own_employee)}</option>` : `<option value="">— choose an employee —</option>`}
			${staff.map((s) => `<option value="${esc(s.name)}" ${S.asEmp === s.name ? "selected" : ""}>${esc(s.employee_name)}${s.designation ? " · " + esc(s.designation) : ""}</option>`).join("")}</select>
			${S.asEmp ? `<div class="sbo-mut" style="margin-top:6px">You are punching <b>for this employee</b>. The punch is saved as “by HR” with your name, and the office-area limit does not apply.</div>` : ""}</div>`;
	}
	function viewPunch() {
		const d = S.d, e = d.employee, o = d.office || {};
		if (!e && d.is_manager) return picker() + `<div class="sbo-card"><div class="sbo-mut">Your own login (${esc(d.user)}) is not linked to an employee, so you cannot punch for yourself.
			Choose an employee above to punch for them, or open <b>Team</b> to see everyone and change the settings.</div></div>`;
		if (!e) return `<div class="sbo-card"><h3>Your login is not linked to an employee</h3>
			<div class="sbo-mut">To punch, HR must open your <b>Employee</b> record and put your login (<b>${esc(d.user)}</b>) in the <b>User ID</b> field. Then reload this app.</div></div>`;
		const next = d.next || "IN";
		const ini = (e.employee_name || "?").split(" ").map((x) => x[0]).join("").slice(0, 2).toUpperCase();
		const logs = d.logs || [];
		const firstIn = logs.find((l) => l.log_type === "IN");
		const lastOut = logs.filter((l) => l.log_type === "OUT").pop();
		let h = picker();
		if (!NATIVE && "Notification" in window && Notification.permission === "default" && Number(o.reminder))
			h += `<div class="sbo-banner info">🔔 Get a reminder ${o.reminder} min before office time.<button class="sbo-btn sm pri" data-a="notify">Turn on</button></div>`;
		if (d.is_holiday) h += `<div class="sbo-banner info">Today is a holiday. You can still punch if you are working.</div>`;
		if (!o.set) h += `<div class="sbo-banner warn">The office place is not set yet. ${d.is_manager ? "Open Team → Office place, stand inside the office and press “Set office here”." : "Ask HR to set it."}</div>`;
		h += `<div class="sbo-card"><div class="sbo-who"><div class="sbo-av">${e.image ? `<img src="${esc(e.image)}" alt="">` : esc(ini)}</div>
			<div><div class="sbo-name">${esc(e.employee_name)}</div><div class="sbo-mut">${esc([e.designation, e.department].filter(Boolean).join(" · ") || e.name)}</div></div></div>
			<div class="sbo-shift"><div><b>${esc(o.in_time || "–")}</b><span>office starts</span></div><div><b>${esc(o.out_time || "–")}</b><span>office ends</span></div>
				<div><b>${d.hours ? d.hours.toFixed(1) + " h" : "–"}</b><span>worked today</span></div></div>
			<div class="sbo-gps" data-gps></div>
			<div class="sbo-punch"><button class="sbo-ring ${next === "OUT" ? "out" : ""}" data-a="open">${ICON.finger}<b>PUNCH ${next}</b><span>tap · selfie + location</span></button></div>
			<div class="sbo-note sbo-mut">${firstIn ? `In at <b>${esc(firstIn.t)}</b>` : "Not punched in yet"}${lastOut ? ` · Out at <b>${esc(lastOut.t)}</b>` : ""} · ${d.month || 0} day(s) this month</div></div>`;
		let appCard = !NATIVE && /android/i.test(navigator.userAgent || "") ? `<div class="sbo-banner info">📱 Install the SBI Office Android app for punch reminders.<a class="sbo-btn sm pri" href="${APK}" download>Download</a></div>` : "";
		if (IOS && !STANDALONE) appCard = `<div class="sbo-banner info">📱 <span><b>Install on iPhone:</b> open this page in <b>Safari</b>, tap <b>Share</b> (□↑) → <b>Add to Home Screen</b> → Add. SBI Office then opens like an app.</span></div>`;
		const faces = e.enrolled ? `<div class="sbo-card"><h3>Face record <span class="sbo-mut">${esc(e.sbi_face_on ? "taken " + e.sbi_face_on : "")}</span></h3>
			<div class="sbo-faces">${["front", "left", "right"].map((k) => e["sbi_face_" + k] ? `<a href="${esc(e["sbi_face_" + k])}" target="_blank"><img src="${esc(e["sbi_face_" + k])}" alt=""><i>${k}</i></a>` : "").join("")}</div>
			${d.is_manager ? `<div class="sbo-row"><button class="sbo-btn sm" data-a="resetface">Retake face photos</button></div>` : ""}</div>`
			: `<div class="sbo-banner info">📸 First punch: the app takes 3 face photos (front, left, right) for your record. It takes 20 seconds.</div>`;
		h += appCard + `<div class="sbo-card"><h3>Today</h3>${logs.length ? `<ul class="sbo-tl">${logs.map((l) => `<li><span class="sbo-tag ${l.log_type === "OUT" ? "out" : ""}">${esc(l.log_type)}</span>
			<span class="t">${esc(l.t)}</span><span class="m">${l.distance ? km(l.distance) + " from office" : ""}${l.within === 0 ? ` <span class="sbo-pill r">outside</span>` : ""}
			${l.address ? `<br>📍 ${esc(l.address)}` : ""}${l.photo ? `<br><a href="${esc(l.photo)}" target="_blank">selfie</a>` : ""}${l.latitude ? ` · <a href="https://maps.google.com/?q=${l.latitude},${l.longitude}" target="_blank">map</a>` : ""}</span></li>`).join("")}</ul>`
			: `<div class="sbo-mut">No punch yet today.</div>`}</div>`;
		h += faces;
		return h;
	}
	function viewMonth() {
		const m = S.month;
		if (!m) return `<div class="sbo-card"><div class="sbo-mut">Loading…</div></div>`;
		const days = m.days || [];
		return `<div class="sbo-card"><h3>My salary month <span class="sbo-mut">${dmy(m.from)} – ${dmy(m.to)}</span></h3>
			<div class="sbo-row" style="margin:0 0 10px"><button class="sbo-btn sm" data-a="mprev">‹ Previous</button>${m.back ? `<button class="sbo-btn sm" data-a="mnext">Next ›</button>` : ""}</div>
			<div class="sbo-sum"><div><b>${days.length}</b><span>days present</span></div><div><b>${(m.hours || 0).toFixed(1)}</b><span>hours</span></div><div><b>${m.late || 0}</b><span>late days</span></div></div>
			${days.length ? `<table class="sbo-tbl"><thead><tr><th>Date</th><th>In</th><th>Out</th><th class="r">Hours</th></tr></thead><tbody>
			${days.map((r) => `<tr><td>${dmy(r.d)}</td><td>${esc(r.first_in || "–")}${r.late ? ` <span class="sbo-pill a">late</span>` : ""}</td>
				<td>${esc(r.last_out || "–")}${r.outside ? ` <span class="sbo-pill r">outside</span>` : ""}</td><td class="r">${r.hours ? r.hours.toFixed(2) : "–"}</td></tr>`).join("")}</tbody></table>`
			: `<div class="sbo-mut">No punches in this month.</div>`}</div>`;
	}
	function viewTeam() {
		const d = S.d, o = d.office || {}, team = d.team || [];
		const inn = team.filter((t) => t.last_type === "IN").length;
		let h = `<div class="sbo-card"><h3>Team today <span class="sbo-mut">${inn} in · ${team.filter((t) => t.punches).length}/${team.length} punched</span></h3>
			<table class="sbo-tbl"><thead><tr><th>Name</th><th>In</th><th>Out</th><th>Status</th></tr></thead><tbody>
			${team.map((t) => `<tr data-a="pick" data-e="${esc(t.employee)}" style="cursor:pointer"><td><b>${esc(t.employee_name)}</b><div class="sbo-mut">${esc(t.designation || t.employee)}</div></td><td>${esc(t.first_in || "–")}</td><td>${esc(t.last_out || "–")}</td>
				<td>${!t.punches ? (t.user_id ? `<span class="sbo-pill">not punched</span>` : `<span class="sbo-pill a">no login</span>`) : t.last_type === "IN" ? `<span class="sbo-pill g">in office</span>` : `<span class="sbo-pill">left</span>`}
				${t.outside ? ` <span class="sbo-pill r">${t.outside} outside</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`;
		h += `<div class="sbo-card"><h3>Office place <span class="sbo-mut">HR / owner</span></h3>
			<div class="sbo-mut">${o.set ? `${esc(o.name || "Office")} · ${Number(o.lat).toFixed(6)}, ${Number(o.lng).toFixed(6)} · allowed area ${o.radius} m ·
				<a href="https://maps.google.com/?q=${o.lat},${o.lng}" target="_blank">map</a>` : "Not set yet. Stand inside the office and press “Set office here”."}</div>
			<div class="sbo-gps" data-gps></div>
			<label>Office name</label><input id="sbo-oname" value="${esc(o.name || "")}" placeholder="e.g. Head office">
			<label>Allowed area (metres)</label><input id="sbo-orad" type="number" min="20" step="10" value="${o.radius || 200}">
			<div class="sbo-row"><button class="sbo-btn pri" data-a="setoffice">📍 Set office here</button></div>
			</div>
			<div class="sbo-card"><h3>⚙ Settings <span class="sbo-mut">HR / owner</span></h3>
			<div class="sbo-sum" style="grid-template-columns:1fr 1fr">
				<div><label style="margin:0">Office starts at</label><input id="sbo-in" type="time" value="${esc(o.in_time || "09:30")}"></div>
				<div><label style="margin:0">Office ends at</label><input id="sbo-out" type="time" value="${esc(o.out_time || "18:30")}"></div>
				<div><label style="margin:0">Late after (minutes)</label><input id="sbo-grace" type="number" min="0" max="240" value="${o.grace || 0}"></div>
				<div><label style="margin:0">Reminder before (minutes)</label><input id="sbo-rem" type="number" min="0" max="120" value="${o.reminder || 0}"></div>
				<div><label style="margin:0">Salary month starts on day</label><input id="sbo-sd" type="number" min="1" max="28" value="${d.start_day || 1}"></div>
				<div><label style="margin:0">Allowed area (metres)</label><input id="sbo-rad2" type="number" min="20" step="10" value="${o.radius || 200}"></div></div>
			<label style="display:flex;gap:8px;align-items:center;color:var(--ink);font-size:13.5px"><input type="checkbox" id="sbo-block" style="width:auto" ${o.block ? "checked" : ""}> Allow punch only inside the office area</label>
			<div class="sbo-row"><button class="sbo-btn pri" data-a="savesettings">Save settings</button></div>
			<div class="sbo-mut" style="margin-top:6px">Tap a name in “Team today” to open that employee and punch for them.</div></div>
			<div class="sbo-card"><h3>📱 Android app</h3><div class="sbo-mut">Share this link with staff. They open it on their Android phone, install, and log in once.</div>
				<div class="sbo-row"><input readonly value="${esc(location.origin + APK)}" onclick="this.select()"><a class="sbo-btn pri" href="${APK}" download>Download APK</a></div></div>`;
		return h;
	}
	function render() {
		if (!S.d) return;
		const body = S.tab === "month" ? viewMonth() : S.tab === "team" && S.d.is_manager ? viewTeam() : viewPunch();
		$("#sbo").innerHTML = shell(body);
		clock();
		gpsPaint();
	}
	function clock() {
		const n = new Date();
		const t = $("#sbo-time"), d = $("#sbo-date");
		if (t) t.textContent = n.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
		if (d) d.textContent = n.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" });
	}

	// ---------------------------------------------------------------- camera + punch
	// ---- photo helpers: GPS stamp burnt into the picture + GPS / time written into the JPEG (EXIF)
	function exifJpeg(dataUrl, m) {
		try {
			const bin = atob(dataUrl.split(",")[1]);
			const jpg = new Uint8Array(bin.length);
			for (let i = 0; i < bin.length; i++) jpg[i] = bin.charCodeAt(i);
			const asc = (s) => { const a = []; for (const ch of String(s)) { const c = ch.charCodeAt(0); a.push(c > 31 && c < 127 ? c : 63); } a.push(0); return a; };
			const u16 = (n) => [n & 255, (n >>> 8) & 255];
			const u32 = (n) => [n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255];
			const rat = (num, den) => u32(Math.round(num)).concat(u32(den));
			const dms = (v) => { v = Math.abs(v); const d = Math.floor(v), mm = Math.floor((v - d) * 60), ss = ((v - d) * 60 - mm) * 60; return rat(d, 1).concat(rat(mm, 1), rat(ss * 1000, 1000)); };
			const block = (entries, start) => {
				const head = u16(entries.length), data = [];
				const dataOff = start + 2 + 12 * entries.length + 4;
				entries.forEach(([tag, type, count, val]) => {
					head.push(...u16(tag), ...u16(type), ...u32(count));
					if (val.length <= 4) { const v = val.slice(); while (v.length < 4) v.push(0); head.push(...v); }
					else { head.push(...u32(dataOff + data.length)); data.push(...val); if (data.length % 2) data.push(0); }
				});
				return head.concat([0, 0, 0, 0], data);
			};
			const dt = m.when;
			const p2 = (n) => ("0" + n).slice(-2);
			const stamp = dt.getFullYear() + ":" + p2(dt.getMonth() + 1) + ":" + p2(dt.getDate()) + " " + p2(dt.getHours()) + ":" + p2(dt.getMinutes()) + ":" + p2(dt.getSeconds());
			const tz = -dt.getTimezoneOffset(), tzs = (tz >= 0 ? "+" : "-") + p2(Math.floor(Math.abs(tz) / 60)) + ":" + p2(Math.abs(tz) % 60);
			const desc = asc(m.desc || "SBI Office");
			const ifd0 = (ex, gp) => [[0x010E, 2, desc.length, desc], [0x010F, 2, 11, asc("SBI Office")], [0x0131, 2, 11, asc("SBI Office")],
				[0x0132, 2, 20, asc(stamp)], [0x8769, 4, 1, u32(ex)]].concat(m.lat !== undefined ? [[0x8825, 4, 1, u32(gp)]] : []);
			const exif = [[0x9003, 2, 20, asc(stamp)], [0x9011, 2, 7, asc(tzs)]];
			let b0 = block(ifd0(0, 0), 8);
			const exOff = 8 + b0.length;
			const bE = block(exif, exOff);
			const gpOff = exOff + bE.length;
			b0 = block(ifd0(exOff, gpOff), 8);
			let bG = [];
			if (m.lat !== undefined) {
				const gd = dt.getUTCFullYear() + ":" + p2(dt.getUTCMonth() + 1) + ":" + p2(dt.getUTCDate());
				const gps = [[0x0000, 1, 4, [2, 3, 0, 0]], [0x0001, 2, 2, asc(m.lat >= 0 ? "N" : "S")], [0x0002, 5, 3, dms(m.lat)],
					[0x0003, 2, 2, asc(m.lng >= 0 ? "E" : "W")], [0x0004, 5, 3, dms(m.lng)],
					[0x0007, 5, 3, rat(dt.getUTCHours(), 1).concat(rat(dt.getUTCMinutes(), 1), rat(dt.getUTCSeconds(), 1))],
					[0x001D, 2, 11, asc(gd)], [0x001F, 5, 1, rat((m.acc || 0) * 10, 10)]];
				bG = block(gps, gpOff);
			}
			const tiff = [0x49, 0x49, 0x2A, 0x00, 8, 0, 0, 0].concat(b0, bE, bG);
			const len = 2 + 6 + tiff.length;
			const app1 = [0xFF, 0xE1, (len >> 8) & 255, len & 255, 0x45, 0x78, 0x69, 0x66, 0, 0].concat(tiff);
			const out = new Uint8Array(jpg.length + app1.length);
			out.set(jpg.subarray(0, 2), 0); out.set(app1, 2); out.set(jpg.subarray(2), 2 + app1.length);
			let s = "";
			for (let i = 0; i < out.length; i += 0x8000) s += String.fromCharCode.apply(null, out.subarray(i, i + 0x8000));
			return "data:image/jpeg;base64," + btoa(s);
		} catch (e) { return dataUrl; }
	}
	function grab(maxW) {
		const v = $("#sbo-video");
		if (!S.stream || !v || !v.videoWidth) return null;
		const z = S.zoom > 1 ? S.zoom : 1;   // zoom out (below 1×) keeps the whole picture
		const sw = v.videoWidth / z, sh = v.videoHeight / z;
		const ccx = S.cx === null ? v.videoWidth / 2 : S.cx, ccy = S.cy === null ? v.videoHeight / 2 : S.cy;
		const sx = Math.max(0, Math.min(v.videoWidth - sw, ccx - sw / 2)), sy = Math.max(0, Math.min(v.videoHeight - sh, ccy - sh / 2));
		const w = Math.min(maxW, Math.round(sw) || maxW), h = Math.round(w * sh / sw);
		const c = document.createElement("canvas");
		c.width = w; c.height = h;
		const g = c.getContext("2d");
		g.translate(w, 0); g.scale(-1, 1); g.drawImage(v, sx, sy, sw, sh, 0, 0, w, h); g.setTransform(1, 0, 0, 1, 0, 0);
		return { c: c, g: g, w: w, h: h };
	}
	function wrapLines(g, text, maxW) {
		const words = String(text).split(" "), out = [];
		let line = "";
		words.forEach((wd) => {
			const t = line ? line + " " + wd : wd;
			if (g.measureText(t).width > maxW && line) { out.push(line); line = wd; } else line = t;
		});
		if (line) out.push(line);
		return out;
	}
	function snapPhoto() {
		const f = grab(1080);
		if (!f) return "";
		const { c, g, w, h } = f;
		const e = S.d.employee || {}, o = S.d.office || {}, p = S.pos, dd = distTo(o, p), now = new Date(), next = S.d.next || "IN";
		const base = Math.max(14, Math.round(w / 40));
		const pad = Math.round(base * 0.8);
		const when = now.toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short", year: "numeric" }) + "  " +
			now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + "  GMT" + (-now.getTimezoneOffset() >= 0 ? "+" : "-") +
			("0" + Math.floor(Math.abs(now.getTimezoneOffset()) / 60)).slice(-2) + ":" + ("0" + Math.abs(now.getTimezoneOffset()) % 60).slice(-2);
		const tl = (S.d.logs || []).map((l) => l.log_type + " " + l.t).concat([next + " " + now.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false })]);
		const rows = [];
		g.font = "bold " + Math.round(base * 1.25) + "px Arial";
		rows.push({ t: (e.employee_name || "") + "  ·  PUNCH " + next, f: g.font, c: next === "OUT" ? "#fecaca" : "#bbf7d0" });
		g.font = "bold " + base + "px Arial";
		const A = S.addr || {};
		const ad1 = uniq([A.place, A.street]).join(", ");
		const ad2 = uniq([A.area, A.locality]).join(", ");
		const ad3 = uniq([A.city, A.state]).join(", ") + (A.pin ? " – " + A.pin : "");
		if (!S.addr) rows.push({ t: "Address not found (no internet for maps)", f: g.font, c: "#fff" });
		[ad1, ad2, ad3].forEach((ln) => { if (ln.trim()) wrapLines(g, ln, w - pad * 2).forEach((t) => rows.push({ t: t, f: g.font, c: "#fff" })); });
		g.font = base + "px Arial";
		rows.push({ t: p ? "Lat " + p.lat.toFixed(6) + "°  Long " + p.lng.toFixed(6) + "°  ±" + p.acc + " m" : "GPS not available", f: g.font, c: "#e5e7eb" });
		if (dd !== null) rows.push({ t: km(dd) + " from " + (o.name || "office") + (dd <= (o.radius || 200) + Math.min((p && p.acc) || 0, 100) ? "  (inside)" : "  (outside)"), f: g.font, c: "#e5e7eb" });
		rows.push({ t: when, f: g.font, c: "#e5e7eb" });
		wrapLines(g, "Today: " + tl.join("  →  "), w - pad * 2).forEach((t) => rows.push({ t: t, f: g.font, c: "#fde68a" }));
		const lh = Math.round(base * 1.45);
		const bh = rows.length * lh + pad * 1.6;
		g.fillStyle = "rgba(0,0,0,.62)"; g.fillRect(0, h - bh, w, bh);
		g.fillStyle = "#c8102e"; g.fillRect(0, h - bh, Math.max(6, Math.round(base * 0.35)), bh);
		let y = h - bh + pad + base;
		rows.forEach((r) => { g.font = r.f; g.fillStyle = r.c; g.fillText(r.t, pad + Math.round(base * 0.4), y); y += lh; });
		g.font = "bold " + Math.round(base * 0.9) + "px Arial"; g.fillStyle = "rgba(255,255,255,.85)";
		const tag = "SBI Office";
		g.fillText(tag, w - pad - g.measureText(tag).width, pad + base);
		const url = c.toDataURL("image/jpeg", 0.8);
		return exifJpeg(url, { when: now, lat: p ? p.lat : undefined, lng: p ? p.lng : undefined, acc: p ? p.acc : 0,
			desc: (e.employee_name || "") + " PUNCH " + next + " | " + addrText(S.addr).replace("\u2013", "-") + (p ? " | " + p.lat.toFixed(6) + "," + p.lng.toFixed(6) : "") });
	}
	function snapFace(side) {
		const f = grab(720);
		if (!f) return "";
		const { c, g, w, h } = f;
		const base = Math.max(13, Math.round(w / 42));
		g.fillStyle = "rgba(0,0,0,.55)"; g.fillRect(0, h - base * 2.2, w, base * 2.2);
		g.fillStyle = "#fff"; g.font = "bold " + base + "px Arial";
		g.fillText(((S.d.employee || {}).employee_name || "") + " · face record · " + side + " · " + new Date().toLocaleString("en-IN"), base * 0.7, h - base * 0.75);
		return c.toDataURL("image/jpeg", 0.82);
	}

	// ---- camera overlay: first time = face record (front, left, right), then the punch selfie
	const FACE_STEPS = [
		{ k: "front", t: "1 of 3 · Look straight at the camera", arrow: "◉" },
		{ k: "left", t: "2 of 3 · Turn your face a little to your LEFT", arrow: "◀" },
		{ k: "right", t: "3 of 3 · Turn your face a little to your RIGHT", arrow: "▶" },
	];
	function camMsg(t) { const m = $("#sbo-cam-msg"); if (m) m.innerHTML = t; }
	function setMode(mode) {
		S.mode = mode;
		const d = S.d, next = d.next || "IN", e = d.employee || {};
		const enroll = mode === "enroll";
		$("#sbo-cam-title").textContent = enroll ? "Face record (one time)" : "Punch " + next;
		$("#sbo-thumbs").classList.toggle("hide", !enroll);
		$("#sbo-reason-wrap").classList.toggle("hide", enroll);
		document.querySelectorAll("#sbo-cam [data-gps]").forEach((x) => x.classList.toggle("hide", enroll));
		const sh = $("#sbo-shutter");
		sh.classList.toggle("out", !enroll && next === "OUT");
		sh.classList.toggle("enroll", enroll);
		$("#sbo-save-face").classList.add("hide");
		showLive();
		if (enroll) {
			S.faces = S.faces || {};
			const step = FACE_STEPS.find((s) => !S.faces[s.k]);
			paintThumbs();
			if (step) {
				$("#sbo-arrow").textContent = step.arrow;
				$("#sbo-arrow").classList.toggle("hide", step.k === "front");
				camMsg(`<b>${esc(step.t)}</b><br>${esc(e.employee_name || "")} – we keep these 3 photos as your record. The app fits your face in the circle by itself (use <b>−</b> / <b>+</b> if needed). Then tap the button.`);
				sh.disabled = !S.stream;
			} else {
				$("#sbo-arrow").classList.add("hide");
				camMsg("<b>All 3 photos taken.</b> Tap a photo to take it again, or save.");
				sh.disabled = true;
				$("#sbo-save-face").classList.remove("hide");
			}
		} else {
			$("#sbo-arrow").classList.add("hide");
			camMsg("Look at the camera – your face is fitted into the circle automatically (use <b>−</b> / <b>+</b> if needed). Then tap the button.");
			gpsPaint();
		}
	}
	function paintThumbs() {
		$("#sbo-thumbs").innerHTML = FACE_STEPS.map((s) => `<div class="sbo-th ${S.faces[s.k] ? "ok" : ""}" data-a="refacet" data-k="${s.k}">
			${S.faces[s.k] ? `<img src="${S.faces[s.k]}" alt="">` : `<span>${s.arrow}</span>`}<i>${s.k}</i></div>`).join("");
	}
	function showLive() {
		S.shot = "";
		const im = $("#sbo-shot");
		if (im) im.classList.add("hide");
		$("#sbo-video").classList.remove("hide");
		$("#sbo-oval").classList.remove("hide");
		$("#sbo-retake").classList.add("hide");
		$("#sbo-spacer").classList.remove("hide");
		const zb = $("#sbo-zoombar");
		if (zb && S.stream) zb.classList.remove("hide");
	}
	// ---- camera zoom + auto fit: the face is found and zoomed / moved into the circle; the user can still zoom by hand
	const FACEAPI = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/dist/face-api.js";
	const FACEMODEL = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model";
	let faceLib = null;
	function loadFaceApi() {
		if (faceLib) return faceLib;
		faceLib = new Promise((res) => {
			const go = async () => { try { await window.faceapi.nets.tinyFaceDetector.loadFromUri(FACEMODEL); res({ kind: "faceapi" }); } catch (e) { res(null); } };
			if (window.faceapi) { go(); return; }
			const s = document.createElement("script");
			s.src = FACEAPI; s.async = true;
			s.onload = go; s.onerror = () => res(null);
			document.head.appendChild(s);
		});
		return faceLib;
	}
	async function faceLibrary() {
		if (window.FaceDetector) {
			try { return { kind: "native", fd: new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 }) }; } catch (e) { /* not on this device */ }
		}
		return loadFaceApi();
	}
	async function detectFace(v, lib) {
		if (lib.kind === "native") {
			const r = await lib.fd.detect(v);
			return r && r[0] ? { x: r[0].boundingBox.x, y: r[0].boundingBox.y, w: r[0].boundingBox.width, h: r[0].boundingBox.height } : null;
		}
		const r = await window.faceapi.detectSingleFace(v, new window.faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.4 }));
		return r ? { x: r.box.x, y: r.box.y, w: r.box.width, h: r.box.height } : null;
	}
	const ZMIN = 0.1, ZMAX = 4;
	function zoomSetup() {
		S.zoom = 1; S.cx = null; S.cy = null; S.autoFit = true; S.faceSeen = 0;
		const tr = S.stream && S.stream.getVideoTracks()[0];
		try {
			// hardware auto focus where the camera supports it
			const caps = tr && tr.getCapabilities ? tr.getCapabilities() : {};
			if (caps && caps.focusMode && caps.focusMode.indexOf("continuous") >= 0) tr.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
		} catch (e) { /* ignore */ }
		const r = $("#sbo-zoom");
		if (!r) return;
		r.min = ZMIN; r.max = ZMAX; r.step = 0.05; r.value = 1;
		$("#sbo-zoombar").classList.remove("hide");
		zoomApply(1, true);
		autoFitLoop();
	}
	function viewTransform() {
		const v = $("#sbo-video"), st = $("#sbo-cam .sbo-stage"), ov = $("#sbo-oval");
		if (!v || !st) return;
		const vw = v.videoWidth || 1, vh = v.videoHeight || 1;
		const base = Math.min(st.clientWidth / vw, st.clientHeight / vh);
		const z = S.zoom || 1;
		let tx = 0, ty = 0;
		if (S.cx !== null && S.cy !== null && ov) {
			const sr = st.getBoundingClientRect(), orr = ov.getBoundingClientRect();
			const ovalDY = (orr.top + orr.height / 2) - (sr.top + sr.height / 2);
			tx = (S.cx - vw / 2) * base * z;
			ty = -(S.cy - vh / 2) * base * z + ovalDY;
		}
		v.style.transform = "translate(" + tx.toFixed(1) + "px," + ty.toFixed(1) + "px) scaleX(-1) scale(" + z + ")";
	}
	function zoomApply(z, auto) {
		if (!auto) S.autoFit = false;
		z = Math.max(ZMIN, Math.min(ZMAX, Number(z) || 1));
		S.zoom = Math.round(z * 100) / 100;
		const r = $("#sbo-zoom"), lb = $("#sbo-zoomv");
		if (r) r.value = S.zoom;
		if (lb) lb.textContent = (S.autoFit ? "Auto " : "") + (S.zoom < 1 ? S.zoom.toFixed(2).replace(/0$/, "") : S.zoom.toFixed(1)) + "×";
		document.querySelectorAll(".sbo-zp button").forEach((b) => b.classList.toggle("on", b.dataset.a === "zauto" ? !!S.autoFit : !S.autoFit && Math.abs(Number(b.dataset.z) - S.zoom) < 0.01));
		viewTransform();
	}
	function fitTo(f) {
		const v = $("#sbo-video"), st = $("#sbo-cam .sbo-stage"), ov = $("#sbo-oval");
		if (!v || !st || !ov || !v.videoWidth) return;
		const base = Math.min(st.clientWidth / v.videoWidth, st.clientHeight / v.videoHeight);
		// face box (forehead to chin) should fill about 60% of the circle height
		const want = Math.max(ZMIN, Math.min(ZMAX, 0.6 * ov.clientHeight / (f.h * base)));
		const fx = f.x + f.w / 2, fy = f.y + f.h / 2;
		const first = S.cx === null;
		const nz = first ? want : S.zoom + (want - S.zoom) * 0.5;
		S.cx = first ? fx : S.cx + (fx - S.cx) * 0.5;
		S.cy = first ? fy : S.cy + (fy - S.cy) * 0.5;
		if (first || Math.abs(nz - S.zoom) / S.zoom > 0.04) zoomApply(nz, true); else viewTransform();
	}
	async function autoFitLoop() {
		if (S.fitRun) return;
		S.fitRun = true;
		let lib = await faceLibrary();
		const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
		while (S.stream && $("#sbo-cam")) {
			const v = $("#sbo-video");
			if (lib && S.autoFit && !S.shot && v && v.videoWidth && !v.classList.contains("hide")) {
				try {
					const f = await detectFace(v, lib);
					if (f && f.h > 20) { S.faceSeen = Date.now(); fitTo(f); }
				} catch (e) {
					// the built-in detector is not available here: switch to the downloaded one
					if (lib.kind === "native") lib = await loadFaceApi(); else lib = null;
				}
			}
			await sleep(300);
		}
		S.fitRun = false;
	}
	function pinchStart(ev) {
		if (ev.touches && ev.touches.length === 2) {
			const t = ev.touches;
			S.pinch = { d: Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY), z: S.zoom || 1 };
		}
	}
	function pinchMove(ev) {
		if (!S.pinch || !ev.touches || ev.touches.length !== 2) return;
		ev.preventDefault();
		const t = ev.touches;
		const d = Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
		zoomApply(S.pinch.z * d / S.pinch.d);
	}
	async function openCam() {
		const d = S.d, e = d.employee || {};
		S.shot = "";
		S.faces = {};
		const ov = document.createElement("div");
		ov.className = "sbo-cam";
		ov.id = "sbo-cam";
		ov.innerHTML = `<div class="sbo-cam-top"><b id="sbo-cam-title"></b><span style="color:#ddd">${esc(e.employee_name || "")}</span><span style="margin-left:auto" id="sbo-cam-clock"></span></div>
			<div class="sbo-stage"><video id="sbo-video" playsinline autoplay muted></video><img id="sbo-shot" class="hide" alt="">
				<div class="sbo-oval" id="sbo-oval"></div><div class="sbo-arrow hide" id="sbo-arrow"></div>
				<div class="sbo-zoombar hide" id="sbo-zoombar">
					<div class="sbo-zp"><button data-a="zauto" class="on">Auto</button>${[0.1, 0.3, 0.6, 0.8, 1, 2].map((z) => `<button data-a="zset" data-z="${z}">${z}×</button>`).join("")}</div>
					<button data-a="zout" aria-label="Zoom out">−</button>
					<input type="range" id="sbo-zoom" min="1" max="4" step="0.1" value="1" aria-label="Zoom"><button data-a="zin" aria-label="Zoom in">+</button><b id="sbo-zoomv">1.0×</b></div></div>
			<div class="sbo-cam-msg" id="sbo-cam-msg"></div>
			<div class="sbo-thumbs hide" id="sbo-thumbs"></div>
			<div class="sbo-cam-low">
				<div class="sbo-cam-reason hide" id="sbo-reason-wrap"><div class="hide" id="sbo-reason"><input id="sbo-reason-in" placeholder="You are outside – reason (e.g. client visit)"></div></div>
				<div class="sbo-cam-gps" data-gps></div>
				<div class="sbo-cam-bar"><button class="sbo-btn" data-a="cancel">Cancel</button>
					<button class="sbo-shutter" id="sbo-shutter" data-a="snap" aria-label="Take photo"></button>
					<button class="sbo-btn hide" data-a="retake" id="sbo-retake">Retake</button><button class="sbo-btn pri hide" data-a="saveface" id="sbo-save-face">Save photos</button>
					<button class="sbo-btn" data-a="noop" id="sbo-spacer" style="visibility:hidden">.</button></div></div>`;
		document.body.appendChild(ov);
		$("#sbo-cam-clock").textContent = new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
		setMode(e.enrolled === 0 ? "enroll" : "punch");
		try {
			S.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } }, audio: false });
			$("#sbo-video").srcObject = S.stream;
			setMode(S.mode);
			zoomSetup();
			const st = ov.querySelector(".sbo-stage");
			st.addEventListener("touchstart", pinchStart, { passive: true });
			st.addEventListener("touchmove", pinchMove, { passive: false });
			st.addEventListener("touchend", () => { S.pinch = null; });
		} catch (err) {
			S.stream = null;
			camMsg("Camera is not allowed (" + esc(err.message || err.name) + "). Allow the camera for this app and try again.");
			$("#sbo-shutter").disabled = true;
		}
		geocode(true);
	}
	function closeCam() {
		if (S.stream) S.stream.getTracks().forEach((t) => t.stop());
		S.stream = null;
		const c = $("#sbo-cam");
		if (c) c.remove();
	}
	async function saveFaces() {
		if (S.busy) return;
		S.busy = true;
		$("#sbo-save-face").disabled = true;
		camMsg("Saving your face photos…");
		try {
			const r = await call("enroll", { photo_front: S.faces.front, photo_left: S.faces.left, photo_right: S.faces.right });
			S.d.employee = Object.assign(S.d.employee || {}, r.employee || {}, { enrolled: 1 });
			S.busy = false;
			toast("Face photos saved. Now take your punch selfie.", "ok");
			setMode("punch");
		} catch (err) {
			S.busy = false;
			$("#sbo-save-face").disabled = false;
			camMsg(esc(err.message || "Could not save. Check the internet and try again."));
		}
	}
	async function doPunch() {
		if (S.busy) return;
		if (S.mode === "enroll") {
			const step = FACE_STEPS.find((s) => !S.faces[s.k]);
			if (!step) return;
			const ph = snapFace(step.k);
			if (!ph) { toast("Camera is not ready yet. Wait a second and tap again.", "warn"); return; }
			S.faces[step.k] = ph;
			try { navigator.vibrate && navigator.vibrate(60); } catch (e) { /* ignore */ }
			setMode("enroll");
			return;
		}
		const g = gpsState();
		if (!g.ok) { toast(g.txt.replace(/<[^>]+>/g, ""), "warn"); return; }
		if (!S.shot) {
			S.shot = snapPhoto();
			if (!S.shot) { toast("Camera is not ready yet. Wait a second and tap again.", "warn"); return; }
			$("#sbo-shot").src = S.shot; $("#sbo-shot").classList.remove("hide"); $("#sbo-video").classList.add("hide"); $("#sbo-oval").classList.add("hide");
			$("#sbo-retake").classList.remove("hide"); $("#sbo-spacer").classList.add("hide");
			$("#sbo-zoombar").classList.add("hide");
			camMsg("Looks good? Tap the button again to punch.");
			return;
		}
		if (!S.pos && !window.confirm("Your location is not found yet. Punch without location?")) return;
		S.busy = true;
		const sh = $("#sbo-shutter");
		if (sh) sh.disabled = true;
		camMsg("Saving your punch…");
		try {
			const next = S.d.next || "IN";
			const r = await call("punch", { log_type: next, latitude: S.pos ? S.pos.lat : "", longitude: S.pos ? S.pos.lng : "", accuracy: S.pos ? S.pos.acc : "",
				photo: S.shot, address: addrText(S.addr), remarks: ($("#sbo-reason-in") || {}).value || "", device: (navigator.userAgent || "").slice(0, 80) });
			const p = r.punched || {};
			const shot = S.shot;
			closeCam();
			S.d = Object.assign(S.d, r);
			S.busy = false;
			render();
			nativeSchedule();
			const ok = document.createElement("div");
			ok.className = "sbo-done " + (p.log_type === "OUT" ? "out" : "");
			ok.innerHTML = `${shot ? `<img src="${shot}" alt="">` : `<div class="tick">✓</div>`}<b>Punched ${esc(p.log_type)} at ${esc(p.time)}</b>
				<div>${p.late ? "Late by " + p.late + " min" : p.early ? "Leaving " + p.early + " min early" : p.log_type === "IN" ? "Have a good day!" : "Thank you – see you tomorrow!"}</div>
				${S.addr ? `<div>📍 ${esc(addrText(S.addr))}</div>` : ""}
				${p.within === 0 ? `<div>Marked outside the office (${km(p.distance)} away)</div>` : p.distance ? `<div>${km(p.distance)} from office</div>` : ""}`;
			document.body.appendChild(ok);
			try { navigator.vibrate && navigator.vibrate(120); } catch (e) { /* ignore */ }
			setTimeout(() => ok.remove(), 3200);
			ok.addEventListener("click", () => ok.remove());
		} catch (e) {
			S.busy = false;
			if (sh) sh.disabled = false;
			camMsg(esc(e.message || "Could not save. Check the internet and try again."));
		}
	}
	async function loadMonth() {
		S.month = null;
		render();
		try { const r = await call("month", { back: S.back }); S.month = r.month_view || { days: [] }; } catch (e) { S.month = { days: [] }; toast(e.message); }
		render();
	}
	async function load() {
		S.d = await call("status");
		if (S.d.must_change) { window.location.href = "/desk/lite-erp"; return; }
		if (!S.d.employee && S.d.is_manager && S.tab === "punch" && !S.chosen) S.tab = "team";
		render();
		remTick();
		nativeSchedule();
	}

	document.addEventListener("click", async (ev) => {
		const el = ev.target.closest("[data-a]");
		if (!el || !el.closest(".sbo, .sbo-cam")) return;
		const a = el.dataset.a;
		if (a === "tab") { S.tab = el.dataset.t; if (S.tab === "month") loadMonth(); else render(); }
		else if (a === "open") {
			const g = gpsState();
			if (!g.ok) { toast(g.txt.replace(/<[^>]+>/g, ""), "warn"); return; }
			openCam();
		}
		else if (a === "cancel") closeCam();
		else if (a === "snap") doPunch();
		else if (a === "retake") { showLive(); camMsg("Keep your face inside the circle and tap the button."); gpsPaint(); }
		else if (a === "refacet") { if (S.faces) { delete S.faces[el.dataset.k]; setMode("enroll"); } }
		else if (a === "saveface") saveFaces();
		else if (a === "zset") { S.cx = null; S.cy = null; zoomApply(Number(el.dataset.z)); }
		else if (a === "zauto") { S.autoFit = true; zoomApply(S.zoom, true); }
		else if (a === "zin") zoomApply((S.zoom || 1) + ((S.zoom || 1) < 1 ? 0.1 : 0.25));
		else if (a === "zout") zoomApply((S.zoom || 1) - ((S.zoom || 1) <= 1 ? 0.1 : 0.25));
		else if (a === "resetface") {
			if (!window.confirm("Clear this employee's face photos? They will take new ones at the next punch.")) return;
			try { const r = await call("reset_face"); S.d.employee = Object.assign(S.d.employee || {}, r.employee || {}); render(); toast("Face photos cleared.", "ok"); } catch (e) { toast(e.message); }
		}
		else if (a === "notify") askNotify();
		else if (a === "pick") { S.asEmp = el.dataset.e; S.chosen = 1; S.tab = "punch"; load().catch((e) => toast(e.message)); }
		else if (a === "savesettings") {
			try {
				const r = await call("save_settings", { in_time: $("#sbo-in").value, out_time: $("#sbo-out").value, grace: $("#sbo-grace").value, reminder: $("#sbo-rem").value,
					start_day: $("#sbo-sd").value, radius: $("#sbo-rad2").value, block: $("#sbo-block").checked ? 1 : 0, office_name: $("#sbo-oname").value });
				S.d = Object.assign(S.d, r);
				render();
				toast("Settings saved.", "ok");
			} catch (e) { toast(e.message); }
		}
		else if (a === "mprev") { S.back += 1; loadMonth(); }
		else if (a === "mnext") { S.back = Math.max(0, S.back - 1); loadMonth(); }
		else if (a === "setoffice") {
			if (!S.pos) { toast("Your location is not found yet. Wait a few seconds and try again."); return; }
			if (!window.confirm("Set the office to where you are standing now (±" + S.pos.acc + " m)?")) return;
			try {
				const r = await call("set_office", { latitude: S.pos.lat, longitude: S.pos.lng, radius: $("#sbo-orad").value, office_name: $("#sbo-oname").value });
				S.d = Object.assign(S.d, r);
				render();
				toast("Office place saved.", "ok");
			} catch (e) { toast(e.message); }
		}
	});
	document.addEventListener("input", (ev) => { if (ev.target && ev.target.id === "sbo-zoom") zoomApply(ev.target.value); });
	document.addEventListener("change", (ev) => {
		if (ev.target && ev.target.id === "sbo-as") { S.asEmp = ev.target.value; S.chosen = 1; S.month = null; load().catch((e) => toast(e.message)); }
	});
	window.addEventListener("resize", () => { if ($("#sbo-cam")) viewTransform(); });
	document.addEventListener("visibilitychange", () => { if (!document.hidden && S.d && !$("#sbo-cam")) load().catch(() => {}); });

	function start() {
		setInterval(clock, 10000);
		setInterval(remTick, 30000);
		startGps();
		load().catch((e) => { if (e.message !== "login" && $("#sbo")) $("#sbo").innerHTML = `<div class="sbo-wrap"><div class="sbo-card"><div class="sbo-banner warn">${esc(e.message || "Could not load.")} Check the internet and reload.</div></div></div>`; });
	}
	// wait for the page to finish (the login token is written after this script)
	if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();'''
OFFICE_REMINDER = r'''# SBI Office - punch reminders. Runs every 5 minutes (Scheduler Event, cron */5 * * * *).
# Sends a bell notification (and the user's notification e-mail) N minutes before office start / end
# to staff who have not punched IN yet, or who are still punched IN near the end of the day.
def_val = {"in": "", "out": "", "rem": 15, "name": "the office"}
hm = frappe.get_meta("HR Settings")
for pair in [["in", "sbi_office_in_time"], ["out", "sbi_office_out_time"], ["rem", "sbi_reminder_minutes"], ["name", "sbi_office_name"]]:
    if hm.has_field(pair[1]):
        v = frappe.db.get_single_value("HR Settings", pair[1])
        if v not in (None, ""):
            def_val[pair[0]] = v
rem = frappe.utils.cint(def_val["rem"])
now = frappe.utils.now_datetime()
today = frappe.utils.nowdate()
jobs = []
for pair in [["IN", def_val["in"]], ["OUT", def_val["out"]]]:
    tp = str(pair[1] or "").split(":")
    if rem <= 0 or not tp[0]:
        continue
    hhmm = ("0" + tp[0])[-2:] + ":" + (tp[1] if len(tp) > 1 else "00")[:2]
    at = frappe.utils.get_datetime(today + " " + hhmm + ":00")
    send_at = frappe.utils.add_to_date(at, minutes=-rem)
    gap = frappe.utils.time_diff_in_seconds(now, send_at)
    if gap >= 0 and gap < 300:
        jobs.append([pair[0], hhmm])
for job in jobs:
    lt = job[0]
    hhmm = job[1]
    staff = frappe.db.sql("""select e.name, e.employee_name, e.user_id, e.company, ifnull(e.holiday_list, '') holiday_list,
        (select c.log_type from `tabEmployee Checkin` c where c.employee = e.name and date(c.time) = %s order by c.time desc limit 1) last_type
        from `tabEmployee` e join `tabUser` u on u.name = e.user_id and u.enabled = 1
        where e.status = 'Active' and ifnull(e.user_id, '') != ''""", today, as_dict=1)
    sent = 0
    for e in staff:
        if lt == "IN" and e.last_type:
            continue
        if lt == "OUT" and e.last_type != "IN":
            continue
        hl = e.holiday_list or frappe.db.get_value("Company", e.company, "default_holiday_list")
        if hl and frappe.db.exists("Holiday", {"parent": hl, "holiday_date": today}):
            continue
        if frappe.db.exists("DocType", "Leave Application") and frappe.db.sql("""select name from `tabLeave Application` where employee=%s and docstatus=1
                and status='Approved' and %s between from_date and to_date limit 1""", (e.name, today)):
            continue
        if lt == "IN":
            subj = "Punch IN reminder: office starts at " + hhmm + ". Open SBI Office and punch IN."
        else:
            subj = "Punch OUT reminder: office ends at " + hhmm + ". Open SBI Office and punch OUT before you leave."
        if frappe.db.exists("Notification Log", {"for_user": e.user_id, "subject": subj, "creation": [">=", today + " 00:00:00"]}):
            continue
        frappe.get_doc({"doctype": "Notification Log", "for_user": e.user_id, "from_user": "Administrator", "type": "Alert",
            "subject": subj, "email_content": subj + "<br><br><a href='/sbi_office'>Open SBI Office</a>"}).insert(ignore_permissions=True)
        sent = sent + 1
    frappe.db.commit()'''
OFFICE_APK = (
    'UEsDBBQAAAAAACiQc10qWaD9pAkAAKQJAAAOAAgAcmVzb3VyY2VzLmFyc2M12QQABAAAAAIADACkCQAAAQAAAAEAHACYAgAAEAAAAAAAAAAAAQAAXAAAAAAAAAAAAAAADQAAAC8AAABRAAAAdAAAAJgAAAC9AAAA3wAAAAcBAAApAQAAUQEAAHQBAACdAQAAwQEAAOsBAAAQAgAACgpTQkkgT2ZmaWNlAB8fcmVzL2RyYXdhYmxlLWhkcGkvaWNfbm90aWZ5LnBuZwAfH3Jlcy9kcmF3YWJsZS1tZHBpL2ljX25vdGlmeS5wbmcAICByZXMvZHJhd2FibGUteGhkcGkvaWNfbm90aWZ5LnBuZwAhIXJlcy9kcmF3YWJsZS14eGhkcGkvaWNfbm90aWZ5LnBuZwAiInJlcy9kcmF3YWJsZS14eHhoZHBpL2ljX25vdGlmeS5wbmcAHx9yZXMvbWlwbWFwLWhkcGkvaWNfbGF1bmNoZXIucG5nACUlcmVzL21pcG1hcC1oZHBpL2ljX2xhdW5jaGVyX3JvdW5kLnBuZwAfH3Jlcy9taXBtYXAtbWRwaS9pY19sYXVuY2hlci5wbmcAJSVyZXMvbWlwbWFwLW1kcGkvaWNfbGF1bmNoZXJfcm91bmQucG5nACAgcmVzL21pcG1hcC14aGRwaS9pY19sYXVuY2hlci5wbmcAJiZyZXMvbWlwbWFwLXhoZHBpL2ljX2xhdW5jaGVyX3JvdW5kLnBuZwAhIXJlcy9taXBtYXAteHhoZHBpL2ljX2xhdW5jaGVyLnBuZwAnJ3Jlcy9taXBtYXAteHhoZHBpL2ljX2xhdW5jaGVyX3JvdW5kLnBuZwAiInJlcy9taXBtYXAteHh4aGRwaS9pY19sYXVuY2hlci5wbmcAKChyZXMvbWlwbWFwLXh4eGhkcGkvaWNfbGF1bmNoZXJfcm91bmQucG5nAAAAAiABAAcAAH8AAABjAG8AbQAuAHMAaABpAHYAYgBoAGEAcgBhAHQALgBzAGIAaQBvAGYAZgBpAGMAZQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
    'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA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'
)
ICON_180 = (
    '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'
)
ICON_192 = (
    'iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAMAAABlApw1AAAB4FBMVEWvDSeWCyHDDiz+/v4AAACyEiytABuYARfHEzD46evOZnfTdYT/AADsyM7w1dm8V2bThpLjqLHHVmh/AACxJDq0N0q2RleqAADltLzamaPovMKdECaXCiHFRFmXCyGWCiC7ATzdpq7JDizXkpzDOE6WCyG0K0HIDizIDi3/AFX03eHCIjzHDi2XCR2ZCyHNCi7MDSzEKkP/AH/hl6PITmGZDSGqAFXIDi3GEizKEC2+ZHF/AD+XDByZESKwCizHESvIcX7Wb4BVAACSCR+WCyK/Dyu/Dyy7ETPPES/QEC7OEC7NEC7/AD/gk5+3UF/fsrkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAfAyI4AAAAoHRSTlP+/v7/AP///v7///8B////////Av///wP/////k/9TqgX/Uf//0v+UqgP//9Iadxcl/wL//yUDdRaS/wQnDyVa//8DUBakxQ8rfa/fBP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABZJNPQAACyNJREFUeNrtXWl3ojoYDkrYBJS11tal2sVr1+ky09ln7r7f//9vbgIICUKJGiOc0/dDj0VsnifvmjexALlUzIMf0U/v6aeb8dmZpEpCRZXOzsY3Pz15CMKPB2Y5SlD2hneAflyPjs+kvcrZ8egaATnw1iSA4X8ejaVayHj0uZwCKDYeWX6K517dN3o11sMTomCyEkDwPx1LNZPjTxEwBgKmJ/9cO/gRhZ9lz6wmgFiO6mA6RaY0KlBCnoAnX49rCD+hML6WvZcJmNH011hGsvkCAdOUb2o6/akSbjDKEgKe7B1LtZdjjzIjQM7/ZCw1QMYTUgeAwP+xEfgRg48Eg4yAZ47rbP6kI4xNb5XAgXwsNUaOs3ywJPARx5/myA0CTBE4qHv8X80HByQB07uWGibXSV0EEgWMm0ZgnKgANNKACCOKCHgTqYEy8ZYEUAQFzcMP4lgKcAZ7khopTzifgYalsJV0BlBp90lqqHxC4EFDPSD1AmDKn6XGymfZBJ48Ak3FD0ayhwiMm6uBMSIgX0sNlmvkxM21oMiGQGNjUBKHwOSsySZ0NgFfdrZ0pWRXo3wBox1hP/KD8IPRQ/LtQzfwj3bEYgRuAH/0frfXt9uU2INZ15e4c0Dwx4Av+qOwZ7VLxJqFR3w5IPhnXOEHM7v9ouiHIVcKZxwJqFJ30GYQ68ORypEAP/gf7Daj2AY/CnwIIMvuMsOPKHxA3lIjAmrQb68pVqDWhQCa/k57A+lJPJQAOOD3i+KmfdIz/g0DJGFo9E4sfUdK2J6A2i2I91HSosQvyg+Gun8Cai8/9b1AisqGo9RA8CtMIujlPf1Q3TMBVT2hEQ26ONcW2vYRriTC/+j7+9sG1O0IqEd06hqEZegzDgFN2YLq/gioR5RZ212WKkFVQ/pT2zHYTgNWLiyyJu0OPwbbEFDJ7GWHLxpPPvGR1K09aUA9JECcQBWWLspW3kBzTn1Y3QMBqH4jzUeVVvHDMBFYRL9DfRyIJgDUsCohZRmuqxYlcDIBdlUoXAMLEj8sokgQAEUqJBjo/qY62PRjZAIrxF9JgGYwEEuA'
    'GrtTrP5KAuivGFWzwEBgI5GgTpQzsPgmikChQKKQwkYkTMiBrdJxqwmge/pELBVHQD1nmTgWAqQqA3EMCA82ygyIjQAkonFfGAE1YBqUhQBikKXkUBXlAZkC/G0JkEYkSgWqT5QAcFsCkKgpxHgBMaIOXyTKRABJus6cqVCICmwmBbASINKZLgR/Fjd0X+GigcwLXAEqIMLGocrFhIi0KCSZQZsx7DFrQDkXaUNZErCr7mQlANQB651cY1CvwmDZfSBb3AmIQ1n5FSgVd7qZbwJGG7KU3buAzmqv7AQAsNLAtmv8SuoCjsqNABHZwl2rIEPVqTJXJSOgVBEwGKpb3j5cOVfsBAi9znZOIFX2eeW0hlnCgKye1d+xCUGlz5xzFCd1F4W5vrJ2HoUsxpGgMstaDjOlyl+WqWwBRRUSA6UCf0B2oIOXGUDlRFQxkRqrUwWJ7N62TxQFQKa7fVEETqqsgt4Oszv+Cxyg0mONDcIIwJV91ZOwlAJJoKYaiB3fgIgCrAeBSh9winbnF73zIjWI9IEsClUQcEtOGDghWKGQ0d39koY1DwCl9PyH/Q0qysb5cdtqdMA8ErReOLcVbDovW5cSJ+zGCmPP1Pt60VkVygSJWmjHxVwWLsLqoRQfnbs0fMXvrIYkl/x4lrYPd04gWw9UDwWBokTWrgA35xH25n+V24qMZSgIo7CPmQQz0pIooEThN1SEFUP2WiNBFHigYZU1gCxRaYCMjsGaVQtSAwidQlNP+927Xw4QXry+uWJLOu8t8uU1VAxRPowHC7eZLeQRCnSt3MIx06qrQHGNobVtKLOkHEq/LawtRNVdsw2na6UQSjsdfREKUB5595KzfrehiNjiyI55cMk6hAuL2aEh4hCnAW1xMSiW8zZHFRAK2DAqbDCkwzNqZFFtIAY/1fJxtlUB2f96FGRB1Hp3y8xD5EURmxurJenWfpyFUAGFaGHbbSvDJXXZF4efblv1Nh+YyMG7bwiVxr7N0yfVeukIVQDdNNnQkaEyJJp2QLT4+pYMKPztAIhVQK7ztgEDGr8h2IDokiiy4HVnkPQiYUVQ2R4YhgDWYYBuJekPwJ6E+hJAwKwEtCbzB9Q3IPYDH5JpFJsRWu5CtgaLQbaIUEVYEwbWsHj7Ir+qp7+3uPAVuC8TgvkOtBMoL3LAs39+SPcYz/eHP2KQ+wqxM8RNh8JtJDz54DS3cWNBsEf8UTg5zG+Edc5BpIekL7p8hdq8vpHfMnD2jD+KKMZK63zQGUIlaUzjeIsFnnZWt2zWTx87yWinBRuS+uCw454GPpLg1DVmg4JNjsWQKWwJYABn5ZtJeulbDlTqAD82o6G17tehbbcO5pMpARj6OvD1Tm2mP1UC7DBT0Ht+naafoMD0nw3wuY/awV/2zR+dCjXojgvrCX+5AwNdZ1GO3vCV+sJf1mooZ3138v/FQLedKLsBWGf4Sw5RKXH6aHR6hw8PD72O4Z76+FoD0Gd1W1JBJJJebJBASsCrvMqrvMqrvEpTcldj4SfVAyiseWrPK+pauYbhPp7il/E1PyslsjI6vlrD6U+7Vrr1cIqbdmgPRF+KhZcCMNleQ78v6seA6jHio0Qw1/LSo22YZGdSh3VTgLNyLheu9OyGkV7qSACCYbJm/Ocfx8oR6DtOslIe1JdAvGHWjzqi4NIdEAR0fDFuw+u1NaHkyADudUYrSgCJ3fA3eFtg+bLeBDpKdto4I3AJMmWAeptQ++HxEqSdB4IAiBvY/do7Me67Od9PAWVCNpLYxd8QBDReY1+1+IfRwTCO+HQYtS7JPMCHQOsK/Kpx2ixz6C3XgkTmaJQGeBiR9iv4ReNVSrjkV02GWeixkOjLHT3eBH4B7zR+DbnLx96SBDoNSDox7CwPBXEm8A5MNV74kwzg6slXTMg8kBysGADeBKbgrtXiY0Fp3dxJzj8QBJaGs+DsA63WHZhcaTzwu268wQ21+CBRTgNJpuNNQLuaAPlC45PIBsabaEV2'
    'aSU5a5l+NVwfucnBMr4mpF2gJ0BMuRCIUFnOw0PixUbmxLgatdo7cWJtigjccnACTcn952kb4dNW1gPxVX4EWq1bGdzLc40Dge800jdAAysE+pcI9JIrDwLaXL4HE/krj0CqDXvpaQK7h9BjVsSaeGE9DEF8NV4TcyHwVZ6gRxn91uIhKAhpuCuBtpM09DK6pl1qqeD3s6uXyest5Tf0KCP5BxSHOPwtjDFqDCHTTNER5qplkBP73X7ICwQeP87rS4uPpLO9eoWa8PzvG8uX6HFe8lucClqNE5wE3kZPhDPNu1Yj5Q4/YxY/VPAH+X3zVAC09wh4TMD0bpuogNvo2aDJgzWnWtPgoyrigHy06bxhDFASPqAeLvvcNA08Uw+XRfGoWUaEDOgt/YDlifyuQQy0dwhw7hHXnCoKMfgvoghKEzDv75viyNr8/t4sesz7pBkMtPmk8DHviMHfTWCgzf8m8JMEUGnn1d8PtAsEUy4mgHRQ+1iE4g85/zkCyJPlaavGFLTWVL6n8OcI4HzwPNdqSkHT5s9p/C8jgBPc13oqQWt9lZf59wUC2MRu39ePgtZ6f5sz/xICOCnLv9eMAoL/u5yl3woCsonuvLv4qy6+oGl/Xdwh+KbMSgClBFRsP0//bGn7JoEB/Dl9RksWrxhpCQFEAevrdnpx1doXi2jYq4vpLbZqrwxnKQFsSHjNM7mb/jG/uhKP/+pq/sf0DkfNg2LjieV/GdAWVsm4UeMAAAAASUVORK5CYII='
)
ICON_512 = (
    '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'
)
OFFICE_SW = """self.addEventListener("install", function (e) { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = (e.notification.data && e.notification.data.url) || "/sbi_office";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (cs) {
    for (var i = 0; i < cs.length; i++) { if (cs[i].url.indexOf("/sbi_office") >= 0 && "focus" in cs[i]) return cs[i].focus(); }
    return self.clients.openWindow(url);
  }));
});
"""

roles = []
for r in ROLES_WANTED:
    if frappe.db.exists("Role", r):
        roles.append(r)

# ---------------------------------------------------------------- 1. custom fields
FIELDS = [
    # doctype, fieldname, label, type, options, insert_after, list view, read only
    ["Purchase Invoice", "sbi_stage", "Stage / Milestone", "Data", "", "project", 1, 0],
    ["Site Cash Issue", "sbi_tally_je", "Tally Journal Entry", "Link", "Journal Entry", "remarks", 0, 1],
    ["Site Expense Entry", "sbi_tally_je", "Tally Journal Entry", "Link", "Journal Entry", "entered_by", 0, 1],
]
for f in FIELDS:
    cf_name = f[0] + "-" + f[1]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    frappe.get_doc({
        "doctype": "Custom Field", "dt": f[0], "fieldname": f[1], "label": f[2], "fieldtype": f[3],
        "options": f[4], "insert_after": f[5], "in_list_view": f[6], "in_standard_filter": 1,
        "read_only": f[7], "no_copy": f[7],
    }).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# Bank Transaction: the owner's invoice check, editable after the line is submitted
BT_FIELDS = [
    {"fieldname": "sbi_check_sb", "label": "Invoice check (Lite ERP)", "fieldtype": "Section Break", "insert_after": "description", "collapsible": 0},
    {"fieldname": "sbi_check_status", "label": "Check Status", "fieldtype": "Select", "options": "\nMatched\nNo Invoice",
        "insert_after": "sbi_check_sb", "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "sbi_match_doctype", "label": "Invoice Type", "fieldtype": "Link", "options": "DocType", "insert_after": "sbi_check_status"},
    {"fieldname": "sbi_match_name", "label": "Invoice", "fieldtype": "Dynamic Link", "options": "sbi_match_doctype", "insert_after": "sbi_match_doctype"},
    {"fieldname": "sbi_check_cb", "fieldtype": "Column Break", "insert_after": "sbi_match_name"},
    {"fieldname": "sbi_reason", "label": "No Invoice Reason", "fieldtype": "Data", "insert_after": "sbi_check_cb"},
    {"fieldname": "sbi_remarks", "label": "Remarks", "fieldtype": "Small Text", "insert_after": "sbi_reason"},
    {"fieldname": "sbi_checked_by", "label": "Checked By", "fieldtype": "Link", "options": "User", "insert_after": "sbi_remarks", "read_only": 1},
    {"fieldname": "sbi_checked_on", "label": "Checked On", "fieldtype": "Datetime", "insert_after": "sbi_checked_by", "read_only": 1},
]
if frappe.db.exists("DocType", "Bank Transaction"):
    for f in BT_FIELDS:
        cf_name = "Bank Transaction-" + f["fieldname"]
        if frappe.db.exists("Custom Field", cf_name):
            continue
        row = {"doctype": "Custom Field", "dt": "Bank Transaction", "allow_on_submit": 1, "no_copy": 1}
        row.update(f)
        frappe.get_doc(row).insert(ignore_permissions=True)
        log("field added: " + cf_name)

# Project BOQ Item: Sl. No., description, type and remarks for BOQs typed or uploaded in Lite ERP
PBI_FIELDS = [
    {"fieldname": "sbi_sl_no", "label": "Sl. No.", "fieldtype": "Data", "insert_after": "stage", "columns": 1},
    {"fieldname": "sbi_description", "label": "Item Description", "fieldtype": "Small Text", "insert_after": "sbi_sl_no", "in_list_view": 1, "columns": 3},
    {"fieldname": "sbi_type", "label": "Type", "fieldtype": "Select", "insert_after": "sbi_description", "in_list_view": 1, "columns": 1,
        "options": "\nMaterial\nManpower\nEquipment\nTransport\nSubcontract\nOther"},
    {"fieldname": "sbi_remarks", "label": "Remarks", "fieldtype": "Small Text", "insert_after": "amount"},
]
if frappe.db.exists("DocType", "Project BOQ Item"):
    for f in PBI_FIELDS:
        cf_name = "Project BOQ Item-" + f["fieldname"]
        if frappe.db.exists("Custom Field", cf_name):
            continue
        row = {"doctype": "Custom Field", "dt": "Project BOQ Item"}
        row.update(f)
        frappe.get_doc(row).insert(ignore_permissions=True)
        log("field added: " + cf_name)

# one Site Activity per BOQ type: the whole line amount goes to that type in the budget
if frappe.db.exists("DocType", "Site Activity"):
    for pair in [["Material", "material_rate"], ["Manpower", "labour_rate"], ["Equipment", "equipment_rate"],
                 ["Transport", "other_rate"], ["Subcontract", "subcontract_rate"], ["Other", "other_rate"]]:
        an = "BOQ " + pair[0]
        if not frappe.db.exists("Site Activity", an):
            a = {"doctype": "Site Activity", "activity_name": an, "unit_rate": 1, "labour_rate": 0, "material_rate": 0,
                "equipment_rate": 0, "subcontract_rate": 0, "other_rate": 0}
            a[pair[1]] = 1
            frappe.get_doc(a).insert(ignore_permissions=True)
            log("activity added: " + an)

# ---------------------------------------------------------------- permission repair
# Once a doctype has ANY Custom DocPerm rows, ERPNext ignores its standard permissions. If those
# custom rows exist only at level 1 (used to hide fields such as wages), nobody can open the
# doctype at all - not even from the desk. Give such doctypes their level-0 rows back.
PERM_FIELDS = ["read", "write", "create", "delete", "submit", "cancel", "amend", "report", "export", "import",
    "print", "email", "share", "select"]
for dtn in frappe.db.sql("""select distinct parent from `tabCustom DocPerm`
        where parent not in (select parent from `tabCustom DocPerm` where ifnull(permlevel, 0)=0)"""):
    dtn = dtn[0]
    if not frappe.db.exists("DocType", dtn):
        continue
    added = []
    std = frappe.db.sql("select * from `tabDocPerm` where parent=%s and ifnull(permlevel, 0)=0", dtn, as_dict=1)
    have = []
    for p in std:
        row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
            "role": p.role, "permlevel": 0, "if_owner": p.if_owner or 0}
        for fld in PERM_FIELDS:
            if fld in p:
                row[fld] = p.get(fld) or 0
        frappe.get_doc(row).insert(ignore_permissions=True)
        have.append(p.role)
        added.append(p.role)
    # roles already trusted with level 1 also need to open the record
    for p in frappe.db.sql("select role, `write` from `tabCustom DocPerm` where parent=%s and permlevel=1 and `read`=1", dtn, as_dict=1):
        if p.role in have:
            continue
        frappe.get_doc({"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
            "role": p.role, "permlevel": 0, "read": 1, "write": p.write or 0, "create": p.write or 0, "report": 1,
            "export": 1, "print": 1, "select": 1}).insert(ignore_permissions=True)
        have.append(p.role)
        added.append(p.role + " (read)")
    log("permissions repaired for " + dtn + ": level 0 for " + ", ".join(added))

# HR team must be able to open the site labour records too (Labour register, Labour punches)
for dtn in ["Labour", "Labour Attendance Log", "Site Shift"]:
    if not frappe.db.exists("DocType", dtn) or not frappe.db.exists("Role", "HR Manager"):
        continue
    if not frappe.db.exists("Custom DocPerm", {"parent": dtn}):
        # first custom row replaces the standard ones, so copy those over first
        for p in frappe.db.sql("select * from `tabDocPerm` where parent=%s", dtn, as_dict=1):
            row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
                "role": p.role, "permlevel": p.permlevel or 0, "if_owner": p.if_owner or 0}
            for fld in PERM_FIELDS:
                if fld in p:
                    row[fld] = p.get(fld) or 0
            frappe.get_doc(row).insert(ignore_permissions=True)
    levels = [0]
    for lv in frappe.db.sql("select distinct ifnull(permlevel, 0) from `tabCustom DocPerm` where parent=%s", dtn):
        if lv[0] not in levels:
            levels.append(lv[0])
    for hrr in ["HR Manager", "HR User"]:
        if not frappe.db.exists("Role", hrr):
            continue
        for lv in levels:
            if frappe.db.exists("Custom DocPerm", {"parent": dtn, "role": hrr, "permlevel": lv}):
                continue
            full = 1 if (hrr == "HR Manager" or lv == 0) else 0
            row = {"doctype": "Custom DocPerm", "parent": dtn, "parenttype": "DocType", "parentfield": "permissions",
                "role": hrr, "permlevel": lv, "read": 1, "write": full, "report": 1 if lv == 0 else 0}
            if lv == 0:
                row.update({"create": 1, "delete": 1 if hrr == "HR Manager" else 0, "export": 1, "print": 1, "email": 1, "share": 1, "select": 1})
            frappe.get_doc(row).insert(ignore_permissions=True)
            log("HR access added: " + dtn + " level " + str(lv) + " for " + hrr)

# ---------------------------------------------------------------- 1b. order lines: Sl. No. + MS (milestone) yes / no
ORDER_FIELDS = []
for dt in ["Sales Order Item", "Purchase Order Item", "Sales Invoice Item", "Purchase Invoice Item"]:
    order = dt in ("Sales Order Item", "Purchase Order Item")
    ORDER_FIELDS.append({"dt": dt, "fieldname": "sbi_sl_no", "label": "Sl. No.", "fieldtype": "Data", "insert_after": "item_code",
        "in_list_view": 1, "columns": 1, "length": 20})
    ORDER_FIELDS.append({"dt": dt, "fieldname": "sbi_ms", "label": "MS (milestone)", "fieldtype": "Check", "default": "1",
        "insert_after": "amount", "in_list_view": 1 if order else 0, "columns": 1, "read_only": 0 if order else 1,
        "description": "Ticked = billed by milestones. Not ticked = billed separately (non-MS bill)."})
ORDER_FIELDS.append({"dt": "Payment Schedule", "fieldname": "sbi_ms_percent", "label": "% of milestone work", "fieldtype": "Float",
    "insert_after": "invoice_portion", "read_only": 1, "precision": "4",
    "description": "The milestone % of the MS lines only (Lite ERP)."})
ORDER_FIELDS.append({"dt": "Purchase Invoice", "fieldname": "sbi_source_purchase_order", "label": "Source Purchase Order", "fieldtype": "Link",
    "options": "Purchase Order", "insert_after": "sbi_stage", "read_only": 1, "no_copy": 1})
ORDER_FIELDS.append({"dt": "Purchase Invoice", "fieldname": "sbi_source_payment_terms", "label": "Source Payment Term Rows", "fieldtype": "Small Text",
    "insert_after": "sbi_source_purchase_order", "read_only": 1, "hidden": 1, "no_copy": 1})
if not frappe.get_meta("Sales Invoice").has_field("sbi_source_sales_order"):
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_source_sales_order", "label": "Source Sales Order", "fieldtype": "Link",
        "options": "Sales Order", "insert_after": "project", "read_only": 1, "no_copy": 1})
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_source_payment_terms", "label": "Source Payment Term Rows", "fieldtype": "Small Text",
        "insert_after": "sbi_source_sales_order", "read_only": 1, "hidden": 1, "no_copy": 1})
if not frappe.get_meta("Sales Invoice").has_field("sbi_stage"):
    ORDER_FIELDS.append({"dt": "Sales Invoice", "fieldname": "sbi_stage", "label": "Stage / Milestone", "fieldtype": "Data", "insert_after": "project"})
for f in ORDER_FIELDS:
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# HR: salary month + office location (HR Settings) and office punch details (Employee Checkin)
HR_FIELDS = [
    {"dt": "HR Settings", "fieldname": "sbi_lite_hr_sb", "label": "Lite ERP: salary month and office punch", "fieldtype": "Section Break", "insert_after": None, "collapsible": 0},
    {"dt": "HR Settings", "fieldname": "sbi_salary_start_day", "label": "Salary month starts on day", "fieldtype": "Int", "default": "1", "insert_after": "sbi_lite_hr_sb",
        "description": "1 = calendar month (1st to last day). 26 = 26th to 25th of next month."},
    {"dt": "HR Settings", "fieldname": "sbi_full_day_hours", "label": "Full day (hours)", "fieldtype": "Float", "default": "8", "insert_after": "sbi_salary_start_day"},
    {"dt": "HR Settings", "fieldname": "sbi_half_day_hours", "label": "Half day (hours)", "fieldtype": "Float", "default": "4", "insert_after": "sbi_full_day_hours"},
    {"dt": "HR Settings", "fieldname": "sbi_lite_hr_cb", "fieldtype": "Column Break", "insert_after": "sbi_half_day_hours"},
    {"dt": "HR Settings", "fieldname": "sbi_office_name", "label": "Office name", "fieldtype": "Data", "insert_after": "sbi_lite_hr_cb"},
    {"dt": "HR Settings", "fieldname": "sbi_office_latitude", "label": "Office latitude", "fieldtype": "Float", "precision": "7", "insert_after": "sbi_office_name"},
    {"dt": "HR Settings", "fieldname": "sbi_office_longitude", "label": "Office longitude", "fieldtype": "Float", "precision": "7", "insert_after": "sbi_office_latitude"},
    {"dt": "HR Settings", "fieldname": "sbi_office_radius", "label": "Office area (metres)", "fieldtype": "Int", "default": "200", "insert_after": "sbi_office_longitude"},
    {"dt": "HR Settings", "fieldname": "sbi_block_outside", "label": "Allow punch only inside the office area", "fieldtype": "Check", "default": "1", "insert_after": "sbi_office_radius",
        "description": "Staff marked “Can punch anywhere” on their Employee record are not blocked."},
    {"dt": "HR Settings", "fieldname": "sbi_office_in_time", "label": "Office starts at", "fieldtype": "Time", "default": "09:30:00", "insert_after": "sbi_block_outside"},
    {"dt": "HR Settings", "fieldname": "sbi_office_out_time", "label": "Office ends at", "fieldtype": "Time", "default": "18:30:00", "insert_after": "sbi_office_in_time"},
    {"dt": "HR Settings", "fieldname": "sbi_late_grace", "label": "Late after (minutes of grace)", "fieldtype": "Int", "default": "10", "insert_after": "sbi_office_out_time"},
    {"dt": "HR Settings", "fieldname": "sbi_reminder_minutes", "label": "Punch reminder (minutes before)", "fieldtype": "Int", "default": "15", "insert_after": "sbi_late_grace",
        "description": "SBI Office reminds staff this many minutes before the office start and end time. 0 = no reminders."},
    {"dt": "Employee", "fieldname": "sbi_punch_anywhere", "label": "Can punch anywhere (SBI Office)", "fieldtype": "Check", "default": "0", "insert_after": "user_id",
        "description": "Tick for field staff who punch outside the office area."},
    {"dt": "Employee", "fieldname": "sbi_face_front", "label": "Face photo – front (SBI Office)", "fieldtype": "Attach Image", "insert_after": "sbi_punch_anywhere",
        "description": "Taken once in the SBI Office app. Clear all three to let the employee take them again."},
    {"dt": "Employee", "fieldname": "sbi_face_left", "label": "Face photo – left", "fieldtype": "Attach Image", "insert_after": "sbi_face_front"},
    {"dt": "Employee", "fieldname": "sbi_face_right", "label": "Face photo – right", "fieldtype": "Attach Image", "insert_after": "sbi_face_left"},
    {"dt": "Employee", "fieldname": "sbi_face_on", "label": "Face photos taken on", "fieldtype": "Datetime", "insert_after": "sbi_face_right", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_address", "label": "Place (street, area, city)", "fieldtype": "Small Text", "insert_after": "sbi_remarks", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_punch_sb", "label": "Office punch", "fieldtype": "Section Break", "insert_after": "longitude", "collapsible": 0},
    {"dt": "Employee Checkin", "fieldname": "sbi_photo", "label": "Punch photo", "fieldtype": "Attach Image", "insert_after": "sbi_punch_sb", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_source", "label": "Source", "fieldtype": "Data", "insert_after": "sbi_photo", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_punch_cb", "fieldtype": "Column Break", "insert_after": "sbi_source"},
    {"dt": "Employee Checkin", "fieldname": "sbi_distance", "label": "Distance from office (m)", "fieldtype": "Float", "insert_after": "sbi_punch_cb", "read_only": 1, "in_list_view": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_within", "label": "Inside office area", "fieldtype": "Check", "default": "1", "insert_after": "sbi_distance", "read_only": 1, "in_list_view": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_accuracy", "label": "GPS accuracy (m)", "fieldtype": "Float", "insert_after": "sbi_within", "read_only": 1},
    {"dt": "Employee Checkin", "fieldname": "sbi_remarks", "label": "Reason (if outside)", "fieldtype": "Small Text", "insert_after": "sbi_accuracy", "read_only": 1},
]
for f in HR_FIELDS:
    if not frappe.db.exists("DocType", f["dt"]):
        log("skipped (no " + f["dt"] + "): " + f["fieldname"])
        continue
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    if not row.get("insert_after"):
        flds = frappe.get_meta(f["dt"]).fields
        row["insert_after"] = flds[-1].fieldname if flds else None
    if f["dt"] == "Employee Checkin" and f["fieldname"] == "sbi_punch_sb" and not frappe.get_meta("Employee Checkin").has_field("longitude"):
        row["insert_after"] = "time"
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

module = "SBI Projects" if frappe.db.exists("Module Def", "SBI Projects") else "Accounts"
# ---------------------------------------------------------------- staff: logins by user id, self-service requests, letters
STAFF_ROLE = "SBI Staff"
if not frappe.db.exists("Role", STAFF_ROLE):
    frappe.get_doc({"doctype": "Role", "role_name": STAFF_ROLE, "desk_access": 1}).insert(ignore_permissions=True)
    log("role added: " + STAFF_ROLE)
for r in [STAFF_ROLE, "Employee", "Employee Self Service", "Sales User", "Sales Manager", "Purchase User", "Purchase Manager", "Projects User", "Projects Manager"]:
    if frappe.db.exists("Role", r) and r not in roles:
        roles.append(r)

STAFF_FIELDS = [
    {"dt": "User", "fieldname": "sbi_must_change_password", "label": "Must change password at next login (Lite ERP)", "fieldtype": "Check", "default": "0", "insert_after": "enabled",
        "description": "Set when HR gives a login with the default password. Cleared when the person sets their own password."},
    {"dt": "Attendance Request", "fieldname": "sbi_status", "label": "HR decision", "fieldtype": "Select", "options": "\nPending\nApproved\nRejected", "insert_after": "explanation",
        "in_list_view": 1, "in_standard_filter": 1},
    {"dt": "Attendance Request", "fieldname": "sbi_hr_remarks", "label": "HR remarks", "fieldtype": "Small Text", "insert_after": "sbi_status"},
]
for f in STAFF_FIELDS:
    if not frappe.db.exists("DocType", f["dt"]):
        continue
    cf_name = f["dt"] + "-" + f["fieldname"]
    if frappe.db.exists("Custom Field", cf_name):
        log("field exists: " + cf_name)
        continue
    row = {"doctype": "Custom Field"}
    row.update(f)
    if not frappe.get_meta(f["dt"]).has_field(row["insert_after"]):
        flds = frappe.get_meta(f["dt"]).fields
        row["insert_after"] = flds[-1].fieldname if flds else None
    frappe.get_doc(row).insert(ignore_permissions=True)
    log("field added: " + cf_name)

# more reasons for attendance requests (only "Work From Home" is marked WFH, all others are marked Present); no shifts for office staff
PROPS = [
    ["Attendance Request", "reason", "options", "Work From Home\nOn Duty\nForgot to Punch\nClient / Site Visit\nOfficial Travel\nTraining / Meeting Outside\nMobile / GPS Problem\nOther", "Text"],
    ["Employee", "default_shift", "hidden", "1", "Check"],
    ["Attendance Request", "shift", "hidden", "1", "Check"],
    ["Employee", "employee_number", "label", "Employee ID No.", "Data"],
]
for pp in PROPS:
    if not frappe.db.exists("DocType", pp[0]) or not frappe.get_meta(pp[0]).has_field(pp[1]):
        continue
    psn = pp[0] + "-" + pp[1] + "-" + pp[2]
    if frappe.db.exists("Property Setter", psn):
        ps = frappe.get_doc("Property Setter", psn)
        ps.value = pp[3]
        ps.save(ignore_permissions=True)
    else:
        frappe.get_doc({"doctype": "Property Setter", "doctype_or_field": "DocField", "doc_type": pp[0], "field_name": pp[1],
            "property": pp[2], "property_type": pp[4], "value": pp[3]}).insert(ignore_permissions=True)
    log("property set: " + psn)

# employee detail changes waiting for HR
CR_DT = "SBI Employee Change Request"
if not frappe.db.exists("DocType", CR_DT):
    frappe.get_doc({"doctype": "DocType", "name": CR_DT, "module": module, "custom": 1, "autoname": "ECR-.#####", "naming_rule": "Expression (old style)",
        "title_field": "employee_name", "track_changes": 1, "sort_field": "creation", "sort_order": "DESC",
        "fields": [
            {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "employee_name", "label": "Employee name", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "status", "label": "Status", "fieldtype": "Select", "options": "Pending\nApproved\nRejected", "default": "Pending", "in_list_view": 1, "in_standard_filter": 1},
            {"fieldname": "summary", "label": "What changes", "fieldtype": "Data", "in_list_view": 1},
            {"fieldname": "cb1", "fieldtype": "Column Break"},
            {"fieldname": "reviewed_by", "label": "Checked by", "fieldtype": "Link", "options": "User", "read_only": 1},
            {"fieldname": "reviewed_on", "label": "Checked on", "fieldtype": "Datetime", "read_only": 1},
            {"fieldname": "hr_remarks", "label": "HR remarks", "fieldtype": "Small Text"},
            {"fieldname": "sb1", "fieldtype": "Section Break", "label": "Changes"},
            {"fieldname": "changes", "label": "New values", "fieldtype": "Code", "options": "JSON", "read_only": 1},
            {"fieldname": "new_photo", "label": "New photo", "fieldtype": "Attach Image"},
        ],
        "permissions": [{"role": "HR Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
            {"role": "HR User", "read": 1, "write": 1, "create": 1, "report": 1},
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1}]}).insert(ignore_permissions=True)
    log("doctype added: " + CR_DT)

# log in with the user id (not only e-mail)
if not frappe.db.get_single_value("System Settings", "allow_login_using_user_name"):
    sset = frappe.get_doc("System Settings")
    sset.allow_login_using_user_name = 1
    sset.flags.ignore_mandatory = True
    sset.save(ignore_permissions=True)
    log("System Settings: login with user id allowed")

# every employee with a login opens Lite ERP after login and has the Employee role
EMP_USERS = frappe.db.sql("""select e.user_id from `tabEmployee` e join `tabUser` u on u.name = e.user_id
    where e.status = 'Active' and ifnull(e.user_id, '') != '' and u.user_type = 'System User' and u.enabled = 1""")
n_ws = 0
for eu in EMP_USERS:
    uid = eu[0]
    if uid in ("Administrator", "Guest"):
        continue
    if frappe.db.get_value("User", uid, "default_workspace") != LABEL:
        frappe.db.set_value("User", uid, "default_workspace", LABEL, update_modified=False)
        n_ws = n_ws + 1
    if frappe.db.exists("Role", "Employee") and not frappe.db.exists("Has Role", {"parenttype": "User", "parent": uid, "role": "Employee"}):
        ud = frappe.get_doc("User", uid)
        ud.append("roles", {"role": "Employee"})
        ud.flags.ignore_password_policy = True
        ud.save(ignore_permissions=True)
log("employee logins opening Lite ERP: " + str(len(EMP_USERS)) + " (" + str(n_ws) + " changed)")

# appointment and relieving orders (print formats on Employee - HR can edit the wording in Print Format)
LETTER_TOP = """<style>.sbi-letter { font-size: 13px; line-height: 1.6; } .sbi-letter h3 { text-align: center; text-decoration: underline; letter-spacing: 1px; margin: 18px 0; }
.sbi-letter .r { text-align: right; } .sbi-letter ol li { margin-bottom: 6px; } .sbi-letter .sign { margin-top: 48px; }</style>
{% set mr = "Mr." if doc.gender == "Male" else ("Ms." if doc.gender == "Female" else "") %}
{% set he = "He" if doc.gender == "Male" else ("She" if doc.gender == "Female" else "They") %}
{% set his = "his" if doc.gender == "Male" else ("her" if doc.gender == "Female" else "their") %}
{% set idno = doc.employee_number or doc.name %}
<div class="sbi-letter">
"""
APPOINT_HTML = LETTER_TOP + """<p class="r">Date: {{ frappe.utils.formatdate(frappe.utils.nowdate()) }}</p>
<p>Ref: APT/{{ idno }}</p>
<p>To,<br><b>{{ mr }} {{ doc.employee_name }}</b><br>{{ (doc.current_address or doc.permanent_address or "") | replace("\\n", "<br>") }}</p>
<h3>APPOINTMENT ORDER</h3>
<p>Dear {{ doc.first_name }},</p>
<p>We are pleased to appoint you as <b>{{ doc.designation or "__________" }}</b>{% if doc.department %} in the <b>{{ doc.department.split(" - ")[0] }}</b> department{% endif %}
of <b>{{ doc.company }}</b> with effect from <b>{{ frappe.utils.formatdate(doc.date_of_joining) }}</b>, on the following terms and conditions:</p>
<ol>
<li>Your Employee ID No. is <b>{{ idno }}</b>. Please quote it in all correspondence.</li>
{% if doc.ctc %}<li>Your total cost to the company will be <b>{{ frappe.utils.fmt_money(doc.ctc, currency="INR") }}</b> per year, as detailed in the salary annexure.</li>{% endif %}
<li>You will be on probation for six months from the date of joining. On satisfactory completion you will be confirmed in writing.</li>
<li>Office hours are {{ ((frappe.db.get_single_value("HR Settings", "sbi_office_in_time") or "09:30")|string)[:5] }} to {{ ((frappe.db.get_single_value("HR Settings", "sbi_office_out_time") or "18:30")|string)[:5] }}.
Attendance must be marked every day with the SBI Office app (photo and GPS). Leave must be applied for and approved in advance.</li>
<li>You may be posted to any office, site or project of the company as required by the work.</li>
<li>During probation either party may end the employment with 15 days' notice; after confirmation, with one month's notice or salary in lieu of notice.</li>
<li>You will keep all company information confidential and follow the rules of the company in force from time to time.</li>
</ol>
<p>Please sign the duplicate copy of this order as a token of your acceptance.</p>
<p class="sign">For <b>{{ doc.company }}</b><br><br><br>Authorised Signatory</p>
<hr>
<p><b>Acceptance</b><br>I have read and accept the above terms and conditions.</p>
<p>Signature: ______________________ &nbsp;&nbsp; Name: {{ doc.employee_name }} &nbsp;&nbsp; Date: ______________</p>
</div>"""
RELIEVE_HTML = LETTER_TOP + """<p class="r">Date: {{ frappe.utils.formatdate(doc.relieving_date or frappe.utils.nowdate()) }}</p>
<p>Ref: REL/{{ idno }}</p>
<p>To,<br><b>{{ mr }} {{ doc.employee_name }}</b><br>Employee ID No. {{ idno }}<br>{{ (doc.current_address or doc.permanent_address or "") | replace("\\n", "<br>") }}</p>
<h3>RELIEVING ORDER</h3>
<p>This is to certify that <b>{{ mr }} {{ doc.employee_name }}</b> (Employee ID No. {{ idno }}) was employed with <b>{{ doc.company }}</b>
as <b>{{ doc.designation or "__________" }}</b> from <b>{{ frappe.utils.formatdate(doc.date_of_joining) }}</b>
to <b>{{ frappe.utils.formatdate(doc.relieving_date) if doc.relieving_date else "__________" }}</b>.</p>
<p>{% if doc.resignation_letter_date %}With reference to {{ his }} resignation dated {{ frappe.utils.formatdate(doc.resignation_letter_date) }}, {% endif %}{{ he|lower if doc.resignation_letter_date else he }}
is relieved from {{ his }} duties with effect from the close of working hours on <b>{{ frappe.utils.formatdate(doc.relieving_date) if doc.relieving_date else "__________" }}</b>.</p>
<p>{{ he }} has handed over all company property and documents in {{ his }} charge. {{ his|capitalize }} full and final settlement will be made as per company rules.</p>
<p>During {{ his }} service we found {{ his }} conduct and work satisfactory. We wish {{ "him" if doc.gender == "Male" else ("her" if doc.gender == "Female" else "them") }} success in the future.</p>
<p class="sign">For <b>{{ doc.company }}</b><br><br><br>Authorised Signatory</p>
</div>"""
for pfn in [["SBI Appointment Order", APPOINT_HTML], ["SBI Relieving Order", RELIEVE_HTML]]:
    if frappe.db.exists("Print Format", pfn[0]):
        log("print format exists (kept, HR may have edited it): " + pfn[0])
        continue
    pdoc = frappe.get_doc({"doctype": "Print Format", "name": pfn[0], "__newname": pfn[0], "doc_type": "Employee", "module": module, "standard": "No",
        "custom_format": 1, "print_format_type": "Jinja", "html": pfn[1], "disabled": 0, "font_size": 13})
    pdoc.insert(ignore_permissions=True)
    log("print format added: " + pfn[0])

# units used on order lines (sq.ft and sq.m already come with ERPNext)
for u in ["Square Foot", "Square Meter", "Running Meter", "Lump Sum"]:
    if not frappe.db.exists("UOM", u):
        frappe.get_doc({"doctype": "UOM", "uom_name": u, "must_be_whole_number": 0, "enabled": 1}).insert(ignore_permissions=True)
        log("unit added: " + u)
    elif not frappe.db.get_value("UOM", u, "enabled"):
        frappe.db.set_value("UOM", u, "enabled", 1)

# ---------------------------------------------------------------- 2. server script (API)
if frappe.db.exists("Server Script", "SBI Lite ERP"):
    ss = frappe.get_doc("Server Script", "SBI Lite ERP")
else:
    ss = frappe.new_doc("Server Script")
    ss.name = "SBI Lite ERP"
    ss.flags.is_new_doc = True
ss.script_type = "API"
ss.api_method = API_METHOD
ss.allow_guest = 0
ss.disabled = 0
ss.script = SERVER_SCRIPT
if ss.flags.is_new_doc:
    ss.insert(ignore_permissions=True)
else:
    ss.save(ignore_permissions=True)
log("server script saved: " + ss.name)

# ---------------------------------------------------------------- 3. the page (Custom HTML Block)
if frappe.db.exists("Custom HTML Block", LABEL):
    blk = frappe.get_doc("Custom HTML Block", LABEL)
else:
    blk = frappe.new_doc("Custom HTML Block")
    blk.name = LABEL
    blk.flags.is_new_doc = True
blk.html = BLOCK_HTML
blk.style = BLOCK_CSS
blk.script = BLOCK_JS
blk.private = 0
blk.set("roles", [])
for r in roles:
    blk.append("roles", {"role": r})
if blk.flags.is_new_doc:
    blk.insert(ignore_permissions=True)
else:
    blk.save(ignore_permissions=True)
log("page saved: " + blk.name)

# ---------------------------------------------------------------- 4. workspace  /app/lite-erp
module = "SBI Projects" if frappe.db.exists("Module Def", "SBI Projects") else "Accounts"
if frappe.db.exists("Workspace", LABEL):
    ws = frappe.get_doc("Workspace", LABEL)
else:
    ws = frappe.new_doc("Workspace")
    ws.label = LABEL
    ws.standard = 0
    ws.flags.is_new_doc = True
ws.title = LABEL
ws.module = module
ws.public = 1
ws.is_hidden = 0
ws.type = "Workspace"
ws.icon = "layout"
ws.sequence_id = 0.5
ws.content = '[{"id":"sbiLiteErp01","type":"custom_block","data":{"custom_block_name":"Lite ERP","col":12}}]'
ws.set("custom_blocks", [{"custom_block_name": LABEL, "label": LABEL}])
ws.set("shortcuts", [])
ws.set("roles", [])
for r in roles:
    ws.append("roles", {"role": r})
ws.flags.ignore_links = True
if ws.flags.is_new_doc:
    ws.insert(ignore_permissions=True)
else:
    ws.save(ignore_permissions=True)
log("workspace saved: " + ROUTE)

# ---------------------------------------------------------------- 5. desktop icon (v16)
# v16 only lets a plain "Link" icon through when it belongs to a module sidebar, so the icon
# is an "App" icon that opens /desk/lite-erp. Users who have arranged their desktop see only
# their saved arrangement, so the icon is also added to every saved arrangement.
ICON_FIELDS = ["label", "bg_color", "link", "link_type", "app", "icon_type", "parent_icon", "icon", "link_to",
    "idx", "standard", "logo_url", "hidden", "name", "restrict_removal", "icon_image"]
if frappe.db.exists("DocType", "Desktop Icon"):
    if frappe.db.exists("Desktop Icon", LABEL):
        ic = frappe.get_doc("Desktop Icon", LABEL)
    else:
        ic = frappe.new_doc("Desktop Icon")
        ic.label = LABEL
        ic.flags.is_new_doc = True
        top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
        mx = 0
        for i in top:
            if (i or 0) > mx:
                mx = i or 0
        ic.idx = mx + 1
    ic.icon_type = "App"
    ic.link_type = "External"
    ic.link = ROUTE
    ic.link_to = None
    ic.icon = "layout"
    ic.bg_color = "blue"
    ic.app = "sbi_projects"
    ic.standard = 1          # v16 hides a non-standard App icon from everyone but its creator
    ic.hidden = 0
    ic.parent_icon = None
    ic.set("roles", [])
    for r in roles:
        ic.append("roles", {"role": r})
    ic.flags.ignore_links = True
    ic.flags.ignore_mandatory = True
    if ic.flags.is_new_doc:
        ic.insert(ignore_permissions=True)
    else:
        ic.save(ignore_permissions=True)
    frappe.db.set_value("Desktop Icon", ic.name, "owner", "Administrator", update_modified=False)
    log("desktop icon saved: " + ic.name)

    if frappe.db.exists("DocType", "Desktop Layout"):
        entry = {"child_icons": []}
        for fld in ICON_FIELDS:
            entry[fld] = ic.get(fld)
        users = ["Administrator"]
        if roles:
            for u in frappe.db.sql("""select distinct parent from `tabHas Role`
                    where parenttype='User' and role in %(r)s""", {"r": tuple(roles)}):
                users.append(u[0])
        added = 0
        for lay in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
            if lay.name not in users or not lay.layout:
                continue
            try:
                items = json.loads(lay.layout)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            kept = []
            for it in items:
                if not (isinstance(it, dict) and it.get("label") == LABEL):
                    kept.append(it)
            kept.append(entry)
            frappe.db.set_value("Desktop Layout", lay.name, "layout", json.dumps(kept), update_modified=False)
            added += 1
        log("added to " + str(added) + " saved desktop arrangement(s)")

# ---------------------------------------------------------------- 6. remove the earlier Accounts Desk
if REMOVE_OLD_ACCOUNTS_DESK:
    for pair in [["Desktop Icon", "Accounts Desk"], ["Workspace", "Accounts Desk"],
                 ["Custom HTML Block", "Accounts Desk"], ["Server Script", "SBI Accounts Desk"]]:
        if frappe.db.exists("DocType", pair[0]) and frappe.db.exists(pair[0], pair[1]):
            frappe.delete_doc(pair[0], pair[1], ignore_permissions=True)
            log("removed old " + pair[0] + ": " + pair[1])

# ---------------------------------------------------------------- 7. Office Punch app (desktop icon for every employee)
oroles = []
for r in OFFICE_ROLES_WANTED:
    if frappe.db.exists("Role", r):
        oroles.append(r)
if frappe.db.exists("Server Script", "SBI Office Punch"):
    oss = frappe.get_doc("Server Script", "SBI Office Punch")
else:
    oss = frappe.new_doc("Server Script")
    oss.name = "SBI Office Punch"
    oss.flags.is_new_doc = True
oss.script_type = "API"
oss.api_method = OFFICE_API
oss.allow_guest = 0
oss.disabled = 0
oss.script = OFFICE_SERVER
if oss.flags.is_new_doc:
    oss.insert(ignore_permissions=True)
else:
    oss.save(ignore_permissions=True)
log("server script saved: " + oss.name)

# reminders: every 5 minutes, N minutes before office start / end (HR Settings)
if frappe.db.exists("Server Script", "SBI Office Reminder"):
    rss = frappe.get_doc("Server Script", "SBI Office Reminder")
else:
    rss = frappe.new_doc("Server Script")
    rss.name = "SBI Office Reminder"
    rss.flags.is_new_doc = True
rss.script_type = "Scheduler Event"
rss.event_frequency = "Cron"
rss.cron_format = "*/5 * * * *"
rss.disabled = 0
rss.script = OFFICE_REMINDER
if rss.flags.is_new_doc:
    rss.insert(ignore_permissions=True)
else:
    rss.save(ignore_permissions=True)
log("reminder schedule saved: every 5 minutes")

# the app page itself (any logged-in user; the API only lets people punch for their own Employee)
wp_name = frappe.db.get_value("Web Page", {"route": OFFICE_ROUTE.strip("/")}, "name")
if wp_name:
    wp = frappe.get_doc("Web Page", wp_name)
else:
    wp = frappe.new_doc("Web Page")
    wp.flags.is_new_doc = True
wp.title = "SBI Office"
wp.route = OFFICE_ROUTE.strip("/")
wp.published = 1
wp.content_type = "HTML"
wp.main_section_html = OFFICE_HTML
wp.css = OFFICE_CSS
wp.insert_style = 1
wp.javascript = OFFICE_JS
wp.full_width = 1
wp.show_title = 0
wp.dynamic_template = 0
wp.meta_title = "SBI Office"
wp.meta_description = "Shiv Bharat office staff attendance - punch IN / OUT with selfie and GPS"
if wp.meta.has_field("show_sidebar"):
    wp.show_sidebar = 0
if wp.flags.is_new_doc:
    wp.insert(ignore_permissions=True)
else:
    wp.save(ignore_permissions=True)
log("app page saved: " + OFFICE_ROUTE)

# install-as-app files: manifest (Add to Home screen / APK) and the notification worker
app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo") or "/assets/frappe/images/frappe-framework-logo.svg"
# app icons (Android home screen, iPhone home screen)
for pair in [["sbi_office_icon_180.png", ICON_180], ["sbi_office_icon_192.png", ICON_192], ["sbi_office_icon_512.png", ICON_512]]:
    if frappe.get_all("File", filters={"file_url": "/files/" + pair[0]}, pluck="name"):
        continue
    idoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1], "decode": True})
    idoc.flags.ignore_permissions = True
    idoc.insert(ignore_permissions=True)
    log("icon saved: " + idoc.file_url)
MANIFEST = '{"name": "SBI Office - Staff Attendance", "short_name": "SBI Office", "id": "/sbi_office", "start_url": "/sbi_office", "scope": "/sbi_office", ' + \
    '"display": "standalone", "orientation": "portrait", "background_color": "#f3f4f6", "theme_color": "#c8102e", ' + \
    '"description": "Punch IN / OUT with selfie and GPS", "icons": [{"src": "/files/sbi_office_icon_192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"}, ' + \
    '{"src": "/files/sbi_office_icon_512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]}'
for pair in [["sbi_office_manifest_v2.json", MANIFEST], ["sbi_office_sw.js", OFFICE_SW]]:
    furl = "/files/" + pair[0]
    old = frappe.get_all("File", filters={"file_url": furl}, pluck="name")
    if old:
        log("file kept: " + furl)
        continue
    fdoc = frappe.get_doc({"doctype": "File", "file_name": pair[0], "is_private": 0, "content": pair[1]})
    fdoc.flags.ignore_permissions = True
    fdoc.insert(ignore_permissions=True)
    log("file saved: " + fdoc.file_url)

# Android app (APK) for staff to download: /files/SBI-Office-v1.0.apk
APK_NAME = "SBI-Office-v1.0.apk"
if frappe.get_all("File", filters={"file_url": "/files/" + APK_NAME}, pluck="name"):
    log("android app kept: /files/" + APK_NAME)
else:
    adoc = frappe.get_doc({"doctype": "File", "file_name": APK_NAME, "is_private": 0, "content": OFFICE_APK, "decode": True})
    adoc.flags.ignore_permissions = True
    adoc.insert(ignore_permissions=True)
    log("android app saved: " + adoc.file_url)

# old desk version of the punch page (if an earlier test made it)
for pair in [["Workspace", "Office Punch"], ["Custom HTML Block", "Office Punch"], ["Desktop Icon", "Office Punch"]]:
    if frappe.db.exists(pair[0], pair[1]):
        frappe.delete_doc(pair[0], pair[1], ignore_permissions=True)
        log("removed old " + pair[0] + ": " + pair[1])

if frappe.db.exists("DocType", "Desktop Icon"):
    if frappe.db.exists("Desktop Icon", OFFICE_LABEL):
        oic = frappe.get_doc("Desktop Icon", OFFICE_LABEL)
    else:
        oic = frappe.new_doc("Desktop Icon")
        oic.label = OFFICE_LABEL
        oic.flags.is_new_doc = True
        top = frappe.get_all("Desktop Icon", filters={"parent_icon": ["in", ["", None]]}, pluck="idx")
        mx = 0
        for i in top:
            if (i or 0) > mx:
                mx = i or 0
        oic.idx = mx + 1
    oic.icon_type = "App"
    oic.link_type = "External"
    oic.link = OFFICE_ROUTE
    oic.link_to = None
    oic.icon = "map-pin"
    oic.bg_color = "blue"
    oic.app = "sbi_projects"
    oic.standard = 1
    oic.hidden = 0
    oic.parent_icon = None
    oic.set("roles", [])
    for r in oroles:
        oic.append("roles", {"role": r})
    oic.flags.ignore_links = True
    oic.flags.ignore_mandatory = True
    if oic.flags.is_new_doc:
        oic.insert(ignore_permissions=True)
    else:
        oic.save(ignore_permissions=True)
    frappe.db.set_value("Desktop Icon", oic.name, "owner", "Administrator", update_modified=False)
    log("desktop icon saved: " + oic.name)
    if frappe.db.exists("DocType", "Desktop Layout"):
        oentry = {"child_icons": []}
        for fld in ICON_FIELDS:
            oentry[fld] = oic.get(fld)
        ousers = ["Administrator"]
        if oroles:
            for u in frappe.db.sql("""select distinct parent from `tabHas Role` where parenttype='User' and role in %(r)s""", {"r": tuple(oroles)}):
                ousers.append(u[0])
        oadded = 0
        for lay in frappe.get_all("Desktop Layout", fields=["name", "layout"]):
            if lay.name not in ousers or not lay.layout:
                continue
            try:
                items = json.loads(lay.layout)
            except Exception:
                continue
            if not isinstance(items, list):
                continue
            kept = []
            for it in items:
                if not (isinstance(it, dict) and it.get("label") == OFFICE_LABEL):
                    kept.append(it)
            kept.append(oentry)
            frappe.db.set_value("Desktop Layout", lay.name, "layout", json.dumps(kept), update_modified=False)
            oadded = oadded + 1
        log("SBI Office added to " + str(oadded) + " saved desktop arrangement(s)")

# Tally belongs to the accounts team: hide the Tally workspace and Tally desktop icons from everyone else (e.g. HR)
TALLY_ROLES = []
for r in ["System Manager", "Accounts Manager", "Accounts User", "Business Owner"]:
    if frappe.db.exists("Role", r):
        TALLY_ROLES.append(r)
for pair in [["Workspace", "Tally Integration"], ["Desktop Icon", "Tally"], ["Desktop Icon", "Tally Reports"]]:
    if not frappe.db.exists("DocType", pair[0]) or not frappe.db.exists(pair[0], pair[1]):
        continue
    tdoc = frappe.get_doc(pair[0], pair[1])
    tdoc.set("roles", [])
    for r in TALLY_ROLES:
        tdoc.append("roles", {"role": r})
    tdoc.flags.ignore_links = True
    tdoc.flags.ignore_mandatory = True
    tdoc.save(ignore_permissions=True)
    log("accounts team only: " + pair[0] + " " + pair[1])

# who can punch: active employees need their login in Employee -> User ID
nolink = frappe.db.sql("select count(*) from `tabEmployee` where status='Active' and ifnull(user_id, '')=''")[0][0]
log("active employees without a login (cannot punch until User ID is set): " + str(nolink))

frappe.db.commit()
log("DONE. Reload the browser (Ctrl+Shift+R). Lite ERP: " + ROUTE + "   Staff punch app: " + frappe.utils.get_url(OFFICE_ROUTE))
