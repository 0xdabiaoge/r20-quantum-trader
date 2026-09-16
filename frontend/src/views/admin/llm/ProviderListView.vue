<script setup lang="ts">
/**
 * ProviderListView · 供应商矩阵（列表屏）
 * ---------------------------------------------------------------------------
 * 骨架（推倒重来）：
 *   旧 = 两张巨型配置卡（**同一段预设按钮复制 5 遍**）+ 搜索框
 *        + 供应商列表（**10 个分支的 emoji/符号头像** + 硬编码 rgba 胶囊）
 *   新 = 共享 PageHeader
 *        → **状态带**（在册供应商 / 主脑模型 / 思考上限 / 回退链）
 *        → **全局思考上限面板**（预设按钮由数组驱动）
 *        → **请求韧性与回退面板**（回退链行 + 可选模型 + 回退审计日志面板）
 *        → **供应商矩阵清单**（中性单字头像 + 语义徽章 + BaseSwitch）
 *
 * ⚠️ 状态仍由父页 `provide(LLM_KEY, useLlmConfig())` 注入，本组件只做展示；
 *    `useLlmConfig.ts` / `llmLogic.ts` 两个逻辑模块**未触碰**。
 *
 * 批 14 补：`loadConfig()` 内部把失败吞进 `console.error`，不发任何错误状态
 * ——于是拉取失败时页面会渲染成「没有供应商」（**失败被显示成空**）。
 * 逻辑层不动的前提下，展示层用「加载已结束但仍无 cfg」判定失败并给出重试。
 */
import { computed } from 'vue'
import PageHeader from '../../../components/admin/PageHeader.vue'
import BaseSwitch from '../../../components/base/BaseSwitch.vue'
import { fmtDateTime } from '../../../utils/format'
import { useI18n } from '../../../composables/useI18n'
import { useLlmCtx } from './injection'
import { AlertCircle, ArrowDown, ArrowUp, CheckCircle2, Clock, History, Plus,
  RefreshCw, Save, Search, ShieldAlert, X, Server, Brain, Timer, Route } from 'lucide-vue-next'

const { t } = useI18n()
const {
  cfg,
  failoverEvents,
  fallbackIds,
  fallbackOptions,
  filteredProviders,
  loadConfig,
  loadFailoverEvents,
  loading,
  modelNameOf,
  moveFallback,
  openAddProviderModal,
  requestAttemptsInput,
  saveGlobalSettings,
  savingSettings,
  searchQuery,
  selectProvider,
  setPresetTimeout,
  settingsResult,
  thinkingTimeoutInput,
  toggleFallback,
  toggleProviderQuick,
} = useLlmCtx()

/** 首次加载中（尚无配置可渲染）→ 骨架 */
const cfgFirstLoad = computed(() => loading.value && !cfg.value)

/** 加载已结束但仍无配置 → 判定为拉取失败（`loadConfig` 把异常吞在 console）
 *  纯展示层判定：成功时 `cfg` 必为对象（endpoint 返回配置对象），故 `!cfg` 即失败。 */
const cfgFailed = computed(() => !loading.value && !cfg.value)

/** 思考超时预设（旧版把这一段按钮块逐字复制了 5 遍）
 *  注：这里存**完整键路径**并直接 `t(p.labelKey)`，不使用拼接式键名——
 *  拼接出来的键无法被 i18n 静态校验识别，且缺键时会在界面渲染出裸键名。 */
const TIMEOUT_PRESETS = [
  { sec: 30, labelKey: 'admin.llm.presetFast' },
  { sec: 60, labelKey: 'admin.llm.presetStd' },
  { sec: 120, labelKey: 'admin.llm.presetRec' },
  { sec: 180, labelKey: 'admin.llm.presetDeep' },
  { sec: 300, labelKey: 'admin.llm.presetLong' },
]
const ATTEMPT_PRESETS = [1, 2, 3, 5]

/** 供应商头像改为中性单字（旧版是 10 个分支的 emoji/符号 + 色相类） */
function monogram(name: string): string {
  return String(name || '?').trim().slice(0, 2).toUpperCase()
}

/**
 * BaseSwitch 只抛出布尔值，而 `toggleProviderQuick(prov, e)` 需要一个能 `stopPropagation()`
 * 的事件对象（旧版传的是原生点击事件，用于阻止冒泡到整行的 `selectProvider`）。
 * 这里补一个最小事件替身，语义与旧版一致；行内已用 `@click.stop` 兜住冒泡。
 */
function onToggleProvider(prov: any) {
  const evt = { stopPropagation() {} } as unknown as Event
  void toggleProviderQuick(prov, evt)
}

/** 状态带 4 项事实 */
const bandFacts = () => [
  {
    icon: Server,
    label: t('admin.llm.bandProviders'),
    value: String(cfg.value?.providers?.length ?? '--'),
    foot: `${(cfg.value?.providers || []).filter((p: any) => p.enabled).length} ${t('admin.llm.enabledOnList')}`,
    tone: '',
  },
  {
    icon: Brain,
    label: t('admin.llm.bandActiveModel'),
    value: cfg.value?.active_model_id || t('admin.llm.notSelected'),
    foot: cfg.value?.active_reasoning_effort ? String(cfg.value.active_reasoning_effort).toUpperCase() : 'HIGH',
    tone: cfg.value?.active_model_id ? 'is-accent' : 'is-off',
  },
  {
    icon: Timer,
    label: t('admin.llm.bandTimeout'),
    value: `${cfg.value?.thinking_timeout || 120}s`,
    foot: t('admin.llm.validRange'),
    tone: '',
  },
  {
    icon: Route,
    label: t('admin.llm.bandFallback'),
    value: String(fallbackIds.value.length),
    foot: fallbackIds.value.length ? modelNameOf(fallbackIds.value[0]) : t('admin.llm.noFallback'),
    tone: fallbackIds.value.length ? '' : 'is-off',
  },
]
</script>

<template>
  <div class="pv">
    <PageHeader :title="t('nav.admin.llm')" :description="t('admin.llm.desc')">
      <template #actions>
        <button class="btn btn-ghost btn-sm" :disabled="loading" @click="loadConfig">
          <RefreshCw :size="14" :class="loading && 'pv-spin'" />
          <span>{{ t('admin.llm.refreshStatus') }}</span>
        </button>
        <button class="btn btn-primary btn-sm" :title="t('admin.llm.addProviderTitle')" @click="openAddProviderModal">
          <Plus :size="14" />
          <span>{{ t('admin.llm.addProvider') }}</span>
        </button>
      </template>
    </PageHeader>

    <!-- ══ 状态带 ══ -->
    <section class="card pv-band">
      <div v-for="f in bandFacts()" :key="f.label" class="pv-fact">
        <span class="pv-fact-label"><component :is="f.icon" :size="12" />{{ f.label }}</span>
        <span class="pv-fact-value" :class="f.tone">{{ f.value }}</span>
        <span class="pv-fact-foot truncate">{{ f.foot }}</span>
      </div>
    </section>

    <!-- ══ 全局思考上限 ══ -->
    <section class="card">
      <header class="card-head">
        <div>
          <h2 class="card-title"><Clock :size="14" />{{ t('admin.llm.globalTimeoutTitle') }}</h2>
          <p class="card-sub">{{ t('admin.llm.globalTimeoutDesc') }}</p>
        </div>
        <span class="badge mono">{{ t('admin.llm.currentLimit', undefined, { n: cfg?.thinking_timeout || 120 }) }}</span>
        <button class="btn btn-primary btn-sm" :disabled="savingSettings" @click="saveGlobalSettings">
          <RefreshCw v-if="savingSettings" :size="14" class="pv-spin" />
          <Save v-else :size="14" />
          <span>{{ savingSettings ? t('admin.llm.saving') : t('admin.llm.saveReasoning') }}</span>
        </button>
      </header>

      <div class="pv-body">
        <div class="pv-kv">
          <span class="label-caps">{{ t('admin.llm.activeModel') }}</span>
          <span class="pv-kv-v mono" :class="cfg?.active_model_id ? 'is-accent' : 'is-off'">
            {{ cfg?.active_model_id || t('admin.llm.notSelected') }}
          </span>
        </div>
        <div class="pv-kv">
          <span class="label-caps">{{ t('admin.llm.effort') }}</span>
          <span class="pv-kv-v mono">{{ (cfg?.active_reasoning_effort || 'HIGH').toUpperCase() }}</span>
        </div>
      </div>

      <div class="pv-field">
        <div class="pv-field-head">
          <span class="form-label">{{ t('admin.llm.timeoutLabel') }}</span>
          <span class="pv-hint">{{ t('admin.llm.validRange') }}</span>
        </div>
        <div class="pv-field-row">
          <div class="pv-num focus-ring">
            <input
              v-model.number="thinkingTimeoutInput"
              type="number"
              min="10"
              max="1800"
              step="5"
              placeholder="120"
              class="pv-num-input"
            />
            <span class="pv-num-unit">{{ t('admin.llm.secondsUnit') }}</span>
          </div>
          <div class="pv-presets">
            <span class="label-caps">{{ t('admin.llm.presetLabel') }}</span>
            <button
              v-for="p in TIMEOUT_PRESETS"
              :key="p.sec"
              type="button"
              class="pv-preset"
              :class="{ 'is-on': thinkingTimeoutInput === p.sec }"
              @click="setPresetTimeout(p.sec)"
            >
              {{ t(p.labelKey) }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="settingsResult" class="pv-result" :class="settingsResult.ok ? 'is-ok' : 'is-error'">
        <CheckCircle2 v-if="settingsResult.ok" :size="14" />
        <AlertCircle v-else :size="14" />
        <span>{{ settingsResult.message || settingsResult.error }}</span>
      </div>
    </section>

    <!-- ══ 请求韧性与回退 ══ -->
    <section class="card">
      <header class="card-head">
        <div>
          <h2 class="card-title"><ShieldAlert :size="14" />{{ t('admin.llm.resilienceTitle') }}</h2>
          <p class="card-sub">{{ t('admin.llm.resilienceDesc') }}</p>
        </div>
        <span class="badge mono">
          {{ t('admin.llm.attemptsChip', undefined, { n: cfg?.request_attempts || 3, m: (cfg?.fallback_model_ids || []).length }) }}
        </span>
        <button class="btn btn-primary btn-sm" :disabled="savingSettings" @click="saveGlobalSettings">
          <RefreshCw v-if="savingSettings" :size="14" class="pv-spin" />
          <Save v-else :size="14" />
          <span>{{ savingSettings ? t('admin.llm.saving') : t('admin.llm.saveResilience') }}</span>
        </button>
      </header>

      <div class="pv-resilience">
        <!-- 请求次数 -->
        <div class="pv-sub">
          <div class="pv-field-head">
            <span class="form-label">{{ t('admin.llm.attemptsLabel') }}</span>
            <span class="pv-hint">{{ t('admin.llm.attemptsRange') }}</span>
          </div>
          <div class="pv-field-row">
            <div class="pv-num focus-ring">
              <input
                v-model.number="requestAttemptsInput"
                type="number"
                min="1"
                max="10"
                step="1"
                class="pv-num-input"
              />
              <span class="pv-num-unit">{{ t('admin.llm.timesUnit') }}</span>
            </div>
            <div class="pv-presets">
              <button
                v-for="n in ATTEMPT_PRESETS"
                :key="n"
                type="button"
                class="pv-preset"
                :class="{ 'is-on': requestAttemptsInput === n }"
                @click="requestAttemptsInput = n"
              >
                {{ t('admin.llm.timesN', undefined, { n }) }}
              </button>
            </div>
          </div>
          <p class="pv-hint block">{{ t('admin.llm.attemptsDesc') }}</p>
        </div>

        <!-- 回退链 -->
        <div class="pv-sub">
          <div class="pv-field-head">
            <span class="form-label">{{ t('admin.llm.fallbackLabel') }}</span>
            <span class="pv-hint">{{ t('admin.llm.currentBrain') }} {{ cfg?.active_model_id || '--' }}</span>
          </div>

          <p v-if="!fallbackIds.length" class="pv-empty">{{ t('admin.llm.noFallback') }}</p>
          <ol v-else class="pv-chain">
            <li v-for="(fid, idx) in fallbackIds" :key="fid" class="pv-chain-row">
              <span class="pv-chain-n mono">{{ idx + 1 }}</span>
              <span class="pv-chain-name truncate">{{ modelNameOf(fid) }}</span>
              <button type="button" class="btn btn-quiet btn-icon btn-sm" :title="t('admin.llm.moveUp')" :disabled="idx === 0" @click="moveFallback(idx, -1)">
                <ArrowUp :size="12" />
              </button>
              <button type="button" class="btn btn-quiet btn-icon btn-sm" :title="t('admin.llm.moveDown')" :disabled="idx === fallbackIds.length - 1" @click="moveFallback(idx, 1)">
                <ArrowDown :size="12" />
              </button>
              <button type="button" class="btn btn-quiet btn-icon btn-sm is-danger" :title="t('admin.llm.remove')" @click="toggleFallback(fid)">
                <X :size="12" />
              </button>
            </li>
          </ol>

          <div class="pv-pool">
            <span class="label-caps">{{ t('admin.llm.toggleFallbackHint') }}</span>
            <div class="pv-pool-items">
              <button
                v-for="m in fallbackOptions"
                :key="m.id"
                type="button"
                class="pv-preset"
                :class="{ 'is-on': fallbackIds.includes(m.id) }"
                :title="m.description || m.id"
                @click="toggleFallback(m.id)"
              >
                {{ m.name || m.id }}
              </button>
              <span v-if="!fallbackOptions.length" class="pv-empty">{{ t('admin.llm.noSpareModels') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 回退审计 -->
      <div class="pv-audit-head">
        <span class="label-caps"><History :size="11" />{{ t('admin.llm.recentFailover') }}</span>
        <button class="btn btn-ghost btn-sm" @click="loadFailoverEvents">
          <RefreshCw :size="12" />
          <span>{{ t('admin.llm.refresh') }}</span>
        </button>
      </div>

      <p v-if="!failoverEvents.length" class="pv-empty pad">{{ t('admin.llm.noFailover') }}</p>

      <div v-else class="log-panel pv-audit">
        <div v-for="(ev, i) in failoverEvents.slice(0, 8)" :key="i" class="pv-audit-row">
          <span class="badge" :class="ev.succeeded ? 'badge-up' : 'badge-down'">
            {{ ev.type === 'fallback_hit' ? t('admin.llm.fallbackHit') : t('admin.llm.chainDead') }}
          </span>
          <span class="pv-audit-chain mono truncate">
            {{ ev.from_model }}<template v-if="ev.to_model"> → {{ ev.to_model }}</template>
          </span>
          <span class="pv-audit-time mono">{{ fmtDateTime(ev.ts || ev.time_str) }} · {{ ev.elapsed_seconds }}s</span>
          <span class="pv-audit-err truncate" :title="(ev.errors || []).join(' | ')">
            {{ (ev.errors || [])[0] || ev.chain || '' }}
          </span>
        </div>
      </div>
    </section>

    <!-- ══ 供应商矩阵 ══ -->
    <section class="card">
      <header class="card-head">
        <h2 class="card-title"><Server :size="14" />{{ t('admin.llm.providersTitle') }}</h2>
        <div class="pv-search focus-ring">
          <Search :size="13" />
          <input v-model="searchQuery" :placeholder="t('admin.llm.searchPlaceholder')" class="pv-search-input" />
        </div>
        <span class="badge mono">{{ filteredProviders.length }}</span>
      </header>

      <!-- ① 首次加载：骨架 -->
      <div v-if="cfgFirstLoad" class="pv-skel">
        <div v-for="i in 4" :key="i" class="skeleton skeleton-row" />
      </div>

      <!-- ② 加载结束但无配置：报错 + 重试（失败不再伪装成"没有供应商"） -->
      <div v-else-if="cfgFailed" class="state-block is-error pv-gate-err">
        <span class="state-icon"><ShieldAlert :size="17" /></span>
        <p class="state-title">{{ t('common.loadFailed') }}</p>
        <p class="state-desc">{{ t('common.networkError') }}</p>
        <button class="btn btn-ghost btn-sm" :disabled="loading" @click="loadConfig">
          <RefreshCw :size="13" />
          <span>{{ t('common.retry') }}</span>
        </button>
      </div>

      <p v-else-if="!filteredProviders.length" class="pv-empty pad">{{ t('common.noRecords') }}</p>

      <div v-else class="pv-rows">
        <article
          v-for="prov in filteredProviders"
          :key="prov.id"
          class="pv-row"
          :class="{ 'is-off': !prov.enabled }"
          @click="selectProvider(prov)"
        >
          <span class="pv-avatar mono">{{ monogram(prov.name) }}</span>

          <div class="pv-main">
            <div class="pv-title">
              <span class="pv-name">{{ prov.name }}</span>
              <span
                v-if="prov.models?.some((m: any) => m.id === cfg?.active_model_id)"
                class="badge badge-up"
              >
                {{ t('admin.llm.brainActive') }}
              </span>
            </div>
            <span class="pv-meta mono">
              {{ prov.id }} · {{ prov.models_count || 0 }} {{ t('admin.llm.modelsSuffix') }} · {{ prov.group || t('admin.llm.groupOther') }}
            </span>
          </div>

          <div class="pv-actions" @click.stop>
            <span class="pv-state" :class="prov.enabled ? 'is-on' : ''">
              {{ prov.enabled ? t('admin.llm.enabledOnList') : t('admin.llm.disabledOnList') }}
            </span>
            <BaseSwitch
              :model-value="prov.enabled === true"
              :disabled="false"
              :label="`${prov.name || prov.id} · ${t('admin.llm.enabledField')}`"
              @update:model-value="() => onToggleProvider(prov)"
            />
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.pv {
  display: flex;
  flex-direction: column;
  gap: var(--ds-space-4);
}
.pv-spin {
  animation: pv-rotate 0.9s linear infinite;
}
@keyframes pv-rotate {
  to {
    transform: rotate(360deg);
  }
}

/* ══ 状态带 ══ */
.pv-band {
  display: grid;
  grid-template-columns: 1fr;
}
@media (min-width: 640px) {
  .pv-band {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (min-width: 1280px) {
  .pv-band {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}
.pv-fact {
  display: flex;
  flex-direction: column;
  gap:4px;
  min-width: 0;
  padding: var(--ds-space-4);
  border-top: 1px solid var(--ds-color-border-default);
}
.pv-fact:first-child {
  border-top: 0;
}
@media (min-width: 640px) {
  .pv-fact:nth-child(2) {
    border-top: 0;
  }
  .pv-fact:nth-child(even) {
    border-left: 1px solid var(--ds-color-border-default);
  }
}
@media (min-width: 1280px) {
  .pv-fact {
    border-top: 0;
  }
  .pv-fact + .pv-fact {
    border-left: 1px solid var(--ds-color-border-default);
  }
}
.pv-fact-label {
  display: flex;
  align-items: center;
  gap:6px;
  font-size: var(--text-3xs);
  font-weight: 500;
  letter-spacing: var(--track-label);
  text-transform: uppercase;
  color: var(--ds-color-text-placeholder);
}
.pv-fact-value {
  font-size: var(--text-md);
  font-weight: 500;
  letter-spacing: var(--track-display);
  line-height: 1.25;
  color: var(--ds-color-text-primary);
  min-width: 0;
  overflow-wrap: anywhere;
}
.pv-fact-value.is-accent {
  color: var(--ds-color-brand);
}
.pv-fact-value.is-off {
  color: var(--ds-color-text-placeholder);
}
.pv-fact-foot {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}

/* ══ 通用块 ══ */
.pv-body {
  display: grid;
  grid-template-columns: 1fr;
  border-bottom: 1px solid var(--ds-color-border-default);
}
@media (min-width: 700px) {
  .pv-body {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.pv-kv {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: 10px var(--ds-space-4);
}
@media (min-width: 700px) {
  .pv-kv + .pv-kv {
    border-left: 1px solid var(--ds-color-border-default);
  }
}
.pv-kv-v {
  font-size: var(--text-xs);
  color: var(--ds-color-text-primary);
  overflow-wrap: anywhere;
}
.pv-kv-v.is-accent {
  color: var(--ds-color-brand);
}
.pv-kv-v.is-off {
  color: var(--ds-color-text-placeholder);
}

.pv-field {
  padding: var(--ds-space-4);
}
.pv-field-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ds-space-3);
  flex-wrap: wrap;
  margin-bottom:8px;
}
.pv-field-row {
  display: flex;
  align-items: center;
  gap: var(--ds-space-4);
  flex-wrap: wrap;
}
.pv-hint {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.pv-hint.block {
  display: block;
  margin-top:8px;
  line-height: var(--leading-body);
}

.pv-num {
  display: flex;
  align-items: center;
  border: 1px solid var(--ds-color-border-default);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-input);
  overflow: hidden;
  flex-shrink: 0;
}
.pv-num-input {
  width: 76px;
  padding:8px 10px;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--ds-color-text-primary);
  font-size: var(--text-xs);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.pv-num-unit {
  padding:0 10px 0 2px;
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
  white-space: nowrap;
}

.pv-presets {
  display: flex;
  align-items: center;
  gap:6px;
  flex-wrap: wrap;
  min-width: 0;
}
.pv-preset {
  /* 批 18：热区补到 24px 高（原 23px，正好卡在可点下限之下） */
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 4px 10px;
  border: 1px solid var(--ds-color-border-default);
  border-radius: var(--r-ctl);
  background-color: transparent;
  font-size: var(--text-4xs);
  color: var(--ds-color-text-description);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.pv-preset:hover {
  background-color: var(--ds-color-bg-hover);
  color: var(--ds-color-text-primary);
}
.pv-preset.is-on {
  background-color: var(--r20-brand-bg);
  border-color: var(--r20-brand-line);
  color: var(--ds-color-brand);
  font-weight: 600;
}

.pv-result {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 var(--ds-space-4) var(--ds-space-4);
  padding: 8px 10px;
  border-radius: var(--r-ctl);
  font-size: var(--text-3xs);
}
.pv-result.is-ok {
  background-color: var(--up-bg);
  color: var(--up);
}
.pv-result.is-error {
  background-color: var(--down-bg);
  color: var(--down);
}

/* ══ 韧性 ══ */
.pv-resilience {
  display: grid;
  grid-template-columns: 1fr;
}
@media (min-width: 1000px) {
  .pv-resilience {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}
.pv-sub {
  padding: var(--ds-space-4);
  border-top: 1px solid var(--ds-color-border-default);
}
@media (min-width: 1000px) {
  .pv-sub {
    border-top: 0;
  }
  .pv-sub + .pv-sub {
    border-left: 1px solid var(--ds-color-border-default);
  }
}

.pv-empty {
  font-size: var(--text-3xs);
  color: var(--ds-color-text-placeholder);
  line-height: var(--leading-body);
}
.pv-empty.pad {
  padding: var(--ds-space-4);
}

/* 批 14：首次加载骨架 / 拉取失败态 */
.pv-skel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: var(--ds-space-4);
}
.pv-gate-err {
  border-top: 1px solid var(--ds-color-border-default);
}

.pv-chain {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.pv-chain-row {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  padding:6px 8px;
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-surface-inset);
}
.pv-chain-n {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background-color: var(--ds-color-bg-surface-1);
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
  flex-shrink: 0;
}
.pv-chain-name {
  flex: 1;
  min-width: 0;
  font-size: var(--text-3xs);
  font-weight: 600;
  color: var(--ds-color-text-primary);
}

.pv-pool {
  margin-top: var(--ds-space-3);
  padding-top: var(--ds-space-3);
  border-top: 1px solid var(--ds-color-border-default);
}
.pv-pool-items {
  display: flex;
  flex-wrap: wrap;
  gap:6px;
  margin-top: 6px;
  max-height: 108px;
  overflow-y: auto;
}

.pv-audit-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ds-space-3);
  padding: var(--ds-space-3) var(--ds-space-4) 6px;
  border-top: 1px solid var(--ds-color-border-default);
}
.pv-audit-head .label-caps {
  display: flex;
  align-items: center;
  gap:6px;
}
.pv-audit {
  border: 0;
  border-radius: 0;
  background-color: transparent;
  max-height: 240px;
}
.pv-audit-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1.1fr) auto minmax(0, 1.4fr);
  align-items: center;
  gap: var(--ds-space-3);
  padding:6px var(--ds-space-4);
  font-size: var(--text-4xs);
}
.pv-audit-row:hover {
  background-color: var(--ds-color-bg-hover);
}
.pv-audit-chain {
  color: var(--ds-color-text-secondary);
  min-width: 0;
}
.pv-audit-time {
  color: var(--ds-color-text-placeholder);
  white-space: nowrap;
}
.pv-audit-err {
  color: var(--ds-color-text-placeholder);
  min-width: 0;
}
@media (max-width: 900px) {
  .pv-audit-row {
    grid-template-columns: auto minmax(0, 1fr);
  }
  .pv-audit-err {
    grid-column: 2;
  }
}

/* ══ 供应商清单 ══ */
.pv-search {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  padding: 0 10px;
  border: 1px solid var(--ds-color-border-default);
  border-radius: var(--r-ctl);
  background-color: var(--ds-color-bg-input);
  color: var(--ds-color-text-placeholder);
}
.pv-search-input {
  width: 190px;
  padding: 6px 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--ds-color-text-primary);
  font-size: var(--text-3xs);
}
@media (max-width: 760px) {
  .pv-search-input {
    width: 110px;
  }
}

.pv-rows {
  display: flex;
  flex-direction: column;
}
.pv-row {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ds-space-3);
  padding: var(--ds-space-3) var(--ds-space-4);
  border-bottom: 1px solid var(--ds-color-border-default);
  cursor: pointer;
  transition: background-color var(--dur-fast);
}
.pv-row:last-child {
  border-bottom: 0;
}
.pv-row:hover {
  background-color: var(--ds-color-bg-hover);
}
.pv-row.is-off {
  opacity: 0.6;
}
.pv-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: var(--r-ctl);
  border: 1px solid var(--ds-color-border-default);
  background-color: var(--ds-color-bg-surface-1);
  font-size: var(--text-4xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--ds-color-text-description);
  flex-shrink: 0;
}
.pv-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.pv-title {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.pv-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ds-color-text-primary);
}
.pv-meta {
  font-size: var(--text-4xs);
  color: var(--ds-color-text-placeholder);
}
.pv-actions {
  display: flex;
  align-items: center;
  gap: var(--ds-space-2);
  flex-shrink: 0;
}
.pv-state {
  font-size: var(--text-4xs);
  font-weight: 600;
  color: var(--ds-color-text-placeholder);
}
.pv-state.is-on {
  color: var(--up);
}

@media (max-width: 720px) {
  .pv-row {
    grid-template-columns: 34px minmax(0, 1fr);
  }
  .pv-actions {
    grid-column: 2;
    justify-content: flex-end;
  }
}
</style>
