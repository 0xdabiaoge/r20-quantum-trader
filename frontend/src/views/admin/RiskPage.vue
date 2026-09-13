<script setup lang="ts">
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
const toast = useToast()
const { ask } = useConfirm()
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from '../../composables/useI18n'
const { t } = useI18n()
import { useApi } from '../../composables/useApi'
import { useAsyncAction } from '../../composables/useAsyncAction'
import { useDashboardStore } from '../../stores/dashboard'
import PageHeader from '../../components/admin/PageHeader.vue'
import DangerZone from '../../components/admin/page-parts/DangerZone.vue'
import {ShieldAlert,
  Save,
  RotateCcw,
  Loader2,
  Info,
  Layers,
  Target,
  Flame,
  TrendingUp} from 'lucide-vue-next'

const { api } = useApi()
const store = useDashboardStore()

const busy = ref<'save' | 'reset' | ''>('')

const schema = ref<{ groups: any[]; params: any[]; high_risk_phrase?: string } | null>(null)
/** 引擎此刻的口径（审计未完成清单#3）：文件值 = 下一周期生效；进程内值 = 长驻进程正在用的 */
const processValues = ref<Record<string, number>>({})
const processFresh = ref<{ stale: boolean; note: string; env_file_mtime: number | null; loaded_at: number | null } | null>(null)
const engineValues = ref<Record<string, any> | null>(null)
const driftCount = computed(() => {
  const keys = Object.keys(processValues.value || {})
  return keys.filter((k) => {
    const file = serverValues.value[k]
    const proc = processValues.value[k]
    return typeof file === 'number' && typeof proc === 'number' && Math.abs(file - proc) > 1e-9
  })
})
const suites = ref<any[]>([])
const effectText = ref('')
const serverValues = ref<Record<string, number>>({})
const draft = reactive<Record<string, number>>({})       // 原生值（比例类为小数）
const disp = reactive<Record<string, string>>({})        // 显示值字符串（用户编辑）

const activeSuiteId = computed(() => {
  if (dirtyKeys.value.length || !suites.value.length) return ''
  for (const s of suites.value) {
    const match = Object.entries(s.values as Record<string, number>).every(
      ([k, v]) => Math.abs((serverValues.value[k] ?? NaN) - v) < 1e-9)
    if (match) return s.id
  }
  return ''
})

async function applySuite(s: any) {
  if (busy.value) return
  busy.value = 'save'
  try {
    const res = await api('/api/v1/admin/risk', { method: 'POST', body: JSON.stringify({ suite_id: s.id }) })
    syncFromServer(res.values)
    toast.ok(`已一键应用「${s.name}」预设 ✓ ${res.effect}`)
  } catch (e: any) {
    toast.err(`应用预设失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

const groupIcons: Record<string, any> = {
  exposure: Layers,
  per_trade: Target,
  stop_loss: Flame,
  pyramiding: TrendingUp,
}

// 杠杆区间合并行的参数引用（schema 缺失时自动退回通用行渲染，不炸页面）
const levMinP = computed<any>(() => schema.value?.params.find((x: any) => x.key === 'R20_MIN_LEVERAGE') || null)
const levMaxP = computed<any>(() => schema.value?.params.find((x: any) => x.key === 'R20_MAX_LEVERAGE') || null)
const levInverted = computed(() => !!levMinP.value && !!levMaxP.value
  && (draft[levMinP.value.key] ?? 0) > (draft[levMaxP.value.key] ?? 0))

function toDisplay(p: any, native: number): string {
  const v = native * (p.display_scale || 1)
  // 去掉浮点噪声，最多保留 4 位小数
  return String(Math.round(v * 10000) / 10000)
}

function fromDisplay(p: any, display: string): number | null {
  const raw = parseFloat(display)
  if (Number.isNaN(raw)) return null
  let native = raw / (p.display_scale || 1)
  if (p.type === 'int') native = Math.round(native)
  else native = Math.round(native * 1e6) / 1e6
  return native
}

function syncFromServer(values: Record<string, number>) {
  serverValues.value = { ...values }
  for (const p of schema.value!.params) {
    const v = values[p.key]
    draft[p.key] = v
    disp[p.key] = toDisplay(p, v)
  }
}

// F2：动作类样板（busy + 统一错误出口）。error → toast 与原实现一致；
// initialBusy: true 保持"首帧即加载态"（原为 loading = ref(true)）。
const { run: loadData, busy: loading } = useAsyncAction(async () => {
  // 带上页面上展示的可用权益，让后端派生"引擎此刻的口径"（权益未知时后端会如实标 None）
  const eq = Number((store as any)?.data?.account?.avail_eq)
  const query = Number.isFinite(eq) && eq > 0 ? `?equity=${eq}` : ''
  const res = await api<any>(`/api/v1/admin/risk${query}`)
  schema.value = res.schema
  suites.value = res.suites || []
  effectText.value = res.effect || ''
  processValues.value = res.process_values || {}
  processFresh.value = res.process_freshness || null
  engineValues.value = res.engine_values || null
  syncFromServer(res.values)
}, { onError: (e) => toast.err(`加载失败: ${e.message}`), initialBusy: true })

const dirtyKeys = computed(() => {
  if (!schema.value) return []
  return schema.value.params
    .filter((p: any) => draft[p.key] !== undefined && serverValues.value[p.key] !== undefined
      && Math.abs((draft[p.key] ?? 0) - (serverValues.value[p.key] ?? 0)) > 1e-9)
    .map((p: any) => p.key)
})

function isCustomized(p: any): boolean {
  return serverValues.value[p.key] !== undefined
    && Math.abs(serverValues.value[p.key] - p.default) > 1e-9
}

function onFieldInput(p: any) {
  const native = fromDisplay(p, disp[p.key])
  if (native !== null) draft[p.key] = native
}

function revertOne(p: any) {
  draft[p.key] = p.default
  disp[p.key] = toDisplay(p, p.default)
}


async function saveChanges() {
  if (!dirtyKeys.value.length) return
  const bad = schema.value!.params.filter((p: any) => {
    const v = draft[p.key]
    return dirtyKeys.value.includes(p.key) && (v < p.min || v > p.max)
  })
  if (bad.length) {
    toast.err(`以下参数越界：${bad.map((p: any) => p.label).join('、')}`)
    return
  }
  if (levInverted.value) {
    toast.err('杠杆下限不能高于上限，请先修正「单笔杠杆区间」')
    return
  }
  if (levInverted.value) {
    toast.err('杠杆下限不能高于上限，请调整区间后再保存')
    return
  }
  // 审计 P2-9：极端值（单标的占比≥50% / 日亏≥25% 权益 / 杠杆≥10x 等）此前一次点击即落盘，
  // 误触就能把硬风控放松到接近失效。后端要求逐字短语 HIGH RISK，这里补上确认框。
  const values: Record<string, number> = {}
  for (const k of dirtyKeys.value) values[k] = draft[k]
  const limitOf = (key: string): number | null => {
    const row = schema.value?.params.find((x: any) => x.key === key)
    return row && (row as any).high_risk_at != null ? Number((row as any).high_risk_at) : null
  }
  const extreme = dirtyKeys.value.filter((k) => {
    const lim = limitOf(k)
    return lim != null && Number(values[k]) >= lim
  })
  let confirmation = ''
  if (extreme.length) {
    const detail = extreme
      .map((k) => `${schema.value?.params.find((x: any) => x.key === k)?.label || k} = ${values[k]}`)
      .join('；')
    const _ok = await ask({
      title: '极端风控参数确认',
      desc: `以下参数已进入极端区间，将显著放松硬风控：${detail}`,
      danger: true,
      confirmPhrase: 'HIGH RISK',
      okText: '确认写入',
    })
    if (!_ok) return
    confirmation = 'HIGH RISK'
  }
  busy.value = 'save'
  try {
    const res = await api('/api/v1/admin/risk', { method: 'POST', body: JSON.stringify({ values, confirmation }) })
    syncFromServer(res.values)
    toast.ok(`已保存 ${res.updated.length} 项修改 ✓ ${res.effect}`)
  } catch (e: any) {
    toast.err(`保存失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function resetAll() {
  // 批C(2026-09-13)·补门禁：本操作把全部风控参数恢复代码默认基线（含仓位/日亏上限），
  // 此前**零确认**一次点击即执行，而后端本就要求逐字短语 `RESET RISK`（前端把短语写死
  // 在请求体里，等于保险被旁路）。移动端误触即放松风控，风险极高——现要求逐字确认。
  const _ok = await ask({
    title: '重置全部风控参数',
    desc: '所有风控阈值将恢复为代码默认基线（含单笔仓位上限、日亏上限、杠杆上限等）',
    danger: true,
    confirmPhrase: 'RESET RISK',
    okText: '重置基线',
  })
  if (!_ok) return
  busy.value = 'reset'
  try {
    const res = await api('/api/v1/admin/risk/reset', { method: 'POST', body: JSON.stringify({ confirmation: 'RESET RISK' }) })
    syncFromServer(res.values)
    toast.ok(`已恢复代码默认基线 ✓ ${res.effect}`)
  } catch (e: any) {
    toast.err(`重置失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-4 max-w-[1400px] mx-auto pb-24">
    <PageHeader
      :title="t('nav.admin.risk')"
      :description="t('admin.risk.pageDesc')"
    >
      <template #actions>
        <span class="badge-lever">
          {{ dirtyKeys.length ? t('admin.risk.pendingSave', undefined, { n: dirtyKeys.length }) : t('admin.risk.inSync') }}
        </span>
      </template>
    </PageHeader>

    <!-- Effect banner -->
    <div class="p-3 rounded-lg text-[11px] border flex items-start gap-2" style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-2);">
      <Info class="w-3.5 h-3.5 shrink-0 mt-0.5" style="color: var(--accent, var(--info));" />
      <div class="space-y-1">
        <p>{{ effectText || t('admin.risk.effectHint') }}</p>
        <p v-if="processFresh?.stale" style="color: var(--warn, #d97706);">
          ⚠ {{ t('admin.risk.processStale') }}（{{ t('admin.risk.processDiffCount', undefined, { n: driftCount.length }) }}）
        </p>
        <p v-else-if="driftCount.length" style="color: var(--warn, #d97706);">
          ⚠ {{ t('admin.risk.processDiffCount', undefined, { n: driftCount.length }) }}
        </p>
      </div>
    </div>

    <!-- 引擎此刻的口径（审计未完成清单#3）：文件值 vs 进程内快照 vs 派生执行口径 -->
    <div v-if="engineValues" class="rounded-xl border p-4 space-y-3" style="background-color: var(--surface-2); border-color: var(--line-1);">
      <div class="flex items-center gap-2">
        <Target class="w-4 h-4" style="color: var(--accent);" />
        <span class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.risk.engineNow') }}</span>
        <span class="text-[10px] num" style="color: var(--ink-3);">{{ t('admin.risk.engineNowHint') }}</span>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[11px]">
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineDailyLoss') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">
            {{ engineValues.daily_loss_limit_usdt == null ? '--' : `${engineValues.daily_loss_limit_usdt} U` }}
          </div>
        </div>
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineSingleAsset') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">
            {{ engineValues.single_asset_margin_usdt == null ? '--' : `${engineValues.single_asset_margin_usdt} U` }}
          </div>
        </div>
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineMaxPositions') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">
            {{ engineValues.max_positions == null ? '--' : `${engineValues.max_positions} / ${engineValues.max_same_direction}` }}
          </div>
        </div>
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineTargetRR') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">≥ {{ engineValues.target_rr }}</div>
        </div>
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineConfBand') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">
            {{ (engineValues.confidence_band || []).join('% ~ ') }}%
          </div>
        </div>
        <div class="card-flat p-2">
          <div style="color: var(--ink-3);">{{ t('admin.risk.engineEquityUsed') }}</div>
          <div class="num font-bold" style="color: var(--ink-1);">
            {{ engineValues.usdt_available_used == null ? t('admin.risk.engineEquityUnknown') : `${engineValues.usdt_available_used} U` }}
          </div>
        </div>
      </div>
      <p v-if="driftCount.length" class="text-[11px]" style="color: var(--warn, #d97706);">
        {{ t('admin.risk.engineDrift') }}：{{ driftCount.map((k) => schema?.params.find((x: any) => x.key === k)?.label || k).join('、') }}
      </p>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-24">
      <Loader2 class="w-6 h-6 animate-spin" style="color: var(--ink-2);" />
    </div>

    <template v-else-if="schema">
      <!-- 优质预设套件 -->
      <div v-if="suites.length" class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div
          v-for="s in suites"
          :key="s.id"
          class="rounded-xl border p-4 flex flex-col gap-2 transition-all"
          :style="activeSuiteId === s.id
            ? { backgroundColor: 'var(--surface-2)', borderColor: 'var(--ink-1)', boxShadow: '0 0 0 1px var(--ink-1)' }
            : { backgroundColor: 'var(--surface-2)', borderColor: 'var(--line-1)' }"
        >
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-xs font-semibold" style="color: var(--ink-1);">{{ s.name }}</h3>
            <span v-if="activeSuiteId === s.id" class="text-[11px] px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">{{ t('admin.risk.activeNow') }}</span>
            <span v-else class="text-[11px] opacity-60" style="color: var(--ink-2);">{{ s.tagline }}</span>
          </div>
          <p class="text-[11px] leading-relaxed flex-1" style="color: var(--ink-2);">{{ s.desc }}</p>
          <button
            @click="applySuite(s)"
            :disabled="busy !== '' || activeSuiteId === s.id"
            class="self-start mt-1 px-3 py-1.5 rounded-lg text-[11px] font-bold border transition-colors disabled:opacity-40"
            style="border-color: var(--line-1); color: var(--ink-1);"
          >
            {{ activeSuiteId === s.id ? t('admin.risk.applied') : t('admin.risk.applySuite') }}
          </button>
        </div>
      </div>

      <!-- Group cards -->
      <div
        v-for="group in schema.groups"
        :key="group.id"
        class="rounded-xl border overflow-hidden"
        style="background-color: var(--surface-2); border-color: var(--line-1);"
      >
        <div class="px-4 py-3 border-b flex items-center gap-2" style="border-color: var(--line-1);">
          <component :is="groupIcons[group.id] || ShieldAlert" class="w-4 h-4" style="color: var(--ink-1);" />
          <div>
            <h2 class="text-xs font-semibold" style="color: var(--ink-1);">{{ group.label }}</h2>
            <p class="text-[11px] mt-0.5" style="color: var(--ink-2);">{{ group.desc }}</p>
          </div>
        </div>

        <div class="divide-y" style="border-color: var(--line-1);">
          <!-- 杠杆区间合并行：下限~上限一体编辑（用户 2026-09-10 明确要求「下限到上限」形态） -->
          <div
            v-if="group.id === 'exposure' && levMinP && levMaxP"
            class="px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4"
            style="border-color: var(--line-1);"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.risk.levRangeTitle') }}</span>
                <span v-if="isCustomized(levMinP) || isCustomized(levMaxP)" class="text-[11px] px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-400">{{ t('admin.risk.customized') }}</span>
                <span v-if="levInverted" class="text-[11px] px-1.5 py-0.5 rounded border border-rose-500/40 bg-rose-500/10 text-rose-400">{{ t('admin.risk.levInverted') }}</span>
              </div>
              <p class="text-[11px] mt-1 leading-relaxed" style="color: var(--ink-2);">{{ t('admin.risk.levRangeDesc') }}</p>
              <p class="text-[11px] mt-0.5 opacity-60" style="color: var(--ink-2);">
                {{ t('admin.risk.defaultWord') }} {{ toDisplay(levMinP, levMinP.default) }} ~ {{ toDisplay(levMaxP, levMaxP.default) }} x · {{ t('admin.risk.configurableWord') }} {{ toDisplay(levMinP, levMinP.min) }} ~ {{ toDisplay(levMaxP, levMaxP.max) }} x · {{ levMinP.key }} / {{ levMaxP.key }}
              </p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <div class="flex items-center rounded-lg border overflow-hidden" style="background-color: var(--surface-input); border-color: var(--line-1);">
                <input
                  v-model="disp[levMinP.key]"
                  @input="onFieldInput(levMinP)"
                  type="number"
                  :min="toDisplay(levMinP, levMinP.min)"
                  :max="toDisplay(levMinP, levMinP.max)"
                  :step="levMinP.step"
                  class="w-20 sm:w-24 px-2.5 py-2 text-xs outline-none text-right"
                  style="background: transparent; color: var(--ink-1);"
                  :class="draft[levMinP.key] < levMinP.min || draft[levMinP.key] > levMinP.max || levInverted ? 'ring-1 ring-rose-500' : ''"
                />
                <span class="px-1 text-[11px]" style="color: var(--ink-2);">x</span>
                <span class="px-0.5 text-[11px]" style="color: var(--ink-3);">~</span>
                <input
                  v-model="disp[levMaxP.key]"
                  @input="onFieldInput(levMaxP)"
                  type="number"
                  :min="toDisplay(levMaxP, levMaxP.min)"
                  :max="toDisplay(levMaxP, levMaxP.max)"
                  :step="levMaxP.step"
                  class="w-20 sm:w-24 px-2.5 py-2 text-xs outline-none text-right"
                  style="background: transparent; color: var(--ink-1);"
                  :class="draft[levMaxP.key] < levMaxP.min || draft[levMaxP.key] > levMaxP.max || levInverted ? 'ring-1 ring-rose-500' : ''"
                />
                <span class="px-2 text-[11px] whitespace-nowrap select-none" style="color: var(--ink-2);">x</span>
              </div>
            </div>
          </div>
          <div
            v-for="p in schema.params.filter((x: any) => x.group === group.id && x.key !== 'R20_MIN_LEVERAGE' && x.key !== 'R20_MAX_LEVERAGE')"
            :key="p.key"
            class="px-4 py-3 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4"
            style="border-color: var(--line-1);"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-bold" style="color: var(--ink-1);">{{ p.label }}</span>
                <span v-if="isCustomized(p)" class="text-[11px] px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-400">{{ t('admin.risk.customized') }}</span>
              </div>
              <p class="text-[11px] mt-1 leading-relaxed" style="color: var(--ink-2);">{{ p.desc }}</p>
              <p class="text-[11px] mt-0.5 opacity-60" style="color: var(--ink-2);">
                {{ t('admin.risk.defaultWord') }} {{ toDisplay(p, p.default) }} {{ p.unit }} · {{ t('admin.risk.rangeWord') }} {{ toDisplay(p, p.min) }} ~ {{ toDisplay(p, p.max) }} {{ p.unit }} · <span class="opacity-70">{{ p.key }}</span>
              </p>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <div class="flex items-center rounded-lg border overflow-hidden" style="background-color: var(--surface-input); border-color: var(--line-1);">
                <input
                  v-model="disp[p.key]"
                  @input="onFieldInput(p)"
                  type="number"
                  :min="toDisplay(p, p.min)"
                  :max="toDisplay(p, p.max)"
                  :step="p.step * (p.display_scale || 1)"
                  class="w-24 sm:w-28 px-2.5 py-2 text-xs outline-none text-right"
                  style="background: transparent; color: var(--ink-1);"
                  :class="draft[p.key] < p.min || draft[p.key] > p.max ? 'ring-1 ring-rose-500' : ''"
                />
                <span class="px-2 text-[11px] whitespace-nowrap select-none" style="color: var(--ink-2);">{{ p.unit }}</span>
              </div>
              <button
                v-if="Math.abs((draft[p.key] ?? 0) - p.default) > 1e-9"
                @click="revertOne(p)"
                class="p-2 rounded-lg border transition-colors hover:bg-[var(--surface-3)]"
                style="border-color: var(--line-1); color: var(--ink-2);"
                :title="t('admin.risk.revertItem')"
              >
                <RotateCcw class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Danger zone: reset (P2 shared component) -->
      <DangerZone
        :title="t('admin.risk.resetTitle')"
        :description="t('admin.risk.resetDesc')"
        confirm-phrase="RESET RISK"
        :action-label="busy === 'reset' ? t('admin.risk.resetting') : t('admin.risk.resetAllBtn')"
        @confirm="resetAll"
      />
    </template>

    <!-- Sticky save bar -->
    <div
      v-if="schema && dirtyKeys.length"
      class="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 px-4 py-3 rounded-2xl border shadow-2xl flex items-center gap-3"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <span class="text-xs" style="color: var(--ink-1);">{{ t('admin.risk.unsavedCount', undefined, { n: dirtyKeys.length }) }}</span>
      <button
        @click="saveChanges"
        :disabled="busy !== ''"
        class="px-4 py-2 rounded-lg text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
        style="background-color: var(--accent); color: var(--accent-ink);"
      >
        <Save class="w-3.5 h-3.5" />
        {{ busy === 'save' ? t('admin.risk.saving') : t('admin.risk.saveApply') }}
      </button>
    </div>
  </div>
</template>
