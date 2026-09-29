# Copyright (c) 2026, Velmaska and contributors
# For license information, please see license.txt
"""
The Techno-Commercial Proposal print format.

This is the document the client receives, laid out as SBI already writes it:
project details, a four-line commercial summary, the scope matrix, the payment
stages and the terms. The priced BOQ stays behind -- the client never sees a
line rate, only the rate per square foot by trade.

The format is rewritten on every migrate, so edits belong in this file rather
than in the Print Format Builder.
"""

import frappe

NAME = "SBI Techno-Commercial Proposal"

HTML = r"""
{%- set C = frappe.get_doc("Company", doc.company) -%}

<div class="sbi-proposal">

<div class="hdr">
  <div class="co">{{ C.company_name }}</div>
  {%- if C.get("address_html") %}<div class="ln">{{ C.address_html }}</div>{% endif %}
  <div class="ln">
    {%- if C.email %}Email: {{ C.email }}{% endif %}
    {%- if C.phone_no %} &nbsp;|&nbsp; Mobile: {{ C.phone_no }}{% endif %}
    {%- if C.website %} &nbsp;|&nbsp; {{ C.website }}{% endif %}
  </div>
  {%- if C.get("tax_id") %}<div class="ln">GSTIN: {{ C.tax_id }}</div>{% endif %}
</div>

<table class="meta">
  <tr>
    <td><b>Proposal No:</b> {{ doc.name }}</td>
    <td class="r"><b>Date:</b> {{ frappe.utils.formatdate(doc.transaction_date, "dd-MM-yyyy") }}</td>
  </tr>
</table>

<div class="subject">
  Techno-Commercial Proposal for
  {{ doc.get("sbi_scope_note") or "Design, Supply &amp; Construction" }}
  {%- if doc.get("sbi_project_title") %} &mdash; {{ doc.sbi_project_title }}{% endif %}
</div>

<!-- 1 ............................................................. -->
<div class="sec"><span class="no">1</span> Project Details</div>
<table class="grid">
  <tr class="th"><th style="width:32%">Item</th><th>Description</th></tr>
  {%- if doc.get("sbi_project_title") %}
  <tr><td>Project</td><td>{{ doc.sbi_project_title }}</td></tr>{% endif %}
  {%- if doc.get("sbi_client_name") %}
  <tr><td>Client</td><td>{{ doc.sbi_client_name }}</td></tr>{% endif %}
  {%- if doc.get("sbi_location") %}
  <tr><td>Location</td><td>{{ doc.sbi_location }}</td></tr>{% endif %}
  {%- if doc.get("sbi_area_note") %}
  <tr><td>Area of Building</td><td>{{ doc.sbi_area_note }}</td></tr>{% endif %}
  {%- if doc.get("sbi_scope_note") %}
  <tr><td>Scope</td><td>{{ doc.sbi_scope_note }}</td></tr>{% endif %}
  {%- if doc.get("sbi_design_note") %}
  <tr><td>Design Data</td><td>{{ doc.sbi_design_note|replace("\n", "<br>") }}</td></tr>{% endif %}
  {%- if doc.get("sbi_dimensions") %}
  <tr><td>Dimensions</td><td>{{ doc.sbi_dimensions|replace("\n", "<br>") }}</td></tr>{% endif %}
</table>

<!-- 2 ............................................................. -->
{%- if doc.get("sbi_trade_summary") %}
<div class="sec"><span class="no">2</span> Commercial Summary</div>
<table class="grid">
  <tr class="th">
    <th style="width:34%">Description</th>
    <th class="r" style="width:16%">Area (sft)</th>
    <th class="r" style="width:20%">Unit Rate</th>
    <th class="r" style="width:30%">Total</th>
  </tr>
  {%- for r in doc.sbi_trade_summary %}
  <tr class="{{ 'tot' if r.is_total else '' }}">
    <td>{{ r.trade }}</td>
    <td class="r">{{ "{:,.0f}".format(r.area_sft or 0) }}</td>
    <td class="r">{{ frappe.utils.fmt_money(r.unit_rate, currency=doc.currency) }}</td>
    <td class="r">{{ frappe.utils.fmt_money(r.total, currency=doc.currency) }}{% if r.is_total %} <span class="gst">+ applicable GST</span>{% endif %}</td>
  </tr>
  {%- endfor %}
</table>
{%- endif %}

<!-- 3 ............................................................. -->
{%- if doc.get("sbi_scope") %}
<div class="sec"><span class="no">3</span> Scope of Works</div>
<table class="grid scope">
  <tr class="th">
    <th style="width:7%">Sl. No</th>
    <th>Description of Works</th>
    <th class="c" style="width:11%">{{ C.abbr or "SBI" }}</th>
    <th class="c" style="width:11%">Client</th>
    <th style="width:30%">Remarks</th>
  </tr>
  {%- set ns = namespace(section=None, n=0) %}
  {%- for r in doc.sbi_scope %}
    {%- if r.scope_section and r.scope_section != ns.section %}
      {%- set ns.section = r.scope_section %}
  <tr class="grp"><td colspan="5">{{ r.scope_section }}</td></tr>
    {%- endif %}
    {%- set ns.n = ns.n + 1 %}
  <tr>
    <td class="c">{{ ns.n }}</td>
    <td>{{ r.description }}</td>
    <td class="c">{% if r.carried_out_by == "SBI" %}&#10003;{% endif %}</td>
    <td class="c">{% if r.carried_out_by == "Client" %}&#10003;{% endif %}</td>
    <td class="sm">{{ r.remarks or "" }}</td>
  </tr>
  {%- endfor %}
</table>
<div class="note">Any item not specifically mentioned above is excluded from this proposal.</div>
{%- endif %}

<!-- 4 ............................................................. -->
{%- if doc.payment_schedule %}
<div class="sec"><span class="no">4</span> Payment Terms</div>
<table class="grid">
  <tr class="th">
    <th style="width:7%">Sl. No</th>
    <th>Stage</th>
    <th class="r" style="width:12%">%</th>
    <th class="r" style="width:24%">Amount</th>
  </tr>
  {%- for r in doc.payment_schedule %}
  <tr>
    <td class="c">{{ loop.index }}</td>
    <td>{{ r.get("project_stage") or r.description or r.payment_term or "" }}</td>
    <td class="r">{{ "{:.0f}%".format(r.invoice_portion or 0) }}</td>
    <td class="r">{{ frappe.utils.fmt_money(r.payment_amount, currency=doc.currency) }}</td>
  </tr>
  {%- endfor %}
  <tr class="tot">
    <td></td><td>Total</td>
    <td class="r">100%</td>
    <td class="r">{{ frappe.utils.fmt_money(doc.grand_total, currency=doc.currency) }}</td>
  </tr>
</table>
{%- endif %}

{%- if doc.get("sbi_delivery_note_text") %}
<div class="note"><b>Delivery / Completion Period:</b> {{ doc.sbi_delivery_note_text }}</div>
{%- endif %}

<!-- 5 ............................................................. -->
{%- if doc.terms %}
<div class="sec"><span class="no">5</span> Terms &amp; Conditions</div>
<div class="terms">{{ doc.terms }}</div>
{%- endif %}

<div class="sign">
  <div>Yours faithfully,</div>
  <div class="sp"></div>
  <div class="for">For {{ C.company_name }}</div>
</div>

</div>

<style>
.sbi-proposal { font-family: "Helvetica Neue", Arial, sans-serif; font-size: 9pt;
                color: #1a1a1a; line-height: 1.45; }
.sbi-proposal .hdr { text-align: center; border-bottom: 2px solid #BE1E2D;
                     padding-bottom: 7px; margin-bottom: 11px; }
.sbi-proposal .co { font-size: 14pt; font-weight: 700; color: #BE1E2D;
                    letter-spacing: .3px; }
.sbi-proposal .ln { font-size: 8pt; color: #555; margin-top: 2px; }
.sbi-proposal .ln p { margin: 0; }

.sbi-proposal table.meta { width: 100%; margin-bottom: 10px; font-size: 9pt; }
.sbi-proposal table.meta td { padding: 0; }

.sbi-proposal .subject { font-weight: 700; font-size: 10pt; text-align: center;
                         margin: 4px 0 14px; padding: 7px 10px;
                         background: #f7f7f7; border: 1px solid #ddd; }

.sbi-proposal .sec { font-weight: 700; font-size: 10pt; color: #BE1E2D;
                     margin: 16px 0 6px; padding-bottom: 3px;
                     border-bottom: 1px solid #BE1E2D; }
.sbi-proposal .sec .no { display: inline-block; background: #BE1E2D; color: #fff;
                         width: 17px; height: 17px; line-height: 17px;
                         text-align: center; border-radius: 2px;
                         font-size: 8.5pt; margin-right: 6px; }

.sbi-proposal table.grid { width: 100%; border-collapse: collapse;
                           margin-bottom: 8px; }
.sbi-proposal table.grid th,
.sbi-proposal table.grid td { border: 1px solid #ccc; padding: 4px 7px;
                              vertical-align: top; }
.sbi-proposal table.grid tr.th th { background: #BE1E2D; color: #fff;
                                    font-weight: 600; font-size: 8.5pt; }
.sbi-proposal table.grid tr.grp td { background: #eee; font-weight: 700;
                                     font-size: 8.5pt; }
.sbi-proposal table.grid tr.tot td { background: #f4f4f4; font-weight: 700; }
.sbi-proposal .r { text-align: right; }
.sbi-proposal .c { text-align: center; }
.sbi-proposal .sm { font-size: 8pt; color: #555; }
.sbi-proposal .gst { font-size: 7.5pt; font-weight: 400; color: #666; }
.sbi-proposal table.scope td { font-size: 8.5pt; }

.sbi-proposal .note { font-size: 8.5pt; color: #444; margin: 7px 0 12px;
                      padding: 6px 9px; background: #fff8ec;
                      border-left: 3px solid #d97706; }

.sbi-proposal .terms { font-size: 8.5pt; line-height: 1.5; }
.sbi-proposal .terms p { margin: 0 0 4px; }

.sbi-proposal .sign { margin-top: 26px; font-size: 9pt; }
.sbi-proposal .sign .sp { height: 46px; }
.sbi-proposal .sign .for { font-weight: 700; }

@media print {
  .sbi-proposal .sec { page-break-after: avoid; }
  .sbi-proposal table.grid tr { page-break-inside: avoid; }
}
</style>
"""


def create_proposal_print_format():
	if not frappe.db.exists("DocType", "Quotation"):
		return 0

	if frappe.db.exists("Print Format", NAME):
		doc = frappe.get_doc("Print Format", NAME)
	else:
		doc = frappe.new_doc("Print Format")
		doc.name = NAME

	doc.doc_type = "Quotation"
	doc.module = "PEB Estimation"
	doc.print_format_type = "Jinja"
	doc.standard = "No"
	doc.custom_format = 1
	doc.disabled = 0
	doc.html = HTML
	if doc.meta.has_field("margin_top"):
		doc.margin_top = 12
		doc.margin_bottom = 12
		doc.margin_left = 12
		doc.margin_right = 12

	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return 1
