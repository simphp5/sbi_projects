frappe.ui.form.on("Project BOQ", {
    refresh(frm) {
        if (frm.doc.project) {
            frm.add_custom_button(__("Import from Excel"), () => {
                frappe.prompt(
                    [{fieldname: "file_url", label: "Attached File URL",
                      fieldtype: "Data", reqd: 1,
                      description: "Attach the BOQ template to this document first, then paste its /private/files/... URL here"}],
                    (v) => {
                        frappe.call({
                            method: "sbi_projects.boq_import.import_boq_excel",
                            args: {project: frm.doc.project, file_url: v.file_url},
                            freeze: true,
                            callback: (r) => {
                                frappe.msgprint("Imported: " + JSON.stringify(r.message));
                                frm.reload_doc();
                            }
                        });
                    }, __("Import BOQ"), __("Import"));
            });
            frm.add_custom_button(__("Customer Link"), () => {
                frappe.call({
                    method: "sbi_projects.project_cost_api.create_customer_link",
                    args: {project: frm.doc.project},
                    callback: (r) => {
                        const url = window.location.origin + r.message.url;
                        frappe.msgprint("<a href='" + url + "' target='_blank'>" + url + "</a><br><br>Share this link with the customer.");
                    }
                });
            });
            frm.add_custom_button(__("Cost Overview"), () => {
                window.open("/sbi_owner?project=" + frm.doc.project, "_blank");
            });
        }
    }
});
