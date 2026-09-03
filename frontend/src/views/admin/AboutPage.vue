<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import { Info, GitBranch, Download, AlertCircle } from 'lucide-vue-next'

const { api } = useApi()
const about = ref<any>(null)
const loading = ref(true)
const updateChecking = ref(false)
const updateResult = ref<any>(null)

async function loadAbout() {
  loading.value = true
  try {
    about.value = await api('/api/v1/admin/about')
  } catch (e: any) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function checkUpdate() {
  updateChecking.value = true
  try {
    updateResult.value = await api('/api/v1/admin/update/check', { method: 'POST' })
  } catch (e: any) {
    updateResult.value = { error: e.message }
  } finally {
    updateChecking.value = false
  }
}

onMounted(() => {
  loadAbout()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-[#707E94] font-mono">确认版本，再执行更新。</p>
      <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-1 rounded border border-blue-500/20">治理 · 3/3</span>
    </div>

    <div v-if="loading" class="py-12 text-center text-xs font-mono text-[#707E94]">正在加载...</div>

    <template v-else-if="about">
      <!-- About Cards -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <div class="flex items-center space-x-2">
              <Info class="w-4 h-4 text-blue-400" />
              <h2 class="text-sm font-bold text-white font-mono">关于 R20</h2>
            </div>
            <span class="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">OPEN SOURCE</span>
          </div>
          <div class="text-xs font-mono text-zinc-300 space-y-1">
            <div>产品: <strong class="text-white">{{ about.product?.name }}</strong></div>
            <div>版本: <strong class="text-blue-400">{{ about.product?.version }}</strong></div>
            <div>控制面: {{ about.product?.control_plane }}</div>
          </div>
          <a href="https://github.com/555cute/r20-quantum-trader" target="_blank" class="inline-flex items-center space-x-1 mt-4 px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050]">
            <GitBranch class="w-3.5 h-3.5" />
            <span>GitHub 仓库</span>
          </a>
        </div>

        <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
          <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
            <h2 class="text-sm font-bold text-white font-mono">组件版本</h2>
            <span class="text-[10px] font-mono text-[#707E94]">生产运行栈</span>
          </div>
          <table class="w-full text-left text-xs font-mono">
            <tbody class="divide-y divide-[#1A2232]/50">
              <tr v-for="c in about.components" :key="c.name" class="hover:bg-[#121824]/50">
                <td class="py-2 text-zinc-300">{{ c.name }}</td>
                <td class="py-2 text-white font-bold">{{ c.version }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Update -->
      <div class="bg-[#0D121B] border border-[#1A2232] rounded-xl p-4">
        <div class="flex items-center justify-between pb-3 mb-3 border-b border-[#1A2232]">
          <h2 class="text-sm font-bold text-white font-mono">安全更新</h2>
          <span class="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">GIT</span>
        </div>
        <div class="flex space-x-2">
          <button @click="checkUpdate" :disabled="updateChecking" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-[#111c2a] border border-[#33445b] text-xs font-mono text-[#b8c4d4] cursor-pointer hover:bg-[#1d3050] disabled:opacity-50">
            <Download v-if="!updateChecking" class="w-3.5 h-3.5" />
            <span>{{ updateChecking ? '检查中...' : '检查远端' }}</span>
          </button>
        </div>
        <div v-if="updateResult" class="mt-3 text-xs font-mono" :class="updateResult.error ? 'text-rose-400' : 'text-emerald-400'">
          {{ updateResult.error || updateResult.message || JSON.stringify(updateResult) }}
        </div>
        <p class="mt-3 text-[10px] text-[#6f7d91] font-mono">执行更新必须输入确认短语 UPDATE R20；工作区不干净、远端不可达或无法快进时自动拒绝。</p>
      </div>
    </template>
  </div>
</template>
