import { PropsWithChildren } from 'react'
import Taro from '@tarojs/taro'
import { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import './styles/global.scss'

function App({ children }: PropsWithChildren) {
  const { login, token } = useUserStore()

  useLaunch(() => {
    console.log('App launched.')

    // 已有 token 则跳过静默登录（本地已恢复登录态）
    if (token) return

    // 微信小程序静默登录
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            const loginRes = await login(res.code)
            console.log('Auto login success')
            // 未完善资料则跳转引导页
            if (!loginRes.profileSetup) {
              Taro.navigateTo({ url: '/pages/profile-setup/index' })
            }
          } catch (err) {
            console.warn('Auto login failed:', err)
          }
        }
      },
      fail: (err) => {
        console.warn('Taro.login failed:', err)
      },
    })
  })

  return children
}

export default App
