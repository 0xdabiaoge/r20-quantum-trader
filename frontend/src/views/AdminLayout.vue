<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTheme } from '../composables/useTheme'
import AboutModal from '../components/AboutModal.vue'
import {
  LayoutDashboard,
  Cpu,
  Layers,
  Radio,
  FileCode,
  Scroll,
  UserCog,
  Info,
  Package,
  FileText,
  Users,
  ShieldCheck,
  RefreshCw,
  LogOut,
  ExternalLink,
  BookOpen,
  Sun,
  Moon,
  ChevronRight,
  Wallet,
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { theme, toggleTheme } = useTheme()

const navGroups = [
  {
    label: '系统总览',
    items: [
      { id: 'overview', label: '运行总览', icon: LayoutDashboard },
      { id: 'decisions', label: '决策日志', icon: Radio },
    ],
  },
  {
    label: '策略配置',
    items: [
      { id: 'promptlib', label: '提示词策略', icon: FileText },
      { id: 'interceptors', label: '物理拦截插件', icon: ShieldCheck },
      { id: 'council', label: '模型委员会', icon: Users },
      { id: 'llm', label: '模型连接', icon: Cpu },
      { id: 'agents', label: '运行单元', icon: Package },
      { id: 'plugins', label: '系统插件', icon: FileCode },
    ],
  },
  {
    label: '交易与网关',
    items: [
      { id: 'security', label: 'OKX 账户与标的池', icon: Wallet },
      { id: 'gateway', label: '任务网关', icon: RefreshCw },
      { id: 'notify', label: '消息通知', icon: Radio },
      { id: 'backup', label: '备份与还原', icon: FileCode },
    ],
  },
  {
    label: '系统管理',
    items: [
      { id: 'audit', label: '操作审计', icon: Scroll },
      { id: 'adminsys', label: '管理员与密码', icon: UserCog },
      { id: 'about', label: '版本与更新', icon: Info },
    ],
  },
] as const

function navigateTo(id: string) {
  router.push(`/admin/${id}`)
}

function handleLogout() {
  auth.logout()
  router.push('/admin/login')
}

const currentView = computed<string>(() => {
  const seg = route.path.split('/').filter(Boolean).pop() || 'overview'
  return seg
})

const currentGroupName = computed<string>(() => {
  for (const group of navGroups) {
    const hit = (group.items as readonly { id: string; label: string }[]).find((i) => i.id === currentView.value)
    if (hit) return group.label
  }
  return '管理控制'
})

const currentLabel = computed<string>(() => {
  for (const group of navGroups) {
    const hit = (group.items as readonly { id: string; label: string }[]).find((i) => i.id === currentView.value)
    if (hit) return hit.label
  }
  return currentView.value
})

const showAboutModal = ref(false)
</script>

<template>
  <div
    class="min-h-screen flex flex-col md:flex-row font-sans transition-colors selection:bg-blue-500/30"
    style="background-color: var(--bg-app); color: var(--text-main);"
  >
    <!-- Sidebar (Desktop) / Horizontal Nav (Mobile) -->
    <aside
      class="w-full md:w-[220px] md:shrink-0 border-b md:border-b-0 md:border-r md:flex md:flex-col md:h-screen md:sticky md:top-0 transition-colors z-30"
      style="background-color: var(--bg-card); border-color: var(--border-subtle);"
    >
      <!-- Brand Header -->
      <div
        class="px-4 py-3.5 border-b hidden md:flex items-center justify-between"
        style="border-color: var(--border-subtle);"
      >
        <div class="flex items-center space-x-2.5">
          <div
            class="w-7 h-7 rounded-md flex items-center justify-center font-mono font-black text-xs border shadow-xs"
            style="background-color: var(--bg-card-subtle); border-color: var(--border-medium); color: var(--text-main);"
          >
            R
          </div>
          <div>
            <div class="text-xs font-black tracking-wide font-mono" style="color: var(--text-main);">
              R20 CONTROL
            </div>
            <button
              @click="showAboutModal = true"
              class="text-[10px] font-mono transition-colors cursor-pointer text-left block"
              style="color: var(--color-brand);"
              title="点击查看开源主仓信息"
            >
              v6.6.0
            </button>
          </div>
        </div>

        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="控制面正常"></span>
      </div>

      <!-- Nav Groups -->
      <nav class="overflow-x-auto md:overflow-y-auto md:overflow-x-hidden md:flex-1 py-2 px-2.5 md:space-y-1 flex md:block whitespace-nowrap">
        <div v-for="group in navGroups" :key="group.label" class="mb-2 md:mb-2.5 inline-block md:block mr-3 md:mr-0 align-top">
          <div
            class="text-[9px] font-mono font-bold uppercase tracking-wider px-2 py-1 flex items-center justify-between"
            style="color: var(--text-faint);"
          >
            <span>{{ group.label }}</span>
          </div>
          <div class="flex md:block space-x-1 md:space-x-0 md:space-y-0.5">
            <button
              v-for="item in group.items"
              :key="item.id"
              @click="navigateTo(item.id)"
              class="w-full text-left px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-all flex items-center space-x-2 cursor-pointer"
              :style="currentView === item.id
                ? { backgroundColor: 'var(--color-brand-bg)', color: 'var(--color-brand)', borderColor: 'var(--color-brand-border)' }
                : { color: 'var(--text-muted)' }"
              :class="currentView === item.id ? 'border font-bold shadow-xs' : 'border border-transparent hover:text-[var(--text-main)] hover:bg-[var(--bg-card-hover)]'"
            >
              <component :is="item.icon" class="w-3.5 h-3.5 shrink-0" />
              <span class="truncate">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Sidebar Footer User Profile -->
      <div
        class="px-3 py-2.5 border-t hidden md:flex items-center justify-between text-xs font-mono"
        style="border-color: var(--border-subtle); background-color: var(--bg-card-subtle);"
      >
        <div class="flex items-center space-x-2 min-w-0">
          <div
            class="w-6 h-6 rounded-md border flex items-center justify-center font-bold text-[10px]"
            style="background-color: var(--bg-badge); border-color: var(--border-medium); color: var(--color-brand);"
          >
            {{ auth.user?.username?.charAt(0).toUpperCase() || 'A' }}
          </div>
          <div class="truncate">
            <div class="font-bold truncate text-[11px]" style="color: var(--text-main);">{{ auth.user?.username || 'admin' }}</div>
            <div class="text-[9px] capitalize" style="color: var(--text-faint);">{{ auth.user?.role || 'superadmin' }}</div>
          </div>
        </div>
        <button
          @click="handleLogout"
          class="p-1.5 rounded hover:bg-rose-500/10 hover:text-rose-500 transition-colors cursor-pointer"
          style="color: var(--text-faint);"
          title="退出登录"
        >
          <LogOut class="w-3.5 h-3.5" />
        </button>
      </div>
    </aside>

    <!-- Main Content Shell -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top Title Header Bar with Breadcrumb -->
      <header
        class="h-14 border-b px-4 sm:px-6 flex items-center justify-between z-20 transition-colors"
        style="background-color: var(--bg-header); border-color: var(--border-subtle); backdrop-filter: blur(12px);"
      >
        <!-- Breadcrumbs -->
        <div class="flex items-center space-x-1.5 sm:space-x-2 text-xs font-mono">
          <span style="color: var(--text-faint);" class="hidden sm:inline">控制面</span>
          <ChevronRight class="w-3 h-3 hidden sm:inline" style="color: var(--text-faint);" />
          <span style="color: var(--text-muted);" class="hidden sm:inline">{{ currentGroupName }}</span>
          <ChevronRight class="w-3 h-3 hidden sm:inline" style="color: var(--text-faint);" />
          <h2 class="text-xs sm:text-sm font-black font-mono uppercase tracking-wide" style="color: var(--text-main);">
            {{ currentLabel }}
          </h2>
        </div>

        <div class="flex items-center space-x-2 sm:space-x-2.5 text-xs font-mono">
          <!-- ☀️ / 🌙 Theme Toggle Button -->
          <button
            @click="toggleTheme"
            class="flex items-center justify-center w-7 h-7 rounded-lg border transition-all cursor-pointer shadow-xs"
            style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-main);"
            :title="theme === 'dark' ? '切换为亮色模式' : '切换为暗色模式'"
          >
            <Sun v-if="theme === 'dark'" class="w-3.5 h-3.5 text-amber-400 hover:rotate-45 transition-transform" />
            <Moon v-else class="w-3.5 h-3.5 text-slate-700 hover:-rotate-12 transition-transform" />
          </button>

          <!-- Back to Terminal -->
          <a
            href="/"
            target="_blank"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border transition-all cursor-pointer shadow-xs"
            style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-muted);"
          >
            <span>实盘大屏</span>
            <ExternalLink class="w-3 h-3 opacity-60" />
          </a>

          <!-- Docs -->
          <a
            href="/docs"
            target="_blank"
            class="flex items-center space-x-1 px-2.5 py-1 rounded-lg border transition-all cursor-pointer shadow-xs"
            style="background-color: var(--bg-card); border-color: var(--border-subtle); color: var(--text-muted);"
          >
            <BookOpen class="w-3 h-3" />
            <span class="hidden sm:inline">文档</span>
          </a>

          <!-- Mobile Logout -->
          <button
            @click="handleLogout"
            class="md:hidden flex items-center space-x-1 px-2 py-1 rounded-lg border"
            style="background-color: var(--color-down-bg); color: var(--color-down); border-color: var(--color-down-border);"
          >
            <LogOut class="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      <!-- Router View Workspace -->
      <main class="flex-1 p-3.5 sm:p-5 overflow-y-auto max-w-[2160px] w-full mx-auto">
        <router-view />
      </main>
    </div>

    <!-- About Modal -->
    <AboutModal
      :visible="showAboutModal"
      @close="showAboutModal = false"
    />
  </div>
</template>
