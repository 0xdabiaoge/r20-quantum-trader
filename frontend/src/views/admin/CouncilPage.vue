<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import {
  Users,
  Shield,
  Zap,
  Cpu,
  Save,
  RotateCcw,
  Play,
  Plus,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Sliders,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Gauge,
  Coins,
  Eye,
  SlidersHorizontal,
  Layers,
  HelpCircle,
} from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()

const loading = ref(true)
const saving = ref(false)
const testing = ref(false)
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' | 'warn' } | null>(null)

const councilConfig = ref<any>({
  enabled: false,
  consensus_mode: 'strict',
  timeout_seconds: 60.0,
  roles: {},
})

const availablePresets = ref<any[]>([])
const availableSuites = ref<any[]>([])
const availableModels = ref<any[]>([])
const expandedRole = ref<string>('alpha')
const testResult = ref<any>(null)
const expandedReasoning = ref<Record<string, boolean>>({})

const consensusModes = [
  {
    id: 'strict',
    name: '一票否决制 (Paranoid Veto)',
    tag: '稳健首选 · 胜率优先',
    desc: '胜率高于一切。只要有任何参谋（特别是风控官或数理官）提出量价背离或假突破，强制一票否决观望 WAIT。',
  },
  {
    id: 'weighted',
    name: '加权共识制 (Weighted Majority)',
    tag: '平衡周密 · 概率驱动',
    desc: '综合参谋权重。顺势方向加权支持度超过 60% 且无极端黑天鹅时批准入场，按风控建议缩减保证金。',
  },
  {
    id: 'aggressive',
    name: '动能突破优先 (Alpha Hunter)',
    tag: '顺势进攻 · 猎手风格',
    desc: '重点关注一阶速度与二阶加速度爆发，动量官或巨鲸流向确认时，允许小仓位试探开单（配合云端止损）。',
  },
]

const roleIcons: Record<string, any> = {
  alpha: Zap,
  risk: Shield,
  quant: Cpu,
  arbitrator: Users,
  news_scout: Sparkles,
  macro: Sliders,
  orderbook: Cpu,
  funding_arb: Coins,
  whale_tracker: Eye,
  custom: Users,
}

const roleColors: Record<string, string> = {
  alpha: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  risk: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
  quant: 'text-cyan-400 border-cyan-500/30 bg-cyan-500/10',
  arbitrator: 'text-purple-400 border-purple-500/30 bg-purple-500/10',
  news_scout: 'text-blue-400 border-blue-500/30 bg-blue-500/10',
  macro: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  orderbook: 'text-orange-400 border-orange-500/30 bg-orange-500/10',
  funding_arb: 'text-yellow-400 border-yellow-500/30 bg-yellow-500/10',
  whale_tracker: 'text-teal-400 border-teal-500/30 bg-teal-500/10',
  custom: 'text-indigo-400 border-indigo-500/30 bg-indigo-500/10',
}

async function loadData() {
  loading.value = true
  try {
    const [cRes, mRes] = await Promise.all([
      api('/api/v1/admin/council/config'),
      api('/api/v1/admin/llm/models'),
    ])
    councilConfig.value = cRes
    availablePresets.value = cRes.available_presets || []
    availableSuites.value = cRes.available_suites || []
    availableModels.value = mRes.models || []
  } catch (e: any) {
    bannerMsg.value = { text: `加载配置失败: ${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (!auth.isSuperadmin) {
    bannerMsg.value = { text: '仅超级管理员可修改委员会决策配置', type: 'err' }
    return
  }
  saving.value = true
  try {
    const res = await api('/api/v1/admin/council/config', {
      method: 'PUT',
      body: JSON.stringify({
        enabled: councilConfig.value.enabled,
        consensus_mode: councilConfig.value.consensus_mode || 'strict',
        timeout_seconds: Number(councilConfig.value.timeout_seconds) || 60.0,
        roles: councilConfig.value.roles,
      }),
    })
    councilConfig.value = res.config
    bannerMsg.value = {
      text: councilConfig.value.enabled
        ? `✅ 多模型协作委员会已保存并开启！裁决共识机制：【${consensusModes.find((m) => m.id === councilConfig.value.consensus_mode)?.name}】。`
        : '✅ 委员会配置已保存（当前处于单模型极速模式）。',
      type: 'ok',
    }
  } catch (e: any) {
    bannerMsg.value = { text: `保存失败: ${e.message}`, type: 'err' }
  } finally {
    saving.value = false
  }
}

async function applySuite(suiteId: string) {
  if (!auth.isSuperadmin) return
  const suite = availableSuites.value.find((s) => s.id === suiteId)
  if (!confirm(`确定一键载入【${suite?.name || suiteId}】吗？\n这将重置当前委员会席位配置为该推荐套件。`)) return
  try {
    const res = await api('/api/v1/admin/council/apply-suite', {
      method: 'POST',
      body: JSON.stringify({ suite_id: suiteId }),
    })
    councilConfig.value = res.config
    bannerMsg.value = { text: `🎉 已成功载入【${suite?.name || suiteId}】！`, type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `载入套件失败: ${e.message}`, type: 'err' }
  }
}

function addNewRole(presetKey: string = 'custom') {
  if (!auth.isSuperadmin) return
  const preset = availablePresets.value.find((p) => p.id === presetKey) || {
    name: '新专家参谋',
    role_title: '专项策略 / 自定义视角',
    description: '由用户自定义的独立专家角色',
    prompt: '【角色：R20 自定义量化专家】\n请严格依据你设定的专业分析逻辑，对输入的各币种数据进行研判并输出核心意见（50字内/币种）。',
    weight: 0.3,
    enabled: true,
    reasoning_effort: 'medium',
    temperature: 0.3,
    is_arbitrator: false,
    model_id: '',
  }

  const roleId = `role_${Date.now().toString(36)}`
  councilConfig.value.roles[roleId] = {
    id: roleId,
    name: preset.name,
    role_title: preset.role_title || '自定义专家',
    description: preset.description || '',
    prompt: preset.prompt,
    weight: preset.weight || 0.3,
    enabled: true,
    reasoning_effort: preset.reasoning_effort || 'medium',
    temperature: preset.temperature || 0.3,
    is_arbitrator: false,
    model_id: '',
  }
  expandedRole.value = roleId
  bannerMsg.value = { text: `已添加【${preset.name}】，可直接在卡片上微调参数、权重及提示词`, type: 'ok' }
}

function removeRole(roleId: string) {
  if (!auth.isSuperadmin) return
  const role = councilConfig.value.roles[roleId]
  if (role?.is_arbitrator || roleId === 'arbitrator') {
    alert('首席终审仲裁官负责最终生成交易所发单 JSON 契约，不可删除！')
    return
  }
  if (!confirm(`确定删除角色【${role?.name || roleId}】吗？`)) return
  delete councilConfig.value.roles[roleId]
  bannerMsg.value = { text: `已移除该角色，点击「保存委员会配置」后生效`, type: 'warn' }
}

async function resetRole(roleId: string) {
  if (!confirm(`确定将【${councilConfig.value.roles[roleId]?.name || roleId}】恢复为初始预设模板吗？`)) return
  try {
    const res = await api('/api/v1/admin/council/reset-role', {
      method: 'POST',
      body: JSON.stringify({ role_id: roleId }),
    })
    councilConfig.value = res.config
    bannerMsg.value = { text: `已将角色恢复为出厂模板`, type: 'ok' }
  } catch (e: any) {
    bannerMsg.value = { text: `恢复失败: ${e.message}`, type: 'err' }
  }
}

async function runDebateTest() {
  testing.value = true
  testResult.value = null
  expandedReasoning.value = {}
  bannerMsg.value = { text: '正在并发调度各专家参谋并由首席仲裁官终审，请稍候（预计 8~25 秒）...', type: 'warn' }
  try {
    const res = await api('/api/v1/admin/council/test', {
      method: 'POST',
      body: JSON.stringify({}),
    })
    if (res.status === 'ok') {
      testResult.value = res
      bannerMsg.value = { text: `✅ 委员会现场辩论完成！总耗时 ${res.transcript?.total_duration_ms || 0}ms`, type: 'ok' }
    } else {
      bannerMsg.value = { text: `测试失败: ${res.error || '未知错误'}`, type: 'err' }
    }
  } catch (e: any) {
    bannerMsg.value = { text: `测试出错: ${e.message}`, type: 'err' }
  } finally {
    testing.value = false
  }
}

onMounted(loadData)
</script>

<template>
  <div class="space-y-4">
    <!-- Header info -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center space-x-2">
        <Sparkles class="w-4 h-4 text-purple-400" />
        <p class="text-xs text-[#8A99AD] font-mono">
          多模型委员会决策系统：支持席位启停、共识模式切换、独立长思考链配置、预设套件一键载入与现场辩论审计。
        </p>
      </div>
      <span class="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-1 rounded border border-purple-500/20">
        多模型协作 · v6.5.1 升级版
      </span>
    </div>

    <!-- Alert / Notice Banner -->
    <div
      v-if="bannerMsg"
      class="p-3 rounded-lg text-xs font-mono border"
      :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : bannerMsg.type === 'warn' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'"
    >
      {{ bannerMsg.text }}
    </div>

    <!-- Master Switch & Performance Mode Card -->
    <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4 shadow-lg space-y-4">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#1A2232]">
        <div class="flex items-center space-x-3">
          <div class="p-2.5 rounded-xl bg-gradient-to-tr from-purple-600/30 to-blue-600/20 border border-purple-500/30 text-purple-400">
            <Users class="w-6 h-6" />
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <h2 class="text-sm font-bold text-white font-mono">多角色模型委员会决策机制</h2>
              <span
                class="text-[10px] font-mono font-bold px-2 py-0.5 rounded border"
                :class="councilConfig.enabled ? 'text-purple-400 bg-purple-500/10 border-purple-500/30' : 'text-zinc-400 bg-zinc-800/30 border-zinc-700/30'"
              >
                {{ councilConfig.enabled ? '● 委员会辩论模式 (胜率与风控优先)' : '○ 单模型极速模式 (时延优先)' }}
              </span>
            </div>
            <p class="text-xs text-[#707E94] font-mono mt-0.5">
              关闭时以当前主脑单模型直接推理 (~2s)；开启时多模型参谋多线程辩论博弈并由首席仲裁官收口 (~15-40s)。
            </p>
          </div>
        </div>

        <!-- Big Toggle Switch -->
        <div class="flex items-center space-x-3 shrink-0">
          <button
            type="button"
            @click="councilConfig.enabled = !councilConfig.enabled"
            class="relative inline-flex items-center cursor-pointer focus:outline-none"
            :disabled="!auth.isSuperadmin"
          >
            <div
              class="w-14 h-7 rounded-full transition-colors relative"
              :class="councilConfig.enabled ? 'bg-purple-600' : 'bg-zinc-800'"
            >
              <div
                class="absolute top-[2px] left-[2px] bg-white rounded-full h-6 w-6 transition-transform shadow-md"
                :class="councilConfig.enabled ? 'translate-x-7' : 'translate-x-0'"
              ></div>
            </div>
          </button>
          <span class="text-xs font-mono font-bold text-white">
            {{ councilConfig.enabled ? '已开启' : '已停用' }}
          </span>
        </div>
      </div>

      <!-- Consensus Mode Selection Grid -->
      <div>
        <div class="flex items-center space-x-2 mb-2">
          <SlidersHorizontal class="w-3.5 h-3.5 text-purple-400" />
          <span class="text-xs font-bold text-white font-mono">辩论裁决共识机制 (Consensus Mode)</span>
          <span class="text-[10px] text-[#707E94] font-mono">指导首席仲裁官权衡各方争辩的裁量原则</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          <div
            v-for="mode in consensusModes"
            :key="mode.id"
            @click="auth.isSuperadmin && (councilConfig.consensus_mode = mode.id)"
            class="p-3 rounded-xl border transition-all cursor-pointer"
            :class="councilConfig.consensus_mode === mode.id ? 'border-purple-500 bg-purple-500/10 shadow-sm shadow-purple-500/10' : 'border-[#1A2232] bg-[#090F18] hover:border-zinc-700'"
          >
            <div class="flex items-center justify-between mb-1">
              <span class="text-xs font-bold text-white font-mono">{{ mode.name }}</span>
              <span class="text-[9px] px-1.5 py-0.2 rounded font-mono border" :class="councilConfig.consensus_mode === mode.id ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' : 'bg-zinc-800 text-zinc-400 border-zinc-700'">
                {{ mode.tag }}
              </span>
            </div>
            <p class="text-[11px] text-[#8A99AD] font-sans leading-relaxed">
              {{ mode.desc }}
            </p>
          </div>
        </div>
      </div>

      <!-- One-Click Preset Suites Bar -->
      <div v-if="availableSuites.length > 0" class="pt-2 border-t border-[#1A2232]">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex items-center space-x-1.5 text-xs text-[#8A99AD] font-mono">
            <Layers class="w-3.5 h-3.5 text-blue-400" />
            <span>推荐参谋套件一键载入:</span>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="s in availableSuites"
              :key="s.id"
              @click="applySuite(s.id)"
              :disabled="!auth.isSuperadmin"
              class="px-2.5 py-1 rounded-lg bg-[#111C2A] hover:bg-[#1A2B42] border border-[#23354D] text-xs font-mono text-zinc-200 hover:text-white transition-all cursor-pointer"
              :title="s.description"
            >
              {{ s.name }}
            </button>
          </div>
        </div>
      </div>

      <!-- Settings Sub-bar -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-[#1A2232]">
        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="text-[11px] text-[#8997aa] font-mono">委员会硬超时熔断 (秒)</label>
            <span class="text-[10px] font-mono text-purple-400">支持 10 ~ 300 秒</span>
          </div>
          <input
            v-model="councilConfig.timeout_seconds"
            type="number"
            min="10"
            max="300"
            step="5"
            class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-1.5 text-xs font-mono outline-none focus:border-purple-500"
            :disabled="!auth.isSuperadmin"
          />
          <span class="text-[10px] text-[#707E94] font-mono mt-1 block leading-relaxed">
            💡 推荐配置：若参谋绑定了带深度思考链（Reasoning Effort: High）的模型，建议设为 <strong>60~90 秒</strong>。
          </span>
        </div>
        <div class="flex items-end space-x-2 pb-1">
          <button
            @click="saveConfig"
            :disabled="saving || !auth.isSuperadmin"
            class="flex-1 flex items-center justify-center space-x-1.5 px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 text-white text-xs font-mono font-bold cursor-pointer disabled:opacity-40 shadow-md shadow-purple-600/20"
          >
            <Save class="w-3.5 h-3.5" />
            <span>{{ saving ? '保存中...' : '保存委员会配置' }}</span>
          </button>
          <button
            @click="runDebateTest"
            :disabled="testing"
            class="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-[#111c2a] hover:bg-[#1d3050] border border-[#33445b] text-xs font-mono text-purple-300 cursor-pointer disabled:opacity-40"
          >
            <Play class="w-3.5 h-3.5" :class="{ 'animate-spin': testing }" />
            <span>{{ testing ? '辩论测试中...' : '⚡ 现场辩论测试' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Council Roles Management Header -->
    <div class="flex flex-wrap items-center justify-between gap-2 pt-1">
      <div class="flex items-center space-x-2">
        <h3 class="text-xs font-bold text-white font-mono uppercase">
          参谋与仲裁席位 ({{ Object.keys(councilConfig.roles || {}).length }} 个角色 · {{ Object.values(councilConfig.roles || {}).filter((r: any) => r.enabled !== false).length }} 活跃)
        </h3>
        <span class="text-[10px] text-[#707E94] font-mono">支持自由启闭与参数定制</span>
      </div>

      <!-- Add Role Preset Dropdown Buttons -->
      <div class="flex items-center space-x-1.5 overflow-x-auto pb-0.5">
        <span class="text-[11px] font-mono text-[#707E94] shrink-0">添加参谋:</span>
        <button
          @click="addNewRole('custom')"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-dashed border-[#33445b] text-[11px] font-mono text-purple-300 cursor-pointer"
        >
          <Plus class="w-3 h-3" />
          <span>自定义参谋</span>
        </button>
        <button
          @click="addNewRole('funding_arb')"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-dashed border-[#33445b] text-[11px] font-mono text-yellow-300 cursor-pointer"
          title="资金费率与合约溢价套利官"
        >
          <Plus class="w-3 h-3" />
          <span>费率套利官</span>
        </button>
        <button
          @click="addNewRole('whale_tracker')"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-dashed border-[#33445b] text-[11px] font-mono text-teal-300 cursor-pointer"
          title="OKX Top100 巨鲸筹码追踪官"
        >
          <Plus class="w-3 h-3" />
          <span>巨鲸追踪官</span>
        </button>
        <button
          @click="addNewRole('news_scout')"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-dashed border-[#33445b] text-[11px] font-mono text-blue-300 cursor-pointer"
          title="全网突发资讯与链上异动"
        >
          <Plus class="w-3 h-3" />
          <span>舆情侦察官</span>
        </button>
        <button
          @click="addNewRole('macro')"
          :disabled="!auth.isSuperadmin"
          class="flex items-center space-x-1 px-2.5 py-1 rounded bg-[#111c2a] hover:bg-[#1d3050] border border-dashed border-[#33445b] text-[11px] font-mono text-emerald-300 cursor-pointer"
          title="宏观经济流动性与大盘贝塔"
        >
          <Plus class="w-3 h-3" />
          <span>宏观策略官</span>
        </button>
      </div>
    </div>

    <!-- Council Roles Cards Grid/List -->
    <div class="space-y-3">
      <div
        v-for="(role, roleId) in councilConfig.roles"
        :key="roleId"
        class="bg-[#0D121B] border rounded-xl p-4 transition-all"
        :class="[
          expandedRole === roleId ? 'border-purple-500/40 bg-[#0E131E]' : 'border-[#1A2232]',
          role.enabled === false ? 'opacity-50' : ''
        ]"
      >
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <!-- Role Main Info -->
          <div class="flex items-center space-x-3 min-w-0 flex-1">
            <span
              class="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-xs border shrink-0"
              :class="roleColors[roleId] || roleColors['custom']"
            >
              <component :is="roleIcons[roleId] || roleIcons['custom']" class="w-4 h-4" />
            </span>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <!-- Editable Role Name -->
                <input
                  v-model="role.name"
                  class="bg-transparent border-b border-dashed border-zinc-700 hover:border-purple-400 focus:border-purple-500 text-sm font-bold text-white font-mono outline-none max-w-[260px]"
                  :readonly="!auth.isSuperadmin"
                  placeholder="角色名称"
                />
                <!-- Editable Role Subtitle -->
                <input
                  v-model="role.role_title"
                  class="bg-[#090f18] border border-[#1A2232] rounded px-1.5 py-0.2 text-[10px] font-mono text-zinc-400 outline-none max-w-[160px]"
                  :readonly="!auth.isSuperadmin"
                  placeholder="职责标签"
                />
                <span
                  v-if="role.is_arbitrator || roleId === 'arbitrator'"
                  class="text-[9px] font-mono font-bold text-purple-400 bg-purple-500/10 px-1.5 py-0.2 rounded border border-purple-500/25 shrink-0"
                >
                  ⚖️ 首席终审席位
                </span>
                <span
                  v-else
                  class="text-[9px] font-mono px-1.5 py-0.2 rounded border shrink-0"
                  :class="role.enabled !== false ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-zinc-800 text-zinc-500 border-zinc-700'"
                >
                  {{ role.enabled !== false ? '活跃席位' : '已静音' }}
                </span>
              </div>
              <input
                v-model="role.description"
                class="w-full bg-transparent border-0 text-[11px] text-[#707E94] font-mono mt-0.5 outline-none"
                :readonly="!auth.isSuperadmin"
                placeholder="简明描述此角色的研判视角..."
              />
            </div>
          </div>

          <!-- Controls & Parameters -->
          <div class="flex flex-wrap items-center justify-end gap-2 shrink-0">
            <!-- Model Binding Select -->
            <div class="flex items-center space-x-1">
              <span class="text-[10px] font-mono text-[#707E94] hidden lg:inline">模型:</span>
              <select
                v-model="role.model_id"
                class="bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-2 py-1 text-xs font-mono outline-none focus:border-purple-500 max-w-[140px]"
                :disabled="!auth.isSuperadmin"
              >
                <option value="">(默认模型)</option>
                <option v-for="m in availableModels" :key="m.id" :value="m.id">
                  {{ m.name || m.id }}
                </option>
              </select>
            </div>

            <!-- Weight Input -->
            <div v-if="!role.is_arbitrator && roleId !== 'arbitrator'" class="flex items-center space-x-1">
              <span class="text-[10px] font-mono text-[#707E94]">权重:</span>
              <input
                v-model="role.weight"
                type="number"
                step="0.05"
                min="0.1"
                max="1.0"
                class="w-14 bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-1.5 py-1 text-xs font-mono outline-none text-center"
                :disabled="!auth.isSuperadmin"
              />
            </div>

            <!-- Enable/Mute Toggle (Non-arbitrators) -->
            <button
              v-if="!role.is_arbitrator && roleId !== 'arbitrator'"
              @click="role.enabled = role.enabled === false ? true : false"
              :disabled="!auth.isSuperadmin"
              class="cursor-pointer transition-colors p-1"
              :class="role.enabled !== false ? 'text-emerald-400' : 'text-zinc-600'"
              :title="role.enabled !== false ? '点击静音此参谋' : '点击激活此参谋'"
            >
              <ToggleRight v-if="role.enabled !== false" class="w-5 h-5" />
              <ToggleLeft v-else class="w-5 h-5" />
            </button>

            <!-- Delete Role (Disabled for arbitrator) -->
            <button
              v-if="!role.is_arbitrator && roleId !== 'arbitrator'"
              @click="removeRole(String(roleId))"
              :disabled="!auth.isSuperadmin"
              class="p-1.5 rounded hover:bg-[#4d1924] text-[#707E94] hover:text-rose-400 cursor-pointer disabled:opacity-30"
              title="删除此角色"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>

            <!-- Expand prompt toggle -->
            <button
              @click="expandedRole = expandedRole === roleId ? '' : String(roleId)"
              class="p-1.5 rounded hover:bg-[#151D2C] text-[#707E94] hover:text-white cursor-pointer"
              title="展开/折叠角色微调与提示词"
            >
              <ChevronUp v-if="expandedRole === roleId" class="w-4 h-4" />
              <ChevronDown v-else class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- Collapsible Detailed Settings & System Prompt Editor -->
        <div v-if="expandedRole === roleId" class="mt-3 pt-3 border-t border-[#1A2232] space-y-3">
          <!-- Fine-tuning Parameters Ribbon -->
          <div class="flex flex-wrap items-center gap-4 bg-[#080B10] p-2.5 rounded-lg border border-[#161F2E] text-xs font-mono">
            <!-- Reasoning Effort -->
            <div class="flex items-center space-x-2">
              <span class="text-[#8997aa]">思考强度:</span>
              <select
                v-model="role.reasoning_effort"
                class="bg-[#0E1420] border border-[#23354D] rounded px-2 py-0.5 text-xs text-purple-300 outline-none"
                :disabled="!auth.isSuperadmin"
              >
                <option value="low">低强度 (快速响应)</option>
                <option value="medium">中强度 (均衡分析)</option>
                <option value="high">长思考 (深度推演)</option>
              </select>
            </div>

            <!-- Temperature -->
            <div class="flex items-center space-x-2">
              <span class="text-[#8997aa]">采样温度:</span>
              <input
                v-model="role.temperature"
                type="number"
                step="0.05"
                min="0.0"
                max="1.0"
                class="w-16 bg-[#0E1420] border border-[#23354D] rounded px-1.5 py-0.5 text-xs text-cyan-300 outline-none text-center"
                :disabled="!auth.isSuperadmin"
              />
              <span class="text-[10px] text-[#707E94]">(0.0~0.2 严谨 / 0.3~0.5 活跃)</span>
            </div>

            <div class="flex-1"></div>

            <button
              @click="resetRole(String(roleId))"
              :disabled="!auth.isSuperadmin"
              class="flex items-center space-x-1 text-[10px] text-purple-400 hover:text-purple-300 cursor-pointer"
            >
              <RotateCcw class="w-3 h-3" />
              <span>恢复此角色初始预设</span>
            </button>
          </div>

          <!-- Prompt Textarea -->
          <div class="space-y-1">
            <span class="text-[10px] font-mono text-[#8997aa] font-bold">角色专有 System Prompt（自由定制核心研判逻辑）：</span>
            <textarea
              v-model="role.prompt"
              rows="5"
              class="w-full bg-[#080B10] border border-[#1A2232] rounded-lg text-zinc-300 px-3 py-2 text-xs font-mono outline-none focus:border-purple-500 leading-relaxed resize-y select-text"
              :readonly="!auth.isSuperadmin"
            ></textarea>
          </div>
        </div>
      </div>
    </div>

    <!-- Live Debate Test Result Modal / Inspection Panel -->
    <div v-if="testResult" class="bg-[#0D121B] border border-purple-500/30 rounded-xl p-4 space-y-3.5 shadow-2xl">
      <div class="flex items-center justify-between pb-2.5 border-b border-[#1A2232]">
        <div class="flex flex-wrap items-center gap-2">
          <CheckCircle2 class="w-4 h-4 text-emerald-400" />
          <h3 class="text-sm font-bold text-white font-mono">委员会现场辩论与终审实录</h3>
          <span class="text-[10px] font-mono text-purple-300 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
            共识机制: {{ testResult.transcript?.consensus_mode }}
          </span>
          <span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
            总耗时 {{ testResult.transcript?.total_duration_ms }}ms
          </span>
        </div>
        <button
          @click="testResult = null"
          class="text-xs font-mono text-[#707E94] hover:text-white cursor-pointer px-2 py-1 rounded bg-[#141B26]"
        >
          收起报告
        </button>
      </div>

      <!-- Advisors Viewpoints Grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div
          v-for="(adv, key) in testResult.transcript?.advisors || {}"
          :key="key"
          class="bg-[#080B10] border border-[#1A2232] rounded-xl p-3.5 space-y-2 flex flex-col justify-between"
        >
          <div class="space-y-1">
            <div class="flex items-center justify-between text-xs font-mono font-bold">
              <span class="text-white">{{ adv.role_name }}</span>
              <span class="text-[10px] text-purple-400 truncate max-w-[120px]">{{ adv.model_used }}</span>
            </div>
            <div class="flex items-center justify-between text-[10px] text-[#707E94] font-mono">
              <span>耗时 {{ adv.latency_ms }}ms</span>
              <span v-if="adv.weight !== undefined">权重: {{ adv.weight }}</span>
            </div>
            <p class="text-xs text-zinc-300 font-mono whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto pr-1 select-text">
              {{ adv.content }}
            </p>
          </div>

          <!-- Optional Reasoning Chain Toggle -->
          <div v-if="adv.reasoning" class="pt-2 border-t border-[#141B26]">
            <button
              @click="expandedReasoning[String(key)] = !expandedReasoning[String(key)]"
              class="text-[10px] font-mono text-purple-400 hover:text-purple-300 flex items-center space-x-1 cursor-pointer"
            >
              <span>{{ expandedReasoning[String(key)] ? '收起思考链' : '展开思考链 (Reasoning)' }}</span>
            </button>
            <div
              v-if="expandedReasoning[String(key)]"
              class="mt-1.5 p-2 rounded bg-[#05080E] text-[10px] font-mono text-zinc-400 whitespace-pre-wrap max-h-36 overflow-y-auto select-text border border-[#1E293B]"
            >
              {{ adv.reasoning }}
            </div>
          </div>
        </div>
      </div>

      <!-- Arbitrator Verdict -->
      <div class="bg-[#080B10] border border-purple-500/25 rounded-xl p-3.5 space-y-2">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="text-xs font-bold text-purple-400 font-mono">【首席仲裁官 裁决指令】</span>
            <span class="text-[10px] font-mono text-[#707E94]">{{ testResult.transcript?.arbitrator?.model_used }} · 终审耗时 {{ testResult.transcript?.arbitrator?.latency_ms }}ms</span>
          </div>
        </div>
        <div class="text-xs font-mono text-emerald-400 font-bold leading-relaxed">
          宏观基调与仲裁论证: {{ testResult.brain_output?.macro_assessment }}
        </div>
        <div class="text-[11px] font-mono text-zinc-300">
          发单决策明细 (Decisions):
          <pre class="mt-1 p-2.5 rounded bg-[#05080E] border border-[#1A2232] text-[10px] text-zinc-300 overflow-x-auto max-h-48 select-text">{{ JSON.stringify(testResult.brain_output?.decisions, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>
