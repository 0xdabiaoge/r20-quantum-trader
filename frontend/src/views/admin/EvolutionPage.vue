<script setup lang="ts">
import { fmtDateTime } from '../../utils/format';
import { useToast } from '../../composables/useToast'
import { useConfirm } from '../../composables/useConfirm'
const toast = useToast()
const { ask } = useConfirm()
import { ref, computed, onMounted } from 'vue'
import PageHeader from '../../components/admin/PageHeader.vue'
import { useI18n } from '../../composables/useI18n'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {Brain,
  Sparkles,
  RefreshCw,
  Clock,
  Plus,
  Trash2,
  Save,
  PlayCircle,
  BookOpen,
  Sliders,
  Terminal,
  ShieldCheck,
  RotateCcw,
  ToggleLeft,
  ToggleRight} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()
const { t } = useI18n()

const loading = ref(true)
const busy = ref<'save' | 'run' | 'add' | 'delete' | 'toggle' | 'rollback' | ''>('')

// Pipelines state (evolution_system & evolution_user)
const activeTab = ref<'settings' | 'evolution_system' | 'evolution_user'>('settings')
const lib = ref<any>(null)
const selectedProfileId = ref('stable')
const workingModules = ref<any[]>([])

// Structured White-Box Memory state
const structuredLessons = ref<any[]>([])
const memoryVersion = ref<string | null>(null)
/** 结构化记忆是否启用（后端 legacy_read_only=False 表示走结构化 v1 护栏；缺失不猜） */
const memoryStructured = ref<boolean | null>(null)
const newMemoryText = ref('')
const evolutionReport = ref<any>(null)

// Scheduler settings

const selectedProfile = computed(() => (lib.value?.profiles || []).find((p: any) => p.id === selectedProfileId.value) || null)

async function loadData() {
  loading.value = true
  memoryVersion.value = null
  try {
    const [libRes, memRes, reportRes] = await Promise.all([
      api('/api/v1/prompt-library').catch(() => api('/api/v1/admin/prompt-library')),
      api('/api/v1/admin/memory'),
      api('/api/v1/cache/self-improvement').catch(() => null),
    ])
    lib.value = libRes
    selectedProfileId.value = libRes?.active_profile_id || 'stable'
    structuredLessons.value = memRes?.structured_lessons || []
    memoryVersion.value = memRes?.version || null
    memoryStructured.value = memRes && 'legacy_read_only' in memRes ? !memRes.legacy_read_only : null
    evolutionReport.value = reportRes || null
    syncWorkingModules()
  } catch (e: any) {
    toast.err(`加载失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

function syncWorkingModules() {
  if (activeTab.value === 'settings') return
  const views = selectedProfile.value?.pipeline_views?.[activeTab.value] || []
  workingModules.value = JSON.parse(JSON.stringify(views))
}

function switchTab(tab: 'settings' | 'evolution_system' | 'evolution_user') {
  activeTab.value = tab
  syncWorkingModules()
}

// Never retry writes: on failure require an explicit reload before another attempt.
function expectedMemoryVersion() {
  if (!memoryVersion.value) throw new Error('请重新加载心法后再操作')
  return memoryVersion.value
}

async function refreshMemory() {
  memoryVersion.value = null
  const res = await api('/api/v1/admin/memory')
  structuredLessons.value = res.structured_lessons || []
  memoryVersion.value = res.version || null
  memoryStructured.value = 'legacy_read_only' in res ? !res.legacy_read_only : null
}

async function reloadMemory() {
  if (busy.value || loading.value) return
  loading.value = true
  try {
    await refreshMemory()
  } catch (e: any) {
    toast.err(`重新加载心法失败: ${e.message}`)
  } finally {
    loading.value = false
  }
}

async function toggleLessonStatus(lessonId: string) {
  if (busy.value || loading.value) return
  busy.value = 'toggle'
  try {
    await api(`/api/v1/admin/memory/toggle/${encodeURIComponent(lessonId)}?expected_version=${encodeURIComponent(expectedMemoryVersion())}`, { method: 'POST' })
    await refreshMemory()
    toast.ok(`心法状态已切换（大模型下次决策立即感知）`)
  } catch (e: any) {
    memoryVersion.value = null
    toast.err(`状态切换失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function rollbackToBaseline() {
  // 批C(2026-09-13)·破坏性操作收口：本操作清除非基准心法（含当日自进化成果），
  // 原生 confirm 在移动端易误触；改逐字短语确认。
  const _ok = await ask({
    title: '防污染紧急回滚',
    desc: '清除非基准的过期/被污染心法，重置回官方基准黄金心法库（当日自进化成果将被丢弃）',
    danger: true,
    confirmPhrase: 'ROLLBACK',
    okText: '执行回滚',
  })
  if (!_ok) return
  if (busy.value || loading.value) return
  busy.value = 'rollback'
  try {
    await api(`/api/v1/admin/memory/rollback?expected_version=${encodeURIComponent(expectedMemoryVersion())}`, { method: 'POST' })
    await refreshMemory()
    toast.ok('🛡️ 已成功执行宪法级防污染回滚，系统已重置为黄金基准认知！')
  } catch (e: any) {
    memoryVersion.value = null
    toast.err(`回滚失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function addMemoryItem() {
  const text = newMemoryText.value.trim()
  if (!text) return
  if (busy.value || loading.value) return
  busy.value = 'add'
  try {
    await api('/api/v1/admin/memory', {
      method: 'POST',
      body: JSON.stringify({ text, expected_version: expectedMemoryVersion() }),
    })
    // Reload full structured list
    await refreshMemory()
    newMemoryText.value = ''
    toast.ok('新心法已通过防偏见审查，并成功同步写入决策注入层')
  } catch (e: any) {
    memoryVersion.value = null
    toast.err(`添加心法失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function deleteMemoryItem(idx: number, lessonId: string) {
  const _ok = await ask({ title: '删除自进化心法', desc: '该条心法将从认知库移除', danger: true, okText: '删除' })
  if (!_ok) return
  if (busy.value || loading.value) return
  busy.value = 'delete'
  try {
    await api(`/api/v1/admin/memory/${idx}?lesson_id=${encodeURIComponent(lessonId)}&expected_version=${encodeURIComponent(expectedMemoryVersion())}`, { method: 'DELETE' })
    await refreshMemory()
    toast.ok('该条自进化心法已成功移除')
  } catch (e: any) {
    memoryVersion.value = null
    toast.err(`删除失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function savePipelineModules() {
  if (!selectedProfile.value) return
  busy.value = 'save'
  try {
    const pipelinesMap: Record<string, any[]> = {}
    pipelinesMap[activeTab.value] = workingModules.value.map((m) => ({
      id: m.id,
      title: m.title,
      content: m.content,
      enabled: m.enabled,
      locked: m.locked,
      source: m.source,
    }))

    await api(`/api/v1/admin/prompt-profiles/${selectedProfile.value.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: selectedProfile.value.name,
        description: selectedProfile.value.description,
        pipelines: pipelinesMap,
      }),
    })
    toast.ok(`自进化模版布局已成功保存，下一轮复盘自动生效`)
    await loadData()
  } catch (e: any) {
    toast.err(`保存失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

async function triggerEvolutionNow() {
  const phrase = prompt('立即强制执行自进化复盘任务（对全天战绩穿透提炼并生成最新复盘心法），请输入确认短语：RUN EVOLUTION')
  if (!phrase) return
  if (phrase.trim().toUpperCase() !== 'RUN EVOLUTION') {
    toast.err('确认短语错误，已取消执行')
    return
  }
  busy.value = 'run'
  try {
    const res = await api('/api/v1/admin/gateway/jobs/self_improvement/run', {
      method: 'POST',
      body: JSON.stringify({ confirmation: 'RUN JOB' }),
    })
    toast.ok(`自进化复盘已完成（已自动执行离群噪点过滤与宪法安全审查）！${res.detail || ''}`)
    await loadData()
  } catch (e: any) {
    toast.err(`执行复盘失败: ${e.message}`)
  } finally {
    busy.value = ''
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-4 max-w-[2048px] mx-auto">
    <!-- Header -->
    <PageHeader :title="t('nav.admin.evolution')" :description="t('admin.evolution.desc')">
      <template #actions>
        <span class="chip"><span class="dot dot-up" />{{ t('admin.evolution.guardChip') }}</span>
      </template>
    </PageHeader>

    <!-- Banner -->
    <!-- Navigation Tabs -->
    <div class="flex flex-wrap items-center justify-between gap-3 p-1.5 rounded-xl border" style="background-color: var(--surface-2); border-color: var(--line-1);">
      <div class="flex flex-wrap gap-1">
        <button
          @click="switchTab('settings')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-colors"
          :style="activeTab === 'settings' ? { backgroundColor: 'var(--ink-1)', color: 'var(--surface-2)' } : { color: 'var(--ink-2)' }"
        >
          <Brain class="w-3.5 h-3.5" />
          <span>{{ t('admin.evolution.tabOverview') }}</span>
        </button>
        <button
          @click="switchTab('evolution_system')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-colors"
          :style="activeTab === 'evolution_system' ? { backgroundColor: 'var(--ink-1)', color: 'var(--surface-2)' } : { color: 'var(--ink-2)' }"
        >
          <BookOpen class="w-3.5 h-3.5" />
          <span>{{ t('admin.evolution.tabSystem') }}</span>
        </button>
        <button
          @click="switchTab('evolution_user')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-colors"
          :style="activeTab === 'evolution_user' ? { backgroundColor: 'var(--ink-1)', color: 'var(--surface-2)' } : { color: 'var(--ink-2)' }"
        >
          <Terminal class="w-3.5 h-3.5" />
          <span>{{ t('admin.evolution.tabUser') }}</span>
        </button>
      </div>

      <div class="flex items-center space-x-2">
        <button
          @click="reloadMemory"
          :disabled="busy !== '' || loading"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs cursor-pointer disabled:opacity-40 border"
        >
          <RefreshCw class="w-3.5 h-3.5" />
          <span>{{ t('admin.evolution.reloadMemory') }}</span>
        </button>
        <button
          v-if="auth.isSuperadmin"
          @click="rollbackToBaseline"
          :disabled="busy !== ''"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer disabled:opacity-40 transition-all border shadow-xs"
          style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          :title="t('admin.evolution.rollbackTitle')"
        >
          <RotateCcw class="w-3.5 h-3.5 text-amber-400" />
          <span>{{ t('admin.evolution.rollback') }}</span>
        </button>

        <button
          v-if="auth.isSuperadmin"
          @click="triggerEvolutionNow"
          :disabled="busy !== ''"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs"
          style="background-color: var(--accent-bg); border-color: var(--accent-line); color: var(--accent);"
        >
          <PlayCircle class="w-3.5 h-3.5" />
          <span>{{ busy === 'run' ? t('admin.evolution.runningReview') : t('admin.evolution.reviewNow') }}</span>
        </button>
      </div>
    </div>

    <!-- TAB 1: Settings & Structured White-Box Memory -->
    <div v-if="activeTab === 'settings'" class="space-y-4">
      <!-- 核心新增：最新自进化执行实况与诊断成果看板 -->
      <div v-if="evolutionReport" class="rounded-xl border p-4 shadow-xs space-y-3" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--line-1);">
          <div class="flex items-center space-x-2">
            <Sparkles class="w-4 h-4 text-amber-400" />
            <h3 class="text-xs sm:text-sm font-semibold uppercase tracking-wide" style="color: var(--ink-1);">
              {{ t('admin.evolution.reportTitle') }}
            </h3>
            <span
              class="text-[11px] px-2 py-0.5 rounded border font-bold"
              :class="evolutionReport.change_status === 'EVOLVED' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' : 'text-amber-400 bg-amber-500/10 border-amber-500/30'"
            >
              {{ evolutionReport.change_status || 'NO_CHANGE' }}
            </span>
          </div>
          <div class="text-[11px]" style="color: var(--ink-2);">
            {{ t('admin.evolution.reviewTime') }} <strong class="text-emerald-400 font-bold">{{ fmtDateTime(evolutionReport.timestamp) }}</strong>
          </div>
        </div>

        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
          <div class="p-2 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.evolution.sampleCount') }}</div>
            <div class="font-bold text-sm mt-0.5" style="color: var(--ink-1);">{{ t('admin.evolution.closedTrades', undefined, { n: evolutionReport.total_trades }) }}</div>
          </div>
          <div class="p-2 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.evolution.winRate') }}</div>
            <div class="font-bold text-sm mt-0.5 text-emerald-400">{{ evolutionReport.win_rate }}%</div>
          </div>
          <div class="p-2 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.evolution.profitFactor') }}</div>
            <div class="font-bold text-sm mt-0.5 text-blue-400">{{ evolutionReport.profit_factor }}</div>
          </div>
          <div class="p-2 rounded-lg border" style="background-color: var(--surface-1); border-color: var(--line-1);">
            <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.evolution.memoryGuard') }}</div>
            <div class="font-bold text-sm mt-0.5 text-purple-400">{{ evolutionReport.memory_preserved ? t('admin.evolution.guardOn') : t('admin.evolution.guardRebuild') }}</div>
          </div>
        </div>

        <div v-if="evolutionReport.memory_overwrites_reason" class="p-2.5 rounded-lg border text-xs" style="background-color: var(--surface-1); border-color: var(--line-1);">
          <div class="text-[11px] uppercase font-bold text-amber-400 mb-0.5">{{ t('admin.evolution.verdictReason') }}</div>
          <p class="text-[11px] leading-relaxed" style="color: var(--ink-2);">{{ evolutionReport.memory_overwrites_reason }}</p>
        </div>

        <div v-if="evolutionReport.insights && evolutionReport.insights.length" class="space-y-1">
          <div class="text-[11px] font-bold uppercase" style="color: var(--ink-3);">{{ t('admin.evolution.insightsTitle', undefined, { n: evolutionReport.insights.length }) }}</div>
          <div class="space-y-1 max-h-[160px] overflow-y-auto pr-1">
            <div v-for="(ins, idx) in evolutionReport.insights" :key="idx" class="p-2 rounded border text-[11px] leading-relaxed" style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);">
              <span class="text-indigo-400 font-bold mr-1">#{{ Number(idx) + 1 }}</span>
              <span>{{ ins }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Strategy & Schedule Overview -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-bold" style="color: var(--ink-2);">
            <ShieldCheck class="w-3.5 h-3.5 text-emerald-400" />
            <span>{{ t('admin.evolution.guardrailStatus') }}</span>
          </div>
          <div
            class="text-sm font-bold"
            :style="{ color: memoryStructured === false ? 'var(--warn)' : memoryStructured === true ? 'var(--up, #34d399)' : 'var(--ink-3)' }"
          >
            {{ memoryStructured === true ? t('admin.evolution.guardrailActive')
              : memoryStructured === false ? t('admin.evolution.guardrailLegacy')
              : t('admin.evolution.unknown') }}
          </div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">
            {{ memoryStructured === true ? t('admin.evolution.guardrailSub') : t('admin.evolution.guardrailSubLegacy') }}
          </div>
        </div>

        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-bold" style="color: var(--ink-2);">
            <Clock class="w-3.5 h-3.5 text-cyan-400" />
            <span>{{ t('admin.evolution.cadence') }}</span>
          </div>
          <div class="text-sm font-bold text-cyan-400">{{ t('admin.evolution.cadenceValue') }}</div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">
            02:00, 08:00, 14:00, 20:00 (UTC+8)
          </div>
        </div>

        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-bold" style="color: var(--ink-2);">
            <Sliders class="w-3.5 h-3.5 text-purple-400" />
            <span>{{ t('admin.evolution.currentLessons') }}</span>
          </div>
          <div class="text-sm font-bold" style="color: var(--ink-1);">
            {{ t('admin.evolution.lessonsCount', undefined, { enabled: structuredLessons.filter((l: any) => l.enabled).length, total: structuredLessons.length }) }}
          </div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">
            {{ t('admin.evolution.lessonsSub') }}
          </div>
        </div>

        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--surface-2); border-color: var(--line-1);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-bold" style="color: var(--ink-2);">
            <Sparkles class="w-3.5 h-3.5 text-amber-400" />
            <span>{{ t('admin.evolution.halfLife') }}</span>
          </div>
          <div class="text-sm font-bold text-amber-400">{{ t('admin.evolution.halfLifeValue') }}</div>
          <div class="text-[11px] mt-1" style="color: var(--ink-3);">
            {{ t('admin.evolution.halfLifeSub') }}
          </div>
        </div>
      </div>

      <!-- Structured White-Box Memory Management -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b" style="border-color: var(--line-1);">
          <div class="flex items-center space-x-2">
            <Brain class="w-4 h-4 text-emerald-400" />
            <h2 class="text-xs font-semibold" style="color: var(--ink-1);">
              {{ t('admin.evolution.lifecycle') }}
            </h2>
          </div>
          <span class="text-[11px]" style="color: var(--ink-3);">
            {{ t('admin.evolution.lifecycleHint') }}
          </span>
        </div>

        <!-- Add Rule -->
        <div class="flex flex-col sm:flex-row gap-2 mb-4">
          <input
            v-model="newMemoryText"
            @keydown.enter="addMemoryItem"
            :placeholder="t('admin.evolution.addPlaceholder')"
            class="flex-1 rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
            style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);"
          />
          <button
            @click="addMemoryItem"
            :disabled="busy !== '' || !newMemoryText.trim()"
            class="flex items-center justify-center space-x-1 px-4 py-2 rounded-lg text-xs font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs shrink-0"
            style="background-color: var(--accent); color: var(--accent-ink);"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>{{ busy === 'add' ? t('admin.evolution.auditing') : t('admin.evolution.submitReview') }}</span>
          </button>
        </div>

        <!-- Structured Lessons Cards Grid -->
        <div class="space-y-2.5">
          <div v-if="loading" class="py-8 text-center text-xs" style="color: var(--ink-2);">
            <RefreshCw class="w-4 h-4 animate-spin inline mr-1.5" style="color: var(--accent);" />
            {{ t('admin.evolution.loadingLibrary') }}
          </div>
          <template v-else-if="structuredLessons.length">
            <div
              v-for="(item, idx) in structuredLessons"
              :key="item.id || idx"
              class="p-3.5 rounded-xl border transition-all flex flex-col justify-between gap-2.5"
              :style="{
                backgroundColor: item.enabled ? 'var(--surface-1)' : 'rgba(255, 255, 255, 0.01)',
                borderColor: item.enabled ? 'var(--line-1)' : 'rgba(255, 255, 255, 0.05)',
                opacity: item.enabled ? 1 : 0.6
              }"
            >
              <!-- Card Header Row -->
              <div class="flex items-center justify-between gap-2 text-xs">
                <div class="flex items-center space-x-1.5">
                  <span
                    class="px-1.5 py-0.5 rounded-[3px] text-[11px] font-bold border"
                    :style="{
                      backgroundColor: item.is_baseline ? 'rgba(56, 117, 246, 0.12)' : 'rgba(16, 185, 129, 0.12)',
                      borderColor: item.is_baseline ? 'rgba(56, 117, 246, 0.3)' : 'rgba(16, 185, 129, 0.3)',
                      color: item.is_baseline ? 'var(--info)' : 'var(--up)'
                    }"
                  >
                    {{ item.is_baseline ? t('admin.evolution.baselineBadge') : t('admin.evolution.aiBadge') }}
                  </span>

                  <span class="text-[11px] px-1.5 py-0.5 rounded-[3px] border" style="background-color: var(--surface-3); border-color: var(--line-1); color: var(--ink-2);">
                    {{ item.category }}
                  </span>

                  <span class="text-[11px] px-1.5 py-0.5 rounded-[3px] border bg-emerald-500/10 border-emerald-500/25 text-emerald-400 font-bold">
                    {{ t('admin.evolution.score') }} {{ item.health_score }}
                  </span>
                </div>

                <!-- Action Controls -->
                <div class="flex items-center space-x-2">
                  <!-- Toggle Switch -->
                  <button
                    @click="toggleLessonStatus(item.id)"
                    class="flex items-center space-x-1 px-2.5 py-1 rounded-md border text-[11px] font-bold cursor-pointer transition-colors"
                    :style="item.enabled ? {
                      backgroundColor: 'rgba(16, 185, 129, 0.15)',
                      borderColor: 'rgba(16, 185, 129, 0.3)',
                      color: 'var(--up)',
                    } : {
                      backgroundColor: 'var(--surface-2)',
                      borderColor: 'var(--line-1)',
                      color: 'var(--ink-3)',
                    }"
                    :title="item.enabled ? t('admin.evolution.disableTitle') : t('admin.evolution.enableTitle')"
                  >
                    <ToggleRight v-if="item.enabled" class="w-3.5 h-3.5" />
                    <ToggleLeft v-else class="w-3.5 h-3.5" />
                    <span>{{ item.enabled ? t('admin.evolution.statusOn') : t('admin.evolution.statusOff') }}</span>
                  </button>

                  <!-- Delete -->
                  <button
                    @click="deleteMemoryItem(idx, item.id)"
                    class="p-1 rounded hover:bg-rose-500/20 text-rose-400 opacity-60 hover:opacity-100 transition-opacity cursor-pointer"
                    :title="t('admin.evolution.removeTitle')"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              <!-- Rule Text -->
              <p
                class="text-xs leading-relaxed select-text"
                :style="item.enabled ? { color: 'var(--ink-1)' } : { color: 'var(--ink-3)', textDecoration: 'line-through' }"
              >
                {{ item.rule_text }}
              </p>

              <!-- Footer Audit Line -->
              <div class="flex items-center justify-between text-[11px] pt-1 border-t" style="border-color: var(--line-1); color: var(--ink-3);">
                <span>
                  {{ t('admin.evolution.createdAt') }} {{ fmtDateTime(item.created_at) }}
                  · {{ t('admin.evolution.sampleSupport') }}
                  {{ typeof item.sample_size === 'number' ? `${item.sample_size} ${t('admin.evolution.sampleUnit')}` : t('admin.evolution.unknown') }}
                </span>
                <span
                  class="flex items-center space-x-1"
                  :style="{ color: typeof item.shield_status === 'string' && item.shield_status ? 'var(--up, #34d399)' : 'var(--ink-3)' }"
                >
                  <ShieldCheck class="w-3 h-3" />
                  <span>{{ t('admin.evolution.shieldAudit') }} {{ typeof item.shield_status === 'string' && item.shield_status ? item.shield_status : t('admin.evolution.unknown') }}</span>
                </span>
              </div>
            </div>
          </template>
          <div v-else class="py-8 text-center text-xs border rounded-lg border-dashed" style="border-color: var(--line-1); color: var(--ink-3);">
            {{ t('admin.evolution.emptyLessons') }}
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2 & 3: Template Pipelines (Evolution System / User) -->
    <div v-else class="space-y-4">
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors space-y-4" style="background-color: var(--surface-2); border-color: var(--line-1);">
        <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--line-1);">
          <div>
            <h2 class="text-sm font-bold" style="color: var(--ink-1);">
              {{ activeTab === 'evolution_system' ? t('admin.evolution.systemTitle') : t('admin.evolution.userTitle') }}
            </h2>
            <p class="text-xs mt-0.5" style="color: var(--ink-2);">
              {{ activeTab === 'evolution_system' ? t('admin.evolution.systemDesc') : t('admin.evolution.userDesc') }}
            </p>
          </div>
          <button
            v-if="auth.isSuperadmin"
            @click="savePipelineModules"
            :disabled="busy !== ''"
            class="flex items-center space-x-1 px-4 py-2 rounded-lg text-xs font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs"
            style="background-color: var(--accent); color: var(--accent-ink);"
          >
            <Save class="w-3.5 h-3.5" />
            <span>{{ busy === 'save' ? t('admin.evolution.saving') : t('admin.evolution.saveTemplate') }}</span>
          </button>
        </div>

        <!-- Modules List -->
        <div class="space-y-3">
          <div
            v-for="(mod, mIdx) in workingModules"
            :key="mod.id || mIdx"
            class="border rounded-xl p-4 transition-all"
            style="background-color: var(--surface-1); border-color: var(--line-1);"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-bold" style="color: var(--ink-1);">{{ mod.title }}</span>
              <label class="flex items-center space-x-1.5 text-xs cursor-pointer">
                <input v-model="mod.enabled" type="checkbox" class="accent-blue-500 w-3.5 h-3.5" :disabled="!auth.isSuperadmin" />
                <span :class="mod.enabled ? 'text-emerald-500 font-bold' : 'text-zinc-500'">{{ mod.enabled ? t('admin.evolution.moduleOn') : t('admin.evolution.moduleOff') }}</span>
              </label>
            </div>
            <textarea
              v-model="mod.content"
              :disabled="!auth.isSuperadmin || mod.locked"
              rows="6"
              class="w-full rounded-lg p-3 text-xs leading-relaxed outline-none border transition-colors resize-y"
              style="background-color: var(--surface-input); border-color: var(--line-1); color: var(--ink-1);"
            ></textarea>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
