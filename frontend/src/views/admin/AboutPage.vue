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

    <div v-if="loading" class="py-12 text-center text-xs font-mono" style="color: var(--text-muted);">正在加载...</div>

    <template v-else-if="about">
      <!-- About Cards -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-2">
              <Info class="w-4 h-4" style="color: var(--color-brand);" />
              <h2 class="text-sm font-bold font-mono" style="color: var(--text-main);">关于 R20</h2>
            </div>
            <span class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold" style="background-color: var(--color-up-bg); color: var(--color-up); border-color: var(--color-up-border);">OPEN SOURCE</span>
          </div>
          <div class="text-xs font-mono space-y-1.5" style="color: var(--text-muted);">
            <div>产品: <strong style="color: var(--text-main);">{{ about.product?.name }}</strong></div>
            <div>版本: <strong style="color: var(--color-brand);">{{ about.product?.version }}</strong></div>
            <div>控制面: <span style="color: var(--text-main);">{{ about.product?.control_plane }}</span></div>
          </div>
          <a href="https://github.com/555cute/r20-quantum-trader" target="_blank" class="inline-flex items-center space-x-1.5 mt-4 px-3 py-1.5 rounded-lg border text-xs font-mono font-bold transition-all cursor-pointer shadow-xs" style="background-color: var(--text-main); color: var(--bg-card);">
            <GitBranch class="w-3.5 h-3.5" />
            <span>GitHub 仓库</span>
          </a>
        </div>

        <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <h2 class="text-sm font-bold font-mono" style="color: var(--text-main);">组件版本</h2>
            <span class="text-[10px] font-mono" style="color: var(--text-faint);">生产运行栈</span>
          </div>
          <div class="table-scroll-container">
            <table class="w-full text-left text-xs font-mono whitespace-nowrap">
              <tbody>
                <tr v-for="c in about.components" :key="c.name" class="border-b last:border-b-0 hover:bg-[var(--bg-card-hover)] transition-colors" style="border-color: var(--border-subtle);">
                  <td class="py-2.5" style="color: var(--text-muted);">{{ c.name }}</td>
                  <td class="py-2.5 font-bold num-tabular" style="color: var(--text-main);">{{ c.version }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Update -->
      <div class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors" style="background-color: var(--bg-card); border-color: var(--border-subtle);">
        <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
          <h2 class="text-sm font-bold font-mono" style="color: var(--text-main);">安全更新</h2>
          <span class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold" style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);">GIT</span>
        </div>
        <div class="flex space-x-2">
          <button @click="checkUpdate" :disabled="updateChecking" class="flex items-center space-x-1 px-3 py-1.5 rounded-lg border text-xs font-mono font-bold transition-all cursor-pointer shadow-xs" style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);">
            <Download v-if="!updateChecking" class="w-3.5 h-3.5" />
            <span>{{ updateChecking ? '检查中...' : '检查远端更新' }}</span>
          </button>
        </div>
        <div v-if="updateResult" class="mt-3 text-xs font-mono p-2.5 rounded-lg border" :style="updateResult.error ? { backgroundColor: 'var(--color-down-bg)', borderColor: 'var(--color-down-border)', color: 'var(--color-down)' } : { backgroundColor: 'var(--color-up-bg)', borderColor: 'var(--color-up-border)', color: 'var(--color-up)' }">
          {{ updateResult.error || updateResult.message || JSON.stringify(updateResult) }}
        </div>
        <p class="mt-3 text-[10px] font-mono" style="color: var(--text-faint);">执行更新必须输入确认短语 UPDATE R20；工作区不干净、远端不可达或无法快进时自动拒绝。</p>
      </div>
    </template>
  </div>
</template>
