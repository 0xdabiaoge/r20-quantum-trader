<script setup lang="ts">
import { fmtDateTime } from '../../utils/format';
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import DataTable from '../../components/admin/DataTable.vue'
import { useResource } from '../../composables/useResource'
import { Package, Cpu, KeyRound, RefreshCw } from 'lucide-vue-next'

// F2：取数样板收成一行
const { data, loading, error, reload: load } = useResource<any>('/api/v1/admin/agents')

function statusColor(s: string) {
  if (['success', 'running', 'online', 'idle'].includes(s)) return 'text-emerald-400'
  if (['failed', 'error', 'offline'].includes(s)) return 'text-rose-400'
  return 'text-amber-400'
}

</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[var(--ink-3)]">{{ t('admin.agents.desc') }}</p>
      <span class="text-[11px] text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">{{ t('admin.agents.policyChip') }}</span>
    </div>

    <div v-if="error" class="p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400">{{ error }}</div>
    <div v-if="loading" class="py-12 text-center text-xs text-[var(--ink-3)]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />{{ t('admin.agents.loading') }}</div>

    <template v-else-if="data">
      <!-- Agents -->
      <div class="rounded-xl border overflow-hidden shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color: var(--line-1); background-color: var(--surface-1);">
          <div class="flex items-center space-x-2">
            <Package class="w-4 h-4 text-blue-400" />
            <h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ t('nav.admin.agents') }}</h2>
        <p class="text-[11px] mt-0.5" style="color: var(--ink-2);">{{ t('admin.agents.roster') }}</p>
          </div>
          <button @click="load" class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-[11px] cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-2); color: var(--ink-1);">
            <RefreshCw class="w-3 h-3" />
            <span>{{ t('admin.agents.refresh') }}</span>
          </button>
        </div>
        <DataTable
          flat
          class="table-scroll-container"
          :rows="data.agents || []"
          :row-key="(a: any) => a.id"
          :empty-text="t('common.noRecords')"
        >
          <template #head>
            <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); background-color: var(--surface-1); color: var(--ink-2);">
                            <th class="py-2.5 px-4">{{ t('admin.agents.colUnit') }}</th>
                            <th class="py-2.5 px-3">{{ t('admin.agents.colRole') }}</th>
                            <th class="py-2.5 px-3">{{ t('admin.agents.colHealth') }}</th>
                            <th class="py-2.5 px-3">{{ t('admin.agents.colLastRun') }}</th>
                            <th class="py-2.5 px-3">{{ t('admin.agents.colResult') }}</th>
                            <th class="py-2.5 px-4 text-right">{{ t('admin.agents.colOutputAge') }}</th>
                          </tr>
          </template>
          <template #row="{ row: a }">
            <td class="py-2.5 px-4 font-bold" style="color: var(--ink-1);">{{ a.name }}</td>
            <td class="py-2.5 px-3" style="color: var(--ink-2);">{{ a.role }}</td>
            <td class="py-2.5 px-3 font-bold" :class="statusColor(a.health)">{{ a.health }}</td>
            <td class="py-2.5 px-3 num" style="color: var(--ink-3);">{{ fmtDateTime(a.last_run_at || t('admin.agents.notScheduled')) }}</td>
            <td class="py-2.5 px-3 font-bold" :class="statusColor(a.last_run_status)">{{ a.last_run_status }}</td>
            <td class="py-2.5 px-4 text-right" style="color: var(--ink-2);">{{ a.output_age_seconds != null ? t('admin.agents.minutesAgo', undefined, { n: Math.round(a.output_age_seconds / 60) }) : (a.output ? t('admin.agents.coldStart') : t('admin.agents.noOutput')) }}</td>
          </template>
        </DataTable>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <!-- Model Telemetry -->
        <div class="rounded-xl border overflow-hidden shadow-xs p-4" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 mb-3"><Cpu class="w-4 h-4 text-purple-400" /><h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ t('admin.agents.modelTelemetry') }}</h2></div>
          <div class="text-[11px] mb-3 p-2.5 rounded-lg border leading-relaxed" style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);">{{ data.prompt_policy }}</div>
          <div class="grid grid-cols-3 gap-2.5 mb-3 text-center">
            <div class="rounded-lg border p-2" style="background-color: var(--surface-1); border-color: var(--line-1);"><div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.agents.totalCalls') }}</div><div class="text-sm font-bold num mt-0.5" style="color: var(--ink-1);">{{ data.model_stats?.total_calls ?? '--' }}</div></div>
            <div class="rounded-lg border p-2" style="background-color: var(--surface-1); border-color: var(--line-1);"><div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.agents.successRate') }}</div><div class="text-sm font-bold num mt-0.5" :class="(data.model_stats?.total_calls ?? 0) > 0 && (data.model_stats?.successful_calls ?? 0) < (data.model_stats?.total_calls ?? 0) ? 'text-amber-500' : 'text-emerald-500'">{{ (data.model_stats?.total_calls ?? 0) > 0 ? Math.round(100 * (data.model_stats?.successful_calls ?? 0) / data.model_stats.total_calls) + '%' : '--' }}</div></div>
            <div class="rounded-lg border p-2" style="background-color: var(--surface-1); border-color: var(--line-1);"><div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.agents.avgLatency') }}</div><div class="text-sm font-bold num mt-0.5" style="color: var(--ink-1);">{{ data.model_stats?.avg_duration_ms ? Math.round(data.model_stats.avg_duration_ms) + 'ms' : '--' }}</div></div>
          </div>
          <DataTable
            flat
            class="table-scroll-container max-h-60 overflow-y-auto rounded-lg border"
            style="border-color: var(--line-1);"
            :rows="(data.model_calls || []).slice(0, 30) || []"
            :row-key="(c: any) => c.id"
            :empty-text="t('common.noRecords')"
          >
            <template #head>
              <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); background-color: var(--surface-1); color: var(--ink-2);">
                                <th class="py-2 px-3">{{ t('admin.agents.colCaller') }}</th>
                                <th class="py-2 px-2">{{ t('admin.agents.colModel') }}</th>
                                <th class="py-2 px-2">{{ t('admin.agents.colStatus') }}</th>
                                <th class="py-2 px-2">Tokens</th>
                                <th class="py-2 px-3 text-right">{{ t('admin.agents.colDuration') }}</th>
                              </tr>
            </template>
            <template #row="{ row: c }">
              <td class="py-1.5 px-3" style="color: var(--ink-2);">{{ c.caller || '--' }}</td>
              <td class="py-1.5 px-2 num" style="color: var(--ink-3);">{{ c.model || '--' }}</td>
              <td class="py-1.5 px-2 font-bold" :class="statusColor(c.status)">{{ c.status }}</td>
              <td class="py-1.5 px-2 num" style="color: var(--ink-2);">{{ c.total_tokens ?? '--' }}</td>
              <td class="py-1.5 px-3 text-right num" style="color: var(--ink-2);">{{ c.duration_ms ? Math.round(c.duration_ms) + 'ms' : '--' }}</td>
            </template>
          </DataTable>
        </div>

        <!-- Secret Store -->
        <div class="rounded-xl border p-4 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 mb-3"><KeyRound class="w-4 h-4 text-amber-500" /><h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ t('admin.agents.secretStore') }}</h2></div>
          <div class="space-y-1.5 text-xs">
            <div class="flex items-center justify-between border rounded-lg px-3 py-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
              <span style="color: var(--ink-2);">{{ t('admin.agents.storeStatus') }}</span>
              <span :class="data.secret_store?.initialized ? 'text-emerald-500 font-bold' : 'text-rose-500 font-bold'">{{ data.secret_store?.initialized ? t('admin.agents.initialized') : t('admin.agents.notInitialized') }} · {{ t('admin.agents.cipherCount', undefined, { count: data.secret_store?.count ?? 0 }) }} · {{ t('admin.agents.filePerm') }} {{ data.secret_store?.store_mode || '--' }}</span>
            </div>
            <div class="flex items-center justify-between border rounded-lg px-3 py-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
              <span style="color: var(--ink-2);">{{ t('admin.agents.readPriority') }}</span><span style="color: var(--ink-1);">{{ data.secret_store?.source_priority || 'encrypted-store-over-env' }}</span>
            </div>
            <div v-for="k in (data.secret_store?.keys || [])" :key="k" class="flex items-center justify-between border rounded-lg px-3 py-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
              <span style="color: var(--ink-2);">{{ k }}</span>
              <span class="text-emerald-500 font-bold">{{ t('admin.agents.configured') }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
