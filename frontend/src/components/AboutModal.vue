<script setup lang="ts">
import { ref } from 'vue'
import { X, ExternalLink, Check, Copy, Code, Github, MessageCircle, BookOpen } from 'lucide-vue-next'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const copiedTarget = ref<string | null>(null)

async function copyText(text: string, targetKey: string) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const textarea = document.createElement('textarea')
      textarea.value = text
      document.body.appendChild(textarea)
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    }
    copiedTarget.value = targetKey
    setTimeout(() => {
      if (copiedTarget.value === targetKey) {
        copiedTarget.value = null
      }
    }, 2000)
  } catch (err) {
    console.error('Copy failed:', err)
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="fixed inset-0 z-[9999] flex items-center justify-center p-3 sm:p-4 bg-black/80 backdrop-blur-md transition-all animate-fade-in overflow-y-auto"
      @click.self="emit('close')"
    >
      <div
        class="bg-[#0E121B] border border-[#1A2232] rounded-2xl w-full max-w-xl shadow-2xl p-5 sm:p-6 space-y-3.5 font-mono text-xs animate-scale-up my-auto max-h-[88dvh] overflow-y-auto"
      >
      <!-- Modal Header -->
      <div class="flex items-center justify-between pb-3 border-b border-[#1A2232]">
        <div class="flex items-center space-x-2.5">
          <div class="w-7 h-7 rounded-lg bg-blue-600 text-white flex items-center justify-center font-bold shadow-md shadow-blue-500/20">
            <Code class="w-4 h-4" />
          </div>
          <div>
            <h3 class="text-sm font-bold text-white uppercase tracking-wide flex items-center gap-2">
              <span>R20 Quantum Trader</span>
              <span class="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                v6.5.1
              </span>
            </h3>
          </div>
        </div>
        <button
          @click="emit('close')"
          class="w-7 h-7 rounded-lg bg-[#141B26] text-[#707E94] hover:text-white flex items-center justify-center border border-[#1A2232] transition-colors cursor-pointer"
          title="关闭"
        >
          <X class="w-4 h-4" />
        </button>
      </div>

      <!-- Description -->
      <p class="text-xs text-[#8A99AD] font-sans leading-relaxed">
        面向 OKX 永续合约的 LLM 原生高频量化交易系统。集成高阶微积分物理动能推演、多模型委员会协同决策、100% 交易所云端 OCO 止盈止损防线、智能 Maker 挂单与每日 20:00 闭环自进化认知复盘。
      </p>

      <!-- Links Grid -->
      <div class="space-y-2.5">
        <!-- System Documentation Link -->
        <a
          href="/docs"
          class="p-3 rounded-xl bg-[#0B0F17] border border-[#1A2232] hover:border-cyan-500/80 hover:bg-[#111723] flex items-center justify-between transition-all group cursor-pointer"
          @click="emit('close')"
        >
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-6 h-6 rounded-lg bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 shrink-0">
              <BookOpen class="w-3.5 h-3.5" />
            </div>
            <div class="truncate">
              <span class="text-white font-bold block group-hover:text-cyan-400 transition-colors">
                系统开发与使用文档 (Docs)
              </span>
              <span class="text-[10px] text-[#707E94] truncate block">
                架构说明 · 提示词变量插槽 · 物理拦截插件规范
              </span>
            </div>
          </div>
          <div class="flex items-center space-x-1 text-cyan-400 group-hover:translate-x-0.5 transition-transform shrink-0">
            <span class="text-[11px]">查看文档</span>
            <ExternalLink class="w-3.5 h-3.5" />
          </div>
        </a>

        <!-- GitHub Official Repo -->
        <a
          href="https://github.com/555cute/r20-quantum-trader"
          target="_blank"
          rel="noopener noreferrer"
          class="p-3 rounded-xl bg-[#0B0F17] border border-[#1A2232] hover:border-blue-500/80 hover:bg-[#111723] flex items-center justify-between transition-all group cursor-pointer"
        >
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-6 h-6 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-white shrink-0">
              <Github class="w-3.5 h-3.5" />
            </div>
            <div class="truncate">
              <span class="text-white font-bold block group-hover:text-blue-400 transition-colors">
                GitHub 官方开源主仓
              </span>
              <span class="text-[10px] text-[#707E94] truncate block">
                https://github.com/555cute/r20-quantum-trader
              </span>
            </div>
          </div>
          <div class="flex items-center space-x-1 text-blue-400 group-hover:translate-x-0.5 transition-transform shrink-0">
            <span class="text-[11px]">查看源码</span>
            <ExternalLink class="w-3.5 h-3.5" />
          </div>
        </a>

        <!-- LINUX DO Community -->
        <a
          href="https://linux.do/"
          target="_blank"
          rel="noopener noreferrer"
          class="p-3 rounded-xl bg-[#0B0F17] border border-[#1A2232] hover:border-orange-500/80 hover:bg-[#15121b] flex items-center justify-between transition-all group cursor-pointer"
        >
          <div class="flex items-center space-x-2.5 min-w-0">
            <div class="w-6 h-6 rounded-lg bg-orange-500/10 border border-orange-500/20 flex items-center justify-center text-orange-400 text-sm shrink-0">
              🐧
            </div>
            <div class="truncate">
              <span class="text-white font-bold block group-hover:text-orange-400 transition-colors">
                LINUX DO 社区交流
              </span>
              <span class="text-[10px] text-[#707E94] truncate block">
                https://linux.do/
              </span>
            </div>
          </div>
          <div class="flex items-center space-x-1 text-orange-400 group-hover:translate-x-0.5 transition-transform shrink-0">
            <span class="text-[11px]">访问社区</span>
            <ExternalLink class="w-3.5 h-3.5" />
          </div>
        </a>
      </div>

      <!-- QQ Contacts & Community -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-2 border-t border-[#1A2232]">
        <!-- QQ Group -->
        <div class="p-3 rounded-xl bg-[#0B0F17] border border-[#1A2232] flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded bg-emerald-500/10 text-emerald-400 flex items-center justify-center">
              <MessageCircle class="w-3.5 h-3.5" />
            </div>
            <div>
              <span class="text-[10px] text-[#707E94] block">量化交流 QQ 群</span>
              <strong class="text-[#0ECB81] font-mono text-xs">655973677</strong>
            </div>
          </div>
          <button
            @click="copyText('655973677', 'qq_group')"
            class="px-2.5 py-1 rounded bg-[#141B26] hover:bg-[#1E2738] text-[10px] text-[#EAECEF] hover:text-white border border-[#1A2232] transition-colors cursor-pointer flex items-center space-x-1"
          >
            <Check v-if="copiedTarget === 'qq_group'" class="w-3 h-3 text-emerald-400" />
            <Copy v-else class="w-3 h-3 text-[#707E94]" />
            <span>{{ copiedTarget === 'qq_group' ? '已复制' : '复制' }}</span>
          </button>
        </div>

        <!-- Author QQ -->
        <div class="p-3 rounded-xl bg-[#0B0F17] border border-[#1A2232] flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <div class="w-6 h-6 rounded bg-blue-500/10 text-blue-400 flex items-center justify-center">
              <Code class="w-3.5 h-3.5" />
            </div>
            <div>
              <span class="text-[10px] text-[#707E94] block">作者个人 QQ</span>
              <strong class="text-blue-400 font-mono text-xs">1090188816</strong>
            </div>
          </div>
          <button
            @click="copyText('1090188816', 'author_qq')"
            class="px-2.5 py-1 rounded bg-[#141B26] hover:bg-[#1E2738] text-[10px] text-[#EAECEF] hover:text-white border border-[#1A2232] transition-colors cursor-pointer flex items-center space-x-1"
          >
            <Check v-if="copiedTarget === 'author_qq'" class="w-3 h-3 text-emerald-400" />
            <Copy v-else class="w-3 h-3 text-[#707E94]" />
            <span>{{ copiedTarget === 'author_qq' ? '已复制' : '复制' }}</span>
          </button>
        </div>
      </div>

      <!-- Architecture Footnote -->
      <div class="pt-2 text-[10px] text-[#556677] text-center border-t border-[#1A2232]/50 flex items-center justify-center space-x-2">
        <span>FastAPI + Vue 3 SPA</span>
        <span>•</span>
        <span>100% 交易所云端 OCO 全覆盖</span>
        <span>•</span>
        <span>MIT License</span>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<style scoped>
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes scaleUp {
  from { opacity: 0; transform: scale(0.96); }
  to { opacity: 1; transform: scale(1); }
}

.animate-fade-in {
  animation: fadeIn 0.15s ease-out;
}

.animate-scale-up {
  animation: scaleUp 0.15s ease-out;
}
</style>
