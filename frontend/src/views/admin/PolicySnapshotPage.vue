<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../../composables/useApi'
import {
  Layers,
  FileText,
  Sparkles,
  ShieldCheck,
  Users,
  RefreshCw,
  Hash,
  Activity,
  Clock,
  ArrowUpRight,
} from 'lucide-vue-next'

const { api } = useApi()

const loading = ref(true)
const refreshing = ref(false)
const snapshotData = ref<any>(null)
const errorMsg = ref<string | null>(null)

async function fetchSnapshot() {
  refreshing.value = true
  errorMsg.value = null
  try {
    const res = await api('/api/v1/admin/policy/current-snapshot')
    if (res && res.ok) {
      snapshotData.value = res
    } else {
      errorMsg.value = '未能获取到策略快照'
    }
  } catch (err: any) {
    errorMsg.value = err.message || '获取策略版本快照失败'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function formatTimestamp(ts: number) {
  if (!ts) return '未记录'
  const d = new Date(ts * 1000)
  return d.toLocaleString()
}

onMounted(() => {
  fetchSnapshot()
})
</script>

<template>
  <div class="space-y-4">
    <!-- Header Banner -->
    <div
      class="rounded-2xl border p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <div class="flex items-center space-x-3">
        <div
          class="p-2.5 rounded-xl border"
          style="background-color: var(--color-brand-bg); border-color: var(--color-brand-border); color: var(--color-brand);"
        >
          <Layers class="w-5 h-5" />
        </div>
        <div>
          <div class="flex items-center space-x-2">
            <h2 class="text-sm font-bold font-mono" style="color: var(--text-main);">
              策略大一统版本快照 (Policy Snapshot)
            </h2>
            <span
              v-if="snapshotData?.policy_version"
              class="text-[10px] font-mono font-bold px-2 py-0.5 rounded border"
              style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
            >
              {{ snapshotData.policy_version }}
            </span>
          </div>
          <p class="text-xs font-mono mt-0.5" style="color: var(--text-muted);">
            四大策略单元（提示词、自进化、物理拦截、模型委员会）的不可变指纹聚合与全链路决策归因。
          </p>
        </div>
      </div>

      <div class="flex items-center space-x-2 shrink-0">
        <button
          @click="fetchSnapshot"
          :disabled="refreshing"
          class="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-mono font-bold cursor-pointer transition-all shadow-xs"
          style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': refreshing }" />
          <span>{{ refreshing ? '抓取中...' : '刷新快照指纹' }}</span>
        </button>
      </div>
    </div>

    <!-- Error Alert -->
    <div
      v-if="errorMsg"
      class="p-3 rounded-xl text-xs font-mono border bg-rose-500/10 border-rose-500/20 text-rose-400"
    >
      {{ errorMsg }}
    </div>

    <!-- Loading Skeleton -->
    <div v-if="loading" class="py-12 text-center text-xs font-mono text-zinc-500">
      正在计算并聚合四大策略单元实时指纹...
    </div>

    <div v-else-if="snapshotData?.snapshot" class="space-y-4">
      <!-- 1. Master Identity Bar -->
      <div
        class="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-2xl border font-mono text-xs"
        style="background-color: var(--bg-card-subtle); border-color: var(--border-subtle);"
      >
        <div class="flex items-center space-x-2">
          <Hash class="w-4 h-4 text-purple-400 shrink-0" />
          <div>
            <div class="text-[10px] text-[#8A99AD]">当前策略版本 (Version)</div>
            <div class="font-bold text-sm mt-0.5" style="color: var(--text-main);">
              {{ snapshotData.snapshot.policy_version }}
            </div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <Activity class="w-4 h-4 text-cyan-400 shrink-0" />
          <div>
            <div class="text-[10px] text-[#8A99AD]">指纹哈希 (Policy Hash)</div>
            <div class="font-bold text-sm mt-0.5 text-cyan-400">
              #{{ snapshotData.snapshot.policy_hash }}
            </div>
          </div>
        </div>
        <div class="flex items-center space-x-2">
          <Clock class="w-4 h-4 text-emerald-400 shrink-0" />
          <div>
            <div class="text-[10px] text-[#8A99AD]">快照生成时间 (Captured At)</div>
            <div class="font-bold text-sm mt-0.5 text-emerald-400">
              {{ formatTimestamp(snapshotData.snapshot.timestamp) }}
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Four Strategy Units Matrix -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Unit 1: Prompt Policy -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--border-subtle);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
                  <FileText class="w-4 h-4" />
                </span>
                <span class="font-bold font-mono text-xs" style="color: var(--text-main);">提示词策略工作室 (Prompt Studio)</span>
              </div>
              <router-link
                to="/admin/promptlib"
                class="text-[10px] font-mono text-blue-400 flex items-center hover:underline"
              >
                <span>进入配置</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs font-mono">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">当前方案名称:</span>
                <span class="font-bold" style="color: var(--text-main);">
                  {{ snapshotData.snapshot.units?.prompt_profile?.active_profile_name || snapshotData.snapshot.units?.prompt_profile?.active_profile_id }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">模块布局指纹 Layout Hash:</span>
                <span class="text-blue-400 font-bold">#{{ snapshotData.snapshot.units?.prompt_profile?.layout_hash }}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">编辑模式 Mode:</span>
                <span style="color: var(--text-main);">{{ snapshotData.snapshot.units?.prompt_profile?.editor_mode }}</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[#8A99AD]">插槽延迟渲染保护:</span>
                <span class="text-emerald-400 font-bold">单次延迟渲染 · 未提供数据显式标识</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px] font-mono" style="background-color: var(--bg-card-subtle); color: var(--text-muted);">
            ✓ 模板占位符单次延迟渲染，未提供真实数据明确标记，绝不伪装为空仓。
          </div>
        </div>

        <!-- Unit 2: Evolution Shield -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--border-subtle);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <Sparkles class="w-4 h-4" />
                </span>
                <span class="font-bold font-mono text-xs" style="color: var(--text-main);">自进化心法防线 (Evolution Shield)</span>
              </div>
              <router-link
                to="/admin/evolution"
                class="text-[10px] font-mono text-emerald-400 flex items-center hover:underline"
              >
                <span>进入配置</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs font-mono">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">已发布心法指纹 Version:</span>
                <span class="text-emerald-400 font-bold truncate max-w-[180px]" :title="snapshotData.snapshot.units?.evolution_mind?.version">
                  {{ snapshotData.snapshot.units?.evolution_mind?.version }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">启用心法 / 总收录心法:</span>
                <span class="font-bold" style="color: var(--text-main);">
                  {{ snapshotData.snapshot.units?.evolution_mind?.enabled_count }} / {{ snapshotData.snapshot.units?.evolution_mind?.total_count }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">白盒审核机制:</span>
                <span class="text-emerald-400 font-bold">红线防御 · 审核拒绝硬阻断</span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[#8A99AD]">并发版本安全保护:</span>
                <span class="text-emerald-400 font-bold">CAS 乐观锁 · 428/409 拒绝过期覆盖</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px] font-mono" style="background-color: var(--bg-card-subtle); color: var(--text-muted);">
            ✓ 结构化原子发布 + 乐观版本锁，NO_CHANGE 与异常禁止重写交易心法。
          </div>
        </div>

        <!-- Unit 3: Interceptor Plugins -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--border-subtle);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400">
                  <ShieldCheck class="w-4 h-4" />
                </span>
                <span class="font-bold font-mono text-xs" style="color: var(--text-main);">物理拦截插件 (Interceptors)</span>
              </div>
              <router-link
                to="/admin/interceptors"
                class="text-[10px] font-mono text-amber-400 flex items-center hover:underline"
              >
                <span>进入配置</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs font-mono">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">核心不可禁用底座:</span>
                <span class="text-amber-400 font-bold">几何/有限性/75%置信/2.0R</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">插件管线指纹 Plugins Hash:</span>
                <span class="text-amber-400 font-bold">#{{ snapshotData.snapshot.units?.physical_interceptors?.plugins_hash }}</span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">启用可选插件:</span>
                <span class="font-bold" style="color: var(--text-main);">
                  {{ snapshotData.snapshot.units?.physical_interceptors?.enabled_count }} / {{ snapshotData.snapshot.units?.physical_interceptors?.total_count }} 个插件
                </span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[#8A99AD]">最终发单二次复验:</span>
                <span class="text-emerald-400 font-bold">生效报价缩放/舍入后复验</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px] font-mono" style="background-color: var(--bg-card-subtle); color: var(--text-muted);">
            ✓ 核心安全与可选插件彻底解耦，插件参数深拷贝隔离防篡改，缺失文件 Fail-Closed。
          </div>
        </div>

        <!-- Unit 4: Trading Desk Council -->
        <div
          class="p-4 sm:p-5 rounded-2xl border space-y-3 flex flex-col justify-between"
          style="background-color: var(--bg-card); border-color: var(--border-subtle);"
        >
          <div class="space-y-2">
            <div class="flex items-center justify-between pb-2 border-b" style="border-color: var(--border-subtle);">
              <div class="flex items-center space-x-2">
                <span class="p-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-400">
                  <Users class="w-4 h-4" />
                </span>
                <span class="font-bold font-mono text-xs" style="color: var(--text-main);">模型委员会中枢 (Council Desk)</span>
              </div>
              <router-link
                to="/admin/council"
                class="text-[10px] font-mono text-purple-400 flex items-center hover:underline"
              >
                <span>进入配置</span>
                <ArrowUpRight class="w-3 h-3 ml-0.5" />
              </router-link>
            </div>

            <div class="space-y-1 text-xs font-mono">
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">机制启停状态:</span>
                <span
                  class="font-bold"
                  :style="snapshotData.snapshot.units?.model_council?.enabled ? { color: 'var(--color-up)' } : { color: 'var(--text-faint)' }"
                >
                  {{ snapshotData.snapshot.units?.model_council?.enabled ? '● 投委会辩论模式' : '○ 单模型决策模式' }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">真实共识模式 Mode:</span>
                <span class="text-purple-400 font-bold">
                  {{ snapshotData.snapshot.units?.model_council?.consensus_mode === 'cross_examination' ? '双轮真实质询 (Cross-Exam)' : '标准提案裁决 (Standard)' }}
                </span>
              </div>
              <div class="flex justify-between py-1 border-b border-dashed" style="border-color: var(--border-subtle);">
                <span class="text-[#8A99AD]">活跃交易员席位:</span>
                <span class="font-bold" style="color: var(--text-main);">
                  {{ snapshotData.snapshot.units?.model_council?.active_roles?.length || 0 }} 位一线交易员 + CIO
                </span>
              </div>
              <div class="flex justify-between py-1">
                <span class="text-[#8A99AD]">决策采纳追踪 Adopted Role:</span>
                <span class="text-emerald-400 font-bold">机器可追溯 · 动态截止时间保护</span>
              </div>
            </div>
          </div>

          <div class="p-2 rounded-xl text-[11px] font-mono" style="background-color: var(--bg-card-subtle); color: var(--text-muted);">
            ✓ 剔除虚假共识选项，实战双轮互评，超时毫秒级自适应安全降级。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
