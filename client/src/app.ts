import { PropsWithChildren } from 'react'
import Taro, { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import './styles/global.scss'

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

  return children
}

export default App
