// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric Sync Log", {
	refresh: function (frm) {
		if (frm.doc.request_data && frm.doc.status == "Error") {
			frm.add_custom_button("Retry", function () {
				frappe.call({
					method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.resync",
					args: {
						method: frm.doc.method,
						name: frm.doc.name,
						request_data: frm.doc.request_data,
					},
					callback: function (r) {
						frappe.msgprint(__("Reattempting to sync"));
					},
				});
			}).addClass("btn-primary");
		}
	},
});
