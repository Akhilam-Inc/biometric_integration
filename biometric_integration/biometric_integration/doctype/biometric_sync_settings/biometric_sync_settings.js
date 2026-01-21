// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric Sync Settings", {
	refresh(frm) {},
	sync_logs: function (frm) {
		frappe.call({
			method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.fetch_device_logs_background",
			callback: function (r) {
				if (!r.exc) {
					if (r.message) {
						frappe.msgprint(r.message);
					} else {
						frappe.msgprint("Error: " + r.message.message);
					}
				} else {
					frappe.msgprint("Unexpected server error.");
				}
			},
		});
	},
	sync_logs_for_missing_date : function (frm) {
		frappe.call({
			method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.fetch_device_logs_for_missing_date_background",
			callback: function (r) {
				if (!r.exc) {
					if (r.message) {
						frappe.msgprint(r.message);
					} else {
						frappe.msgprint("Error: " + r.message.message);
					}
				} else {
					frappe.msgprint("Unexpected server error.");
				}
			},
		});
	},
});
