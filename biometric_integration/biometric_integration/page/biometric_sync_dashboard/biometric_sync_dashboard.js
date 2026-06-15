// Copyright (c) 2026, Akhilam Inc. and contributors
// For license information, please see license.txt

frappe.pages["biometric-sync-dashboard"].on_page_load = function (wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: "Biometric Sync Dashboard",
		single_column: true,
	});
};

frappe.pages["biometric-sync-dashboard"].on_page_show = function (wrapper) {
	load_biometric_dashboard(wrapper);
};

function load_biometric_dashboard(wrapper) {
	let $parent = $(wrapper).find(".layout-main-section");
	$parent.empty();

	frappe.require("biosyncdashboard.bundle.js").then(() => {
		new biosyncdashboard.ui.BiometricSyncDashboardUI({
			wrapper: $parent,
			page: wrapper.page,
		});
	});
}
