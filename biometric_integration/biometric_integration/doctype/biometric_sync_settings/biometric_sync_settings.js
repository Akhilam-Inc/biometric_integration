// Copyright (c) 2025, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Biometric Sync Settings", {
	refresh(frm) {
		frappe.realtime.on("biometric_sync_update", function (data) {
			frm.reload_doc();
		});
		get_missing_date_data(frm);
	},
	sync_logs_for_missing_date: function (frm) {
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
	server_type: function (frm) {
		get_missing_date_data(frm);
	},
});

function get_missing_date_data(frm) {

	if (frm.doc.server_type != "Bio Server") {
		frm.remove_custom_button('Get Missing Data');
		return
	}
	frm.add_custom_button(__("Get Missing Data"), () => {
		let locations = frm.doc.biometric_location_detail.map(
			row => row.location
		);

		let d = new frappe.ui.Dialog({
			title: __("Fetch Missing Logs"),
			fields: [
				{
					fieldname: "location",
					label: __("Location"),
					fieldtype: "Select",
					options: locations.join("\n"),
					reqd: 1,
				},
				{
					fieldname: "missing_date",
					label: __("Missing Date"),
					fieldtype: "Date",
					reqd: 1
				}
			],
			primary_action_label: __("Submit"),
			primary_action(values) {
				const today = frappe.datetime.get_today();

				if (values.missing_date > today) {
					frappe.msgprint({
						title: __("Invalid Date"),
						message: __("The selected Missing Date cannot be later than today. Please choose a valid date."),
						indicator: "red"
					});
					return;
				}

				frappe.call({
					method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.fetch_device_logs_for_missing_date_background",
					args: {
						location: values.location,
						missing_date: values.missing_date,
					},
					callback: function (r) {
						d.hide();
						if (!r.exc) {
							if (r.message) {
								frappe.msgprint(r.message);
							} else {
								frappe.msgprint("Error: " + r.message.message);
							}
						} else {
							frappe.msgprint("Unexpected server error.");
						}
					}
				});
			}
		});

		d.show();
	}).css({
		"background-color": "#000",
		"color": "#fff",
		"border-color": "#000"
	});
}

frappe.ui.form.on("Biometric Location Detail", {
	sync_log: function (frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		location_name = row.location;
		last_sync_date = row.last_sync_date;
		if (!location_name) {
			frappe.throw("Please select a location to sync.");
			return;
		}
		if (!last_sync_date) {
			frappe.throw("Please select the last sync date to sync.");
			return;
		}
		frappe.call({
			method: "biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log.fetch_device_logs_background",
			args: {
				location: location_name,
				last_sync_date: last_sync_date
			},
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
