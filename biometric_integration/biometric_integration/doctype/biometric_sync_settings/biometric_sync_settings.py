# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class BiometricSyncSettings(Document):
	def validate(self):
		if self.server_type == "Bio Server":
			if not self.last_sync_date:
				frappe.throw("Please set Last Sync Date for Bio Server.")
			if not self.location:
				frappe.throw("Please set Location for Bio Server.")

		if self.server_type == "eTime Tracker Lite":
			if not self.last_sync_datetime:
				frappe.throw("Please set Last Sync DateTime for eTime Tracker Lite.")
			if not self.serial_no:
				frappe.throw("Please set Serial No for eTime Tracker Lite.")
