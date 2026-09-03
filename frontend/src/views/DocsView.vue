<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from '../composables/useTheme'
import {
  BookOpen, ShieldCheck, Cpu, FileText, Sparkles, ArrowLeft,
  ExternalLink, Copy, Check, Terminal, Users, Brain, TrendingUp,
  Layers, Lock, ShieldAlert, ChevronRight, Menu, X, Play, RefreshCw,
  Sun, Moon
} from 'lucide-vue-next'

const router = useRouter()
const { theme, toggleTheme } = useTheme()

const activeSection = ref('overview')
const mobileMenuOpen = ref(false)
const copiedTag = ref('')
const zoomImage = ref<string | null>(null)

const sections = [
  { id: 'overview', title: '1. 系统架构与量化哲学', icon: TrendingUp },
  { id: 'dashboard', title: '2. 实盘终端与资产 HUD', icon: Terminal },
  { id: 'council', title: '3. 多模型决策委员会', icon: Users },
  { id: 'prompt_studio', title: '4. 提示词策略与变量插槽', icon: FileText },
  { id: 'interceptors', title: '5. Python 物理拦截插件', icon: ShieldCheck },
  { id: 'self_evolution', title: '6. 自进化与长期记忆闭环', icon: Brain },
  { id: 'deployment', title: '7. 部署启动与消息通知', icon: Cpu },
  { id: 'faq', title: '8. 常见问题与风控底线', icon: ShieldAlert },
]

function copyText(text: string, tag: string) {
  navigator.clipboard.writeText(text)
  copiedTag.value = tag
  setTimeout(() => {
    copiedTag.value = ''
  }, 2000)
}

function scrollToSection(id: string) {
  activeSection.value = id
  mobileMenuOpen.value = false
  const el = document.getElementById(id)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// Scroll spy
function onScroll() {
  const scrollPos = window.scrollY + 120
  for (let i = sections.length - 1; i >= 0; i--) {
    const el = document.getElementById(sections[i].id)
    if (el && el.offsetTop <= scrollPos) {
      activeSection.value = sections[i].id
      break
    }
  }
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})
</script>

<template>
  <div class="min-h-screen font-sans transition-colors selection:bg-blue-500/30" style="background-color: var(--bg-app); color: var(--text-main);">
    <!-- Top Header Navigation -->
    <header class="sticky top-0 z-40 backdrop-blur-md border-b px-4 sm:px-6 py-3 flex items-center justify-between" style="background-color: var(--bg-header); border-color: var(--border-subtle);">
      <div class="flex items-center space-x-3">
        <button
          @click="router.push('/')"
          class="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-mono transition-colors cursor-pointer"
          style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-muted);"
        >
          <ArrowLeft class="w-3.5 h-3.5" />
          <span>返回实盘终端</span>
        </button>
        <div class="h-4 w-px hidden sm:block" style="background-color: var(--border-subtle);"></div>
        <div class="flex items-center space-x-2">
          <span class="font-mono font-black text-sm tracking-wider flex items-center gap-1.5" style="color: var(--text-main);">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            R20 QUANTUM
          </span>
          <span
            class="px-2 py-0.5 rounded text-[10px] font-mono border font-bold"
            style="background-color: var(--color-brand-bg); color: var(--color-brand); border-color: var(--color-brand-border);"
          >
            v6.5.1 官方开发与使用文档
          </span>
        </div>
      </div>

      <div class="flex items-center space-x-2.5">
        <button
          @click="toggleTheme"
          class="flex items-center justify-center w-8 h-8 rounded-lg border transition-all cursor-pointer shadow-xs"
          style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
          :title="theme === 'dark' ? '切换为亮色浅白主题' : '切换为暗色钛金主题'"
        >
          <Sun v-if="theme === 'dark'" class="w-4 h-4 text-amber-400 hover:rotate-45 transition-transform" />
          <Moon v-else class="w-4 h-4 text-slate-700 hover:-rotate-12 transition-transform" />
        </button>
        <button
          @click="router.push('/admin')"
          class="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border text-xs font-mono cursor-pointer transition-colors"
          style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-muted);"
        >
          <Lock class="w-3.5 h-3.5 text-blue-500" />
          <span>管理控制台</span>
        </button>
        <a
          href="https://github.com/555cute/r20-quantum-trader"
          target="_blank"
          class="flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs font-mono transition-colors shadow-sm"
        >
          <ExternalLink class="w-3.5 h-3.5" />
          <span>GitHub 主仓</span>
        </a>
        <button
          @click="mobileMenuOpen = !mobileMenuOpen"
          class="sm:hidden p-1.5 rounded-lg bg-[#141B26] text-zinc-300"
        >
          <Menu v-if="!mobileMenuOpen" class="w-5 h-5" />
          <X v-else class="w-5 h-5" />
        </button>
      </div>
    </header>

    <!-- Main Container -->
    <div class="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 flex gap-8">
      <!-- Left Sticky Sidebar (TOC) -->
      <aside
        class="w-64 shrink-0 fixed inset-y-16 left-0 z-30 bg-[#0A0E17] sm:bg-transparent p-4 sm:p-0 border-r sm:border-r-0 border-[#1A2232] transition-transform duration-200 sm:translate-x-0 sm:sticky sm:top-20 sm:h-[calc(100vh-6rem)] overflow-y-auto"
        :class="mobileMenuOpen ? 'translate-x-0' : '-translate-x-full sm:translate-x-0'"
      >
        <div class="text-[11px] font-mono font-bold text-[#707E94] uppercase tracking-wider mb-3 px-2">
          目录索引 (TOC)
        </div>
        <nav class="space-y-1">
          <button
            v-for="s in sections"
            :key="s.id"
            @click="scrollToSection(s.id)"
            class="w-full text-left px-3 py-2 rounded-xl text-xs font-medium transition-all flex items-center justify-between group cursor-pointer"
            :class="activeSection === s.id ? 'bg-blue-600/15 text-blue-400 font-bold border border-blue-500/30' : 'text-zinc-400 hover:text-white hover:bg-[#121926]'"
          >
            <div class="flex items-center space-x-2.5 truncate">
              <component :is="s.icon" class="w-4 h-4 shrink-0" :class="activeSection === s.id ? 'text-blue-400' : 'text-[#556677] group-hover:text-zinc-300'" />
              <span class="truncate">{{ s.title }}</span>
            </div>
            <ChevronRight class="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" :class="activeSection === s.id ? 'opacity-100' : ''" />
          </button>
        </nav>

        <div class="mt-8 p-3.5 rounded-xl border border-[#1A2232] bg-[#0A0E17] text-xs font-mono space-y-2">
          <div class="text-[10px] text-[#707E94] uppercase">交流与反馈</div>
          <div class="text-zinc-300 font-bold flex items-center justify-between">
            <span>QQ 官方群</span>
            <span class="text-blue-400">655973677</span>
          </div>
          <p class="text-[10px] text-[#8A99AD]">欢迎量化极客、提示词工程师与策略开发者交流探讨！</p>
        </div>
      </aside>

      <!-- Right Content Area -->
      <main class="min-w-0 flex-1 space-y-16 pb-24">
        <!-- 1. 系统概览与量化哲学 -->
        <section id="overview" class="space-y-4 pt-2">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 01</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">系统架构与量化哲学</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            <strong>R20 Quantum Trader</strong> 是一套专为高波动加密货币（Crypto）打造的<strong>机构级全自动波段量化决策与执行系统</strong>。系统依托 OKX 交易所官方 REST/WebSocket API 与 @okx_ai 官方交易底座，运行在严格的北京时间（UTC+8）自然日财务基准之上，聚焦 1H~4H 大级别顺势波段，以<strong>“胜率第一、宁缺毋滥、三位一体 Fail-Closed 物理硬防线”</strong>为最高风控宗旨。
          </p>

          <!-- Feature Cards Grid -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-2">
            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0B101A] space-y-2">
              <div class="flex items-center space-x-2 text-blue-400 font-bold text-xs font-mono">
                <ShieldCheck class="w-4 h-4" />
                <span>Fail-Closed 物理硬拦截</span>
              </div>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                绝不将风控寄托于 LLM 提示词本身。在交易执行底层设立不可覆盖的 Python 物理拦截插件管线，4H 顺势门禁、80% 置信度、1H ADX 震荡过滤及真实 2.0R 盈亏比门禁物理硬切断。
              </p>
            </div>
            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0B101A] space-y-2">
              <div class="flex items-center space-x-2 text-purple-400 font-bold text-xs font-mono">
                <Users class="w-4 h-4" />
                <span>多模型多角色决策委员会</span>
              </div>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                支持并发调度宏观分析师、盘口微结构官、舆情侦察官等多参谋席位展开深度思考辩论，由首席终审仲裁官统一收口决策并输出严格 JSON 契约。
              </p>
            </div>
            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0B101A] space-y-2">
              <div class="flex items-center space-x-2 text-emerald-400 font-bold text-xs font-mono">
                <Layers class="w-4 h-4" />
                <span>语义数据插槽提示词系统</span>
              </div>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                全网快讯、自进化心法、6币种数理矩阵等动态数据抽象为标准语义变量插槽（如 <code>&#123;&#123;news_intelligence&#125;&#125;</code>），支持自由拖拽编排与一键导入导出。
              </p>
            </div>
            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0B101A] space-y-2">
              <div class="flex items-center space-x-2 text-amber-400 font-bold text-xs font-mono">
                <Brain class="w-4 h-4" />
                <span>自进化认知复盘闭环</span>
              </div>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                每夜读取真实平仓台账流水进行自我反思与痛点归因，自动更新 <code>AI_TRADING_MEMORY.md</code> 长效实战心法，具备智能时效覆盖与动态淘汰机制。
              </p>
            </div>
          </div>
        </section>

        <!-- 2. 实盘终端与资产大屏 -->
        <section id="dashboard" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 02</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">实盘终端与资产 HUD 大屏</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            前台采用完全只读的财务监视大屏设计。顶栏四张核心 HUD 财务卡片彼此严格解耦，彻底杜绝数据漂移与重复统计：
          </p>

          <ul class="space-y-2 text-xs text-[#8A99AD] font-sans list-disc list-inside">
            <li><strong class="text-white">账户总权益 (USDT)</strong>：直连交易所官方只读探针获取的总净值，并计算相对初始本金 4,061.04 USDT 的累计真实收益率（净扣手续费与资金费）。</li>
            <li><strong class="text-white">基准水位线</strong>：固化自 2026-08-31 06:57:38 起步的纯净资产基准，杜绝任何模拟盘或虚假刷量干扰。</li>
            <li><strong class="text-white">今日已结净盈亏 (UTC+8)</strong>：严格绑定北京时间自然日 00:00:00 - 23:59:59 的已结平仓净收益，不受盘口未结浮盈冲刷乱跳。</li>
            <li><strong class="text-white">当前持仓净盈亏</strong>：100% 全宽展开的在途多空持仓浮动盈亏（UPL、ROI、保证金及云端 OCO 止损盾牌覆盖率）。</li>
          </ul>

          <!-- Screenshot Card -->
          <div class="rounded-2xl border border-[#1E293B] bg-[#0A0E17] p-2 sm:p-3 overflow-hidden shadow-2xl group">
            <div class="text-[11px] font-mono text-[#707E94] px-2 py-1 flex items-center justify-between border-b border-[#1A2232] mb-2">
              <span>实机截图 · 前台实盘大屏全景 (HUD四卡、持仓监控与多币种筹码矩阵)</span>
              <span class="text-blue-400">点击放大查看</span>
            </div>
            <img
              src="/images/dashboard_trading.png"
              alt="前台实盘终端全景"
              class="w-full rounded-xl cursor-zoom-in group-hover:opacity-95 transition-opacity"
              @click="zoomImage = '/images/dashboard_trading.png'"
            />
          </div>
        </section>

        <!-- 3. 多模型决策委员会 -->
        <section id="council" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 03</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">多模型决策委员会 (Council)</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            为了避免单一模型的主观盲区，R20 v6.5.1 引入了<strong>多模型参谋并发辩论与首席仲裁机制</strong>。在进入交易决策前，系统将全市场行情与数理快照同时分发给各专业参谋席位（支持 Claude 3.7、Gemini 2.5/3.8、DeepSeek-R1、OpenAI o3 等异构模型）：
          </p>

          <div class="rounded-xl bg-[#0B101A] border border-[#1A2232] p-4 text-xs font-mono space-y-2">
            <div class="text-blue-400 font-bold">委员会决策执行流：</div>
            <div class="text-zinc-300 pl-3 border-l border-blue-500/40 space-y-1.5">
              <div>1. [并发调度] 舆情侦察官 + 宏观策略官 + 盘口微结构官 同时推演</div>
              <div>2. [交叉审视] 提取各模型深度思考内容 (reasoning_content) 并交叉论证</div>
              <div>3. [终审仲裁] 首席仲裁官综合多方辩论记录，收口输出符合 JSON 契约的发单指令</div>
              <div>4. [超时熔断] 整体辩论设 60s 超时保障，异常自动平滑回退至单模型决策</div>
            </div>
          </div>

          <!-- Screenshot Card -->
          <div class="rounded-2xl border border-[#1E293B] bg-[#0A0E17] p-2 sm:p-3 overflow-hidden shadow-2xl group">
            <div class="text-[11px] font-mono text-[#707E94] px-2 py-1 flex items-center justify-between border-b border-[#1A2232] mb-2">
              <span>实机截图 · 多模型决策委员会控制台 (角色动态CRUD、预设参谋库与现场辩论测试)</span>
              <span class="text-blue-400">点击放大查看</span>
            </div>
            <img
              src="/images/admin_council.png"
              alt="多模型委员会控制台"
              class="w-full rounded-xl cursor-zoom-in group-hover:opacity-95 transition-opacity"
              @click="zoomImage = '/images/admin_council.png'"
            />
          </div>
        </section>

        <!-- 4. 提示词策略与变量插槽 -->
        <section id="prompt_studio" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 04</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">提示词策略与语义变量插槽</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            提示词策略工作室支持对四大管线（交易 System、交易 User、自进化 System、自进化 User）进行 100% 解锁自由定制。通过全新的<strong>语义变量插槽（Semantic Slots）</strong>系统，用户可直接在任意模块中引用实时数据：
          </p>

          <!-- Variable Table -->
          <div class="rounded-xl border border-[#1E293B] overflow-x-auto">
            <table class="w-full text-left text-xs font-mono">
              <thead class="bg-[#0A0E17] text-[#8A99AD] border-b border-[#1E293B]">
                <tr>
                  <th class="p-3">变量占位符</th>
                  <th class="p-3">数据源分类</th>
                  <th class="p-3">注入内容与作用</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[#1A2232]/60 bg-[#080B10]">
                <tr>
                  <td class="p-3 text-blue-400 font-bold">&#123;&#123;news_intelligence&#125;&#125;</td>
                  <td class="p-3 text-zinc-300">实时快讯</td>
                  <td class="p-3 text-[#8A99AD]">注入全网最新重大突发要闻、宏观基调与市场情绪</td>
                </tr>
                <tr>
                  <td class="p-3 text-purple-400 font-bold">&#123;&#123;trading_memory&#125;&#125;</td>
                  <td class="p-3 text-zinc-300">自进化心法</td>
                  <td class="p-3 text-[#8A99AD]">注入每日复盘提炼的核心实战心法、避坑指南与痛点归因</td>
                </tr>
                <tr>
                  <td class="p-3 text-emerald-400 font-bold">&#123;&#123;market_matrix&#125;&#125;</td>
                  <td class="p-3 text-zinc-300">行情数理</td>
                  <td class="p-3 text-[#8A99AD]">注入6币种K线、微积分动力学(v/a/j/I)、定积分做功与VaR风险</td>
                </tr>
                <tr>
                  <td class="p-3 text-amber-400 font-bold">&#123;&#123;account_positions&#125;&#125;</td>
                  <td class="p-3 text-zinc-300">账户敞口</td>
                  <td class="p-3 text-[#8A99AD]">注入在途持仓方向、均价、标记价、浮盈ROI与动态止损线</td>
                </tr>
                <tr>
                  <td class="p-3 text-cyan-400 font-bold">&#123;&#123;pending_orders&#125;&#125;</td>
                  <td class="p-3 text-zinc-300">挂单池</td>
                  <td class="p-3 text-[#8A99AD]">注入未成交 Maker 限价挂单、价格、数量及附带云端 OCO</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Screenshot Card -->
          <div class="rounded-2xl border border-[#1E293B] bg-[#0A0E17] p-2 sm:p-3 overflow-hidden shadow-2xl group">
            <div class="text-[11px] font-mono text-[#707E94] px-2 py-1 flex items-center justify-between border-b border-[#1A2232] mb-2">
              <span>实机截图 · 提示词策略工作室 (多方案切换、模块自由拖拽、一键插入变量与右侧实时编译预览)</span>
              <span class="text-blue-400">点击放大查看</span>
            </div>
            <img
              src="/images/admin_prompt_studio.png"
              alt="提示词策略工作室"
              class="w-full rounded-xl cursor-zoom-in group-hover:opacity-95 transition-opacity"
              @click="zoomImage = '/images/admin_prompt_studio.png'"
            />
          </div>
        </section>

        <!-- 5. Python 物理拦截插件 -->
        <section id="interceptors" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 05</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">Python 物理拦截插件配置中心</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            交易发单绝不能只相信大模型的口头承诺。R20 将一切执行层风控重构为<strong>可插拔的 Python 物理拦截插件管线（Fail-Closed）</strong>。任何开仓或加仓指令发出前，必须链式通过所有激活插件的严格审查：
          </p>

          <div class="p-4 rounded-xl border border-[#1E293B] bg-[#080B10] space-y-3 font-mono text-xs">
            <div class="text-zinc-300 font-bold flex items-center justify-between">
              <span>标准插件接口定义规范:</span>
              <button
                @click="copyText('def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:', 'plugin_code')"
                class="flex items-center space-x-1 text-blue-400 hover:text-white cursor-pointer"
              >
                <Copy class="w-3 h-3" />
                <span>{{ copiedTag === 'plugin_code' ? '已复制代码' : '复制规范' }}</span>
              </button>
            </div>
            <pre class="bg-[#05080E] p-3 rounded-lg text-zinc-300 overflow-x-auto leading-relaxed">def check_risk(package: dict, decision: dict, context: dict) -> tuple[bool, str]:
    """
    输入参数:
    - package: 包含标的K线与动力学数据 (macro_4h, velocity_v, acceleration_a, adx_1h 等)
    - decision: 包含模型决策 (action, confidence, entry_price, take_profit_price, stop_loss_price)
    - context: 包含全局持仓与账户可用余额

    返回值规范:
    - 返回 (True, ""): 判定安全，放行订单
    - 返回 (False, "原因描述"): 触发物理风控，系统强制重写为 WAIT 并记录审计
    """
    action = str(decision.get("action", "WAIT")).upper()
    if action == "WAIT":
        return True, ""

    # 编写你的风控卡点逻辑...
    return True, ""</pre>
          </div>

          <!-- Official Built-in Plugins List -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="p-3.5 rounded-xl border border-[#1A2232] bg-[#0A0F18] space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white text-xs font-mono">01_macro_trend_filter.py</span>
                <span class="px-2 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">顺势铁律</span>
              </div>
              <p class="text-[11px] text-[#8A99AD]">4H 多头通道严禁逆势摸顶开空；4H 空头通道严禁逆势接飞刀做多。</p>
            </div>
            <div class="p-3.5 rounded-xl border border-[#1A2232] bg-[#0A0F18] space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white text-xs font-mono">02_confidence_gatekeeper.py</span>
                <span class="px-2 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">胜率第一</span>
              </div>
              <p class="text-[11px] text-[#8A99AD]">置信度低于 80% 一律强制降级为 WAIT；DOGE 等 Meme 标的提至 85%。</p>
            </div>
            <div class="p-3.5 rounded-xl border border-[#1A2232] bg-[#0A0F18] space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white text-xs font-mono">03_adx_volatility_filter.py</span>
                <span class="px-2 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">震荡过滤</span>
              </div>
              <p class="text-[11px] text-[#8A99AD]">1H ADX 趋势强度 &lt; 18 判定为垃圾猴市，严禁开仓过度磨损手续费。</p>
            </div>
            <div class="p-3.5 rounded-xl border border-[#1A2232] bg-[#0A0F18] space-y-1.5">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white text-xs font-mono">04_risk_reward_gatekeeper.py</span>
                <span class="px-2 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 font-bold">真实 2R</span>
              </div>
              <p class="text-[11px] text-[#8A99AD]">基于入场、止盈目标与云端止损线严格计算 R:R，拒绝 &lt; 2.0R 的劣质赔率。</p>
            </div>
          </div>
        </section>

        <!-- 6. 自进化与长期记忆闭环 -->
        <section id="self_evolution" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 06</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">自进化与长期记忆闭环</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            传统的量化策略一旦设定参数便静态固化，无法适应牛熊轮动。R20 的<strong>自进化引擎（Self-Improvement Engine）</strong>通过对历史交易流水深度复盘，实现策略经验的自我累积与动态淘汰：
          </p>

          <div class="space-y-2 text-xs text-[#8A99AD] font-sans">
            <div>• <strong class="text-white">智能时效覆盖</strong>：每次复盘必定更新覆盖基准时间戳与样本量；若前期提炼的某些经验在最新单边市中造成亏损，引擎将判定为 REVISE，淘汰旧心法；</div>
            <div>• <strong class="text-white">双层持久化存储</strong>：机器可读 JSON 与人类可读 Markdown（<code>data/AI_TRADING_MEMORY.md</code>）同步生成；</div>
            <div>• <strong class="text-white">毫秒级推演注入</strong>：下一轮 15 分钟交易主脑启动时，直接在提示词插槽中加载最新认知，形成“实战 → 复盘 → 提炼 → 进化”的完美飞轮。</div>
          </div>

          <!-- Screenshot Card -->
          <div class="rounded-2xl border border-[#1E293B] bg-[#0A0E17] p-2 sm:p-3 overflow-hidden shadow-2xl group">
            <div class="text-[11px] font-mono text-[#707E94] px-2 py-1 flex items-center justify-between border-b border-[#1A2232] mb-2">
              <span>实机截图 · 自进化实验室与长期记忆库 (样本胜率曲线、痛点归因与 Heuristic Lessons)</span>
              <span class="text-blue-400">点击放大查看</span>
            </div>
            <img
              src="/images/self_evolution_memory.png"
              alt="自进化实验室与长期记忆库"
              class="w-full rounded-xl cursor-zoom-in group-hover:opacity-95 transition-opacity"
              @click="zoomImage = '/images/self_evolution_memory.png'"
            />
          </div>
        </section>

        <!-- 7. 部署启动与消息通知 -->
        <section id="deployment" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 07</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">部署启动与多渠道消息通知</h2>
          </div>

          <p class="text-sm text-zinc-300 leading-relaxed font-sans">
            R20 支持在任意标准 Linux (Ubuntu/Debian) 云服务器上秒级开箱即用：
          </p>

          <div class="rounded-xl border border-[#1E293B] bg-[#080B10] p-4 text-xs font-mono space-y-2">
            <div class="text-zinc-400 flex items-center justify-between">
              <span>极速启动命令序列:</span>
              <button
                @click="copyText('git clone https://github.com/555cute/r20-quantum-trader.git\ncd r20-quantum-trader\npip install -r requirements.txt\n./scripts/start_standalone.sh', 'deploy_cmd')"
                class="flex items-center space-x-1 text-blue-400 hover:text-white cursor-pointer"
              >
                <Copy class="w-3 h-3" />
                <span>{{ copiedTag === 'deploy_cmd' ? '已复制命令' : '复制命令' }}</span>
              </button>
            </div>
            <pre class="bg-[#05080E] p-3 rounded-lg text-emerald-400 overflow-x-auto">git clone https://github.com/555cute/r20-quantum-trader.git
cd r20-quantum-trader
pip install -r requirements.txt
./scripts/start_standalone.sh</pre>
          </div>

          <div class="text-xs text-[#8A99AD] space-y-1.5 font-sans">
            <p><strong class="text-white">支持的告警通知渠道：</strong></p>
            <p>1. <strong>企业微信 Webhook</strong>：开仓、平仓、止盈止损移动、自进化报告实时推送到工作群；</p>
            <p>2. <strong>Telegram Bot</strong>：支持自定义 API Base 反向代理，支持海外 VPS 免代理畅连；</p>
            <p>3. <strong>QQ 机器人频道</strong>：支持通过腾讯官方开放平台 AppID 与 ClientSecret 私聊推送；</p>
            <p>4. <strong>通用 Webhook</strong>：支持飞书、钉钉、Discord 及自建服务器无缝接入。</p>
          </div>
        </section>

        <!-- 8. 常见问题解答 -->
        <section id="faq" class="space-y-4 pt-6 border-t border-[#1A2232]">
          <div class="flex items-center space-x-2">
            <span class="px-2.5 py-0.5 rounded text-[11px] font-mono font-bold bg-blue-600/20 text-blue-400 border border-blue-500/30">CHAPTER 08</span>
            <h2 class="text-xl sm:text-2xl font-black text-white tracking-wide">常见问题解答与风控底线 (FAQ)</h2>
          </div>

          <div class="space-y-3">
            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0A0F18] space-y-2">
              <h3 class="text-sm font-bold text-white">Q1: 为什么我的策略推演经常输出 WAIT？是系统出故障了吗？</h3>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                不是故障。在 R20 的量化哲学中，<strong>WAIT 是最核心、最高价值的风险防御决策</strong>。当 4H 趋势不明朗、1H ADX &lt; 18 处于横盘猴市、或置信度未达到 80% 及格线时，系统坚决选择空仓等待，杜绝因频繁交易损耗昂贵的手续费与资金费。
              </p>
            </div>

            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0A0F18] space-y-2">
              <h3 class="text-sm font-bold text-white">Q2: 我的 OKX API Key 和大模型密钥会泄露吗？</h3>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                绝不会。系统采用<strong>全本地无害化存储</strong>（本地加密 SQLite 库与环境变量隔离），开源仓库的 <code>.gitignore</code> 已严密阻断任何凭证提交；公开接口及前台响应对所有 Key、Token 与 Secret 均进行强力掩码脱敏（如 <code>sk-***abcd</code>）。
              </p>
            </div>

            <div class="p-4 rounded-xl border border-[#1E293B] bg-[#0A0F18] space-y-2">
              <h3 class="text-sm font-bold text-white">Q3: 什么是“策略广场”，我该如何将策略分享给他人？</h3>
              <p class="text-xs text-[#8A99AD] leading-relaxed">
                通过我们全新落地的<strong>策略导入/导出机制</strong>，在「提示词策略」工作室点击「导出当前策略」即可生成轻量标准的 <code>.json</code> 策略包，包含完整的管线模块拆解与自定义规则；后续策略广场上线后，用户可一键下载社区优质策略并直接导入运行！
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>

    <!-- Image Zoom Modal -->
    <div
      v-if="zoomImage"
      class="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex items-center justify-center p-4 cursor-zoom-out"
      @click="zoomImage = null"
    >
      <div class="relative max-w-6xl max-h-[92dvh]">
        <img :src="zoomImage" alt="Zoomed Screenshot" class="rounded-xl shadow-2xl max-h-[90dvh] object-contain" />
        <button
          @click="zoomImage = null"
          class="absolute top-3 right-3 p-2 rounded-full bg-black/60 hover:bg-black/90 text-white cursor-pointer"
        >
          <X class="w-5 h-5" />
        </button>
      </div>
    </div>
  </div>
</template>
