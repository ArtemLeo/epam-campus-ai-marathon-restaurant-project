<template>
  <div class="reports-page container">
    <div class="page-header"><h1>{{ t('staff.reportsTitle') }}</h1><p>{{ t('staff.reportsSubtitle') }}</p></div>
    <form class="card reports-form" @submit.prevent="generate">
      <div class="form-row">
        <div class="field"><label for="report-location">{{ t('staff.location') }}</label><select id="report-location" v-model="params.locationId" required><option value="" disabled>{{ t('staff.selectLocation') }}</option><option v-for="loc in locations" :key="loc.id" :value="loc.id">{{ loc.address }}</option></select></div>
        <div class="field"><label for="report-start-date">{{ t('staff.startDate') }}</label><input id="report-start-date" v-model="params.startDate" type="date" :max="params.endDate" required /></div>
        <div class="field"><label for="report-end-date">{{ t('staff.endDate') }}</label><input id="report-end-date" v-model="params.endDate" type="date" :min="params.startDate" required /></div>
        <div class="field"><label for="report-report-type">{{ t('staff.reportType') }}</label><select id="report-report-type" v-model.number="params.type"><option :value="1">{{ t('staff.sales') }}</option><option :value="0">{{ t('staff.serviceByWaiter') }}</option></select></div>
      </div>
      <div class="report-actions">
        <AppButton type="submit" :loading="generating" :disabled="!valid">{{ t('staff.generateReport') }}</AppButton>
        <div class="field"><label for="report-download-format">{{ t('staff.downloadFormat') }}</label><select id="report-download-format" v-model="format"><option value="csv">CSV</option><option value="excel">Excel</option><option value="pdf">PDF</option></select></div>
        <AppButton variant="secondary" :loading="downloading" :disabled="!valid" @click="download(params)">{{ t('staff.download') }}</AppButton>
      </div>
      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </form>
    <LoadingSpinner v-if="loading" :text="t('staff.loadingReports')" />
    <section v-if="generated !== null" class="card history-card">
      <h2>{{ t('staff.generatedReport') }}</h2>
      <p v-if="!generated.length">{{ t('staff.noActivity') }}</p>
      <table v-else>
        <thead><tr><th>{{ t('staff.location') }}</th><th>{{ t('staff.waiter') }}</th><th>{{ t('staff.orders') }}</th><th>{{ t('staff.change') }}</th><th>{{ t('staff.revenue') }}</th><th>{{ t('staff.change') }}</th><th>{{ t('staff.averageFeedback') }}</th></tr></thead>
        <tbody>
          <tr v-for="(row, i) in generated" :key="i">
            <td>{{ row.locationName }}</td><td>{{ row.waiterName || '—' }}</td><td>{{ formatNumber(row.totalOrders) }}</td><td>{{ delta(row.deltaTotalOrders) }}</td>
            <td>{{ row.revenue === undefined ? '—' : formatCurrency(row.revenue) }}</td><td>{{ delta(row.deltaRevenue) }}</td><td>{{ formatNumber(row.avgServiceFeedback ?? row.avgCuisineFeedback) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
    <section class="card history-card">
      <h2>{{ t('staff.reportHistory') }}</h2><p v-if="!history.length">{{ t('staff.noReports') }}</p>
      <table v-else>
        <thead><tr><th>{{ t('staff.type') }}</th><th>{{ t('staff.location') }}</th><th>{{ t('staff.period') }}</th><th>{{ t('staff.file') }}</th></tr></thead>
        <tbody><tr v-for="(report, i) in history" :key="i"><td>{{ t(report.reportType === 0 ? 'staff.service' : 'staff.sales') }}</td><td>{{ report.locationName }}</td><td>{{ periodDate(report.startDate) }} – {{ periodDate(report.endDate) }}</td><td><button class="button button--secondary button--small" :disabled="downloading" @click="download({ ...report, type: report.reportType })">{{ t('staff.downloadFile', { format: format.toUpperCase() }) }}</button></td></tr></tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { t, locale, localeTag, type Locale } from '@/i18n'
import { reportsApi, locationsApi, type Location, type ReportFormat, type ReportHistoryItem, type ReportQuery, type ReportRow } from '@/services/api'
import { saveFile } from '@/services/http/api-client'
import { restaurantToday } from '@/utils/date-time'
import { formatCurrency, formatNumber, formatPercent } from '@/utils/formatters'
import AppButton from '@/components/shared/AppButton.vue'
import LoadingSpinner from '@/components/shared/LoadingSpinner.vue'

const locations = ref<Location[]>([])
const history = ref<ReportHistoryItem[]>([])
const generated = ref<ReportRow[] | null>(null)
const params = ref<ReportQuery>({ locationId: '', startDate: restaurantToday(Date.now() - 7 * 86_400_000), endDate: restaurantToday(), type: 1 })
const format = ref<ReportFormat>('csv')
const loading = ref(true)
const generating = ref(false)
const downloading = ref(false)
const error = ref('')
const valid = computed(() => !!params.value.locationId && !!params.value.startDate && params.value.endDate >= params.value.startDate)
const delta = (value?: number) => value == null ? '—' : `${value > 0 ? '+' : ''}${formatPercent(value)}`
// Report ranges are calendar dates, not instants in the restaurant timezone.
const periodDate = (value: string) => new Intl.DateTimeFormat(localeTag.value, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${value}T12:00:00Z`))

async function generate(): Promise<void> {
  if (!valid.value) return
  generating.value = true
  error.value = ''
  try { generated.value = await reportsApi.generate(params.value); history.value = await reportsApi.history() }
  catch (err) { error.value = err instanceof Error ? err.message : t('staff.reportGenerateFailed') }
  finally { generating.value = false }
}
async function download(query: ReportQuery): Promise<void> {
  downloading.value = true
  error.value = ''
  try { saveFile(await reportsApi.download({ ...query, locale: locale.value as Locale }, format.value)) }
  catch (err) { error.value = err instanceof Error ? err.message : t('staff.reportDownloadFailed') }
  finally { downloading.value = false }
}
onMounted(async () => {
  try {
    [locations.value, history.value] = await Promise.all([locationsApi.list(), reportsApi.history()])
    params.value.locationId = locations.value[0]?.id ?? ''
  } catch (err) { error.value = err instanceof Error ? err.message : t('staff.reportsLoadFailed') }
  finally { loading.value = false }
})
</script>

<style scoped>
.reports-page { padding-bottom: 48px; }
.reports-form, .history-card { padding: 24px; margin-bottom: 24px; }
.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.field { display: grid; gap: 8px; }
input, select { padding: 10px; border: 1px solid var(--neutral-300); border-radius: 8px; font: inherit; background: white; min-width: 0; }
.report-actions { display: flex; flex-wrap: wrap; gap: 16px; align-items: end; margin-top: 20px; }
.history-card { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 12px; border-bottom: 1px solid var(--neutral-200); text-align: left; }
.form-error { color: var(--red-600); }
</style>
