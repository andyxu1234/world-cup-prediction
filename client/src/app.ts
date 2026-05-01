import { PropsWithChildren } from 'react'
import Taro from '@tarojs/taro'
import { useLaunch } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import './styles/global.scss'

function App({ children }: PropsWithChildren) {
  const { login, token, setLoginReady } = useUserStore()

  useLaunch(() => {
    console.log('App launched.')

    // 每次启动都调微信静默登录，确保登录态最新
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            const loginRes = await login(res.code)
            console.log('Auto login success, isNewUser:', loginRes.is_new_user)
            if (loginRes.is_new_user) {
              Taro.redirectTo({ url: '/pages/profile-setup/index' })
            } else {
              setLoginReady()
            }
          } catch (err) {
            console.warn('Auto login failed:', err)
            // 登录失败但有本地 token，仍允许页面正常加载
            if (token) {
              setLoginReady()
            }
          }
        }
      },
      fail: (err) => {
        console.warn('Taro.login failed:', err)
        if (token) {
          setLoginReady()
        }
      },
    })
  })

  return children
}

export default App
