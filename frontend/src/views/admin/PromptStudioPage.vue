<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {
  FileText, Plus, ArrowUp, ArrowDown, Eye, CheckCircle2, Save,
  ToggleLeft, ToggleRight, History, RotateCcw, Trash2, Copy,
  Download, Upload, FileUp, Sparkles, X
} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const lib = ref<any>(null)
const loading = ref(true)
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' | 'warn' } | null>(null)

const selectedProfileId = ref<string>('')
const activePipeline = ref<'trading_system' | 'trading_user' | 'evolution_system' | 'evolution_user'>('trading_system')
const workingModules = ref<any[]>([])
const dirty = ref(false)
const historyVisible = ref(false)
const historyList = ref<any[]>([])

// Import Modal State
const importVisible = ref(false)
const importRawJson = ref('')
const importNameOverride = ref('')
const importFileError = ref('')

const pipelines = [
  { id: 'trading_system', label: '交易 System', desc: '发给交易主脑的规则与决策纪律' },
  { id: 'trading_user', label: '交易 User', desc: '每轮拼装实时行情、动力学与决策任务' },
  { id: 'evolution_system', label: '自进化 System', desc: '复盘官规则与心法提炼' },
  { id: 'evolution_user', label: '自进化 User', desc: '每夜注入战绩与实战流水证据' },
] as const

const selectedProfile = computed(() => (lib.value?.profiles || []).find((p: any) => p.id === selectedProfileId.value) || null)
const compiledPreview = computed(() => {
  if (!selectedProfile.value?.pipeline_views) return lib.value?.effective_templates?.[activePipeline.value] || ''
  return compileLocal()
})

function compileLocal(): string {
  return workingModules.value
    .filter((m) => m.enabled && String(m.content || '').trim())
    .map((m) => String(m.content).trim())
    .join('\n\n')
}

async function loadLib() {
  loading.value = true
  try {
    lib.value = await api('/api/v1/admin/prompt-library')
    if (!selectedProfileId.value || !(lib.value.profiles || []).some((p: any) => p.id === selectedProfileId.value)) {
      selectedProfileId.value = lib.value.active_profile_id || lib.value.profiles?.[0]?.id || ''
    }
    loadWorkingModules()
  } catch (e: any) {
    bannerMsg.value = { text: `加载失败：${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

function loadWorkingModules() {
  const views = selectedProfile.value?.pipeline_views?.[activePipeline.value] || []
  workingModules.value = JSON.parse(JSON.stringify(views)).map((m: any) => ({
    ...m,
    locked: false, // 全量解锁，支持自由修改
  }))
  dirty.value = false
}

function selectProfile(id: string) {
  if (dirty.value && !confirm('当前修改尚未保存，切换方案将丢失修改。继续？')) return
  selectedProfileId.value = id
  loadWorkingModules()
}

function switchPipeline(id: any) {
  if (dirty.value && !confirm('当前模块修改尚未保存，切换管线将丢失修改。继续？')) return
  activePipeline.value = id
  loadWorkingModules()
}

function moveModule(idx: number, dir: -1 | 1) {
  const target = idx + dir
  if (target < 0 || target >= workingModules.value.length) return
  const arr = workingModules.value
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
  dirty.value = true
}

function toggleModule(m: any) {
  m.enabled = !m.enabled
  dirty.value = true
}

async function saveProfile() {
  try {
    const pipelinesMap: Record<string, any[]> = {}
    for (const p of pipelines) {
      pipelinesMap[p.id] = p.id === activePipeline.value
        ? workingModules.value
        : JSON.parse(JSON.stringify(selectedProfile.value.pipeline_views?.[p.id] || [])).map((m: any) => ({ ...m, locked: false }))
    }
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: selectedProfile.value.name,
        description: selectedProfile.value.description || '',
        enabled: true,
        editor_mode: 'modules',
        pipelines: pipelinesMap,
      }),
    })
    bannerMsg.value = { text: `✅ 方案「${selectedProfile.value.name}」· ${pipelines.find(p => p.id === activePipeline.value)?.label} 模块布局已保存，下一轮推演自动生效`, type: 'ok' }
    dirty.value = false
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `保存失败：${e.message}`, type: 'err' }
  }
}

async function activateProfile() {
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/activate`, { method: 'POST', body: '{}' })
    bannerMsg.value = { text: `已激活方案「${selectedProfile.value?.name}」`, type: 'ok' }
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `激活失败：${e.message}`, type: 'err' }
  }
}

async function duplicateProfile() {
  const name = prompt('新方案名称：', `${selectedProfile.value?.name || ''} 副本`)
  if (!name) return
  try {
    const res = await api('/api/v1/admin/prompt-profiles', {
      method: 'POST',
      body: JSON.stringify({ name, description: '', source_id: selectedProfileId.value }),
    })
    bannerMsg.value = { text: `已复制为可编辑方案「${res.profile.name}」`, type: 'ok' }
    selectedProfileId.value = res.profile.id
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `复制失败：${e.message}`, type: 'err' }
  }
}

async function createProfile() {
  const name = prompt('新方案名称：', '我的策略')
  if (!name) return
  try {
    const res = await api('/api/v1/admin/prompt-profiles', {
      method: 'POST',
      body: JSON.stringify({ name, description: '', source_id: 'stable' }),
    })
    bannerMsg.value = { text: `已创建可编辑方案「${res.profile.name}」，现在可以自由增删改模块`, type: 'ok' }
    selectedProfileId.value = res.profile.id
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `创建失败：${e.message}`, type: 'err' }
  }
}

function addModule() {
  workingModules.value.push({
    id: `module-${Date.now().toString(36)}`,
    title: `自定义规则模块 ${workingModules.value.length + 1}`,
    content: '',
    enabled: true,
    locked: false,
    source: 'custom',
  })
  dirty.value = true
}

function removeModule(idx: number) {
  if (!confirm('确定删除该模块？')) return
  workingModules.value.splice(idx, 1)
  dirty.value = true
}

function duplicateModule(idx: number) {
  const m = workingModules.value[idx]
  if (!m) return
  workingModules.value.splice(idx + 1, 0, {
    ...JSON.parse(JSON.stringify(m)),
    id: `module-${Date.now().toString(36)}`,
    title: `${m.title} 副本`,
    locked: false,
    source: 'custom'
  })
  dirty.value = true
}

async function deleteProfile() {
  if (!confirm(`确定删除方案「${selectedProfile.value?.name}」？`)) return
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}`, { method: 'DELETE' })
    selectedProfileId.value = ''
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `删除失败：${e.message}`, type: 'err' }
  }
}

async function showHistory() {
  historyVisible.value = true
  try {
    const res = await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/history`)
    historyList.value = res.history || []
  } catch (e: any) {
    bannerMsg.value = { text: `历史加载失败：${e.message}`, type: 'err' }
  }
}

async function rollback(revId: string) {
  if (!confirm('回滚将覆盖当前方案内容，确定？')) return
  try {
    await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ revision_id: revId }),
    })
    bannerMsg.value = { text: '已回滚到所选历史版本', type: 'ok' }
    historyVisible.value = false
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `回滚失败：${e.message}`, type: 'err' }
  }
}

// 导出策略方案为 JSON
async function exportProfile() {
  if (!selectedProfileId.value) return
  try {
    const res = await api(`/api/v1/admin/prompt-profiles/${encodeURIComponent(selectedProfileId.value)}/export`)
    const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `r20-strategy-${selectedProfile.value?.name || 'profile'}-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    bannerMsg.value = { text: `✅ 方案「${selectedProfile.value?.name}」已成功导出为 JSON 策略包`, type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `导出失败：${e.message}`, type: 'err' }
  }
}

// 处理导入文件选择
function handleFileSelect(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const text = e.target?.result as string
      JSON.parse(text) // Validate JSON
      importRawJson.value = text
      importFileError.value = ''
      if (!importNameOverride.value && file.name) {
        importNameOverride.value = file.name.replace(/\.json$/i, '').replace(/^r20-strategy-/, '')
      }
    } catch {
      importFileError.value = '文件内容不是合法的 JSON 格式'
    }
  }
  reader.readAsText(file)
}

// 提交导入
async function submitImport() {
  importFileError.value = ''
  if (!importRawJson.value.trim()) {
    importFileError.value = '请先选择 JSON 策略文件或粘贴 JSON 内容'
    return
  }
  try {
    const payload = JSON.parse(importRawJson.value.trim())
    const res = await api('/api/v1/admin/prompt-profiles/import', {
      method: 'POST',
      body: JSON.stringify({
        payload,
        name_override: importNameOverride.value.trim() || undefined,
      }),
    })
    bannerMsg.value = { text: `🎉 成功导入策略方案「${res.profile.name}」！`, type: 'ok' }
    importVisible.value = false
    importRawJson.value = ''
    importNameOverride.value = ''
    selectedProfileId.value = res.profile.id
    await loadLib()
  } catch (e: any) {
    importFileError.value = `导入失败：${e.message}`
  }
}

function copyPreview() {
  navigator.clipboard.writeText(compiledPreview.value)
  bannerMsg.value = { text: '编译后实发 Prompt 已复制', type: 'ok' }
}

onMounted(loadLib)
</script>

<template>
  <div class="space-y-4 font-mono text-xs">
    <!-- Header Summary & Plaza Gateway -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center space-x-2">
        <Sparkles class="w-4 h-4 text-blue-400" />
        <p class="text-xs text-[#8A99AD] font-sans">
          四条消息管线自由编排，所有提示词 100% 解除锁死。支持导出/导入，全面无缝对接后续「策略广场」。
        </p>
      </div>
      <div class="flex items-center space-x-2">
        <button
          @click="importVisible = true"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1a2b42] border border-[#23354d] text-blue-400 hover:text-blue-300 font-bold transition-all cursor-pointer shadow-sm"
          title="从本地文件或文本导入策略方案"
        >
          <Upload class="w-3.5 h-3.5" />
          <span>导入策略方案</span>
        </button>
        <button
          @click="exportProfile"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1a2b42] border border-[#23354d] text-[#b8c4d4] hover:text-white font-bold transition-all cursor-pointer shadow-sm"
          title="将当前方案导出为 JSON 策略包"
        >
          <Download class="w-3.5 h-3.5" />
          <span>导出当前策略</span>
        </button>
        <span class="text-[10px] text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">
          策略中心 · 自由编排
        </span>
      </div>
    </div>

    <!-- Alert / Banner Message -->
    <div
      v-if="bannerMsg"
      class="p-3 rounded-lg text-xs font-mono border transition-all"
      :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : bannerMsg.type === 'warn' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'"
    >
      {{ bannerMsg.text }}
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="py-12 text-center text-xs text-[#707E94]">正在加载提示词策略库...</div>

    <!-- Main Workspace Grid -->
    <div v-else-if="lib" class="grid grid-cols-1 xl:grid-cols-[250px_minmax(0,1fr)_390px] gap-4">
      <!-- Left: Profile List -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-3 space-y-2.5 h-fit shadow-lg">
        <div class="flex items-center justify-between px-1 pb-2 border-b border-[#1A2232]">
          <span class="text-[10px] font-bold text-[#8A99AD] uppercase tracking-wider">策略方案列表</span>
          <button
            v-if="auth.isSuperadmin"
            @click="createProfile"
            class="flex items-center space-x-1 px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-[10px] text-white cursor-pointer shadow-sm"
          >
            <Plus class="w-3 h-3" />
            <span>新建方案</span>
          </button>
        </div>
        <div class="space-y-1.5 max-h-[620px] overflow-y-auto pr-0.5">
          <button
            v-for="p in lib.profiles"
            :key="p.id"
            @click="selectProfile(p.id)"
            class="w-full text-left p-3 rounded-xl border transition-all cursor-pointer group"
            :class="selectedProfileId === p.id ? 'border-blue-500/60 bg-blue-500/10 shadow-md shadow-blue-500/5' : 'border-[#1A2232] bg-[#080B10] hover:border-[#2D3748] hover:bg-[#0c1018]'"
          >
            <div class="flex items-center justify-between">
              <span class="text-xs font-bold text-white group-hover:text-blue-300 transition-colors">{{ p.name }}</span>
              <span v-if="p.id === lib.active_profile_id" class="text-[9px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20 font-bold">
                当前生效
              </span>
            </div>
            <div class="text-[10px] text-[#707E94] mt-1 line-clamp-1">
              {{ p.description || '无详细描述' }}
            </div>
          </button>
        </div>
      </div>

      <!-- Center: Modules Editor (100% Unlocked) -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 sm:p-5 min-w-0 shadow-lg space-y-3.5">
        <!-- Pipeline Navigation Tabs -->
        <div class="flex space-x-1.5 border-b border-[#1A2232] pb-1 overflow-x-auto">
          <button
            v-for="p in pipelines"
            :key="p.id"
            @click="switchPipeline(p.id)"
            class="px-3.5 py-2 text-xs font-bold border-b-2 whitespace-nowrap cursor-pointer transition-all"
            :class="activePipeline === p.id ? 'border-blue-400 text-white bg-[#141B26] rounded-t-lg' : 'border-transparent text-[#707E94] hover:text-zinc-200'"
          >
            {{ p.label }}
          </button>
        </div>
        <div class="flex items-center justify-between text-[11px] text-[#707E94] bg-[#0A0D14] px-3 py-2 rounded-lg border border-[#1A2232]">
          <span>{{ pipelines.find(p => p.id === activePipeline)?.desc }}</span>
          <span class="text-zinc-300 font-bold">当前编辑方案：{{ selectedProfile?.name }}</span>
        </div>

        <!-- Module Cards List -->
        <div class="space-y-3 max-h-[580px] overflow-y-auto pr-1">
          <div
            v-for="(m, idx) in workingModules"
            :key="m.id"
            class="border rounded-xl p-3.5 transition-all"
            :class="m.enabled ? 'border-[#273246] bg-[#0A0F18]' : 'border-[#1A2232] bg-[#080B10] opacity-45'"
          >
            <div class="flex items-center justify-between mb-2 gap-2">
              <!-- Title & Ordering -->
              <div class="flex items-center space-x-2 min-w-0 flex-1">
                <button
                  @click="moveModule(idx, -1)"
                  :disabled="idx === 0"
                  class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] hover:text-white disabled:opacity-20 cursor-pointer"
                  title="上移"
                >
                  <ArrowUp class="w-3.5 h-3.5" />
                </button>
                <button
                  @click="moveModule(idx, 1)"
                  :disabled="idx === workingModules.length - 1"
                  class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] hover:text-white disabled:opacity-20 cursor-pointer"
                  title="下移"
                >
                  <ArrowDown class="w-3.5 h-3.5" />
                </button>
                <input
                  v-model="m.title"
                  class="bg-transparent border-b border-transparent focus:border-blue-500 text-xs font-bold text-white font-mono outline-none flex-1 min-w-[120px] transition-colors"
                  placeholder="模块标题"
                  @input="dirty = true"
                />
                <span class="px-1.5 py-0.5 rounded text-[9px] font-bold bg-[#141B26] text-blue-300 border border-blue-500/20 shrink-0">
                  可自由定制
                </span>
              </div>

              <!-- Controls: Copy, Delete, Toggle -->
              <div class="flex items-center space-x-1.5 shrink-0">
                <button
                  @click="duplicateModule(idx)"
                  class="p-1.5 rounded-lg hover:bg-[#151D2C] text-[#707E94] hover:text-white cursor-pointer"
                  title="复制模块"
                >
                  <Copy class="w-3.5 h-3.5" />
                </button>
                <button
                  @click="removeModule(idx)"
                  class="p-1.5 rounded-lg hover:bg-[#4d1924] text-[#707E94] hover:text-rose-400 cursor-pointer"
                  title="删除模块"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
                <button
                  @click="toggleModule(m)"
                  class="cursor-pointer transition-colors"
                  :class="m.enabled ? 'text-emerald-400' : 'text-[#707E94]'"
                  :title="m.enabled ? '已启用该模块 (点击禁用)' : '已禁用该模块 (点击启用)'"
                >
                  <ToggleRight v-if="m.enabled" class="w-5 h-5" />
                  <ToggleLeft v-else class="w-5 h-5" />
                </button>
              </div>
            </div>

            <!-- Content Area (100% Editable) -->
            <textarea
              v-model="m.content"
              rows="3"
              class="w-full bg-[#080B10] border border-[#1A2232] rounded-lg text-zinc-200 px-3 py-2 text-xs outline-none focus:border-blue-500 resize-y leading-relaxed transition-colors"
              placeholder="编写该模块的提示词指令..."
              @input="dirty = true"
            ></textarea>
          </div>

          <!-- Add Module Button -->
          <button
            @click="addModule"
            class="w-full py-2.5 rounded-xl border border-dashed border-[#2D3748] text-xs text-[#8A99AD] hover:text-white hover:border-blue-500/60 bg-[#0A0D14]/40 hover:bg-[#0E1420] cursor-pointer flex items-center justify-center space-x-1.5 transition-all"
          >
            <Plus class="w-4 h-4 text-blue-400" />
            <span>新增自定义规则模块</span>
          </button>
        </div>

        <!-- Action Bar -->
        <div class="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-[#1A2232]">
          <div class="flex flex-wrap items-center gap-2">
            <button
              @click="saveProfile"
              :disabled="!dirty"
              class="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold cursor-pointer disabled:opacity-40 transition-all shadow-md shadow-blue-600/20"
            >
              <Save class="w-4 h-4" />
              <span>保存当前方案{{ dirty ? ' *' : '' }}</span>
            </button>
            <button
              v-if="selectedProfileId !== lib.active_profile_id && auth.isSuperadmin"
              @click="activateProfile"
              class="flex items-center space-x-1.5 px-3.5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold cursor-pointer transition-all shadow-md shadow-emerald-600/20"
            >
              <CheckCircle2 class="w-4 h-4" />
              <span>激活为实盘方案</span>
            </button>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button
              v-if="auth.isSuperadmin"
              @click="duplicateProfile"
              class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-[#b8c4d4] hover:text-white cursor-pointer transition-all"
            >
              <Copy class="w-3.5 h-3.5" />
              <span>复制副本</span>
            </button>
            <button
              @click="showHistory"
              class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-[#b8c4d4] hover:text-white cursor-pointer transition-all"
            >
              <History class="w-3.5 h-3.5" />
              <span>历史版本</span>
            </button>
            <button
              v-if="selectedProfileId !== lib.active_profile_id && auth.isSuperadmin"
              @click="deleteProfile"
              class="flex items-center space-x-1 px-3 py-2 rounded-lg bg-[#4d1924] hover:bg-[#5d2230] border border-[#873044] text-[#ffdce1] cursor-pointer transition-all"
            >
              <Trash2 class="w-3.5 h-3.5" />
              <span>删除</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Right: Compiled Live Preview -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 sm:p-5 h-fit shadow-lg space-y-3">
        <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <Eye class="w-4 h-4 text-cyan-400" />
            <h3 class="text-xs font-bold text-white uppercase tracking-wider">实发 Prompt 原文对照</h3>
          </div>
          <button
            @click="copyPreview"
            class="px-2.5 py-1 rounded-lg bg-[#111c2a] border border-[#33445b] text-[10px] text-[#b8c4d4] hover:text-white cursor-pointer hover:bg-[#1d3050] transition-colors"
          >
            复制全文
          </button>
        </div>
        <pre class="bg-[#080B10] border border-[#1A2232] rounded-xl p-3.5 text-[11px] text-zinc-300 whitespace-pre-wrap leading-relaxed max-h-[640px] overflow-y-auto select-text">{{ compiledPreview || '（空）' }}</pre>
      </div>
    </div>

    <!-- Import Modal (File & Raw JSON Support for Strategy Plaza) -->
    <div
      v-if="importVisible"
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      @click.self="importVisible = false"
    >
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-2xl p-5 sm:p-6 w-full max-w-xl max-h-[90dvh] overflow-y-auto space-y-4 shadow-2xl">
        <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2.5">
            <div class="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center">
              <Upload class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-white">导入策略方案包</h3>
              <p class="text-[10px] text-[#707E94]">支持导入从本系统导出或从策略广场获取的 .json 策略方案</p>
            </div>
          </div>
          <button @click="importVisible = false" class="text-[#707E94] hover:text-white cursor-pointer p-1">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div v-if="importFileError" class="p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400">
          {{ importFileError }}
        </div>

        <!-- Mode 1: File Upload -->
        <div>
          <label class="block text-xs font-bold text-zinc-300 mb-1.5">方式一：选择本地 .json 策略文件</label>
          <div class="flex items-center space-x-3">
            <label class="flex items-center space-x-2 px-3 py-2 rounded-xl bg-[#0E1420] border border-dashed border-[#2E3C52] hover:border-blue-500 text-xs text-blue-400 hover:text-blue-300 cursor-pointer transition-all">
              <FileUp class="w-4 h-4" />
              <span>选择策略文件 (.json)</span>
              <input type="file" accept=".json" class="hidden" @change="handleFileSelect" />
            </label>
          </div>
        </div>

        <!-- Mode 2: Paste JSON -->
        <div>
          <label class="block text-xs font-bold text-zinc-300 mb-1.5">方式二：或直接粘贴策略 JSON 文本</label>
          <textarea
            v-model="importRawJson"
            rows="6"
            class="w-full bg-[#080B10] border border-[#1A2232] rounded-xl text-zinc-200 px-3 py-2 text-xs outline-none focus:border-blue-500 resize-y font-mono"
            placeholder='{"format": "r20-prompt-profile", "version": 3, "profile": { ... }}'
          ></textarea>
        </div>

        <!-- Optional Name Override -->
        <div>
          <label class="block text-xs font-bold text-zinc-300 mb-1.5">自定义导入方案名称（可选）</label>
          <input
            v-model="importNameOverride"
            type="text"
            class="w-full bg-[#080B10] border border-[#1A2232] rounded-xl text-white px-3 py-2 text-xs outline-none focus:border-blue-500"
            placeholder="留空则自动采用策略包内部的原始名称"
          />
        </div>

        <!-- Modal Actions -->
        <div class="flex items-center justify-end space-x-2 pt-3 border-t border-[#1A2232]">
          <button
            @click="importVisible = false"
            class="px-4 py-2 rounded-xl bg-[#141B26] hover:bg-[#1e2738] text-zinc-300 text-xs cursor-pointer"
          >
            取消
          </button>
          <button
            @click="submitImport"
            class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs cursor-pointer transition-all shadow-md shadow-blue-500/20"
          >
            确认导入并载入方案
          </button>
        </div>
      </div>
    </div>

    <!-- History Modal -->
    <div
      v-if="historyVisible"
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      @click.self="historyVisible = false"
    >
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-2xl p-5 sm:p-6 w-full max-w-[560px] max-h-[85dvh] overflow-y-auto shadow-2xl">
        <div class="flex items-center justify-between mb-4 pb-3 border-b border-[#1A2232]">
          <h3 class="text-sm font-bold text-white">版本历史 · {{ selectedProfile?.name }}</h3>
          <button @click="historyVisible = false" class="text-[#707E94] hover:text-white cursor-pointer text-xs">
            <X class="w-4 h-4" />
          </button>
        </div>
        <div v-if="historyList.length === 0" class="text-xs text-[#707E94] py-8 text-center">暂无历史版本</div>
        <div
          v-for="h in historyList"
          :key="h.id || h.revision_id"
          class="flex items-center justify-between py-2.5 border-b border-[#1A2232]/60"
        >
          <div>
            <div class="text-xs text-white">{{ h.note || h.summary || h.id || h.revision_id }}</div>
            <div class="text-[10px] text-[#707E94]">{{ h.created_at || h.time }} · {{ h.actor || 'system' }}</div>
          </div>
          <button
            @click="rollback(h.id || h.revision_id)"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-[#111c2a] border border-[#33445b] text-[10px] text-[#b8c4d4] hover:text-white cursor-pointer hover:bg-[#1d3050] transition-colors"
          >
            <RotateCcw class="w-3 h-3" />
            <span>回滚</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
