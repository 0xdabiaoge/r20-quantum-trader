<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {
  Brain,
  Sparkles,
  RefreshCw,
  Clock,
  Plus,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Save,
  PlayCircle,
  BookOpen,
  Sliders,
  Terminal,
} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const loading = ref(true)
const busy = ref<'save' | 'run' | 'add' | 'delete' | ''>('')
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' | 'warn' } | null>(null)

// Pipelines state (evolution_system & evolution_user)
const activeTab = ref<'settings' | 'evolution_system' | 'evolution_user'>('settings')
const lib = ref<any>(null)
const selectedProfileId = ref('stable')
const workingModules = ref<any[]>([])

// Memory items state
const memoryItems = ref<string[]>([])
const newMemoryText = ref('')

// Scheduler settings
const briefingTimes = ref<string[]>(['02:00', '08:00', '14:00', '20:00'])
const newTimeInput = ref('')

const selectedProfile = computed(() => (lib.value?.profiles || []).find((p: any) => p.id === selectedProfileId.value) || null)

async function loadData() {
  loading.value = true
  try {
    const [libRes, memRes] = await Promise.all([
      api('/api/v1/admin/prompt-library'),
      api('/api/v1/admin/memory'),
    ])
    lib.value = libRes
    selectedProfileId.value = libRes.active_profile_id || 'stable'
    memoryItems.value = memRes.items || []
    syncWorkingModules()
  } catch (e: any) {
    bannerMsg.value = { text: `加载失败: ${e.message}`, type: 'err' }
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

async function addMemoryItem() {
  const text = newMemoryText.value.trim()
  if (!text) return
  busy.value = 'add'
  bannerMsg.value = null
  try {
    const res = await api('/api/v1/admin/memory', {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
    memoryItems.value = res.items || []
    newMemoryText.value = ''
    bannerMsg.value = { text: '✅ 自进化实战心法已新增并同步写入大模型决策注入层', type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `添加心法失败: ${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

async function deleteMemoryItem(idx: number) {
  if (!confirm('确定删除此条自进化心法吗？删除后大模型推演将不再参考本条规则。')) return
  busy.value = 'delete'
  bannerMsg.value = null
  try {
    const res = await api(`/api/v1/admin/memory/${idx}`, {
      method: 'DELETE',
    })
    memoryItems.value = res.items || []
    bannerMsg.value = { text: '✅ 该条自进化心法已成功移除', type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `删除失败: ${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

async function savePipelineModules() {
  if (!selectedProfile.value) return
  busy.value = 'save'
  bannerMsg.value = null
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
    bannerMsg.value = { text: `✅ 自进化模版布局已成功保存，下一轮复盘自动生效`, type: 'ok' }
    await loadData()
  } catch (e: any) {
    bannerMsg.value = { text: `保存失败: ${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

async function triggerEvolutionNow() {
  const phrase = prompt('立即强制执行自进化复盘任务（对全天战绩穿透提炼并生成最新复盘心法），请输入确认短语：RUN EVOLUTION')
  if (!phrase) return
  if (phrase.trim().toUpperCase() !== 'RUN EVOLUTION') {
    alert('确认短语错误，已取消执行')
    return
  }
  busy.value = 'run'
  bannerMsg.value = null
  try {
    const res = await api('/api/v1/admin/gateway/jobs/self_improvement/run', {
      method: 'POST',
      body: JSON.stringify({ confirmation: 'RUN JOB' }),
    })
    bannerMsg.value = { text: `✅ 自进化复盘任务已启动并完成！${res.detail || ''}`, type: 'ok' }
    await loadData()
  } catch (e: any) {
    bannerMsg.value = { text: `执行复盘失败: ${e.message}`, type: 'err' }
  } finally {
    busy.value = ''
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-4 max-w-[2160px] mx-auto">
    <div class="flex items-center justify-between">
      <p class="text-xs font-mono" style="color: var(--text-muted);">配置 AI 交易自进化复盘调度、提炼规则、战绩证据注入与实战长期心法记忆库。</p>
      <span
        class="text-[10px] font-mono px-2 py-1 rounded border font-bold"
        style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
      >
        认知中枢 · 进化栈
      </span>
    </div>

    <!-- Banner -->
    <div
      v-if="bannerMsg"
      class="p-3 rounded-lg text-xs font-mono border"
      :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'"
    >
      <div class="flex items-center gap-2">
        <CheckCircle2 v-if="bannerMsg.type === 'ok'" class="w-4 h-4 shrink-0" />
        <AlertCircle v-else class="w-4 h-4 shrink-0" />
        <span>{{ bannerMsg.text }}</span>
      </div>
    </div>

    <!-- Navigation Tabs for Self-Improvement -->
    <div class="flex flex-wrap items-center justify-between gap-3 p-1.5 rounded-xl border" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
      <div class="flex flex-wrap gap-1">
        <button
          @click="switchTab('settings')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold cursor-pointer transition-colors"
          :style="activeTab === 'settings' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
        >
          <Brain class="w-3.5 h-3.5" />
          <span>心法记忆与调度概览</span>
        </button>
        <button
          @click="switchTab('evolution_system')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold cursor-pointer transition-colors"
          :style="activeTab === 'evolution_system' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
        >
          <BookOpen class="w-3.5 h-3.5" />
          <span>复盘官 System 模版</span>
        </button>
        <button
          @click="switchTab('evolution_user')"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-mono font-bold cursor-pointer transition-colors"
          :style="activeTab === 'evolution_user' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { color: 'var(--text-muted)' }"
        >
          <Terminal class="w-3.5 h-3.5" />
          <span>战绩流水 User 模版</span>
        </button>
      </div>

      <div class="flex items-center space-x-2">
        <button
          v-if="auth.isSuperadmin"
          @click="triggerEvolutionNow"
          :disabled="busy !== ''"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-mono font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs"
          style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
        >
          <PlayCircle class="w-3.5 h-3.5" />
          <span>{{ busy === 'run' ? '正在执行复盘提炼...' : '强制立即复盘' }}</span>
        </button>
      </div>
    </div>

    <!-- TAB 1: Settings & Heuristic Memory -->
    <div v-if="activeTab === 'settings'" class="space-y-4">
      <!-- Strategy & Schedule Overview -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-mono font-bold" style="color: var(--text-muted);">
            <Clock class="w-3.5 h-3.5 text-cyan-400" />
            <span>自动复盘频次</span>
          </div>
          <div class="text-sm font-bold font-mono text-emerald-400">每 6 小时 (4次/天)</div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            调度时间：02:00, 08:00, 14:00, 20:00 (UTC+8)
          </div>
        </div>

        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-mono font-bold" style="color: var(--text-muted);">
            <Sliders class="w-3.5 h-3.5 text-purple-400" />
            <span>复盘策略基准</span>
          </div>
          <div class="text-sm font-bold font-mono" style="color: var(--text-main);">全维度波段强化版</div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            顺势多空对称 · 宽止损抗噪 · 浮盈0.8R保本移损
          </div>
        </div>

        <div class="rounded-xl border p-3.5 shadow-xs" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
          <div class="flex items-center space-x-1.5 mb-1 text-[11px] font-mono font-bold" style="color: var(--text-muted);">
            <Sparkles class="w-3.5 h-3.5 text-amber-400" />
            <span>有效心法储备</span>
          </div>
          <div class="text-sm font-bold font-mono text-amber-400">{{ memoryItems.length }} 条实战准则</div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            每轮实时注入 AI 交易主脑 System Prompt
          </div>
        </div>
      </div>

      <!-- Heuristic Memory Management -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <Brain class="w-4 h-4 text-emerald-400" />
            <h2 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">AI 实战长期心法记忆库 (Heuristic Long-Term Memory)</h2>
          </div>
          <span class="text-[10px] font-mono" style="color: var(--text-faint);">
            每 6 小时自动增量提炼 · 支持管理员手动干预增删
          </span>
        </div>

        <!-- Add Rule -->
        <div class="flex flex-col sm:flex-row gap-2 mb-4">
          <input
            v-model="newMemoryText"
            @keydown.enter="addMemoryItem"
            placeholder="输入新提炼的实战心法（如：【顺势回踩确认】在 4H 多头通道中只挂回踩支撑多单，杜绝逆势摸顶...）"
            class="flex-1 rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
            style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
          />
          <button
            @click="addMemoryItem"
            :disabled="busy !== '' || !newMemoryText.trim()"
            class="flex items-center justify-center space-x-1 px-4 py-2 rounded-lg text-xs font-mono font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs shrink-0"
            style="background-color: var(--text-main); color: var(--bg-card);"
          >
            <Plus class="w-3.5 h-3.5" />
            <span>{{ busy === 'add' ? '添加中...' : '添加心法' }}</span>
          </button>
        </div>

        <!-- List -->
        <div class="space-y-2">
          <div v-if="loading" class="py-6 text-center text-xs font-mono" style="color: var(--text-muted);">
            <RefreshCw class="w-4 h-4 animate-spin inline mr-1.5" style="color: var(--color-brand);" />
            正在加载自进化心法...
          </div>
          <template v-else-if="memoryItems.length">
            <div
              v-for="(item, idx) in memoryItems"
              :key="idx"
              class="flex items-start justify-between gap-3 p-3 rounded-lg border transition-colors group"
              style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
            >
              <div class="flex items-start space-x-2.5 flex-1 min-w-0">
                <span class="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border shrink-0 mt-0.5" style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--color-brand);">#{{ idx + 1 }}</span>
                <p class="text-xs font-mono leading-relaxed select-text" style="color: var(--text-main);">{{ item }}</p>
              </div>
              <button
                @click="deleteMemoryItem(idx)"
                class="p-1 rounded hover:bg-rose-500/20 text-rose-400 opacity-60 group-hover:opacity-100 transition-opacity cursor-pointer shrink-0"
                title="删除此条心法"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </template>
          <div v-else class="py-8 text-center text-xs font-mono border rounded-lg border-dashed" style="border-color: var(--border-subtle); color: var(--text-faint);">
            暂无自进化心法记忆，可点击上方添加或等待下一轮定时复盘自动提炼
          </div>
        </div>
      </div>
    </div>

    <!-- TAB 2 & 3: Template Pipelines (Evolution System / User) -->
    <div v-else class="space-y-4">
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors space-y-4" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
        <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--border-subtle);">
          <div>
            <h2 class="text-sm font-bold font-mono" style="color: var(--text-main);">
              {{ activeTab === 'evolution_system' ? '自进化复盘官 System 提示词模版' : '自进化战绩流水 User 提示词模版' }}
            </h2>
            <p class="text-xs font-mono mt-0.5" style="color: var(--text-muted);">
              {{ activeTab === 'evolution_system' ? '定义复盘官的角色定位、归因逻辑与心法沉淀标准' : '配置每 6 小时自动组装实战对账单与动力学快照证据的模版语法' }}
            </p>
          </div>
          <button
            v-if="auth.isSuperadmin"
            @click="savePipelineModules"
            :disabled="busy !== ''"
            class="flex items-center space-x-1 px-4 py-2 rounded-lg text-xs font-mono font-bold cursor-pointer disabled:opacity-40 transition-all shadow-xs"
            style="background-color: var(--text-main); color: var(--bg-card);"
          >
            <Save class="w-3.5 h-3.5" />
            <span>{{ busy === 'save' ? '保存中...' : '保存模版' }}</span>
          </button>
        </div>

        <!-- Modules List -->
        <div class="space-y-3">
          <div
            v-for="(mod, mIdx) in workingModules"
            :key="mod.id || mIdx"
            class="border rounded-xl p-4 transition-all"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="text-xs font-bold font-mono" style="color: var(--text-main);">{{ mod.title }}</span>
              <label class="flex items-center space-x-1.5 text-xs font-mono cursor-pointer">
                <input v-model="mod.enabled" type="checkbox" class="accent-blue-500 w-3.5 h-3.5" :disabled="!auth.isSuperadmin" />
                <span :class="mod.enabled ? 'text-emerald-500 font-bold' : 'text-zinc-500'">{{ mod.enabled ? '启用模块' : '已停用' }}</span>
              </label>
            </div>
            <textarea
              v-model="mod.content"
              :disabled="!auth.isSuperadmin || mod.locked"
              rows="6"
              class="w-full rounded-lg p-3 text-xs font-mono leading-relaxed outline-none border transition-colors resize-y"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            ></textarea>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
