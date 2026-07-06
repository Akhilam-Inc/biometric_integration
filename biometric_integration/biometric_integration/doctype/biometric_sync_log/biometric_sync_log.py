# Copyright (c) 2025, Akhilam Inc. and contributors
# For license information, please see license.txt

import json
import xml.etree.ElementTree as ET

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now
from frappe.utils import add_days, get_datetime, getdate, strip_html, today
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
			table,
			filters=(table.modified < (Now() - Interval(days=days))) & (table.status == "Success"),
		)


# ---------------------------------------------------------------------------
# Low-level log record helper (used by BiometricApiClient)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Retry management
# ---------------------------------------------------------------------------

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
		method=run_sync_job,
		location=doc.location or None,
		sync_date=str(doc.sync_date) if doc.sync_date else None,
		serial_no=doc.serial_no or None,
		last_sync_datetime=str(doc.last_sync_datetime) if doc.last_sync_datetime else None,
		is_missing_date=bool(doc.is_missing_date_sync),
		queue="short",
		timeout=3500,
		is_async=True,
		enqueue_after_commit=True,
	)


@frappe.whitelist()
def bulk_retry(names):
	if isinstance(names, str):
		names = json.loads(names)
	for name in names:
		_retry_job(name)


# ---------------------------------------------------------------------------
# Scheduler entry point
# ---------------------------------------------------------------------------

def sync_all():
	"""
	Daily scheduler entry point.

	Enqueues ONE background job per missing calendar day per unit, from the
	last synced date up to and including yesterday.  Every job uses
	is_missing_date=True so it fetches exactly one calendar day from the
	device API — never a multi-day range.

	Example: last sync was June 5, today is June 10 →
	  enqueues June 5, June 6, June 7, June 8, June 9  (5 jobs per unit).

	The settings pointer is advanced here after enqueueing, not inside
	individual jobs.  Failed jobs appear in Biometric Sync Log with
	status=Error and can be retried per-day from the dashboard.
	"""
	settings = frappe.get_single("Biometric Sync Settings")
	yesterday = add_days(getdate(today()), -1)

	if settings.server_type == "Bio Server":
		for row in settings.biometric_location_detail:
			if not row.location or not row.last_sync_date:
				continue

			current = getdate(row.last_sync_date)
			if current > yesterday:
				continue  # already up to date

			queued = 0
			while current <= yesterday:
				frappe.enqueue(
					method=run_sync_job,
					location=row.location,
					sync_date=str(current),
					is_missing_date=True,
					queue="short",
					timeout=3500,
					is_async=True,
					enqueue_after_commit=True,
				)
				current = add_days(current, 1)
				queued += 1

			# Advance pointer so next run starts from today
			if queued:
				update_biometric_sync_settings(row.location, getdate(today()))

	elif settings.server_type == "eTime Tracker Lite":
		for row in settings.biometric_serial_detail:
			if not row.serial_no or not row.last_sync_datetime:
				continue

			# Derive start date from the last sync datetime
			current = getdate(row.last_sync_datetime)
			if current > yesterday:
				continue

			queued = 0
			while current <= yesterday:
				# is_missing_date=True makes run_sync_job use a full-day window:
				#   from = {sync_date} 00:00:00,  to = {sync_date} 23:59:59
				frappe.enqueue(
					method=run_sync_job,
					serial_no=row.serial_no,
					sync_date=str(current),
					is_missing_date=True,
					queue="short",
					timeout=3500,
					is_async=True,
					enqueue_after_commit=True,
				)
				current = add_days(current, 1)
				queued += 1

			# Advance pointer so next run starts from today
			if queued:
				update_etime_sync_settings(row.serial_no, frappe.utils.now_datetime())

	elif settings.server_type == "ZKTeco":
		for row in settings.biometric_zkteco_device:
			if not row.terminal_sn or not row.last_sync_datetime:
				continue

			current = getdate(row.last_sync_datetime)
			if current > yesterday:
				continue

			queued = 0
			while current <= yesterday:
				frappe.enqueue(
					method=run_sync_job,
					serial_no=row.terminal_sn,
					sync_date=str(current),
					is_missing_date=True,
					queue="short",
					timeout=3500,
					is_async=True,
					enqueue_after_commit=True,
				)
				current = add_days(current, 1)
				queued += 1

			if queued:
				update_zkteco_sync_settings(row.terminal_sn, frappe.utils.now_datetime())


# ---------------------------------------------------------------------------
# Universal sync job (Bio Server + eTime Tracker Lite + ZKTeco)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def run_sync_job_background(
	location=None,
	sync_date=None,
	serial_no=None,
	last_sync_datetime=None,
):
	"""Whitelisted wrapper — called from the JS row-level Sync Log button."""
	settings = frappe.get_single("Biometric Sync Settings")

	if settings.server_type == "Bio Server":
		if not location:
			frappe.throw("Location is required.", title="Location Required")
		if not sync_date:
			frappe.throw(
				f"Last Sync Date is required for location <b>{location}</b>.",
				title="Last Sync Date Required",
			)
	else:
		# eTime Tracker Lite and ZKTeco both use serial_no + last_sync_datetime
		if not serial_no:
			frappe.throw("Serial No is required.", title="Serial No Required")
		if not last_sync_datetime:
			frappe.throw(
				f"Last Sync Datetime is required for serial <b>{serial_no}</b>.",
				title="Last Sync Datetime Required",
			)

	frappe.enqueue(
		method=run_sync_job,
		location=location,
		sync_date=sync_date,
		serial_no=serial_no,
		last_sync_datetime=last_sync_datetime,
		queue="short",
		timeout=3500,
		is_async=True,
	)
	return "Enqueued. Please check Biometric Sync Log for status."


def run_sync_job(
	location=None,
	sync_date=None,
	serial_no=None,
	last_sync_datetime=None,
	is_missing_date=False,
):
	"""
	Universal background job — Bio Server, eTime Tracker Lite, and ZKTeco.

	Bio Server:     location + sync_date
	eTime regular:  serial_no + last_sync_datetime  (to_datetime = now)
	eTime missing:  serial_no + sync_date           (from = date 00:00, to = date 23:59:59)
	ZKTeco regular: serial_no + last_sync_datetime  (to_datetime = now)
	ZKTeco missing: serial_no + sync_date           (from = date 00:00, to = date 23:59:59)
	"""
	settings = frappe.get_single("Biometric Sync Settings")
	server_type = settings.server_type

	if server_type == "ZKTeco":
		return _run_zkteco_sync_job(
			terminal_sn=serial_no,
			sync_date=sync_date,
			last_sync_datetime=last_sync_datetime,
			is_missing_date=is_missing_date,
		)

	client = BiometricApiClient()

	# For eTime missing-date syncs: derive the exact datetime window from sync_date
	etime_from_dt = last_sync_datetime
	etime_to_dt = None
	if serial_no and is_missing_date and sync_date:
		etime_from_dt = f"{sync_date} 00:00:00"
		etime_to_dt = f"{sync_date} 23:59:59"

	result = client.get_device_logs(
		location=location,
		sync_date=sync_date,
		serial_no=serial_no,
		last_sync_datetime=etime_from_dt,
		to_datetime=etime_to_dt,
		is_missing_date=is_missing_date,
	)

	if result["status"] != "success":
		return  # error already logged inside get_device_logs

	stats = _process_response(result["type"], result["data"], serial_no=serial_no)

	if not is_missing_date:
		if result["type"] == "Bio Server":
			next_date = frappe.utils.add_days(getdate(sync_date), 1)
			if next_date <= getdate(today()):
				update_biometric_sync_settings(location, next_date)
		else:
			update_etime_sync_settings(serial_no, frappe.utils.now_datetime())

	_write_sync_log(
		server_type=result["type"],
		location=location,
		serial_no=serial_no,
		sync_date=sync_date,
		last_sync_datetime=etime_from_dt,
		is_missing_date=is_missing_date,
		stats=stats,
	)


def _run_zkteco_sync_job(
	terminal_sn: str,
	sync_date=None,
	last_sync_datetime=None,
	is_missing_date: bool = False,
):
	"""ZKTeco-specific background job body (REST/JWT, paginated)."""
	from biometric_integration.biometric_integration.api.base import ZKTecoApiClient

	if is_missing_date and sync_date:
		start_dt = f"{sync_date} 00:00:00"
		end_dt = f"{sync_date} 23:59:59"
		effective_from_dt = start_dt
	elif last_sync_datetime:
		start_dt = str(last_sync_datetime)
		end_dt = str(frappe.utils.now_datetime())
		effective_from_dt = start_dt
	else:
		# Neither a missing-date window nor a last-sync pointer to resume from —
		# happens if a Retry is triggered from a log whose identity fields never
		# got captured. Bail loudly instead of sending start_time="None" to the API.
		frappe.log_error(
			title="ZKTeco Sync Skipped",
			message=f"terminal_sn={terminal_sn}: no sync_date or last_sync_datetime to sync from.",
		)
		return

	try:
		client = ZKTecoApiClient()
		transactions = client.get_transactions(
			start_dt,
			end_dt,
			terminal_sn=terminal_sn,
			sync_date=sync_date,
			is_missing_date=is_missing_date,
		)
	except Exception:
		# get_transactions already logged via create_biometric_log — just return
		return

	stats = process_device_logs_zkteco(transactions, terminal_sn=terminal_sn)

	if not is_missing_date:
		update_zkteco_sync_settings(terminal_sn, frappe.utils.now_datetime())

	_write_sync_log(
		server_type="ZKTeco",
		location=None,
		serial_no=terminal_sn,
		sync_date=sync_date,
		last_sync_datetime=effective_from_dt,
		is_missing_date=is_missing_date,
		stats=stats,
	)


def _process_response(server_type, response_data, serial_no=None):
	"""Dispatch to the mode-specific parser. All return the same stats dict."""
	if server_type == "Bio Server":
		return process_device_logs(response_data)
	if server_type == "eTime Tracker Lite":
		return process_device_logs_etime(response_data, serial_no=serial_no)
	# ZKTeco — response_data may be a list (fresh sync) or a JSON string (retry from stored log)
	if isinstance(response_data, str):
		try:
			response_data = json.loads(response_data)
		except Exception:
			frappe.log_error(title="ZKTeco: response_data parse error", message=response_data[:500])
			return dict(_EMPTY_STATS)
	return process_device_logs_zkteco(response_data, terminal_sn=serial_no)


# ---------------------------------------------------------------------------
# Settings pointer helpers
# ---------------------------------------------------------------------------

def update_biometric_sync_settings(location, next_sync_date):
	row = frappe.db.get_value(
		"Biometric Location Detail",
		{"parent": "Biometric Sync Settings", "location": location},
		"name",
	)
	if row:
		frappe.db.set_value(
			"Biometric Location Detail",
			row,
			"last_sync_date",
			next_sync_date,
			update_modified=False,
		)
		frappe.publish_realtime(
			"biometric_sync_update", {"location": location, "status": "success"}
		)


def update_etime_sync_settings(serial_no, last_sync_datetime):
	row = frappe.db.get_value(
		"Biometric Serial Detail",
		{"parent": "Biometric Sync Settings", "serial_no": serial_no},
		"name",
	)
	if row:
		frappe.db.set_value(
			"Biometric Serial Detail",
			row,
			"last_sync_datetime",
			last_sync_datetime,
			update_modified=False,
		)
		frappe.publish_realtime(
			"biometric_sync_update", {"serial_no": serial_no, "status": "success"}
		)


def update_zkteco_sync_settings(terminal_sn, last_sync_datetime):
	row = frappe.db.get_value(
		"Biometric ZKTeco Device",
		{"parent": "Biometric Sync Settings", "terminal_sn": terminal_sn},
		"name",
	)
	if row:
		frappe.db.set_value(
			"Biometric ZKTeco Device",
			row,
			"last_sync_datetime",
			last_sync_datetime,
			update_modified=False,
		)
		frappe.publish_realtime(
			"biometric_sync_update", {"serial_no": terminal_sn, "status": "success"}
		)


# ---------------------------------------------------------------------------
# Structured log writer
# ---------------------------------------------------------------------------

def _write_sync_log(
	server_type,
	location,
	serial_no,
	sync_date,
	last_sync_datetime,
	is_missing_date,
	stats,
):
	"""Stamps the in-flight log record with structured execution results."""
	if not frappe.flags.request_id:
		return
	try:
		# For eTime regular syncs sync_date arrives as None — derive it from
		# last_sync_datetime so the date column is always populated on every log row.
		effective_sync_date = sync_date
		if not effective_sync_date and last_sync_datetime:
			effective_sync_date = getdate(last_sync_datetime)

		doc = frappe.get_doc("Biometric Sync Log", frappe.flags.request_id)
		doc.server_type = server_type
		doc.location = location or ""
		doc.serial_no = serial_no or ""
		doc.sync_date = effective_sync_date
		doc.last_sync_datetime = last_sync_datetime
		doc.is_missing_date_sync = 1 if is_missing_date else 0
		doc.total_records_received = stats.get("total_records_received", 0)
		doc.employees_total        = stats.get("employees_total", 0)
		doc.checkins_created       = stats.get("created", 0)
		doc.checkins_skipped       = stats.get("skipped_duplicate", 0)
		doc.employees_not_found    = len(stats.get("skipped_no_employee", []))
		doc.errored_count          = len(stats.get("errored_employees", []))
		doc.skipped_inactive       = len(stats.get("skipped_inactive", []))
		doc.sync_summary = json.dumps(stats, separators=(",", ":"))
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.log_error(
			title="Biometric: _write_sync_log failed", message=frappe.get_traceback()
		)
	finally:
		# Always release the flag — this job is done with the log record
		frappe.flags.request_id = None


# ---------------------------------------------------------------------------
# Bio Server response processor
# ---------------------------------------------------------------------------

_EMPTY_STATS = {
	"created": 0,
	"skipped_duplicate": 0,
	"skipped_no_employee": [],
	"skipped_inactive": [],
	"errored_employees": [],
	"bad_lines": 0,
	"total_records_received": 0,
	"employees_total": 0,
}


def process_device_logs(response_text):
	"""
	Parse Bio Server GetDeviceLogs SOAP response and create Employee Checkins.
	Returns a stats dict. Empty/no-punch days return zero stats (not an error).
	"""
	ns = {
		"soap": "http://schemas.xmlsoap.org/soap/envelope/",
		"ns1": "http://tempuri.org/",
	}

	try:
		root = ET.fromstring(response_text)
	except ET.ParseError as e:
		frappe.log_error(title="Bio Server XML parse error", message=str(e))
		return dict(_EMPTY_STATS)

	result_tag = root.find(".//ns1:GetDeviceLogsResult", ns)
	result = None

	if result_tag is not None and result_tag.text:
		result = result_tag.text.strip()

	if not result:
		# No punches for this date — valid (weekend / holiday / device offline)
		return dict(_EMPTY_STATS)

	logs = result.split(";\n")
	total_records_received = sum(1 for l in logs if l.strip())

	created = 0
	skipped_duplicate = 0
	skipped_no_employee = []
	skipped_inactive = []
	errored_employees = []
	bad_lines = 0

	for line in logs:
		if not line.strip():
			continue

		try:
			parts = line.split(",")
			if len(parts) < 4:
				bad_lines += 1
				continue

			log_time_str = parts[0].strip()
			device_id = parts[1].strip()
			location = parts[3].strip()

			log_time = get_datetime(log_time_str)

			employee = frappe.db.get_value("Employee", {"attendance_device_id": device_id})
			if not employee:
				skipped_no_employee.append(device_id)
				continue

			emp_status = frappe.db.get_value("Employee", employee, "status")
			if emp_status != "Active":
				skipped_inactive.append(device_id)
				continue

			if frappe.db.exists("Employee Checkin", {"employee": employee, "time": log_time}):
				skipped_duplicate += 1
				continue

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
			errored_employees.append(line[:50])
			frappe.log_error(
				title="Bio Server: Checkin insert error",
				message=f"Error processing line: {line}\n{frappe.get_traceback()}",
			)

	return {
		"created": created,
		"skipped_duplicate": skipped_duplicate,
		"skipped_no_employee": skipped_no_employee,
		"skipped_inactive": skipped_inactive,
		"errored_employees": errored_employees,
		"bad_lines": bad_lines,
		"total_records_received": total_records_received,
		# Bio Server: each raw line = 1 punch for 1 device ID, so same as total_records_received
		"employees_total": total_records_received,
	}


# ---------------------------------------------------------------------------
# eTime Tracker Lite response processor
# ---------------------------------------------------------------------------

def process_device_logs_etime(response_text, serial_no=None):
	"""
	Parse eTime Tracker Lite GetTransactionsLog SOAP response and create Employee Checkins.

	Groups punches by employee:
	  - first timestamp → IN
	  - last timestamp  → OUT (only if different from first)

	Returns a stats dict.
	"""
	ns = {
		"soap": "http://www.w3.org/2003/05/soap-envelope",
		"t": "http://tempuri.org/",
	}

	try:
		root = ET.fromstring(response_text)
	except ET.ParseError as e:
		frappe.log_error(title="eTime XML parse error", message=str(e))
		return dict(_EMPTY_STATS)

	body = root.find("soap:Body", ns)
	if body is None:
		frappe.log_error(title="eTime SOAP error", message="Missing SOAP Body")
		return dict(_EMPTY_STATS)

	resp = body.find("t:GetTransactionsLogResponse", ns)
	if resp is None:
		fault = body.find("soap:Fault", ns)
		if fault is not None:
			frappe.log_error(
				title="eTime SOAP Fault", message=ET.tostring(fault, encoding="unicode")
			)
		else:
			frappe.log_error(
				title="eTime SOAP error", message="Missing GetTransactionsLogResponse"
			)
		return dict(_EMPTY_STATS)

	data_el = resp.find("t:strDataList", ns)
	if data_el is None:
		frappe.log_error(
			title="eTime: strDataList missing", message=ET.tostring(resp, encoding="unicode")
		)
		return dict(_EMPTY_STATS)

	blob = (data_el.text or "").strip()
	if not blob:
		return dict(_EMPTY_STATS)

	total_records_received = sum(1 for l in blob.splitlines() if l.strip())
	device_id_label = serial_no or "eTime Tracker Lite"

	created = 0
	skipped_duplicate = 0
	skipped_no_employee = []
	skipped_inactive = []
	errored_employees = []
	bad_lines = 0

	logs_by_emp = {}

	for raw_line in blob.splitlines():
		line = raw_line.strip()
		if not line:
			continue
		try:
			parts = [p.strip() for p in line.split("\t") if p.strip() != ""]
			if len(parts) < 2:
				bad_lines += 1
				continue
			emp_code = parts[0]
			ts_str = parts[1]
			log_time = get_datetime(ts_str)
			logs_by_emp.setdefault(emp_code, []).append(log_time)
		except Exception:
			bad_lines += 1
			frappe.log_error(
				title="eTime: line parse error",
				message=f"Line: {raw_line}\n{frappe.get_traceback()}",
			)

	for emp_code, times in logs_by_emp.items():
		try:
			unique_times = sorted(set(times))
			if not unique_times:
				continue

			employee = frappe.db.get_value("Employee", {"attendance_device_id": emp_code})
			if not employee:
				skipped_no_employee.append(emp_code)
				continue

			emp_details = frappe.db.get_value(
				"Employee", employee, ["name", "status"], as_dict=True
			)

			if emp_details.status != "Active":
				skipped_inactive.append(emp_code)
				continue

			for log_time in unique_times:
				try:
					if not frappe.db.exists(
						"Employee Checkin", {"employee": employee, "time": log_time}
					):
						frappe.get_doc(
							{
								"doctype": "Employee Checkin",
								"employee": employee,
								"time": log_time,
								"device_id": device_id_label,
								"log_type": "IN",
							}
						).insert(ignore_permissions=True)
						created += 1
					else:
						skipped_duplicate += 1

				except Exception:
					errored_employees.append(emp_code)
					frappe.log_error(
						title="eTime: Checkin insert error",
						message=f"Emp: {emp_code} at {log_time}\n{frappe.get_traceback()}",
					)
					frappe.db.rollback()

			frappe.db.commit()

		except Exception:
			frappe.db.rollback()
			errored_employees.append(emp_code)
			frappe.log_error(
				title="eTime: Employee group error",
				message=f"Emp Code: {emp_code}\n{frappe.get_traceback()}",
			)

	return {
		"created": created,
		"skipped_duplicate": skipped_duplicate,
		"skipped_no_employee": skipped_no_employee,
		"skipped_inactive": skipped_inactive,
		"errored_employees": errored_employees,
		"bad_lines": bad_lines,
		"total_records_received": total_records_received,
		# eTime: unique employees attempted (not raw lines — they are N punches per employee)
		"employees_total": len(logs_by_emp),
	}


# ---------------------------------------------------------------------------
# ZKTeco response processor
# ---------------------------------------------------------------------------

def _get_zkteco_machine_type(terminal_sn: str | None) -> str:
	"""Look up the configured Machine Type (IN/OUT) for a ZKTeco terminal, default IN."""
	if not terminal_sn:
		return "IN"
	return (
		frappe.db.get_value(
			"Biometric ZKTeco Device",
			{"parent": "Biometric Sync Settings", "terminal_sn": terminal_sn},
			"machine_type",
		)
		or "IN"
	)


def process_device_logs_zkteco(transactions: list, terminal_sn: str | None = None) -> dict:
	"""
	Process a flat list of ZKTeco transaction dicts (already parsed JSON) and
	create Employee Checkins.

	terminal_sn is passed as a query param to the API, but we also filter in-app
	as a safety net in case the API returns stray records.
	Maps emp_code → attendance_device_id → Employee.
	Returns the same stats dict shape as the other processors.
	"""
	if not transactions:
		return dict(_EMPTY_STATS)

	device_id_label = terminal_sn or "ZKTeco"
	log_type = _get_zkteco_machine_type(terminal_sn)

	# Safety-net filter — the API already filters by terminal_sn, but guard against stray records.
	if terminal_sn:
		transactions = [t for t in transactions if t.get("terminal_sn") == terminal_sn]

	total_records_received = len(transactions)

	# Batch-fetch all emp_codes present in this result to avoid N+1 DB calls.
	emp_codes = list({t.get("emp_code", "") for t in transactions if t.get("emp_code")})
	employees_by_code: dict = {}
	if emp_codes:
		rows = frappe.get_all(
			"Employee",
			filters={"attendance_device_id": ["in", emp_codes]},
			fields=["name", "attendance_device_id", "status"],
		)
		for r in rows:
			employees_by_code[r.attendance_device_id] = r

	# Group punches by employee so we can commit per-employee (same pattern as eTime).
	logs_by_emp: dict = {}
	for record in transactions:
		emp_code = record.get("emp_code", "")
		punch_time_str = record.get("punch_time", "")
		if emp_code and punch_time_str:
			logs_by_emp.setdefault(emp_code, []).append(punch_time_str)

	created = 0
	skipped_duplicate = 0
	skipped_no_employee: list = []
	skipped_inactive: list = []
	errored_employees: list = []

	for emp_code, punch_time_strs in logs_by_emp.items():
		try:
			emp = employees_by_code.get(emp_code)
			if not emp:
				skipped_no_employee.append(emp_code)
				continue

			if emp.status != "Active":
				skipped_inactive.append(emp_code)
				continue

			for punch_time_str in punch_time_strs:
				try:
					punch_time = get_datetime(punch_time_str)

					if frappe.db.exists(
						"Employee Checkin", {"employee": emp.name, "time": punch_time}
					):
						skipped_duplicate += 1
						continue

					frappe.get_doc(
						{
							"doctype": "Employee Checkin",
							"employee": emp.name,
							"time": punch_time,
							"device_id": device_id_label,
							"log_type": log_type,
						}
					).insert(ignore_permissions=True)
					created += 1

				except Exception:
					errored_employees.append(emp_code)
					frappe.log_error(
						title="ZKTeco: Checkin insert error",
						message=f"Emp: {emp_code} at {punch_time_str}\n{frappe.get_traceback()}",
					)
					frappe.db.rollback()

			frappe.db.commit()

		except Exception:
			frappe.db.rollback()
			errored_employees.append(emp_code)
			frappe.log_error(
				title="ZKTeco: Employee group error",
				message=f"Emp Code: {emp_code}\n{frappe.get_traceback()}",
			)

	return {
		"created": created,
		"skipped_duplicate": skipped_duplicate,
		"skipped_no_employee": list(set(skipped_no_employee)),
		"skipped_inactive": list(set(skipped_inactive)),
		"errored_employees": list(set(errored_employees)),
		"bad_lines": 0,
		"total_records_received": total_records_received,
		"employees_total": len(logs_by_emp),
	}


# ---------------------------------------------------------------------------
# Webhook — attendance push from device (unchanged)
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def attendance_log():
	import json as _json

	if frappe.request.method != "POST":
		frappe.local.response.http_status_code = 405
		return {"error": "Method Not Allowed"}

	try:
		data = frappe.request.data
		if isinstance(data, bytes):
			data = data.decode("utf-8")

		data = _json.loads(data)

		frappe.log_error(
			title="Employee Checkin Data",
			message=f"Received Webhook: {_json.dumps(data, indent=4)}",
		)
		created = 0

		for entry in data:
			device_id = entry.get("EmployeeCode")
			log_time_str = entry.get("LogDate")
			location = entry.get("DeviceName") or entry.get("SerialNumber")

			log_time = get_datetime(log_time_str)

			employee = frappe.db.get_value("Employee", {"attendance_device_id": device_id})
			if not employee:
				frappe.logger().info(f"No employee found for device_id: {device_id}")
				continue

			if frappe.db.exists("Employee Checkin", {"employee": employee, "time": log_time}):
				continue

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

		return "success"

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Webhook Handler Error")
		frappe.local.response.http_status_code = 500
		return {"status": "error", "message": str(e)}
