<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { ShieldAlert } from 'lucide-vue-next'

const { api } = useApi()
const config = ref<any>(null)
const runtime = ref<any>(null)
const loading = ref(true)

async function loadAll() {
  loading.value = true
  try {
    const [cfg, rt] = await Promise.all([api('/api/v1/admin/config'), api('/api/v1/admin/okx/runtime')])
    config.value = cfg
    runtime.value = rt
  } catch (e: any) {
    console.error(e)
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
        initial_capital: parseFloat(config.value.editable.initial_capital),
      }),
    })
    alert('交易环境配置已保存')
    await loadAll()
  } catch (e: any) {
    alert(e.message)
  }
}

onMounted(() => {
  loadAll()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">先连接账户，再配置交易环境；API Key 仅作为服务器部署备选。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">日常运行 · 2/4</span>
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
          <div>
            <label class="block text-[11px] text-[#8997aa] mb-1 font-mono">初始本金 (USDT)</label>
            <input v-model="config.editable.initial_capital" type="number" step="0.01" class="w-full bg-[#090f18] border border-[#1A2232] rounded-lg text-white px-3 py-2 text-xs font-mono outline-none focus:border-blue-500" />
          </div>
          <div class="col-span-2">
            <label class="flex items-center space-x-2 cursor-pointer">
              <input type="checkbox" v-model="config.editable.manual_close_enabled" class="accent-blue-500" />
              <span class="text-xs font-mono text-zinc-300">启用手动快速平仓</span>
            </label>
          </div>
        </div>
        <button @click="saveConfig" class="mt-4 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-bold cursor-pointer transition-colors">保存配置</button>
      </div>
    </template>
  </div>
</template>
