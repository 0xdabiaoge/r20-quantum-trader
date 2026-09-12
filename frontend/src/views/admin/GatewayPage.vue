<script setup lang="ts">
import { fmtDateTime } from '../../utils/format';
import { useToast } from '../../composables/useToast'
const toast = useToast()
import { ref, computed, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import { Zap, RefreshCw, RotateCcw, Server, Clock, AlertTriangle } from 'lucide-vue-next'

const { api } = useApi()

/** 调度时间 ISO → MM-DD HH:MM:SS */
function fmtJobTime(iso: string): string {
  return fmtDateTime(iso).slice(5)
}
const gw = ref<any>(null)
const loading = ref(true)

const deliveredCount = computed(() => (gw.value?.stats?.delivered ?? 0) + (gw.value?.stats?.accepted ?? 0))
const deliveryTotal = computed(() => Object.values(gw.value?.stats || {}).reduce((a: number, b: any) => a + Number(b || 0), 0))
const overdueCount = computed(() => (gw.value?.scheduler?.jobs || []).filter((j: any) => j.overdue).length)

async function load() {
  loading.value = true
  try {
    gw.value = await api('/api/v1/admin/gateway?limit=50')
  } catch (e: any) {
    toast.err(t('admin.gateway.msgs.loadFailed', undefined, { msg: e.message }))
  } finally {
    loading.value = false
  }
}

async function replayDelivery(id: number) {
  const phrase = prompt(t('admin.gateway.msgs.replayPrompt', undefined, { id: id }))
  if (!phrase) return
  try {
    await api(`/api/v1/admin/gateway/deliveries/${id}/replay`, {
      method: 'POST',
      body: JSON.stringify({ confirmation: phrase.trim().toUpperCase() }),
    })
    toast.ok(t('admin.gateway.msgs.replayed', undefined, { id: id }))
    await load()
  } catch (e: any) {
    toast.err(t('admin.gateway.msgs.replayFailed', undefined, { msg: e.message }))
  }
}

function statusColor(s: string) {
  if (s === 'success' || s === 'delivered' || s === 'ok') return 'text-emerald-400'
  if (s === 'dead' || s === 'failed' || s === 'error') return 'text-rose-400'
  if (s === 'pending' || s === 'retrying') return 'text-amber-400'
  return 'text-zinc-300'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[var(--ink-3)]">{{ t('admin.gateway.desc') }}</p>
      <span class="text-[11px] text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">{{ t('admin.gateway.opsBadge') }}</span>
    </div>
    <div v-if="loading" class="py-12 text-center text-xs text-[var(--ink-3)]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />{{ t('admin.gateway.loading') }}</div>

    <template v-else-if="gw">
      <!-- Worker & Stats Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div class="rounded-xl border p-4 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 text-[11px] mb-2" style="color: var(--ink-2);"><Server class="w-4 h-4 text-emerald-500" /><span>{{ t('admin.gateway.cards.process') }}</span></div>
          <div class="text-lg font-semibold" :class="gw.running ? 'text-emerald-500' : 'text-rose-500'">{{ gw.running ? 'ONLINE' : 'OFFLINE' }}</div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">PID {{ gw.pid || '--' }} · v{{ gw.version }}</div>
        </div>
        <div class="rounded-xl border p-4 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 text-[11px] mb-2" style="color: var(--ink-2);"><Zap class="w-4 h-4 text-blue-500" /><span>{{ t('admin.gateway.cards.deliveryQueue') }}</span></div>
          <div class="text-lg font-semibold num" style="color: var(--ink-1);">{{ deliveredCount }}<span class="text-xs" style="color: var(--ink-2);"> / {{ deliveryTotal }}</span></div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">{{ t('admin.gateway.cards.queueStats', undefined, { n: gw.stats?.pending ?? 0, m: gw.stats?.retry ?? 0 }) }}</div>
        </div>
        <div class="rounded-xl border p-4 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 text-[11px] mb-2" style="color: var(--ink-2);"><AlertTriangle class="w-4 h-4 text-amber-500" /><span>{{ t('admin.gateway.cards.deadLetter') }}</span></div>
          <div class="text-lg font-semibold num" :class="(gw.stats?.dead ?? 0) > 0 ? 'text-rose-500' : 'text-emerald-500'">{{ gw.stats?.dead ?? 0 }}<span class="text-xs" style="color: var(--ink-2);"> / {{ gw.event_health?.critical_total ?? 0 }}</span></div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">{{ t('admin.gateway.cards.criticalStats', undefined, { n: gw.event_health?.critical_unmet ?? 0, m: gw.event_health?.critical_failed ?? 0 }) }}</div>
        </div>
        <div class="rounded-xl border p-4 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-2 text-[11px] mb-2" style="color: var(--ink-2);"><Clock class="w-4 h-4 text-purple-500" /><span>{{ t('admin.gateway.cards.scheduler') }}</span></div>
          <div class="text-lg font-semibold num" style="color: var(--ink-1);">{{ gw.scheduler?.jobs?.length ?? 0 }}</div>
          <div class="text-[11px] mt-1" :class="overdueCount > 0 ? 'text-rose-500' : 'text-emerald-500'">{{ overdueCount > 0 ? t('admin.gateway.cards.overdueJobs', undefined, { n: overdueCount }) : t('admin.gateway.cards.noOverdue') }}</div>
        </div>
      </div>

      <!-- Scheduler Jobs -->
      <div v-if="gw.scheduler?.jobs?.length" class="rounded-xl border overflow-hidden shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color: var(--line-1); background-color: var(--surface-1);">
          <h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ t('nav.admin.gateway') }}</h2>
        <p class="text-[11px] mt-0.5" style="color: var(--ink-2);"> {{ t('admin.gateway.scheduler.subtitle') }} </p>
          <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.gateway.scheduler.managedJobs', undefined, { n: gw.scheduler.jobs.length }) }}</span>
        </div>
        <div class="table-scroll-container">
          <table class="w-full text-left text-xs whitespace-nowrap">
            <thead>
              <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); background-color: var(--surface-1); color: var(--ink-2);">
                <th class="py-2.5 px-4">{{ t('admin.gateway.scheduler.colJob') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.scheduler.colScript') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.scheduler.colTrigger') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.scheduler.colLastRun') }}</th>
                <th class="py-2.5 px-4 text-right">{{ t('admin.gateway.scheduler.colStatus') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="j in gw.scheduler.jobs" :key="j.name" class="border-b last:border-b-0 hover:bg-[var(--surface-3)] transition-colors" style="border-color: var(--line-1);">
                <td class="py-2.5 px-4 font-bold" style="color: var(--ink-1);">{{ j.name }}</td>
                <td class="py-2.5 px-3 text-[11px]" style="color: var(--ink-2);">{{ j.script }}</td>
                <td class="py-2.5 px-3 font-medium" style="color: var(--ink-1);">{{ j.schedule }}</td>
                <td class="py-2.5 px-3 num" style="color: var(--ink-3);">{{ j.last_scheduled_at ? fmtJobTime(j.last_scheduled_at) : t('admin.gateway.scheduler.notScheduled') }}</td>
                <td class="py-2.5 px-4 text-right font-bold" :class="j.overdue ? 'text-rose-400' : 'text-emerald-400'">
                  {{ j.overdue ? t('admin.gateway.scheduler.overdue') : t('admin.gateway.scheduler.normal') }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Deliveries -->
      <div class="rounded-xl border overflow-hidden shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color: var(--line-1); background-color: var(--surface-1);">
          <div class="flex items-center space-x-2">
            <h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ t('admin.gateway.deliveries.title') }}</h2>
            <span class="text-[11px] px-2 py-0.2 rounded border font-bold" style="background-color: var(--accent-bg); color: var(--accent); border-color: var(--accent-line);">
              {{ t('admin.gateway.deliveries.records', undefined, { n: gw.deliveries?.length || 0 }) }}
            </span>
          </div>
          <button @click="load" class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-[11px] cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-2); color: var(--ink-1);">
            <RefreshCw class="w-3 h-3" />
            <span>{{ t('admin.gateway.deliveries.refresh') }}</span>
          </button>
        </div>
        <div class="table-scroll-container max-h-[420px] overflow-y-auto">
          <table class="w-full text-left text-xs whitespace-nowrap">
            <thead class="sticky top-0 z-10">
              <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); background-color: var(--surface-1); color: var(--ink-2);">
                <th class="py-2.5 px-4">#</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.deliveries.colEventType') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.deliveries.colChannel') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.deliveries.colStatus') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.deliveries.colAttempts') }}</th>
                <th class="py-2.5 px-3">{{ t('admin.gateway.deliveries.colTime') }}</th>
                <th class="py-2.5 px-4 text-right">{{ t('admin.gateway.deliveries.colActions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in gw.deliveries" :key="d.id" class="border-b last:border-b-0 hover:bg-[var(--surface-3)] transition-colors" style="border-color: var(--line-1);">
                <td class="py-2.5 px-4 num" style="color: var(--ink-3);">{{ d.id }}</td>
                <td class="py-2.5 px-3 font-bold" style="color: var(--ink-1);">{{ d.event_type || d.topic || '--' }}</td>
                <td class="py-2.5 px-3" style="color: var(--ink-2);">{{ d.channel || '--' }}</td>
                <td class="py-2.5 px-3 font-bold" :class="statusColor(d.status)">{{ d.status }}</td>
                <td class="py-2.5 px-3 num" style="color: var(--ink-2);">{{ d.attempts ?? d.attempt_count ?? 1 }}</td>
                <td class="py-2.5 px-3 num" style="color: var(--ink-3);">{{ fmtDateTime(d.created_at || d.time) }}</td>
                <td class="py-2.5 px-4 text-right">
                  <button v-if="d.status === 'dead'" @click="replayDelivery(d.id)" class="flex items-center space-x-1 ml-auto px-2 py-1 rounded-md border text-[11px] cursor-pointer transition-colors" style="background-color: var(--warn-bg); border-color: var(--warn-line); color: var(--warn);">
                    <RotateCcw class="w-3 h-3" /><span>{{ t('admin.gateway.deliveries.replay') }}</span>
                  </button>
                  <span v-else class="text-[11px]" style="color: var(--ink-3);">--</span>
                </td>
              </tr>
              <tr v-if="!gw.deliveries || gw.deliveries.length === 0">
                <td colspan="7" class="py-8 text-center" style="color: var(--ink-3);">{{ t('admin.gateway.deliveries.empty') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>
