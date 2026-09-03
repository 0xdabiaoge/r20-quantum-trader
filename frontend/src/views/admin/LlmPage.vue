<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Cpu, Plus, Zap, Trash2, Pencil, CheckCircle2, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const cfg = ref<any>(null)
const loading = ref(true)
const testResult = ref<any>(null)
const testLoading = ref(false)
const modalVisible = ref(false)
const editingModel = ref<any>(null)
const form = ref<any>({ id: '', name: '', api_format: 'openai_chat', base_url: 'https://api.openai.com/v1', api_key: '', provider_name: '', reasoning_effort: 'high', description: '' })

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
    form.value = { id: m.id, name: m.name, api_format: m.api_format || 'openai_chat', base_url: m.base_url, api_key: '', provider_name: m.provider_name, reasoning_effort: m.reasoning_effort || 'high', description: m.description }
  } else {
    form.value = { id: '', name: '', api_format: 'openai_chat', base_url: 'https://api.openai.com/v1', api_key: '', provider_name: '', reasoning_effort: 'high', description: '' }
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
  testResult.value = null
  try {
    testResult.value = await api('/api/v1/admin/llm/test', {
      method: 'POST',
      body: JSON.stringify({ model: m.id, base_url: m.base_url, api_format: m.api_format || 'openai_chat', reasoning_effort: m.reasoning_effort || 'auto' }),
    })
  } catch (e: any) {
    testResult.value = { ok: false, error: e.message }
  } finally {
    testLoading.value = false
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
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <p class="text-xs text-[#707E94] font-mono">配置 Base URL、模型、密钥和思考强度后，再到运行单元查看调用遥测。</p>
      </div>
      <button @click="openModal(null)" class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-medium cursor-pointer transition-colors">
        <Plus class="w-3.5 h-3.5" />
        <span>+ 添加自定义模型</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">正在加载模型库...</div>

    <template v-else-if="cfg">
      <!-- Active Model Badge -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <Cpu class="w-5 h-5 text-emerald-400" />
          <div>
            <div class="text-xs text-[#707E94] font-mono">当前激活模型</div>
            <div class="text-sm font-bold text-white font-mono">{{ cfg.active_model_id }}</div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">{{ cfg.active_reasoning_effort?.toUpperCase() }}</span>
          <span class="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">{{ apiFormatBadge(cfg.models?.find((m: any) => m.id === cfg.active_model_id)?.api_format || 'openai_chat') }}</span>
        </div>
      </div>

      <!-- Model Table -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 overflow-x-auto">
        <table class="w-full text-left text-xs font-mono">
          <thead>
            <tr class="text-[#707E94] border-b border-[#1A2232]">
              <th class="pb-2">模型</th>
              <th class="pb-2">供应商</th>
              <th class="pb-2">协议</th>
              <th class="pb-2">思考强度</th>
              <th class="pb-2">Base URL</th>
              <th class="pb-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="m in cfg.models" :key="m.id" :class="{ 'bg-emerald-500/5': m.id === cfg.active_model_id }" class="hover:bg-[#121824]/50">
              <td class="py-2.5">
                <strong class="text-white">{{ m.name || m.id }}</strong>
                <div class="text-[10px] text-[#707E94]">{{ m.id }}</div>
              </td>
              <td class="py-2.5 text-zinc-300">{{ m.provider_name || '自定义' }}</td>
              <td class="py-2.5">
                <span class="text-[10px] font-mono px-1.5 py-0.5 rounded border" :class="{
                  'border-blue-500/30 text-blue-400 bg-blue-500/10': m.api_format === 'openai_chat',
                  'border-emerald-500/30 text-emerald-400 bg-emerald-500/10': m.api_format === 'openai_responses',
                  'border-purple-500/30 text-purple-400 bg-purple-500/10': m.api_format === 'claude_messages',
                }">{{ apiFormatBadge(m.api_format) }}</span>
              </td>
              <td class="py-2.5 text-zinc-300">{{ (m.reasoning_effort || 'high').toUpperCase() }}</td>
              <td class="py-2.5 text-[10px] text-[#707E94] break-all max-w-[200px]">{{ m.base_url }}</td>
              <td class="py-2.5 text-right space-x-1 whitespace-nowrap">
                <span v-if="m.id === cfg.active_model_id" class="text-[10px] font-mono text-emerald-400 font-bold">● 正在使用</span>
                <button v-else @click="activateModel(m.id, m.reasoning_effort)" class="px-2 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-[10px] text-white cursor-pointer">一键启用</button>
                <button @click="runTest(m)" class="px-2 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-[10px] text-white cursor-pointer">⚡ 测试</button>
                <button @click="openModal(m)" class="px-2 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-[10px] text-white cursor-pointer">✏️ 编辑</button>
                <button v-if="m.id !== cfg.active_model_id" @click="deleteModel(m.id)" class="px-2 py-1 rounded bg-[#4d1924] hover:bg-[#5d2230] border border-[#873044] text-[10px] text-[#ffdce1] cursor-pointer">删除</button>
              </td>
            </tr>
            <tr v-if="!cfg.models || cfg.models.length === 0">
              <td colspan="6" class="py-6 text-center text-[#707E94]">暂无自定义模型，点击上方"+ 添加自定义模型"添加</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Test Result -->
      <div v-if="testResult" class="bg-[#0D121B] border rounded-xl p-4" :class="testResult.ok ? 'border-emerald-500/30' : 'border-rose-500/30'">
        <div class="flex items-center space-x-2 mb-2">
          <CheckCircle2 v-if="testResult.ok" class="w-5 h-5 text-emerald-400" />
          <AlertCircle v-else class="w-5 h-5 text-rose-400" />
          <span class="text-sm font-bold" :class="testResult.ok ? 'text-emerald-400' : 'text-rose-400'">
            {{ testResult.ok ? `连接测试通过 (${testResult.latency_ms}ms)` : '连接测试未通过' }}
          </span>
        </div>
        <div v-if="testResult.ok" class="space-y-1 text-xs font-mono text-zinc-300">
          <div>响应预览: <span class="text-white">{{ testResult.response_preview }}</span></div>
          <div v-if="testResult.reasoning_detected" class="text-emerald-400">🧠 成功捕获链式推演输出 · Token: {{ testResult.reasoning_tokens || '已捕获' }}</div>
        </div>
        <div v-else class="text-xs font-mono text-rose-400 break-all">{{ testResult.error || '连接失败' }}</div>
      </div>
    </template>

    <!-- Model Add/Edit Modal -->
    <div v-if="modalVisible" class="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4" @click.self="modalVisible = false">
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-xl p-6 w-full max-w-[620px] max-h-[90vh] overflow-y-auto">
        <h3 class="text-sm font-bold text-white mb-4">{{ editingModel ? '编辑模型' : '添加自定义模型' }}</h3>
        <div class="space-y-3">
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">模型 ID (必填)</label>
            <input v-model="form.id" :readonly="!!editingModel" placeholder="gemini-3.8-flash-high" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">展示名称</label>
            <input v-model="form.name" placeholder="Gemini 3.8 Flash" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">API 协议格式</label>
            <select v-model="form.api_format" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500">
              <option value="openai_chat">OpenAI Chat (/chat/completions)</option>
              <option value="openai_responses">OpenAI Responses (/responses)</option>
              <option value="claude_messages">Claude Messages (/messages)</option>
            </select>
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">Base URL</label>
            <input v-model="form.base_url" placeholder="https://api.openai.com/v1" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">API Key (留空保持现有)</label>
            <input v-model="form.api_key" type="password" placeholder="sk-..." class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">供应商 / 备注</label>
            <input v-model="form.provider_name" placeholder="CPA代理 / 官方直连" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">默认思考强度</label>
            <select v-model="form.reasoning_effort" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500">
              <option value="high">高 · 深度推演</option>
              <option value="medium">中 · 均衡推演</option>
              <option value="low">低 · 快速响应</option>
              <option value="minimal">极简</option>
              <option value="none">关闭</option>
              <option value="auto">自适应</option>
            </select>
          </div>
        </div>
        <div class="flex justify-end space-x-2 mt-5">
          <button @click="modalVisible = false" class="px-3 py-2 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">取消</button>
          <button @click="saveModel" class="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer">保存模型</button>
        </div>
      </div>
    </div>
  </div>
</template>
