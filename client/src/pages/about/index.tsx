import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

// 假设的收款码图片URL，实际需要替换为真实的图片URL
const DONATION_QR_CODE = 'https://via.placeholder.com/300x300/10b981/ffffff?text=收款码'
const GITHUB_URL = 'https://github.com/your-username/world-cup-prediction'

export default function About() {
  const handleCopyGithub = () => {
    Taro.setClipboardData({
      data: GITHUB_URL,
      success: () => {
        Taro.showToast({ title: 'GitHub地址已复制', icon: 'success' })
      }
    })
  }

  const handleSaveQRCode = () => {
    Taro.showModal({
      title: '保存收款码',
      content: '长按二维码图片可保存到手机',
      showCancel: false,
      confirmText: '知道了'
    })
  }

  return (
    <View className='about-page'>
      {/* 顶部标题区域 */}
      <View className='about-hero'>
        <View className='about-hero-glow' />
        <Text className='about-hero-title'>关于小程序</Text>
        <Text className='about-hero-sub'>世界杯AI预测 · 开源项目</Text>
      </View>

      {/* 内容卡片 */}
      <View className='about-content'>
        {/* GitHub 卡片 */}
        <View className='about-card'>
          <View className='about-card-hd'>
            <View className='about-card-icon' style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}>
              <Text>💻</Text>
            </View>
            <Text className='about-card-title'>开源项目</Text>
          </View>
          <Text className='about-card-desc'>
            这是一个开源的世界杯AI预测小程序，采用现代前端技术栈开发，欢迎贡献代码和提出建议。
          </Text>
          <View className='about-github' onClick={handleCopyGithub}>
            <Text className='about-github-icon'>📋</Text>
            <Text className='about-github-text'>GitHub地址（点击复制）</Text>
          </View>
          <Text className='about-github-url'>{GITHUB_URL}</Text>
        </View>

        {/* 打赏支持卡片 */}
        <View className='about-card'>
          <View className='about-card-hd'>
            <View className='about-card-icon' style={{ background: 'rgba(245,158,11,0.1)', color: '#d97706' }}>
              <Text>❤️</Text>
            </View>
            <Text className='about-card-title'>支持开发者</Text>
          </View>
          <Text className='about-card-desc'>
            如果这个小程序对你有帮助，欢迎打赏支持开发者的持续维护和更新。
          </Text>
          
          {/* 收款码 */}
          <View className='about-qr-wrapper'>
            <Image 
              className='about-qr-code' 
              src={DONATION_QR_CODE} 
              mode='aspectFit'
              onClick={handleSaveQRCode}
            />
            <Text className='about-qr-tip'>长按保存收款码</Text>
          </View>

          <View className='about-donation-info'>
            <Text className='about-donation-title'>打赏说明：</Text>
            <Text className='about-donation-item'>• 所有打赏将用于服务器费用和维护</Text>
            <Text className='about-donation-item'>• 我们会持续更新和改进功能</Text>
            <Text className='about-donation-item'>• 感谢你的支持！❤️</Text>
          </View>
        </View>

        {/* 版本信息 */}
        <View className='about-card'>
          <View className='about-card-hd'>
            <View className='about-card-icon' style={{ background: 'rgba(168,85,247,0.1)', color: '#a855f7' }}>
              <Text>📱</Text>
            </View>
            <Text className='about-card-title'>版本信息</Text>
          </View>
          <View className='about-version'>
            <View className='about-version-item'>
              <Text className='about-version-label'>当前版本</Text>
              <Text className='about-version-value'>v1.0.0</Text>
            </View>
            <View className='about-version-item'>
              <Text className='about-version-label'>更新日期</Text>
              <Text className='about-version-value'>2024年11月</Text>
            </View>
            <View className='about-version-item'>
              <Text className='about-version-label'>技术支持</Text>
              <Text className='about-version-value'>worldcupai@example.com</Text>
            </View>
          </View>
        </View>
      </View>

      {/* 底部致谢 */}
      <View className='about-footer'>
        <Text className='about-footer-text'>感谢使用世界杯AI预测小程序</Text>
        <Text className='about-footer-sub'>⚽ 预测快乐，理性观赛！</Text>
      </View>
    </View>
  )
}