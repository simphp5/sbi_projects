/* ---------------------------------------------------------------------------
 * SBI Projects - open the print view in a NEW BROWSER TAB
 * ---------------------------------------------------------------------------
 * Frappe default: the Print button routes to /app/print/<doctype>/<name>
 * in the SAME tab, so the user loses the form they were on.
 *
 * This patch replaces Form.print_doc() so the print view opens in a new tab
 * instead. Everything else (print format picker, letter head, PDF button)
 * behaves exactly as before.
 * --------------------------------------------------------------------------- */

(function () {
    "use strict";

    var MAX_TRIES = 40;   // ~10 seconds
    var tries = 0;

    function build_print_url(doctype, name) {
        return "/app/print/" +
            encodeURIComponent(doctype) + "/" +
            encodeURIComponent(name);
    }

    function patch() {
        if (typeof frappe === "undefined") { return false; }
        if (!frappe.ui || !frappe.ui.form || !frappe.ui.form.Form) { return false; }

        var proto = frappe.ui.form.Form.prototype;
        if (proto.__sbi_print_newtab) { return true; }   // already patched

        proto.__sbi_print_newtab = true;

        proto.print_doc = function () {
            var doc = this.doc || {};

            if (doc.docstatus === 2) {
                frappe.msgprint(__("Cannot print a cancelled document"));
                return;
            }

            if (this.is_new && this.is_new()) {
                frappe.msgprint(__("Please save the document before printing"));
                return;
            }

            var url = build_print_url(doc.doctype, doc.name);
            var win = window.open(url, "_blank", "noopener");

            if (!win) {
                // popup blocker kicked in - fall back to normal in-tab routing
                frappe.show_alert({
                    message: __("Allow pop-ups for this site to open print in a new tab"),
                    indicator: "orange"
                }, 7);
                frappe.set_route("print", doc.doctype, doc.name);
            }
        };

        return true;
    }

    function boot() {
        if (patch()) { return; }
        tries += 1;
        if (tries < MAX_TRIES) { setTimeout(boot, 250); }
    }

    // try immediately, and again once the desk signals it is ready
    boot();
    if (typeof $ !== "undefined") {
        $(document).on("app_ready", function () { patch(); });
    }
})();