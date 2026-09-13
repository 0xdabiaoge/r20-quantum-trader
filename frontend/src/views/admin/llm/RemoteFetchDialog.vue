<script setup lang="ts">
/**
 * RemoteFetchDialog：从 1762 行的 LlmPage.vue 拆出的视图块（结构优化阶段 3·F3）。
 *
 * 状态由父页 `provide(LLM_KEY, useLlmConfig())` 注入，本组件 `useLlmCtx()` 取用：
 * 这样拆**不会**新建一份状态（composable 每次调用都会建新状态，直接调用即出错），
 * 也不必为几十个绑定铺 prop/emit 管道。标记一处未改，DOM 结构未变。
 */
import { useI18n } from '../../../composables/useI18n'
import { useLlmCtx } from './injection'
import {DownloadCloud, RefreshCw, Search} from 'lucide-vue-next'

const { t } = useI18n()
const {
  customFetchUrl,
  executeRemoteFetch,
  fetchModalVisible,
  fetchingRemote,
  filteredRemoteModels,
  importAllFilteredRemoteModels,
  importRemoteModel,
  remoteFetchResult,
  remoteSearch,
  selectedProvider,
} = useLlmCtx()
</script>

<template>
  <div
    v-if="fetchModalVisible"
    class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-md flex items-center justify-center p-4"
    @click.self="fetchModalVisible = false"
  >
    <div
      class="border rounded-2xl w-full max-w-2xl shadow-2xl p-5 space-y-4 text-xs max-h-[90dvh] flex flex-col"
      style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
    >
      <div class="flex items-center justify-between pb-3 border-b shrink-0" style="border-color: var(--line-1);">
        <div class="flex items-center space-x-2">
          <DownloadCloud class="w-4 h-4 text-blue-500" />
          <h3 class="text-sm font-bold uppercase" style="color: var(--ink-1);">
            {{ t('admin.llm.fetchTitle', undefined, { name: selectedProvider?.name }) }}
          </h3>
        </div>
        <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.probeHint') }}</span>
      </div>

      <!-- Probe Configuration (仅当需要微调或端点无预存 Key 时作为高级选项展开) -->
      <div class="p-3 rounded-xl border space-y-2 shrink-0 text-xs" style="background-color: var(--surface-1); border-color: var(--line-1);">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="font-bold text-[11px]" style="color: var(--ink-1);">{{ t('admin.llm.probeEndpoint') }}</span>
            <span class="text-[11px] text-blue-400">{{ customFetchUrl || selectedProvider?.base_url }}</span>
          </div>
          <div class="flex items-center space-x-1.5">
            <span v-if="selectedProvider?.has_key" class="text-[11px] text-emerald-400 font-bold">
              {{ t('admin.llm.useStoredKey') }}
            </span>
            <button
              @click="executeRemoteFetch"
              :disabled="fetchingRemote"
              class="flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
              style="background-color: var(--accent); color: var(--accent-ink);"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="fetchingRemote ? 'animate-spin' : ''" />
              <span>{{ fetchingRemote ? t('admin.llm.probing') : t('admin.llm.reprobe') }}</span>
            </button>
          </div>
        </div>
      </div>


      <!-- Status Banner -->
      <div v-if="remoteFetchResult" class="shrink-0">
        <div
          v-if="remoteFetchResult.ok"
          class="p-2.5 rounded-xl border text-xs flex items-center justify-between"
          style="background-color: var(--up-bg); border-color: var(--up-line); color: var(--up);"
        >
          <span class="font-bold">{{ t('admin.llm.probeSuccess', undefined, { n: remoteFetchResult.total }) }}</span>
          <span class="text-[11px] opacity-80">{{ remoteFetchResult.endpoint_used }}</span>
        </div>
        <div
          v-else
          class="p-2.5 rounded-xl border text-xs"
          style="background-color: var(--down-bg); border-color: var(--down-line); color: var(--down);"
        >
          {{ remoteFetchResult.error }}
        </div>
      </div>

      <!-- Remote Search Box -->
      <div v-if="remoteFetchResult?.ok" class="relative shrink-0">
        <input
          v-model="remoteSearch"
          :placeholder="t('admin.llm.filterPlaceholder')"
          class="w-full rounded-xl px-3.5 py-1.5 pl-9 text-xs outline-none border"
          style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
        />
        <Search class="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-400 pointer-events-none" />
      </div>

      <!-- Remote Scroll List -->
      <div v-if="remoteFetchResult?.ok" class="flex-1 overflow-y-auto space-y-2 pr-1 min-h-[200px]">
        <div
          v-for="rm in filteredRemoteModels"
          :key="rm.id"
          class="p-3 rounded-xl border flex items-center justify-between hover:border-[var(--line-3)] transition-colors"
          style="background-color: var(--surface-1); border-color: var(--line-1);"
        >
          <div>
            <div class="font-bold text-xs" style="color: var(--ink-1);">{{ rm.name }}</div>
            <div class="text-[11px] text-blue-400">{{ rm.id }}</div>
          </div>

          <div class="flex items-center space-x-2 shrink-0">
            <button
              @click="importRemoteModel(rm, false)"
              class="px-2.5 py-1 rounded-lg text-xs font-medium border cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
              style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
            >
              {{ t('admin.llm.addBtn') }}
            </button>
            <button
              @click="importRemoteModel(rm, true)"
              class="px-3 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
              style="background-color: var(--accent); color: var(--accent-ink);"
            >
              {{ t('admin.llm.addAndEnable') }}
            </button>
          </div>
        </div>
      </div>

      <div class="flex items-center justify-between pt-3 border-t shrink-0" style="border-color: var(--line-1);">
        <div class="text-[11px]" style="color: var(--ink-2);">
          <span v-if="filteredRemoteModels.length">{{ t('admin.llm.showingCount', undefined, { n: filteredRemoteModels.length }) }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <button
            v-if="filteredRemoteModels.length"
            @click="importAllFilteredRemoteModels"
            class="px-3 py-1.5 rounded-xl border text-xs font-bold cursor-pointer transition-all hover:opacity-90"
            style="background-color: rgba(99, 102, 241, 0.1); border-color: rgba(99, 102, 241, 0.25); color: #818CF8;"
          >
            {{ t('admin.llm.addAll', undefined, { n: filteredRemoteModels.length }) }}
          </button>
          <button
            @click="fetchModalVisible = false"
            class="px-4 py-1.5 rounded-xl border text-xs cursor-pointer"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          >
            {{ t('admin.llm.done') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
