# 🕒 Biometric Integration for ERPNext

Automatically sync biometric attendance logs into ERPNext. Reduce manual work, eliminate errors, and maintain accurate employee check-ins for HR and payroll.

---

## ⭐ Why This App?

- **Stop manual attendance entry** — Biometric punches are imported automatically into ERPNext.  
- **Improve payroll accuracy** — Verified device events reduce mismatches and buddy-punching.  
- **Easy to operate** — Register devices, map users, schedule syncs, and monitor logs from one screen.  
- **Retry & auditing** — Failed imports can be retried from the sync log with full request/response visibility.

---

## 🌐 Key Features

- **Automated Biometric Log Sync**  
  Fetch attendance logs from your biometric device at scheduled intervals or on-demand.

- **Biometric Sync Settings**  
  Configure device URL, credentials, sync schedule, and employee mapping rules from one screen.

- **Supports Multiple Devices**  
  Manage more than one biometric machine with consistent processing logic.

- **Employee Mapping Engine**  
  Maps device user IDs to ERPNext Employee records with error handling for unmapped IDs.

- **Attendance or Check-in Creation**  
  Create ERPNext Attendance or Check-in entries based on your HR settings.

- **Detailed Sync Logs**  
  Every sync run is logged with timestamps, record counts, messages, and any errors.

- **Manual “Sync Now” Option**  
  HR teams can trigger a manual sync whenever needed.

- **Duplicate Prevention**  
  Delta/last-seen syncing prevents duplicate imports on re-runs.

---

## 🧠 How It Works (High Level)

1. Configure your device URL, username, and password.  
2. Map biometric user IDs to ERPNext employees.  
3. Scheduler automatically triggers sync jobs.  
4. The app fetches logs from the biometric device.  
5. Logs are converted into Attendance or Check-ins in ERPNext.  
6. A Sync Log entry is created for auditing and retries.

---

## 🔧 Installation

### Via bench (self-hosted)

```bash
bench get-app https://github.com/Akhilam-Inc/biometric_integration
bench --site your-site-name install-app biometric_integration
```

### From marketplace / cloud  
Install the app directly from **Frappe Cloud / ERPNext Marketplace** (if listed).  
Search for **“Biometric Integration”**, click **Install**, and assign it to your site.

---

## ⚙️ Configuration Steps

1. Open **Biometric Sync Settings** in your ERPNext site.  
2. Add a device entry (name, base URL/IP, port, username, password).  
3. Test the connection to confirm device API access.  
4. Ensure employees have biometric user IDs (or upload a CSV mapping).  
5. Set the automatic sync interval (hourly/daily/custom).  
6. Use **Sync Now** to perform a manual test import.  
7. Monitor Sync Logs and verify created Attendance/Check-in entries.

---

## 👥 Who Is It For?

- HR Managers  
- Payroll Teams  
- Factory & Warehouse Operations  
- Multi-location Companies  
- ERPNext Administrators

---

## 🧩 Use Cases

- Automating daily attendance capture for office & factory staff.  
- Preparing timesheets and payroll with reliable check-ins.  
- Consolidating punches from multiple devices at different sites.  
- Monitoring shift start/end times and overtime.  
- Removing spreadsheet-based attendance workflows.

---

## 📌 Troubleshooting & Tips

- **Device unreachable**: Confirm network access (IP/port) and credentials. Ensure the device API is enabled.  
- **Duplicate imports**: Check last-seen sync timestamps; verify device timezone.  
- **Unmapped IDs**: Update biometric → employee mapping and retry failed logs.  
- **Slow imports**: Enable incremental sync or increase batch size if supported.  
- **Auth errors**: Revalidate device credentials or token settings.

---

## 🔒 Security & Data Handling

- Credentials stored in secure fields.  
- API communication uses authenticated requests (HTTPS recommended).  
- Sync Logs stored for audit and debugging.  
- No external sharing of attendance data.  
- Access controlled via ERPNext user permissions.

---

## 📦 Requirements

- ERPNext (v13+ recommended)  
- Biometric device with accessible API/endpoint  
- Employee biometric IDs mapped in ERPNext  
- Admin permissions for installation & configuration

---

## 🛠 Support

📩 **Email:** support@akhilaminc.com  
Professional help available for installation, device testing, and custom logic.

---

## 📝 License

MIT License  
© 2025 Akhilam Inc

---

## ❤️ Made by Akhilam Inc  
Automation solutions for modern businesses.