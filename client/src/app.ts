import { PropsWithChildren } from 'react'
import Taro, { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import './styles/global.scss'

// 引导页配置缓存 key
const WELCOME_SHOWN_COUNT_KEY = 'welcome_shown_count'
const WELCOME_CONFIG_CACHE_KEY = 'welcome_config_cache'
const WELCOME_CONFIG_CACHE_TTL = 5 * 60 * 1000 // 5 分钟

// 微信场景值：1038 = 从「我的小程序」进入，跳过引导
const SCENE_FROM_FAVORITE = 1038

// 防止同一次会话内重复弹窗（onAppShow 可能多次触发）
let welcomeShownThisSession = false

interface CachedWelcomeConfig {
  enabled: boolean
  max_show_count: number
  cached_at: number
}

/** 读取引导页配置（带本地缓存，避免每次冷启动都打后端） */
async function fetchWelcomeConfig(): Promise<{ enabled: boolean; max_show_count: number } | null> {
  // 先用本地缓存
  try {
    const cached = Taro.getStorageSync(WELCOME_CONFIG_CACHE_KEY) as CachedWelcomeConfig | null
    if (cached && Date.now() - cached.cached_at < WELCOME_CONFIG_CACHE_TTL) {
      return { enabled: cached.enabled, max_show_count: cached.max_show_count }
    }
  } catch {}

  // 拉后端
  try {
    const res = await api.getAppConfig()
    const cfg = { enabled: res.welcome.enabled, max_show_count: res.welcome.max_show_count }
    const cacheObj: CachedWelcomeConfig = { ...cfg, cached_at: Date.now() }
    try { Taro.setStorageSync(WELCOME_CONFIG_CACHE_KEY, cacheObj) } catch {}
    return cfg
  } catch (err) {
    console.warn('[App] fetch welcome config failed:', err)
    return null
  }
}

/** 判断是否需要展示告别引导页，需要则 reLaunch 到 welcome 页 */
async function maybeShowWelcome(): Promise<void> {
  // 同一次会话只弹一次（防止 onAppShow 多次触发）
  if (welcomeShownThisSession) return

  // 从「我的小程序」入口进入，跳过
  try {
    const launchOpts = Taro.getLaunchOptionsSync()
    if (launchOpts.scene === SCENE_FROM_FAVORITE) return
  } catch {}

  const config = await fetchWelcomeConfig()
  if (!config || !config.enabled) return

  // 读取已展示次数
  let shownCount = 0
  try {
    shownCount = Number(Taro.getStorageSync(WELCOME_SHOWN_COUNT_KEY) || 0)
  } catch {}

  // 达到上限不再弹
  if (shownCount >= config.max_show_count) return

  // 标记本次会话已弹 + 计数 +1 并跳转
  welcomeShownThisSession = true
  try {
    Taro.setStorageSync(WELCOME_SHOWN_COUNT_KEY, shownCount + 1)
  } catch {}
  Taro.reLaunch({ url: '/pages/welcome/index' })
}

function App({ children }: PropsWithChildren) {
  const { login, setLoginReady } = useUserStore()

  useLaunch(() => {
    console.log('App launched.')

    // 从本地存储加载 token 和 profileSetup（避免模块初始化时 Taro API 未就绪）
    try {
      const token = Taro.getStorageSync('token') || null
      const profileSetup = Taro.getStorageSync('profile_setup') || false
      useUserStore.setState({ token, profileSetup })
    } catch (e) {
      console.warn('[App] Failed to load storage:', e)
    }

    // 立即放行页面渲染，登录在后台静默完成
    // 这样分享到朋友圈的场景不会卡在"加载中"
    setLoginReady()

    // 判断是否需要展示告别引导页（异步，不阻塞渲染）
    maybeShowWelcome()

    // 后台静默登录：成功后更新用户状态，失败也不影响页面展示
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            const loginRes = await login(res.code)
            console.log('Auto login success, isNewUser:', loginRes.is_new_user)
          } catch (err) {
            console.warn('[App] Silent login failed, page already rendered:', err)
          }
        }
      },
      fail: (err) => {
        console.warn('[App] Taro.login failed, page already rendered:', err)
      },
    })
  })

  // 监听 App 显示（冷启动 + 从后台切回前台都会触发）
  // 解决 useLaunch 在 H5 刷新或部分场景下不重复触发的问题
  Taro.onAppShow(() => {
    maybeShowWelcome()
  })

  return children
}

export default App
