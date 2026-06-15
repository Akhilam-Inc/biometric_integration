<template>
	<div class="bsd-root">
		<!-- ───────────────────────── HEADER ───────────────────────── -->
		<div class="bsd-header">
			<!-- Left: title + subtitle row -->
			<div class="bsd-header-left">
				<div class="bsd-title-row">
					<h2 class="bsd-title">Biometric Sync Dashboard</h2>
					<span v-if="dashData" class="bsd-server-badge" :class="serverBadgeClass">
						{{ dashData.server_type }}
					</span>
				</div>
				<div class="bsd-header-sub">
					<span v-if="dashData?.last_sync_datetime" class="bsd-last-sync">
						Last sync: {{ fmtDatetime(dashData.last_sync_datetime) }}
					</span>
					<span v-else class="bsd-last-sync bsd-last-sync-dim">
						{{ loading ? "Syncing…" : "No sync info available" }}
					</span>
				</div>
			</div>

			<!-- Right: date control + settings -->
			<div class="bsd-header-right">
				<div v-if="activeTab === 'daily'" class="bsd-date-control">
					<span class="bsd-date-control-label">Sync Date</span>
					<input
						type="date"
						v-model="syncDate"
						@change="loadAll"
						class="bsd-date-input"
					/>
				</div>
				<button class="bsd-settings-btn" @click="openSettings">
					<svg
						width="13"
						height="13"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
					>
						<circle cx="12" cy="12" r="3" />
						<path
							d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
						/>
					</svg>
					Settings
				</button>
			</div>
		</div>

		<!-- ──────────────────────── TAB BAR ────────────────────────── -->
		<div class="bsd-tab-bar">
			<button
				:class="['bsd-tab', { active: activeTab === 'daily' }]"
				@click="activeTab = 'daily'"
			>
				Daily View
			</button>
			<button
				:class="['bsd-tab', { active: activeTab === 'unit' }]"
				@click="activeTab = 'unit'"
			>
				Location / Serial No
			</button>
			<button
				:class="['bsd-tab', { active: activeTab === 'employee' }]"
				@click="activeTab = 'employee'"
			>
				Employee View
			</button>
		</div>

		<!-- ════════════════════════ TAB 1: DAILY VIEW ════════════════ -->
		<template v-if="activeTab === 'daily'">
			<div v-if="loading" class="bsd-loading">
				<div class="bsd-spinner"></div>
				<span>Loading dashboard…</span>
			</div>

			<template v-else-if="dashData">
				<!-- ─────────────────────── KPI CARDS ─────────────────────── -->
				<div class="bsd-kpi-row">
					<!-- Card 1: Raw device records received -->
					<div
						class="bsd-kpi-card"
						:class="{ active: activeFilter === 'raw_records' }"
						@click="toggleFilter('raw_records')"
						:title="
							isEtime
								? 'Raw tab-delimited lines received from device'
								: 'Total raw punch events received from device'
						"
					>
						<div class="bsd-kpi-icon punch">⬡</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ (dashData.kpis.raw_records || 0).toLocaleString() }}
							</div>
							<div class="bsd-kpi-label">Device Records</div>
							<div class="bsd-kpi-sub" v-if="isEtime">
								{{ (dashData.kpis.total || 0).toLocaleString() }} unique employees
							</div>
							<div class="bsd-kpi-sub" v-else>Raw Punch Events</div>
						</div>
					</div>

					<!-- Card 2: Checkins created -->
					<div
						class="bsd-kpi-card"
						:class="{ active: activeFilter === 'created' }"
						@click="toggleFilter('created')"
						title="ERP Employee Checkin records successfully created"
					>
						<div class="bsd-kpi-icon created">✓</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ (dashData.kpis.created || 0).toLocaleString() }}
							</div>
							<div class="bsd-kpi-label">Checkins Created</div>
							<div class="bsd-kpi-sub">ERP Records</div>
						</div>
					</div>

					<!-- Card 3: Duplicates skipped -->
					<div
						class="bsd-kpi-card"
						:class="{ active: activeFilter === 'skipped' }"
						@click="toggleFilter('skipped')"
						title="Duplicate punch events skipped — already exist in ERP"
					>
						<div class="bsd-kpi-icon skipped">⟳</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ (dashData.kpis.skipped || 0).toLocaleString() }}
							</div>
							<div class="bsd-kpi-label">Duplicates Skipped</div>
							<div class="bsd-kpi-sub">
								{{ isEtime ? "Checkin Records" : "Punch Records" }}
							</div>
						</div>
					</div>

					<!-- Card 4: Unmapped employees -->
					<div
						class="bsd-kpi-card warn"
						:class="{ active: activeFilter === 'unmapped' }"
						@click="toggleFilter('unmapped')"
						title="Unique employees whose device ID is not mapped to any Employee in ERP"
					>
						<div class="bsd-kpi-icon unmapped">!</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ (dashData.kpis.unmapped_employees || 0).toLocaleString() }}
							</div>
							<div class="bsd-kpi-label">Unmapped Employees</div>
							<div class="bsd-kpi-sub">Employee Count</div>
						</div>
					</div>

					<!-- Card 5: Insert errors -->
					<div
						class="bsd-kpi-card error"
						:class="{ active: activeFilter === 'errored' }"
						@click="toggleFilter('errored')"
						title="Employees that were matched but threw insert errors during checkin creation"
					>
						<div class="bsd-kpi-icon api-err">✕</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ (dashData.kpis.errored || 0).toLocaleString() }}
							</div>
							<div class="bsd-kpi-label">Insert Errors</div>
							<div class="bsd-kpi-sub">Employee Count</div>
						</div>
					</div>

					<!-- Card 6: Locations healthy -->
					<div
						class="bsd-kpi-card healthy"
						:class="{ active: activeFilter === 'success' }"
						@click="toggleFilter('success')"
						title="Locations synced with zero unmapped or errored employees"
					>
						<div class="bsd-kpi-icon loc-ok">✓</div>
						<div class="bsd-kpi-body">
							<div class="bsd-kpi-value">
								{{ dashData.kpis.locations_healthy }}
								<span class="bsd-kpi-total"
									>/ {{ dashData.kpis.locations_total }}</span
								>
							</div>
							<div class="bsd-kpi-label">Locations Healthy</div>
							<div class="bsd-kpi-sub">Unit Count</div>
						</div>
					</div>
				</div>

				<!-- KPI legend + active filter badge -->
				<div class="bsd-kpi-legend">
					<span class="bsd-legend-group records"
						>◼ {{ isEtime ? "Employee" : "Punch" }} Record metrics</span
					>
					<span class="bsd-legend-group employees">◼ Employee issue metrics</span>
					<span
						v-if="activeFilter"
						class="bsd-filter-badge"
						@click="activeFilter = null"
					>
						Filtering: {{ filterLabel }} &times;
					</span>
				</div>

				<!-- ─────────────────────── LOCATION TABLE ────────────────── -->
				<div class="bsd-card bsd-table-card">
					<div class="bsd-card-header">
						<h4>Location / Device Status</h4>
						<div class="bsd-table-meta">
							{{ filteredRows.length }} of {{ dashData.table_rows.length }} units ·
							{{ syncDate }}
						</div>
					</div>

					<div class="bsd-table-wrap">
						<table class="bsd-table">
							<thead>
								<tr>
									<th class="col-dot"></th>
									<th class="col-unit sortable" @click="sort('unit')">
										{{ isEtime ? "Serial No" : "Location" }}
										<sort-icon
											col="unit"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th class="sortable" @click="sort('status')">
										Status
										<sort-icon
											col="status"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('raw_records')"
										title="Raw device records / lines received"
									>
										Raw Records
										<sort-icon
											col="raw_records"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('total')"
										:title="
											isEtime
												? 'Unique employees in device response'
												: 'Total punch events received from device'
										"
									>
										{{ isEtime ? "Employees" : "Punches" }}
										<sort-icon
											col="total"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('created')"
										title="ERP Employee Checkin records created"
									>
										Checkins
										<sort-icon
											col="created"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('skipped')"
										title="Duplicate checkins skipped"
									>
										Dupes
										<sort-icon
											col="skipped"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('unmapped_employees')"
										title="Unique employees whose device ID is not mapped in ERP (employee count)"
									>
										Unmapped
										<sort-icon
											col="unmapped_employees"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="sortable num-col"
										@click="sort('errored')"
										title="Employees that matched but threw insert errors (employee count)"
									>
										Errored
										<sort-icon
											col="errored"
											:sort-key="sortKey"
											:sort-dir="sortDir"
										/>
									</th>
									<th
										class="col-progress"
										:title="`Clean rate: (${
											isEtime ? 'Employees' : 'Punches'
										} − Unmapped − Errored) / Total`"
									>
										Progress
									</th>
									<th class="col-actions">Actions</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in filteredRows"
									:key="row.unit"
									:class="['bsd-row', `bsd-row-${row.status}`]"
								>
									<td class="col-dot">
										<span class="bsd-dot" :class="`dot-${row.status}`"></span>
									</td>

									<td class="bsd-unit-cell">
										<span class="bsd-unit-name">{{ row.unit }}</span>
										<a
											v-if="row.log_name"
											:href="`/app/biometric-sync-log/${row.log_name}`"
											target="_blank"
											class="bsd-log-link"
											>{{ row.log_name }} ↗</a
										>
									</td>

									<td>
										<span class="bsd-pill" :class="`pill-${row.status}`">
											{{ statusLabel(row.status) }}
										</span>
									</td>

									<!-- total_records_received -->
									<td class="num-col">
										<span v-if="row.raw_records != null">{{
											row.raw_records.toLocaleString()
										}}</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- employees_total -->
									<td class="num-col">
										<span v-if="row.total != null">{{
											row.total.toLocaleString()
										}}</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- checkins_created -->
									<td class="num-col">
										<span v-if="row.created != null">{{
											row.created.toLocaleString()
										}}</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- checkins_skipped (duplicates) -->
									<td class="num-col">
										<span v-if="row.skipped != null">{{
											row.skipped.toLocaleString()
										}}</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- employees_not_found — employee count -->
									<td
										class="num-col"
										:class="{ 'num-warn': (row.unmapped_employees || 0) > 0 }"
									>
										<span v-if="row.unmapped_employees != null">
											{{ row.unmapped_employees.toLocaleString() }}
											<span
												v-if="row.unmapped_employees > 0"
												class="num-unit"
												>emp</span
											>
										</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- errored_count -->
									<td
										class="num-col"
										:class="{ 'num-error': (row.errored || 0) > 0 }"
									>
										<span v-if="row.errored != null">
											{{ row.errored.toLocaleString() }}
											<span v-if="row.errored > 0" class="num-unit"
												>emp</span
											>
										</span>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- progress -->
									<td class="col-progress">
										<template v-if="row.progress != null">
											<div class="bsd-prog-wrap">
												<div class="bsd-prog-bar">
													<div
														class="bsd-prog-fill"
														:class="progressClass(row.progress)"
														:style="{ width: row.progress + '%' }"
													></div>
												</div>
												<span class="bsd-prog-pct"
													>{{ row.progress }}%</span
												>
											</div>
											<div class="bsd-prog-caption">Clean / Total</div>
										</template>
										<span v-else class="bsd-nil">—</span>
									</td>

									<!-- action buttons -->
									<td class="col-actions">
										<button
											v-if="row.status === 'missing'"
											class="bsd-action-btn trigger"
											@click="triggerMissing(row)"
											title="Trigger single-day sync for this date"
										>
											Sync
										</button>
										<button
											v-else-if="row.status === 'error'"
											class="bsd-action-btn retry"
											@click="doRetryApi(row)"
											title="Re-fetch this date's data from the device (1 day only)"
										>
											Retry API
										</button>
										<button
											v-if="row.log_name && row.status !== 'missing'"
											class="bsd-action-btn detail"
											@click="openDrawer(row)"
											title="View log details"
										>
											Detail
										</button>
									</td>
								</tr>

								<tr v-if="filteredRows.length === 0">
									<td colspan="11" class="bsd-empty">
										{{
											activeFilter
												? "No units match the current filter."
												: "No sync data for this date."
										}}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<!-- ─────────────────────── CHARTS ROW ───────────────────── -->
				<div class="bsd-charts-row">
					<div class="bsd-card bsd-chart-card">
						<div class="bsd-card-header">
							<h4>7-Day Trend</h4>
							<span class="bsd-chart-sub">Device Records vs Checkins Created</span>
						</div>
						<div ref="trendChartEl" class="bsd-chart-area"></div>
						<div v-if="!trendData?.labels?.length" class="bsd-chart-empty">
							No trend data available
						</div>
					</div>

					<div class="bsd-card bsd-chart-card">
						<div class="bsd-card-header">
							<h4>Failure Breakdown</h4>
							<span class="bsd-chart-sub">{{ syncDate }}</span>
						</div>
						<div v-if="failureData?.length" class="bsd-failure-list">
							<div
								v-for="item in failureData"
								:key="item.category"
								class="bsd-failure-row"
							>
								<span class="bsd-failure-label">{{ item.category }}</span>
								<div class="bsd-failure-bar-wrap">
									<div
										class="bsd-failure-bar"
										:style="{ width: failureBarWidth(item.count) + '%' }"
									></div>
								</div>
								<span class="bsd-failure-count">{{ item.count }}</span>
							</div>
						</div>
						<div v-else class="bsd-chart-empty">No failures on this date</div>
					</div>
				</div>
			</template>
		</template>
		<!-- ════ END TAB 1 ════════════════════════════════════════════ -->

		<!-- ════════════════════════ TAB 2: UNIT HISTORY ═════════════ -->
		<template v-else-if="activeTab === 'unit'">
			<!-- Unit + date range filter bar -->
			<div class="bsd-unit-filter-bar">
				<div class="bsd-filter-group">
					<label>{{ isEtime ? "Serial No" : "Location" }}</label>
					<select v-model="unitFilter" class="bsd-select">
						<option value="">— Select Unit —</option>
						<option v-for="u in unitsList" :key="u" :value="u">{{ u }}</option>
					</select>
				</div>
				<div class="bsd-filter-group">
					<label>From Date</label>
					<input type="date" v-model="unitFromDate" class="bsd-date-input" />
				</div>
				<div class="bsd-filter-group">
					<label>To Date</label>
					<input type="date" v-model="unitToDate" class="bsd-date-input" />
				</div>
				<button
					class="bsd-btn-primary bsd-load-btn"
					@click="loadUnitHistory"
					:disabled="!unitFilter || unitLoading"
				>
					{{ unitLoading ? "Loading…" : "Load History" }}
				</button>
			</div>

			<div v-if="unitLoading" class="bsd-loading">
				<div class="bsd-spinner"></div>
				<span>Loading history…</span>
			</div>

			<template v-else-if="unitHistory">
				<!-- Summary stats strip -->
				<div class="bsd-unit-summary-bar">
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">{{ unitHistory.summary.days_in_range }}</div>
						<div class="bsd-sum-label">Days in Range</div>
					</div>
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">{{ unitHistory.summary.days_synced }}</div>
						<div class="bsd-sum-label">Days Synced</div>
					</div>
					<div class="bsd-sum-stat ok">
						<div class="bsd-sum-value">{{ unitHistory.summary.days_ok }}</div>
						<div class="bsd-sum-label">Days OK</div>
					</div>
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">
							{{ unitHistory.summary.total_raw_records.toLocaleString() }}
						</div>
						<div class="bsd-sum-label">Total Raw Records</div>
					</div>
					<div class="bsd-sum-stat" v-if="isEtime">
						<div class="bsd-sum-value">
							{{ unitHistory.summary.employees_total.toLocaleString() }}
						</div>
						<div class="bsd-sum-label">Total Employees</div>
					</div>
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">
							{{ unitHistory.summary.created.toLocaleString() }}
						</div>
						<div class="bsd-sum-label">Checkins Created</div>
					</div>
					<div class="bsd-sum-stat warn" v-if="unitHistory.summary.unmapped > 0">
						<div class="bsd-sum-value">{{ unitHistory.summary.unmapped }}</div>
						<div class="bsd-sum-label">Unmapped Emp</div>
					</div>
					<div class="bsd-sum-stat error" v-if="unitHistory.summary.errored > 0">
						<div class="bsd-sum-value">{{ unitHistory.summary.errored }}</div>
						<div class="bsd-sum-label">Errored</div>
					</div>
				</div>

				<!-- Daily breakdown table -->
				<div class="bsd-card bsd-table-card">
					<div class="bsd-card-header">
						<h4>{{ unitHistory.unit }} — Daily Breakdown</h4>
						<div class="bsd-table-meta">
							{{ unitHistory.rows.length }} days · {{ unitFromDate }} to
							{{ unitToDate }}
						</div>
					</div>
					<div class="bsd-table-wrap">
						<table class="bsd-table">
							<thead>
								<tr>
									<th class="col-dot"></th>
									<th>Date</th>
									<th>Status</th>
									<th
										class="num-col"
										title="Raw device records / lines received"
									>
										Raw Records
									</th>
									<th
										class="num-col"
										:title="
											isEtime
												? 'Unique employees in response'
												: 'Punch events received'
										"
									>
										{{ isEtime ? "Employees" : "Punches" }}
									</th>
									<th class="num-col" title="ERP checkins created">Checkins</th>
									<th class="num-col" title="Duplicate checkins skipped">
										Dupes
									</th>
									<th
										class="num-col"
										title="Unmapped employees (employee count)"
									>
										Unmapped
									</th>
									<th class="num-col" title="Insert errors (employee count)">
										Errored
									</th>
									<th class="col-progress">Progress</th>
									<th class="col-actions">Log</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in unitHistory.rows"
									:key="row.sync_date"
									:class="['bsd-row', `bsd-row-${row.status}`]"
								>
									<td class="col-dot">
										<span class="bsd-dot" :class="`dot-${row.status}`"></span>
									</td>
									<td class="bsd-date-cell">{{ row.sync_date }}</td>
									<td>
										<span class="bsd-pill" :class="`pill-${row.status}`">
											{{ statusLabel(row.status) }}
										</span>
									</td>
									<td class="num-col">
										{{ (row.raw_records || 0).toLocaleString() }}
									</td>
									<td class="num-col">
										{{ (row.total || 0).toLocaleString() }}
									</td>
									<td class="num-col">
										{{ (row.created || 0).toLocaleString() }}
									</td>
									<td class="num-col">
										{{ (row.skipped || 0).toLocaleString() }}
									</td>
									<td
										class="num-col"
										:class="{ 'num-warn': (row.unmapped_employees || 0) > 0 }"
									>
										{{ (row.unmapped_employees || 0).toLocaleString() }}
									</td>
									<td
										class="num-col"
										:class="{ 'num-error': (row.errored || 0) > 0 }"
									>
										{{ (row.errored || 0).toLocaleString() }}
									</td>
									<td class="col-progress">
										<template v-if="row.progress != null">
											<div class="bsd-prog-wrap">
												<div class="bsd-prog-bar">
													<div
														class="bsd-prog-fill"
														:class="progressClass(row.progress)"
														:style="{ width: row.progress + '%' }"
													></div>
												</div>
												<span class="bsd-prog-pct"
													>{{ row.progress }}%</span
												>
											</div>
										</template>
										<span v-else class="bsd-nil">—</span>
									</td>
									<td class="col-actions">
										<a
											v-if="row.log_name"
											:href="`/app/biometric-sync-log/${row.log_name}`"
											target="_blank"
											class="bsd-action-btn detail"
										>
											Open ↗
										</a>
									</td>
								</tr>
								<tr v-if="unitHistory.rows.length === 0">
									<td colspan="11" class="bsd-empty">
										No logs found for this unit in the selected range.
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</template>

			<div v-else-if="!unitLoading && !unitHistory" class="bsd-tab2-hint">
				Select a {{ isEtime ? "serial no" : "location" }} and date range, then click
				<strong>Load History</strong> to view the daily breakdown.
			</div>
		</template>
		<!-- ════ END TAB 2 ════════════════════════════════════════════ -->

		<!-- ════════════════════════ TAB 3: EMPLOYEE VIEW ═════════════ -->
		<template v-else-if="activeTab === 'employee'">
			<!-- Employee + date range filter bar -->
			<div class="bsd-unit-filter-bar">
				<div class="bsd-filter-group">
					<label>Employee</label>
					<button class="bsd-select bsd-emp-picker" @click="empSearchOpen = true">
						<span v-if="empFilter"
							>{{ empFilter.employee_name }} ({{ empFilter.name }})</span
						>
						<span v-else class="bsd-nil">— Select Employee —</span>
					</button>
				</div>
				<div class="bsd-filter-group">
					<label>From Date</label>
					<input type="date" v-model="empFromDate" class="bsd-date-input" />
				</div>
				<div class="bsd-filter-group">
					<label>To Date</label>
					<input type="date" v-model="empToDate" class="bsd-date-input" />
				</div>
				<button
					class="bsd-btn-primary bsd-load-btn"
					@click="loadEmployeeHistory"
					:disabled="!empFilter || empLoading"
				>
					{{ empLoading ? "Loading…" : "Load History" }}
				</button>
			</div>

			<div v-if="empLoading" class="bsd-loading">
				<div class="bsd-spinner"></div>
				<span>Loading employee history…</span>
			</div>

			<template v-else-if="empHistory">
				<!-- Employee header strip -->
				<div class="bsd-card bsd-emp-header-card">
					<div class="bsd-emp-header-main">
						<div class="bsd-emp-header-name">{{ empHistory.employee_name }}</div>
						<div class="bsd-emp-header-id">{{ empHistory.employee }}</div>
					</div>
					<div class="bsd-emp-header-device">
						<span v-if="empHistory.attendance_device_id" class="bsd-pill pill-success">
							Device ID: {{ empHistory.attendance_device_id }}
						</span>
						<template v-else>
							<span class="bsd-pill pill-warning">Not Mapped</span>
							<button class="bsd-action-btn trigger" @click="openMapModal(null)">
								Map Device ID
							</button>
						</template>
					</div>
				</div>

				<!-- Summary stats strip -->
				<div class="bsd-unit-summary-bar">
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">{{ empHistory.summary.days_in_range }}</div>
						<div class="bsd-sum-label">Days in Range</div>
					</div>
					<div class="bsd-sum-stat ok">
						<div class="bsd-sum-value">{{ empHistory.summary.days_with_checkin }}</div>
						<div class="bsd-sum-label">Days With Checkins</div>
					</div>
					<div class="bsd-sum-stat">
						<div class="bsd-sum-value">{{ empHistory.summary.total_checkins }}</div>
						<div class="bsd-sum-label">Total Checkins</div>
					</div>
					<div class="bsd-sum-stat warn" v-if="empHistory.summary.sync_issue_days > 0">
						<div class="bsd-sum-value">{{ empHistory.summary.sync_issue_days }}</div>
						<div class="bsd-sum-label">Sync Issue Days</div>
					</div>
				</div>

				<!-- Daily breakdown table -->
				<div class="bsd-card bsd-table-card">
					<div class="bsd-card-header">
						<h4>Daily Checkin Breakdown</h4>
						<div class="bsd-table-meta">
							{{ empHistory.rows.length }} days · {{ empFromDate }} to
							{{ empToDate }}
						</div>
					</div>
					<div class="bsd-table-wrap">
						<table class="bsd-table">
							<thead>
								<tr>
									<th class="col-dot"></th>
									<th>Date</th>
									<th>Checkins</th>
									<th class="num-col">Count</th>
									<th>Sync Issue</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in empHistory.rows"
									:key="row.date"
									:class="['bsd-row', row.sync_issue ? 'bsd-row-warning' : '']"
								>
									<td class="col-dot">
										<span
											class="bsd-dot"
											:class="
												row.checkins.length ? 'dot-success' : 'dot-empty'
											"
										></span>
									</td>
									<td class="bsd-date-cell">{{ row.date }}</td>
									<td>
										<span v-if="row.checkins.length" class="bsd-tag-list">
											<span
												v-for="(c, i) in row.checkins"
												:key="i"
												class="bsd-tag"
												:class="
													c.log_type === 'OUT'
														? 'bsd-tag-out'
														: 'bsd-tag-in'
												"
											>
												{{ c.log_type }} {{ fmtTime(c.time) }}
											</span>
										</span>
										<span v-else class="bsd-nil">No checkins</span>
									</td>
									<td class="num-col">{{ row.checkins.length }}</td>
									<td>
										<a
											v-if="row.sync_issue && row.log_name"
											:href="`/app/biometric-sync-log/${row.log_name}`"
											target="_blank"
											class="bsd-pill pill-warning"
										>
											Issue ↗
										</a>
										<span v-else class="bsd-nil">—</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</template>

			<div v-else-if="!empLoading && !empHistory" class="bsd-tab2-hint">
				Select an employee and date range, then click <strong>Load History</strong>
				to view their daily checkin breakdown.
			</div>
		</template>
		<!-- ════ END TAB 3 ════════════════════════════════════════════ -->

		<!-- ─────────────────────────── DRAWER ───────────────────────── -->
		<Teleport to="body">
			<transition name="drawer-slide">
				<div v-if="drawerRow" class="bsd-drawer-overlay" @click.self="closeDrawer">
					<div class="bsd-drawer bsd-drawer-wide">
						<div class="bsd-drawer-header">
							<div>
								<strong>{{ drawerRow.unit }}</strong>
								<span
									class="bsd-pill"
									:class="`pill-${drawerRow.status}`"
									style="margin-left: 8px"
								>
									{{ statusLabel(drawerRow.status) }}
								</span>
							</div>
							<button class="bsd-drawer-close" @click="closeDrawer">✕</button>
						</div>

						<div v-if="drawerLoading" class="bsd-drawer-loading">
							<div class="bsd-spinner"></div>
						</div>

						<template v-else-if="drawerDetail">
							<!-- ── Drawer sub-tabs ── -->
							<div class="bsd-drawer-tabs">
								<button
									:class="[
										'bsd-drawer-tab',
										{ active: drawerTab === 'overview' },
									]"
									@click="drawerTab = 'overview'"
								>
									Overview
								</button>
								<button
									:class="['bsd-drawer-tab', { active: drawerTab === 'issues' }]"
									@click="drawerTab = 'issues'"
								>
									Issues
									<span v-if="drawerIssueCount" class="bsd-drawer-tab-badge">{{
										drawerIssueCount
									}}</span>
								</button>
								<button
									:class="[
										'bsd-drawer-tab',
										{ active: drawerTab === 'checkins' },
									]"
									@click="drawerTab = 'checkins'"
								>
									Checkins
								</button>
							</div>

							<div class="bsd-drawer-body">
								<!-- ════ OVERVIEW TAB ════ -->
								<template v-if="drawerTab === 'overview'">
									<div class="bsd-drawer-card">
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon punch">⬡</span>
											<span class="bsd-drawer-card-title">
												{{
													isEtime
														? "Employee Records (Device Response)"
														: "Punch Records (Device Response)"
												}}
											</span>
										</div>
										<div class="bsd-drawer-stats">
											<div class="bsd-stat-row">
												<span class="bsd-stat-label"
													>Raw Records Received</span
												>
												<span class="bsd-stat-value">{{
													drawerDetail.total_records_received.toLocaleString()
												}}</span>
											</div>
											<div class="bsd-stat-row">
												<span class="bsd-stat-label">
													{{
														isEtime
															? "Unique Employees in Response"
															: "Total Punch Events"
													}}
												</span>
												<span class="bsd-stat-value muted">{{
													drawerDetail.employees_total.toLocaleString()
												}}</span>
											</div>
										</div>
									</div>

									<div class="bsd-drawer-card">
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon created">✓</span>
											<span class="bsd-drawer-card-title"
												>ERP Processing Results</span
											>
										</div>
										<div class="bsd-drawer-stats">
											<div class="bsd-stat-row">
												<span class="bsd-stat-label"
													>Checkins Created</span
												>
												<span class="bsd-stat-value ok">{{
													drawerDetail.checkins_created.toLocaleString()
												}}</span>
											</div>
											<div class="bsd-stat-row">
												<span class="bsd-stat-label"
													>Duplicates Skipped</span
												>
												<span class="bsd-stat-value muted">{{
													drawerDetail.checkins_skipped.toLocaleString()
												}}</span>
											</div>
										</div>
									</div>

									<div class="bsd-drawer-card">
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon info">ℹ</span>
											<span class="bsd-drawer-card-title">Log Info</span>
										</div>
										<div class="bsd-drawer-meta">
											<div class="bsd-meta-row">
												<span>Log Name</span>
												<a
													:href="`/app/biometric-sync-log/${drawerDetail.name}`"
													target="_blank"
												>
													{{ drawerDetail.name }} ↗
												</a>
											</div>
											<div class="bsd-meta-row">
												<span>Sync Date</span
												><span>{{ drawerDetail.sync_date }}</span>
											</div>
											<div
												class="bsd-meta-row"
												v-if="drawerDetail.last_sync_datetime"
											>
												<span>Last Sync Datetime</span>
												<span>{{
													fmtDatetime(drawerDetail.last_sync_datetime)
												}}</span>
											</div>
											<div class="bsd-meta-row">
												<span>Missing-Date Sync</span>
												<span>{{
													drawerDetail.is_missing_date_sync
														? "Yes"
														: "No"
												}}</span>
											</div>
										</div>
									</div>
								</template>

								<!-- ════ ISSUES TAB ════ -->
								<template v-else-if="drawerTab === 'issues'">
									<div class="bsd-drawer-card">
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon unmapped">!</span>
											<span class="bsd-drawer-card-title"
												>Employee Issues</span
											>
										</div>
										<div class="bsd-drawer-stats">
											<div class="bsd-stat-row">
												<span class="bsd-stat-label"
													>Unmapped (device ID not in ERP)</span
												>
												<span class="bsd-stat-value warn">{{
													drawerDetail.employees_not_found
												}}</span>
												<span class="bsd-stat-unit">employees</span>
											</div>
											<div class="bsd-stat-row">
												<span class="bsd-stat-label">Insert Errors</span>
												<span class="bsd-stat-value error">{{
													drawerDetail.errored_count
												}}</span>
												<span class="bsd-stat-unit">employees</span>
											</div>
											<div class="bsd-stat-row">
												<span class="bsd-stat-label"
													>Skipped (Inactive in ERP)</span
												>
												<span class="bsd-stat-value muted">{{
													drawerDetail.skipped_inactive
												}}</span>
												<span class="bsd-stat-unit">employees</span>
											</div>
										</div>
									</div>

									<!-- ── Unmapped device IDs ── -->
									<div
										v-if="drawerDetail.summary?.skipped_no_employee?.length"
										class="bsd-drawer-card"
									>
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon unmapped">!</span>
											<span class="bsd-drawer-card-title">
												Unmapped Device IDs ({{
													drawerDetail.summary.skipped_no_employee
														.length
												}})
											</span>
											<button
												v-if="
													drawerDetail.summary.skipped_no_employee
														.length > 8
												"
												class="bsd-accordion-toggle"
												@click="showAllUnmapped = !showAllUnmapped"
											>
												{{ showAllUnmapped ? "Show less" : "Show all" }}
											</button>
										</div>
										<div class="bsd-tag-list">
											<span
												v-for="id in showAllUnmapped
													? drawerDetail.summary.skipped_no_employee
													: drawerDetail.summary.skipped_no_employee.slice(
															0,
															8
													  )"
												:key="id"
												class="bsd-tag bsd-tag-mappable"
											>
												{{ id }}
												<button
													class="bsd-tag-map-btn"
													title="Map this device ID to an Employee"
													@click="openMapModal(id)"
												>
													Map
												</button>
											</span>
										</div>
									</div>

									<!-- ── Errored employees ── -->
									<div
										v-if="drawerDetail.summary?.errored_employees?.length"
										class="bsd-drawer-card"
									>
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon api-err">✕</span>
											<span class="bsd-drawer-card-title">
												Insert Errors ({{
													drawerDetail.summary.errored_employees.length
												}})
											</span>
											<button
												v-if="
													drawerDetail.summary.errored_employees.length >
													8
												"
												class="bsd-accordion-toggle"
												@click="showAllErrored = !showAllErrored"
											>
												{{ showAllErrored ? "Show less" : "Show all" }}
											</button>
										</div>
										<div class="bsd-tag-list">
											<span
												v-for="emp in showAllErrored
													? drawerDetail.summary.errored_employees
													: drawerDetail.summary.errored_employees.slice(
															0,
															8
													  )"
												:key="emp"
												class="bsd-tag bsd-tag-err"
											>
												{{ emp }}
											</span>
										</div>
									</div>

									<div
										v-if="
											!drawerDetail.summary?.skipped_no_employee?.length &&
											!drawerDetail.summary?.errored_employees?.length
										"
										class="bsd-drawer-empty"
									>
										No employee issues for this log. 🎉
									</div>
								</template>

								<!-- ════ CHECKINS TAB ════ -->
								<template v-else-if="drawerTab === 'checkins'">
									<div class="bsd-drawer-card">
										<div class="bsd-drawer-card-header">
											<span class="bsd-drawer-card-icon created">✓</span>
											<span class="bsd-drawer-card-title">
												Checkins Created — by Employee ({{
													drawerDetail.checkins_by_employee.length
												}})
											</span>
										</div>
										<div
											v-if="drawerDetail.checkins_by_employee.length"
											class="bsd-table-wrap"
										>
											<table class="bsd-table">
												<thead>
													<tr>
														<th>Employee</th>
														<th>Name</th>
														<th class="num-col">Total</th>
													</tr>
												</thead>
												<tbody>
													<tr
														v-for="row in drawerDetail.checkins_by_employee"
														:key="row.employee"
													>
														<td>{{ row.employee }}</td>
														<td>{{ row.employee_name }}</td>
														<td class="num-col">{{ row.total }}</td>
													</tr>
												</tbody>
											</table>
										</div>
										<div v-else class="bsd-drawer-empty">
											No checkins were created for this date/unit.
										</div>
									</div>
								</template>
							</div>

							<!-- ── Actions footer ── -->
							<div class="bsd-drawer-actions">
								<button
									v-if="drawerRow.status === 'error'"
									class="bsd-btn-primary"
									@click="doRetryApi(drawerRow)"
									title="Re-fetch exactly this date's data from the device"
								>
									↻ Retry API (1 day only)
								</button>
								<button
									v-if="
										drawerDetail.has_response_data &&
										drawerRow.status !== 'error' &&
										drawerHasIssues
									"
									class="bsd-btn-secondary"
									@click="doRetryCheckin(drawerDetail.name)"
									title="Re-process stored response — no API call"
								>
									↻ Recreate Checkins
								</button>
								<button
									v-if="drawerRow.status === 'missing'"
									class="bsd-btn-secondary"
									@click="triggerMissing(drawerRow)"
								>
									↻ Trigger Missing Sync
								</button>
								<a
									:href="`/app/biometric-sync-log/${drawerDetail.name}`"
									target="_blank"
									class="bsd-btn-ghost"
								>
									Open Full Log ↗
								</a>
							</div>
						</template>
					</div>
				</div>
			</transition>
		</Teleport>

		<!-- ─────────────────── EMPLOYEE SEARCH MODAL (Quick Map) ──────────── -->
		<Teleport to="body">
			<transition name="modal-fade">
				<div v-if="empSearchOpen" class="bsd-modal-overlay" @click.self="closeEmpSearch">
					<div class="bsd-modal">
						<div class="bsd-modal-header">
							<strong>{{
								mappingDeviceId
									? `Map Device ID: ${mappingDeviceId}`
									: "Select Employee"
							}}</strong>
							<button class="bsd-drawer-close" @click="closeEmpSearch">✕</button>
						</div>
						<div class="bsd-modal-body">
							<input
								type="text"
								v-model="empSearchTxt"
								class="bsd-modal-search"
								placeholder="Search by employee name or ID…"
								autofocus
							/>
							<div v-if="empSearchLoading" class="bsd-loading">
								<div class="bsd-spinner"></div>
							</div>
							<div v-else class="bsd-modal-results">
								<div
									v-for="emp in empSearchResults"
									:key="emp.name"
									class="bsd-modal-result-row"
									@click="selectEmployee(emp)"
								>
									<div class="bsd-modal-result-main">
										<span class="bsd-modal-result-name">{{
											emp.employee_name
										}}</span>
										<span class="bsd-modal-result-id">{{ emp.name }}</span>
									</div>
									<div class="bsd-modal-result-meta">
										<span v-if="emp.department">{{ emp.department }}</span>
										<span
											v-if="emp.attendance_device_id"
											class="bsd-pill pill-success"
										>
											{{ emp.attendance_device_id }}
										</span>
										<span v-else class="bsd-pill pill-missing"
											>No device ID</span
										>
									</div>
								</div>
								<div v-if="!empSearchResults.length" class="bsd-drawer-empty">
									No employees found.
								</div>
							</div>
						</div>
					</div>
				</div>
			</transition>
		</Teleport>
	</div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from "vue";

// ── API helper ────────────────────────────────────────────────────────────────

const API =
	"biometric_integration.biometric_integration.page.biometric_sync_dashboard.biometric_sync_dashboard.";

function call(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: API + method,
			args,
			callback: (r) => resolve(r.message),
			error: reject,
		});
	});
}

// ── utils ─────────────────────────────────────────────────────────────────────

function yesterday() {
	const d = new Date();
	d.setDate(d.getDate() - 1);
	return d.toISOString().slice(0, 10);
}

function daysAgo(n) {
	const d = new Date();
	d.setDate(d.getDate() - n);
	return d.toISOString().slice(0, 10);
}

function fmtDatetime(dt) {
	if (!dt) return "—";
	return new Date(dt).toLocaleString(undefined, {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
}

function statusLabel(s) {
	return (
		{
			success: "OK",
			warning: "Warning",
			error: "Error",
			pending: "Queued",
			missing: "Missing",
			empty: "Empty",
		}[s] || s
	);
}

function progressClass(p) {
	if (p >= 95) return "prog-green";
	if (p >= 70) return "prog-yellow";
	return "prog-red";
}

function fmtTime(dt) {
	if (!dt) return "—";
	return new Date(dt).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// ── state ─────────────────────────────────────────────────────────────────────

// Tab state
const activeTab = ref("daily");

// Daily view
const syncDate = ref(yesterday());
const loading = ref(false);
const dashData = ref(null);
const trendData = ref(null);
const failureData = ref(null);
const activeFilter = ref(null);

const sortKey = ref("unit");
const sortDir = ref("asc");

// Drawer
const drawerRow = ref(null);
const drawerDetail = ref(null);
const drawerLoading = ref(false);
const drawerTab = ref("overview");
const showAllUnmapped = ref(false);
const showAllErrored = ref(false);

// Chart
const trendChartEl = ref(null);
let chartInstance = null;

// Unit history (Tab 2)
const unitFilter = ref("");
const unitFromDate = ref(daysAgo(7));
const unitToDate = ref(yesterday());
const unitHistory = ref(null);
const unitLoading = ref(false);

// Employee history (Tab 3)
const empFilter = ref(null);
const empFromDate = ref(daysAgo(7));
const empToDate = ref(yesterday());
const empHistory = ref(null);
const empLoading = ref(false);

// Employee search modal (Quick Map + Tab 3 employee picker)
const empSearchOpen = ref(false);
const empSearchTxt = ref("");
const empSearchResults = ref([]);
const empSearchLoading = ref(false);
const mappingDeviceId = ref(null);

// ── computed ──────────────────────────────────────────────────────────────────

const drawerIssueCount = computed(() => {
	const d = drawerDetail.value;
	if (!d) return 0;
	return (
		(d.summary?.skipped_no_employee?.length || 0) + (d.summary?.errored_employees?.length || 0)
	);
});

// 100% success = unmapped, insert-errors and skipped-inactive all zero;
// then there is nothing for "Recreate Checkins" to fix
const drawerHasIssues = computed(() => {
	const d = drawerDetail.value;
	if (!d) return false;
	return (d.employees_not_found || 0) + (d.errored_count || 0) + (d.skipped_inactive || 0) > 0;
});

const isEtime = computed(() => dashData.value?.server_type === "eTime Tracker Lite");

const serverBadgeClass = computed(() =>
	dashData.value?.server_type === "Bio Server" ? "badge-blue" : "badge-purple"
);

const unitsList = computed(() => dashData.value?.units ?? []);

const filterLabel = computed(
	() =>
		({
			raw_records: "Device Records",
			total: isEtime.value ? "Employees Received" : "Punches Received",
			created: "Checkins Created",
			skipped: "Duplicates Skipped",
			unmapped: "Unmapped Employees",
			errored: "Insert Errors",
			error: "API Errors",
			success: "Healthy",
		}[activeFilter.value] || activeFilter.value)
);

const filteredRows = computed(() => {
	if (!dashData.value) return [];
	let rows = [...dashData.value.table_rows];

	switch (activeFilter.value) {
		case "error":
			rows = rows.filter((r) => r.status === "error");
			break;
		case "success":
			rows = rows.filter((r) => r.status === "success");
			break;
		case "unmapped":
			rows = rows.filter((r) => (r.unmapped_employees || 0) > 0);
			break;
		case "errored":
			rows = rows.filter((r) => (r.errored || 0) > 0);
			break;
		case "skipped":
			rows = rows.filter((r) => (r.skipped || 0) > 0);
			break;
		case "raw_records":
			rows = rows.filter((r) => (r.raw_records || 0) > 0);
			break;
		case "total":
			rows = rows.filter((r) => (r.total || 0) > 0);
			break;
		case "created":
			rows = rows.filter((r) => (r.created || 0) > 0);
			break;
	}

	const key = sortKey.value;
	const dir = sortDir.value === "asc" ? 1 : -1;
	rows.sort((a, b) => {
		const av = a[key] ?? -Infinity;
		const bv = b[key] ?? -Infinity;
		if (typeof av === "string") return dir * av.localeCompare(bv);
		return dir * (av - bv);
	});
	return rows;
});

const failureBarMax = computed(() =>
	failureData.value?.length ? Math.max(...failureData.value.map((f) => f.count), 1) : 1
);
function failureBarWidth(count) {
	return Math.round((count / failureBarMax.value) * 100);
}

// ── data loading ──────────────────────────────────────────────────────────────

async function loadAll() {
	loading.value = true;
	try {
		const [dash, trend, failure] = await Promise.all([
			call("get_dashboard_data", { sync_date: syncDate.value }),
			call("get_trend_data"),
			call("get_failure_breakdown", { sync_date: syncDate.value }),
		]);
		dashData.value = dash;
		trendData.value = trend;
		failureData.value = failure;
		await nextTick();
		renderTrendChart();
		// Fallback render in case the ref wasn't mounted on the first tick
		setTimeout(renderTrendChart, 200);
	} catch (e) {
		frappe.msgprint({ message: String(e), title: "Dashboard Error", indicator: "red" });
	} finally {
		loading.value = false;
	}
}

async function loadUnitHistory() {
	if (!unitFilter.value) return;
	unitLoading.value = true;
	unitHistory.value = null;
	try {
		unitHistory.value = await call("get_unit_history", {
			unit: unitFilter.value,
			from_date: unitFromDate.value,
			to_date: unitToDate.value,
		});
	} catch (e) {
		frappe.msgprint({ message: String(e), title: "History Error", indicator: "red" });
	} finally {
		unitLoading.value = false;
	}
}

// ── trend chart ───────────────────────────────────────────────────────────────

function renderTrendChart() {
	const el = trendChartEl.value;
	if (!el || !trendData.value?.labels?.length) return;

	if (chartInstance) {
		try {
			chartInstance.destroy?.();
		} catch (_) {}
		el.innerHTML = "";
	}

	const totalLabel = isEtime.value ? "Emp. Received" : "Dev. Records";

	try {
		chartInstance = new frappe.Chart(el, {
			type: "line",
			data: {
				labels: trendData.value.labels,
				datasets: [
					{ name: totalLabel, values: trendData.value.raw_records },
					{ name: "Checkins", values: trendData.value.created },
				],
			},
			colors: ["#5e64ff", "#28a745"],
			height: 240,
			lineOptions: { regionFill: 1 },
			axisOptions: { xIsSeries: true },
		});
	} catch (err) {
		console.error("Trend chart render error:", err);
	}
}

// ── interactions ──────────────────────────────────────────────────────────────

function toggleFilter(key) {
	activeFilter.value = activeFilter.value === key ? null : key;
}

function sort(col) {
	if (sortKey.value === col) {
		sortDir.value = sortDir.value === "asc" ? "desc" : "asc";
	} else {
		sortKey.value = col;
		sortDir.value = "asc";
	}
}

async function openDrawer(row) {
	drawerRow.value = row;
	drawerDetail.value = null;
	drawerLoading.value = true;
	drawerTab.value = "overview";
	showAllUnmapped.value = false;
	showAllErrored.value = false;
	try {
		drawerDetail.value = await call("get_log_detail", { log_name: row.log_name });
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	} finally {
		drawerLoading.value = false;
	}
}

async function refreshDrawer() {
	if (!drawerDetail.value) return;
	try {
		drawerDetail.value = await call("get_log_detail", { log_name: drawerDetail.value.name });
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	}
}

function closeDrawer() {
	drawerRow.value = null;
	drawerDetail.value = null;
}

async function doRetryApi(row) {
	if (!row.log_name) return;
	const confirmed = await new Promise((res) =>
		frappe.confirm(
			`Retry API for <b>${row.unit}</b> on <b>${row.sync_date || syncDate.value}</b>?<br>
      This will re-fetch <b>exactly that one day</b> from the device.`,
			() => res(true),
			() => res(false)
		)
	);
	if (!confirmed) return;
	try {
		await call("retry_api", { log_name: row.log_name });
		frappe.show_alert({ message: "Retry queued (1 day only)", indicator: "blue" });
		setTimeout(loadAll, 1500);
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	}
}

async function doRetryCheckin(log_name) {
	try {
		const r = await call("retry_checkin_creation", { log_name });
		frappe.show_alert({
			message: `Created: ${r.created}, Dupes: ${r.skipped_duplicate}, Unmapped: ${r.employees_not_found}, Errored: ${r.errored_count}`,
			indicator: "green",
		});
		closeDrawer();
		loadAll();
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	}
}

async function triggerMissing(row) {
	try {
		const msg = await call("trigger_missing_date_sync", {
			unit: row.unit,
			sync_date: syncDate.value,
		});
		frappe.show_alert({ message: msg, indicator: "blue" });
		setTimeout(loadAll, 1500);
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	}
}

function openSettings() {
	frappe.set_route("Form", "Biometric Sync Settings");
}

// ── Employee history (Tab 3) ──────────────────────────────────────────────────

async function loadEmployeeHistory() {
	if (!empFilter.value) return;
	empLoading.value = true;
	empHistory.value = null;
	try {
		empHistory.value = await call("get_employee_history", {
			employee: empFilter.value.name,
			from_date: empFromDate.value,
			to_date: empToDate.value,
		});
	} catch (e) {
		frappe.msgprint({ message: String(e), title: "History Error", indicator: "red" });
	} finally {
		empLoading.value = false;
	}
}

// ── Employee search modal (Quick Map + Tab 3 picker) ──────────────────────────

let empSearchDebounce = null;
watch([empSearchTxt, empSearchOpen], () => {
	if (!empSearchOpen.value) return;
	clearTimeout(empSearchDebounce);
	empSearchDebounce = setTimeout(runEmpSearch, 250);
});

async function runEmpSearch() {
	empSearchLoading.value = true;
	try {
		empSearchResults.value = await call("search_employees", {
			txt: empSearchTxt.value,
			only_unmapped: !!mappingDeviceId.value,
		});
	} catch (e) {
		frappe.msgprint({ message: String(e), indicator: "red" });
	} finally {
		empSearchLoading.value = false;
	}
}

function openMapModal(deviceId) {
	mappingDeviceId.value = deviceId;
	empSearchTxt.value = "";
	empSearchResults.value = [];
	empSearchOpen.value = true;
	runEmpSearch();
}

function closeEmpSearch() {
	empSearchOpen.value = false;
	mappingDeviceId.value = null;
}

async function selectEmployee(emp) {
	if (mappingDeviceId.value) {
		try {
			await call("map_device_id", { device_id: mappingDeviceId.value, employee: emp.name });
			frappe.show_alert({
				message: `Mapped ${mappingDeviceId.value} → ${emp.employee_name}`,
				indicator: "green",
			});
			closeEmpSearch();

			if (drawerDetail.value?.has_response_data) {
				const recreate = await new Promise((res) =>
					frappe.confirm(
						"Recreate checkins for this date now using the newly mapped employee?",
						() => res(true),
						() => res(false)
					)
				);
				if (recreate) {
					await doRetryCheckin(drawerDetail.value.name);
					return;
				}
			}
			await refreshDrawer();
			loadAll();
		} catch (e) {
			frappe.msgprint({ message: String(e), indicator: "red" });
		}
	} else {
		empFilter.value = emp;
		closeEmpSearch();
	}
}

// Re-render chart whenever we switch back to the daily tab — the DOM node is
// destroyed and recreated by v-if, so the old chartInstance is stale.
watch(activeTab, async (newTab) => {
	if (newTab === "daily" && trendData.value?.labels?.length) {
		await nextTick();
		renderTrendChart();
		setTimeout(renderTrendChart, 200);
	}
});

// Lock background page scroll while the drawer or modal is open so wheel
// events at the overlay's scroll boundary can't chain to the main view.
watch([drawerRow, empSearchOpen], ([row, modal]) => {
	const lock = !!row || !!modal;
	document.documentElement.style.overflow = lock ? "hidden" : "";
	document.body.style.overflow = lock ? "hidden" : "";
});

onUnmounted(() => {
	document.documentElement.style.overflow = "";
	document.body.style.overflow = "";
});

onMounted(loadAll);
</script>

<script>
export const SortIcon = {
	props: ["col", "sortKey", "sortDir"],
	template: `<span class="bsd-sort-icon">
    <span :style="{opacity: sortKey===col && sortDir==='asc' ? 1 : 0.25}">▲</span>
    <span :style="{opacity: sortKey===col && sortDir==='desc' ? 1 : 0.25}">▼</span>
  </span>`,
};
</script>

<style scoped>
/* ── root ────────────────────────────────────────────────────────────────────*/
.bsd-root {
	padding: 16px 24px;
	font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
	font-size: 13px;
	color: #2d3748;
	max-width: 1500px;
	margin: 0 auto;
}

/* ── header ──────────────────────────────────────────────────────────────────*/
.bsd-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	flex-wrap: wrap;
	background: #fff;
	border: 1px solid #e8edf2;
	border-radius: 12px;
	padding: 16px 20px;
	margin-bottom: 0;
}
.bsd-header-left {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.bsd-title-row {
	display: flex;
	align-items: center;
	gap: 10px;
	flex-wrap: wrap;
}
.bsd-title {
	margin: 0;
	font-size: 17px;
	font-weight: 700;
	color: #1a202c;
	letter-spacing: -0.01em;
}
.bsd-header-sub {
	display: flex;
	align-items: center;
	gap: 8px;
}
.bsd-server-badge {
	padding: 2px 10px;
	border-radius: 20px;
	font-size: 11px;
	font-weight: 600;
	flex-shrink: 0;
}
.badge-blue {
	background: #e0e7ff;
	color: #3730a3;
}
.badge-purple {
	background: #ede9fe;
	color: #5b21b6;
}
.bsd-last-sync {
	font-size: 11px;
	color: #718096;
}
.bsd-last-sync-dim {
	font-style: italic;
}

.bsd-header-right {
	display: flex;
	align-items: center;
	gap: 10px;
	flex-shrink: 0;
}

/* Date control: styled pill — label + input in one box */
.bsd-date-control {
	display: flex;
	align-items: center;
	gap: 8px;
	border: 1px solid #e2e8f0;
	border-radius: 8px;
	background: #f8fafc;
	padding: 6px 12px;
	height: 36px;
	box-sizing: border-box;
	transition: border-color 0.15s, box-shadow 0.15s;
}
.bsd-date-control:focus-within {
	border-color: #5e64ff;
	box-shadow: 0 0 0 2px rgba(94, 100, 255, 0.12);
	background: #fff;
}
.bsd-date-control-label {
	font-size: 11px;
	color: #a0aec0;
	font-weight: 600;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	white-space: nowrap;
}
.bsd-date-input {
	border: none;
	background: transparent;
	font-size: 12px;
	color: #2d3748;
	font-weight: 500;
	padding: 0;
	outline: none;
	min-width: 110px;
}

/* Settings button */
.bsd-settings-btn {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	border: 1px solid #e2e8f0;
	background: #fff;
	border-radius: 8px;
	padding: 0 14px;
	height: 36px;
	cursor: pointer;
	font-size: 12px;
	color: #4a5568;
	font-weight: 500;
	transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.bsd-settings-btn:hover {
	background: #f7fafc;
	border-color: #cbd5e0;
	color: #2d3748;
}
.bsd-settings-btn svg {
	flex-shrink: 0;
}

/* ── tab bar ─────────────────────────────────────────────────────────────────*/
.bsd-tab-bar {
	display: flex;
	gap: 2px;
	border-bottom: 2px solid #e8edf2;
	margin-top: 16px;
	margin-bottom: 20px;
}
.bsd-tab {
	padding: 9px 22px;
	border: none;
	background: none;
	font-size: 13px;
	font-weight: 500;
	color: #718096;
	cursor: pointer;
	border-bottom: 2px solid transparent;
	margin-bottom: -2px;
	border-radius: 6px 6px 0 0;
	transition: color 0.15s, background 0.15s, border-color 0.15s;
	letter-spacing: 0.01em;
}
.bsd-tab:hover {
	color: #4a5568;
	background: #f7fafc;
}
.bsd-tab.active {
	color: #5e64ff;
	border-bottom-color: #5e64ff;
	font-weight: 600;
	background: #fafaff;
}

/* ── loading ─────────────────────────────────────────────────────────────────*/
.bsd-loading {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 60px 20px;
	justify-content: center;
	color: #718096;
}
.bsd-spinner {
	width: 20px;
	height: 20px;
	border: 2px solid #e2e8f0;
	border-top-color: #5e64ff;
	border-radius: 50%;
	animation: spin 0.6s linear infinite;
}
@keyframes spin {
	to {
		transform: rotate(360deg);
	}
}

/* ── kpi row ─────────────────────────────────────────────────────────────────*/
.bsd-kpi-row {
	display: grid;
	grid-template-columns: repeat(6, 1fr);
	gap: 12px;
	margin-bottom: 6px;
}
@media (max-width: 1000px) {
	.bsd-kpi-row {
		grid-template-columns: repeat(3, 1fr);
	}
}
@media (max-width: 600px) {
	.bsd-kpi-row {
		grid-template-columns: repeat(2, 1fr);
	}
}

.bsd-kpi-card {
	background: #fff;
	border: 1px solid #e8edf2;
	border-radius: 10px;
	padding: 14px 16px;
	cursor: pointer;
	display: flex;
	align-items: center;
	gap: 12px;
	transition: box-shadow 0.15s, border-color 0.15s;
}
.bsd-kpi-card:hover {
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
	border-color: #cbd5e0;
}
.bsd-kpi-card.active {
	border-color: #5e64ff;
	box-shadow: 0 0 0 2px rgba(94, 100, 255, 0.15);
}
.bsd-kpi-card.warn {
	border-left: 3px solid #f6ad55;
}
.bsd-kpi-card.warn.active {
	border-color: #f6ad55;
	box-shadow: 0 0 0 2px rgba(246, 173, 85, 0.2);
}
.bsd-kpi-card.error {
	border-left: 3px solid #fc8181;
}
.bsd-kpi-card.error.active {
	border-color: #fc8181;
	box-shadow: 0 0 0 2px rgba(252, 129, 129, 0.2);
}
.bsd-kpi-card.healthy {
	border-left: 3px solid #68d391;
}
.bsd-kpi-card.healthy.active {
	border-color: #68d391;
	box-shadow: 0 0 0 2px rgba(104, 211, 145, 0.2);
}

.bsd-kpi-icon {
	width: 36px;
	height: 36px;
	border-radius: 8px;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 14px;
	font-weight: 700;
	flex-shrink: 0;
}
.bsd-kpi-icon.punch {
	background: #eff6ff;
	color: #3b82f6;
}
.bsd-kpi-icon.created {
	background: #f0fdf4;
	color: #16a34a;
}
.bsd-kpi-icon.skipped {
	background: #f5f3ff;
	color: #7c3aed;
}
.bsd-kpi-icon.unmapped {
	background: #fffbeb;
	color: #d97706;
}
.bsd-kpi-icon.api-err {
	background: #fef2f2;
	color: #dc2626;
}
.bsd-kpi-icon.loc-ok {
	background: #f0fdf4;
	color: #16a34a;
}

.bsd-kpi-body {
	min-width: 0;
}
.bsd-kpi-value {
	font-size: 20px;
	font-weight: 700;
	line-height: 1.2;
}
.bsd-kpi-total {
	font-size: 14px;
	font-weight: 400;
	color: #718096;
}
.bsd-kpi-label {
	font-size: 11px;
	font-weight: 600;
	color: #4a5568;
	margin-top: 2px;
}
.bsd-kpi-sub {
	font-size: 10px;
	color: #a0aec0;
}

/* ── kpi legend ──────────────────────────────────────────────────────────────*/
.bsd-kpi-legend {
	display: flex;
	align-items: center;
	gap: 16px;
	margin-bottom: 16px;
	flex-wrap: wrap;
}
.bsd-legend-group {
	font-size: 10px;
	color: #a0aec0;
}
.bsd-legend-group.records {
	color: #3b82f6;
}
.bsd-legend-group.employees {
	color: #d97706;
}
.bsd-filter-badge {
	background: #eef2ff;
	color: #4338ca;
	padding: 2px 10px;
	border-radius: 10px;
	font-size: 11px;
	cursor: pointer;
	font-weight: 500;
}
.bsd-filter-badge:hover {
	background: #e0e7ff;
}

/* ── card shell ──────────────────────────────────────────────────────────────*/
.bsd-card {
	background: #fff;
	border: 1px solid #e8edf2;
	border-radius: 10px;
	margin-bottom: 16px;
	overflow: hidden;
}
.bsd-card-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 12px 16px;
	border-bottom: 1px solid #f0f4f8;
}
.bsd-card-header h4 {
	margin: 0;
	font-size: 14px;
	font-weight: 600;
}
.bsd-table-meta {
	font-size: 11px;
	color: #718096;
}

/* ── table ───────────────────────────────────────────────────────────────────*/
.bsd-table-wrap {
	overflow-x: auto;
}
.bsd-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 12px;
}

.bsd-table thead th {
	padding: 8px 12px;
	text-align: left;
	font-size: 11px;
	font-weight: 600;
	color: #718096;
	background: #f8fafc;
	border-bottom: 1px solid #e8edf2;
	white-space: nowrap;
	user-select: none;
}
.bsd-table thead th.sortable {
	cursor: pointer;
}
.bsd-table thead th.sortable:hover {
	color: #4a5568;
}
.bsd-table thead th.num-col {
	text-align: right;
}

.bsd-table tbody td {
	padding: 9px 12px;
	border-bottom: 1px solid #f7f9fb;
	vertical-align: middle;
}
.bsd-table tbody td.num-col {
	text-align: right;
	font-variant-numeric: tabular-nums;
}
.bsd-table tbody tr:last-child td {
	border-bottom: none;
}
.bsd-table tbody tr:hover {
	background: #fafbff;
}
.bsd-row-missing td {
	opacity: 0.6;
}

/* fixed column widths */
.col-dot {
	width: 20px;
}
.col-unit {
	min-width: 130px;
}
.num-col {
	width: 80px;
}
.col-progress {
	width: 130px;
}
.col-actions {
	width: 100px;
	white-space: nowrap;
}
.bsd-date-cell {
	white-space: nowrap;
	font-weight: 500;
}

.bsd-dot {
	display: inline-block;
	width: 8px;
	height: 8px;
	border-radius: 50%;
}
.dot-success {
	background: #48bb78;
}
.dot-warning {
	background: #f6ad55;
}
.dot-error {
	background: #fc8181;
}
.dot-pending {
	background: #90cdf4;
}
.dot-missing {
	background: #e2e8f0;
	border: 1px solid #cbd5e0;
}
.dot-empty {
	background: #cbd5e0;
}

.bsd-pill {
	padding: 2px 8px;
	border-radius: 8px;
	font-size: 10px;
	font-weight: 600;
	display: inline-block;
}
.pill-success {
	background: #f0fff4;
	color: #22543d;
}
.pill-warning {
	background: #fffaf0;
	color: #744210;
}
.pill-error {
	background: #fff5f5;
	color: #742a2a;
}
.pill-pending {
	background: #ebf8ff;
	color: #2a4365;
}
.pill-missing {
	background: #f7fafc;
	color: #718096;
}
.pill-empty {
	background: #f1f5f9;
	color: #64748b;
}

.bsd-unit-cell {
	min-width: 130px;
}
.bsd-unit-name {
	font-weight: 500;
	display: block;
}
.bsd-log-link {
	font-size: 10px;
	color: #5e64ff;
	text-decoration: none;
	display: block;
}
.bsd-log-link:hover {
	text-decoration: underline;
}

.bsd-sort-icon {
	font-size: 8px;
	margin-left: 3px;
	display: inline-flex;
	flex-direction: column;
	line-height: 1;
}

.bsd-nil {
	color: #cbd5e0;
}
.num-warn {
	color: #d97706;
	font-weight: 600;
}
.num-error {
	color: #e53e3e;
	font-weight: 600;
}
.num-unit {
	font-size: 9px;
	color: #a0aec0;
	margin-left: 2px;
}

.bsd-prog-wrap {
	display: flex;
	align-items: center;
	gap: 6px;
}
.bsd-prog-bar {
	flex: 1;
	height: 6px;
	background: #edf2f7;
	border-radius: 3px;
	overflow: hidden;
}
.bsd-prog-fill {
	height: 100%;
	border-radius: 3px;
	transition: width 0.3s;
}
.prog-green {
	background: #48bb78;
}
.prog-yellow {
	background: #f6ad55;
}
.prog-red {
	background: #fc8181;
}
.bsd-prog-pct {
	font-size: 10px;
	color: #718096;
	min-width: 32px;
	text-align: right;
}
.bsd-prog-caption {
	font-size: 9px;
	color: #a0aec0;
	margin-top: 1px;
}

.bsd-action-btn {
	padding: 3px 8px;
	border-radius: 4px;
	font-size: 10px;
	font-weight: 500;
	cursor: pointer;
	border: 1px solid;
	margin-right: 4px;
	text-decoration: none;
	display: inline-block;
}
.bsd-action-btn.retry {
	background: #fff5f5;
	color: #e53e3e;
	border-color: #fed7d7;
}
.bsd-action-btn.retry:hover {
	background: #fed7d7;
}
.bsd-action-btn.trigger {
	background: #ebf8ff;
	color: #2b6cb0;
	border-color: #bee3f8;
}
.bsd-action-btn.trigger:hover {
	background: #bee3f8;
}
.bsd-action-btn.detail {
	background: #f7fafc;
	color: #4a5568;
	border-color: #e2e8f0;
}
.bsd-action-btn.detail:hover {
	background: #edf2f7;
}

.bsd-empty {
	text-align: center;
	padding: 40px 20px;
	color: #a0aec0;
}

/* ── charts row ──────────────────────────────────────────────────────────────*/
.bsd-charts-row {
	display: grid;
	grid-template-columns: 1fr 1fr;
	gap: 16px;
}
@media (max-width: 768px) {
	.bsd-charts-row {
		grid-template-columns: 1fr;
	}
}
.bsd-chart-card {
	padding: 0;
}
.bsd-chart-sub {
	font-size: 11px;
	color: #a0aec0;
}
.bsd-chart-area {
	padding: 8px 12px 4px;
	min-height: 200px;
}
.bsd-chart-empty {
	padding: 40px;
	text-align: center;
	color: #a0aec0;
	font-size: 12px;
}

/* Fix frappe.Chart legend wrapping inside scoped component */
.bsd-chart-area :deep(.chart-legend) {
	flex-wrap: wrap !important;
	justify-content: center;
	gap: 4px 16px;
	padding: 4px 8px 8px;
}
.bsd-chart-area :deep(.legend-dataset-text) {
	font-size: 11px !important;
}

.bsd-failure-list {
	padding: 16px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}
.bsd-failure-row {
	display: flex;
	align-items: center;
	gap: 10px;
}
.bsd-failure-label {
	min-width: 160px;
	font-size: 11px;
	color: #4a5568;
	text-align: right;
}
.bsd-failure-bar-wrap {
	flex: 1;
	height: 8px;
	background: #edf2f7;
	border-radius: 4px;
	overflow: hidden;
}
.bsd-failure-bar {
	height: 100%;
	background: #fc8181;
	border-radius: 4px;
	transition: width 0.3s;
}
.bsd-failure-count {
	font-size: 11px;
	font-weight: 600;
	min-width: 30px;
}

/* ── unit history tab ────────────────────────────────────────────────────────*/
.bsd-unit-filter-bar {
	display: grid;
	grid-template-columns: 1fr 1fr 1fr auto;
	align-items: end;
	gap: 16px;
	background: #fff;
	border: 1px solid #e8edf2;
	border-radius: 10px;
	padding: 16px 20px;
	margin-bottom: 16px;
}
@media (max-width: 800px) {
	.bsd-unit-filter-bar {
		grid-template-columns: 1fr 1fr;
	}
	.bsd-load-btn {
		grid-column: span 2;
	}
}
.bsd-filter-group {
	display: flex;
	flex-direction: column;
	gap: 5px;
}
.bsd-filter-group label {
	font-size: 11px;
	color: #718096;
	font-weight: 600;
	letter-spacing: 0.02em;
}
.bsd-select {
	border: 1px solid #e2e8f0;
	border-radius: 6px;
	padding: 6px 10px;
	font-size: 12px;
	background: #fff;
	width: 100%;
	appearance: auto;
	height: 32px;
}
.bsd-select:focus {
	outline: none;
	border-color: #5e64ff;
	box-shadow: 0 0 0 2px rgba(94, 100, 255, 0.15);
}
/* Align the date inputs in Tab 2 filter to match the select height */
.bsd-unit-filter-bar .bsd-date-input {
	width: 100%;
	height: 32px;
	padding: 6px 8px;
}
.bsd-load-btn {
	white-space: nowrap;
	height: 32px;
	padding: 0 20px;
}

.bsd-unit-summary-bar {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
	background: #fff;
	border: 1px solid #e8edf2;
	border-radius: 10px;
	padding: 16px 20px;
	margin-bottom: 16px;
}
.bsd-sum-stat {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 3px;
	padding: 12px 18px;
	border-radius: 8px;
	background: #f8fafc;
	min-width: 96px;
	flex: 1;
	border: 1px solid #edf2f7;
}
.bsd-sum-stat.ok {
	background: #f0fff4;
	border-color: #c6f6d5;
}
.bsd-sum-stat.warn {
	background: #fffbeb;
	border-color: #feebc8;
}
.bsd-sum-stat.error {
	background: #fff5f5;
	border-color: #fed7d7;
}
.bsd-sum-value {
	font-size: 22px;
	font-weight: 700;
	line-height: 1.1;
	color: #2d3748;
}
.bsd-sum-stat.ok .bsd-sum-value {
	color: #276749;
}
.bsd-sum-stat.warn .bsd-sum-value {
	color: #c05621;
}
.bsd-sum-stat.error .bsd-sum-value {
	color: #c53030;
}
.bsd-sum-label {
	font-size: 10px;
	color: #718096;
	text-align: center;
	font-weight: 500;
	white-space: nowrap;
}

.bsd-tab2-hint {
	text-align: center;
	padding: 64px 24px;
	color: #a0aec0;
	font-size: 13px;
	background: #fff;
	border: 1px dashed #e2e8f0;
	border-radius: 10px;
	line-height: 1.6;
}
.bsd-tab2-hint strong {
	color: #5e64ff;
}

/* ── drawer ──────────────────────────────────────────────────────────────────*/
.bsd-drawer-overlay {
	position: fixed;
	inset: 0;
	height: 100vh;
	background: rgba(0, 0, 0, 0.25);
	z-index: 1000;
	display: flex;
	justify-content: flex-end;
}
.bsd-drawer {
	width: 420px;
	max-width: 95vw;
	height: 100vh;
	background: #fff;
	overflow: hidden;
	padding: 0;
	display: flex;
	flex-direction: column;
	box-shadow: -4px 0 24px rgba(0, 0, 0, 0.12);
}
.bsd-drawer-wide {
	width: 640px;
}
.drawer-slide-enter-active,
.drawer-slide-leave-active {
	transition: transform 0.25s;
}
.drawer-slide-enter-from,
.drawer-slide-leave-to {
	transform: translateX(100%);
}

.bsd-drawer-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 16px 20px;
	border-bottom: 1px solid #edf2f7;
	flex-shrink: 0;
	background: #fff;
}
.bsd-drawer-close {
	background: none;
	border: none;
	cursor: pointer;
	font-size: 14px;
	color: #a0aec0;
	padding: 4px 6px;
}
.bsd-drawer-close:hover {
	color: #4a5568;
}
.bsd-drawer-loading {
	display: flex;
	justify-content: center;
	padding: 40px;
}

/* ── drawer sub-tabs ── */
.bsd-drawer-tabs {
	display: flex;
	gap: 2px;
	padding: 0 20px;
	border-bottom: 1px solid #edf2f7;
	flex-shrink: 0;
	background: #fff;
}
.bsd-drawer-tab {
	padding: 10px 16px;
	border: none;
	background: none;
	font-size: 12px;
	font-weight: 500;
	color: #718096;
	cursor: pointer;
	border-bottom: 2px solid transparent;
	margin-bottom: -1px;
	display: flex;
	align-items: center;
	gap: 6px;
	transition: color 0.15s, border-color 0.15s;
}
.bsd-drawer-tab:hover {
	color: #4a5568;
}
.bsd-drawer-tab.active {
	color: #5e64ff;
	border-bottom-color: #5e64ff;
	font-weight: 600;
}
.bsd-drawer-tab-badge {
	background: #fff5f5;
	color: #c53030;
	border-radius: 10px;
	font-size: 10px;
	font-weight: 700;
	padding: 1px 6px;
	min-width: 16px;
	text-align: center;
}

.bsd-drawer-body {
	padding: 16px 20px;
	display: flex;
	flex-direction: column;
	gap: 14px;
	flex: 1;
	min-height: 0;
	overflow-y: auto;
	overscroll-behavior: contain;
}
/* cards have overflow:hidden, which lets flex shrink them to fit instead of
   overflowing the body — force full height so the body scrolls */
.bsd-drawer-body > * {
	flex-shrink: 0;
}

/* ── drawer cards ── */
.bsd-drawer-card {
	border: 1px solid #e8edf2;
	border-radius: 10px;
	overflow: hidden;
	background: #fff;
}
.bsd-drawer-card-header {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 10px 14px;
	background: #f8fafc;
	border-bottom: 1px solid #edf2f7;
}
.bsd-drawer-card-title {
	font-size: 11px;
	font-weight: 700;
	color: #4a5568;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	flex: 1;
}
.bsd-drawer-card-icon {
	width: 22px;
	height: 22px;
	border-radius: 6px;
	flex-shrink: 0;
	display: flex;
	align-items: center;
	justify-content: center;
	font-size: 11px;
	font-weight: 700;
}
.bsd-drawer-card-icon.punch {
	background: #eff6ff;
	color: #3b82f6;
}
.bsd-drawer-card-icon.created {
	background: #f0fdf4;
	color: #16a34a;
}
.bsd-drawer-card-icon.unmapped {
	background: #fffbeb;
	color: #d97706;
}
.bsd-drawer-card-icon.api-err {
	background: #fef2f2;
	color: #dc2626;
}
.bsd-drawer-card-icon.info {
	background: #eef2ff;
	color: #5e64ff;
}

.bsd-accordion-toggle {
	background: none;
	border: none;
	cursor: pointer;
	font-size: 11px;
	color: #5e64ff;
	font-weight: 600;
	padding: 2px 4px;
	flex-shrink: 0;
}
.bsd-accordion-toggle:hover {
	text-decoration: underline;
}

.bsd-drawer-empty {
	padding: 24px 14px;
	text-align: center;
	color: #a0aec0;
	font-size: 12px;
}

.bsd-drawer-stats {
	display: flex;
	flex-direction: column;
	gap: 8px;
	padding: 12px 14px;
}
.bsd-stat-row {
	display: flex;
	align-items: baseline;
	gap: 8px;
}
.bsd-stat-label {
	flex: 1;
	font-size: 12px;
	color: #718096;
}
.bsd-stat-value {
	font-size: 16px;
	font-weight: 700;
}
.bsd-stat-value.ok {
	color: #22543d;
}
.bsd-stat-value.warn {
	color: #d97706;
}
.bsd-stat-value.error {
	color: #c53030;
}
.bsd-stat-value.muted {
	color: #718096;
}
.bsd-stat-unit {
	font-size: 10px;
	color: #a0aec0;
}

.bsd-drawer-meta {
	display: flex;
	flex-direction: column;
	gap: 6px;
	padding: 12px 14px;
}
.bsd-meta-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
}
.bsd-meta-row span:first-child {
	color: #718096;
	font-size: 11px;
}
.bsd-meta-row span:last-child,
.bsd-meta-row a {
	font-weight: 500;
	font-size: 12px;
	color: #2d3748;
}
.bsd-meta-row a {
	color: #5e64ff;
	text-decoration: none;
}
.bsd-meta-row a:hover {
	text-decoration: underline;
}

.bsd-tag-list {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
	padding: 12px 14px;
}
.bsd-tag {
	background: #edf2f7;
	color: #4a5568;
	padding: 2px 8px;
	border-radius: 4px;
	font-size: 11px;
}
.bsd-tag-err {
	background: #fff5f5;
	color: #c53030;
}
.bsd-tag-in {
	background: #f0fdf4;
	color: #16a34a;
}
.bsd-tag-out {
	background: #eff6ff;
	color: #3b82f6;
}
.bsd-tag-mappable {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	background: #fffbeb;
	color: #92400e;
}
.bsd-tag-map-btn {
	background: #fff;
	border: 1px solid #f6ad55;
	color: #c05621;
	border-radius: 4px;
	font-size: 9px;
	font-weight: 700;
	padding: 1px 6px;
	cursor: pointer;
}
.bsd-tag-map-btn:hover {
	background: #f6ad55;
	color: #fff;
}

.bsd-drawer-actions {
	padding: 12px 20px;
	display: flex;
	flex-direction: column;
	gap: 8px;
	border-top: 1px solid #edf2f7;
	background: #fff;
	flex-shrink: 0;
}
.bsd-btn-primary {
	background: #5e64ff;
	color: #fff;
	border: none;
	border-radius: 6px;
	padding: 8px 16px;
	cursor: pointer;
	font-size: 12px;
	font-weight: 600;
	text-align: center;
}
.bsd-btn-primary:hover {
	background: #4b52e0;
}
.bsd-btn-primary:disabled {
	background: #a0aec0;
	cursor: not-allowed;
}
.bsd-btn-secondary {
	background: #f7fafc;
	color: #4a5568;
	border: 1px solid #e2e8f0;
	border-radius: 6px;
	padding: 8px 16px;
	cursor: pointer;
	font-size: 12px;
	font-weight: 500;
	text-align: center;
}
.bsd-btn-secondary:hover {
	background: #edf2f7;
}
.bsd-drawer-actions .bsd-btn-ghost {
	display: block;
	text-align: center;
	text-decoration: none;
	padding: 7px 16px;
}

/* ── employee search modal ── */
.bsd-modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.3);
	z-index: 1100;
	display: flex;
	align-items: center;
	justify-content: center;
}
.modal-fade-enter-active,
.modal-fade-leave-active {
	transition: opacity 0.15s;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
	opacity: 0;
}
.bsd-modal {
	width: 460px;
	max-width: 92vw;
	max-height: 80vh;
	background: #fff;
	border-radius: 12px;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.18);
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.bsd-modal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 14px 18px;
	border-bottom: 1px solid #edf2f7;
	font-size: 13px;
}
.bsd-modal-body {
	padding: 14px 18px;
	overflow-y: auto;
}
.bsd-modal-search {
	width: 100%;
	border: 1px solid #e2e8f0;
	border-radius: 8px;
	padding: 8px 12px;
	font-size: 13px;
	margin-bottom: 10px;
	box-sizing: border-box;
}
.bsd-modal-search:focus {
	outline: none;
	border-color: #5e64ff;
	box-shadow: 0 0 0 2px rgba(94, 100, 255, 0.15);
}
.bsd-modal-results {
	display: flex;
	flex-direction: column;
	gap: 4px;
}
.bsd-modal-result-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 8px 10px;
	border-radius: 8px;
	cursor: pointer;
	transition: background 0.1s;
}
.bsd-modal-result-row:hover {
	background: #f7fafc;
}
.bsd-modal-result-main {
	display: flex;
	flex-direction: column;
}
.bsd-modal-result-name {
	font-size: 12px;
	font-weight: 600;
	color: #2d3748;
}
.bsd-modal-result-id {
	font-size: 10px;
	color: #a0aec0;
}
.bsd-modal-result-meta {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 10px;
	color: #718096;
}

/* ── employee view tab ── */
.bsd-emp-picker {
	border: 1px solid #e2e8f0;
	border-radius: 6px;
	padding: 6px 10px;
	font-size: 12px;
	background: #fff;
	width: 100%;
	height: 32px;
	text-align: left;
	cursor: pointer;
}
.bsd-emp-picker:hover {
	border-color: #cbd5e0;
}
.bsd-emp-header-card {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding: 14px 18px;
	margin-bottom: 16px;
}
.bsd-emp-header-name {
	font-size: 15px;
	font-weight: 700;
	color: #1a202c;
}
.bsd-emp-header-id {
	font-size: 11px;
	color: #a0aec0;
}
.bsd-emp-header-device {
	display: flex;
	align-items: center;
	gap: 8px;
}
.bsd-row-warning td {
	background: #fffaf0;
}
</style>
