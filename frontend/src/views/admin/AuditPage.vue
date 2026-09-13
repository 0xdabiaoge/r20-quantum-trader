<script setup lang="ts">
import { fmtDateTime } from '../../utils/format';
import { ref, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'
import DataTable from '../../components/admin/DataTable.vue'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import { Scroll, RefreshCw, Search } from 'lucide-vue-next'

const { api } = useApi()
const records = ref<any[]>([])
const loading = ref(true)
const search = ref('')
const detailRec = ref<any | null>(null)

async function load() {
  loading.value = true
  try {
    const res = await api('/api/v1/admin/audit?limit=200')
    records.value = res.records || []
  } finally {
    loading.value = false
  }
}

function filtered() {
  const q = search.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter((r) =>
    [r.action, r.status, JSON.stringify(r.detail || '')].join(' ').toLowerCase().includes(q)
  )
}

function statusColor(s: string) {
  if (s === 'success' || s === 'completed' || s === 'accepted') return 'text-emerald-400'
  if (s === 'failed' || s === 'denied') return 'text-rose-400'
  return 'text-amber-400'
}

onMounted(load)
</script>

<template>
  <div class="space-y-4 max-w-[2048px] mx-auto">
    <div class="flex items-center justify-between">
      <p class="text-xs" style="color: var(--ink-2);">{{ t('admin.audit.intro') }}</p>
      <span
        class="text-[11px] px-2 py-1 rounded border font-bold"
        style="background-color: var(--accent-bg); color: var(--accent); border-color: var(--accent-line);"
      >
        {{ t('admin.audit.badge') }}
      </span>
    </div>

    <!-- Toolbar -->
    <div class="rounded-xl border p-3 flex items-center gap-3 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
      <div class="flex items-center space-x-2 flex-1 rounded-lg px-3 py-2 border transition-colors" style="background-color: var(--surface-input); border-color: var(--line-1);">
        <Search class="w-3.5 h-3.5" style="color: var(--ink-3);" />
        <input v-model="search" :placeholder="t('admin.audit.searchPlaceholder')" class="flex-1 bg-transparent text-xs outline-none" style="color: var(--ink-1);" />
      </div>
      <button @click="load" class="flex items-center space-x-1 px-3 py-2 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': loading }" /><span>{{ t('admin.audit.refresh') }}</span>
      </button>
    </div>

    <!-- Audit Rows -->
    <div class="rounded-xl border overflow-hidden shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
      <div class="px-4 py-3 border-b flex items-center justify-between" style="border-color: var(--line-1); background-color: var(--surface-1);">
        <div class="flex items-center space-x-2">
          <Scroll class="w-4 h-4 text-purple-400" />
          <h2 class="text-xs font-semibold" style="color: var(--ink-1);">
            {{ t('nav.admin.audit') }} ({{ filtered().length }} {{ t('admin.audit.entries') }})
          </h2>
        </div>
        <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.audit.rowHint') }}</span>
      </div>

      <div class="max-h-[580px] overflow-y-auto">
        <DataTable
          flat
          clickable
          :columns="[
            { key: 'timestamp', label: t('admin.audit.colTimestamp') },
            { key: 'action', label: t('admin.audit.colAction') },
            { key: 'status', label: t('admin.audit.colStatus') },
            { key: 'detail', label: t('admin.audit.colDetail') },
          ]"
          :rows="filtered()"
          :row-key="(_r: any, i: number) => i"
          :empty-text="t('admin.audit.empty')"
          @row-click="detailRec = $event"
        >
          <template #cell-timestamp="{ row }">
            <span class="num" style="color: var(--ink-3);">{{ fmtDateTime(row.timestamp) }}</span>
          </template>
          <template #cell-action="{ row }">
            <span class="font-bold" style="color: var(--accent);">{{ row.action }}</span>
          </template>
          <template #cell-status="{ row }">
            <span class="font-bold" :class="statusColor(row.status)">{{ row.status }}</span>
          </template>
          <template #cell-detail="{ row }">
            <span class="block max-w-[480px] truncate">
              <strong style="color: var(--ink-1);">{{ row.detail?.actor || row.detail?.username || 'system' }}</strong>
              <span class="ml-1 block break-all opacity-70" style="color: var(--ink-2); max-width: 420px">· {{ JSON.stringify(row.detail || {}) }}</span>
            </span>
          </template>
        </DataTable>
      </div>
    </div>

    <!-- Detail Modal -->
    <div v-if="detailRec" class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-xs flex items-center justify-center p-4" @click.self="detailRec = null">
      <div class="rounded-xl border p-5 sm:p-6 w-full max-w-[640px] max-h-[88dvh] overflow-y-auto shadow-2xl transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <h3 class="text-sm font-bold mb-3" style="color: var(--ink-1);">{{ t('admin.audit.detailTitle') }} · {{ detailRec.action }}</h3>
        <pre class="border rounded-lg p-3 text-xs whitespace-pre-wrap max-h-[400px] overflow-y-auto select-text" style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);">{{ JSON.stringify(detailRec, null, 2) }}</pre>
        <div class="flex justify-end mt-4">
          <button @click="detailRec = null" class="px-4 py-2 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs" style="background-color: var(--surface-1); border-color: var(--line-2); color: var(--ink-1);">{{ t('admin.audit.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>
