import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

const GITHUB_URL = 'https://github.com/AndyXu-Citi/world-cup-prediction'

export default function About() {
  const handleCopyGithub = () => {
    Taro.setClipboardData({
      data: GITHUB_URL,
      success: () => Taro.showToast({ title: 'GitHub地址已复制', icon: 'success' }),
    })
  }

  return (
    <View className='about-page'>
      {/* ======== 内容区 ======== */}
      <View className='body'>
        {/* ======== Hero 区域 ======== */}
        <View className='hero'>
          <View className='hero-orb hero-orb-1' />
          <View className='hero-orb hero-orb-2' />
          <View className='hero-grid-bg' />
          <View className='hero-content'>
            <Text className='hero-badge'>ABOUT</Text>
            <Text className='hero-title'>关于小程序</Text>
            <Text className='hero-sub'>AI 驱动的世界杯预测平台</Text>
          </View>
          <View className='hero-deco-line' />
        </View>

        {/* 开源项目 */}
        <View className='card card-open'>
          <View className='card-tag-row'>
            <View className='tag tag-blue'><Text>OPEN SOURCE</Text></View>
          </View>
          <Text className='card-head'>开源项目</Text>
          <Text className='card-body-text'>
            本项目完全开源，采用现代前端技术栈构建。我们相信透明与协作的力量，欢迎每一位开发者参与贡献代码、提出 Issue 或 Pull Request。
          </Text>
          <View className='github-box' onClick={handleCopyGithub}>
            <View className='gh-left'>
              <Text className='gh-icon'>⌘</Text>
              <View className='gh-info'>
                <Text className='gh-label'>GitHub Repository</Text>
                <Text className='gh-url'>{GITHUB_URL}</Text>
              </View>
            </View>
            <Text className='gh-action'>点击复制</Text>
          </View>
        </View>

        {/* 版本信息 — 紧凑信息条风格 */}
        <View className='card card-meta'>
          <View className='meta-row'>
            <Text className='meta-label'>版本</Text>
            <Text className='meta-value mono'>v1.0.0</Text>
          </View>
          <View className='meta-divider' />
          <View className='meta-row'>
            <Text className='meta-label'>更新</Text>
            <Text className='meta-value'>2026.05</Text>
          </View>
          <View className='meta-divider' />
          <View className='meta-row'>
            <Text className='meta-label'>联系</Text>
            <Text className='meta-value mono-sm'>andyxu199510@gmail.com</Text>
          </View>
        </View>

      </View>

      {/* ======== 底部签名 ======== */}
      <View className='footer'>
        <View className='footer-line' />
        <Text className='footer-brand'>⚽ AI PREDICTOR</Text>
        <Text className='footer-slogan'>预测快乐 · 理性观赛</Text>
      </View>
    </View>
  )
}
