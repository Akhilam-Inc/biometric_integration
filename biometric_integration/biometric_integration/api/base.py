import textwrap
from datetime import date, datetime, time
from enum import Enum

import frappe
import requests
from frappe.utils import get_datetime


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
