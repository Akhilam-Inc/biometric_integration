import textwrap
from datetime import date, datetime, time
from enum import Enum

import frappe
import requests
from frappe.utils import get_datetime
from types import SimpleNamespace


class SupportedHTTPMethod(Enum):
	GET = "GET"
	POST = "POST"


WEB_URI_BIO_SERVER = "/iclock/webservice.asmx"
WEB_URI_ETRACKER_LITE = "/iclock/WebAPIService.asmx"


class BiometricApiClient:
	"""
	SOAP API client for biometric device logs
	"""

	def __init__(self):
		self.settings = frappe.get_single("Biometric Sync Settings")  # Define this DocType
		self.base_url = (
			(self.settings.endpoint_url.rstrip("/") + WEB_URI_BIO_SERVER)
			if self.settings.server_type == "Bio Server"
			else (self.settings.endpoint_url.rstrip("/") + WEB_URI_ETRACKER_LITE)
		)
		self.username = self.settings.api_user
		self.password = self.settings.get_password("api_password")
		# For eTime Tracker Lite
		self.server_type = self.settings.server_type
		self.last_sync_datetime = self.settings.last_sync_datetime
		self.serial_no = self.settings.serial_no
		self.missing_date = self.settings.missing_date

		self.headers = (
			{
				"Content-Type": "text/xml; charset=utf-8",
			}
			if self.settings.server_type == "Bio Server"
			else {
				"Content-Type": "application/soap+xml",
			}
		)

	def get_device_logs(self, location = None, last_sync_date = None):
		from biometric_integration.biometric_integration.api.utils import create_biometric_log

		"""Send SOAP request to get device logs for a given date (YYYY-MM-DD or YYYY/MM/DD)"""
		server_type = (self.settings.server_type or "").strip()
		if server_type == "Bio Server":
			try:
				if not location:
					frappe.log_error(title="Location is missing", message=f"Location is required")
					return {"status": "error", "message": f"Location is required"}

				if not last_sync_date:
					frappe.log_error(title="Last sync date is missing", message=f"Last sync date is required")
					return {"status": "error", "message": f"Last sync date is required"}

				log_date = self._format_log_date(last_sync_date)
				body = self._build_soap_request(log_date, location)

				log = create_biometric_log(
					method=self.get_device_logs.__name__, request_data=body, make_new=True
				)
				frappe.flags.request_id = log.name
				# response = requests.post(
				# 	self.base_url,
				# 	data=body,
				# 	headers={**self.headers, **{"SOAPAction": "http://tempuri.org/GetDeviceLogs"}},
				# 	timeout=30,
				# )

				# suceess
				response = SimpleNamespace(
					status_code=200,
					text=f"{location} - {log_date}"
				)

				# failure
				# response = SimpleNamespace(
				# 	status_code=400,
				# 	text=f"fail - {location} - {log_date}"
				# )

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "Bio Server"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}
		else:
			try:
				log_date = self._format_for_etime_tracker(self.last_sync_datetime)
				body = self._build_etime_server_envelope(
					log_date, frappe.utils.now_datetime(), self.serial_no, self.username, self.password
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
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "eTime Tracker Lite"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}

	def retry_get_device_logs(self, payload, request_id):
		from biometric_integration.biometric_integration.api.utils import create_biometric_log

		"""Send SOAP request to get device logs for a given date (YYYY-MM-DD or YYYY/MM/DD)"""
		if "GetTransactionsLog" not in payload:
			try:
				frappe.flags.request_id = request_id
				# response = requests.post(
				# 	self.base_url,
				# 	data=payload,
				# 	headers={**self.headers, **{"SOAPAction": "http://tempuri.org/DeviceLogs"}},
				# 	timeout=30,
				# )
				response = SimpleNamespace(
					status_code=200,
					text=f"retry job called"
				)

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "Bio Server"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}
		else:
			try:
				frappe.flags.request_id = request_id
				response = requests.post(
					self.base_url,
					data=payload,
					headers={**self.headers, **{"SOAPAction": "http://tempuri.org/GetTransactionsLog"}},
					timeout=30,
				)

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "eTime Tracker Lite"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}

	def get_device_logs_for_date(self, location = None, missing_date = None):
		from biometric_integration.biometric_integration.api.utils import create_biometric_log

		"""Send SOAP request to get device logs for a given date (YYYY-MM-DD or YYYY/MM/DD)"""
		server_type = (self.settings.server_type or "").strip()
		if server_type == "Bio Server":
			try:
				log_date = self._format_log_date(missing_date)
				body = self._build_soap_request(log_date, location)

				log = create_biometric_log(
					method=self.get_device_logs_for_date.__name__, request_data=body, make_new=True
				)
				frappe.flags.request_id = log.name
				# response = requests.post(
				# 	self.base_url,
				# 	data=body,
				# 	headers={**self.headers, **{"SOAPAction": "http://tempuri.org/GetDeviceLogs"}},
				# 	timeout=30,
				# )

				# suceess
				# response = SimpleNamespace(
				# 	status_code=200,
				# 	text=f"{location} - {log_date}"
				# )

				# failure
				response = SimpleNamespace(
					status_code=400,
					text=f"fail - {location} - {log_date}"
				)

				if response.status_code == 200:
					create_biometric_log(
						message="Device Log Fetched Successfully",
						response_data=response.text,
						status="Success",
					)
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "Bio Server"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}
		else:
			try:
				log_date = self._format_for_etime_tracker(self.missing_date)
				end_date = get_datetime(self.missing_date).replace(hour=23, minute=59, second=59)
				log_end_date = self._format_for_etime_tracker(end_date)
				body = self._build_etime_server_envelope(
					log_date, log_end_date, self.serial_no, self.username, self.password
				)

				log = create_biometric_log(
					method=self.get_device_logs_for_date.__name__, request_data=body, make_new=True
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
					frappe.flags.request_id = None
					return {"status": "success", "data": response.text, "type": "eTime Tracker Lite"}
				else:
					create_biometric_log(
						message="Device Log Fetch Error", response_data=response.text, status="Error"
					)
					frappe.flags.request_id = None
					return {"status": "error", "message": f"HTTP {response.status_code}: {response.text}"}
			except Exception as e:
				create_biometric_log(message="Device Log Fetch Error", exception=e, status="Error")
				frappe.flags.request_id = None
				frappe.log_error(title="Biometric API Error", message=frappe.get_traceback(e))
				return {"status": "error", "message": str(e)}

	def _build_soap_request(self, log_date, location):
		"""Construct SOAP XML body"""
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
		"""Convert various date formats to 'YYYY/MM/DD'"""
		if isinstance(date_input, str):
			# Parse string to date if necessary
			try:
				date_obj = datetime.strptime(date_input, "%Y-%m-%d")
			except ValueError:
				date_obj = datetime.strptime(date_input, "%Y/%m/%d")  # fallback
		elif isinstance(date_input, datetime):
			date_obj = date_input
		else:
			raise ValueError("Unsupported date format")

		return date_obj.strftime("%Y/%m/%d")

	def _coerce_to_datetime(self, val) -> datetime:
		"""
		Accepts str | date | datetime | None.
		Returns a *naive* datetime with no timezone conversions.
		Prefers explicit DD-MM-YYYY parsing if present.
		"""
		if val is None:
			# choose sane default; keep naive local "now"
			dt = get_datetime()
			return dt.replace(tzinfo=None)

		if isinstance(val, datetime):
			return val.replace(tzinfo=None)

		if isinstance(val, date):
			return datetime.combine(val, time.min)

		if isinstance(val, str):
			s = val.strip()
			# Try common explicit formats first (NO TZ):
			for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
				try:
					return datetime.strptime(s, fmt)
				except ValueError:
					pass
			# Date-only variants:
			for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
				try:
					d = datetime.strptime(s, fmt).date()
					return datetime.combine(d, time.min)
				except ValueError:
					pass
			# Last resort: let frappe parse, then strip tz to keep LOCAL WALL TIME
			return get_datetime(s).replace(tzinfo=None)

		# Anything else: stringify then best-effort parse, strip tz
		return get_datetime(str(val)).replace(tzinfo=None)

	def _format_for_etime_tracker(self, dt: datetime) -> str:
		# Bio server expects YYYY/MM/DD HH:MM:SS (slashes)
		dt = self._coerce_to_datetime(dt)
		return dt.strftime("%Y/%m/%d %H:%M:%S")

	def _build_etime_server_envelope(
		self, from_dt: datetime, to_dt: datetime, serial: str, username: str, password: str
	) -> str:
		xml_decl = '<?xml version="1.0" encoding="utf-8"?>'
		body = textwrap.dedent(f"""\
        <soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
                    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/2001/XMLSchema">
        <soap:Body>
            <GetTransactionsLog xmlns="http://tempuri.org/">
            <FromDateTime>{from_dt}</FromDateTime>
            <ToDateTime>{self._format_for_etime_tracker(to_dt)}</ToDateTime>
            <SerialNumber>{serial}</SerialNumber>
            <UserName>{username}</UserName>
            <UserPassword>{password}</UserPassword>
            <strDataList></strDataList>
            </GetTransactionsLog>
        </soap:Body>
        </soap:Envelope>""")

		# Remove any accidental BOM/leading whitespace before xml decl
		body = body.lstrip()  # removes \n/space before <soap:Envelope> (fine)
		xml = xml_decl + body  # ensures <?xml?> is the very first bytes
		xml = xml.replace("\ufeff", "")  # strip BOM if somehow present in string
		return xml
