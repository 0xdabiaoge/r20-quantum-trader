<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Blocks, ShieldAlert, RefreshCw } from 'lucide-vue-next'

const { api } = useApi()
const data = ref<any>(null)
const loading = ref(true)
const errText = ref('')

async function load() {
  loading.value = true
  try {
    data.value = await api('/api/v1/admin/plugins')
    errText.value = ''
  } catch (e: any) {
    errText.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">内置插件健康状态；实盘控制面仅允许随仓库审计过的内置插件。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">策略配置 · 2/3</span>
    </div>

    <div v-if="errText" class="p-3 rounded-lg text-xs font-mono bg-rose-500/10 border border-rose-500/20 text-rose-400">{{ errText }}</div>
    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]"><RefreshCw class="w-5 h-5 animate-spin inline mr-1.5 text-blue-400" />正在加载插件状态...</div>

    <template v-else-if="data">
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center space-x-2"><Blocks class="w-4 h-4 text-blue-400" /><h2 class="text-xs font-bold text-white font-mono uppercase">插件清单</h2></div>
          <button @click="load" class="px-2.5 py-1 rounded bg-[#111c2a] border border-[#33445b] text-[10px] font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">刷新</button>
        </div>
        <table class="w-full text-left text-xs font-mono">
          <thead><tr class="text-[#707E94] border-b border-[#1A2232]"><th class="pb-2">插件</th><th class="pb-2">类型</th><th class="pb-2">版本</th><th class="pb-2">权限声明</th><th class="pb-2">启用开关</th><th class="pb-2">健康</th></tr></thead>
          <tbody class="divide-y divide-[#1A2232]/50">
            <tr v-for="p in data.plugins" :key="p.plugin_id">
              <td class="py-2.5 text-white font-bold">{{ p.name }}<div class="text-[9px] text-[#556677]">{{ p.plugin_id }}</div></td>
              <td class="py-2.5 text-zinc-300">{{ p.plugin_type }}</td>
              <td class="py-2.5 text-[#707E94]">{{ p.version }}</td>
              <td class="py-2.5 text-[#707E94] text-[10px]">{{ (p.permissions || []).join(', ') }}</td>
              <td class="py-2.5 text-[#707E94]">{{ p.enabled_key || '默认启用' }}</td>
              <td class="py-2.5 font-bold" :class="p.health === 'healthy' ? 'text-emerald-400' : 'text-amber-400'">{{ p.health === 'healthy' ? '正常' : p.health === 'disabled' ? '已禁用' : p.health }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="bg-[#0D121B] border border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
        <ShieldAlert class="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div>
          <h3 class="text-xs font-bold text-amber-400 font-mono mb-1">安装策略：{{ data.installation_policy === 'builtin-only' ? '仅内置插件' : data.installation_policy }}</h3>
          <p class="text-[11px] text-[#707E94] font-mono leading-relaxed">{{ data.reason }}</p>
        </div>
      </div>
    </template>
  </div>
</template>
