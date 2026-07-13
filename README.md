# SBI Projects

Site Management, Project Templates and BOQ for Shiv Bharat Infrastructures.
Built on Frappe/ERPNext v16.

## What it adds

| DocType | Purpose |
|---|---|
| **Project Stage** | Master list of all possible stages (Design, Foundation, Fabrication...). Users add their own. |
| **SBI Project Template** | Reusable template: pick stages, set weight % and duration. Total must = 100%. |
| **Project Template Stage** | Child table of the above. |
| **BOQ Template** | Reusable BOQ: items + default qty/rate, each tagged to a stage. |
| **BOQ Template Item** | Child table of the above. |
| **BOQ** | Actual BOQ for a project. Submittable, revisable. |
| **BOQ Item** | Child table; each row links to a stage and (on submit) to the project's Task. |

Custom fields added to **Project**: template, current stage, site in-charge, site
address, site warehouse, BOQ link, contract value, built-up area, tonnage, and
GPS lat/long + geofence radius (for the attendance module).

Custom field added to **Task**: `sbi_stage` — this is the join between a project
task and its BOQ items.

## How it works

1. Create **Project Stage** records (12 are seeded on install).
2. Create an **SBI Project Template** — select stages, set weights (must total 100%),
   durations, and dependencies.
3. Create a **BOQ Template** — add items, tag each to a stage.
4. Create a **Project** → select the template → **Save**. Tasks are created
   automatically with weight, dates and dependencies.
5. From the Project, click **Create → BOQ** → select the BOQ Template → items
   auto-fill → edit qty/rate → **Submit**.
6. On submit, each BOQ item is linked to its matching Task, and the BOQ total is
   pushed to `Project.estimated_costing`.

Set the project's **% Complete Method** to `Task Weight` so progress reflects the
template weights.

## Install

```bash
cd ~/frappe-bench
bench get-app https://github.com/<your-org>/sbi_projects.git
bench --site erp.shiv-bharath.com install-app sbi_projects
bench --site erp.shiv-bharath.com migrate
bench build --app sbi_projects
bench --site erp.shiv-bharath.com clear-cache
```

On Frappe Cloud: Bench → Apps → **Add App** → point at the GitHub repo, then
deploy and install on the site.

## Developing

```bash
bench get-app sbi_projects /path/to/sbi_projects
bench --site <site> install-app sbi_projects
```

Export DocType changes back to the repo:

```bash
bench --site <site> export-fixtures --app sbi_projects
```
