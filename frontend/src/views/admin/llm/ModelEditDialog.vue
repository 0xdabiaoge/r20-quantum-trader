<script setup lang="ts">
/**
 * ModelEditDialog：从 1762 行的 LlmPage.vue 拆出的视图块（结构优化阶段 3·F3）。
 *
 * 状态由父页 `provide(LLM_KEY, useLlmConfig())` 注入，本组件 `useLlmCtx()` 取用：
 * 这样拆**不会**新建一份状态（composable 每次调用都会建新状态，直接调用即出错），
 * 也不必为几十个绑定铺 prop/emit 管道。标记一处未改，DOM 结构未变。
 */
import { useI18n } from '../../../composables/useI18n'
import { useLlmCtx } from './injection'

const { t } = useI18n()
const {
  availableEffortOptions,
  editingModel,
  modelForm,
  modelModalVisible,
  saveModelForm,
  selectedProvider,
  toggleCapability,
} = useLlmCtx()
</script>

<template>
  <div
    v-if="modelModalVisible"
    class="fixed inset-0 z-[var(--z-dialog)] bg-black/60 backdrop-blur-md flex items-center justify-center p-4"
    @click.self="modelModalVisible = false"
  >
    <div
      class="border rounded-2xl w-full max-w-lg shadow-2xl p-5 sm:p-6 space-y-4 text-xs"
      style="background-color: var(--surface-2); border-color: var(--line-1); color: var(--ink-1);"
    >
      <div class="flex items-center justify-between pb-3 border-b" style="border-color: var(--line-1);">
        <h3 class="text-sm font-bold uppercase" style="color: var(--ink-1);">
          {{ editingModel ? t('admin.llm.editModel') : t('admin.llm.addNewModel') }}
        </h3>
        <span class="text-[11px]" style="color: var(--ink-3);">{{ t('admin.llm.belongsTo') }} {{ selectedProvider?.name }}</span>
      </div>

      <div class="space-y-3">
        <div>
          <label class="block text-[11px] font-bold mb-1" style="color: var(--ink-2);">{{ t('admin.llm.modelIdLabel') }}</label>
          <input
            v-model="modelForm.id"
            :readonly="!!editingModel"
            :placeholder="t('admin.llm.modelIdPlaceholder')"
            class="w-full rounded-xl px-3.5 py-2 text-xs outline-none border"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>

        <div>
          <label class="block text-[11px] font-bold mb-1" style="color: var(--ink-2);">{{ t('admin.llm.displayName') }}</label>
          <input
            v-model="modelForm.name"
            :placeholder="t('admin.llm.displayNamePlaceholder')"
            class="w-full rounded-xl px-3.5 py-2 text-xs outline-none border"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>

        <!-- 模型能力标签选择 -->
        <div>
          <label class="block text-[11px] font-bold mb-1" style="color: var(--ink-2);">{{ t('admin.llm.capBadges') }}</label>
          <div class="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              @click="toggleCapability('chat')"
              class="px-2.5 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all"
              :style="modelForm.capabilities.includes('chat') ? { backgroundColor: 'rgba(99, 102, 241, 0.2)', borderColor: '#818CF8', color: '#818CF8' } : { backgroundColor: 'var(--surface-1)', borderColor: 'var(--line-1)', color: 'var(--ink-2)' }"
            >
              {{ t('admin.llm.capChatFull') }}
            </button>
            <button
              type="button"
              @click="toggleCapability('vision')"
              class="px-2.5 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all"
              :style="modelForm.capabilities.includes('vision') ? { backgroundColor: 'rgba(236, 72, 153, 0.2)', borderColor: '#F472B6', color: '#F472B6' } : { backgroundColor: 'var(--surface-1)', borderColor: 'var(--line-1)', color: 'var(--ink-2)' }"
            >
              {{ t('admin.llm.capVisionFull') }}
            </button>
            <button
              type="button"
              @click="toggleCapability('tools')"
              class="px-2.5 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all"
              :style="modelForm.capabilities.includes('tools') ? { backgroundColor: 'rgba(59, 130, 246, 0.2)', borderColor: 'var(--info)', color: 'var(--info)' } : { backgroundColor: 'var(--surface-1)', borderColor: 'var(--line-1)', color: 'var(--ink-2)' }"
            >
              {{ t('admin.llm.capToolsFull') }}
            </button>
            <button
              type="button"
              @click="toggleCapability('reasoning')"
              class="px-2.5 py-1 rounded-lg border text-xs font-medium cursor-pointer transition-all"
              :style="modelForm.capabilities.includes('reasoning') ? { backgroundColor: 'rgba(245, 158, 11, 0.2)', borderColor: 'var(--warn)', color: 'var(--warn)' } : { backgroundColor: 'var(--surface-1)', borderColor: 'var(--line-1)', color: 'var(--ink-2)' }"
            >
              {{ t('admin.llm.capCotFull') }}
            </button>
          </div>
        </div>

        <!-- 思考强度配置 (动态精简与自适应展示) -->
        <div>
          <label class="block text-[11px] font-bold mb-1" style="color: var(--ink-2);">{{ t('admin.llm.effortLabel') }}</label>
          <select
            v-model="modelForm.reasoning_effort"
            class="w-full rounded-xl px-3.5 py-2 text-xs outline-none border cursor-pointer"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          >
            <option
              v-for="opt in availableEffortOptions"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
          </select>
        </div>

        <div>
          <label class="block text-[11px] font-bold mb-1" style="color: var(--ink-2);">{{ t('admin.llm.contextLen') }}</label>
          <input
            v-model.number="modelForm.context_length"
            type="number"
            placeholder="1048576"
            class="w-full rounded-xl px-3.5 py-2 text-xs outline-none border"
            style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-1);"
          />
        </div>

      </div>

      <div class="flex justify-end space-x-2 pt-3 border-t" style="border-color: var(--line-1);">
        <button
          @click="modelModalVisible = false"
          class="px-4 py-1.5 rounded-xl border text-xs cursor-pointer"
          style="background-color: var(--surface-1); border-color: var(--line-1); color: var(--ink-2);"
        >
          {{ t('admin.llm.cancel') }}
        </button>
        <button
          @click="saveModelForm"
          class="px-5 py-1.5 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs btn-primary-text"
          style="background-color: var(--accent); color: var(--accent-ink);"
        >
          {{ t('admin.llm.saveModel') }}
        </button>
      </div>
    </div>
  </div>
</template>
