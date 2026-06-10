// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric Sync Settings", {
	refresh(frm) {
		frappe.realtime.on("biometric_sync_update", function (data) {
			frm.reload_doc();
		});
	},
});

frappe.ui.form.on("Biometric Location Detail", {
	sync_log: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.location) {
			frappe.throw(__("Please select a location before syncing."));
			return;
		}
		if (!row.last_sync_date) {
			frappe.throw(__("Please set the Last Sync Date before syncing."));
			return;
		}

		frappe.call({
			method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.run_sync_job_background",
			args: {
				location: row.location,
				sync_date: row.last_sync_date,
			},
			callback: function (r) {
				if (!r.exc) {
					frappe.msgprint(r.message || __("Enqueued successfully."));
				} else {
					frappe.msgprint(__("Unexpected server error."));
				}
			},
		});
	},
});

frappe.ui.form.on("Biometric Serial Detail", {
	sync_log: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];

		if (!row.serial_no) {
			frappe.throw(__("Please enter a Serial No before syncing."));
			return;
		}
		if (!row.last_sync_datetime) {
			frappe.throw(__("Please set the Last Sync Datetime before syncing."));
			return;
		}

		frappe.call({
			method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.run_sync_job_background",
			args: {
				serial_no: row.serial_no,
				last_sync_datetime: row.last_sync_datetime,
			},
			callback: function (r) {
				if (!r.exc) {
					frappe.msgprint(r.message || __("Enqueued successfully."));
				} else {
					frappe.msgprint(__("Unexpected server error."));
				}
			},
		});
	},
});
