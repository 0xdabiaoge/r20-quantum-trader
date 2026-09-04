<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../../composables/useApi'
import {
  Cpu,
  Database,
  Activity,
  Server,
  ShieldCheck,
  RefreshCw,
  ArrowRight,
  FileText,
  Users,
  Layers,
  Clock,
  CheckCircle2,
  AlertCircle,
} from 'lucide-vue-next'

const router = useRouter()
const { api } = useApi()
const runtime = ref<any>(null)
const loading = ref(true)

async function loadRuntime() {
  loading.value = true
  try {
    const [rt, cfg] = await Promise.all([
      api('/api/v1/admin/runtime'),
      api('/api/v1/admin/config').catch(() => null),
    ])
    if (cfg?.configuration) {
      rt.configuration = { ...cfg.configuration, ...(rt?.configuration || {}) }
    }
    runtime.value = rt
  } catch (e: any) {
    console.error('Failed to load runtime:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRuntime()
})

function duration(s: number | null): string {
  if (s == null) return '--'
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}

const quickNav = [
  { label: '提示词策略工作室', desc: '语义变量与预设方案', route: '/admin/promptlib', icon: FileText },
  { label: '物理拦截插件', desc: 'Fail-Closed 风险拦截器', route: '/admin/interceptors', icon: ShieldCheck },
  { label: '多模型决策委员会', desc: '博弈仲裁与思考链透视', route: '/admin/council', icon: Users },
  { label: '模型连接配置', desc: '供应商与思考强度', route: '/admin/llm', icon: Cpu },
]
</script>

<template>
  <div class="space-y-4 max-w-[2160px] mx-auto">
    <!-- Top Executive Header Strip -->
    <div
      class="rounded-xl border p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-3 shadow-xs transition-colors"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div>
        <div class="flex items-center space-x-2">
          <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <h1 class="text-sm sm:text-base font-black font-mono tracking-wide" style="color: var(--text-main);">
            R20 QUANTUM CONTROL CENTER
          </h1>
          <span
            class="px-2 py-0.2 rounded text-[10px] font-mono font-bold border"
            style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
          >
            v6.7.0
          </span>
        </div>
        <p class="text-xs font-mono mt-1" style="color: var(--text-muted);">
          交易引擎、微积分决策链路、数据健康与物理拦截插件全景监控。
        </p>
      </div>

      <div class="flex items-center space-x-2">
        <button
          @click="loadRuntime"
          :disabled="loading"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono font-bold transition-all cursor-pointer shadow-xs disabled:opacity-50"
          style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--text-main);"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
          <span>刷新状态</span>
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="py-16 text-center text-xs font-mono" style="color: var(--text-muted);">
      <RefreshCw class="w-6 h-6 animate-spin mx-auto mb-2" style="color: var(--color-brand);" />
      <span>正在拉取最新控制面运行态...</span>
    </div>

    <!-- Runtime Data -->
    <template v-else-if="runtime">
      <!-- 4 High-Density Metric Bento Cards -->
      <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <!-- 1. 服务状态 -->
        <div
          class="rounded-xl border p-4 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-mono" style="color: var(--text-muted);">后台服务进程</span>
            <div
              class="w-6 h-6 rounded-md flex items-center justify-center border"
              style="background-color: var(--color-up-bg); border-color: var(--color-up-border); color: var(--color-up);"
            >
              <Server class="w-3.5 h-3.5" />
            </div>
          </div>
          <div class="text-xl sm:text-2xl font-black font-mono tracking-tight" style="color: var(--color-up);">
            ONLINE
          </div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            PID {{ runtime.service?.pid || '--' }} · FastAPI V5
          </div>
        </div>

        <!-- 2. 运行时间 -->
        <div
          class="rounded-xl border p-4 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-mono" style="color: var(--text-muted);">引擎持续运行</span>
            <div
              class="w-6 h-6 rounded-md flex items-center justify-center border"
              style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
            >
              <Activity class="w-3.5 h-3.5" />
            </div>
          </div>
          <div class="text-xl sm:text-2xl font-black font-mono tracking-tight num-tabular" style="color: var(--text-main);">
            {{ duration(runtime.service?.uptime_seconds) }}
          </div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            R20 Standalone · 独立高可用
          </div>
        </div>

        <!-- 3. 数据链路健康 -->
        <div
          class="rounded-xl border p-4 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-mono" style="color: var(--text-muted);">行情数据链路</span>
            <div
              class="w-6 h-6 rounded-md flex items-center justify-center border"
              :style="{
                backgroundColor: (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? 'var(--color-up-bg)' : 'var(--color-down-bg)',
                borderColor: (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? 'var(--color-up-border)' : 'var(--color-down-border)',
                color: (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? 'var(--color-up)' : 'var(--color-down)'
              }"
            >
              <Database class="w-3.5 h-3.5" />
            </div>
          </div>
          <div
            class="text-xl sm:text-2xl font-black font-mono tracking-tight"
            :style="{ color: (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? 'var(--color-up)' : 'var(--color-down)' }"
          >
            {{ (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? '100% FRESH' : 'EXPIRED' }}
          </div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            {{ (runtime.data_health?.filter((x: any) => !x.fresh).length || 0) === 0 ? '全链路低时延新鲜' : '存在异常延迟' }}
          </div>
        </div>

        <!-- 4. 持仓追踪与拦截 -->
        <div
          class="rounded-xl border p-4 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="text-[11px] font-mono" style="color: var(--text-muted);">活跃追踪器</span>
            <div
              class="w-6 h-6 rounded-md flex items-center justify-center border"
              style="background-color: var(--bg-badge); border-color: var(--border-medium); color: var(--text-main);"
            >
              <ShieldCheck class="w-3.5 h-3.5" />
            </div>
          </div>
          <div class="text-xl sm:text-2xl font-black font-mono tracking-tight num-tabular" style="color: var(--text-main);">
            {{ runtime.trackers || 0 }} 个
          </div>
          <div class="text-[10px] font-mono mt-1" style="color: var(--text-faint);">
            Fail-Closed 物理防护激活
          </div>
        </div>
      </div>

      <!-- Quick Navigation Action Bar -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <div
          v-for="item in quickNav"
          :key="item.route"
          @click="router.push(item.route)"
          class="rounded-xl border p-3.5 transition-all duration-150 flex items-center justify-between cursor-pointer group shadow-xs hover:border-[var(--border-medium)]"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center space-x-3">
            <div
              class="w-8 h-8 rounded-lg flex items-center justify-center border"
              style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle); color: var(--color-brand);"
            >
              <component :is="item.icon" class="w-4 h-4" />
            </div>
            <div>
              <div class="text-xs font-bold font-mono" style="color: var(--text-main);">{{ item.label }}</div>
              <div class="text-[10px] font-mono mt-0.5" style="color: var(--text-faint);">{{ item.desc }}</div>
            </div>
          </div>
          <ArrowRight class="w-3.5 h-3.5 opacity-40 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all" style="color: var(--text-muted);" />
        </div>
      </div>

      <!-- Dual Column: AI Decisions & Data Health -->
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
        <!-- AI Decisions Table -->
        <div
          class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-2">
              <Cpu class="w-4 h-4" style="color: var(--color-brand);" />
              <h2 class="text-xs font-black font-mono uppercase tracking-wider" style="color: var(--text-main);">
                最新 AI 多币种决策
              </h2>
            </div>
            <span
              class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold"
              style="background-color: var(--bg-badge); color: var(--color-brand); border-color: var(--border-subtle);"
            >
              {{ runtime.decisions?.length || 0 }} 标的
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-mono whitespace-nowrap">
              <thead>
                <tr class="border-b text-[11px] uppercase tracking-wider" style="border-color: var(--border-subtle); color: var(--text-muted);">
                  <th class="pb-2 font-bold">标的</th>
                  <th class="pb-2 font-bold">建议操作</th>
                  <th class="pb-2 font-bold">置信度</th>
                  <th class="pb-2 text-right font-bold">决策时间</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(d, i) in runtime.decisions"
                  :key="i"
                  class="border-b last:border-b-0 transition-colors hover:bg-[var(--bg-card-hover)]"
                  style="border-color: var(--border-subtle);"
                >
                  <td class="py-2.5 font-bold font-mono" style="color: var(--text-main);">
                    {{ d.instId?.replace('-USDT-SWAP', '') }}
                  </td>
                  <td class="py-2.5">
                    <span
                      class="px-2 py-0.5 rounded text-[10px] font-bold border"
                      :style="{
                        backgroundColor: d.action === 'WAIT' ? 'var(--bg-badge)' : d.action?.includes('LONG') ? 'var(--color-up-bg)' : 'var(--color-down-bg)',
                        borderColor: d.action === 'WAIT' ? 'var(--border-subtle)' : d.action?.includes('LONG') ? 'var(--color-up-border)' : 'var(--color-down-border)',
                        color: d.action === 'WAIT' ? 'var(--text-muted)' : d.action?.includes('LONG') ? 'var(--color-up)' : 'var(--color-down)'
                      }"
                    >
                      {{ d.action }}
                    </span>
                  </td>
                  <td class="py-2.5 font-bold num-tabular" style="color: var(--text-main);">
                    {{ d.confidence }}%
                  </td>
                  <td class="py-2.5 text-right num-tabular" style="color: var(--text-muted);">
                    {{ d.updated_at || '--' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Data Health Table -->
        <div
          class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
            <div class="flex items-center space-x-2">
              <Database class="w-4 h-4" style="color: var(--color-up);" />
              <h2 class="text-xs font-black font-mono uppercase tracking-wider" style="color: var(--text-main);">
                数据链路健康度
              </h2>
            </div>
            <span
              class="text-[10px] font-mono px-2 py-0.5 rounded border font-bold"
              style="background-color: var(--color-up-bg); color: var(--color-up); border-color: var(--color-up-border);"
            >
              REALTIME
            </span>
          </div>

          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs font-mono whitespace-nowrap">
              <thead>
                <tr class="border-b text-[11px] uppercase tracking-wider" style="border-color: var(--border-subtle); color: var(--text-muted);">
                  <th class="pb-2 font-bold">数据源</th>
                  <th class="pb-2 font-bold">状态</th>
                  <th class="pb-2 font-bold">更新时延</th>
                  <th class="pb-2 text-right font-bold">文件体积</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(x, i) in runtime.data_health"
                  :key="i"
                  class="border-b last:border-b-0 transition-colors hover:bg-[var(--bg-card-hover)]"
                  style="border-color: var(--border-subtle);"
                >
                  <td class="py-2.5 font-mono font-medium" style="color: var(--text-main);">
                    {{ x.name }}
                  </td>
                  <td class="py-2.5">
                    <span
                      class="px-2 py-0.5 rounded text-[10px] font-bold border inline-flex items-center space-x-1"
                      :style="{
                        backgroundColor: x.fresh ? 'var(--color-up-bg)' : 'var(--color-down-bg)',
                        borderColor: x.fresh ? 'var(--color-up-border)' : 'var(--color-down-border)',
                        color: x.fresh ? 'var(--color-up)' : 'var(--color-down)'
                      }"
                    >
                      <CheckCircle2 v-if="x.fresh" class="w-2.5 h-2.5" />
                      <AlertCircle v-else class="w-2.5 h-2.5" />
                      <span>{{ x.fresh ? '正常新鲜' : '延迟过期' }}</span>
                    </span>
                  </td>
                  <td class="py-2.5 num-tabular" style="color: var(--text-muted);">
                    {{ duration(x.age_seconds) }}
                  </td>
                  <td class="py-2.5 text-right font-mono num-tabular" style="color: var(--text-muted);">
                    {{ x.bytes ? Math.round(x.bytes / 1024) + ' KB' : '--' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Security & Config Cards -->
      <div
        class="rounded-xl border p-4 sm:p-5 shadow-xs transition-colors"
        style="background-color: var(--bg-card); border-color: var(--border-subtle);"
      >
        <div class="flex items-center justify-between pb-3 mb-3 border-b" style="border-color: var(--border-subtle);">
          <div class="flex items-center space-x-2">
            <ShieldCheck class="w-4 h-4 text-emerald-500" />
            <h2 class="text-xs font-black font-mono uppercase tracking-wider" style="color: var(--text-main);">
              生产环境核心安全配置
            </h2>
          </div>
          <span class="text-[10px] font-mono" style="color: var(--text-faint);">敏感 Key 已脱敏防泄露保护</span>
        </div>

        <div v-if="runtime.configuration && Object.keys(runtime.configuration).length" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3">
          <div
            v-for="(v, k) in runtime.configuration"
            :key="k"
            class="rounded-lg border p-3 font-mono transition-colors"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
          >
            <div class="text-[10px] uppercase truncate font-medium" style="color: var(--text-faint);">{{ k }}</div>
            <div class="text-xs font-bold truncate mt-1.5" style="color: var(--text-main);" :title="String(v)">{{ v || '未配置' }}</div>
          </div>
        </div>
        <div v-else class="py-6 text-center text-xs font-mono" style="color: var(--text-muted);">
          正在拉取核心安全配置...
        </div>
      </div>
    </template>
  </div>
</template>
