# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now
from frappe.utils import strip_html
from frappe.utils.data import cstr
from biometric_integration.biometric_integration.api.base import BiometricApiClient
import xml.etree.ElementTree as ET
from frappe.utils import get_datetime


class BiometricSyncLog(Document):
	def validate(self):
		self._set_title()

	def _set_title(self):
		title = None
		if self.message != "None":
			title = self.message

		if not title and self.method:
			method = self.method.split(".")[-1]
			title = method

		if title:
			title = strip_html(title)
			self.title = title if len(title) < 100 else title[:100] + "..."

	@staticmethod
	def clear_old_logs(days=90):
		table = frappe.qb.DocType("Biometric Sync Log")
		frappe.db.delete(
			table, filters=((table.modified < (Now() - Interval(days=days)))) & (table.status == "Success")
		)


def create_log(
	module_def="Biometric Integration",
	status="Queued",
	response_data=None,
	request_data=None,
	exception=None,
	rollback=False,
	method=None,
	message=None,
	make_new=False,
):
	make_new = make_new or not bool(frappe.flags.request_id)

	if rollback:
		frappe.db.rollback()

	if make_new:
		log = frappe.get_doc({"doctype": "Biometric Sync Log", "integration": cstr(module_def)})
		log.insert(ignore_permissions=True)
	else:
		log = frappe.get_doc("Biometric Sync Log", frappe.flags.request_id)

	if response_data and not isinstance(response_data, str):
		response_data = json.dumps(response_data, sort_keys=True, indent=4)

	if request_data and not isinstance(request_data, str):
		request_data = json.dumps(request_data, sort_keys=True, indent=4)

	log.message = message or _get_message(exception)
	log.method = log.method or method
	log.response_data = response_data or log.response_data
	log.request_data = request_data or log.request_data
	log.traceback = log.traceback or frappe.get_traceback()
	log.status = status
	log.save(ignore_permissions=True)

	frappe.db.commit()

	return log


def _get_message(exception):
	if hasattr(exception, "message"):
		return strip_html(exception.message)
	elif hasattr(exception, "__str__"):
		return strip_html(exception.__str__())
	else:
		return _("Something went wrong while syncing")


@frappe.whitelist()
def resync(method, name, request_data):
	_retry_job(name)


def _retry_job(job: str):
	frappe.only_for("System Manager")

	doc = frappe.get_doc("Biometric Sync Log", job)
	if doc.status != "Error":
		return

	doc.db_set("status", "Queued", update_modified=False)
	doc.db_set("traceback", "", update_modified=False)

	frappe.enqueue(
		method=retry_logs,
		queue="short",
		timeout=300,
		is_async=True,
		payload=doc.request_data,
		request_id=doc.name,
		enqueue_after_commit=True,
	)


@frappe.whitelist()
def bulk_retry(names):
	if isinstance(names, str):
		names = json.loads(names)
	for name in names:
		_retry_job(name)


@frappe.whitelist()
def fetch_device_logs_background():
	"""Call this from JS to enqueue a background job."""
	frappe.enqueue(
		method=fetch_and_log_device_logs,
		queue="short",
		timeout=300,
		is_async= True
	)
	return "Enqueued. Please check Biometric Sync Log for status."


def fetch_and_log_device_logs():
	"""Actual background job that fetches and logs biometric data."""
	client = BiometricApiClient()
	logs_data = client.get_device_logs()
	if logs_data["status"] == "success":
		process_device_logs(logs_data["data"])
		sync_settings = frappe.get_single("Biometric Sync Settings")
		current_sync_date = frappe.utils.getdate(sync_settings.last_sync_date)
		next_sync_date = frappe.utils.add_days(current_sync_date, 1)
		sync_settings.last_sync_date = next_sync_date
		sync_settings.save(ignore_permissions=True)
		

def retry_logs(payload , request_id):
	client = BiometricApiClient()
	logs_data = client.retry_get_device_logs(payload , request_id)
	if logs_data["status"] == "success":
		process_device_logs(logs_data["data"])

def process_device_logs(response_text):
	ns = {
		"soap": "http://schemas.xmlsoap.org/soap/envelope/",
		"ns1": "http://tempuri.org/"
	}

	root = ET.fromstring(response_text)
	result_tag = root.find(".//ns1:GetDeviceLogsResult", ns)
	result = None
	
	if result_tag is not None and result_tag.text:
		result = result_tag.text.strip()
	
	if not result:
		frappe.log_error(title = "No logs found in the response." , message=result_tag)
		frappe.throw("No logs found in the response.")

	logs = result.split(";\n")
	
	created = 0
	for line in logs:
		if not line.strip():
			continue
		
		try:
			parts = line.split(",")
			log_time_str = parts[0].strip()
			device_id = parts[1].strip()
			location = parts[3].strip()

			# Step 1: Convert time
			log_time = get_datetime(log_time_str)

			# Step 2: Find Employee
			employee = frappe.db.get_value("Employee", {"attendance_device_id": device_id})
			if not employee:
				frappe.logger().info(f"No employee found for device_id: {device_id}")
				continue

			# Step 3: Avoid duplicate check-ins
			exists = frappe.db.exists(
				"Employee Checkin",
				{
					"employee": employee,
					"time": log_time,
				},
			)
			if exists:
				continue

			# Step 4: Insert Employee Checkin
			frappe.get_doc({
				"doctype": "Employee Checkin",
				"employee": employee,
				"time": log_time,
				"device_id": location,
				"log_type": "IN"
			}).insert(ignore_permissions=True)
			created += 1
		except Exception as e:
			frappe.log_error(title= "Employee Checkin" , message=f"Error processing line: {line}\n{frappe.get_traceback()}")

	return f"{created} Employee Checkin(s) created."

@frappe.whitelist(allow_guest=True)
def attendance_log():
	import json
	from frappe.utils.response import build_response

	# Only allow POST
	if frappe.request.method != "POST":
		frappe.local.response.http_status_code = 405
		return {"error": "Method Not Allowed"}

	try:
		# Try to parse JSON payload
		data = frappe.request.get_json()

		# You can log it, process it, or store it
		frappe.log_error(title = "Employee Checkin Data" ,message=f"Received Webhook: {json.dumps(data, indent=4)}")
		created = 0

		for entry in data:
			device_id = entry.get("EmployeeCode")
			log_time_str = entry.get("LogDate")
			location = entry.get("DeviceName") or entry.get("SerialNumber")

			# Step 1: Convert time
			log_time = get_datetime(log_time_str)

			# Step 2: Find Employee
			employee = frappe.db.get_value("Employee", {"attendance_device_id": device_id})
			if not employee:
				frappe.logger().info(f"No employee found for device_id: {device_id}")
				continue

			# Step 3: Avoid duplicate check-ins
			exists = frappe.db.exists(
				"Employee Checkin",
				{
					"employee": employee,
					"time": log_time,
				},
			)
			if exists:
				continue

			# Step 4: Insert Employee Checkin
			frappe.get_doc({
				"doctype": "Employee Checkin",
				"employee": employee,
				"time": log_time,
				"device_id": location,
				"log_type": "IN",  # optionally use entry.get("DeviceDirection") or similar if needed
			}).insert(ignore_permissions=True)
			
			created += 1
		return "success"
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Webhook Handler Error")
		frappe.local.response.http_status_code = 500
		return {"status": "error", "message": str(e)}