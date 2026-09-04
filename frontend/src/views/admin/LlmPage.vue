<script setup lang="ts">
import { ref, onMounted } from 'vue'
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

const form = ref<any>({
  id: '',
  name: '',
  api_format: 'openai_chat',
  base_url: 'https://api.openai.com/v1',
  api_key: '',
  provider_name: '',
  reasoning_effort: 'high',
  description: '',
})

const presets = [
  { label: 'DeepSeek R1', id: 'deepseek-reasoner', name: 'DeepSeek R1 (满血推理)', api_format: 'openai_chat', base_url: 'https://api.deepseek.com/v1', provider: 'DeepSeek 官方', effort: 'high' },
  { label: 'Gemini 2.5 Flash', id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', api_format: 'openai_chat', base_url: 'https://generativelanguage.googleapis.com/v1beta/openai', provider: 'Google AI Studio', effort: 'high' },
  { label: 'Claude 3.7 Sonnet', id: 'claude-3-7-sonnet-20250219', name: 'Claude 3.7 Sonnet', api_format: 'claude_messages', base_url: 'https://api.anthropic.com/v1', provider: 'Anthropic 官方', effort: 'high' },
  { label: 'OpenAI o3-mini', id: 'o3-mini', name: 'OpenAI o3-mini', api_format: 'openai_responses', base_url: 'https://api.openai.com/v1', provider: 'OpenAI 官方', effort: 'high' },
  { label: 'Qwen 2.5 72B', id: 'qwen-max-latest', name: '通义千问 Qwen Max', api_format: 'openai_chat', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', provider: '阿里云百炼', effort: 'medium' },
]

function applyPreset(p: typeof presets[0]) {
  form.value.id = p.id
  form.value.name = p.name
  form.value.api_format = p.api_format
  form.value.base_url = p.base_url
  form.value.provider_name = p.provider
  form.value.reasoning_effort = p.effort
}

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

function openModal(m: any | null) {
  editingModel.value = m
  if (m) {
    form.value = {
      id: m.id,
      name: m.name,
      api_format: m.api_format || 'openai_chat',
      base_url: m.base_url,
      api_key: '',
      provider_name: m.provider_name,
      reasoning_effort: m.reasoning_effort || 'high',
      description: m.description,
    }
  } else {
    form.value = {
      id: '',
      name: '',
      api_format: 'openai_chat',
      base_url: 'https://api.openai.com/v1',
      api_key: '',
      provider_name: '',
      reasoning_effort: 'high',
      description: '',
    }
  }
  modalVisible.value = true
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
  if (!confirm(`确定删除模型 ${id}？`)) return
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
  <div class="space-y-4 max-w-[2160px] mx-auto">
    <!-- Header Strip -->
    <div
      class="rounded-xl border p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs transition-colors"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div>
        <div class="flex items-center space-x-2">
          <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
          <h1 class="text-sm sm:text-base font-black font-mono tracking-wide" style="color: var(--text-main);">
            LLM 多模型连接与供应商中心
          </h1>
          <span
            class="px-2 py-0.2 rounded text-[10px] font-mono font-bold border"
            style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
          >
            3 大协议全兼容
          </span>
        </div>
        <p class="text-xs font-mono mt-1" style="color: var(--text-muted);">
          统一纳管 OpenAI Chat、OpenAI Responses 与 Claude Messages 协议；支持长链思考强度（Reasoning Effort）动态适配。
        </p>
      </div>

      <div class="flex items-center space-x-2 shrink-0">
        <!-- View Mode Switcher -->
        <div class="flex items-center rounded-lg border p-0.5" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);">
          <button
            @click="viewMode = 'cards'"
            class="p-1.5 rounded-md text-xs font-mono transition-all cursor-pointer"
            :style="viewMode === 'cards' ? { backgroundColor: 'var(--bg-card)', color: 'var(--text-main)', boxShadow: '0 1px 2px rgba(0,0,0,0.1)' } : { color: 'var(--text-faint)' }"
            title="卡片视图"
          >
            <LayoutGrid class="w-3.5 h-3.5" />
          </button>
          <button
            @click="viewMode = 'table'"
            class="p-1.5 rounded-md text-xs font-mono transition-all cursor-pointer"
            :style="viewMode === 'table' ? { backgroundColor: 'var(--bg-card)', color: 'var(--text-main)', boxShadow: '0 1px 2px rgba(0,0,0,0.1)' } : { color: 'var(--text-faint)' }"
            title="表格视图"
          >
            <List class="w-3.5 h-3.5" />
          </button>
        </div>

        <button
          @click="openModal(null)"
          class="flex items-center justify-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer shadow-xs"
          style="background-color: var(--text-main); color: var(--bg-card);"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>添加自定义模型</span>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="py-16 text-center text-xs font-mono" style="color: var(--text-muted);">
      <RefreshCw class="w-6 h-6 animate-spin mx-auto mb-2" style="color: var(--color-brand);" />
      <span>正在加载模型连接库...</span>
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
              <span class="text-[10px] font-mono font-bold uppercase tracking-wider" style="color: var(--color-up);">
                ● 当前全局决策生效主脑
              </span>
              <span
                class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold border"
                style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
              >
                生产部署中
              </span>
            </div>
            <div class="text-base sm:text-lg font-black font-mono tracking-tight mt-0.5" style="color: var(--text-main);">
              {{ cfg.active_model_id }}
            </div>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono mt-1" style="color: var(--text-muted);">
              <span>供应商: <strong style="color: var(--text-main);">{{ cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.provider_name || '官方/代理' }}</strong></span>
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
            class="px-2.5 py-1 rounded-lg border text-xs font-mono font-bold"
            style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-main);"
          >
            思考强度: {{ cfg.active_reasoning_effort?.toUpperCase() || 'HIGH' }}
          </span>
          <span
            class="px-2.5 py-1 rounded-lg border text-xs font-mono font-bold"
            style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
          >
            {{ apiFormatBadge(cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.api_format || 'openai_chat') }}
          </span>
          <button
            @click="runTest(cfg.models?.find((m: any) => m.id === cfg.active_model_id))"
            :disabled="testLoading"
            class="flex items-center space-x-1.5 px-3 py-1 rounded-lg border text-xs font-mono font-bold cursor-pointer transition-all shadow-xs"
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
        class="rounded-xl border p-4 transition-all shadow-xs font-mono text-xs"
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
            <span>{{ testResult.ok ? `模型网关连接成功 (耗时: ${testResult.latency_ms}ms)` : '连接测试未通过' }}</span>
          </div>
          <span class="text-[10px] opacity-75 font-mono">HTTP 200 OK</span>
        </div>

        <div v-if="testResult.ok" class="space-y-1 text-xs" style="color: var(--text-main);">
          <div>响应输出: <span class="font-bold">{{ testResult.response_preview }}</span></div>
          <div v-if="testResult.reasoning_detected" style="color: var(--color-up);" class="font-bold flex items-center space-x-1">
            <span>🧠 成功捕获链式推演输出</span>
            <span class="text-[11px] opacity-80">(Reasoning Tokens: {{ testResult.reasoning_tokens || '已成功识别' }})</span>
          </div>
        </div>
        <div v-else class="text-xs break-all" style="color: var(--color-down);">
          {{ testResult.error || '连通性测试超时或未收到有效响应' }}
        </div>
      </div>

      <!-- Model Library Container -->
      <div class="space-y-3">
        <div class="flex items-center justify-between px-1">
          <div class="flex items-center space-x-2">
            <Server class="w-4 h-4" style="color: var(--text-muted);" />
            <h2 class="text-xs font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
              已配置模型连接库 ({{ cfg.models?.length || 0 }} 个模型)
            </h2>
          </div>
          <span class="text-[11px] font-mono" style="color: var(--text-faint);">
            点击「一键启用」即刻热加载至交易主脑
          </span>
        </div>

        <!-- Mode 1: Bento Cards View (Organized & Uncrowded) -->
        <div v-if="viewMode === 'cards'" class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
          <div
            v-for="m in cfg.models"
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
                    <span class="font-bold text-sm font-mono" style="color: var(--text-main);">{{ m.name || m.id }}</span>
                    <span
                      v-if="m.id === cfg.active_model_id"
                      class="px-1.5 py-0.2 rounded text-[9px] font-mono font-bold border"
                      style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
                    >
                      当前活跃
                    </span>
                  </div>
                  <div class="text-[11px] font-mono num-tabular mt-0.5" style="color: var(--text-faint);">{{ m.id }}</div>
                </div>

                <!-- Protocol Badge -->
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-mono font-bold border shrink-0"
                  style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
                >
                  {{ apiFormatBadge(m.api_format) }}
                </span>
              </div>

              <!-- Metadata Row -->
              <div class="flex flex-wrap items-center gap-2 pt-1 text-[11px] font-mono">
                <span class="px-2 py-0.5 rounded border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);">
                  渠道: <strong style="color: var(--text-main);">{{ m.provider_name || '自定义' }}</strong>
                </span>
                <span class="px-2 py-0.5 rounded border" style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);">
                  思考: <strong style="color: var(--text-main);">{{ (m.reasoning_effort || 'high').toUpperCase() }}</strong>
                </span>
              </div>
            </div>

            <!-- Base URL Strip -->
            <div
              class="px-2.5 py-1.5 rounded-lg border flex items-center justify-between text-[11px] font-mono"
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
                  class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border text-xs font-mono font-medium transition-all cursor-pointer shadow-xs"
                  style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                >
                  <RefreshCw class="w-3 h-3" :class="testLoading && testingModelId === m.id ? 'animate-spin' : ''" />
                  <span>测试</span>
                </button>
                <button
                  @click="openModal(m)"
                  class="px-2.5 py-1 rounded-lg border text-xs font-mono font-medium transition-all cursor-pointer shadow-xs"
                  style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
                >
                  编辑
                </button>
                <button
                  v-if="m.id !== cfg.active_model_id"
                  @click="deleteModel(m.id)"
                  class="p-1 rounded-lg border text-xs font-mono transition-all cursor-pointer shadow-xs hover:opacity-80"
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
                  class="text-[11px] font-mono font-bold flex items-center space-x-1"
                  style="color: var(--color-up);"
                >
                  <CheckCircle2 class="w-3.5 h-3.5" />
                  <span>生效中</span>
                </span>
                <button
                  v-else
                  @click="activateModel(m.id, m.reasoning_effort)"
                  class="px-3 py-1 rounded-lg text-xs font-mono font-bold border transition-all cursor-pointer shadow-xs"
                  style="background-color: var(--text-main); color: var(--bg-card); border-color: var(--text-main);"
                >
                  一键启用
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Mode 2: Compact Normalized Table View -->
        <div
          v-else
          class="rounded-xl border shadow-xs transition-colors overflow-hidden"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-mono whitespace-nowrap">
              <thead>
                <tr
                  class="border-b text-[11px] uppercase tracking-wider"
                  style="border-color: var(--border-subtle); background-color: var(--bg-card-subtle); color: var(--text-muted);"
                >
                  <th class="py-3 px-4 font-bold">模型名称 / ID</th>
                  <th class="py-3 px-3 font-bold">协议格式</th>
                  <th class="py-3 px-3 font-bold">供应商</th>
                  <th class="py-3 px-3 font-bold">思考强度</th>
                  <th class="py-3 px-3 font-bold">Base URL</th>
                  <th class="py-3 px-4 text-right font-bold">操作与调度</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="m in cfg.models"
                  :key="m.id"
                  class="border-b last:border-b-0 transition-colors hover:bg-[var(--bg-card-hover)]"
                  :style="{
                    backgroundColor: m.id === cfg.active_model_id ? 'var(--color-brand-bg)' : 'transparent',
                    borderColor: 'var(--border-subtle)'
                  }"
                >
                  <!-- 模型 -->
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

                  <!-- 协议 -->
                  <td class="py-3 px-3">
                    <span
                      class="px-2 py-0.5 rounded text-[10px] font-bold border"
                      style="background-color: var(--bg-badge); border-color: var(--border-subtle); color: var(--text-muted);"
                    >
                      {{ apiFormatBadge(m.api_format) }}
                    </span>
                  </td>

                  <!-- 供应商 -->
                  <td class="py-3 px-3 font-medium" style="color: var(--text-main);">
                    {{ m.provider_name || '自定义' }}
                  </td>

                  <!-- 思考强度 -->
                  <td class="py-3 px-3 font-bold num-tabular" style="color: var(--text-main);">
                    {{ (m.reasoning_effort || 'high').toUpperCase() }}
                  </td>

                  <!-- Base URL -->
                  <td class="py-3 px-3 font-mono text-[11px] max-w-[200px] truncate" style="color: var(--text-muted);" :title="m.base_url">
                    {{ m.base_url }}
                  </td>

                  <!-- 操作 -->
                  <td class="py-3 px-4 text-right space-x-1.5 whitespace-nowrap">
                    <button
                      v-if="m.id !== cfg.active_model_id"
                      @click="activateModel(m.id, m.reasoning_effort)"
                      class="px-2.5 py-1 rounded-md text-[11px] font-bold border transition-all cursor-pointer shadow-xs"
                      style="background-color: var(--text-main); color: var(--bg-card); border-color: var(--text-main);"
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

    <!-- Model Add/Edit Modal -->
    <div
      v-if="modalVisible"
      class="fixed inset-0 z-50 bg-black/60 backdrop-blur-md flex items-center justify-center p-3 sm:p-4"
      @click.self="modalVisible = false"
    >
      <div
        class="border rounded-2xl w-full max-w-xl shadow-2xl p-5 sm:p-6 space-y-4 font-mono text-xs max-h-[90dvh] overflow-y-auto"
        style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
      >
        <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
            <h3 class="text-sm font-black uppercase" style="color: var(--text-main);">
              {{ editingModel ? '编辑模型连接' : '添加自定义模型连接' }}
            </h3>
          </div>
          <span class="text-[10px] font-mono" style="color: var(--text-faint);">API 凭证加密持久化</span>
        </div>

        <!-- Preset Quick Selector (when adding new) -->
        <div v-if="!editingModel" class="space-y-1.5">
          <div class="text-[10px] font-bold uppercase" style="color: var(--text-faint);">主流架构一键填入预设:</div>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="p in presets"
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
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">模型 ID (唯一标识)</label>
              <input
                v-model="form.id"
                :readonly="!!editingModel"
                placeholder="例如: gemini-2.5-flash"
                class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">展示别名</label>
              <input
                v-model="form.name"
                placeholder="例如: Gemini 2.5 Flash"
                class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">API 协议格式</label>
              <select
                v-model="form.api_format"
                class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors cursor-pointer"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              >
                <option value="openai_chat">OpenAI Chat (/chat/completions)</option>
                <option value="openai_responses">OpenAI Responses (/responses)</option>
                <option value="claude_messages">Claude Messages (/messages)</option>
              </select>
            </div>
            <div>
              <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">供应商名称 / 渠道渠道</label>
              <input
                v-model="form.provider_name"
                placeholder="例如: 官方直连 / OneAPI / 代理站"
                class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
                style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
              />
            </div>
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">API Base URL (端点根路径)</label>
            <input
              v-model="form.base_url"
              placeholder="https://api.openai.com/v1"
              class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">
              API Key (密钥) <span v-if="editingModel" class="text-[10px] font-normal" style="color: var(--text-faint);">(留空保持现有凭证)</span>
            </label>
            <input
              v-model="form.api_key"
              type="password"
              placeholder="sk-..."
              class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors"
              style="background-color: var(--bg-input); border-color: var(--border-subtle); color: var(--text-main);"
            />
          </div>

          <div>
            <label class="block text-[11px] font-bold mb-1" style="color: var(--text-muted);">思考强度 (Reasoning Effort)</label>
            <select
              v-model="form.reasoning_effort"
              class="w-full rounded-lg px-3 py-2 text-xs font-mono outline-none border transition-colors cursor-pointer"
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
            class="px-3.5 py-1.5 rounded-lg border text-xs font-mono cursor-pointer transition-colors"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-muted);"
          >
            取消
          </button>
          <button
            @click="saveModel"
            class="px-4 py-1.5 rounded-lg text-xs font-mono font-bold transition-all cursor-pointer shadow-xs"
            style="background-color: var(--text-main); color: var(--bg-card);"
          >
            保存并应用
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
