# Tally ⇄ ERPNext Integration (sbi_projects)

Two-way sync between TallyPrime and ERPNext for Shiv Bharat Infrastructures. Both systems can be used for entry. Each record crosses once, and a record never comes back to the system it came from.

## What moves

| From Tally into ERPNext | From ERPNext into Tally |
|---|---|
| Ledgers become **Accounts**. Each one is placed under the ERPNext group from the Group Map. | **Sales / Purchase Invoices** become Sales / Purchase vouchers. Returns become Credit / Debit Notes. |
| Sundry Debtors become **Customers**, and Sundry Creditors become **Suppliers**. | **Payment Entries** become Receipt / Payment / Contra vouchers. |
| Stock Items become **Items**. Stock groups become Item Groups, units become UOMs, and the HSN code comes across when it exists in ERPNext. | **Journal Entries** become Journal vouchers. Contra Entries become Contra vouchers. |
| Every voucher type becomes a **Journal Entry** with the same ledgers, the same party and the same bill references. This covers sales, purchase, receipt, payment, contra, journal, and credit/debit notes. | Any ledger a voucher needs is **created in Tally first**, along with new Customers and Suppliers. |
| An edit in Tally cancels the old entry and re-posts it (amended). A delete or cancel in Tally cancels the entry. | A cancel in ERPNext deletes the voucher in Tally. |
| **Opening balances** come in as one draft Opening Entry, on request. | |

**Bill references cross in both directions.** A receipt typed in Tally "Agst Ref SINV-0001" arrives in ERPNext linked to that Sales Invoice, so the invoice's outstanding amount drops.

**Loop protection works in four ways:**
- Vouchers that ERPNext sends carry `REMOTEID = ERPN:<type>:<name>`.
- The Sync Log remembers every exported voucher, so when the Day Book shows it again, it is skipped.
- Journal Entries that came from Tally carry a `tally_guid` and are never exported.
- Ledgers are matched by name before anything is created.

## How it is built

```
Tally PC                                  ERPNext (Frappe Cloud)
┌──────────────┐  XML on port 9000   ┌───────────┐   HTTPS + API key   ┌──────────────────────────┐
│  TallyPrime  │ ◀─────────────────▶ │  agent    │ ◀─────────────────▶ │ sbi_projects.tally       │
└──────────────┘                     │ (relay)   │                     │  builds every request,   │
                                     └───────────┘                     │  maps, logs, dashboard   │
                                                                       └──────────────────────────┘
```

All the logic lives in ERPNext, so future fixes are deployed through Git and the Tally PC never needs touching. The agent does three things on every cycle: it asks ERPNext for requests, passes them to Tally, and returns Tally's answers.

The stages run in this order on every cycle: `status → masters → export_masters → export_vouchers → import_vouchers → opening`.

**Change detection.** The agent compares Tally's company *AltMstId* and *AltVchId* with the values from the last sync. Masters and the Day Book are re-read only when one of these has changed.

## Files

| Path | Purpose |
|---|---|
| `sbi_projects/tally/tallyxml.py` | Tally XML builders and parsers (pure Python) |
| `sbi_projects/tally/agent_api.py` | Endpoints that the agent calls |
| `sbi_projects/tally/exporter.py` | ERPNext → Tally |
| `sbi_projects/tally/importer.py` | Tally → ERPNext (status, masters, vouchers, opening balances) |
| `sbi_projects/tally/admin.py` | Settings buttons, summary panel and number-card method |
| `sbi_projects/tally/common.py` | Settings access, Sync Log upsert, name helpers |
| `sbi_projects/sbi_projects/doctype/tally_settings` | Single DocType where the customer sets everything |
| `sbi_projects/sbi_projects/doctype/tally_group_map` | Child table: Tally group ⇄ ERPNext group account |
| `sbi_projects/sbi_projects/doctype/tally_sync_log` | One row per record moved; this is the source for all counts |
| `sbi_projects/setup/tally_setup.py` | Custom fields, the *Tally Agent* role, 4 number cards, 4 charts and the **Tally Integration** workspace |
| `sbi_projects/public/tally_agent/` | `tally_agent.py` and `agent_autostart.ps1`, downloadable from Tally Settings |
| `sbi_projects/setup/install.py` | Adds the `setup_tally` step (2 lines) |

## Deploy (implementer)

1. Copy the files into the repo. Check them first, as usual:
   - Python: `python -m py_compile`
   - JavaScript: `node --check`
   - JSON: confirm the files have no BOM
2. Commit, then run `git push origin main`.
3. In Frappe Cloud:
   - Run **Update Now** from the Site Updates tab.
   - Run **In-Place Migrate**. `after_migrate` creates the custom fields, the role, the cards, the charts and the workspace.
4. Check in the console:
   ```js
   frappe.db.exists("DocType","Tally Settings").then(console.log)
   ```

## Customer setup (Tally Settings form)

1. **TallyPrime:**
   - Go to F1 Help → Settings → Connectivity → Client/Server configuration.
   - Set *TallyPrime acts as* = **Both** and *Port* = **9000**, then restart Tally.
   - Set the voucher types to **Manual** numbering, so that ERPNext numbers are kept.
2. **ERPNext:** open **Tally Settings** and fill in:
   - Company, Tally Company Name, Sync From Date, Host/Port
   - The **Group Map**, which fills itself from the chart of accounts. Check it, and add rows for your own Tally sub-groups if needed.
   - Save.
3. Click **Agent → Generate Agent Key**. A `config.json` file downloads.
4. On the Tally PC:
   - Install Python 3, ticking *Add to PATH*.
   - Make a folder `C:\TallyAgent` and put three files in it: `tally_agent.py` (Agent → Download Agent), `agent_autostart.ps1` (Agent → Download Auto-start Installer) and `config.json`.
   - Run `powershell -ExecutionPolicy Bypass -File .\agent_autostart.ps1`. It tests both connections, then installs the agent to start at login.
5. Back in Tally Settings, check **Agent Status**. It should be green, and it lists the companies open in Tally. Make sure **Tally Company Name** matches exactly.
6. Tick **Enable Tally Sync** and save. The first cycle reads masters, sends pending ERPNext vouchers and brings in Tally vouchers.
7. *(Optional)* **Sync → Import Opening Balances** creates a draft opening entry. Review it and submit.

## Dashboard and counts

- **Tally Settings → Sync Summary** shows:
  - Tiles: waiting to send, sent today, received today, failed.
  - A table of Exported / Imported / Linked / Failed / Deleted counts per record type. Every number links to the filtered Sync Log.
- The **Tally Integration** workspace has number cards, *Sent per Day* and *Received per Day* charts, plus breakdowns by record type and by status.
- **Tally Sync Log** has one row per record, showing direction, status, the ERPNext record, the Tally name and voucher, the amount and the error message.

## Handling problems

| Problem | What to do |
|---|---|
| Something shows **Failed** | Read the message in the Sync Log, or in *Tally Sync Error* on the document. Fix the cause, then click **Sync → Retry Failed**. |
| A Tally group has no Group Map row | Add the row and click **Re-read Tally Masters**. |
| Imported entries look wrong | Fix the mapping and click **Re-check Tally Vouchers**. Entries that already match are not duplicated. |
| The safety guard fired | If more than 20% of imported vouchers seem deleted in a single pass, nothing is cancelled. A warning is shown instead. |

## Known limits

- **Tally invoices arrive as Journal Entries, not Sales or Purchase Invoices.** The money impact is exact, but item lines are not carried. GST returns therefore need to come from one system consistently.
- **Inventory is not carried.** Stock movements and stock vouchers are out of scope. Stock-in-Hand ledgers and Stock accounts are skipped.
- **Cost centres are not carried.** Imported entries use the cost centre set in Tally Settings, or the company default.
- **The integration was built and unit-tested without a live TallyPrime.** Run the first sync on a **copy of the Tally company** and check the results in the Sync Log. In particular, confirm that deleting in Tally after an ERPNext cancellation works on your TallyPrime release.
