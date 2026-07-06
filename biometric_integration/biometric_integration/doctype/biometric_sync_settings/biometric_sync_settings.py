# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import frappe
import requests
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
		elif self.server_type == "eTime Tracker Lite":
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
		elif self.server_type == "ZKTeco":
			self._authenticate_zkteco()
			for idx, row in enumerate(self.biometric_zkteco_device, start=1):
				if not row.terminal_sn:
					frappe.throw(
						msg=f"Row {idx}: Terminal Serial No is required.",
						title="Terminal Serial No Required",
					)
				if not row.last_sync_datetime:
					frappe.throw(
						msg=f"Row {idx}: Last Sync Datetime is required for terminal <b>{row.terminal_sn}</b>.",
						title="Last Sync Datetime Required",
					)
				if getdate(row.last_sync_datetime) > getdate(today()):
					frappe.throw(
						msg=f"Row {idx}: Last Sync Datetime for <b>{row.terminal_sn}</b> cannot be later than today.",
						title="Invalid Last Sync Datetime",
					)

	def _authenticate_zkteco(self) -> None:
		"""Call ZKTeco login API and persist the access token on the settings doc."""
		base_url = (self.endpoint_url or "").rstrip("/")
		username = self.api_user
		password = self.get_password("api_password")

		if not base_url or not username or not password:
			frappe.throw(
				msg="Endpoint URL, Api User and Api Password are required for ZKTeco authentication.",
				title="ZKTeco Auth Failed",
			)

		try:
			response = requests.post(
				f"{base_url}/jwt-api-token-auth/",
				json={"username": username, "password": password},
				timeout=30,
			)
			response.raise_for_status()
		except requests.exceptions.RequestException as e:
			frappe.throw(
				msg=f"ZKTeco login failed: {e}",
				title="ZKTeco Auth Failed",
			)

		data = response.json()
		access = data.get("access")
		if not access:
			frappe.throw(
				msg="ZKTeco login response did not contain an access token.",
				title="ZKTeco Auth Failed",
			)

		self.zkteco_auth_token = access

		refresh = data.get("refresh", "")
		if refresh:
			# Persisted (not just cached) so a Redis flush/worker restart can still
			# refresh instead of forcing a full re-auth.
			self.zkteco_refresh_token = refresh

		# Also warm the Redis cache so the first sync doesn't need to re-auth.
		from biometric_integration.biometric_integration.api.base import (
			_ACCESS_TTL,
			_REFRESH_TTL,
			_ZKTECO_ACCESS_KEY,
			_ZKTECO_REFRESH_KEY,
		)
		frappe.cache().set_value(_ZKTECO_ACCESS_KEY, access, expires_in_sec=_ACCESS_TTL)
		if refresh:
			frappe.cache().set_value(_ZKTECO_REFRESH_KEY, refresh, expires_in_sec=_REFRESH_TTL)
