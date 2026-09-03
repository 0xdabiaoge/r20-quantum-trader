<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import { FileText, Lock, Plus, ArrowUp, ArrowDown, Eye, CheckCircle2, Save, ToggleLeft, ToggleRight, History, RotateCcw, Trash2, Copy } from 'lucide-vue-next'

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

const pipelines = [
  { id: 'trading_system', label: '交易 System', desc: '发给交易主脑的不可见规则' },
  { id: 'trading_user', label: '交易 User', desc: '每轮拼装实时行情与决策任务' },
  { id: 'evolution_system', label: '自进化 System', desc: '复盘官规则与 JSON 契约' },
  { id: 'evolution_user', label: '自进化 User', desc: '每夜注入战绩与台账证据' },
] as const

const selectedProfile = computed(() => (lib.value?.profiles || []).find((p: any) => p.id === selectedProfileId.value) || null)
const isReadonly = computed(() => !selectedProfile.value?.editable)
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
  workingModules.value = JSON.parse(JSON.stringify(views))
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
  if (m.locked) return
  m.enabled = !m.enabled
  dirty.value = true
}

async function saveProfile() {
  if (!selectedProfile.value?.editable) return
  try {
    const pipelinesMap: Record<string, any[]> = {}
    // Keep other pipelines intact from server copy; overwrite active one with working set
    for (const p of pipelines) {
      pipelinesMap[p.id] = p.id === activePipeline.value
        ? workingModules.value
        : JSON.parse(JSON.stringify(selectedProfile.value.pipeline_views?.[p.id] || []))
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
    bannerMsg.value = { text: `已创建可编辑方案「${res.profile.name}」，现在可以新增模块`, type: 'ok' }
    selectedProfileId.value = res.profile.id
    await loadLib()
  } catch (e: any) {
    bannerMsg.value = { text: `创建失败：${e.message}`, type: 'err' }
  }
}

function addModule() {
  workingModules.value.push({
    id: `module-${Date.now().toString(36)}`,
    title: `自定义模块 ${workingModules.value.length + 1}`,
    content: '',
    enabled: true,
    locked: false,
    source: 'custom',
  })
  dirty.value = true
}

function removeModule(idx: number) {
  const m = workingModules.value[idx]
  if (!m || m.locked || m.source === 'base') return
  workingModules.value.splice(idx, 1)
  dirty.value = true
}

function duplicateModule(idx: number) {
  const m = workingModules.value[idx]
  if (!m) return
  workingModules.value.splice(idx + 1, 0, { ...JSON.parse(JSON.stringify(m)), id: `module-${Date.now().toString(36)}`, title: `${m.title} 副本`, locked: false, source: 'custom' })
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

function copyPreview() {
  navigator.clipboard.writeText(compiledPreview.value)
  bannerMsg.value = { text: '编译后实发 Prompt 已复制', type: 'ok' }
}

onMounted(loadLib)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">四条消息管线以可排序模块编译；内置方案只读，复制后可编辑。P0 安全规则锁定不可覆盖。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">策略配置 · 1/3</span>
    </div>

    <div v-if="bannerMsg" class="p-3 rounded-lg text-xs font-mono border" :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : bannerMsg.type === 'warn' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'">
      {{ bannerMsg.text }}
    </div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">正在加载提示词库...</div>

    <div v-else-if="lib" class="grid grid-cols-1 xl:grid-cols-[240px_minmax(0,1fr)_380px] gap-4">
      <!-- Left: Profile List -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-3 space-y-2 h-fit">
        <div class="flex items-center justify-between px-1">
          <span class="text-[10px] font-mono font-bold text-[#556677] uppercase">方案列表</span>
          <button v-if="auth.isSuperadmin" @click="createProfile" class="flex items-center space-x-1 px-2 py-0.5 rounded bg-blue-600/80 hover:bg-blue-500 text-[10px] font-mono text-white cursor-pointer"><Plus class="w-3 h-3" /><span>新建方案</span></button>
        </div>
        <button
          v-for="p in lib.profiles"
          :key="p.id"
          @click="selectProfile(p.id)"
          class="w-full text-left p-2.5 rounded-lg border transition-all cursor-pointer"
          :class="selectedProfileId === p.id ? 'border-blue-500/50 bg-blue-500/10' : 'border-[#1A2232] bg-[#080B10] hover:border-[#2D3748]'"
        >
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white font-mono">{{ p.name }}</span>
            <span v-if="p.id === lib.active_profile_id" class="text-[9px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.2 rounded border border-emerald-500/20">激活中</span>
          </div>
          <div class="text-[10px] text-[#707E94] mt-0.5 flex items-center gap-1">
            <Lock v-if="!p.editable" class="w-2.5 h-2.5" />
            <span>{{ p.editable ? '可编辑' : '内置只读' }}</span>
          </div>
        </button>
      </div>

      <!-- Center: Modules Editor -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 min-w-0">
        <!-- Pipeline Tabs -->
        <div class="flex space-x-1 border-b border-[#1A2232] mb-4 overflow-x-auto">
          <button
            v-for="p in pipelines"
            :key="p.id"
            @click="switchPipeline(p.id)"
            class="px-3 py-2 text-xs font-mono font-bold border-b-2 whitespace-nowrap cursor-pointer transition-all"
            :class="activePipeline === p.id ? 'border-blue-400 text-white' : 'border-transparent text-[#707E94] hover:text-zinc-300'"
          >
            {{ p.label }}
          </button>
        </div>
        <div class="text-[10px] text-[#707E94] font-mono mb-3">{{ pipelines.find(p => p.id === activePipeline)?.desc }} · 当前方案：{{ selectedProfile?.name }} {{ isReadonly ? '（只读，可点「复制为可编辑方案」修改）' : '' }}</div>

        <!-- Module Cards -->
        <div class="space-y-2 max-h-[560px] overflow-y-auto pr-1">
          <div
            v-for="(m, idx) in workingModules"
            :key="m.id"
            class="border rounded-lg p-3"
            :class="m.enabled ? 'border-[#273246] bg-[#0A0F18]' : 'border-[#1A2232] bg-[#080B10] opacity-50'"
          >
            <div class="flex items-center justify-between mb-2">
              <div class="flex items-center space-x-2 min-w-0">
                <button @click="moveModule(idx, -1)" :disabled="idx === 0 || isReadonly" class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] disabled:opacity-30 cursor-pointer"><ArrowUp class="w-3.5 h-3.5" /></button>
                <button @click="moveModule(idx, 1)" :disabled="idx === workingModules.length - 1 || isReadonly" class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] disabled:opacity-30 cursor-pointer"><ArrowDown class="w-3.5 h-3.5" /></button>
                <input
                  v-if="!isReadonly && m.source !== 'base' && !m.locked"
                  v-model="m.title"
                  class="bg-transparent border-b border-transparent focus:border-blue-500 text-xs font-bold text-white font-mono truncate max-w-[220px] outline-none"
                  @input="dirty = true"
                />
                <span v-else class="text-xs font-bold text-white font-mono truncate">【{{ m.title }}】</span>
                <span class="text-[9px] font-mono text-[#556677] shrink-0">{{ m.locked ? '🔒 安全/实时模块' : m.source === 'base' ? '✎ 可编辑基础规则' : '✎ 自定义模块' }}</span>
              </div>
              <div class="flex items-center space-x-1.5 shrink-0">
                <button v-if="!isReadonly && !m.locked && m.source !== 'base'" @click="duplicateModule(idx)" class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] cursor-pointer" title="复制模块"><Copy class="w-3.5 h-3.5" /></button>
                <button v-if="!isReadonly && !m.locked && m.source !== 'base'" @click="removeModule(idx)" class="p-1 rounded hover:bg-[#4d1924] text-[#707E94] hover:text-rose-400 cursor-pointer" title="删除模块"><Trash2 class="w-3.5 h-3.5" /></button>
                <button @click="toggleModule(m)" :disabled="m.locked || isReadonly" class="cursor-pointer disabled:opacity-40" :class="m.enabled ? 'text-emerald-400' : 'text-[#707E94]'">
                  <ToggleRight v-if="m.enabled" class="w-5 h-5" />
                  <ToggleLeft v-else class="w-5 h-5" />
                </button>
              </div>
            </div>
            <textarea
              v-model="m.content"
              :readonly="isReadonly || m.source === 'base' || m.locked"
              rows="3"
              class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-zinc-300 px-2.5 py-2 text-[11px] font-mono outline-none focus:border-blue-500 resize-y leading-relaxed"
              @input="dirty = true"
            ></textarea>
          </div>
          <button v-if="!isReadonly" @click="addModule" class="w-full py-2 rounded-lg border border-dashed border-[#2D3748] text-xs font-mono text-[#707E94] hover:text-white hover:border-blue-500/50 cursor-pointer flex items-center justify-center space-x-1"><Plus class="w-3.5 h-3.5" /><span>新增模块</span></button>
        </div>

        <!-- Actions -->
        <div class="flex flex-wrap items-center gap-2 mt-4 pt-3 border-t border-[#1A2232]">
          <button v-if="!isReadonly" @click="saveProfile" :disabled="!dirty" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer disabled:opacity-40"><Save class="w-3.5 h-3.5" /><span>保存方案{{ dirty ? ' *' : '' }}</span></button>
          <button v-if="selectedProfileId !== lib.active_profile_id && auth.isSuperadmin" @click="activateProfile" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold cursor-pointer"><CheckCircle2 class="w-3.5 h-3.5" /><span>激活此方案</span></button>
          <button v-if="auth.isSuperadmin" @click="duplicateProfile" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer"><Copy class="w-3.5 h-3.5" /><span>复制为可编辑方案</span></button>
          <button @click="showHistory" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer"><History class="w-3.5 h-3.5" /><span>版本历史</span></button>
          <button v-if="selectedProfile?.editable && selectedProfileId !== lib.active_profile_id && auth.isSuperadmin" @click="deleteProfile" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#4d1924] hover:bg-[#5d2230] border border-[#873044] text-xs font-mono text-[#ffdce1] cursor-pointer"><Trash2 class="w-3.5 h-3.5" /><span>删除</span></button>
        </div>
      </div>

      <!-- Right: Compiled Preview -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 h-fit">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <Eye class="w-4 h-4 text-cyan-400" />
            <h3 class="text-xs font-bold text-white font-mono uppercase">右侧实发 Prompt 对照</h3>
          </div>
          <button @click="copyPreview" class="px-2 py-1 rounded bg-[#111c2a] border border-[#33445b] text-[10px] font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">复制</button>
        </div>
        <pre class="bg-[#080B10] border border-[#1A2232] rounded-lg p-3 text-[10px] font-mono text-zinc-400 whitespace-pre-wrap leading-relaxed max-h-[640px] overflow-y-auto">{{ compiledPreview || '（空）' }}</pre>
      </div>
    </div>

    <!-- History Modal -->
    <div v-if="historyVisible" class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" @click.self="historyVisible = false">
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-5 w-full max-w-[560px] max-h-[85dvh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-bold text-white font-mono">版本历史 · {{ selectedProfile?.name }}</h3>
          <button @click="historyVisible = false" class="text-[#707E94] hover:text-white cursor-pointer text-xs font-mono">关闭</button>
        </div>
        <div v-if="historyList.length === 0" class="text-xs text-[#707E94] font-mono py-6 text-center">暂无历史版本</div>
        <div v-for="h in historyList" :key="h.id || h.revision_id" class="flex items-center justify-between py-2.5 border-b border-[#1A2232]/60">
          <div>
            <div class="text-xs text-white font-mono">{{ h.note || h.summary || h.id || h.revision_id }}</div>
            <div class="text-[10px] text-[#707E94]">{{ h.created_at || h.time }} · {{ h.actor || 'system' }}</div>
          </div>
          <button @click="rollback(h.id || h.revision_id)" class="flex items-center space-x-1 px-2 py-1 rounded bg-[#111c2a] border border-[#33445b] text-[10px] font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">
            <RotateCcw class="w-3 h-3" /><span>回滚</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
