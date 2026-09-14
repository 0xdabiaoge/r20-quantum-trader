<script setup lang="ts">
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
const toast = useToast()
const { ask } = useConfirm()
import { ref, computed, onMounted } from 'vue'
import PageHeader from '../../components/admin/PageHeader.vue'
import SettingsSection from '../../components/admin/page-parts/SettingsSection.vue'
import DataTable from '../../components/admin/DataTable.vue'
import { useI18n } from '../../composables/useI18n'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import { fmtDateTime } from '../../utils/format'
import {
  deriveOkxLinked, deriveMxHealthChips, deriveGateExecDirty,
  venueStatus, envTextOf, okxEnvText as okxEnvTextOf, envBadge,
} from './securityLogic' 
import VenueCredentialCard from '../../components/admin/page-parts/VenueCredentialCard.vue'
import { Save, RefreshCw, Layers, Trash2, Zap } from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()
const { t } = useI18n()
const config = ref<any>(null)
const runtime = ref<any>(null)
const loading = ref(true)

type TabKey = 'venues' | 'pool' | 'emergency'
const activeTab = ref<TabKey>('venues')
const positionsLoadedOnce = ref(false)

function switchTab(tab: TabKey) {
  activeTab.value = tab
  if (tab === 'emergency' && !positionsLoadedOnce.value) {
    positionsLoadedOnce.value = true
    loadPositions()
  }
}

// ---- LIVE / DEMO API keys (OKX) ----
const keys = ref({ live_key: '', live_secret: '', live_pass: '', demo_key: '', demo_secret: '', demo_pass: '' })

// ---- capital ----
const newCapital = ref<string>('')
const capitalConfirm = ref<string>('')
const savingCapital = ref(false)

// ---- instruments ----
const instruments = ref<any[]>([])
const instLimits = ref<any>({ minimum: 1, maximum: 20 })
const newInstId = ref('')

// ---- positions & close ----
const snapshot = ref<any>(null)
const snapshotState = ref('')
const manualClose = ref(false)
const closePassword = ref('')
const closeModal = ref<{ show: boolean; pos: any } | null>(null)
const closePhraseInput = ref('')
const closing = ref(false)

// ---- 多所凭证与档位（Binance / Gate 独立保存） ----
const mx = ref<any>(null)
const mxForm = ref({ binance_api_key: '', binance_secret_key: '', gate_api_key: '', gate_secret_key: '' })
const mxTestnet = ref({ binance: false, gate: false })
const preferredVenue = ref('auto')
const routingMode = ref('auto')
const gateExec = ref(false)
const gateExecPhrase = ref('')
const savingMx = ref(false)
const savingOkx = ref(false)
const savingVenue = ref<'binance' | 'gate' | ''>('')
const probingVenue = ref<'binance' | 'gate' | 'okx' | ''>('')

async function loadAll() {
  loading.value = true
  try {
    const [cfg, rt] = await Promise.all([
      api('/api/v1/admin/config'),
      api('/api/v1/admin/okx/runtime?refresh=1').catch(() => null),
    ])
    config.value = cfg
    applyRuntime(rt)
    newCapital.value = String(cfg.editable?.initial_capital ?? '')
    manualClose.value = !!cfg.editable?.manual_close_enabled
    const inst = await api('/api/v1/admin/instruments')
    instruments.value = inst.instruments || []
    instLimits.value = inst.limits || instLimits.value
  } catch (e: any) {
    toast.err(`加载失败：${e.message}`)
  } finally {
    loading.value = false
  }
}

function applyRuntime(rt: any) {
  runtime.value = rt
}

// 批2(2026-09-13)：原 rediagnose() 与 loadAll() 重复（后者已带 refresh=1 拉取运行态），
// 且从未被模板调用（TS6133）→ 已删除，避免两套刷新口径。

async function saveEnvironment() {
  const environment = config.value.editable.okx_environment
  if (environment === 'live') {
    // 批C(2026-09-13)：切 LIVE 是全站最高风险动作（真实资金），原先用 prompt() 收短语
    // ——移动端 prompt 常被弱化，且样式/焦点不可控。改用项目危险操作确认框，
    // 要求逐字输入 LIVE（与其余危险操作同一套门禁语义）。
    const _ok = await ask({
      title: '切换到 LIVE 实盘环境',
      desc: '切换后所有交易将以真实资金执行',
      detail: '请先核对实盘 Key 权限与 IP 白名单已配置正确',
      danger: true,
      confirmPhrase: 'LIVE',
      okText: '切换实盘',
    })
    if (!_ok) {
      toast.warn('未确认 LIVE，环境未切换')
      return
    }
  }
  savingOkx.value = true
  try {
    const body: any = { okx_environment: environment }
    if (keys.value.live_key) body.okx_live_api_key = keys.value.live_key
    if (keys.value.live_secret) body.okx_live_secret_key = keys.value.live_secret
    if (keys.value.live_pass) body.okx_live_passphrase = keys.value.live_pass
    if (keys.value.demo_key) body.okx_demo_api_key = keys.value.demo_key
    if (keys.value.demo_secret) body.okx_demo_secret_key = keys.value.demo_secret
    if (keys.value.demo_pass) body.okx_demo_passphrase = keys.value.demo_pass
    await api('/api/v1/admin/config', { method: 'PUT', body: JSON.stringify(body) })
    keys.value = { live_key: '', live_secret: '', live_pass: '', demo_key: '', demo_secret: '', demo_pass: '' }
    toast.ok(`OKX ${environment.toUpperCase()} 环境与凭证已安全保存`)
    await loadAll()
  } catch (e: any) {
    toast.err(`保存失败：${e.message}`)
  } finally {
    savingOkx.value = false
  }
}

async function saveManualClose() {
  try {
    const d = await api('/api/v1/admin/config', { method: 'PUT', body: JSON.stringify({ manual_close_enabled: manualClose.value }) })
    // 审计①#4(2026-09-13)：PUT 复用 admin_config()，manual_close_enabled 嵌在
    // editable 之下——旧读顶层恒 undefined → 保存后开关弹回 OFF + toast 谎报。
    manualClose.value = !!(d?.editable?.manual_close_enabled ?? d?.manual_close_enabled)
    if (manualClose.value) toast.warn('后台手动平仓已启用'); else toast.ok('后台手动平仓已禁用')
  } catch (e: any) {
    toast.err(e.message)
  }
}

async function saveCapital() {
  if (!auth.isSuperadmin) { toast.err('仅超级管理员可修改初始本金'); return }
  if (capitalConfirm.value.trim().toUpperCase() !== 'UPDATE CAPITAL') { toast.err('确认短语必须精确为：UPDATE CAPITAL'); return }
  savingCapital.value = true
  try {
    const res = await api('/api/v1/admin/account-baseline', { method: 'PUT', body: JSON.stringify({ initial_capital: parseFloat(newCapital.value), confirmation: capitalConfirm.value }) })
    toast.ok(res.effect || `初始本金已调整为 ${res.initial_capital} USDT`)
    capitalConfirm.value = ''
    await loadAll()
  } catch (e: any) {
    toast.err(`更新失败：${e.message}`)
  } finally {
    savingCapital.value = false
  }
}

async function addInstrument() {
  const instId = newInstId.value.trim().toUpperCase()
  if (!/^[A-Z0-9]{2,15}-USDT-SWAP$/.test(instId)) { toast.err('格式示例：XRP-USDT-SWAP（仅 USDT 永续）'); return }
  try {
    const res = await api('/api/v1/admin/instruments', { method: 'POST', body: JSON.stringify({ inst_id: instId }) })
    toast.ok(res.message || `${instId} 已成功加入交易池`)
    newInstId.value = ''
    await loadAll()
  } catch (e: any) {
    toast.err(`添加失败：${e.message}`)
  }
}

async function removeInstrument(item: any) {
  if (item.protected) { toast.warn('系统保底标的不可删除'); return }
  // 审计 P1-5：后端已按实时持仓/追踪记录硬拒（删除会让该标的失去移动止损/时间止损/AI 平仓接管），
  // 前端不再承诺"既有持仓不受影响"，而是在入口就把真实原因说清楚。
  if (item.held_live || item.has_tracker) {
    toast.warn(`该标的仍有持仓（${(item.held_venues || []).join('/') || '追踪记录'}），为防止失去风控接管，禁止移除`)
    return
  }
  if (item.holdings_unknown) { toast.warn('当前无法确认实时持仓，删除已暂停；请稍后重试'); return }
  // 批C(2026-09-13)·危险操作确认收口：后端本就要求逐字短语 `REMOVE <instId>`，
  // 但前端把短语写死在请求体、只用原生 confirm() 小条挡一下——移动端随手一按就
  // 能把实盘标的移出交易池（同页平仓却要密码+短语双确认，强度不一致）。现将同一
  // 短语要求显式抬到 UI：必须逐字输入才可确认，前后端确认语义就此一致。
  const _ok = await ask({
    title: '从交易池移除标的',
    desc: `${item.instId} 将不再参与选币与开仓（仅限当前无持仓、无追踪记录的标的）`,
    danger: true,
    confirmPhrase: `REMOVE ${item.instId}`,
    okText: '移除',
  })
  if (!_ok) return
  try {
    const res = await api(`/api/v1/admin/instruments/${encodeURIComponent(item.instId)}`, {
      method: 'DELETE',
      body: JSON.stringify({ confirmation: `REMOVE ${item.instId}` })
    })
    toast.ok(res.message || `${item.instId} 已从交易池移除`)
    await loadAll()
  } catch (e: any) {
    toast.err(`删除失败：${e.message}`)
  }
}

async function loadPositions() {
  snapshotState.value = t('admin.security.loadingPositions')
  try {
    const d = await api('/api/v1/admin/okx/account-snapshot')
    snapshot.value = d
    snapshotState.value = ''
  } catch (e: any) {
    snapshotState.value = e.message
    snapshot.value = null
  }
}

function openClose(pos: any) {
  if (!manualClose.value) { toast.err('请先在「应急平仓」页启用手动平仓开关'); return }
  closePhraseInput.value = ''
  closeModal.value = { show: true, pos }
}

async function confirmClose() {
  const pos = closeModal.value?.pos
  if (!pos) return
  if (!closePassword.value) { toast.err('请输入当前管理员密码'); return }
  if (!pos.close_token || !pos.close_confirmation) { toast.err('平仓令牌缺失，请刷新当前持仓'); return }
  if (closePhraseInput.value.trim().toUpperCase() !== pos.close_confirmation) {
    toast.err(`确认短语必须精确为：${pos.close_confirmation}`)
    return
  }
  closing.value = true
  try {
    const d = await api('/api/v1/admin/positions/close', {
      method: 'POST',
      body: JSON.stringify({ close_token: pos.close_token, admin_password: closePassword.value, confirmation: closePhraseInput.value.trim().toUpperCase(), venue: pos.venue || 'okx' }),
    })
    toast.ok(`已确认平仓：${d.instId} ${d.closed_size}`)
    closeModal.value = null
    closePassword.value = ''
    await loadPositions()
  } catch (e: any) {
    toast.err(`平仓失败：${e.message}`)
    // 一次性令牌可能已被消费/过期：自动刷新快照，并把弹窗指向新令牌的同仓位行，允许直接重试
    await loadPositions()
    const fresh = (snapshot.value?.positions || []).find((x: any) => x.instId === pos.instId && (x.posSide || 'net') === (pos.posSide || 'net') && (x.venue || 'okx') === (pos.venue || 'okx'))
    if (fresh) closeModal.value = { show: true, pos: fresh }
    else { closeModal.value = null; closePassword.value = '' }
  } finally {
    closing.value = false
  }
}

async function loadMx() {
  try {
    mx.value = await api('/api/v1/admin/multi-exchange')
    if (mx.value?.venues) {
      mxTestnet.value.binance = !!mx.value.venues.binance?.testnet
      mxTestnet.value.gate = !!mx.value.venues.gate?.testnet
      gateExec.value = !!mx.value.venues.gate?.execution_open
    }
    if (mx.value?.preferred_venue) {
      preferredVenue.value = mx.value.preferred_venue
    }
    if (mx.value?.routing_mode) {
      routingMode.value = mx.value.routing_mode
    }
  } catch { mx.value = null }
}

/** 单所凭证连接诊断：支持未保存凭证的预检与公共连通性探测。 */
async function probeVenue(venue: 'binance' | 'gate' | 'okx') {
  probingVenue.value = venue
  try {
    const isDemo = venue === 'okx'
      ? (config.value?.editable?.okx_environment === 'demo')
      : !!mxTestnet.value[venue]
    const env = isDemo ? 'demo' : 'live'

    const payload: Record<string, any> = {
      venue,
      environment: env,
    }

    if (venue === 'binance') {
      const k = mxForm.value.binance_api_key.trim()
      const s = mxForm.value.binance_secret_key.trim()
      if (k) payload.api_key = k
      if (s) payload.secret_key = s
    } else if (venue === 'gate') {
      const k = mxForm.value.gate_api_key.trim()
      const s = mxForm.value.gate_secret_key.trim()
      if (k) payload.api_key = k
      if (s) payload.secret_key = s
    } else if (venue === 'okx') {
      if (isDemo) {
        if (keys.value.demo_key.trim()) payload.api_key = keys.value.demo_key.trim()
        if (keys.value.demo_secret.trim()) payload.secret_key = keys.value.demo_secret.trim()
        if (keys.value.demo_pass.trim()) payload.passphrase = keys.value.demo_pass.trim()
      } else {
        if (keys.value.live_key.trim()) payload.api_key = keys.value.live_key.trim()
        if (keys.value.live_secret.trim()) payload.secret_key = keys.value.live_secret.trim()
        if (keys.value.live_pass.trim()) payload.passphrase = keys.value.live_pass.trim()
      }
    }

    const res: any = await api('/api/v1/admin/multi-exchange/test-connection', {
      method: 'POST',
      body: JSON.stringify(payload),
    })

    if (res?.ok) {
      toast.ok(res.message || `${venue.toUpperCase()} 连接诊断成功`)
    } else {
      toast.err(res?.message || `${venue.toUpperCase()} 连接诊断失败`)
    }
    await loadMx()
  } catch (e: any) {
    toast.err(`检测失败：${e.message}`)
  } finally {
    probingVenue.value = ''
  }
}

/** 保存撮合路由首选与模式（只写路由两键，不牵连任何凭证字段）。 */
async function saveRouting() {
  savingMx.value = true
  try {
    await api('/api/v1/admin/multi-exchange', {
      method: 'PUT',
      body: JSON.stringify({ preferred_venue: preferredVenue.value, routing_mode: routingMode.value }),
    })
    toast.ok(`撮合路由已保存：${preferredVenue.value.toUpperCase()} · ${routingMode.value.toUpperCase()}`)
    await loadMx()
  } catch (e: any) {
    toast.err(`保存失败：${e.message}`)
  } finally {
    savingMx.value = false
  }
}

/** 逐所保存凭证与档位：只提交本所键位，留空即不改；Gate 另承载执行总闸。 */
async function saveVenue(venue: 'binance' | 'gate') {
  savingVenue.value = venue
  try {
    const body: any = {}
    if (venue === 'binance') {
      body.binance_testnet = mxTestnet.value.binance
      const k = mxForm.value.binance_api_key.trim()
      const s = mxForm.value.binance_secret_key.trim()
      if (k) body.binance_api_key = k
      if (s) body.binance_secret_key = s
    } else {
      body.gate_testnet = mxTestnet.value.gate
      const k = mxForm.value.gate_api_key.trim()
      const s = mxForm.value.gate_secret_key.trim()
      if (k) body.gate_api_key = k
      if (s) body.gate_secret_key = s
      if (gateExecDirty.value) {
        body.gate_execution = gateExec.value
        body.confirmation = gateExecPhrase.value.trim()
      }
    }
    await api('/api/v1/admin/multi-exchange', { method: 'PUT', body: JSON.stringify(body) })
    toast.ok(`${venue === 'binance' ? 'Binance' : 'Gate'} 凭证与档位已保存`)
    if (venue === 'binance') { mxForm.value.binance_api_key = ''; mxForm.value.binance_secret_key = '' }
    else { mxForm.value.gate_api_key = ''; mxForm.value.gate_secret_key = ''; gateExecPhrase.value = '' }
    await loadMx()
  } catch (e: any) {
    toast.err(`保存失败：${e.message}`)
  } finally {
    savingVenue.value = ''
  }
}

// ---- 总览派生（纯计算，零请求） ----
// 显示派生逻辑已抽至 ./securityLogic.ts（阶段 4·B3 第三十四刀）——
// 纯函数、可脱离组件单测；此处只保留响应式包装。
const okxLinked = computed(() => deriveOkxLinked(runtime.value))
const mxHealthChips = computed(() => deriveMxHealthChips(mx.value))
const gateExecDirty = computed(() => deriveGateExecDirty(gateExec.value, mx.value))

const binanceStatus = computed(() => venueStatus('binance', mx.value, t))
const gateStatus = computed(() => venueStatus('gate', mx.value, t))

const okxEnvText = computed(() => okxEnvTextOf(config.value?.editable?.okx_environment, t))
const binanceEnvText = computed(() => envTextOf('binance', t('admin.security.envDemoBinance'), mx.value, mxTestnet.value, t))
const gateEnvText = computed(() => envTextOf('gate', t('admin.security.envDemoGate'), mx.value, mxTestnet.value, t))

const TABS = computed<Array<{ key: TabKey; label: string }>>(() => [
  { key: 'venues', label: t('admin.security.tabVenues') },
  { key: 'pool', label: t('admin.security.tabPool') },
  { key: 'emergency', label: t('admin.security.tabEmergency') },
])


onMounted(() => { loadAll(); loadMx() })
</script>

<template>
  <div class="space-y-4 text-xs">
    <PageHeader :title="t('nav.admin.security')" :description="t('admin.security.desc')">
      <template #actions>
        <span class="chip flex items-center gap-1.5">
          <span>{{ t('admin.security.chipRouting') }}</span>
          <b class="num" style="color: var(--accent);">{{ routingMode.toUpperCase() }}</b>
          <span class="text-[10px] opacity-70">·</span>
          <span>{{ t('admin.security.chipPreferred') }}</span>
          <b class="num" style="color: var(--accent);">{{ preferredVenue.toUpperCase() }}</b>
          <span class="text-[10px] opacity-70">·</span>
          <span>{{ t('admin.security.chipEnv') }}</span>
          <b class="num" :style="{ color: runtime?.environment === 'live' ? 'var(--down)' : 'var(--up)' }">{{ envBadge(runtime?.environment) }}</b>
        </span>
      </template>
    </PageHeader>

    <div v-if="loading" class="py-12 text-center" style="color: var(--ink-2);">{{ t('admin.security.syncing') }}</div>

    <template v-else-if="config">
      <!-- 状态总览条 -->
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div class="card card-pad flex flex-col justify-between" style="background-color: var(--surface-1);">
          <div class="flex items-center justify-between text-[11px]" style="color: var(--ink-3);">
            <span>{{ t('admin.security.okxApi') }}</span>
            <span class="dot" :class="okxLinked ? 'dot-up' : 'dot-down'" />
          </div>
          <div class="mt-1 flex items-baseline justify-between">
            <b class="text-xs font-bold" :style="{ color: okxLinked ? 'var(--up)' : 'var(--down)' }">
              {{ okxLinked ? t('admin.security.okxLinked') : t('admin.security.okxUnconfigured') }}
            </b>
            <span class="num text-[10px]" style="color: var(--ink-3);">{{ envBadge(runtime?.environment) }}</span>
          </div>
        </div>

        <div class="card card-pad flex flex-col justify-between" style="background-color: var(--surface-1);">
          <div class="flex items-center justify-between text-[11px]" style="color: var(--ink-3);">
            <span>Binance · USDT-M</span>
            <span class="dot" :class="mx?.venues?.binance?.has_api_key ? 'dot-up' : 'dot-warn'" />
          </div>
          <div class="mt-1 flex items-baseline justify-between">
            <b class="text-xs font-bold" :style="{ color: mx?.venues?.binance?.has_api_key ? 'var(--up)' : 'var(--warn)' }">
              {{ mx?.venues?.binance?.has_api_key ? t('admin.security.binanceKeyed') : t('admin.security.publicMarket') }}
            </b>
            <span class="num text-[10px]" style="color: var(--ink-3);">{{ mxTestnet.binance ? 'DEMO' : 'LIVE' }}</span>
          </div>
        </div>

        <div class="card card-pad flex flex-col justify-between" style="background-color: var(--surface-1);">
          <div class="flex items-center justify-between text-[11px]" style="color: var(--ink-3);">
            <span>{{ t('admin.security.gatePerp') }}</span>
            <span class="dot" :class="mx?.venues?.gate?.has_api_key ? 'dot-up' : 'dot-warn'" />
          </div>
          <div class="mt-1 flex items-baseline justify-between">
            <b class="text-xs font-bold" :style="{ color: mx?.venues?.gate?.has_api_key ? 'var(--up)' : 'var(--warn)' }">
              {{ mx?.venues?.gate?.has_api_key ? (mx?.venues?.gate?.execution_open ? t('admin.security.gateOpenLive') : t('admin.security.gateClosed')) : t('admin.security.publicMarket') }}
            </b>
            <span class="num text-[10px]" style="color: var(--ink-3);">{{ mxTestnet.gate ? 'TESTNET' : 'LIVE' }}</span>
          </div>
        </div>

        <div class="card card-pad flex flex-col justify-between" style="background-color: var(--surface-1);">
          <div class="flex items-center justify-between text-[11px]" style="color: var(--ink-3);">
            <span>{{ t('admin.security.activePool') }}</span>
            <Layers class="h-3 w-3" style="color: var(--accent);" />
          </div>
          <div class="mt-1 flex items-baseline justify-between">
            <b class="num text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.poolCount', undefined, { count: instruments.length, max: instLimits.maximum }) }}</b>
            <span class="text-[10px] font-medium" style="color: var(--ink-2);">{{ t('admin.security.usdtPerp') }}</span>
          </div>
        </div>
      </div>

      <!-- 选项卡切换 -->
      <div class="flex items-center gap-2 border-b pb-2 pt-1" style="border-color: var(--line-1);">
        <button
          v-for="tab in TABS" :key="tab.key"
          class="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer"
          :style="activeTab === tab.key ? { backgroundColor: 'var(--ink-1)', color: 'var(--surface-2)' } : { color: 'var(--ink-2)' }"
          @click="switchTab(tab.key)"
        >{{ tab.label }}</button>
      </div>

      <!-- ============ 页签 1：交易所与路由 ============ -->
      <div v-if="activeTab === 'venues'" class="space-y-4">
        <!-- 路由主策略 -->
        <SettingsSection :title="t('admin.security.routingTitle')" :description="t('admin.security.routingDesc')">
          <template #actions>
            <button class="btn btn-primary" :disabled="savingMx" @click="saveRouting"><Save class="h-3.5 w-3.5" /> {{ savingMx ? t('admin.security.saving') : t('admin.security.saveRouting') }}</button>
          </template>
          <div class="space-y-3 rounded-lg border p-3.5" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[10px] font-semibold" style="color: var(--ink-2);">{{ t('admin.security.routingModeLabel') }}</div>
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="routingMode === 'balanced' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="routingMode" type="radio" value="balanced" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.modeA') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.modeADesc') }}</div>
                </div>
              </label>
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="routingMode === 'auto' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="routingMode" type="radio" value="auto" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.modeB') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.modeBDesc') }}</div>
                </div>
              </label>
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="routingMode === 'split' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="routingMode" type="radio" value="split" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.modeC') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.modeCDesc') }}</div>
                </div>
              </label>
            </div>
            <div class="text-[10px] font-semibold pt-1" style="color: var(--ink-2);">{{ t('admin.security.manualLabel') }}</div>
            <div class="grid grid-cols-1 sm:grid-cols-4 gap-2">
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="preferredVenue === 'auto' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="preferredVenue" type="radio" value="auto" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.noManual') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.noManualDesc') }}</div>
                </div>
              </label>
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="preferredVenue === 'okx' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="preferredVenue" type="radio" value="okx" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.lockOkx') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.lockOkxDesc') }}</div>
                </div>
              </label>
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="preferredVenue === 'binance' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="preferredVenue" type="radio" value="binance" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.lockBinance') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.lockBinanceDesc') }}</div>
                </div>
              </label>
              <label class="flex items-center gap-2 p-2.5 rounded-md border cursor-pointer transition-colors" :style="preferredVenue === 'gate' ? { borderColor: 'var(--accent)', backgroundColor: 'var(--surface-2)' } : { borderColor: 'var(--line-1)' }">
                <input v-model="preferredVenue" type="radio" value="gate" class="accent-[var(--accent)]" />
                <div>
                  <div class="text-xs font-bold" style="color: var(--ink-1);">{{ t('admin.security.lockGate') }}</div>
                  <div class="text-[10px]" style="color: var(--ink-3);">{{ t('admin.security.lockGateDesc') }}</div>
                </div>
              </label>
            </div>
            <p class="text-[11px] leading-relaxed" style="color: var(--ink-3);">
              {{ t('admin.security.currentEffective') }}<b class="num" style="color: var(--accent);">{{ routingMode.toUpperCase() }}</b>
              <template v-if="preferredVenue !== 'auto'"> {{ t('admin.security.manualTag') }} <b class="num" style="color: var(--accent);">{{ preferredVenue.toUpperCase() }}</b></template>{{ t('admin.security.period') }}
              {{ t('admin.security.unconfiguredNote') }}
            </p>
          </div>
        </SettingsSection>

        <!-- 三所凭证卡 -->
        <SettingsSection :title="t('admin.security.credsTitle')" :description="t('admin.security.credsDesc')">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <!-- 1. OKX -->
            <VenueCredentialCard
              :name="t('admin.security.okxName')" :api-label="t('admin.security.okxApiLabel')"
              :status-text="okxLinked ? t('admin.security.okxReady') : t('admin.security.okxNotReady')" :tone="okxLinked ? 'up' : 'down'"
              :env-text="okxEnvText" :env-label="t('admin.security.fundEnv')"
            >
              <template #env>
                <label class="block text-[10px] mb-1" style="color: var(--ink-2);">{{ t('admin.security.envTier') }}</label>
                <select v-model="config.editable.okx_environment" class="input w-full text-xs">
                  <option value="demo">{{ t('admin.security.optDemo') }}</option>
                  <option value="live">{{ t('admin.security.optLive') }}</option>
                </select>
              </template>
              <div class="space-y-1.5 pt-1">
                <div class="text-[10px] font-semibold" style="color: var(--ink-2);">{{ t('admin.security.liveTrio') }}</div>
                <input v-model="keys.live_key" type="password" :placeholder="t('admin.security.apiKeyKeep')" class="input w-full text-xs" />
                <input v-model="keys.live_secret" type="password" placeholder="Secret Key" class="input w-full text-xs" />
                <input v-model="keys.live_pass" type="password" placeholder="Passphrase" class="input w-full text-xs" />
              </div>
              <div class="space-y-1.5 pt-1">
                <div class="text-[10px] font-semibold" style="color: var(--ink-2);">{{ t('admin.security.demoTrio') }}</div>
                <input v-model="keys.demo_key" type="password" :placeholder="t('admin.security.apiKeyKeep')" class="input w-full text-xs" />
                <input v-model="keys.demo_secret" type="password" placeholder="Secret Key" class="input w-full text-xs" />
                <input v-model="keys.demo_pass" type="password" placeholder="Passphrase" class="input w-full text-xs" />
              </div>
              <template #extra>
                <p class="text-[10px] leading-relaxed pt-1" style="color: var(--ink-3);">
                  {{ t('admin.security.liveConfirmNote') }}
                </p>
              </template>
              <template #probe>
                <button class="btn btn-quiet btn-sm" :disabled="probingVenue === 'okx'" @click="probeVenue('okx')"><RefreshCw class="h-3 w-3" :class="probingVenue === 'okx' ? 'animate-spin' : ''" /> {{ probingVenue === 'okx' ? t('admin.security.probing') : t('admin.security.detect') }}</button>
              </template>
              <template #save>
                <button class="btn btn-primary btn-sm" :disabled="savingOkx" @click="saveEnvironment"><Save class="h-3 w-3" /> {{ savingOkx ? t('admin.security.saving') : t('admin.security.saveOkx') }}</button>
              </template>
            </VenueCredentialCard>

            <!-- 2. Binance -->
            <VenueCredentialCard
              :name="t('admin.security.binanceName')" :api-label="t('admin.security.binanceApiLabel')"
              :status-text="binanceStatus.text" :tone="binanceStatus.tone"
              :env-text="binanceEnvText" :env-label="t('admin.security.fundEnv')"
            >
              <template #env>
                <label class="block text-[10px] mb-1" style="color: var(--ink-2);">{{ t('admin.security.endpointTier') }}</label>
                <label class="flex items-center gap-1.5 text-[11px] cursor-pointer" style="color: var(--ink-2);">
                  <input v-model="mxTestnet.binance" type="checkbox" class="accent-[var(--accent)]" />
                  {{ t('admin.security.binanceDemoDomain') }}
                </label>
              </template>
              <div class="space-y-1.5 pt-1">
                <div class="text-[10px] font-semibold" style="color: var(--ink-2);">{{ t('admin.security.binanceCredLabel') }}</div>
                <input v-model="mxForm.binance_api_key" type="text" :placeholder="t('admin.security.apiKeyKeep')" class="input w-full text-xs" />
                <input v-model="mxForm.binance_secret_key" type="password" placeholder="API Secret" class="input w-full text-xs" />
              </div>
              <template #extra>
                <p class="text-[10px] leading-relaxed pt-1" style="color: var(--ink-3);">
                  {{ t('admin.security.binanceExtra') }}
                </p>
              </template>
              <template #probe>
                <button class="btn btn-quiet btn-sm" :disabled="probingVenue !== '' && probingVenue !== 'binance'" @click="probeVenue('binance')"><RefreshCw class="h-3 w-3" /> {{ t('admin.security.detect') }}</button>
              </template>
              <template #save>
                <button class="btn btn-primary btn-sm" :disabled="savingVenue !== ''" @click="saveVenue('binance')"><Save class="h-3 w-3" /> {{ savingVenue === 'binance' ? t('admin.security.saving') : t('admin.security.saveBinance') }}</button>
              </template>
            </VenueCredentialCard>

            <!-- 3. Gate -->
            <VenueCredentialCard
              :name="t('admin.security.gateName')" :api-label="t('admin.security.gateApiLabel')"
              :status-text="gateStatus.text" :tone="gateStatus.tone"
              :env-text="gateEnvText" :env-label="t('admin.security.fundEnv')"
            >
              <template #env>
                <label class="block text-[10px] mb-1" style="color: var(--ink-2);">{{ t('admin.security.endpointTier') }}</label>
                <label class="flex items-center gap-1.5 text-[11px] cursor-pointer" style="color: var(--ink-2);">
                  <input v-model="mxTestnet.gate" type="checkbox" class="accent-[var(--accent)]" />
                  {{ t('admin.security.gateSandboxDomain') }}
                </label>
              </template>
              <div class="space-y-1.5 pt-1">
                <div class="text-[10px] font-semibold" style="color: var(--ink-2);">{{ t('admin.security.gateCredLabel') }}</div>
                <input v-model="mxForm.gate_api_key" type="text" :placeholder="t('admin.security.apiKeyKeep')" class="input w-full text-xs" />
                <input v-model="mxForm.gate_secret_key" type="password" placeholder="API Secret" class="input w-full text-xs" />
              </div>
              <template #extra>
                <div class="pt-1">
                  <label class="flex items-center gap-1.5 text-[11px] cursor-pointer font-bold" :style="{ color: gateExec ? 'var(--down)' : 'var(--ink-2)' }">
                    <input v-model="gateExec" type="checkbox" class="accent-[var(--accent)]" />
                    {{ t('admin.security.gateMaster') }} {{ mx?.venues?.gate?.execution_open ? t('admin.security.gateMasterOpen') : t('admin.security.gateMasterClosed') }}
                  </label>
                  <input v-if="gateExecDirty && gateExec" v-model="gateExecPhrase" :placeholder="t('admin.security.gatePhrasePlaceholder')" class="input w-full text-xs mt-1.5" />
                </div>
                <p class="text-[10px] leading-relaxed pt-1" style="color: var(--ink-3);">
                  {{ t('admin.security.gateExtra') }}
                </p>
              </template>
              <template #probe>
                <button class="btn btn-quiet btn-sm" :disabled="probingVenue !== '' && probingVenue !== 'gate'" @click="probeVenue('gate')"><RefreshCw class="h-3 w-3" /> {{ t('admin.security.detect') }}</button>
              </template>
              <template #save>
                <button class="btn btn-primary btn-sm" :disabled="savingVenue !== ''" @click="saveVenue('gate')"><Save class="h-3 w-3" /> {{ savingVenue === 'gate' ? t('admin.security.saving') : t('admin.security.saveGate') }}</button>
              </template>
            </VenueCredentialCard>
          </div>
        </SettingsSection>

        <!-- 跨所行情健康 -->
        <SettingsSection :title="t('admin.security.healthTitle')" :description="t('admin.security.healthDesc')">
          <template #actions>
            <button class="btn btn-quiet btn-sm" @click="loadMx"><RefreshCw class="h-3 w-3" /> {{ t('admin.security.recheck') }}</button>
          </template>
          <div v-if="mxHealthChips" class="flex flex-wrap gap-2 text-[11px]">
            <span v-for="h in mxHealthChips" :key="h.name" class="px-2 py-1 rounded border font-bold num" :style="h.ok === h.total ? { color: 'var(--up)', borderColor: 'var(--up-line)', backgroundColor: 'var(--up-bg)' } : { color: 'var(--warn)', borderColor: 'var(--warn-line)', backgroundColor: 'var(--warn-bg)' }">
              {{ h.name }} {{ h.ok }}/{{ h.total }} {{ t('admin.security.coinsUnit') }}{{ h.avg_ms ? ' · ' + h.avg_ms + 'ms' : '' }}{{ h.testnet ? ' · ' + t('admin.security.sandboxTag') : '' }}
            </span>
          </div>
          <div v-else class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.security.noHealthData') }}</div>
        </SettingsSection>
      </div>

      <!-- ============ 页签 2：标的池与初始本金 ============ -->
      <div v-if="activeTab === 'pool'" class="space-y-4">
        <SettingsSection :title="t('admin.security.capitalTitle')" :description="t('admin.security.capitalDesc')">
          <template #actions>
            <button
              class="btn btn-primary"
              :disabled="savingCapital || !auth.isSuperadmin"
              @click="saveCapital"
            ><Save class="h-3.5 w-3.5" /> {{ savingCapital ? t('admin.security.capitalSaving') : t('admin.security.capitalSave') }}</button>
          </template>
          <div class="grid gap-3 md:grid-cols-2">
            <label class="text-xs space-y-1">
              <span style="color: var(--ink-2);">{{ t('admin.security.capitalAmount') }}</span>
              <input v-model="newCapital" class="input w-full num" inputmode="decimal" />
            </label>
            <label class="text-xs space-y-1">
              <span style="color: var(--ink-2);">{{ t('admin.security.capitalConfirmLabel') }}</span>
              <input v-model="capitalConfirm" class="input w-full num" placeholder="UPDATE CAPITAL" />
            </label>
          </div>
          <p class="pt-3 text-[11px]" style="color: var(--ink-3);">{{ t('admin.security.capitalFooter') }}</p>
        </SettingsSection>

        <SettingsSection :title="t('admin.security.poolTitle')" :description="t('admin.security.poolDesc')">
          <template #actions>
            <input v-model="newInstId" :placeholder="t('admin.security.instPlaceholder')" class="input w-44" @keyup.enter="addInstrument" />
            <button class="btn btn-primary" @click="addInstrument"><Layers class="h-3.5 w-3.5" /> {{ t('admin.security.addInstrument') }}</button>
          </template>
          <DataTable
            flat
            v-if="instruments.length"
            class="overflow-x-auto -mx-4 px-4"
            :rows="instruments || []"
            :row-key="(item: any) => item.instId"
            :empty-text="t('common.noRecords')"
          >
            <template #head>
              <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); color: var(--ink-2);">
                                <th class="py-2 pl-0 pr-4">{{ t('admin.security.colInstId') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colName') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colType') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colRisk') }}</th>
                                <th class="py-2 px-4 text-right">{{ t('admin.security.colAction') }}</th>
                              </tr>
            </template>
            <template #row="{ row: item }">
              <td class="py-2 pl-0 pr-4 font-bold num" style="color: var(--ink-1);">{{ item.instId }}</td>
              <td class="py-2 px-3" style="color: var(--ink-2);">{{ item.name }}</td>
              <td class="py-2 px-3 num" style="color: var(--ink-3);">{{ item.ctType || 'SWAP' }}</td>
              <td class="py-2 px-3">
                <span v-if="item.protected" class="px-1.5 py-0.5 rounded-[3px] text-[11px] font-bold border" style="background-color: var(--warn-bg); border-color: var(--warn-line); color: var(--warn);">{{ t('admin.security.protectedBadge') }}</span>
                <span v-else-if="item.held_live" class="px-1.5 py-0.5 rounded-[3px] text-[11px] font-bold border" style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);">{{ t('admin.security.holdingLiveBadge', undefined, { venues: (item.held_venues || []).join('/') || '—' }) }}</span>
                <span v-else-if="item.has_tracker" class="px-1.5 py-0.5 rounded-[3px] text-[11px] font-bold border" style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);">{{ t('admin.security.holdingBadge') }}</span>
                <span v-else-if="item.holdings_unknown" class="px-1.5 py-0.5 rounded-[3px] text-[11px] font-bold border" style="background-color: var(--surface-3); border-color: var(--warn-line); color: var(--warn);" :title="String(item.holdings_unknown)">{{ t('admin.security.holdingUnknownBadge') }}</span>
                <span v-else class="text-[11px] px-1.5 py-0.5 rounded-[3px] border" style="background-color: var(--surface-3); border-color: var(--line-1); color: var(--ink-3);">{{ t('admin.security.removableBadge') }}</span>
              </td>
              <td class="py-2 px-4 text-right">
                <button
                  :disabled="item.protected || item.has_tracker || item.held_live || item.holdings_unknown"
                  class="p-1 rounded cursor-pointer transition-opacity hover:opacity-80 disabled:opacity-20"
                  style="color: var(--down);"
                  :title="item.held_live ? t('admin.security.removeBlockedHoldings', undefined, { venues: (item.held_venues || []).join('/') || '—' }) : item.holdings_unknown ? t('admin.security.removeBlockedUnknown') : t('admin.security.removeTitle')"
                  @click="removeInstrument(item)"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </td>
            </template>
          </DataTable>
            <div v-else class="py-8 text-center text-xs" style="color: var(--ink-3);">{{ t('admin.security.poolEmpty') }}</div>
          <p class="pt-3 text-[11px]" style="color: var(--ink-3);">{{ t('admin.security.poolFooter', undefined, { max: instLimits.maximum }) }}</p>
        </SettingsSection>
      </div>

      <!-- ============ 页签 3：应急风控与持仓 ============ -->
      <div v-if="activeTab === 'emergency'" class="space-y-4">
        <SettingsSection :title="t('admin.security.manualTitle')" :description="t('admin.security.manualDesc')">
          <template #actions>
            <button class="btn btn-quiet" @click="saveManualClose"><Save class="h-3.5 w-3.5" /> {{ t('admin.security.saveSwitch') }}</button>
          </template>
          <label class="flex items-center gap-2 cursor-pointer w-fit">
            <input v-model="manualClose" type="checkbox" class="accent-[var(--accent)]" />
            <span class="text-xs" :style="{ color: manualClose ? 'var(--warn)' : 'var(--ink-2)', fontWeight: manualClose ? 700 : 400 }">
              {{ manualClose ? t('admin.security.manualOn') : t('admin.security.manualOff') }}
            </span>
          </label>
        </SettingsSection>

        <SettingsSection :title="t('admin.security.snapshotTitle')" :description="t('admin.security.snapshotDesc')">
          <template #actions>
            <button class="btn btn-quiet" @click="loadPositions"><Zap class="h-3.5 w-3.5" /> {{ t('admin.security.refreshPositions') }}</button>
          </template>
          <div v-if="snapshotState" class="text-[11px] pb-2" style="color: var(--warn);">{{ snapshotState }}</div>
          <div v-if="snapshot" class="text-[11px] pb-2" style="color: var(--ink-2);">
            {{ t('admin.security.envWord') }} <b :style="{ color: snapshot.environment === 'live' ? 'var(--down)' : 'var(--up)' }">{{ envBadge(snapshot.environment) }}</b>
            · {{ t('admin.security.positionsWord') }} {{ snapshot.positions?.length ?? 0 }} · {{ t('admin.security.ordersWord') }} {{ snapshot.orders?.length ?? 0 }} · {{ fmtDateTime(snapshot.captured_at_ms) }}
          </div>
          <DataTable
            flat
            v-if="snapshot?.positions?.length"
            class="overflow-x-auto -mx-4 px-4"
            :rows="snapshot.positions || []"
            :row-key="(p: any) => p.instId + p.posSide"
            :empty-text="t('common.noRecords')"
          >
            <template #head>
              <tr class="border-b text-[11px] uppercase tracking-wider font-bold" style="border-color: var(--line-1); color: var(--ink-2);">
                                <th class="py-2 pl-0 pr-4">{{ t('admin.security.colPosition') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colContracts') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colMode') }}</th>
                                <th class="py-2 px-3">{{ t('admin.security.colUpl') }}</th>
                                <th class="py-2 px-4 text-right">{{ t('admin.security.colAction') }}</th>
                              </tr>
            </template>
            <template #row="{ row: p }">
              <td class="py-2 pl-0 pr-4">
                <b class="num" style="color: var(--ink-1);">{{ p.instId }}</b>
                <span v-if="p.venue" class="ml-1 px-1 py-0.5 rounded text-[10px] font-bold uppercase border" :style="p.venue === 'binance' ? { color: '#f3ba2f', borderColor: '#f3ba2f33' } : p.venue === 'gate' ? { color: '#00be98', borderColor: '#00be9833' } : { color: '#3880ff', borderColor: '#3880ff33' }">
                  {{ p.venue }}
                </span>
                <span class="ml-1.5 px-1.5 py-0.5 rounded text-[11px] font-bold border" :style="p.posSide === 'long' ? { backgroundColor: 'var(--up-bg)', borderColor: 'var(--up-line)', color: 'var(--up)' } : { backgroundColor: 'var(--down-bg)', borderColor: 'var(--down-line)', color: 'var(--down)' }">
                  {{ (p.posSide || 'net').toUpperCase() }}
                </span>
              </td>
              <td class="py-2 px-3 num" style="color: var(--ink-2);">{{ p.pos || '0' }}</td>
              <td class="py-2 px-3 text-[11px]" style="color: var(--ink-3);">{{ p.mgnMode || '--' }}</td>
              <td class="py-2 px-3 font-bold num" :style="{ color: Number(p.upl || 0) >= 0 ? 'var(--up)' : 'var(--down)' }">{{ Number(p.upl || 0).toFixed(4) }}</td>
              <td class="py-2 px-4 text-right">
                <button class="px-2.5 py-1 rounded-md text-[11px] font-bold border cursor-pointer transition-all" style="background-color: var(--down-bg); border-color: var(--down-line); color: var(--down);" @click="openClose(p)">{{ t('admin.security.quickClose') }}</button>
              </td>
            </template>
          </DataTable>
            <div v-else-if="snapshot" class="py-8 text-center text-xs" style="color: var(--up);">{{ t('admin.security.noPositions') }}</div>
            <div v-else-if="!snapshotState" class="py-8 text-center text-xs" style="color: var(--ink-3);">{{ t('admin.security.clickRefreshHint') }}</div>
        </SettingsSection>
      </div>
    </template>

    <!-- 平仓双确认弹窗 -->
    <div v-if="closeModal?.show" class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-xs flex items-center justify-center p-4" @click.self="closeModal = null">
      <div class="rounded-xl border p-5 sm:p-6 w-full max-w-[460px] max-h-[88dvh] overflow-y-auto shadow-2xl" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <h3 class="text-sm font-bold mb-2" style="color: var(--down);">{{ t('admin.security.closeModalTitle') }}</h3>
        <p class="text-[11px] leading-relaxed mb-3" style="color: var(--ink-2);">
          {{ t('admin.security.closePrefix') }} <b :style="{ color: snapshot?.environment === 'live' ? 'var(--down)' : 'var(--up)' }">{{ envBadge(snapshot?.environment) }}</b> {{ t('admin.security.closeMiddle') }}
          <b style="color: var(--ink-1);">{{ closeModal.pos.instId }} {{ (closeModal.pos.posSide || 'net').toUpperCase() }} {{ Math.abs(Number(closeModal.pos.pos || 0)) }}</b>{{ t('admin.security.period') }}
          {{ t('admin.security.closeSuffix') }}
        </p>
        <label class="block text-[11px] mb-1" style="color: var(--ink-2);">{{ t('admin.security.adminPasswordLabel') }}</label>
        <input v-model="closePassword" type="password" class="input w-full mb-3" />
        <label class="block text-[11px] mb-1" style="color: var(--ink-2);">{{ t('admin.security.confirmPhraseLabel') }}{{ closeModal.pos.close_confirmation }}</label>
        <input v-model="closePhraseInput" :placeholder="closeModal.pos.close_confirmation" class="input w-full mb-4" />
        <div class="flex justify-end gap-2">
          <button class="btn btn-quiet" @click="closeModal = null">{{ t('admin.security.cancel') }}</button>
          <button class="px-3 py-2 rounded-lg text-xs font-bold cursor-pointer disabled:opacity-50 transition-all" style="background-color: var(--down-bg); border: 1px solid var(--down-line); color: var(--down);" :disabled="closing" @click="confirmClose">{{ closing ? t('admin.security.closing') : t('admin.security.confirmClose') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input {
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
  outline: none;
  border: 1px solid var(--line-1);
  background-color: var(--surface-input);
  color: var(--ink-1);
  transition: border-color 0.15s ease;
}
.input:focus { border-color: var(--accent); }
</style>
