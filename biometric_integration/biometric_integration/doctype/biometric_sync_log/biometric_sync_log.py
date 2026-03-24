# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import json
import xml.etree.ElementTree as ET

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now
from frappe.utils import get_datetime, strip_html
from frappe.utils.data import cstr

from biometric_integration.biometric_integration.api.base import BiometricApiClient


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
			table, filters=(table.modified < (Now() - Interval(days=days))) & (table.status == "Success")
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
		timeout=3500,
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
	frappe.enqueue(method=fetch_and_log_device_logs, queue="short", timeout=3500, is_async=True)
	return "Enqueued. Please check Biometric Sync Log for status."


@frappe.whitelist()
def fetch_device_logs_for_missing_date_background():
	"""Call this from JS to enqueue a background job."""
	frappe.enqueue(
		method=fetch_and_log_device_logs_for_missing_date, queue="short", timeout=3500, is_async=True
	)
	return "Enqueued. Please check Biometric Sync Log for status."


def fetch_device_logs():
	"""Fetch and log biometric data immediately (not in background)."""
	client = BiometricApiClient()
	logs_data = client.get_device_logs()
	if logs_data["status"] == "success":
		if logs_data["type"] == "Bio Server":
			process_device_logs(logs_data["data"])
			sync_settings = frappe.get_single("Biometric Sync Settings")
			current_sync_date = frappe.utils.getdate(sync_settings.last_sync_date)
			next_sync_date = frappe.utils.add_days(current_sync_date, 1)
			sync_settings.last_sync_date = next_sync_date
			sync_settings.save(ignore_permissions=True)
		if logs_data["type"] == "eTime Tracker Lite":
			process_device_logs_etime_day(logs_data["data"])
			sync_settings = frappe.get_single("Biometric Sync Settings")
			sync_settings.last_sync_datetime = frappe.utils.now_datetime()
			sync_settings.save(ignore_permissions=True)
	return "Completed. Please check Biometric Sync Log for status."


def fetch_and_log_device_logs():
	"""Actual background job that fetches and logs biometric data."""
	client = BiometricApiClient()
	logs_data = client.get_device_logs()
	if logs_data["status"] == "success":
		if logs_data["type"] == "Bio Server":
			process_device_logs(logs_data["data"])
			sync_settings = frappe.get_single("Biometric Sync Settings")
			current_sync_date = frappe.utils.getdate(sync_settings.last_sync_date)
			next_sync_date = frappe.utils.add_days(current_sync_date, 1)
			sync_settings.last_sync_date = next_sync_date
			sync_settings.save(ignore_permissions=True)
		if logs_data["type"] == "eTime Tracker Lite":
			process_device_logs_etime(logs_data["data"])
			sync_settings = frappe.get_single("Biometric Sync Settings")
			sync_settings.last_sync_datetime = frappe.utils.now_datetime()
			sync_settings.save(ignore_permissions=True)


def fetch_and_log_device_logs_for_missing_date():
	client = BiometricApiClient()
	logs_data = client.get_device_logs_for_date()
	if logs_data["status"] == "success":
		if logs_data["type"] == "Bio Server":
			process_device_logs(logs_data["data"])
			sync_settings = frappe.get_single("Biometric Sync Settings")
			current_sync_date = frappe.utils.getdate(sync_settings.last_sync_date)
			next_sync_date = frappe.utils.add_days(current_sync_date, 1)
			sync_settings.last_sync_date = next_sync_date
			sync_settings.save(ignore_permissions=True)
		if logs_data["type"] == "eTime Tracker Lite":
			process_device_logs_etime(logs_data["data"])
			# sync_settings = frappe.get_single("Biometric Sync Settings")
			# sync_settings.last_sync_datetime = frappe.utils.now_datetime()
			# sync_settings.save(ignore_permissions=True)


def retry_logs(payload, request_id):
	client = BiometricApiClient()
	logs_data = client.retry_get_device_logs(payload, request_id)
	if logs_data["status"] == "success":
		if logs_data["type"] == "Bio Server":
			process_device_logs(logs_data["data"])
		if logs_data["type"] == "eTime Tracker Lite":
			process_device_logs_etime(logs_data["data"])


def process_device_logs(response_text):
	ns = {"soap": "http://schemas.xmlsoap.org/soap/envelope/", "ns1": "http://tempuri.org/"}

	root = ET.fromstring(response_text)
	result_tag = root.find(".//ns1:GetDeviceLogsResult", ns)
	result = None

	if result_tag is not None and result_tag.text:
		result = result_tag.text.strip()

	if not result:
		frappe.log_error(title="No logs found in the response.", message=result_tag)
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
			frappe.get_doc(
				{
					"doctype": "Employee Checkin",
					"employee": employee,
					"time": log_time,
					"device_id": location,
					"log_type": "IN",
				}
			).insert(ignore_permissions=True)
			created += 1
		except Exception:
			frappe.log_error(
				title="Employee Checkin", message=f"Error processing line: {line}\n{frappe.get_traceback()}"
			)

	return f"{created} Employee Checkin(s) created."


# def process_device_logs_etime(response_text):
#     """
#     Processes Bio Server SOAP GetTransactionsLog response.

#     Groups lines by employee code and creates:
#       - one Employee Checkin with log_type "IN" at the earliest timestamp
#       - one Employee Checkin with log_type "OUT" at the latest timestamp (if different)
#     """
#     ns = {
#         "soap": "http://www.w3.org/2003/05/soap-envelope",
#         "t": "http://tempuri.org/",
#     }

#     try:
#         root = ET.fromstring(response_text)
#     except ET.ParseError as e:
#         frappe.log_error(title="Bio Server XML parse error", message=str(e))
#         frappe.throw("Failed to parse Bio Server response.")

#     body = root.find("soap:Body", ns)
#     if body is None:
#         frappe.log_error(title="Bio Server SOAP error", message="Missing SOAP Body")
#         frappe.throw("Invalid response from Bio Server (no SOAP Body).")

#     resp = body.find("t:GetTransactionsLogResponse", ns)
#     if resp is None:
#         fault = body.find("soap:Fault", ns)
#         if fault is not None:
#             frappe.log_error(title="Bio Server SOAP Fault", message=ET.tostring(fault, encoding="unicode"))
#             frappe.throw("Bio Server returned a SOAP fault.")
#         frappe.log_error(title="Bio Server SOAP error", message="Missing GetTransactionsLogResponse")
#         frappe.throw("Invalid response from Bio Server.")

#     data_el = resp.find("t:strDataList", ns)
#     if data_el is None:
#         frappe.log_error(title="Bio Server: strDataList missing", message=ET.tostring(resp, encoding="unicode"))
#         frappe.throw("No logs found in the response.")

#     blob = (data_el.text or "").strip()
#     if not blob:
#         frappe.throw("No logs found in the response.")

#     # For device_id on checkins, prefer configured serial number
#     serial_number = None
#     try:
#         settings = frappe.get_single("Biometric Sync Settings")
#         serial_number = (settings.serial_no or "").strip() or "eTime Tracker Lite"
#     except Exception:
#         serial_number = "eTime Tracker Lite"

#     # Counters
#     created_in = 0
#     created_out = 0
#     skipped_no_emp = 0
#     skipped_dupe = 0
#     skipped_bad_line = 0
#     employee_errors = 0

#     # Group timestamps by emp_code
#     logs_by_emp = {}

#     # Each line typically: EMP_CODE \t YYYY-MM-DD HH:MM:SS \t ...
#     for raw_line in blob.splitlines():
#         line = raw_line.strip()
#         if not line:
#             continue

#         try:
#             parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
#             if len(parts) < 2:
#                 skipped_bad_line += 1
#                 continue

#             emp_code = parts[0]
#             ts_str = parts[1]

#             # Parse timestamp (Bio Server sample uses YYYY-MM-DD HH:MM:SS)
#             log_time = get_datetime(ts_str)

#             # append to group
#             logs_by_emp.setdefault(emp_code, []).append(log_time)

#         except Exception:
#             skipped_bad_line += 1
#             frappe.log_error(
#                 title="Bio Server: line parse error",
#                 message=f"Line: {raw_line}\n{frappe.get_traceback()}",
#             )

#     # Now process each employee group
#     for emp_code, times in logs_by_emp.items():
#         try:
#             # Normalize unique datetimes and sort
#             unique_times = sorted(set(times))
#             if not unique_times:
#                 continue

#             # Find Employee by attendance_device_id == emp_code
#             employee = frappe.db.get_value("Employee", {"attendance_device_id": emp_code})
#             if not employee:
#                 skipped_no_emp += 1
#                 frappe.logger().info(f"[Bio Server] No employee for code: {emp_code}")
#                 continue

#             # First = IN
#             first_time = unique_times[0]
#             # Last = OUT (only if different)
#             last_time = unique_times[-1]

#             # Insert IN if not exists
#             if not frappe.db.exists("Employee Checkin", {"employee": employee, "time": first_time}):
#                 frappe.get_doc({
#                     "doctype": "Employee Checkin",
#                     "employee": employee,
#                     "time": first_time,
#                     "device_id": serial_number,
#                     "log_type": "IN",
#                 }).insert(ignore_permissions=True)
#                 created_in += 1
#             else:
#                 skipped_dupe += 1

#             # Insert OUT only if last_time > first_time and not already exists
#             if last_time and last_time > first_time:
#                 if not frappe.db.exists("Employee Checkin", {"employee": employee, "time": last_time}):
#                     frappe.get_doc({
#                         "doctype": "Employee Checkin",
#                         "employee": employee,
#                         "time": last_time,
#                         "device_id": serial_number,
#                         "log_type": "OUT",
#                     }).insert(ignore_permissions=True)
#                     created_out += 1
#                 else:
#                     skipped_dupe += 1

#         except Exception:
#             employee_errors += 1
#             frappe.log_error(
#                 title="Bio Server: Checkin insert error for employee group",
#                 message=f"Emp Code: {emp_code}\nLines: {len(times)}\n{frappe.get_traceback()}",
#             )


#     return (
#         f"{created_in} IN created, {created_out} OUT created. "
#         f"(skipped: no-employee={skipped_no_emp}, duplicates={skipped_dupe}, bad-line={skipped_bad_line}, emp-errors={employee_errors})"
#     )
def process_device_logs_etime_day(response_text):
	"""
	Processes Bio Server SOAP GetTransactionsLog response.

	Groups lines by employee code and creates an Employee Checkin for
	every timestamp returned by the device (skips duplicates).
	"""
	ns = {
		"soap": "http://www.w3.org/2003/05/soap-envelope",
		"t": "http://tempuri.org/",
	}

	try:
		root = ET.fromstring(response_text)
	except ET.ParseError as e:
		frappe.log_error(title="Bio Server XML parse error", message=str(e))
		frappe.throw("Failed to parse Bio Server response.")

	body = root.find("soap:Body", ns)
	if body is None:
		frappe.log_error(title="Bio Server SOAP error", message="Missing SOAP Body")
		frappe.throw("Invalid response from Bio Server (no SOAP Body).")

	resp = body.find("t:GetTransactionsLogResponse", ns)
	if resp is None:
		fault = body.find("soap:Fault", ns)
		if fault is not None:
			frappe.log_error(title="Bio Server SOAP Fault", message=ET.tostring(fault, encoding="unicode"))
			frappe.throw("Bio Server returned a SOAP fault.")
		frappe.log_error(title="Bio Server SOAP error", message="Missing GetTransactionsLogResponse")
		frappe.throw("Invalid response from Bio Server.")

	data_el = resp.find("t:strDataList", ns)
	if data_el is None:
		frappe.log_error(
			title="Bio Server: strDataList missing", message=ET.tostring(resp, encoding="unicode")
		)
		frappe.throw("No logs found in the response.")

	blob = (data_el.text or "").strip()
	if not blob:
		frappe.throw("No logs found in the response.")

	# For device_id on checkins, prefer configured serial number
	serial_number = None
	try:
		settings = frappe.get_single("Biometric Sync Settings")
		serial_number = (settings.serial_no or "").strip() or "eTime Tracker Lite"
	except Exception:
		serial_number = "eTime Tracker Lite"

	# Counters
	created = 0
	skipped_no_emp = 0
	skipped_dupe = 0
	skipped_bad_line = 0
	employee_errors = 0
	no_emp = []
	not_active = []
	not_ho = []
	errored_employees = []

	# Group timestamps by emp_code
	logs_by_emp = {}

	# Each line typically: EMP_CODE \t YYYY-MM-DD HH:MM:SS \t ...
	for raw_line in blob.splitlines():
		line = raw_line.strip()
		if not line:
			continue

		try:
			parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
			if len(parts) < 2:
				skipped_bad_line += 1
				continue

			emp_code = parts[0]
			ts_str = parts[1]

			# Parse timestamp (Bio Server sample uses YYYY-MM-DD HH:MM:SS)
			log_time = get_datetime(ts_str)

			# append to group
			logs_by_emp.setdefault(emp_code, []).append(log_time)

		except Exception:
			skipped_bad_line += 1
			frappe.log_error(
				title="Bio Server: line parse error",
				message=f"Line: {raw_line}\n{frappe.get_traceback()}",
			)

	# Now process each employee group
	for emp_code, times in logs_by_emp.items():
		try:
			# Normalize unique datetimes and sort
			unique_times = sorted(set(times))
			if not unique_times:
				continue

			# Find Employee by attendance_device_id == emp_code
			employee = frappe.db.get_value("Employee", {"attendance_device_id": emp_code})
			if not employee:
				skipped_no_emp += 1
				no_emp.append(emp_code)
				frappe.logger().info(f"[Bio Server] No employee for code: {emp_code}")
				continue

			emp_details = frappe.db.get_value(
				"Employee", employee, ["name", "status", "office_type"], as_dict=True
			)

			# Manually check status to avoid erpnext.hr.utils.validate_active_employee throw
			if emp_details.status != "Active":
				employee_errors += 1
				not_active.append(emp_code)
				frappe.logger().info(f"Skipping Inactive Employee: {emp_code}")
				continue

			if emp_details.office_type != "HO":
				employee_errors += 1
				not_ho.append(f"{emp_code}: {emp_details.name} ({emp_details.status}) {emp_details.office_type}")
				frappe.logger().info(f"Skipping Non-HO Employee: {emp_code}")
				continue

			# Insert a checkin for every timestamp (all as IN for etime_day)
			for log_time in unique_times:
				try:
					if not frappe.db.exists("Employee Checkin", {"employee": employee, "time": log_time}):
						frappe.get_doc(
							{
								"doctype": "Employee Checkin",
								"employee": employee,
								"time": log_time,
								"device_id": serial_number,
								"log_type": "IN",
							}
						).insert(ignore_permissions=True)
						created += 1
					else:
						skipped_dupe += 1

				except Exception:
					employee_errors += 1
					errored_employees.append(emp_code)
					frappe.log_error(
						title="Bio Server: Checkin insert error for employee group",
						message=f"Emp Code: {emp_code}\nLines: {len(times)}\n{frappe.get_traceback()}",
					)
					frappe.db.rollback()  # ← Clean broken transaction so next log_time can proceed
					# continue to next log_time for this employee

			# Commit after each employee so locks are released
			# and other employees are not affected if something goes wrong
			frappe.db.commit()

		except Exception:
			frappe.db.rollback()  # ← Clean up if something fails outside the inner loop
			employee_errors += 1
			errored_employees.append(emp_code)
			frappe.log_error(
				title="Bio Server: Employee group processing error",
				message=f"Emp Code: {emp_code}\n{frappe.get_traceback()}",
			)
			# continue to next employee

	frappe.log_error(
		title="Bio Server Sync Summary",
		message=(
			f"{created} entries created. "
			f"(skipped: no-employee={skipped_no_emp} {no_emp} {not_ho}, "
			f"duplicates={skipped_dupe}, bad-line={skipped_bad_line}, "
			f"emp-errors={employee_errors} {errored_employees})"
		),
	)
	return (
		f"{created} entries created. "
		f"(skipped: no-employee={skipped_no_emp} {no_emp} {not_ho}, duplicates={skipped_dupe}, "
		f"bad-line={skipped_bad_line}, emp-errors={employee_errors} {errored_employees})"
	)

def process_device_logs_etime(response_text):
	"""
	Processes Bio Server SOAP GetTransactionsLog response.

	Groups lines by employee code and creates an Employee Checkin for
	every timestamp returned by the device (skips duplicates).
	"""
	ns = {
		"soap": "http://www.w3.org/2003/05/soap-envelope",
		"t": "http://tempuri.org/",
	}

	try:
		root = ET.fromstring(response_text)
	except ET.ParseError as e:
		frappe.log_error(title="Bio Server XML parse error", message=str(e))
		frappe.throw("Failed to parse Bio Server response.")

	body = root.find("soap:Body", ns)
	if body is None:
		frappe.log_error(title="Bio Server SOAP error", message="Missing SOAP Body")
		frappe.throw("Invalid response from Bio Server (no SOAP Body).")

	resp = body.find("t:GetTransactionsLogResponse", ns)
	if resp is None:
		fault = body.find("soap:Fault", ns)
		if fault is not None:
			frappe.log_error(title="Bio Server SOAP Fault", message=ET.tostring(fault, encoding="unicode"))
			frappe.throw("Bio Server returned a SOAP fault.")
		frappe.log_error(title="Bio Server SOAP error", message="Missing GetTransactionsLogResponse")
		frappe.throw("Invalid response from Bio Server.")

	data_el = resp.find("t:strDataList", ns)
	if data_el is None:
		frappe.log_error(
			title="Bio Server: strDataList missing", message=ET.tostring(resp, encoding="unicode")
		)
		frappe.throw("No logs found in the response.")

	blob = (data_el.text or "").strip()
	if not blob:
		frappe.throw("No logs found in the response.")

	# For device_id on checkins, prefer configured serial number
	serial_number = None
	try:
		settings = frappe.get_single("Biometric Sync Settings")
		serial_number = (settings.serial_no or "").strip() or "eTime Tracker Lite"
	except Exception:
		serial_number = "eTime Tracker Lite"

	# Counters
	created = 0
	skipped_no_emp = 0
	skipped_dupe = 0
	skipped_bad_line = 0
	employee_errors = 0

	no_emp = []
	not_active = []
	not_ho = []
	errored_employees = []

	# Group timestamps by emp_code
	logs_by_emp = {}

	# Each line typically: EMP_CODE \t YYYY-MM-DD HH:MM:SS \t ...
	for raw_line in blob.splitlines():
		line = raw_line.strip()
		if not line:
			continue

		try:
			parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
			if len(parts) < 2:
				skipped_bad_line += 1
				continue

			emp_code = parts[0]
			ts_str = parts[1]

			log_time = get_datetime(ts_str)
			logs_by_emp.setdefault(emp_code, []).append(log_time)

		except Exception:
			skipped_bad_line += 1
			frappe.log_error(
				title="Bio Server: line parse error",
				message=f"Line: {raw_line}\n{frappe.get_traceback()}",
			)

	# Now process each employee group
	for emp_code, times in logs_by_emp.items():
		try:
			# Normalize unique datetimes and sort
			unique_times = sorted(set(times))
			if not unique_times:
				continue

			# Find Employee by attendance_device_id == emp_code
			employee = frappe.db.get_value("Employee", {"attendance_device_id": emp_code})
			if not employee:
				skipped_no_emp += 1
				no_emp.append(emp_code)
				frappe.logger().info(f"[Bio Server] No employee for code: {emp_code}")
				continue

			emp_details = frappe.db.get_value(
				"Employee", employee, ["name", "status", "office_type"], as_dict=True
			)

			# Manually check status to avoid erpnext.hr.utils.validate_active_employee throw
			if emp_details.status != "Active":
				employee_errors += 1
				not_active.append(emp_code)
				frappe.logger().info(f"Skipping Inactive Employee: {emp_code}")
				continue

			if emp_details.office_type != "HO":
				employee_errors += 1
				not_ho.append(f"{emp_code}: {emp_details.name} ({emp_details.status}) {emp_details.office_type}")
				frappe.logger().info(f"Skipping Non-HO Employee: {emp_code}")
				continue

			last_time = unique_times[-1]
			in_inserted = False  # ← Track whether IN was successfully inserted for this employee

			# Insert a checkin for every timestamp
			for log_time in unique_times:
				try:
					log_type = "OUT" if log_time == last_time else "IN"

					# ← Don't attempt OUT if IN was never inserted/confirmed
					# This prevents custom_validate_checkin from throwing
					# "Cannot log OUT without logging IN first"
					if log_type == "OUT" and not in_inserted:
						frappe.logger().info(
							f"[Bio Server] Skipping OUT for {emp_code} at {log_time} — IN was not inserted"
						)
						skipped_dupe += 1
						continue

					if not frappe.db.exists("Employee Checkin", {"employee": employee, "time": log_time}):
						frappe.get_doc(
							{
								"doctype": "Employee Checkin",
								"employee": employee,
								"time": log_time,
								"device_id": serial_number,
								"log_type": log_type,
							}
						).insert(ignore_permissions=True)
						created += 1
						if log_type == "IN":
							in_inserted = True  # ← IN created, OUT is now safe
					else:
						skipped_dupe += 1
						if log_type == "IN":
							in_inserted = True  # ← IN already exists, OUT is still safe

				except Exception:
					employee_errors += 1
					errored_employees.append(emp_code)
					frappe.log_error(
						title="Bio Server: Checkin insert error for employee group",
						message=f"Emp Code: {emp_code}\nLines: {len(times)}\n{frappe.get_traceback()}",
					)
					frappe.db.rollback()  # ← Clean dirty transaction so next log_time proceeds normally
					# continues to next log_time

			# ← Commit after each employee to release DB locks
			frappe.db.commit()

		except Exception:
			# Catches anything unexpected outside the inner loop
			# (e.g. emp_details lookup crash, unexpected None, etc.)
			frappe.db.rollback()
			employee_errors += 1
			errored_employees.append(emp_code)
			frappe.log_error(
				title="Bio Server: Employee group processing error",
				message=f"Emp Code: {emp_code}\n{frappe.get_traceback()}",
			)
			# continues to next employee

	frappe.log_error(
		title="Bio Server Sync Summary",
		message=(
			f"{created} entries created. "
			f"(skipped: no-employee={skipped_no_emp} {no_emp} {not_ho}, "
			f"duplicates={skipped_dupe}, bad-line={skipped_bad_line}, "
			f"emp-errors={employee_errors} {errored_employees})"
		),
	)
	return (
		f"{created} entries created. "
		f"(skipped: no-employee={skipped_no_emp} {no_emp} {not_ho}, duplicates={skipped_dupe}, "
		f"bad-line={skipped_bad_line}, emp-errors={employee_errors} {errored_employees})"
	)


@frappe.whitelist(allow_guest=True)
def attendance_log():
	import json

	# Only allow POST
	if frappe.request.method != "POST":
		frappe.local.response.http_status_code = 405
		return {"error": "Method Not Allowed"}

	try:
		data = frappe.request.data  # raw bytes
		if isinstance(data, bytes):
			data = data.decode("utf-8")

		data = json.loads(data)  # parse to Python list/dict

		# You can log it, process it, or store it
		frappe.log_error(
			title="Employee Checkin Data", message=f"Received Webhook: {json.dumps(data, indent=4)}"
		)
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
			frappe.get_doc(
				{
					"doctype": "Employee Checkin",
					"employee": employee,
					"time": log_time,
					"device_id": location,
					"log_type": "IN",  # optionally use entry.get("DeviceDirection") or similar if needed
				}
			).insert(ignore_permissions=True)

			created += 1
		return "success"
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Webhook Handler Error")
		frappe.local.response.http_status_code = 500
		return {"status": "error", "message": str(e)}
