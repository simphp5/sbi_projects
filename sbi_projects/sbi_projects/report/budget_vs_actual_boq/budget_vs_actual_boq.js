// Copyright (c) 2026, Velmaska and contributors
frappe.query_reports["Budget vs Actual BOQ"] = {
	filters: [
		{ fieldname: "company", label: __("Company (all if empty)"), fieldtype: "Link", options: "Company" },
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project",
			get_query: () => { const c = frappe.query_report.get_filter_value("company"); return c ? { filters: { company: c } } : {}; } },
		{ fieldname: "period", label: __("Period"), fieldtype: "Select", default: "This Financial Year",
			options: ["Today", "This Week", "This Month", "This Quarter", "This Half Year", "This Financial Year",
				"Last Month", "Last Quarter", "Last Financial Year", "Custom"].join("\n"),
			},
		{ fieldname: "from_date", label: __("From"), fieldtype: "Date", depends_on: "eval:doc.period=='Custom'" },
		{ fieldname: "to_date", label: __("To"), fieldtype: "Date", depends_on: "eval:doc.period=='Custom'" },
	],
	onload(report) {
		report.page.add_inner_button(__("Cash Flow Dashboard"), () => frappe.set_route("cash-flow"));
	},
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldtype === "Currency" && data && data[column.fieldname] < 0) value = `<span style="color:#d03b3b">${value}</span>`;
		if (column.fieldname === "flag" && data && data.flag === "Over budget") value = `<b style="color:#d03b3b">${value}</b>`;
		return value;
	},
};

