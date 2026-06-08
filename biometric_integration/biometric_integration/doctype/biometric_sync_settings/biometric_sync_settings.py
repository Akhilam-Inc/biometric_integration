# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today

class BiometricSyncSettings(Document):
	def validate(self):
		for idx, row in enumerate(self.biometric_location_detail, start=1):
			if not row.location:
				frappe.throw(
					msg=f"Please select a location in row {idx}.",
					title="Location Required"
				)

			if not row.last_sync_date:
				frappe.throw(
					msg=f"Please set a Last Sync Date for location <b>{row.location}</b>.",
					title="Last Sync Date Required"
				)


			if row.last_sync_date and getdate(row.last_sync_date) > getdate(today()):
				frappe.throw(
					msg=f"Last Sync Date for location <b>{row.location}</b> cannot be later than today's date.",
					title="Invalid Last Sync Date"
				)

		if self.server_type == "eTime Tracker Lite":
			if not self.last_sync_datetime:
				frappe.throw("Please set Last Sync DateTime for eTime Tracker Lite.")
			if not self.serial_no:
				frappe.throw("Please set Serial No for eTime Tracker Lite.")
