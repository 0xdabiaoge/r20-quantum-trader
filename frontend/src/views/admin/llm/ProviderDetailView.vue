<script setup lang="ts">
/**
 * ProviderDetailView：从 1762 行的 LlmPage.vue 拆出的视图块（结构优化阶段 3·F3）。
 *
 * 状态由父页 `provide(LLM_KEY, useLlmConfig())` 注入，本组件 `useLlmCtx()` 取用：
 * 这样拆**不会**新建一份状态（composable 每次调用都会建新状态，直接调用即出错），
 * 也不必为几十个绑定铺 prop/emit 管道。标记一处未改，DOM 结构未变。
 */
import { useI18n } from '../../../composables/useI18n'
import { useLlmCtx } from './injection'
import {AlertCircle, ArrowLeft, CheckCircle2, DownloadCloud, Eye, EyeOff, Layers, Plus, RefreshCw, Settings, Image as Sparkles, Trash2, Wrench} from 'lucide-vue-next'

const { t } = useI18n()
const {
  activateModel,
  cfg,
  clearCurrentProviderModels,
  deleteSingleModel,
  detailTab,
  goBackToList,
  onApiFormatChange,
  openAddModelModal,
  openEditModelModal,
  openFetchDialog,
  providerForm,
  removeProvider,
  runTestModel,
  saveProviderConfig,
  selectedProvider,
  showApiKey,
  testLoading,
  testResult,
  testingModelId,
} = useLlmCtx()
</script>

<template>
    <!-- Detail Top Navigation Bar -->
    <div
      class="rounded-2xl border p-4 flex items-center justify-between shadow-xs transition-colors"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <button
        @click="goBackToList"
        class="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold cursor-pointer transition-all hover:bg-[var(--surface-1)]"
        style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
      >
        <ArrowLeft class="w-4 h-4" />
        <span>{{ t('admin.llm.back') }}</span>
      </button>

      <div class="flex items-center space-x-2">
        <div
          class="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-xs"
          style="background-color: var(--surface-1); color: var(--accent);"
        >
          ❖
        </div>
        <span class="font-bold text-sm sm:text-base" style="color: var(--ink-1);">
          {{ selectedProvider.name }}
        </span>
      </div>

      <div class="w-16"></div>
    </div>

    <!-- SUB-VIEW A: 「配置」Tab (对齐截图 2) -->
    <div
      v-if="detailTab === 'config'"
      class="space-y-4 rounded-2xl border p-5 shadow-xs transition-colors"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <!-- Section 1: 管理设置项列表 -->
      <div class="space-y-1">
        <div class="text-[11px] font-bold uppercase tracking-wider mb-2" style="color: var(--ink-2);">
          {{ t('admin.llm.manage') }}
        </div>

        <div
          class="rounded-xl border divide-y overflow-hidden text-xs"
          style="background-color: var(--surface-1); border-color: var(--line-1);"
        >
          <!-- 供应商类型 -->
          <div class="p-3.5 flex items-center justify-between">
            <span class="font-medium" style="color: var(--ink-1);">{{ t('admin.llm.providerType') }}</span>
            <div class="flex items-center space-x-1" style="color: var(--ink-2);">
              <span>{{ providerForm.type }}</span>
              <span class="text-gray-400">›</span>
            </div>
          </div>

          <!-- API 交互协议类型 (下拉选择) -->
          <div class="p-3.5 flex items-center justify-between">
            <div>
              <span class="font-medium" style="color: var(--ink-1);">{{ t('admin.llm.apiProtocol') }}</span>
              <div class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.apiProtocolDesc') }}</div>
            </div>
            <select
              v-model="providerForm.api_format"
              @change="onApiFormatChange"
              class="rounded-lg px-2.5 py-1.5 text-xs outline-none border cursor-pointer max-w-[200px]"
              style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
            >
              <option value="openai_chat">OpenAI Chat (/chat/completions)</option>
              <option value="claude_messages">Claude Messages (/messages)</option>
              <option value="openai_responses">OpenAI Responses (/responses)</option>
            </select>
          </div>

          <!-- 分组 -->
          <div class="p-3.5 flex items-center justify-between">
            <span class="font-medium" style="color: var(--ink-1);">{{ t('admin.llm.group') }}</span>
            <div class="flex items-center space-x-1" style="color: var(--ink-2);">
              <span>{{ providerForm.group }}</span>
              <span class="text-gray-400">›</span>
            </div>
          </div>

          <!-- 是否启用开关 -->
          <div class="p-3.5 flex items-center justify-between">
            <span class="font-medium" style="color: var(--ink-1);">{{ t('admin.llm.enabledField') }}</span>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                v-model="providerForm.enabled"
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
            </label>
          </div>

          <!-- 多Key模式开关 -->
          <div class="p-3.5 flex items-center justify-between">
            <span class="font-medium" style="color: var(--ink-1);">{{ t('admin.llm.multiKey') }}</span>
            <label class="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                v-model="providerForm.multi_key_enabled"
                class="sr-only peer"
              />
              <div class="w-11 h-6 bg-gray-600 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
            </label>
          </div>
        </div>
      </div>


      <!-- Section 2: 凭据与输入表单区 (对应截图 2 底部字段) -->
      <div class="space-y-3 pt-2">
        <!-- 供应商唯一标识 ID (仅新建自定义供应商时展示) -->
        <div v-if="selectedProvider.is_new">
          <label class="block text-xs font-bold mb-1.5" style="color: var(--ink-2);">{{ t('admin.llm.providerId') }}</label>
          <input
            v-model="providerForm.id"
            :placeholder="t('admin.llm.providerIdPlaceholder')"
            class="w-full rounded-xl px-4 py-2.5 text-xs outline-none border transition-colors"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>

        <!-- 名称 -->
        <div>
          <label class="block text-xs font-bold mb-1.5" style="color: var(--ink-2);">{{ t('admin.llm.name') }}</label>
          <input
            v-model="providerForm.name"
            placeholder="OpenAI"
            class="w-full rounded-xl px-4 py-2.5 text-xs outline-none border transition-colors"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>

        <!-- API Key -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-xs font-bold" style="color: var(--ink-2);">API Key</label>
            <span v-if="selectedProvider.has_key" class="text-[11px] text-emerald-500 font-bold">
              {{ t('admin.llm.keyReady') }}
            </span>
          </div>
          <div class="relative">
            <input
              v-model="providerForm.api_key"
              :type="showApiKey ? 'text' : 'password'"
              placeholder="••••••••••••••••••••••••"
              class="w-full rounded-xl px-4 py-2.5 pr-10 text-xs outline-none border transition-colors"
              style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
            />
            <button
              type="button"
              @click="showApiKey = !showApiKey"
              class="absolute right-3 top-2.5 text-gray-400 hover:text-white cursor-pointer"
            >
              <EyeOff v-if="showApiKey" class="w-4 h-4" />
              <Eye v-else class="w-4 h-4" />
            </button>
          </div>
        </div>

        <!-- API Base URL -->
        <div>
          <label class="block text-xs font-bold mb-1.5" style="color: var(--ink-2);">API Base URL</label>
          <input
            v-model="providerForm.base_url"
            :placeholder="t('admin.llm.baseUrlPlaceholder')"
            class="w-full rounded-xl px-4 py-2.5 text-xs outline-none border transition-colors"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
          <p class="mt-1 text-[10px]" style="color: var(--ink-3);">
            {{ t('admin.llm.baseUrlDesc') }}
          </p>
        </div>

        <!-- API 路径 -->
        <div>
          <label class="block text-xs font-bold mb-1.5" style="color: var(--ink-2);">{{ t('admin.llm.apiPath') }}</label>
          <input
            v-model="providerForm.api_path"
            placeholder="/chat/completions"
            class="w-full rounded-xl px-4 py-2.5 text-xs outline-none border transition-colors"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>
      </div>

      <!-- Save Button -->
      <div class="pt-3 pb-16 flex items-center justify-between">
        <button
          v-if="!selectedProvider.is_new"
          @click="removeProvider"
          class="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer border"
          style="color: #F87171; border-color: rgba(239, 68, 68, 0.3); background-color: rgba(239, 68, 68, 0.06);"
        >
          <Trash2 class="w-3.5 h-3.5" />
          <span>{{ t('admin.llm.deleteProvider') }}</span>
        </button>
        <span v-else></span>
        <button
          @click="saveProviderConfig"
          class="px-6 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
          style="background-color: var(--accent); color: var(--accent-ink);"
        >
          {{ t('admin.llm.saveProvider') }}
        </button>
      </div>
    </div>

    <!-- SUB-VIEW B: 「模型」Tab (完美还原原生截图排版) -->
    <div v-else-if="detailTab === 'models'" class="space-y-4">
      <!-- Models List Container -->
      <div
        class="rounded-3xl border divide-y overflow-hidden shadow-xs transition-colors"
        style="background-color: var(--surface-2); border-color: var(--line-1);"
      >
        <div
          v-for="m in selectedProvider.models"
          :key="m.id"
          class="p-4 sm:p-5 flex items-center justify-between hover:bg-[var(--surface-1)] transition-colors group"
          style="border-color: var(--line-1);"
        >
          <!-- Left: Sparkle Avatar + Model Title + Badges -->
          <div class="flex items-start sm:items-center space-x-3.5 min-w-0 pr-3">
            <!-- Avatar: 经典彩色四角星 Sparkle 图标 -->
            <div
              class="w-10 h-10 rounded-full flex items-center justify-center shrink-0 shadow-2xs border"
              style="background-color: var(--surface-1); border-color: var(--line-1);"
            >
              <Sparkles class="w-5 h-5 text-indigo-400" />
            </div>

            <!-- Content Area -->
            <div class="min-w-0">
              <!-- Model ID & Status Badge -->
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-bold text-sm tracking-tight truncate max-w-[200px] sm:max-w-md" style="color: var(--ink-1);">
                  {{ m.id }}
                </span>
                <span
                  v-if="m.id === cfg?.active_model_id"
                  class="px-2 py-0.5 rounded-full text-[11px] font-bold border"
                  style="background-color: rgba(16, 185, 129, 0.12); border-color: rgba(16, 185, 129, 0.25); color: var(--up);"
                >
                  {{ t('admin.llm.brainActiveModel') }}
                </span>
              </div>

              <!-- Capability Badges (对齐截图 3: 聊天、T图 > T、工具锤子、CoT思考) -->
              <div class="flex flex-wrap items-center gap-1.5 mt-2">
                <span
                  v-if="m.capabilities?.includes('chat')"
                  class="px-2.5 py-0.5 rounded-full text-[11px] font-medium border"
                  style="background-color: rgba(99, 102, 241, 0.08); border-color: rgba(99, 102, 241, 0.2); color: #818CF8;"
                >
                  {{ t('admin.llm.capChat') }}
                </span>
                <span
                  v-if="m.capabilities?.includes('vision')"
                  class="px-2.5 py-0.5 rounded-full text-[11px] font-medium border"
                  style="background-color: rgba(236, 72, 153, 0.08); border-color: rgba(236, 72, 153, 0.2); color: #F472B6;"
                >
                  {{ t('admin.llm.capVision') }}
                </span>
                <span
                  v-if="m.capabilities?.includes('tools')"
                  class="p-1 rounded-full border flex items-center justify-center"
                  style="background-color: rgba(59, 130, 246, 0.08); border-color: rgba(59, 130, 246, 0.2); color: var(--info);"
                  :title="t('admin.llm.capToolsTitle')"
                >
                  <Wrench class="w-3 h-3" />
                </span>
                <span
                  v-if="m.capabilities?.includes('reasoning') || m.reasoning_type !== 'none'"
                  class="px-2 py-0.5 rounded-full text-[11px] border flex items-center gap-1 font-bold text-amber-400"
                  style="background-color: rgba(245, 158, 11, 0.08); border-color: rgba(245, 158, 11, 0.2);"
                  :title="t('admin.llm.capReasonTitle')"
                >
                  {{ t('admin.llm.capThink') }}
                </span>
                <span
                  v-if="m.context_length"
                  class="text-[11px] text-gray-400 ml-1"
                >
                  {{ (m.context_length / 1000).toFixed(0) }}k
                </span>
              </div>
            </div>
          </div>

          <!-- Right: Minimalist Action Controls -->
          <div class="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
            <button
              v-if="m.id !== cfg?.active_model_id"
              @click="activateModel(m)"
              class="px-3 py-1 rounded-xl text-xs font-bold border transition-all cursor-pointer shadow-xs btn-primary-text"
              style="background-color: var(--accent); color: var(--accent-ink);"
              :title="t('admin.llm.setBrainTitle')"
            >
              {{ t('admin.llm.enable') }}
            </button>

            <button
              @click="runTestModel(m)"
              :disabled="testLoading && testingModelId === m.id"
              class="p-2 rounded-xl border text-xs cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
              style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);"
              :title="t('admin.llm.testConnTitle')"
            >
              <RefreshCw class="w-3.5 h-3.5" :class="testLoading && testingModelId === m.id ? 'animate-spin' : ''" />
            </button>

            <button
              @click="openEditModelModal(m)"
              class="p-2 rounded-xl border text-xs cursor-pointer hover:bg-[var(--surface-2)] transition-colors"
              style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);"
              :title="t('admin.llm.editParamsTitle')"
            >
              <Settings class="w-3.5 h-3.5" />
            </button>

            <button
              @click="deleteSingleModel(m)"
              class="p-2 rounded-xl border text-xs cursor-pointer hover:bg-red-500/10 transition-colors text-red-400"
              style="border-color: var(--line-1);"
              :title="t('admin.llm.deleteModelTitle')"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        <div v-if="!selectedProvider.models?.length" class="py-16 text-center text-xs" style="color: var(--ink-2);">
          {{ t('admin.llm.noModels') }}
        </div>
      </div>

      <!-- Diagnostic Response Box -->
      <div
        v-if="testResult"
        class="rounded-2xl border p-4 transition-all shadow-xs text-xs"
        :style="{
          backgroundColor: testResult.ok ? 'var(--up-bg)' : 'var(--down-bg)',
          borderColor: testResult.ok ? 'var(--up-line)' : 'var(--down-line)',
          color: testResult.ok ? 'var(--up)' : 'var(--down)'
        }"
      >
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center space-x-2 font-bold text-sm">
            <CheckCircle2 v-if="testResult.ok" class="w-4 h-4" />
            <AlertCircle v-else class="w-4 h-4" />
            <span>{{ testResult.ok ? t('admin.llm.testPassed', undefined, { ms: testResult.latency_ms }) : t('admin.llm.testFailed') }}</span>
          </div>
          <span class="text-[11px] opacity-75">{{ t('admin.llm.status') }} {{ testResult.status_code || 0 }}</span>
        </div>

        <div v-if="testResult.ok" class="space-y-1 text-xs" style="color: var(--ink-1);">
          <div>{{ t('admin.llm.outputPreview') }} <span class="font-bold">{{ testResult.response_preview }}</span></div>
          <div v-if="testResult.reasoning_detected" class="text-emerald-500 font-bold">
            {{ t('admin.llm.reasoningDetected') }}
          </div>
        </div>
        <div v-else class="text-xs break-all" style="color: var(--down);">
          {{ testResult.error || t('admin.llm.testTimeoutErr') }}
        </div>
      </div>

      <!-- Floating Bottom Operation Bar (完美对齐截图 3 椭圆气泡底栏: [获取] [+ 添加新模型] [清空]) -->
      <div class="flex items-center justify-center pt-2 pb-20">
        <div
          class="flex items-center space-x-3 p-1.5 rounded-full border shadow-2xl backdrop-blur-md"
          style="background-color: var(--surface-2); border-color: var(--line-1);"
        >
          <!-- 获取 (带方块立方体图标的大圆角按钮) -->
          <button
            @click="openFetchDialog"
            class="flex items-center space-x-2 px-5 py-2.5 rounded-full font-bold text-xs cursor-pointer border transition-all hover:opacity-90 shadow-2xs"
            style="background-color: rgba(99, 102, 241, 0.1); border-color: rgba(99, 102, 241, 0.25); color: #818CF8;"
          >
            <DownloadCloud class="w-4 h-4" />
            <span>{{ t('admin.llm.fetch') }}</span>
          </button>

          <!-- + 添加新模型 -->
          <button
            @click="openAddModelModal"
            class="flex items-center space-x-2 px-5 py-2.5 rounded-full font-bold text-xs cursor-pointer border transition-all hover:opacity-90 shadow-2xs"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          >
            <Plus class="w-4 h-4" />
            <span>{{ t('admin.llm.addNewModel') }}</span>
          </button>

          <!-- 清空删除图标 (带红晕气泡) -->
          <button
            @click="clearCurrentProviderModels"
            class="p-2.5 rounded-full border cursor-pointer hover:bg-red-500/10 transition-colors text-red-400"
            style="border-color: rgba(239, 68, 68, 0.2); background-color: rgba(239, 68, 68, 0.08);"
            :title="t('admin.llm.clearModelsTitle')"
          >
            <Trash2 class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Detail Bottom Tab Bar (对齐截图 2 & 截图 3 的底部「配置」与「模型」双Tab) -->
    <div
      class="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 flex items-center rounded-2xl border p-1 shadow-2xl backdrop-blur-md"
      style="background-color: var(--surface-2); border-color: var(--line-1);"
    >
      <button
        @click="detailTab = 'config'"
        class="flex items-center space-x-2 px-6 py-2.5 rounded-xl font-bold text-xs cursor-pointer transition-all border"
        :style="detailTab === 'config' ? {
          backgroundColor: 'var(--info)',
          borderColor: 'var(--info)',
          color: '#FFFFFF',
          boxShadow: '0 2px 10px rgba(37,99,235,0.35)',
        } : {
          backgroundColor: 'transparent',
          borderColor: 'transparent',
          color: 'var(--ink-2)',
        }"
      >
        <Settings class="w-4 h-4" />
        <span>{{ t('admin.llm.tabConfig') }}</span>
      </button>

      <button
        @click="detailTab = 'models'"
        class="flex items-center space-x-2 px-6 py-2.5 rounded-xl font-bold text-xs cursor-pointer transition-all border"
        :style="detailTab === 'models' ? {
          backgroundColor: 'var(--info)',
          borderColor: 'var(--info)',
          color: '#FFFFFF',
          boxShadow: '0 2px 10px rgba(37,99,235,0.35)',
        } : {
          backgroundColor: 'transparent',
          borderColor: 'transparent',
          color: 'var(--ink-2)',
        }"
      >
        <Layers class="w-4 h-4" />
        <span>{{ t('admin.llm.tabModels') }} ({{ selectedProvider.models?.length || 0 }})</span>
      </button>
    </div>
</template>
