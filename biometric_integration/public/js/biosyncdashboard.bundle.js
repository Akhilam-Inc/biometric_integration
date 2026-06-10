import { createApp } from 'vue';
import BiometricSyncDashboard from './BiometricSyncDashboard.vue';

class BiometricSyncDashboardUI {
	constructor({ wrapper, page }) {
		this.$wrapper = $(wrapper);
		this.page = page;
		this.app = null;
		this.init();
	}

	init() {
		this.app = createApp(BiometricSyncDashboard, {
			page: this.page,
		});
		this.app.mount(this.$wrapper.get(0));
	}

	destroy() {
		if (this.app) {
			this.app.unmount();
			this.app = null;
		}
	}
}

frappe.provide('biosyncdashboard.ui');
biosyncdashboard.ui.BiometricSyncDashboardUI = BiometricSyncDashboardUI;

export default BiometricSyncDashboardUI;
