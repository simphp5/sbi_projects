// Copyright (c) 2026, Velmaska and contributors
// For license information, please see license.txt

frappe.query_reports["Purchase Invoice Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
		},
		{
			fieldname: "from_date",
			label: __("From Invoice Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
		},
		{
			fieldname: "to_date",
			label: __("To Invoice Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Draft", "Unpaid", "Overdue", "Paid", "Return", "Cancelled"].join("\n"),
		},
		{
			fieldname: "only_outstanding",
			label: __("Only unpaid"),
			fieldtype: "Check",
			default: 0,
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		// an overdue bill should be obvious at a glance
		if (column.fieldname === "days_overdue" && data && data.days_overdue > 0) {
			const shade = data.days_overdue > 30 ? "var(--red-600)" : "var(--orange-600)";
			value = `<span style="color:${shade};font-weight:600">${value}</span>`;
		}
		return value;
	},
};
