# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class BiometricSyncSettings(Document):
	def validate(self):
		if self.server_type == "Bio Server":
			for idx, row in enumerate(self.biometric_location_detail, start=1):
				if not row.location:
					frappe.throw(
						msg=f"Row {idx}: Location is required.",
						title="Location Required",
					)
				if not row.last_sync_date:
					frappe.throw(
						msg=f"Row {idx}: Last Sync Date is required for location <b>{row.location}</b>.",
						title="Last Sync Date Required",
					)
				if getdate(row.last_sync_date) > getdate(today()):
					frappe.throw(
						msg=f"Row {idx}: Last Sync Date for <b>{row.location}</b> cannot be later than today.",
						title="Invalid Last Sync Date",
					)
		else:  # eTime Tracker Lite
			for idx, row in enumerate(self.biometric_serial_detail, start=1):
				if not row.serial_no:
					frappe.throw(
						msg=f"Row {idx}: Serial No is required.",
						title="Serial No Required",
					)
				if not row.last_sync_datetime:
					frappe.throw(
						msg=f"Row {idx}: Last Sync Datetime is required for serial <b>{row.serial_no}</b>.",
						title="Last Sync Datetime Required",
					)
