<script setup lang="ts">
/**
 * ProviderListView：从 1762 行的 LlmPage.vue 拆出的视图块（结构优化阶段 3·F3）。
 *
 * 状态由父页 `provide(LLM_KEY, useLlmConfig())` 注入，本组件 `useLlmCtx()` 取用：
 * 这样拆**不会**新建一份状态（composable 每次调用都会建新状态，直接调用即出错），
 * 也不必为几十个绑定铺 prop/emit 管道。标记一处未改，DOM 结构未变。
 */
import PageHeader from '../../../components/admin/PageHeader.vue'
import { fmtDateTime } from '../../../utils/format'
import { useI18n } from '../../../composables/useI18n'
import { useLlmCtx } from './injection'
import {AlertCircle, ArrowDown, ArrowUp, CheckCircle2, Clock, History, Plus, RefreshCw, Save, Search, ShieldAlert, X} from 'lucide-vue-next'

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
</script>

<template>
    <!-- Top Title & Navigation Bar -->
    <PageHeader :title="t('nav.admin.llm')" :description="t('admin.llm.desc')">
      <template #actions>
      <div class="flex items-center space-x-2">
        <button
          @click="openAddProviderModal"
          class="btn-admin-primary"
          :title="t('admin.llm.addProviderTitle')"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>{{ t('admin.llm.addProvider') }}</span>
        </button>

        <button
          @click="loadConfig"
          class="btn-admin-secondary px-2"
          :title="t('admin.llm.refreshStatus')"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
        </button>
      </div>
      </template>
    </PageHeader>

    <!-- Global Reasoning & Thinking Timeout Configuration Card -->
    <div
      class="rounded-2xl border p-4 sm:p-5 shadow-xs transition-colors space-y-3"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b" style="border-color: var(--line-1);">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-blue-500/10 text-blue-400 border border-blue-500/20">
            <Clock class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h2 class="text-xs sm:text-[13px] font-bold" style="color: var(--ink-1);">
                {{ t('admin.llm.globalTimeoutTitle') }}
              </h2>
              <span
                class="px-2 py-0.5 rounded text-[11px] font-bold border"
                style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);"
              >
                {{ t('admin.llm.currentLimit', undefined, { n: cfg?.thinking_timeout || 120 }) }}
              </span>
            </div>
            <p class="text-[11px] mt-0.5" style="color: var(--ink-2);">
              {{ t('admin.llm.globalTimeoutDesc') }}
            </p>
          </div>
        </div>

        <button
          @click="saveGlobalSettings"
          :disabled="savingSettings"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold text-white transition-all cursor-pointer shadow-xs disabled:opacity-40"
          style="background-color: var(--accent); border-color: var(--accent); color: var(--accent-ink);"
        >
          <RefreshCw v-if="savingSettings" class="w-3.5 h-3.5 animate-spin" />
          <Save v-else class="w-3.5 h-3.5" />
          <span>{{ savingSettings ? t('admin.llm.saving') : t('admin.llm.saveReasoning') }}</span>
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 pt-1">
        <!-- Active Model & Reasoning Effort Status -->
        <div class="p-3 rounded-xl border space-y-1.5" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.activeModel') }}</div>
          <div class="text-xs font-bold truncate text-blue-400">
            {{ cfg?.active_model_id || t('admin.llm.notSelected') }}
          </div>
          <div class="text-[11px] flex items-center space-x-1" style="color: var(--ink-2);">
            <span>{{ t('admin.llm.effort') }}</span>
            <span class="font-bold uppercase text-emerald-400">{{ cfg?.active_reasoning_effort || 'HIGH' }}</span>
          </div>
        </div>

        <!-- Thinking Timeout Input Field -->
        <div class="p-3 rounded-xl border space-y-1.5 sm:col-span-1 lg:col-span-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="flex items-center justify-between">
            <label class="text-[11px] font-bold" style="color: var(--ink-2);">
              {{ t('admin.llm.timeoutLabel') }}
            </label>
            <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.validRange') }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <input
              v-model.number="thinkingTimeoutInput"
              type="number"
              min="10"
              max="1800"
              step="5"
              placeholder="120"
              class="w-28 rounded-lg px-3 py-1.5 text-xs outline-none border font-bold"
              style="background-color: var(--surface-2); border-color: var(--line-2); color: var(--ink-1);"
            />
            <span class="text-xs font-bold" style="color: var(--ink-2);">{{ t('admin.llm.secondsUnit') }}</span>

            <!-- Quick Presets -->
            <div class="flex flex-wrap items-center gap-1.5 pl-2">
              <button
                type="button"
                @click="setPresetTimeout(30)"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="thinkingTimeoutInput === 30 ? 'bg-blue-500/20 text-blue-400 border-blue-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.presetFast') }}
              </button>
              <button
                type="button"
                @click="setPresetTimeout(60)"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="thinkingTimeoutInput === 60 ? 'bg-blue-500/20 text-blue-400 border-blue-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.presetStd') }}
              </button>
              <button
                type="button"
                @click="setPresetTimeout(120)"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="thinkingTimeoutInput === 120 ? 'bg-blue-500/20 text-blue-400 border-blue-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.presetRec') }}
              </button>
              <button
                type="button"
                @click="setPresetTimeout(180)"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="thinkingTimeoutInput === 180 ? 'bg-blue-500/20 text-blue-400 border-blue-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.presetDeep') }}
              </button>
              <button
                type="button"
                @click="setPresetTimeout(300)"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="thinkingTimeoutInput === 300 ? 'bg-blue-500/20 text-blue-400 border-blue-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.presetLong') }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Feedback Alert -->
      <div
        v-if="settingsResult"
        class="p-2.5 rounded-lg border text-xs flex items-center space-x-2"
        :style="settingsResult.ok
          ? { backgroundColor: 'var(--up-bg)', borderColor: 'var(--up-line)', color: 'var(--up)' }
          : { backgroundColor: 'var(--down-bg)', borderColor: 'var(--down-line)', color: 'var(--down)' }"
      >
        <CheckCircle2 v-if="settingsResult.ok" class="w-3.5 h-3.5 shrink-0" />
        <AlertCircle v-else class="w-3.5 h-3.5 shrink-0" />
        <span>{{ settingsResult.message || settingsResult.error }}</span>
      </div>
    </div>

    <!-- Resilience: Request Attempts & Fallback Model Chain -->
    <div
      class="rounded-2xl border p-4 sm:p-5 shadow-xs transition-colors space-y-3"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <div class="flex flex-wrap items-center justify-between gap-2 pb-3 border-b" style="border-color: var(--line-1);">
        <div class="flex items-center space-x-2.5">
          <div class="w-8 h-8 rounded-lg flex items-center justify-center bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <ShieldAlert class="w-4 h-4" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h2 class="text-xs sm:text-[13px] font-bold" style="color: var(--ink-1);">
                {{ t('admin.llm.resilienceTitle') }}
              </h2>
              <span
                class="px-2 py-0.5 rounded text-[11px] font-bold border"
                style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);"
              >
                {{ t('admin.llm.attemptsChip', undefined, { n: cfg?.request_attempts || 3, m: (cfg?.fallback_model_ids || []).length }) }}
              </span>
            </div>
            <p class="text-[11px] mt-0.5" style="color: var(--ink-2);">
              {{ t('admin.llm.resilienceDesc') }}
            </p>
          </div>
        </div>

        <button
          @click="saveGlobalSettings"
          :disabled="savingSettings"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs disabled:opacity-40"
          style="background-color: var(--accent); border-color: var(--accent); color: var(--accent-ink);"
        >
          <RefreshCw v-if="savingSettings" class="w-3.5 h-3.5 animate-spin" />
          <Save v-else class="w-3.5 h-3.5" />
          <span>{{ savingSettings ? t('admin.llm.saving') : t('admin.llm.saveResilience') }}</span>
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        <!-- Request attempts -->
        <div class="p-3 rounded-xl border space-y-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="flex items-center justify-between">
            <label class="text-[11px] font-bold" style="color: var(--ink-2);">{{ t('admin.llm.attemptsLabel') }}</label>
            <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.attemptsRange') }}</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <input
              v-model.number="requestAttemptsInput"
              type="number"
              min="1"
              max="10"
              step="1"
              class="w-20 rounded-lg px-3 py-1.5 text-xs outline-none border font-bold"
              style="background-color: var(--surface-2); border-color: var(--line-2); color: var(--ink-1);"
            />
            <span class="text-xs font-bold" style="color: var(--ink-2);">{{ t('admin.llm.timesUnit') }}</span>
            <div class="flex flex-wrap items-center gap-1.5 pl-1">
              <button
                v-for="n in [1, 2, 3, 5]"
                :key="n"
                type="button"
                @click="requestAttemptsInput = n"
                class="px-2 py-1 rounded text-[11px] border cursor-pointer transition-all"
                :class="requestAttemptsInput === n ? 'bg-amber-500/20 text-amber-400 border-amber-500 font-bold' : 'text-gray-400 hover:text-white border-transparent'"
              >
                {{ t('admin.llm.timesN', undefined, { n }) }}
              </button>
            </div>
          </div>
          <p class="text-[10px] leading-relaxed" style="color: var(--ink-3);">
            {{ t('admin.llm.attemptsDesc') }}
          </p>
        </div>

        <!-- Fallback chain -->
        <div class="p-3 rounded-xl border space-y-2" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="flex items-center justify-between">
            <label class="text-[11px] font-bold" style="color: var(--ink-2);">{{ t('admin.llm.fallbackLabel') }}</label>
            <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.currentBrain') }} {{ cfg?.active_model_id || '--' }}</span>
          </div>

          <div v-if="fallbackIds.length === 0" class="text-[11px] italic px-1 py-0.5" style="color: var(--ink-3);">
            {{ t('admin.llm.noFallback') }}
          </div>
          <div v-else class="space-y-1">
            <div
              v-for="(fid, idx) in fallbackIds"
              :key="fid"
              class="flex items-center justify-between gap-2 px-2 py-1.5 rounded-lg border text-[11px]"
              style="background-color: var(--surface-2); border-color: var(--line-1);"
            >
              <div class="flex items-center space-x-2 min-w-0">
                <span class="w-4 h-4 shrink-0 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25 flex items-center justify-center font-bold text-[10px]">{{ idx + 1 }}</span>
                <span class="font-bold truncate" style="color: var(--ink-1);">{{ modelNameOf(fid) }}</span>
              </div>
              <div class="flex items-center space-x-1 shrink-0">
                <button type="button" :title="t('admin.llm.moveUp')" @click="moveFallback(idx, -1)" class="p-1 rounded hover:bg-[var(--surface-1)] cursor-pointer text-gray-400"><ArrowUp class="w-3 h-3" /></button>
                <button type="button" :title="t('admin.llm.moveDown')" @click="moveFallback(idx, 1)" class="p-1 rounded hover:bg-[var(--surface-1)] cursor-pointer text-gray-400"><ArrowDown class="w-3 h-3" /></button>
                <button type="button" :title="t('admin.llm.remove')" @click="toggleFallback(fid)" class="p-1 rounded hover:bg-[var(--surface-1)] cursor-pointer text-red-400"><X class="w-3 h-3" /></button>
              </div>
            </div>
          </div>

          <div class="pt-1 border-t" style="border-color: var(--line-1);">
            <div class="text-[10px] mb-1.5" style="color: var(--ink-3);">{{ t('admin.llm.toggleFallbackHint') }}</div>
            <div class="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto">
              <button
                v-for="m in fallbackOptions"
                :key="m.id"
                type="button"
                @click="toggleFallback(m.id)"
                class="px-2 py-1 rounded-lg text-[11px] border cursor-pointer transition-all"
                :class="fallbackIds.includes(m.id)
                  ? 'bg-amber-500/20 text-amber-400 border-amber-500 font-bold'
                  : 'text-gray-400 border-transparent hover:text-white hover:bg-[var(--surface-2)]'"
                :title="m.description || m.id"
              >
                {{ m.name || m.id }}
              </button>
              <span v-if="fallbackOptions.length === 0" class="text-[11px] italic" style="color: var(--ink-3);">
                {{ t('admin.llm.noSpareModels') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Failover audit -->
      <div class="pt-1">
        <div class="flex items-center justify-between pb-1.5">
          <div class="flex items-center space-x-1.5 text-[11px] font-bold" style="color: var(--ink-2);">
            <History class="w-3.5 h-3.5 text-amber-400" />
            <span>{{ t('admin.llm.recentFailover') }}</span>
          </div>
          <button @click="loadFailoverEvents" class="text-[11px] px-2 py-0.5 rounded border cursor-pointer" style="color: var(--ink-2); border-color: var(--line-1);">{{ t('admin.llm.refresh') }}</button>
        </div>
        <div v-if="failoverEvents.length === 0" class="text-[11px] italic px-1" style="color: var(--ink-3);">
          {{ t('admin.llm.noFailover') }}
        </div>
        <div v-else class="rounded-xl border divide-y overflow-hidden" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div
            v-for="(ev, i) in failoverEvents.slice(0, 8)"
            :key="i"
            class="px-3 py-2 text-[11px] space-y-0.5"
            style="border-color: var(--line-1);"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="font-bold" :class="ev.succeeded ? 'text-emerald-400' : 'text-red-400'">
                {{ ev.type === 'fallback_hit' ? t('admin.llm.fallbackHit') : t('admin.llm.chainDead') }}
                {{ ev.from_model }}<template v-if="ev.to_model"> → {{ ev.to_model }}</template>
              </span>
              <span class="shrink-0" style="color: var(--ink-3);">{{ fmtDateTime(ev.ts || ev.time_str) }} · {{ ev.elapsed_seconds }}s</span>
            </div>
            <div class="truncate" style="color: var(--ink-2);" :title="(ev.errors || []).join(' | ')">
              {{ (ev.errors || [])[0] || ev.chain || '' }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Search Box (对应截图 1 顶部的搜索栏) -->
    <div class="relative">
      <input
        v-model="searchQuery"
        :placeholder="t('admin.llm.searchPlaceholder')"
        class="w-full rounded-2xl px-4 py-3 pl-11 text-xs outline-none border transition-colors shadow-xs"
        style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
      />
      <Search class="w-4 h-4 absolute left-4 top-3.5 text-gray-400 pointer-events-none" />
    </div>

    <!-- Providers List Container -->
    <div
      class="rounded-2xl border overflow-hidden shadow-xs divide-y transition-colors"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <div
        v-for="prov in filteredProviders"
        :key="prov.id"
        @click="selectProvider(prov)"
        class="p-4 flex items-center justify-between hover:bg-[var(--surface-1)] transition-colors cursor-pointer group"
        style="border-color: var(--line-1);"
      >
        <!-- Left: Provider Logo / Icon & Name -->
        <div class="flex items-center space-x-3.5">
          <!-- Icon Avatar -->
          <div
            class="w-10 h-10 rounded-xl flex items-center justify-center border font-bold text-sm shrink-0 transition-transform group-hover:scale-105"
            style="background-color: var(--surface-1); border-color: var(--line-1);"
          >
            <span v-if="prov.id === 'openai'" class="text-emerald-500">❖</span>
            <span v-else-if="prov.id === 'siliconflow'" class="text-purple-500">⚡</span>
            <span v-else-if="prov.id === 'gemini'" class="text-blue-500">✦</span>
            <span v-else-if="prov.id === 'openrouter'" class="text-indigo-500">◈</span>
            <span v-else-if="prov.id === 'deepseek'" class="text-sky-500">🐳</span>
            <span v-else-if="prov.id === 'claude'" class="text-amber-500">✳</span>
            <span v-else-if="prov.id === 'grok'" class="text-neutral-300">Ø</span>
            <span v-else-if="prov.id === 'volcengine'" class="text-cyan-500">📶</span>
            <span v-else-if="prov.id === 'dashscope'" class="text-orange-500">[-]</span>
            <span v-else-if="prov.id === 'zhipu'" class="text-violet-500">◆</span>
            <span v-else class="text-blue-400">❖</span>
          </div>

          <!-- Provider Name & Subtitle -->
          <div>
            <div class="flex items-center space-x-2">
              <span class="font-bold text-sm" style="color: var(--ink-1);">{{ prov.name }}</span>
              <span
                v-if="prov.models?.some((m: any) => m.id === cfg?.active_model_id)"
                class="px-1.5 py-0.2 rounded text-[11px] font-bold border"
                style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);"
              >
                {{ t('admin.llm.brainActive') }}
              </span>
            </div>
            <div class="text-[11px] mt-0.5" style="color: var(--ink-3);">
              {{ prov.models_count || 0 }} {{ t('admin.llm.modelsSuffix') }} · {{ prov.group || t('admin.llm.groupOther') }}
            </div>
          </div>
        </div>

        <!-- Right: Enable / Disable Badge & Chevron Arrow (对齐截图 1) -->
        <div class="flex items-center space-x-2.5">
          <!-- Capsule Status Button -->
          <button
            @click="toggleProviderQuick(prov, $event)"
            class="px-3 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer shadow-2xs"
            :style="prov.enabled ? {
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              borderColor: 'rgba(16, 185, 129, 0.25)',
              color: 'var(--up)',
            } : {
              backgroundColor: 'rgba(239, 68, 68, 0.08)',
              borderColor: 'rgba(239, 68, 68, 0.2)',
              color: '#F87171',
            }"
          >
            {{ prov.enabled ? t('admin.llm.enabledOnList') : t('admin.llm.disabledOnList') }}
          </button>

          <!-- Arrow Right -->
          <span class="text-gray-400 font-bold text-base select-none">›</span>
        </div>
      </div>
    </div>
</template>
