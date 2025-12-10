from datetime import datetime
from enum import Enum

import frappe
import requests
from biometric_integration.api.utils import create_biometric_log


class SupportedHTTPMethod(Enum):
    GET = "GET"
    POST = "POST"

class BiometricApiClient:
    """
    SOAP API client for biometric device logs
    """

    def __init__(self):
        self.settings = frappe.get_single("Biometric Sync Settings")  # Define this DocType
        self.base_url = self.settings.base_url.rstrip("/") + "/iclock/webservice.asmx"
        self.username = self.settings.api_user
        self.password = self.settings.get_password("api_password")
        self.location = self.settings.location or "Default"
        self.last_sync_date = self.settings.last_sync_date

        self.headers = {
            "Content-Type": "text/xml; charset=utf-8",
        }

    def get_device_logs(self):
        """Send SOAP request to get device logs for a given date (YYYY-MM-DD or YYYY/MM/DD)"""
        try:
            log_date = self._format_log_date(self.last_sync_date)
            body = self._build_soap_request(log_date)

            log = create_biometric_log(
                method=self.get_device_logs.__name__, request_data=body, make_new=True
            )
            frappe.flags.request_id = log.name
            response = requests.post(self.base_url, data=body, headers={**self.headers , **{"SOAPAction": "\"http://tempuri.org/GetDeviceLogs\""}}, timeout=30)

            if response.status_code == 200:
                create_biometric_log(message = "Device Log Fetched Successfully" ,response_data = response.text, status = "Success")
                frappe.flags.request_id = None
                return {
                    "status": "success",
                    "data": response.text
                }
            else:
                create_biometric_log(message = "Device Log Fetch Error" ,response_data = response.text, status = "Error")
                frappe.flags.request_id = None
                return {
                    "status": "error",
                    "message": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            create_biometric_log(message = "Device Log Fetch Error" ,exception=e, status = "Error")
            frappe.flags.request_id = None
            frappe.log_error(str(e), "Biometric API Error")
            return {
                "status": "error",
                "message": str(e)
            }
        else:
            pass

    def _build_soap_request(self, log_date):
        """Construct SOAP XML body"""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <GetDeviceLogs xmlns="http://tempuri.org/">
      <UserName>{self.username}</UserName>
      <Password>{self.password}</Password>
      <Location>{self.location}</Location>
      <LogDate>{log_date}</LogDate>
    </GetDeviceLogs>
  </soap:Body>
</soap:Envelope>"""

    def _format_log_date(self, date_input) -> str:
        """
        Convert various date formats to 'YYYY/MM/DD'
        """
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
