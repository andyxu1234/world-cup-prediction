import { PropsWithChildren } from 'react'
import Taro from '@tarojs/taro'
import { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import './styles/global.scss'

function App({ children }: PropsWithChildren) {
  const { login, profileSetup } = useUserStore()

  useLaunch(() => {
    console.log('App launched.')

    // 每次启动都调微信静默登录，后端根据 avatar_url + nickname 判断是否需引导
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            const loginRes = await login(res.code)
            console.log('Auto login success, profileSetup:', loginRes.profile_setup)
            if (!loginRes.profile_setup) {
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
