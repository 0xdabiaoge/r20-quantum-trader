<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
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
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const navGroups = [
  {
    label: '系统总览',
    items: [
      { id: 'overview', label: '运行总览', icon: LayoutDashboard },
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
    ],
  },
  {
    label: '交易管理',
    items: [
      { id: 'symbols', label: '标的池', icon: Layers },
      { id: 'manual-trade', label: '手动发单', icon: Radio },
      { id: 'backups', label: '备份与还原', icon: FileCode },
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
  <div class="min-h-screen bg-[#030712] text-slate-100 flex flex-col md:flex-row font-sans selection:bg-blue-600/30 selection:text-white">
    <!-- Sidebar (Desktop) / Horizontal Nav (Mobile) -->
    <aside class="w-full md:w-[220px] md:shrink-0 border-b md:border-b-0 md:border-r border-[#162444] bg-[#060B18]/95 backdrop-blur-xl md:flex md:flex-col md:h-screen md:sticky md:top-0 shadow-2xl z-30">
      <!-- Brand -->
      <div class="px-4 py-3.5 md:py-4 border-b border-[#162444] hidden md:flex items-center space-x-3">
        <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20 ring-1 ring-white/20">
          <span class="text-white font-black text-base tracking-wider font-mono">R</span>
        </div>
        <div>
          <div class="text-sm font-black text-white tracking-wider font-mono">R20 CONTROL</div>
          <button
            @click="showAboutModal = true"
            class="text-[10px] text-slate-400 hover:text-cyan-400 font-mono transition-colors cursor-pointer text-left block"
            title="点击查看开源仓库与项目信息"
          >
            QUANTUM TRADER v6.5.1
          </button>
        </div>
      </div>

      <!-- Nav Groups -->
      <nav class="overflow-x-auto md:overflow-y-auto md:overflow-x-hidden md:flex-1 py-2 px-2.5 md:space-y-1.5 flex md:block whitespace-nowrap">
        <div v-for="group in navGroups" :key="group.label" class="mb-2 md:mb-3 inline-block md:block mr-4 md:mr-0 align-top">
          <div class="text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider px-3 py-1.5">{{ group.label }}</div>
          <div class="flex md:block space-x-1 md:space-x-0 md:space-y-0.5">
            <button
              v-for="item in group.items"
              :key="item.id"
              @click="navigateTo(item.id)"
              class="w-full text-left px-3 py-2 rounded-xl text-xs font-mono font-medium transition-all flex items-center space-x-2.5 cursor-pointer"
              :class="currentView === item.id
                ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-md shadow-blue-600/30 border border-blue-400/40'
                : 'text-slate-400 hover:text-white hover:bg-[#0E172E] border border-transparent'"
            >
              <component :is="item.icon" class="w-3.5 h-3.5 shrink-0" :class="currentView === item.id ? 'text-cyan-200' : 'text-slate-400'" />
              <span class="truncate">{{ item.label }}</span>
            </button>
          </div>
        </div>
      </nav>

      <!-- Sidebar Footer User Profile -->
      <div class="px-3 py-3 border-t border-[#162444] hidden md:flex items-center justify-between text-xs font-mono bg-[#040813]">
        <div class="flex items-center space-x-2 min-w-0">
          <div class="w-6 h-6 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 font-bold text-[10px]">
            {{ auth.user?.username?.charAt(0).toUpperCase() || 'A' }}
          </div>
          <div class="truncate">
            <div class="text-white font-bold truncate text-[11px]">{{ auth.user?.username || 'admin' }}</div>
            <div class="text-[9px] text-cyan-400 capitalize">{{ auth.user?.role || 'superadmin' }}</div>
          </div>
        </div>
        <button
          @click="handleLogout"
          class="p-1.5 rounded-lg hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
          title="退出登录"
        >
          <LogOut class="w-3.5 h-3.5" />
        </button>
      </div>
    </aside>

    <!-- Main Content Shell -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- Top Title Header Bar -->
      <header class="h-14 border-b border-[#162444] bg-[#060B18]/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between z-20">
        <div class="flex items-center space-x-3">
          <h2 class="text-sm sm:text-base font-black text-white font-mono uppercase tracking-wide">
            {{ currentLabel }}
          </h2>
          <span class="text-[10px] font-mono text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded-full border border-cyan-500/20 hidden sm:inline">
            R20 QUANTUM ENGINE
          </span>
        </div>

        <div class="flex items-center space-x-2 sm:space-x-3 text-xs font-mono">
          <a
            href="/"
            target="_blank"
            class="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#0A1124] hover:bg-[#121E3E] border border-[#1E2D4A] hover:border-blue-400/50 text-slate-300 hover:text-white transition-all cursor-pointer shadow-xs"
          >
            <span>实盘大屏</span>
            <ExternalLink class="w-3 h-3 text-slate-400" />
          </a>
          <a
            href="/docs"
            target="_blank"
            class="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-[#0A1124] hover:bg-[#121E3E] border border-[#1E2D4A] hover:border-cyan-400/50 text-cyan-400 hover:text-cyan-300 transition-all cursor-pointer shadow-xs"
          >
            <BookOpen class="w-3 h-3" />
            <span class="hidden sm:inline">文档</span>
          </a>
          <button
            @click="handleLogout"
            class="md:hidden flex items-center space-x-1 px-2.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/25"
          >
            <LogOut class="w-3.5 h-3.5" />
          </button>
        </div>
      </header>

      <!-- Router View Workspace -->
      <main class="flex-1 p-4 sm:p-6 overflow-y-auto max-w-[2160px] w-full mx-auto">
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
