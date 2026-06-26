# Copyright (c) 2026, Akhilam Inc. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from biometric_integration.biometric_integration.doctype.biometric_sync_log.biometric_sync_log import (
	_process_response,
	run_sync_job,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_UNIT_COL = {"Bio Server": "location", "eTime Tracker Lite": "serial_no", "ZKTeco": "serial_no"}


def _settings():
	"""Return (settings, server_type, unit_col, all_units)."""
	s = frappe.get_single("Biometric Sync Settings")
	server_type = s.server_type or "Bio Server"
	unit_col = _UNIT_COL.get(server_type, "location")
	if server_type == "Bio Server":
		all_units = [r.location for r in s.biometric_location_detail if r.location]
	elif server_type == "ZKTeco":
		all_units = [r.terminal_sn for r in s.biometric_zkteco_device if r.terminal_sn]
	else:
		all_units = [r.serial_no for r in s.biometric_serial_detail if r.serial_no]
	return s, server_type, unit_col, all_units


def _row_status(log) -> str:
	"""
	Derive display status from a log row dict.
	Uses only direct columns — no JSON parsing.
	"""
	if not log:
		return "missing"
	status = (log.get("status") or "").strip()
	if status == "Queued":
		return "pending"
	if status == "Error":
		return "error"

	total    = log.get("employees_total") or 0
	created  = log.get("checkins_created") or 0
	unmapped = log.get("employees_not_found") or 0
	errored  = log.get("errored_count") or 0

	# Truly nothing came in and nothing was processed
	if not total and not created and not unmapped and not errored:
		return "empty"

	return "warning" if (unmapped > 0 or errored > 0) else "success"


def _fetch_logs(unit_col: str, server_type: str, sync_date: str):
	"""
	Single SQL query for a given date — returns all columns needed by the
	dashboard without any post-query JSON parsing.
	"""
	return frappe.db.sql(
		"""
		SELECT
			name,
			sync_date,
			`{unit_col}`            AS unit,
			status,
			total_records_received,
			employees_total,
			checkins_created,
			checkins_skipped,
			employees_not_found,
			errored_count,
			skipped_inactive,
			last_sync_datetime,
			is_missing_date_sync,
			sync_summary,
			(response_data IS NOT NULL AND response_data != '') AS has_response_data
		FROM `tabBiometric Sync Log`
		WHERE sync_date = %(sync_date)s
		  AND server_type = %(server_type)s
		ORDER BY modified DESC
		""".format(unit_col=unit_col),
		{"sync_date": sync_date, "server_type": server_type},
		as_dict=True,
	)


# ---------------------------------------------------------------------------
# Dashboard data — single date
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_dashboard_data(sync_date):
	"""
	KPIs + one table row per configured unit for a single sync_date.

	total_records_received — raw device lines/punches received
	employees_total  — Bio Server: = total_records_received (one record = one punch)
	                   eTime:       = unique employees in the response (not raw lines)
	employees_not_found — unique device IDs not mapped in ERP  (employee-level count)
	errored_count       — employees that matched but threw insert errors
	skipped_inactive    — employees skipped because status != Active in ERP
	"""
	frappe.only_for("System Manager")

	_s, server_type, unit_col, all_units = _settings()

	empty_kpis = {
		"raw_records": 0,
		"total": 0,
		"created": 0,
		"skipped": 0,
		"unmapped_employees": 0,
		"errored": 0,
		"api_errors": 0,
		"locations_healthy": 0,
		"locations_total": len(all_units),
	}

	if not all_units:
		return {
			"server_type": server_type,
			"last_sync_datetime": None,
			"kpis": empty_kpis,
			"table_rows": [],
			"units": [],
		}

	logs = _fetch_logs(unit_col, server_type, sync_date)

	# Latest log per unit (rows are ordered by modified DESC)
	latest = {}
	for row in logs:
		if row.unit not in latest:
			latest[row.unit] = row

	unit_set = set(all_units)

	# KPI aggregates — all logs in the date for configured units
	kpi_raw     = sum((r.total_records_received or 0) for r in logs if r.unit in unit_set)
	kpi_total   = sum((r.employees_total or 0)        for r in logs if r.unit in unit_set)
	kpi_created = sum((r.checkins_created or 0)        for r in logs if r.unit in unit_set)
	kpi_skipped = sum((r.checkins_skipped or 0)        for r in logs if r.unit in unit_set)
	kpi_unmapped = sum((r.employees_not_found or 0)    for r in logs if r.unit in unit_set)
	kpi_errored  = sum((r.errored_count or 0)          for r in logs if r.unit in unit_set)
	kpi_api_err  = sum(1 for r in logs if r.unit in unit_set and (r.status or "") == "Error")
	healthy      = sum(1 for u in all_units if _row_status(latest.get(u)) == "success")

	last_sync = None
	for row in logs:
		if row.last_sync_datetime:
			if last_sync is None or row.last_sync_datetime > last_sync:
				last_sync = row.last_sync_datetime

	# One table row per configured unit
	table_rows = []
	for unit in all_units:
		log    = latest.get(unit)
		status = _row_status(log)

		raw_records = (log.total_records_received or 0) if log else None
		total    = (log.employees_total or 0)     if log else None
		created  = (log.checkins_created or 0)    if log else None
		skipped  = (log.checkins_skipped or 0)    if log else None
		unmapped = (log.employees_not_found or 0) if log else None
		errored  = (log.errored_count or 0)       if log else None
		inactive = (log.skipped_inactive or 0)    if log else None

		# Progress = % of received data that processed cleanly (no unmapped / errored)
		progress = None
		if total:
			clean    = max(total - (unmapped or 0) - (errored or 0), 0)
			progress = round(clean / total * 100, 1)

		table_rows.append(
			{
				"unit": unit,
				"log_name": log.name if log else None,
				"sync_date": str(log.sync_date) if log and log.sync_date else None,
				"status": status,
				"raw_records": raw_records,
				"total": total,
				"created": created,
				"skipped": skipped,
				"unmapped_employees": unmapped,
				"errored": errored,
				"inactive": inactive,
				"progress": progress,
				"has_response_data": bool(log.has_response_data) if log else False,
			}
		)

	return {
		"server_type": server_type,
		"last_sync_datetime": str(last_sync) if last_sync else None,
		"kpis": {
			"raw_records": kpi_raw,
			"total": kpi_total,
			"created": kpi_created,
			"skipped": kpi_skipped,
			"unmapped_employees": kpi_unmapped,
			"errored": kpi_errored,
			"api_errors": kpi_api_err,
			"locations_healthy": healthy,
			"locations_total": len(all_units),
		},
		"table_rows": table_rows,
		"units": all_units,
	}


# ---------------------------------------------------------------------------
# 7-day rolling trend (always last 7 days, independent of date picker)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_trend_data():
	"""Rolling 7-day totals: total_records_received vs checkins_created."""
	frappe.only_for("System Manager")

	_s, server_type, _u, _a = _settings()

	end   = getdate(today())
	start = add_days(end, -6)

	rows = frappe.db.sql(
		"""
		SELECT
			sync_date,
			SUM(total_records_received) AS raw_records,
			SUM(checkins_created)        AS created
		FROM `tabBiometric Sync Log`
		WHERE sync_date BETWEEN %(start)s AND %(end)s
		  AND server_type = %(server_type)s
		GROUP BY sync_date
		ORDER BY sync_date ASC
		""",
		{"start": str(start), "end": str(end), "server_type": server_type},
		as_dict=True,
	)

	labels, raw_vals, created_vals = [], [], []
	for r in rows:
		labels.append(getdate(r.sync_date).strftime("%d %b"))
		raw_vals.append(int(r.raw_records or 0))
		created_vals.append(int(r.created or 0))

	return {"labels": labels, "raw_records": raw_vals, "created": created_vals}


# ---------------------------------------------------------------------------
# Failure breakdown — single date, no JSON parsing
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_failure_breakdown(sync_date):
	"""Failure category counts for the selected date using direct columns only."""
	frappe.only_for("System Manager")

	_s, server_type, _u, _a = _settings()

	row = frappe.db.sql(
		"""
		SELECT
			SUM(employees_not_found)                       AS unmapped,
			COUNT(CASE WHEN status = 'Error' THEN 1 END)   AS api_errors,
			SUM(checkins_skipped)                          AS duplicates,
			SUM(errored_count)                             AS insert_errors,
			SUM(skipped_inactive)                          AS inactive
		FROM `tabBiometric Sync Log`
		WHERE sync_date = %(sync_date)s
		  AND server_type = %(server_type)s
		""",
		{"sync_date": sync_date, "server_type": server_type},
		as_dict=True,
	)
	t = row[0] if row else {}

	categories = [
		{"category": _("Unmapped Employees"),  "count": int(t.get("unmapped")       or 0)},
		{"category": _("API / SOAP Error"),     "count": int(t.get("api_errors")     or 0)},
		{"category": _("Insert Error"),         "count": int(t.get("insert_errors")  or 0)},
		{"category": _("Inactive Employees"),   "count": int(t.get("inactive")       or 0)},
		{"category": _("Duplicate Punch"),      "count": int(t.get("duplicates")     or 0)},
	]
	result = [c for c in categories if c["count"] > 0]
	result.sort(key=lambda x: x["count"], reverse=True)
	return result


# ---------------------------------------------------------------------------
# Unit history — date range view for a single location / serial
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_unit_history(unit, from_date, to_date):
	"""
	Per-unit daily breakdown for a date range.
	Returns summary aggregates + one row per calendar day (latest log per day).
	"""
	frappe.only_for("System Manager")

	_s, server_type, unit_col, _a = _settings()

	logs = frappe.db.sql(
		"""
		SELECT
			name,
			sync_date,
			status,
			total_records_received,
			employees_total,
			checkins_created,
			checkins_skipped,
			employees_not_found,
			errored_count,
			skipped_inactive,
			(response_data IS NOT NULL AND response_data != '') AS has_response_data
		FROM `tabBiometric Sync Log`
		WHERE `{unit_col}` = %(unit)s
		  AND sync_date BETWEEN %(from_date)s AND %(to_date)s
		  AND server_type = %(server_type)s
		ORDER BY sync_date DESC, modified DESC
		""".format(unit_col=unit_col),
		{"unit": unit, "from_date": from_date, "to_date": to_date, "server_type": server_type},
		as_dict=True,
	)

	# Deduplicate to latest log per calendar date
	seen: set = set()
	unique_logs = []
	for r in logs:
		d = str(r.sync_date)
		if d not in seen:
			seen.add(d)
			unique_logs.append(r)

	rows = []
	for r in unique_logs:
		status   = _row_status(r)
		total    = r.employees_total or 0
		unmapped = r.employees_not_found or 0
		errored  = r.errored_count or 0

		progress = None
		if total:
			clean    = max(total - unmapped - errored, 0)
			progress = round(clean / total * 100, 1)

		rows.append(
			{
				"log_name":          r.name,
				"sync_date":         str(r.sync_date),
				"status":            status,
				"raw_records":       r.total_records_received or 0,
				"total":             total,
				"created":           r.checkins_created  or 0,
				"skipped":           r.checkins_skipped  or 0,
				"unmapped_employees": unmapped,
				"errored":           errored,
				"progress":          progress,
				"has_response_data": bool(r.has_response_data),
			}
		)

	from_d = getdate(from_date)
	to_d   = getdate(to_date)

	summary = {
		"days_in_range":      (to_d - from_d).days + 1,
		"days_synced":        len(rows),
		"days_ok":            sum(1 for r in rows if r["status"] == "success"),
		"total_raw_records":  sum(r["raw_records"] for r in rows),
		"employees_total":    sum(r["total"] for r in rows),
		"created":            sum(r["created"] for r in rows),
		"skipped":            sum(r["skipped"] for r in rows),
		"unmapped":           sum(r["unmapped_employees"] for r in rows),
		"errored":            sum(r["errored"] for r in rows),
	}

	return {
		"server_type": server_type,
		"unit": unit,
		"summary": summary,
		"rows": rows,
	}


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_log_detail(log_name):
	"""Full log metadata for the detail drawer — uses direct columns, no JSON parse for counts."""
	frappe.only_for("System Manager")

	doc     = frappe.get_doc("Biometric Sync Log", log_name)
	summary = {}
	if doc.sync_summary:
		try:
			summary = json.loads(doc.sync_summary)
		except Exception:
			pass

	unit = doc.location if doc.server_type == "Bio Server" else doc.serial_no

	checkins_by_employee = []
	if unit and doc.sync_date:
		checkins_by_employee = frappe.db.sql(
			"""
			SELECT
				ec.employee,
				e.employee_name,
				COUNT(*) AS total,
				SUM(CASE WHEN ec.log_type = 'IN'  THEN 1 ELSE 0 END) AS in_count,
				SUM(CASE WHEN ec.log_type = 'OUT' THEN 1 ELSE 0 END) AS out_count
			FROM `tabEmployee Checkin` ec
			JOIN `tabEmployee` e ON e.name = ec.employee
			WHERE ec.device_id = %(unit)s AND DATE(ec.time) = %(sync_date)s
			GROUP BY ec.employee, e.employee_name
			ORDER BY total DESC
			""",
			{"unit": unit, "sync_date": doc.sync_date},
			as_dict=True,
		)

	return {
		"name": doc.name,
		"status": doc.status,
		"server_type": doc.server_type,
		"location": doc.location,
		"serial_no": doc.serial_no,
		"sync_date": str(doc.sync_date) if doc.sync_date else None,
		"last_sync_datetime": str(doc.last_sync_datetime) if doc.last_sync_datetime else None,
		"is_missing_date_sync": doc.is_missing_date_sync,
		# --- direct columns (no JSON parsing needed for counts) ---
		"total_records_received": doc.total_records_received or 0,
		"employees_total":        doc.employees_total        or 0,
		"checkins_created":       doc.checkins_created       or 0,
		"checkins_skipped":       doc.checkins_skipped       or 0,
		"employees_not_found":    doc.employees_not_found    or 0,
		"errored_count":          doc.errored_count          or 0,
		"skipped_inactive":       doc.skipped_inactive       or 0,
		"has_response_data": bool(doc.response_data),
		# --- lists from summary (needed for detail drawer chips) ---
		"summary": summary,
		# --- per-employee checkin breakdown for this unit + date ---
		"checkins_by_employee": checkins_by_employee,
	}


# ---------------------------------------------------------------------------
# Employee mapping & employee-centric history
# ---------------------------------------------------------------------------


@frappe.whitelist()
def search_employees(txt="", only_unmapped=False):
	"""Search employees for the Quick Map modal / Employee tab autocomplete."""
	frappe.only_for("System Manager")

	if isinstance(only_unmapped, str):
		only_unmapped = only_unmapped.lower() in ("1", "true", "yes")

	filters = {}
	if only_unmapped:
		filters["attendance_device_id"] = ["in", ["", None]]

	or_filters = None
	if txt:
		or_filters = {
			"employee_name": ["like", f"%{txt}%"],
			"name": ["like", f"%{txt}%"],
		}

	return frappe.get_list(
		"Employee",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "employee_name", "department", "attendance_device_id", "status"],
		limit=20,
		order_by="employee_name asc",
	)


@frappe.whitelist()
def map_device_id(device_id, employee):
	"""Map an unmapped device ID to an Employee's attendance_device_id."""
	frappe.only_for("System Manager")

	existing = frappe.db.get_value("Employee", {"attendance_device_id": device_id})
	if existing and existing != employee:
		frappe.throw(_("Device ID {0} is already mapped to employee {1}").format(device_id, existing))

	frappe.db.set_value("Employee", employee, "attendance_device_id", device_id)
	return {"employee": employee, "device_id": device_id}


@frappe.whitelist()
def get_employee_history(employee, from_date, to_date):
	"""
	Per-employee daily checkin breakdown for a date range, plus sync-issue
	flags derived from Biometric Sync Log summaries for the employee's
	mapped device ID.
	"""
	frappe.only_for("System Manager")

	emp = frappe.db.get_value(
		"Employee", employee, ["employee_name", "attendance_device_id"], as_dict=True
	)
	if not emp:
		frappe.throw(_("Employee {0} not found").format(employee))

	_s, server_type, _unit_col, _all_units = _settings()

	checkins = frappe.db.sql(
		"""
		SELECT time, log_type, device_id
		FROM `tabEmployee Checkin`
		WHERE employee = %(employee)s
		  AND DATE(time) BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY time ASC
		""",
		{"employee": employee, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	by_date = {}
	for c in checkins:
		d = str(getdate(c.time))
		by_date.setdefault(d, []).append(
			{"time": str(c.time), "log_type": c.log_type, "device_id": c.device_id}
		)

	# Sync-issue lookup: scan logs for the employee's device ID in the date range
	issue_by_date = {}
	if emp.attendance_device_id:
		logs = frappe.db.sql(
			"""
			SELECT name, sync_date, sync_summary
			FROM `tabBiometric Sync Log`
			WHERE sync_date BETWEEN %(from_date)s AND %(to_date)s
			  AND server_type = %(server_type)s
			ORDER BY sync_date ASC, modified DESC
			""",
			{"from_date": from_date, "to_date": to_date, "server_type": server_type},
			as_dict=True,
		)
		seen_dates = set()
		for log in logs:
			d = str(log.sync_date)
			if d in seen_dates:
				continue
			if not log.sync_summary:
				continue
			try:
				s = json.loads(log.sync_summary)
			except Exception:
				continue
			device_id = emp.attendance_device_id
			if device_id in (s.get("skipped_no_employee") or []) or device_id in (
				s.get("errored_employees") or []
			):
				issue_by_date[d] = log.name
				seen_dates.add(d)

	from_d = getdate(from_date)
	to_d   = getdate(to_date)

	rows = []
	d = from_d
	while d <= to_d:
		key = str(d)
		rows.append(
			{
				"date": key,
				"checkins": by_date.get(key, []),
				"sync_issue": key in issue_by_date,
				"log_name": issue_by_date.get(key),
			}
		)
		d = add_days(d, 1)

	summary = {
		"days_in_range": (to_d - from_d).days + 1,
		"days_with_checkin": sum(1 for r in rows if r["checkins"]),
		"total_checkins": sum(len(r["checkins"]) for r in rows),
		"sync_issue_days": sum(1 for r in rows if r["sync_issue"]),
	}

	return {
		"employee": employee,
		"employee_name": emp.employee_name,
		"attendance_device_id": emp.attendance_device_id or None,
		"summary": summary,
		"rows": rows,
	}


@frappe.whitelist()
def retry_api(log_name):
	"""
	Re-fetches exactly ONE day's data for a failed log.
	Always uses is_missing_date=True with the log's original sync_date so the
	device API is called for that specific day only — never pulls a backlog.
	"""
	frappe.only_for("System Manager")

	doc = frappe.get_doc("Biometric Sync Log", log_name)
	if not doc.sync_date:
		frappe.throw(_("Cannot retry: log has no sync_date."))

	settings    = frappe.get_single("Biometric Sync Settings")
	server_type = settings.server_type or "Bio Server"

	kwargs = (
		{"location": doc.location, "sync_date": str(doc.sync_date), "is_missing_date": True}
		if server_type == "Bio Server"
		else {"serial_no": doc.serial_no, "sync_date": str(doc.sync_date), "is_missing_date": True}
	)

	frappe.enqueue(method=run_sync_job, **kwargs, queue="short", timeout=3500, is_async=True)
	doc.db_set("status", "Queued")
	return "Queued"


@frappe.whitelist()
def retry_checkin_creation(log_name):
	"""
	Re-processes stored response_data to create checkins without re-hitting the device.
	Safe to call multiple times — duplicate-skip logic prevents double creation.
	"""
	frappe.only_for("System Manager")

	doc = frappe.get_doc("Biometric Sync Log", log_name)

	if not doc.response_data:
		frappe.throw(_("No stored response data to re-process."))

	if doc.status == "Error":
		frappe.throw(
			_("This log recorded an API failure — use 'Retry API' to re-fetch data from the device.")
		)

	stats = _process_response(doc.server_type, doc.response_data, serial_no=doc.serial_no or None)

	doc.employees_total     = stats.get("employees_total", 0)
	doc.checkins_created    = (doc.checkins_created or 0) + stats.get("created", 0)
	doc.checkins_skipped    = (doc.checkins_skipped or 0) + stats.get("skipped_duplicate", 0)
	doc.employees_not_found = len(stats.get("skipped_no_employee", []))
	doc.errored_count       = len(stats.get("errored_employees", []))
	doc.skipped_inactive    = len(stats.get("skipped_inactive", []))
	doc.sync_summary        = json.dumps(stats, separators=(",", ":"))
	doc.save(ignore_permissions=True)

	return {
		"created":            stats.get("created", 0),
		"skipped_duplicate":  stats.get("skipped_duplicate", 0),
		"employees_not_found": doc.employees_not_found,
		"errored_count":       doc.errored_count,
	}


@frappe.whitelist()
def trigger_missing_date_sync(unit, sync_date):
	"""
	Enqueues a single-day sync for a unit that has no log for sync_date.
	Uses is_missing_date=True — does NOT advance the settings last_sync pointer.
	"""
	frappe.only_for("System Manager")

	settings    = frappe.get_single("Biometric Sync Settings")
	server_type = settings.server_type or "Bio Server"

	kwargs = (
		{"location": unit, "sync_date": sync_date, "is_missing_date": True}
		if server_type == "Bio Server"
		else {"serial_no": unit, "sync_date": sync_date, "is_missing_date": True}
	)

	frappe.enqueue(method=run_sync_job, **kwargs, queue="short", timeout=3500, is_async=True)
	return _("Single-day sync queued for {0} on {1}.").format(unit, sync_date)
