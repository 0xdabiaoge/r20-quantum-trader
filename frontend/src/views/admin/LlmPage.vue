<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import {
  Cpu,
  Plus,
  Zap,
  Trash2,
  Pencil,
  CheckCircle2,
  AlertCircle,
  Server,
  RefreshCw,
  ExternalLink,
  Copy,
  Check,
  LayoutGrid,
  List,
  Flame,
  KeyRound,
  Network,
  DownloadCloud,
  Search,
  Globe,
  ChevronRight,
  ShieldCheck,
  Sparkles,
  Sliders,
} from 'lucide-vue-next'

const { api } = useApi()
const cfg = ref<any>(null)
const loading = ref(true)
const testResult = ref<any>(null)
const testLoading = ref(false)
const testingModelId = ref<string | null>(null)
const modalVisible = ref(false)
const editingModel = ref<any>(null)
const copiedId = ref<string | null>(null)
const viewMode = ref<'cards' | 'table'>('cards')

// Local search and filter
const searchQuery = ref('')
const selectedProviderFilter = ref('ALL')

// Provider Management Modal
const providerModalVisible = ref(false)
const editingProvider = ref<any>(null)
const providerForm = ref<any>({
  id: '',
  name: '',
  base_url: '',
  api_key: '',
  api_format: 'openai_chat',
  description: '',
})

// Remote Model Fetcher Drawer / Modal
const fetchModalVisible = ref(false)
const fetchProviderId = ref('openrouter')
const fetchBaseUrl = ref('')
const fetchApiKey = ref('')
const fetchingRemote = ref(false)
const remoteFetchResult = ref<any>(null)
const remoteSearch = ref('')
const remoteFilterCategory = ref('ALL')

// Add / Edit Model Form
const form = ref<any>({
  id: '',
  name: '',
  provider_id: 'custom',
  provider_name: '自定义网关/代理',
  api_format: 'openai_chat',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  reasoning_effort: 'high',
  description: '',
})

const defaultPresets = [
  { label: 'Gemini 3.8 Flash (生产推荐)', id: 'gemini-3.8-flash-high', name: 'Gemini 3.8 Flash (高思维链)', api_format: 'openai_chat', base_url: 'https://cpa.r20.cn/v1', provider: 'Google Gemini / CPA代理', provider_id: 'custom', effort: 'high', desc: '百万超长上下文，高深度长链推演，当前生产主力' },
  { label: 'Claude 3.7 Sonnet (Thinking)', id: 'claude-3-7-sonnet-20250219', name: 'Claude 3.7 Sonnet (Thinking CoT)', api_format: 'claude_messages', base_url: 'https://api.anthropic.com/v1', provider: 'Anthropic 官方', provider_id: 'anthropic', effort: 'high', desc: 'Anthropic 旗舰思维链模型，极高代码与波段因果推理决策胜率' },
  { label: 'OpenAI o3 顶级数理逻辑', id: 'o3', name: 'OpenAI o3 顶级数理推理', api_format: 'openai_responses', base_url: 'https://api.openai.com/v1', provider: 'OpenAI 官方', provider_id: 'openai', effort: 'high', desc: 'OpenAI 新一代数理逻辑顶峰，多阶微积分与因果推演旗舰' },
  { label: 'DeepSeek R1 满血推理 (671B)', id: 'deepseek-reasoner', name: 'DeepSeek R1 (满血推理)', api_format: 'openai_chat', base_url: 'https://api.deepseek.com/v1', provider: 'DeepSeek 官方', provider_id: 'deepseek', effort: 'high', desc: '开源强化学习推理架构，极高性价比与因果微结构穿透力' },
  { label: '通义千问 Qwen Max Latest', id: 'qwen-max-latest', name: '通义千问 Qwen Max Latest', api_format: 'openai_chat', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', provider: '阿里云百炼', provider_id: 'dashscope', effort: 'high', desc: '阿里百炼旗舰模型，超高中文金融理解与量化因子综合感知' },
  { label: 'OpenRouter 聚合旗舰', id: 'google/gemini-3.8-flash', name: 'OpenRouter: Gemini 3.8 Flash', api_format: 'openai_chat', base_url: 'https://openrouter.ai/api/v1', provider: 'OpenRouter 聚合', provider_id: 'openrouter', effort: 'high', desc: '通过 OpenRouter 接入，全球多节点智能容灾路由' },
  { label: 'OpenCode 旗舰直连', id: 'deepseek-ai/DeepSeek-V3', name: 'OpenCode: DeepSeek V3 旗舰', api_format: 'openai_chat', base_url: 'https://api.opencode.cn/v1', provider: 'OpenCode 平台', provider_id: 'opencode', effort: 'high', desc: '国内 AI 开放平台直连，聚合多厂商高并发旗舰' },
]

const flagshipPresets = computed(() => {
  return cfg.value?.flagship_presets?.length ? cfg.value.flagship_presets : defaultPresets
})

const filteredModels = computed(() => {
  if (!cfg.value?.models) return []
  let list = cfg.value.models
  if (selectedProviderFilter.value !== 'ALL') {
    list = list.filter((m: any) => (m.provider_id || 'custom') === selectedProviderFilter.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter((m: any) =>
      m.id.toLowerCase().includes(q) ||
      (m.name && m.name.toLowerCase().includes(q)) ||
      (m.provider_name && m.provider_name.toLowerCase().includes(q)) ||
      (m.base_url && m.base_url.toLowerCase().includes(q))
    )
  }
  return list
})

const filteredRemoteModels = computed(() => {
  if (!remoteFetchResult.value?.models) return []
  let list = remoteFetchResult.value.models
  if (remoteFilterCategory.value !== 'ALL') {
    if (remoteFilterCategory.value === 'reasoning') {
      list = list.filter((m: any) => m.reasoning_type !== 'none')
    } else if (remoteFilterCategory.value === 'flagship') {
      list = list.filter((m: any) => {
        const id = m.id.toLowerCase()
        return id.includes('gemini-3') || id.includes('claude-3') || id.includes('o3') || id.includes('o4') || id.includes('r1') || id.includes('qwen-max')
      })
    }
  }
  if (remoteSearch.value.trim()) {
    const q = remoteSearch.value.trim().toLowerCase()
    list = list.filter((m: any) =>
      m.id.toLowerCase().includes(q) ||
      (m.name && m.name.toLowerCase().includes(q)) ||
      (m.description && m.description.toLowerCase().includes(q))
    )
  }
  return list
})

function copyUrl(url: string, id: string) {
  navigator.clipboard.writeText(url)
  copiedId.value = id
  setTimeout(() => {
    copiedId.value = null
  }, 1800)
}

async function loadConfig() {
  loading.value = true
  try {
    cfg.value = await api('/api/v1/admin/llm/models')
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

// ----------------- Provider Management -----------------
function openProviderModal(p?: any) {
  if (p) {
    editingProvider.value = p
    providerForm.value = {
      id: p.id,
      name: p.name,
      base_url: p.base_url,
      api_key: '',
      api_format: p.api_format || 'openai_chat',
      description: p.description || '',
    }
  } else {
    editingProvider.value = null
    providerForm.value = {
      id: '',
      name: '',
      base_url: '',
      api_key: '',
      api_format: 'openai_chat',
      description: '',
    }
  }
  providerModalVisible.value = true
}

async function saveProvider() {
  try {
    const payload = { ...providerForm.value }
    if (!payload.api_key) delete payload.api_key
    await api('/api/v1/admin/llm/providers', { method: 'POST', body: JSON.stringify(payload) })
    providerModalVisible.value = false
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteProvider(pid: string) {
  if (!confirm(`确定删除供应商 ${pid}？该供应商下的模型仍将保留但需独立配置 Base URL。`)) return
  try {
    await api(`/api/v1/admin/llm/providers/${encodeURIComponent(pid)}`, { method: 'DELETE' })
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
  }
}

// ----------------- Remote Model Fetching -----------------
function openFetchModal(provId?: string) {
  if (provId) {
    fetchProviderId.value = provId
  }
  onFetchProviderChanged()
  fetchModalVisible.value = true
}

function onFetchProviderChanged() {
  const p = cfg.value?.providers?.find((x: any) => x.id === fetchProviderId.value)
  if (p) {
    fetchBaseUrl.value = p.base_url
    fetchApiKey.value = ''
  }
}

async function executeRemoteFetch() {
  fetchingRemote.value = true
  remoteFetchResult.value = null
  try {
    const payload: any = {
      provider_id: fetchProviderId.value,
      base_url: fetchBaseUrl.value,
    }
    if (fetchApiKey.value.trim()) {
      payload.api_key = fetchApiKey.value.trim()
    }
    const res = await api('/api/v1/admin/llm/fetch-models', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    remoteFetchResult.value = res
  } catch (e: any) {
    remoteFetchResult.value = { ok: false, error: e.message }
  } finally {
    fetchingRemote.value = false
  }
}

async function importRemoteModel(m: any, autoActivate = false) {
  try {
    const prov = cfg.value?.providers?.find((x: any) => x.id === fetchProviderId.value)
    const payload = {
      id: m.id,
      name: m.name || m.id,
      provider_id: fetchProviderId.value || 'custom',
      provider_name: prov?.name || '远程供应商',
      base_url: fetchBaseUrl.value || prov?.base_url,
      api_format: m.api_format || prov?.api_format || 'openai_chat',
      reasoning_type: m.reasoning_type || 'auto',
      reasoning_effort: m.default_effort || 'high',
      description: m.description ? m.description.slice(0, 100) : '从远端一键自动收录',
    }
    await api('/api/v1/admin/llm/models', { method: 'POST', body: JSON.stringify(payload) })
    if (autoActivate) {
      await api('/api/v1/admin/llm/activate', {
        method: 'POST',
        body: JSON.stringify({ model_id: m.id, reasoning_effort: payload.reasoning_effort }),
      })
    }
    await loadConfig()
    alert(autoActivate ? `已成功将 ${m.id} 收录并激活为主脑！` : `已成功将 ${m.id} 收录到模型库！`)
  } catch (e: any) {
    alert(e.message)
  }
}

// ----------------- Model Add / Edit / Activate -----------------
function openModal(m: any | null) {
  editingModel.value = m
  if (m) {
    form.value = {
      id: m.id,
      name: m.name,
      provider_id: m.provider_id || 'custom',
      provider_name: m.provider_name || '自定义',
      api_format: m.api_format || 'openai_chat',
      base_url: m.base_url,
      api_key: '',
      reasoning_effort: m.reasoning_effort || 'high',
      description: m.description,
    }
  } else {
    const defProv = cfg.value?.providers?.[0]
    form.value = {
      id: '',
      name: '',
      provider_id: defProv?.id || 'custom',
      provider_name: defProv?.name || '自定义网关/代理',
      api_format: defProv?.api_format || 'openai_chat',
      base_url: defProv?.base_url || 'https://api.openai.com/v1',
      api_key: '',
      reasoning_effort: 'high',
      description: '',
    }
  }
  modalVisible.value = true
}

function onModalProviderSelect(e: any) {
  const pid = e.target.value
  const p = cfg.value?.providers?.find((x: any) => x.id === pid)
  if (p) {
    form.value.provider_id = p.id
    form.value.provider_name = p.name
    form.value.base_url = p.base_url
    form.value.api_format = p.api_format || 'openai_chat'
  }
}

function applyPreset(p: any) {
  form.value.id = p.id
  form.value.name = p.name
  form.value.provider_id = p.provider_id || 'custom'
  form.value.provider_name = p.provider
  form.value.api_format = p.api_format
  form.value.base_url = p.base_url
  form.value.reasoning_effort = p.effort
  form.value.description = p.desc || ''
}

async function quickAddPreset(p: any) {
  try {
    const payload = {
      id: p.id,
      name: p.name,
      provider_id: p.provider_id || 'custom',
      provider_name: p.provider,
      base_url: p.base_url,
      api_format: p.api_format,
      reasoning_effort: p.effort,
      description: p.desc || '快捷收录预设模型',
    }
    await api('/api/v1/admin/llm/models', { method: 'POST', body: JSON.stringify(payload) })
    await loadConfig()
    alert(`预设模型 ${p.name} 已成功收录至模型库！`)
  } catch (e: any) {
    alert(e.message)
  }
}

async function saveModel() {
  try {
    const payload = { ...form.value }
    if (!payload.api_key) delete payload.api_key
    await api('/api/v1/admin/llm/models', { method: 'POST', body: JSON.stringify(payload) })
    modalVisible.value = false
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
  }
}

async function activateModel(id: string, effort: string) {
  try {
    await api('/api/v1/admin/llm/activate', { method: 'POST', body: JSON.stringify({ model_id: id, reasoning_effort: effort }) })
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
  }
}

async function deleteModel(id: string) {
  if (!confirm(`确定从模型库删除 ${id}？`)) return
  try {
    await api(`/api/v1/admin/llm/models/${encodeURIComponent(id)}`, { method: 'DELETE' })
    await loadConfig()
  } catch (e: any) {
    alert(e.message)
  }
}

async function runTest(m: any) {
  testLoading.value = true
  testingModelId.value = m.id
  testResult.value = null
  try {
    testResult.value = await api('/api/v1/admin/llm/test', {
      method: 'POST',
      body: JSON.stringify({
        model: m.id,
        base_url: m.base_url,
        api_format: m.api_format || 'openai_chat',
        reasoning_effort: m.reasoning_effort || 'auto',
      }),
    })
  } catch (e: any) {
    testResult.value = { ok: false, error: e.message }
  } finally {
    testLoading.value = false
    testingModelId.value = null
  }
}

function apiFormatBadge(fmt: string): string {
  if (fmt === 'claude_messages') return 'Claude Messages'
  if (fmt === 'openai_responses') return 'OpenAI Responses'
  return 'OpenAI Chat'
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div class="space-y-4 max-w-[2160px] mx-auto font-mono text-xs">
    <!-- Header Strip -->
    <div
      class="rounded-xl border p-4 sm:p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-3 shadow-xs transition-colors"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div>
        <div class="flex items-center space-x-2">
          <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
          <h1 class="text-sm sm:text-base font-black tracking-wide" style="color: var(--text-main);">
            LLM 多模型连接与供应商调度中心
          </h1>
          <span
            class="px-2 py-0.2 rounded text-[10px] font-bold border"
            style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
          >
            3 大原生协议全兼容
          </span>
          <span
            class="hidden sm:inline-block px-2 py-0.2 rounded text-[10px] font-bold border"
            style="background-color: var(--bg-badge); color: var(--text-muted); border-color: var(--border-subtle);"
          >
            OpenRouter / OpenCode / 官方直连
          </span>
        </div>
        <p class="text-xs mt-1" style="color: var(--text-muted);">
          纳管 OpenAI Chat、OpenAI Responses 与 Claude Messages 协议；支持全平台 API Key 加密托管、远端模型一键动态探测及长链推演（CoT）深度适配。
        </p>
      </div>

      <!-- Action Buttons -->
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <!-- Remote Fetch Button -->
        <button
          @click="openFetchModal()"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all cursor-pointer shadow-xs hover:opacity-90"
          style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
          title="从远端供应商动态拉取模型"
        >
          <DownloadCloud class="w-3.5 h-3.5 text-blue-500" />
          <span>远端一键拉取模型</span>
        </button>

        <!-- Provider Matrix Button -->
        <button
          @click="openProviderModal()"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-bold border transition-all cursor-pointer shadow-xs hover:opacity-90"
          style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
          title="管理多供应商平台凭据"
        >
          <Globe class="w-3.5 h-3.5 text-emerald-500" />
          <span>供应商矩阵 ({{ cfg?.providers?.length || 0 }})</span>
        </button>

        <!-- View Mode Switcher -->
        <div class="flex items-center rounded-lg border p-0.5" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <button
            @click="viewMode = 'cards'"
            class="p-1.5 rounded-md text-xs transition-all cursor-pointer"
            :style="viewMode === 'cards' ? { backgroundColor: 'var(--bg-card)', color: 'var(--text-main)', boxShadow: '0 1px 2px rgba(0,0,0,0.1)' } : { color: 'var(--text-faint)' }"
            title="卡片视图"
          >
            <LayoutGrid class="w-3.5 h-3.5" />
          </button>
          <button
            @click="viewMode = 'table'"
            class="p-1.5 rounded-md text-xs transition-all cursor-pointer"
            :style="viewMode === 'table' ? { backgroundColor: 'var(--bg-card)', color: 'var(--text-main)', boxShadow: '0 1px 2px rgba(0,0,0,0.1)' } : { color: 'var(--text-faint)' }"
            title="表格视图"
          >
            <List class="w-3.5 h-3.5" />
          </button>
        </div>

        <!-- Add Custom Model -->
        <button
          @click="openModal(null)"
          class="flex items-center justify-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
          style="background-color: #2563EB; color: #FFFFFF;"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>添加模型</span>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="py-16 text-center text-xs" style="color: var(--text-muted);">
      <RefreshCw class="w-6 h-6 animate-spin mx-auto mb-2" style="color: var(--color-brand);" />
      <span>正在加载模型连接库与供应商矩阵...</span>
    </div>

    <template v-else-if="cfg">
      <!-- Active Model Hero Bento -->
      <div
        class="rounded-xl border p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 shadow-xs transition-colors"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div class="flex items-start sm:items-center space-x-3.5">
          <div
            class="w-11 h-11 rounded-xl flex items-center justify-center border shrink-0 mt-0.5 sm:mt-0"
            style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
          >
            <Zap class="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-[10px] font-bold uppercase tracking-wider" style="color: var(--color-up);">
                ● 当前全局决策生效主脑
              </span>
              <span
                class="px-1.5 py-0.2 rounded text-[9px] font-bold border"
                style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
              >
                生产部署中
              </span>
            </div>
            <div class="text-base sm:text-lg font-black tracking-tight mt-0.5" style="color: var(--text-main);">
              {{ cfg.active_model_id }}
            </div>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] mt-1" style="color: var(--text-muted);">
              <span>渠道: <strong style="color: var(--text-main);">{{ cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.provider_name || '官方/代理' }}</strong></span>
              <span>·</span>
              <span class="flex items-center space-x-1">
                <span>Base URL:</span>
                <span class="num-tabular font-bold" style="color: var(--text-main);">{{ cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.base_url }}</span>
              </span>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap items-center gap-2 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0" style="border-color: var(--border-subtle);">
          <span
            class="px-2.5 py-1 rounded-lg border text-xs font-bold"
            style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-main);"
          >
            思考强度: {{ cfg.active_reasoning_effort?.toUpperCase() || 'HIGH' }}
          </span>
          <span
            class="px-2.5 py-1 rounded-lg border text-xs font-bold"
            style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
          >
            {{ apiFormatBadge(cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.api_format || 'openai_chat') }}
          </span>
          <button
            @click="runTest(cfg.models?.find((m: any) => m.id === cfg.active_model_id))"
            :disabled="testLoading"
            class="flex items-center space-x-1.5 px-3 py-1 rounded-lg border text-xs font-bold cursor-pointer transition-all shadow-xs"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
          >
            <RefreshCw class="w-3.5 h-3.5" :class="testLoading && testingModelId === cfg.active_model_id ? 'animate-spin' : ''" />
            <span>诊断主脑连通性</span>
          </button>
        </div>
      </div>

      <!-- Test Result Diagnostic Box -->
      <div
        v-if="testResult"
        class="rounded-xl border p-4 transition-all shadow-xs text-xs"
        :style="{
          backgroundColor: testResult.ok ? 'var(--color-up-bg)' : 'var(--color-down-bg)',
          borderColor: testResult.ok ? 'var(--color-up-border)' : 'var(--color-down-border)',
          color: testResult.ok ? 'var(--color-up)' : 'var(--color-down)'
        }"
      >
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center space-x-2 font-bold text-sm">
            <CheckCircle2 v-if="testResult.ok" class="w-4 h-4" />
            <AlertCircle v-else class="w-4 h-4" />
            <span>{{ testResult.ok ? `模型网关测试成功 (耗时: ${testResult.latency_ms}ms)` : '连通性测试未通过' }}</span>
          </div>
          <span class="text-[10px] opacity-75 font-mono">状态: {{ testResult.status_code || 0 }}</span>
        </div>

        <div v-if="testResult.ok" class="space-y-1 text-xs" style="color: var(--text-main);">
          <div>响应输出: <span class="font-bold">{{ testResult.response_preview }}</span></div>
          <div v-if="testResult.reasoning_detected" style="color: var(--color-up);" class="font-bold flex items-center space-x-1">
            <span>🧠 成功捕获原生链式推演输出 (Reasoning Tokens: {{ testResult.reasoning_tokens || '已识别' }})</span>
          </div>
          <div v-if="testResult.warning" class="text-[11px] text-amber-500">
            ⚠️ {{ testResult.warning }}
          </div>
        </div>
        <div v-else class="text-xs break-all" style="color: var(--color-down);">
          {{ testResult.error || '连通性测试超时或未收到有效响应' }}
          <div v-if="testResult.recommendation" class="text-[11px] opacity-90 mt-0.5">
            建议: {{ testResult.recommendation }}
          </div>
        </div>
      </div>

      <!-- Flagship Presets Bento Strip -->
      <div
        class="rounded-xl border p-4 space-y-2.5 shadow-xs transition-colors"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-1.5">
            <Sparkles class="w-3.5 h-3.5 text-amber-400" />
            <span class="text-xs font-black uppercase tracking-wide" style="color: var(--text-main);">
              最新旗舰标杆预设 (2025/2026 前沿模型)
            </span>
          </div>
          <span class="text-[11px]" style="color: var(--text-faint);">
            点击「收录」快捷保存至本地库
          </span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-2">
          <div
            v-for="p in flagshipPresets"
            :key="p.id"
            class="rounded-lg border p-2.5 flex flex-col justify-between space-y-2 transition-all hover:border-[var(--border-strong)]"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div>
              <div class="flex items-center justify-between gap-1">
                <span class="font-bold text-[11px] truncate" style="color: var(--text-main);" :title="p.label">
                  {{ p.label }}
                </span>
              </div>
              <div class="text-[9px] num-tabular truncate mt-0.5" style="color: var(--text-faint);" :title="p.id">
                {{ p.id }}
              </div>
              <div class="text-[10px] mt-1 line-clamp-2" style="color: var(--text-muted);" :title="p.desc">
                {{ p.desc }}
              </div>
            </div>

            <div class="pt-1 border-t flex items-center justify-between gap-1" style="border-color: var(--border-subtle);">
              <span class="text-[9px] font-bold px-1.5 py-0.2 rounded border" style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-faint);">
                {{ p.provider }}
              </span>
              <button
                @click="quickAddPreset(p)"
                class="px-2 py-0.5 rounded text-[10px] font-bold border transition-colors cursor-pointer shadow-xs hover:bg-[var(--text-main)] hover:text-[var(--bg-card)]"
                style="background-color: var(--bg-card); border-color: var(--border-medium); color: var(--text-main);"
              >
                + 收录
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Provider Overview Badges Strip -->
      <div
        class="rounded-xl border p-3 flex flex-wrap items-center justify-between gap-2 shadow-xs"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div class="flex items-center space-x-2">
          <Globe class="w-3.5 h-3.5" style="color: var(--color-brand);" />
          <span class="text-xs font-bold" style="color: var(--text-main);">接入供应商:</span>
        </div>
        <div class="flex flex-wrap items-center gap-1.5">
          <button
            v-for="prov in cfg.providers"
            :key="prov.id"
            @click="openFetchModal(prov.id)"
            class="px-2.5 py-1 rounded-lg border text-[11px] flex items-center space-x-1.5 transition-all cursor-pointer hover:border-[var(--text-main)]"
            :style="{
              backgroundColor: prov.has_key ? 'var(--color-up-bg)' : 'var(--bg-card-subtle)',
              borderColor: prov.has_key ? 'var(--color-up-border)' : 'var(--border-subtle)',
              color: prov.has_key ? 'var(--color-up)' : 'var(--text-muted)'
            }"
            :title="`端点: ${prov.base_url} · 点击拉取模型`"
          >
            <span class="w-1.5 h-1.5 rounded-full" :style="{ backgroundColor: prov.has_key ? 'var(--color-up)' : 'var(--text-faint)' }"></span>
            <span class="font-bold">{{ prov.name }}</span>
            <span class="text-[9px] opacity-75">({{ prov.models_count || 0 }})</span>
          </button>
        </div>
        <button
          @click="openProviderModal()"
          class="text-[11px] font-bold underline cursor-pointer hover:opacity-80"
          style="color: var(--color-brand);"
        >
          配置密钥与端点 →
        </button>
      </div>

      <!-- Model Library Container -->
      <div class="space-y-3">
        <!-- Filter & Search Strip -->
        <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 px-1">
          <div class="flex items-center space-x-2">
            <Server class="w-4 h-4" style="color: var(--text-muted);" />
            <h2 class="text-xs font-black uppercase tracking-wide" style="color: var(--text-main);">
              已配置模型连接库 ({{ filteredModels.length }} / {{ cfg.models?.length || 0 }} 个模型)
            </h2>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- Provider Filter -->
            <select
              v-model="selectedProviderFilter"
              class="px-2.5 py-1 rounded-lg border text-xs outline-none cursor-pointer"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            >
              <option value="ALL">全部供应商渠道</option>
              <option v-for="p in cfg.providers" :key="p.id" :value="p.id">
                {{ p.name }}
              </option>
              <option value="custom">自定义中继/代理</option>
            </select>

            <!-- Search Input -->
            <div class="relative">
              <input
                v-model="searchQuery"
                placeholder="搜索模型 ID / 名称..."
                class="px-2.5 py-1 pl-7 rounded-lg border text-xs outline-none w-44 sm:w-56"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
              <Search class="w-3.5 h-3.5 absolute left-2 top-2 text-[var(--text-faint)] pointer-events-none" />
            </div>
          </div>
        </div>

        <!-- Mode 1: Bento Cards View -->
        <div v-if="viewMode === 'cards'" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
          <div
            v-for="m in filteredModels"
            :key="m.id"
            class="rounded-xl border p-4 flex flex-col justify-between space-y-3 transition-all shadow-xs hover:border-[var(--border-strong)]"
            :style="{
              backgroundColor: m.id === cfg.active_model_id ? 'var(--bg-card)' : 'var(--bg-card)',
              borderColor: m.id === cfg.active_model_id ? 'var(--color-up-border)' : 'var(--border-subtle)',
              boxShadow: m.id === cfg.active_model_id ? '0 0 0 1px var(--color-up-border)' : 'none'
            }"
          >
            <!-- Card Header -->
            <div class="space-y-1.5">
              <div class="flex items-start justify-between gap-2">
                <div>
                  <div class="flex items-center space-x-2">
                    <span class="font-bold text-sm" style="color: var(--text-main);">{{ m.name || m.id }}</span>
                    <span
                      v-if="m.id === cfg.active_model_id"
                      class="px-1.5 py-0.2 rounded text-[9px] font-bold border"
                      style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
                    >
                      当前活跃
                    </span>
                  </div>
                  <div class="text-[11px] num-tabular mt-0.5" style="color: var(--text-faint);">{{ m.id }}</div>
                </div>

                <!-- Protocol Badge -->
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-bold border shrink-0"
                  style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
                >
                  {{ apiFormatBadge(m.api_format) }}
                </span>
              </div>

              <!-- Metadata Row -->
              <div class="flex flex-wrap items-center gap-2 pt-1 text-[11px]">
                <span class="px-2 py-0.5 rounded border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);">
                  供应商: <strong style="color: var(--text-main);">{{ m.provider_name || '自定义' }}</strong>
                </span>
                <span class="px-2 py-0.5 rounded border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);">
                  思考: <strong style="color: var(--text-main);">{{ (m.reasoning_effort || 'high').toUpperCase() }}</strong>
                </span>
                <span v-if="m.has_key" class="px-2 py-0.5 rounded border text-emerald-500" style="background-color: var(--color-up-bg); border-color: var(--color-up-border);">
                  🔑 密钥就绪
                </span>
              </div>
            </div>

            <!-- Base URL Strip -->
            <div
              class="px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[11px]"
              style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
            >
              <div class="truncate mr-2" style="color: var(--text-muted);" :title="m.base_url">
                {{ m.base_url }}
              </div>
              <button
                @click="copyUrl(m.base_url, m.id)"
                class="shrink-0 p-1 rounded hover:bg-[var(--bg-card)] text-[10px] cursor-pointer transition-colors"
                style="color: var(--text-faint);"
                title="复制端点 URL"
              >
                <Check v-if="copiedId === m.id" class="w-3.5 h-3.5 text-emerald-400" />
                <Copy v-else class="w-3.5 h-3.5" />
              </button>
            </div>

            <!-- Card Actions Footer -->
            <div class="pt-2 border-t flex items-center justify-between gap-2" style="border-color: var(--border-subtle);">
              <div class="flex items-center space-x-1.5">
                <button
                  @click="runTest(m)"
                  :disabled="testLoading && testingModelId === m.id"
                  class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-xs font-medium transition-all cursor-pointer shadow-xs"
                  style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                >
                  <RefreshCw class="w-3 h-3" :class="testLoading && testingModelId === m.id ? 'animate-spin' : ''" />
                  <span>测试</span>
                </button>
                <button
                  @click="openModal(m)"
                  class="px-2.5 py-1 rounded-lg border text-xs font-medium transition-all cursor-pointer shadow-xs"
                  style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                >
                  编辑
                </button>
                <button
                  v-if="m.id !== cfg.active_model_id"
                  @click="deleteModel(m.id)"
                  class="p-1 rounded-lg border text-xs transition-all cursor-pointer shadow-xs hover:opacity-80"
                  style="background-color: var(--color-down-bg); border-color: var(--color-down-border); color: var(--color-down);"
                  title="从模型库删除"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </div>

              <!-- Main Switch Action -->
              <div>
                <span
                  v-if="m.id === cfg.active_model_id"
                  class="text-[11px] font-bold flex items-center space-x-1"
                  style="color: var(--color-up);"
                >
                  <CheckCircle2 class="w-3.5 h-3.5" />
                  <span>已主脑生效</span>
                </span>
                <button
                  v-else
                  @click="activateModel(m.id, m.reasoning_effort)"
                  class="flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
                  style="background-color: #2563EB; color: #FFFFFF;"
                >
                  <Zap class="w-3 h-3" />
                  <span>一键启用</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Mode 2: Table View -->
        <div
          v-else
          class="rounded-xl border overflow-hidden shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="overflow-x-auto">
            <table class="w-full text-left border-collapse text-xs">
              <thead>
                <tr class="border-b" style="border-color: var(--border-subtle); background-color: var(--bg-card-subtle);">
                  <th class="py-2.5 px-4 font-bold" style="color: var(--text-muted);">模型 ID / 别名</th>
                  <th class="py-2.5 px-3 font-bold" style="color: var(--text-muted);">协议格式</th>
                  <th class="py-2.5 px-3 font-bold" style="color: var(--text-muted);">供应商渠道</th>
                  <th class="py-2.5 px-3 font-bold" style="color: var(--text-muted);">思考强度</th>
                  <th class="py-2.5 px-3 font-bold" style="color: var(--text-muted);">Base URL</th>
                  <th class="py-2.5 px-4 text-right font-bold" style="color: var(--text-muted);">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y" style="border-color: var(--border-subtle);">
                <tr
                  v-for="m in filteredModels"
                  :key="m.id"
                  class="hover:bg-[var(--bg-card-subtle)] transition-colors"
                  :style="m.id === cfg.active_model_id ? { backgroundColor: 'var(--color-up-bg)' } : {}"
                >
                  <td class="py-3 px-4">
                    <div class="flex items-center space-x-2">
                      <span class="font-bold text-sm" style="color: var(--text-main);">{{ m.name || m.id }}</span>
                      <span
                        v-if="m.id === cfg.active_model_id"
                        class="px-1.5 py-0.2 rounded text-[9px] font-bold border"
                        style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
                      >
                        活跃
                      </span>
                    </div>
                    <div class="text-[10px] num-tabular" style="color: var(--text-faint);">{{ m.id }}</div>
                  </td>

                  <td class="py-3 px-3">
                    <span
                      class="px-2 py-0.5 rounded text-[10px] font-bold border"
                      style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
                    >
                      {{ apiFormatBadge(m.api_format) }}
                    </span>
                  </td>

                  <td class="py-3 px-3 font-medium" style="color: var(--text-main);">
                    {{ m.provider_name || '自定义' }}
                  </td>

                  <td class="py-3 px-3 font-bold num-tabular" style="color: var(--text-main);">
                    {{ (m.reasoning_effort || 'high').toUpperCase() }}
                  </td>

                  <td class="py-3 px-3 text-[11px] max-w-[200px] truncate" style="color: var(--text-muted);" :title="m.base_url">
                    {{ m.base_url }}
                  </td>

                  <td class="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                    <button
                      v-if="m.id !== cfg.active_model_id"
                      @click="activateModel(m.id, m.reasoning_effort)"
                      class="px-2.5 py-1 rounded-md text-[11px] font-bold border transition-all cursor-pointer shadow-xs btn-primary-text"
                      style="background-color: #2563EB; color: #FFFFFF; border-color: #2563EB;"
                    >
                      一键启用
                    </button>
                    <button
                      @click="runTest(m)"
                      :disabled="testLoading && testingModelId === m.id"
                      class="px-2.5 py-1 rounded-md text-[11px] border transition-all cursor-pointer shadow-xs"
                      style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                    >
                      ⚡ 测试
                    </button>
                    <button
                      @click="openModal(m)"
                      class="px-2.5 py-1 rounded-md text-[11px] border transition-all cursor-pointer shadow-xs"
                      style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                    >
                      ✏️ 编辑
                    </button>
                    <button
                      v-if="m.id !== cfg.active_model_id"
                      @click="deleteModel(m.id)"
                      class="px-2.5 py-1 rounded-md text-[11px] border transition-all cursor-pointer shadow-xs"
                      style="background-color: var(--color-down-bg); border-color: var(--color-down-border); color: var(--color-down);"
                    >
                      删除
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <!-- Modal 1: Model Add / Edit Modal -->
    <div
      v-if="modalVisible"
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-3 sm:p-4"
      @click.self="modalVisible = false"
    >
      <div
        class="border rounded-2xl w-full max-w-xl shadow-2xl p-5 sm:p-6 space-y-4 text-xs max-h-[90dvh] overflow-y-auto"
        style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
      >
        <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
            <h3 class="text-sm font-black uppercase" style="color: var(--text-main);">
              {{ editingModel ? '编辑模型连接' : '添加模型连接' }}
            </h3>
          </div>
          <span class="text-[10px]" style="color: var(--text-faint);">API 凭证加密存储</span>
        </div>

        <!-- Quick Fill Presets (when adding new) -->
        <div v-if="!editingModel" class="space-y-1.5">
          <div class="text-[10px] font-bold uppercase" style="color: var(--text-faint);">
            快捷预设一键填入:
          </div>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="p in flagshipPresets"
              :key="p.id"
              @click="applyPreset(p)"
              class="px-2 py-1 rounded-md border text-[11px] cursor-pointer transition-all hover:border-[var(--text-main)]"
              style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);"
            >
              + {{ p.label }}
            </button>
          </div>
        </div>

        <!-- Form Fields -->
        <div class="space-y-3 pt-1">
          <!-- Provider Selector -->
          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">关联供应商渠道</label>
            <select
              :value="form.provider_id"
              @change="onModalProviderSelect"
              class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors cursor-pointer"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            >
              <option v-for="p in cfg?.providers" :key="p.id" :value="p.id">
                {{ p.name }} ({{ p.base_url }})
              </option>
              <option value="custom">自定义独立 Base URL</option>
            </select>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">模型 ID (唯一标识)</label>
              <input
                v-model="form.id"
                :readonly="!!editingModel"
                placeholder="例如: gemini-3.8-flash"
                class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">展示别名</label>
              <input
                v-model="form.name"
                placeholder="例如: Gemini 3.8 Flash (高思考)"
                class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">API 协议格式</label>
              <select
                v-model="form.api_format"
                class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors cursor-pointer"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              >
                <option value="openai_chat">OpenAI Chat (/chat/completions)</option>
                <option value="openai_responses">OpenAI Responses (/responses)</option>
                <option value="claude_messages">Claude Messages (/messages)</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">展示供应商名</label>
              <input
                v-model="form.provider_name"
                placeholder="例如: OpenRouter / 官方直连"
                class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">API Base URL (端点根路径)</label>
            <input
              v-model="form.base_url"
              placeholder="https://openrouter.ai/api/v1"
              class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">
              API Key (密钥) <span class="text-[10px] font-normal" style="color: var(--text-faint);">(留空则自动继承供应商已保存凭证)</span>
            </label>
            <input
              v-model="form.api_key"
              type="password"
              placeholder="sk-..."
              class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">思考强度 (Reasoning Effort)</label>
            <select
              v-model="form.reasoning_effort"
              class="w-full rounded-lg px-3 py-2 text-xs outline-none border transition-colors cursor-pointer"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            >
              <option value="high">HIGH · 深度长链推演 (推荐用于实盘与终审仲裁)</option>
              <option value="medium">MEDIUM · 均衡推演</option>
              <option value="low">LOW · 极速响应</option>
              <option value="auto">AUTO · 自动适配模型默认值</option>
              <option value="none">NONE · 强制关闭思考</option>
            </select>
          </div>
        </div>

        <div class="flex justify-end space-x-2 pt-3 border-t" style="border-color: var(--border-subtle);">
          <button
            @click="modalVisible = false"
            class="px-3.5 py-1.5 rounded-lg border text-xs cursor-pointer transition-colors"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);"
          >
            取消
          </button>
          <button
            @click="saveModel"
            class="px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
            style="background-color: #2563EB; color: #FFFFFF;"
          >
            保存并收录
          </button>
        </div>
      </div>
    </div>

    <!-- Modal 2: Provider Matrix Management Modal -->
    <div
      v-if="providerModalVisible"
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-3 sm:p-4"
      @click.self="providerModalVisible = false"
    >
      <div
        class="border rounded-2xl w-full max-w-2xl shadow-2xl p-5 sm:p-6 space-y-4 text-xs max-h-[90dvh] overflow-y-auto"
        style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
      >
        <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <Globe class="w-4 h-4 text-emerald-500" />
            <h3 class="text-sm font-black uppercase" style="color: var(--text-main);">
              大模型多供应商接入矩阵
            </h3>
          </div>
          <button
            @click="openProviderModal()"
            class="px-2.5 py-1 rounded text-[11px] font-bold border cursor-pointer hover:opacity-80"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
          >
            + 新增供应商
          </button>
        </div>

        <!-- Provider Edit Form (if active) -->
        <div v-if="editingProvider !== null || providerForm.id" class="p-3.5 rounded-xl border space-y-3" style="background-color: var(--bg-card-subtle); border-color: var(--border-medium);">
          <div class="flex items-center justify-between">
            <span class="font-bold text-xs" style="color: var(--text-main);">
              {{ editingProvider ? `编辑供应商: ${editingProvider.name}` : '新建供应商平台' }}
            </span>
            <button @click="editingProvider = null; providerForm.id = ''" class="text-[10px] text-[var(--text-faint)] hover:underline">收起编辑</button>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">供应商标识 (ID)</label>
              <input
                v-model="providerForm.id"
                :readonly="!!editingProvider"
                placeholder="例如: openrouter / opencode"
                class="w-full rounded-lg px-3 py-1.5 text-xs outline-none border"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">供应商名称</label>
              <input
                v-model="providerForm.name"
                placeholder="例如: OpenRouter 全球聚合"
                class="w-full rounded-lg px-3 py-1.5 text-xs outline-none border"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">Base URL</label>
            <input
              v-model="providerForm.base_url"
              placeholder="https://openrouter.ai/api/v1"
              class="w-full rounded-lg px-3 py-1.5 text-xs outline-none border"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">
              API Key (密钥) <span v-if="editingProvider" class="text-[10px] font-normal" style="color: var(--text-faint);">(留空保持现有凭证)</span>
            </label>
            <input
              v-model="providerForm.api_key"
              type="password"
              placeholder="sk-..."
              class="w-full rounded-lg px-3 py-1.5 text-xs outline-none border"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div class="flex justify-end space-x-2 pt-2">
            <button
              @click="editingProvider = null; providerForm.id = ''"
              class="px-3 py-1 rounded-md border text-xs cursor-pointer"
              style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-muted);"
            >
              取消
            </button>
            <button
              @click="saveProvider"
              class="px-3.5 py-1 rounded-md text-xs font-bold transition-all cursor-pointer btn-primary-text"
              style="background-color: #2563EB; color: #FFFFFF;"
            >
              保存供应商
            </button>
          </div>
        </div>

        <!-- Providers List -->
        <div class="space-y-2">
          <div
            v-for="p in cfg?.providers"
            :key="p.id"
            class="p-3 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-all"
            style="background-color: var(--bg-card); border-color: var(--border-subtle);"
          >
            <div>
              <div class="flex items-center space-x-2">
                <span class="font-bold text-sm" style="color: var(--text-main);">{{ p.name }}</span>
                <span class="text-[10px] num-tabular" style="color: var(--text-faint);">({{ p.id }})</span>
                <span
                  class="px-1.5 py-0.2 rounded text-[9px] font-bold border"
                  :style="{
                    backgroundColor: p.has_key ? 'var(--color-up-bg)' : 'var(--bg-card-subtle)',
                    borderColor: p.has_key ? 'var(--color-up-border)' : 'var(--border-subtle)',
                    color: p.has_key ? 'var(--color-up)' : 'var(--text-faint)'
                  }"
                >
                  {{ p.has_key ? '已配置 Key' : '未配 Key' }}
                </span>
              </div>
              <div class="text-[11px] truncate max-w-md mt-0.5" style="color: var(--text-muted);">
                {{ p.base_url }}
              </div>
              <div class="text-[10px] mt-0.5" style="color: var(--text-faint);">
                已关联模型: {{ p.models_count || 0 }} 个 · {{ p.description }}
              </div>
            </div>

            <div class="flex items-center space-x-1.5 shrink-0">
              <button
                @click="openFetchModal(p.id)"
                class="px-2.5 py-1 rounded text-xs font-bold border cursor-pointer hover:opacity-80"
                style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
              >
                拉取模型
              </button>
              <button
                @click="openProviderModal(p)"
                class="px-2.5 py-1 rounded text-xs border cursor-pointer hover:opacity-80"
                style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
              >
                编辑
              </button>
              <button
                v-if="p.id !== 'custom'"
                @click="deleteProvider(p.id)"
                class="p-1 rounded text-xs border cursor-pointer hover:opacity-80"
                style="background-color: var(--color-down-bg); border-color: var(--color-down-border); color: var(--color-down);"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end pt-3 border-t" style="border-color: var(--border-subtle);">
          <button
            @click="providerModalVisible = false"
            class="px-4 py-1.5 rounded-lg border text-xs cursor-pointer"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-main);"
          >
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- Modal 3: Remote Model Fetcher Modal -->
    <div
      v-if="fetchModalVisible"
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-3 sm:p-4"
      @click.self="fetchModalVisible = false"
    >
      <div
        class="border rounded-2xl w-full max-w-3xl shadow-2xl p-5 sm:p-6 space-y-4 text-xs max-h-[92dvh] flex flex-col"
        style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
      >
        <div class="flex items-center justify-between pb-3 border-b shrink-0" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <DownloadCloud class="w-4 h-4 text-blue-500" />
            <h3 class="text-sm font-black uppercase" style="color: var(--text-main);">
              从远端供应商一键动态拉取模型
            </h3>
          </div>
          <span class="text-[10px]" style="color: var(--text-faint);">实时探测 /models 兼容端点</span>
        </div>

        <!-- Probe Configuration Bar -->
        <div class="p-3.5 rounded-xl border space-y-3 shrink-0" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">选择目标供应商</label>
              <select
                v-model="fetchProviderId"
                @change="onFetchProviderChanged"
                class="w-full rounded-lg px-2.5 py-1.5 text-xs outline-none border cursor-pointer"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              >
                <option v-for="p in cfg?.providers" :key="p.id" :value="p.id">
                  {{ p.name }}
                </option>
              </select>
            </div>

            <div class="sm:col-span-2">
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">Base URL</label>
              <input
                v-model="fetchBaseUrl"
                placeholder="https://openrouter.ai/api/v1"
                class="w-full rounded-lg px-2.5 py-1.5 text-xs outline-none border"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-1">
            <div class="flex-1">
              <input
                v-model="fetchApiKey"
                type="password"
                placeholder="临时覆盖 API Key (留空则默认使用该供应商已保存凭据)"
                class="w-full rounded-lg px-2.5 py-1.5 text-xs outline-none border"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
            <button
              @click="executeRemoteFetch"
              :disabled="fetchingRemote"
              class="flex items-center justify-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text shrink-0"
              style="background-color: #2563EB; color: #FFFFFF;"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="fetchingRemote ? 'animate-spin' : ''" />
              <span>{{ fetchingRemote ? '正在探测拉取...' : '⚡ 开始动态拉取' }}</span>
            </button>
          </div>
        </div>

        <!-- Probe Status Banner -->
        <div v-if="remoteFetchResult" class="shrink-0">
          <div
            v-if="remoteFetchResult.ok"
            class="p-3 rounded-xl border flex items-center justify-between text-xs"
            style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
          >
            <div class="flex items-center space-x-2 font-bold">
              <CheckCircle2 class="w-4 h-4" />
              <span>成功探测到 {{ remoteFetchResult.total }} 个可用模型！</span>
              <span class="text-[10px] opacity-80 font-normal">({{ remoteFetchResult.endpoint_used }})</span>
            </div>
            <span class="text-[10px] opacity-80">点击右侧「收录」即可加入本地模型库</span>
          </div>
          <div
            v-else
            class="p-3 rounded-xl border text-xs"
            style="background-color: var(--color-down-bg); border-color: var(--color-down-border); color: var(--color-down);"
          >
            <div class="font-bold flex items-center space-x-1.5">
              <AlertCircle class="w-4 h-4" />
              <span>{{ remoteFetchResult.error }}</span>
            </div>
            <div v-if="remoteFetchResult.recommendation" class="text-[11px] opacity-80 mt-0.5">
              建议: {{ remoteFetchResult.recommendation }}
            </div>
          </div>
        </div>

        <!-- Filter & Search Inside Remote List -->
        <div v-if="remoteFetchResult?.ok" class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 shrink-0 pt-1">
          <div class="flex items-center space-x-1.5">
            <button
              @click="remoteFilterCategory = 'ALL'"
              class="px-2.5 py-1 rounded text-xs cursor-pointer font-bold border transition-all"
              :style="remoteFilterCategory === 'ALL' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { backgroundColor: 'var(--bg-card-subtle)', color: 'var(--text-muted)' }"
            >
              全部 ({{ remoteFetchResult.total }})
            </button>
            <button
              @click="remoteFilterCategory = 'flagship'"
              class="px-2.5 py-1 rounded text-xs cursor-pointer font-bold border transition-all"
              :style="remoteFilterCategory === 'flagship' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { backgroundColor: 'var(--bg-card-subtle)', color: 'var(--text-muted)' }"
            >
              ⭐ 旗舰前沿
            </button>
            <button
              @click="remoteFilterCategory = 'reasoning'"
              class="px-2.5 py-1 rounded text-xs cursor-pointer font-bold border transition-all"
              :style="remoteFilterCategory === 'reasoning' ? { backgroundColor: 'var(--text-main)', color: 'var(--bg-card)' } : { backgroundColor: 'var(--bg-card-subtle)', color: 'var(--text-muted)' }"
            >
              🧠 链式推演
            </button>
          </div>

          <div class="relative">
            <input
              v-model="remoteSearch"
              placeholder="过滤模型 ID / 名称..."
              class="px-2.5 py-1 pl-7 rounded-lg border text-xs outline-none w-48 sm:w-60"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
            <Search class="w-3.5 h-3.5 absolute left-2 top-2 text-[var(--text-faint)] pointer-events-none" />
          </div>
        </div>

        <!-- Remote Models Scrollable List -->
        <div v-if="remoteFetchResult?.ok" class="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[220px]">
          <div
            v-for="m in filteredRemoteModels"
            :key="m.id"
            class="p-3 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 hover:border-[var(--border-strong)] transition-colors"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div>
              <div class="flex items-center space-x-2">
                <span class="font-bold text-xs" style="color: var(--text-main);">{{ m.name }}</span>
                <span v-if="m.reasoning_type !== 'none'" class="px-1.5 py-0.2 rounded text-[9px] font-bold border text-amber-400 border-amber-500/30 bg-amber-500/10">
                  🧠 推理
                </span>
                <span v-if="m.context_length" class="text-[9px] font-mono opacity-70" style="color: var(--text-muted);">
                  {{ (m.context_length / 1000).toFixed(0) }}k 上下文
                </span>
              </div>
              <div class="text-[10px] num-tabular mt-0.5 text-blue-400 font-mono">
                {{ m.id }}
              </div>
              <div v-if="m.description" class="text-[10px] text-[var(--text-faint)] line-clamp-1 mt-0.5">
                {{ m.description }}
              </div>
            </div>

            <div class="flex items-center space-x-2 shrink-0">
              <button
                @click="importRemoteModel(m, false)"
                class="px-2.5 py-1 rounded text-xs font-bold border transition-colors cursor-pointer shadow-xs hover:bg-[var(--text-main)] hover:text-[var(--bg-card)]"
                style="background-color: var(--bg-card); border-color: var(--border-medium); color: var(--text-main);"
              >
                + 收录至库
              </button>
              <button
                @click="importRemoteModel(m, true)"
                class="px-3 py-1 rounded text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
                style="background-color: #2563EB; color: #FFFFFF;"
              >
                收录并启用
              </button>
            </div>
          </div>

          <div v-if="filteredRemoteModels.length === 0" class="py-10 text-center text-xs" style="color: var(--text-faint);">
            未找到匹配的模型，请尝试调整搜索关键词
          </div>
        </div>

        <div class="flex justify-end pt-3 border-t shrink-0" style="border-color: var(--border-subtle);">
          <button
            @click="fetchModalVisible = false"
            class="px-4 py-1.5 rounded-lg border text-xs cursor-pointer"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-main);"
          >
            完成
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
