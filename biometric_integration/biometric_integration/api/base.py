import textwrap
from datetime import date, datetime, time
from enum import Enum

import frappe
import requests
from frappe.utils import get_datetime

_ZKTECO_ACCESS_KEY = "zkteco_access_token"
_ZKTECO_REFRESH_KEY = "zkteco_refresh_token"
# Cache TTLs — access token lives 5 min on the server; we evict at 4 min to
# avoid using a token that expires mid-request.  Refresh lives 24 h; we
# evict at ~23.6 h for the same reason.
_ACCESS_TTL = 240
_REFRESH_TTL = 85000


class SupportedHTTPMethod(Enum):
	GET = "GET"
	POST = "POST"


WEB_URI_BIO_SERVER = "/iclock/webservice.asmx"
WEB_URI_ETRACKER_LITE = "/iclock/WebAPIService.asmx"


class BiometricApiClient:
	"""
	SOAP API client for biometric device logs.
	Supports Bio Server (location + date) and eTime Tracker Lite (serial + datetime range).
	"""

	def __init__(self):
		self.settings = frappe.get_single("Biometric Sync Settings")
		self.base_url = (
			self.settings.endpoint_url.rstrip("/") + WEB_URI_BIO_SERVER
			if self.settings.server_type == "Bio Server"
			else self.settings.endpoint_url.rstrip("/") + WEB_URI_ETRACKER_LITE
		)
		self.username = self.settings.api_user
		self.password = self.settings.get_password("api_password")
		self.server_type = self.settings.server_type

		self.headers = (
			{"Content-Type": "text/xml; charset=utf-8"}
			if self.settings.server_type == "Bio Server"
			else {"Content-Type": "application/soap+xml"}
		)

	def get_device_logs(
		self,
		location=None,
		sync_date=None,
		serial_no=None,
		last_sync_datetime=None,
		to_datetime=None,
	):
		from biometric_integration.biometric_integration.api.utils import create_biometric_log

		"""Send SOAP request to fetch device logs for the given unit."""
		server_type = (self.settings.server_type or "").strip()

		if server_type == "Bio Server":
			try:
				if not location:
					frappe.log_error(title="Location is missing", message="Location is required")
					return {"status": "error", "message": "Location is required"}

				if not sync_date:
					frappe.log_error(title="Sync date is missing", message="Sync date is required")
					return {"status": "error", "message": "Sync date is required"}

				log_date = self._format_log_date(sync_date)
				body = self._build_soap_request(log_date, location)

				log = create_biometric_log(
					method=self.get_device_logs.__name__, request_data=body, make_new=True
				)
				frappe.flags.request_id = log.name

				response = requests.post(
					self.base_url,
					data=body,
					headers={**self.headers, **{"SOAPAction": "http://tempuri.org/GetDeviceLogs"}},
					timeout=30,
				)

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					# NOTE: do NOT clear frappe.flags.request_id here.
					# _write_sync_log in biometric_sync_log.py uses it after this
					# returns to stamp structured stats onto the log record.
					return {"status": "success", "data": response.text, "type": "Bio Server"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error",
						response_data=response.text,
						status="Error",
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}

			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}

		else:  # eTime Tracker Lite
			try:
				if not serial_no:
					frappe.log_error(title="Serial No missing", message="Serial No is required")
					return {"status": "error", "message": "Serial No is required"}

				if not last_sync_datetime:
					frappe.log_error(
						title="Last Sync Datetime missing", message="Last Sync Datetime is required"
					)
					return {"status": "error", "message": "Last Sync Datetime is required"}

				from_dt = self._format_for_etime_tracker(last_sync_datetime)
				end_dt = to_datetime if to_datetime else frappe.utils.now_datetime()
				to_dt = self._format_for_etime_tracker(end_dt)

				body = self._build_etime_server_envelope(
					from_dt, to_dt, serial_no, self.username, self.password
				)

				log = create_biometric_log(
					method=self.get_device_logs.__name__, request_data=body, make_new=True
				)
				frappe.flags.request_id = log.name

				response = requests.post(
					self.base_url,
					data=body,
					headers={**self.headers, **{"SOAPAction": "http://tempuri.org/GetTransactionsLog"}},
					timeout=30,
				)

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					# NOTE: do NOT clear frappe.flags.request_id here.
					# _write_sync_log in biometric_sync_log.py uses it after this
					# returns to stamp structured stats onto the log record.
					return {"status": "success", "data": response.text, "type": "eTime Tracker Lite"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error",
						response_data=response.text,
						status="Error",
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}

			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}

	def _build_soap_request(self, log_date, location):
		"""Construct Bio Server SOAP XML body."""
		return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetDeviceLogs xmlns="http://tempuri.org/">
      <UserName>{self.username}</UserName>
      <Password>{self.password}</Password>
      <Location>{location}</Location>
      <LogDate>{log_date}</LogDate>
    </GetDeviceLogs>
  </soap:Body>
</soap:Envelope>"""

	def _format_log_date(self, date_input) -> str:
		"""Convert various date formats to 'YYYY/MM/DD'."""
		if isinstance(date_input, str):
			try:
				date_obj = datetime.strptime(date_input, "%Y-%m-%d")
			except ValueError:
				date_obj = datetime.strptime(date_input, "%Y/%m/%d")
		elif isinstance(date_input, datetime):
			date_obj = date_input
		else:
			raise ValueError("Unsupported date format")
		return date_obj.strftime("%Y/%m/%d")

	def _coerce_to_datetime(self, val) -> datetime:
		"""
		Accepts str | date | datetime | None.
		Returns a naive datetime with no timezone conversions.
		"""
		if val is None:
			return get_datetime().replace(tzinfo=None)

		if isinstance(val, datetime):
			return val.replace(tzinfo=None)

		if isinstance(val, date):
			return datetime.combine(val, time.min)

		if isinstance(val, str):
			s = val.strip()
			for fmt in (
				"%d-%m-%Y %H:%M:%S",
				"%Y-%m-%d %H:%M:%S",
				"%d/%m/%Y %H:%M:%S",
				"%Y/%m/%d %H:%M:%S",
			):
				try:
					return datetime.strptime(s, fmt)
				except ValueError:
					pass
			for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
				try:
					d = datetime.strptime(s, fmt).date()
					return datetime.combine(d, time.min)
				except ValueError:
					pass
			return get_datetime(s).replace(tzinfo=None)

		return get_datetime(str(val)).replace(tzinfo=None)

	def _format_for_etime_tracker(self, dt) -> str:
		"""Format datetime as YYYY/MM/DD HH:MM:SS for eTime Tracker Lite API."""
		dt = self._coerce_to_datetime(dt)
		return dt.strftime("%Y/%m/%d %H:%M:%S")

	def _build_etime_server_envelope(
		self, from_dt: str, to_dt: str, serial: str, username: str, password: str
	) -> str:
		xml_decl = '<?xml version="1.0" encoding="utf-8"?>'
		body = textwrap.dedent(f"""\
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <soap:Body>
            <GetTransactionsLog xmlns="http://tempuri.org/">
            <FromDateTime>{from_dt}</FromDateTime>
            <ToDateTime>{to_dt}</ToDateTime>
            <SerialNumber>{serial}</SerialNumber>
            <UserName>{username}</UserName>
            <UserPassword>{password}</UserPassword>
            <strDataList></strDataList>
            </GetTransactionsLog>
        </soap:Body>
        </soap:Envelope>""")

		body = body.lstrip()
		xml = xml_decl + body
		xml = xml.replace("﻿", "")
		return xml


class ZKTecoApiClient:
	"""
	REST/JSON API client for ZKTeco BioTime server.

	Auth: JWT tokens via /jwt-api-token-auth/ (access=5 min, refresh=24 h).
	Tokens are cached in Redis (frappe.cache) so background jobs share them
	and avoid redundant auth calls.  The fetch loop re-requests a token per
	page so an expiry mid-pagination is handled transparently.
	"""

	def __init__(self) -> None:
		self.settings = frappe.get_single("Biometric Sync Settings")
		self.base_url = self.settings.endpoint_url.rstrip("/")
		self.username = self.settings.api_user
		self.password = self.settings.get_password("api_password")

	# ------------------------------------------------------------------
	# Token management
	# ------------------------------------------------------------------

	def _get_access_token(self) -> str:
		"""Return a valid access token: Redis cache → settings field → refresh → full re-auth."""
		token = frappe.cache().get_value(_ZKTECO_ACCESS_KEY)
		if token:
			return token

		# Warm cache from the token saved on the settings doc (survives worker restarts).
		stored = self.settings.get_password("zkteco_auth_token")
		if stored:
			frappe.cache().set_value(_ZKTECO_ACCESS_KEY, stored, expires_in_sec=_ACCESS_TTL)
			return stored

		refresh = frappe.cache().get_value(_ZKTECO_REFRESH_KEY)
		if refresh:
			return self._do_refresh(refresh)

		return self._do_auth()

	def _do_auth(self) -> str:
		"""Full credential auth.  Caches both access and refresh tokens."""
		response = requests.post(
			f"{self.base_url}/jwt-api-token-auth/",
			json={"username": self.username, "password": self.password},
			timeout=30,
		)
		response.raise_for_status()
		data = response.json()

		access = data["access"]
		refresh = data.get("refresh", "")

		frappe.cache().set_value(_ZKTECO_ACCESS_KEY, access, expires_in_sec=_ACCESS_TTL)
		if refresh:
			frappe.cache().set_value(_ZKTECO_REFRESH_KEY, refresh, expires_in_sec=_REFRESH_TTL)

		self._persist_token(access)
		return access

	def _do_refresh(self, refresh_token: str) -> str:
		"""Exchange a refresh token for a new access token."""
		try:
			response = requests.post(
				f"{self.base_url}/jwt-api-token-refresh/",
				json={"refresh": refresh_token},
				timeout=30,
			)
			response.raise_for_status()
			access = response.json()["access"]
			frappe.cache().set_value(_ZKTECO_ACCESS_KEY, access, expires_in_sec=_ACCESS_TTL)
			self._persist_token(access)
			return access
		except Exception:
			# Refresh token may have expired — fall back to full re-auth
			frappe.cache().delete_value(_ZKTECO_REFRESH_KEY)
			return self._do_auth()

	def _persist_token(self, access: str) -> None:
		"""Write the latest access token back to Biometric Sync Settings so it
		survives worker restarts and Redis flushes."""
		frappe.db.set_value(
			"Biometric Sync Settings",
			"Biometric Sync Settings",
			"zkteco_auth_token",
			access,
			update_modified=False,
		)
		frappe.db.commit()

	def _auth_header(self) -> dict:
		return {"Authorization": f"JWT {self._get_access_token()}"}

	# ------------------------------------------------------------------
	# Transactions
	# ------------------------------------------------------------------

	def get_transactions(
		self,
		start_dt: str,
		end_dt: str,
		terminal_sn: str | None = None,
		page_size: int = 1000,
	) -> list:
		"""
		Fetch all attendance transactions in the given datetime window.

		Paginates through every page (following `next` until null).
		Re-acquires a token per page so a 5-min expiry mid-loop is handled
		transparently via the Redis cache layer.

		On a 401 response the cached access token is cleared and the request
		is retried once with a freshly issued token.

		Args:
			start_dt:    ISO-like string "YYYY-MM-DD HH:MM:SS"
			end_dt:      ISO-like string "YYYY-MM-DD HH:MM:SS"
			terminal_sn: device serial number to filter by (optional)
			page_size:   records per page (default 1000, max tested = 1000)

		Returns:
			Flat list of transaction dicts from the API.
		"""
		from biometric_integration.biometric_integration.api.utils import create_biometric_log

		initial_params = {
			"start_time": start_dt,
			"end_time": end_dt,
			"page_size": page_size,
			"page": 1,
		}
		if terminal_sn:
			initial_params["terminal_sn"] = terminal_sn

		log = create_biometric_log(
			method="ZKTecoApiClient.get_transactions",
			request_data=initial_params,
			make_new=True,
		)
		frappe.flags.request_id = log.name

		all_records: list = []
		pages_fetched = 0
		# First page uses constructed params; subsequent pages follow the `next` URL
		# returned by the API so we never drift out of sync with server-side pagination.
		next_url: str | None = f"{self.base_url}/iclock/api/transactions/"
		next_params: dict | None = initial_params

		try:
			while next_url:
				response = self._request_with_retry(next_url, next_params)
				data = response.json()

				records = data.get("data") or []
				all_records.extend(records)
				pages_fetched += 1

				# Follow the server-provided `next` URL directly; no manual page math.
				next_url = data.get("next")
				next_params = None  # next URL already contains all query params

			# Store the full transaction list so retry_checkin_creation can re-process
			# without hitting the device again (same pattern as SOAP response storage).
			create_biometric_log(
				message=f"Fetched {len(all_records)} transactions ({pages_fetched} page(s))",
				response_data=all_records,
				status="Success",
			)
			return all_records

		except Exception as e:
			create_biometric_log(
				message="ZKTeco Transaction Fetch Error",
				exception=e,
				status="Error",
			)
			frappe.flags.request_id = None
			frappe.log_error(title="ZKTeco API Error", message=frappe.get_traceback())
			raise

	def _request_with_retry(self, url: str, params: dict | None = None) -> requests.Response:
		"""GET a transactions URL with one automatic retry on 401."""
		response = requests.get(url, headers=self._auth_header(), params=params, timeout=60)

		if response.status_code == 401:
			# Access token expired between cache write and this request — clear and retry once
			frappe.cache().delete_value(_ZKTECO_ACCESS_KEY)
			response = requests.get(url, headers=self._auth_header(), params=params, timeout=60)

		response.raise_for_status()
		return response
