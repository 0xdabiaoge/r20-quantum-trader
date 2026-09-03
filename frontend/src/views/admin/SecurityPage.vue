<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { useAuthStore } from '../../stores/auth'
import { ShieldAlert, Wallet, Save, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const auth = useAuthStore()
const config = ref<any>(null)
const runtime = ref<any>(null)
const loading = ref(true)
const bannerMsg = ref<{ text: string; type: 'ok' | 'err' } | null>(null)

// Initial capital editing state
const newCapital = ref<string>('')
const capitalConfirm = ref<string>('')
const savingCapital = ref(false)

async function loadAll() {
  loading.value = true
  try {
    const [cfg, rt] = await Promise.all([api('/api/v1/admin/config'), api('/api/v1/admin/okx/runtime')])
    config.value = cfg
    runtime.value = rt
    newCapital.value = String(cfg.editable?.initial_capital ?? '')
  } catch (e: any) {
    bannerMsg.value = { text: `加载失败：${e.message}`, type: 'err' }
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  try {
    await api('/api/v1/admin/config', {
      method: 'PUT',
      body: JSON.stringify({
        okx_environment: config.value.editable.okx_environment,
        manual_close_enabled: config.value.editable.manual_close_enabled,
      }),
    })
    bannerMsg.value = { text: '交易环境配置已保存', type: 'ok' }
    await loadAll()
  } catch (e: any) {
    bannerMsg.value = { text: `保存失败：${e.message}`, type: 'err' }
  }
}

async function saveCapital() {
  if (!auth.isSuperadmin) {
    bannerMsg.value = { text: '仅超级管理员可修改初始本金', type: 'err' }
    return
  }
  if (capitalConfirm.value.trim().toUpperCase() !== 'UPDATE CAPITAL') {
    bannerMsg.value = { text: '确认短语必须精确为：UPDATE CAPITAL', type: 'err' }
    return
  }
  savingCapital.value = true
  try {
    const res = await api('/api/v1/admin/account-baseline', {
      method: 'PUT',
      body: JSON.stringify({
        initial_capital: parseFloat(newCapital.value),
        confirmation: capitalConfirm.value,
      }),
    })
    bannerMsg.value = { text: `✅ ${res.effect || '初始本金已更新，主页基准盈亏水线将按新本金重算。'}`, type: 'ok' }
    capitalConfirm.value = ''
    await loadAll()
  } catch (e: any) {
    bannerMsg.value = { text: `更新失败：${e.message}`, type: 'err' }
  } finally {
    savingCapital.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">先连接账户，再配置交易环境与主页盈亏基准。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">日常运行 · 2/4</span>
    </div>

    <!-- Banner -->
    <div v-if="bannerMsg" class="p-3 rounded-lg text-xs font-mono flex items-center gap-2 border" :class="bannerMsg.type === 'ok' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'">
      <AlertCircle v-if="bannerMsg.type === 'err'" class="w-4 h-4 shrink-0" />
      <span>{{ bannerMsg.text }}</span>
    </div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">正在加载...</div>

    <template v-else>
      <!-- OKX Runtime Status -->
      <div v-if="runtime" class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <ShieldAlert class="w-4 h-4 text-blue-400" />
            <h2 class="text-sm font-bold text-white font-mono">OKX 账号连接与交易环境</h2>
          </div>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded border" :class="runtime.ready ? 'text-emerald-400 border-emerald-500/20 bg-emerald-500/10' : 'text-amber-400 border-amber-500/20 bg-amber-500/10'">
            {{ runtime.ready ? 'READY' : (runtime.degraded ? 'DEGRADED' : 'NOT READY') }}
          </span>
        </div>
        <div class="space-y-1 text-xs font-mono text-zinc-300">
          <div>当前环境: <strong class="text-white">{{ runtime.selected_mode?.toUpperCase() }}</strong></div>
          <div>认证来源: <span class="text-blue-300">{{ runtime.credential_source }}</span></div>
          <div v-if="runtime.oauth">OAuth: {{ runtime.oauth.status }} {{ runtime.oauth.site ? '· ' + runtime.oauth.site : '' }}</div>
          <div>只读探针: <span :class="runtime.read_probe?.ok ? 'text-emerald-400' : 'text-amber-400'">{{ runtime.read_probe?.detail || '--' }}</span></div>
        </div>
      </div>

      <!-- Trade Environment Config -->
      <div v-if="config" class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <h2 class="text-sm font-bold text-white font-mono mb-4 pb-3 border-b border-[#1A2232]">交易环境配置</h2>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">OKX 交易环境</label>
            <select v-model="config.editable.okx_environment" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500">
              <option value="demo">DEMO 模拟盘</option>
              <option value="live">LIVE 实盘</option>
            </select>
          </div>
          <div class="flex items-end pb-1">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" v-model="config.editable.manual_close_enabled" class="accent-blue-500" />
              <span class="text-xs font-mono text-zinc-300">启用手动快速平仓</span>
            </label>
          </div>
        </div>
        <button @click="saveConfig" class="mt-4 flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer transition-colors">
          <Save class="w-3.5 h-3.5" />
          <span>保存交易环境</span>
        </button>
      </div>

      <!-- Initial Capital Baseline (dynamically configured, NOT hardcoded) -->
      <div v-if="config" class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center space-x-2 mb-4 pb-3 border-b border-[#1A2232]">
          <Wallet class="w-4 h-4 text-emerald-400" />
          <h2 class="text-sm font-bold text-white font-mono">主页盈亏基准 · 初始本金配置</h2>
        </div>
        <div class="text-xs font-mono text-zinc-300 space-y-1.5 mb-4">
          <div>当前基准本金: <strong class="text-emerald-400 text-sm">{{ config.editable.initial_capital }} USDT</strong></div>
          <div>历史起算时间: <span class="text-zinc-400">{{ config.editable.initial_capital_reset_time }}</span>（修改本金不改变起算时间）</div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">新初始本金 (USDT)</label>
            <input v-model="newCapital" type="number" step="0.01" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">确认短语 (UPDATE CAPITAL)</label>
            <input v-model="capitalConfirm" placeholder="输入 UPDATE CAPITAL" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div class="flex items-end">
            <button @click="saveCapital" :disabled="savingCapital" class="w-full flex items-center justify-center space-x-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold cursor-pointer transition-colors disabled:opacity-50">
              <Save class="w-3.5 h-3.5" />
              <span>{{ savingCapital ? '更新中...' : '更新基准本金' }}</span>
            </button>
          </div>
        </div>
        <p class="mt-3 text-[10px] text-[#6f7d91] font-mono">
          ⚠️ 修改后主页「基准净盈亏水线」的累计盈亏、累计 ROI 将按新本金即时重算；需要超级管理员权限，历史起算时间保持不变。
        </p>
      </div>
    </template>
  </div>
</template>
