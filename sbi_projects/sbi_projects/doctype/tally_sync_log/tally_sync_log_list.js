frappe.listview_settings["Tally Sync Log"] = {
	add_fields: ["status", "direction"],
	get_indicator(doc) {
		const colour = {
			Success: "green", Linked: "blue", Failed: "red", Skipped: "gray", Deleted: "orange",
		}[doc.status] || "gray";
		return [doc.direction + " · " + doc.status, colour, "status,=," + doc.status];
	},
};
