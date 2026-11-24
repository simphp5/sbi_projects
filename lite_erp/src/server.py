# SBI Lite ERP - API server script (api_method: sbi_lite_erp)
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

frappe.response["message"] = out
