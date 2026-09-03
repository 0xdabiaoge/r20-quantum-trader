<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {
  ShieldCheck, ArrowUp, ArrowDown, Plus, Code, Trash2,
  ToggleLeft, ToggleRight, Play, CheckCircle2, AlertTriangle,
  X, Save, Download, FileCode, Sparkles
} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const plugins = ref<any[]>([])
const loading = ref(true)
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' | 'warn' } | null>(null)

// Code Editor Modal State
const editorVisible = ref(false)
const editingFilename = ref('')
const editingCode = ref('')
const editingName = ref('')
const savingCode = ref(false)
const codeError = ref('')

// Sandbox Test State
const testing = ref(false)
const testResults = ref<any>(null)
const testModalVisible = ref(false)

// Create New Plugin State
const createModalVisible = ref(false)
const newFilename = ref('')
const newCode = ref('')
const createError = ref('')

async function loadPlugins() {
  loading.value = true
  try {
    const res = await api('/api/v1/admin/interceptors')
    plugins.value = res.plugins || []
  } catch (e: any) {
    bannerMsg.value = { text: `加载插件失败：${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

async function togglePlugin(p: any) {
  try {
    const nextState = !p.enabled
    await api(`/api/v1/admin/interceptors/${encodeURIComponent(p.filename)}/toggle`, {
      method: 'PUT',
      body: JSON.stringify({ enabled: nextState }),
    })
    p.enabled = nextState
    bannerMsg.value = {
      text: `已${nextState ? '启用' : '停用'}拦截插件「${p.name || p.filename}」`,
      type: 'ok',
    }
  } catch (e: any) {
    bannerMsg.value = { text: `操作失败：${e.message}`, type: 'err' }
  }
}

async function movePlugin(idx: number, dir: -1 | 1) {
  const target = idx + dir
  if (target < 0 || target >= plugins.value.length) return
  const arr = [...plugins.value]
  ;[arr[idx], arr[target]] = [arr[target], arr[idx]]
  plugins.value = arr

  const newOrder = arr.map((x) => x.filename)
  try {
    const res = await api('/api/v1/admin/interceptors/reorder', {
      method: 'POST',
      body: JSON.stringify({ pipeline_order: newOrder }),
    })
    plugins.value = res.plugins || arr
    bannerMsg.value = { text: '已更新拦截管线执行优先级顺序', type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `排序更新失败：${e.message}`, type: 'err' }
    await loadPlugins()
  }
}

async function openEditor(p: any) {
  try {
    const detail = await api(`/api/v1/admin/interceptors/${encodeURIComponent(p.filename)}`)
    editingFilename.value = detail.filename
    editingName.value = detail.name || detail.filename
    editingCode.value = detail.code || ''
    codeError.value = ''
    editorVisible.value = true
  } catch (e: any) {
    bannerMsg.value = { text: `读取插件源码失败：${e.message}`, type: 'err' }
  }
}

async function saveCode() {
  savingCode.value = true
  codeError.value = ''
  try {
    await api(`/api/v1/admin/interceptors/${encodeURIComponent(editingFilename.value)}/code`, {
      method: 'PUT',
      body: JSON.stringify({ code: editingCode.value }),
    })
    bannerMsg.value = { text: `✅ 插件「${editingFilename.value}」代码已保存并热加载生效`, type: 'ok' }
    editorVisible.value = false
    await loadPlugins()
  } catch (e: any) {
    codeError.value = e.message
  } finally {
    savingCode.value = false
  }
}

function exportPluginCode(filename: string, code: string) {
  const blob = new Blob([code], { type: 'text/x-python' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function deletePlugin(p: any) {
  if (!confirm(`确定删除拦截插件「${p.name || p.filename}」？\n文件将被从磁盘彻底移除。`)) return
  try {
    await api(`/api/v1/admin/interceptors/${encodeURIComponent(p.filename)}`, { method: 'DELETE' })
    bannerMsg.value = { text: `已删除插件「${p.filename}」`, type: 'ok' }
    await loadPlugins()
  } catch (e: any) {
    bannerMsg.value = { text: `删除失败：${e.message}`, type: 'err' }
  }
}

async function runSandbox() {
  testing.value = true
  try {
    testResults.value = await api('/api/v1/admin/interceptors/test', {
      method: 'POST',
      body: '{}',
    })
    testModalVisible.value = true
  } catch (e: any) {
    bannerMsg.value = { text: `沙箱回归测试执行失败：${e.message}`, type: 'err' }
  } finally {
    testing.value = false
  }
}

function openCreateModal() {
  newFilename.value = `custom_interceptor_${Date.now().toString(36)}.py`
  newCode.value = `"""
R20 物理拦截插件规范
====================
id: my_custom_rule
name: 我的自定义风控规则
version: 1.0.0
author: ${auth.user?.username || 'Trader'}
description: 描述你的专有物理拦截规则
tags: 自定义, 策略广场
"""

def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    """
    检查交易候选风控指标:
    - package: 包含标的行情与动力学数据 (macro_4h, velocity_v, acceleration_a, adx_1h 等)
    - decision: 包含 AI 主脑建议 (action, confidence, entry_price, take_profit_price, stop_loss_price)
    - context: 包含持仓上下文与可用资金

    返回 (True, "") 表示放行通过；
    返回 (False, "具体拦截原因") 表示拦截并安全重写为 WAIT。
    """
    action = str(decision.get("action", "WAIT")).upper()
    if action == "WAIT":
        return True, ""

    # 编写你的风控卡点规则...
    return True, ""
`
  createError.value = ''
  createModalVisible.value = true
}

async function submitCreate() {
  createError.value = ''
  if (!newFilename.value.trim()) {
    createError.value = '请输入插件文件名'
    return
  }
  try {
    const res = await api('/api/v1/admin/interceptors', {
      method: 'POST',
      body: JSON.stringify({
        filename: newFilename.value.trim(),
        code: newCode.value,
      }),
    })
    bannerMsg.value = { text: `🎉 成功创建拦截插件「${res.name || res.filename}」！`, type: 'ok' }
    createModalVisible.value = false
    await loadPlugins()
  } catch (e: any) {
    createError.value = e.message
  }
}

onMounted(loadPlugins)
</script>

<template>
  <div class="space-y-4 font-mono text-xs">
    <!-- Header & Action Bar -->
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center space-x-2.5">
        <div class="w-8 h-8 rounded-lg bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
          <ShieldCheck class="w-4 h-4" />
        </div>
        <div>
          <h1 class="text-sm font-bold text-white uppercase tracking-wide">物理拦截插件配置中心</h1>
          <p class="text-[11px] text-[#707E94] font-sans">
            所有交易决策发出前必须通过 Python 物理拦截插件管线 (Fail-Closed)。支持热插拔、热编辑与策略广场插件生态。
          </p>
        </div>
      </div>
      <div class="flex items-center space-x-2">
        <button
          @click="runSandbox"
          :disabled="testing"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1a2b42] border border-[#23354d] text-emerald-400 hover:text-emerald-300 font-bold transition-all cursor-pointer shadow-sm disabled:opacity-50"
        >
          <Play class="w-3.5 h-3.5" />
          <span>{{ testing ? '正在回归测试...' : '⚡ 现场沙箱回归测试' }}</span>
        </button>
        <button
          v-if="auth.isSuperadmin"
          @click="openCreateModal"
          class="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold transition-all cursor-pointer shadow-md shadow-blue-500/20"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>新建拦截插件</span>
        </button>
        <span class="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded border border-emerald-500/20 font-bold">
          FAIL-CLOSED 物理防线
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
    <div v-if="loading" class="py-12 text-center text-xs text-[#707E94]">正在扫描加载物理拦截插件...</div>

    <!-- Plugins Pipeline List -->
    <div v-else class="space-y-3">
      <div
        v-for="(p, idx) in plugins"
        :key="p.filename"
        class="bg-[#0D121B] border rounded-xl p-4 sm:p-5 transition-all shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-4"
        :class="p.enabled ? 'border-[#233147] hover:border-blue-500/50' : 'border-[#1A2232] opacity-60'"
      >
        <!-- Left: Order & Meta -->
        <div class="flex items-start space-x-3.5 min-w-0 flex-1">
          <!-- Ordering Buttons -->
          <div class="flex flex-col space-y-1 shrink-0 pt-0.5">
            <button
              @click="movePlugin(idx, -1)"
              :disabled="idx === 0"
              class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] hover:text-white disabled:opacity-20 cursor-pointer"
              title="提高执行优先级"
            >
              <ArrowUp class="w-3.5 h-3.5" />
            </button>
            <button
              @click="movePlugin(idx, 1)"
              :disabled="idx === plugins.length - 1"
              class="p-1 rounded hover:bg-[#151D2C] text-[#707E94] hover:text-white disabled:opacity-20 cursor-pointer"
              title="降低执行优先级"
            >
              <ArrowDown class="w-3.5 h-3.5" />
            </button>
          </div>

          <!-- Title, Description & Tags -->
          <div class="space-y-1.5 min-w-0 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              <span class="w-6 h-6 rounded-md bg-[#141B26] border border-[#20293A] text-zinc-300 font-bold flex items-center justify-center text-[11px]">
                #{{ idx + 1 }}
              </span>
              <h3 class="text-sm font-bold text-white tracking-wide truncate">
                {{ p.name || p.filename }}
              </h3>
              <span class="px-2 py-0.5 rounded text-[10px] font-mono text-zinc-400 bg-[#141B26] border border-[#1A2232]">
                {{ p.filename }}
              </span>
              <span v-if="p.version" class="px-1.5 py-0.2 rounded text-[10px] text-blue-400 bg-blue-500/10 border border-blue-500/20 font-bold">
                v{{ p.version }}
              </span>
              <span v-if="p.author" class="text-[10px] text-[#707E94]">
                by {{ p.author }}
              </span>
            </div>

            <p class="text-xs text-[#8A99AD] font-sans leading-relaxed">
              {{ p.description || '暂无详细描述' }}
            </p>

            <!-- Tags -->
            <div v-if="p.tags && p.tags.length > 0" class="flex flex-wrap gap-1.5 pt-1">
              <span
                v-for="t in p.tags"
                :key="t"
                class="px-2 py-0.5 rounded text-[10px] bg-[#080B10] border border-[#1A2232] text-[#8A99AD]"
              >
                {{ t }}
              </span>
            </div>

            <div v-if="p.error" class="text-[11px] text-rose-400 flex items-center space-x-1 pt-1">
              <AlertTriangle class="w-3.5 h-3.5 shrink-0" />
              <span>{{ p.error }}</span>
            </div>
          </div>
        </div>

        <!-- Right: Controls & Actions -->
        <div class="flex items-center justify-end space-x-2 shrink-0 border-t md:border-t-0 border-[#1A2232] pt-3 md:pt-0">
          <button
            @click="openEditor(p)"
            class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#111c2a] hover:bg-[#1a2b42] border border-[#23354d] text-[#b8c4d4] hover:text-white font-bold cursor-pointer transition-colors"
            title="查看或修改 Python 源码"
          >
            <Code class="w-3.5 h-3.5 text-blue-400" />
            <span>源码与规则</span>
          </button>

          <button
            v-if="auth.isSuperadmin && !p.filename.startsWith('0')"
            @click="deletePlugin(p)"
            class="p-2 rounded-lg hover:bg-[#4d1924] text-[#707E94] hover:text-rose-400 cursor-pointer transition-colors"
            title="删除插件"
          >
            <Trash2 class="w-4 h-4" />
          </button>

          <button
            @click="togglePlugin(p)"
            class="cursor-pointer transition-colors p-1"
            :class="p.enabled ? 'text-emerald-400' : 'text-[#707E94]'"
            :title="p.enabled ? '已启用 (点击停用)' : '已停用 (点击启用)'"
          >
            <ToggleRight v-if="p.enabled" class="w-6 h-6" />
            <ToggleLeft v-else class="w-6 h-6" />
          </button>
        </div>
      </div>
    </div>

    <!-- Code Editor Modal -->
    <div
      v-if="editorVisible"
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      @click.self="editorVisible = false"
    >
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-2xl p-5 sm:p-6 w-full max-w-4xl max-h-[92dvh] flex flex-col shadow-2xl space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2.5">
            <div class="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center">
              <FileCode class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-white flex items-center space-x-2">
                <span>{{ editingName }}</span>
                <span class="text-xs text-[#707E94] font-normal">({{ editingFilename }})</span>
              </h3>
              <p class="text-[10px] text-[#707E94]">Python 源码热更新，保存后下一轮决策实时执行</p>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <button
              @click="exportPluginCode(editingFilename, editingCode)"
              class="flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-[#141B26] border border-[#23354d] text-zinc-300 hover:text-white cursor-pointer"
              title="导出当前 .py 脚本文件"
            >
              <Download class="w-3.5 h-3.5" />
              <span>导出 .py</span>
            </button>
            <button @click="editorVisible = false" class="text-[#707E94] hover:text-white cursor-pointer p-1">
              <X class="w-4 h-4" />
            </button>
          </div>
        </div>

        <div v-if="codeError" class="p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400">
          {{ codeError }}
        </div>

        <div class="flex-1 min-h-[360px] flex flex-col">
          <textarea
            v-model="editingCode"
            class="flex-1 w-full bg-[#080B10] border border-[#1A2232] rounded-xl text-zinc-200 p-4 font-mono text-xs leading-relaxed outline-none focus:border-blue-500 resize-none select-text"
            spellcheck="false"
          ></textarea>
        </div>

        <div class="flex items-center justify-between pt-3 border-t border-[#1A2232]">
          <span class="text-[11px] text-[#707E94]">标准接口: def check_risk(package, decision, context) -> tuple[bool, str]</span>
          <div class="flex items-center space-x-2">
            <button
              @click="editorVisible = false"
              class="px-4 py-2 rounded-xl bg-[#141B26] hover:bg-[#1e2738] text-zinc-300 text-xs cursor-pointer"
            >
              取消
            </button>
            <button
              @click="saveCode"
              :disabled="savingCode"
              class="flex items-center space-x-1.5 px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs cursor-pointer transition-all shadow-md shadow-blue-500/20 disabled:opacity-50"
            >
              <Save class="w-4 h-4" />
              <span>{{ savingCode ? '正在校验并保存...' : '保存代码并热加载' }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <div
      v-if="createModalVisible"
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      @click.self="createModalVisible = false"
    >
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-2xl p-5 sm:p-6 w-full max-w-2xl max-h-[92dvh] flex flex-col shadow-2xl space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2.5">
            <div class="w-7 h-7 rounded-lg bg-blue-600/20 text-blue-400 flex items-center justify-center">
              <Sparkles class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-white">新建物理拦截插件</h3>
              <p class="text-[10px] text-[#707E94]">编写自定义 Python 拦截规则，适配策略广场规范</p>
            </div>
          </div>
          <button @click="createModalVisible = false" class="text-[#707E94] hover:text-white cursor-pointer p-1">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div v-if="createError" class="p-3 rounded-lg text-xs bg-rose-500/10 border border-rose-500/20 text-rose-400">
          {{ createError }}
        </div>

        <div>
          <label class="block text-xs font-bold text-zinc-300 mb-1.5">插件文件名 (.py)</label>
          <input
            v-model="newFilename"
            type="text"
            class="w-full bg-[#080B10] border border-[#1A2232] rounded-xl text-white px-3 py-2 text-xs outline-none focus:border-blue-500"
            placeholder="如: my_volatility_filter.py"
          />
        </div>

        <div class="flex-1 min-h-[280px] flex flex-col">
          <label class="block text-xs font-bold text-zinc-300 mb-1.5">插件 Python 源码</label>
          <textarea
            v-model="newCode"
            class="flex-1 w-full bg-[#080B10] border border-[#1A2232] rounded-xl text-zinc-200 p-3.5 font-mono text-xs leading-relaxed outline-none focus:border-blue-500 resize-y"
            spellcheck="false"
          ></textarea>
        </div>

        <div class="flex items-center justify-end space-x-2 pt-3 border-t border-[#1A2232]">
          <button
            @click="createModalVisible = false"
            class="px-4 py-2 rounded-xl bg-[#141B26] hover:bg-[#1e2738] text-zinc-300 text-xs cursor-pointer"
          >
            取消
          </button>
          <button
            @click="submitCreate"
            class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs cursor-pointer transition-all shadow-md shadow-blue-500/20"
          >
            创建并加入管线
          </button>
        </div>
      </div>
    </div>

    <!-- Sandbox Test Results Modal -->
    <div
      v-if="testModalVisible && testResults"
      class="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4"
      @click.self="testModalVisible = false"
    >
      <div class="bg-gradient-to-b from-[#111a29] to-[#0D121B] border border-[#1A2232] rounded-2xl p-5 sm:p-6 w-full max-w-3xl max-h-[90dvh] overflow-y-auto shadow-2xl space-y-4">
        <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2.5">
            <div class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-400 flex items-center justify-center">
              <Play class="w-4 h-4" />
            </div>
            <div>
              <h3 class="text-sm font-bold text-white">沙箱拦截回归测试报告</h3>
              <p class="text-[10px] text-[#707E94]">
                已激活 {{ testResults.enabled_plugins_count }}/{{ testResults.total_plugins_count }} 个拦截插件 · 总执行耗时 {{ testResults.duration_total_ms }}ms
              </p>
            </div>
          </div>
          <button @click="testModalVisible = false" class="text-[#707E94] hover:text-white cursor-pointer p-1">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="space-y-3">
          <div
            v-for="(r, i) in testResults.results"
            :key="i"
            class="p-3.5 rounded-xl border transition-all"
            :class="r.intercepted ? 'bg-amber-500/5 border-amber-500/20' : 'bg-emerald-500/5 border-emerald-500/20'"
          >
            <div class="flex items-center justify-between mb-1.5">
              <span class="text-xs font-bold text-white">{{ r.scenario }}</span>
              <div class="flex items-center space-x-2">
                <span class="text-[10px] font-mono text-[#707E94]">{{ r.duration_ms }}ms</span>
                <span
                  class="px-2 py-0.5 rounded text-[10px] font-bold"
                  :class="r.intercepted ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30' : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'"
                >
                  {{ r.intercepted ? '🛑 已成功物理拦截 (WAIT)' : '🟢 顺势放行通过' }}
                </span>
              </div>
            </div>
            <div class="text-[11px] text-zinc-300 font-mono flex items-center space-x-3">
              <span>原始意向: <strong class="text-white">{{ r.raw_action }}</strong></span>
              <span>最终指令: <strong :class="r.final_action === 'WAIT' ? 'text-amber-400' : 'text-emerald-400'">{{ r.final_action }}</strong></span>
              <span v-if="r.risk_reward !== '--'">盈亏比: {{ r.risk_reward }}</span>
            </div>
            <div v-if="r.reason" class="text-[11px] text-amber-300 mt-1 font-sans">
              拦截审计：{{ r.reason }}
            </div>
          </div>
        </div>

        <div class="flex justify-end pt-3 border-t border-[#1A2232]">
          <button
            @click="testModalVisible = false"
            class="px-5 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs cursor-pointer"
          >
            关闭测试报告
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
