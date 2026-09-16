import { ref } from 'vue'

export type ThemeMode = 'dark'

const currentTheme = ref<ThemeMode>('dark')
const cvdMode = ref(false)
let initialized = false

function applyCvd(on: boolean) {
  cvdMode.value = on
  if (typeof document !== 'undefined') {
    const el = document.documentElement
    if (on) el.setAttribute('data-cvd', 'true')
    else el.removeAttribute('data-cvd')
    try {
      localStorage.setItem('r20_cvd', on ? '1' : '0')
    } catch {
      // ignore
    }
  }
}

export function useTheme() {
  function applyTheme(_theme: string = 'dark') {
    currentTheme.value = 'dark'
    if (typeof document !== 'undefined') {
      const el = document.documentElement
      el.setAttribute('data-theme', 'dark')
      el.classList.add('dark')
      el.classList.remove('light')
      try {
        localStorage.setItem('r20_theme', 'dark')
      } catch {
        // ignore
      }
    }
  }

  function toggleTheme() {
    applyTheme('dark')
  }

  function initTheme() {
    if (initialized) return
    initialized = true
    if (typeof document !== 'undefined') {
      const el = document.documentElement
      el.setAttribute('data-theme', 'dark')
      el.classList.add('dark')
      el.classList.remove('light')
      try {
        if (localStorage.getItem('r20_cvd') === '1') applyCvd(true)
        localStorage.setItem('r20_theme', 'dark')
      } catch {
        // fallback
      }
    }
    applyTheme('dark')
  }

  return {
    theme: currentTheme,
    toggleTheme,
    setTheme: applyTheme,
    initTheme,
    cvd: cvdMode,
    setCvd: applyCvd,
    toggleCvd: () => applyCvd(!cvdMode.value),
  }
}
