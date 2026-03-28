# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
import requests
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

		if self.server_type == "ZKTeco":
			if not self.zkteco_last_sync_datetime:
				frappe.throw("Please set ZKTeco Last Sync Datetime for ZKTeco.")
			if not frappe.flags.get("skip_zkteco_token_refresh"):
				self._fetch_and_save_zkteco_token()

	def _fetch_and_save_zkteco_token(self):
		try:
			url = self.endpoint_url.rstrip("/") + "/jwt-api-token-auth/"
			response = requests.post(
				url,
				json={"username": self.api_user, "password": self.get_password("api_password")},
				headers={"Content-Type": "application/json"},
				timeout=30,
			)
			if response.status_code == 200:
				token = response.json().get("token")
				if token:
					self.zkteco_token = token
				else:
					frappe.throw("ZKTeco authentication failed: No token received in response.")
			else:
				frappe.throw(
					f"ZKTeco authentication failed: HTTP {response.status_code} - {response.text}"
				)
		except frappe.exceptions.ValidationError:
			raise
		except Exception as e:
			frappe.throw(f"ZKTeco authentication error: {str(e)}")
