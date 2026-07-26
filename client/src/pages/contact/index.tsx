import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

const WECHAT_IDS = ['xyhu2890', 'AndyXu2020May']
const EMAIL = 'andyxu199510@gmail.com'
const OFFICIAL_ACCOUNT_NAME = 'AI足球先知'
const OFFICIAL_ARTICLE_URL = 'https://mp.weixin.qq.com/s/7Pe3v1qGNt66adAR2vvp_A'

export default function Contact() {
  const handleCopyWechat = (id: string) => {
    Taro.setClipboardData({
      data: id,
      success: () => Taro.showToast({ title: '微信号已复制', icon: 'success' }),
    })
  }

  const handleCopyEmail = () => {
    Taro.setClipboardData({
      data: EMAIL,
      success: () => Taro.showToast({ title: '邮箱已复制', icon: 'success' }),
    })
  }

  const handleCopyAccountName = () => {
    Taro.setClipboardData({
      data: OFFICIAL_ACCOUNT_NAME,
      success: () => Taro.showToast({ title: '公众号名称已复制', icon: 'success' }),
    })
  }

  const handleOpenArticle = () => {
    Taro.navigateTo({
      url: `/pages/webview/index?url=${encodeURIComponent(OFFICIAL_ARTICLE_URL)}`,
    })
  }

  return (
    <View className='contact-page'>
      <View className='content'>
        {/* Hero */}
        <View className='hero'>
          <View className='hero-glow' />
          <Text className='hero-title'>联系作者</Text>
          <Text className='hero-sub'>期待与你交流</Text>
        </View>

        {/* 去广告入口 */}
        <View className='card card-vip'>
          <Text className='card-title'>🚫 去除广告</Text>
          <Text className='card-desc'>
            如果广告影响了你的体验，可以添加作者微信获取帮助，享受纯净无广告体验。添加任意微信即可，备注「去广告」。
          </Text>
          {WECHAT_IDS.map((id, index) => (
            <View
              key={id}
              className={`action-box action-box-vip ${index > 0 ? 'action-box-secondary' : ''}`}
              onClick={() => handleCopyWechat(id)}
            >
              <View className='action-left'>
                <View className='action-icon-wrap action-icon-vip'>
                  <Text className='action-icon'>💬</Text>
                </View>
                <View className='action-info'>
                  <Text className='action-label'>微信号 {index + 1}</Text>
                  <Text className='action-value mono'>{id}</Text>
                </View>
              </View>
              <Text className='action-btn action-btn-vip'>点击复制</Text>
            </View>
          ))}
        </View>

        {/* 微信号 */}
        <View className='card'>
          <Text className='card-title'>交流或反馈</Text>
          <Text className='card-desc'>
            点击下方微信号即可复制，打开微信搜索添加好友。备注技术交流或者世界杯交流，加你进群。
          </Text>
          {WECHAT_IDS.map((id, index) => (
            <View
              key={id}
              className={`action-box ${index > 0 ? 'action-box-secondary' : ''}`}
              onClick={() => handleCopyWechat(id)}
            >
              <View className='action-left'>
                <View className='action-icon-wrap'>
                  <Text className='action-icon'>💬</Text>
                </View>
                <View className='action-info'>
                  <Text className='action-label'>微信号 {index + 1}</Text>
                  <Text className='action-value mono'>{id}</Text>
                </View>
              </View>
              <Text className='action-btn'>点击复制</Text>
            </View>
          ))}
        </View>

        {/* 邮箱 */}
        <View className='card'>
          <Text className='card-title'>商务合作</Text>
          <Text className='card-desc'>
            如有商务合作或较长的反馈内容，欢迎通过邮件联系。
          </Text>
          <View className='action-box' onClick={handleCopyEmail}>
            <View className='action-left'>
              <View className='action-icon-wrap action-icon-purple'>
                <Text className='action-icon'>📧</Text>
              </View>
              <View className='action-info'>
                <Text className='action-label'>邮箱地址</Text>
                <Text className='action-value mono'>{EMAIL}</Text>
              </View>
            </View>
            <Text className='action-btn action-btn-purple'>点击复制</Text>
          </View>
        </View>

        {/* 公众号 - 暂时隐藏，需要时取消注释即可恢复 */}
        {/* <View className='card'>
          <Text className='card-title'>关注公众号</Text>
          <Text className='card-desc'>
            点击下方按钮阅读公众号文章，在文章页面即可关注公众号，获取最新世界杯动态和 AI 赛事分析。
          </Text>
          <View className='action-box' onClick={handleCopyAccountName}>
            <View className='action-left'>
              <View className='action-icon-wrap action-icon-blue'>
                <Text className='action-icon'>📢</Text>
              </View>
              <View className='action-info'>
                <Text className='action-label'>{OFFICIAL_ACCOUNT_NAME}</Text>
                <Text className='action-sub'>复制名称，微信搜索关注</Text>
              </View>
            </View>
            <Text className='action-btn action-btn-blue'>点击复制</Text>
          </View>
          <View className='action-box action-box-secondary' onClick={handleOpenArticle}>
            <View className='action-left'>
              <View className='action-icon-wrap action-icon-blue'>
                <Text className='action-icon'>📄</Text>
              </View>
              <View className='action-info'>
                <Text className='action-label'>阅读公众号文章</Text>
                <Text className='action-sub'>在文章页面直接关注</Text>
              </View>
            </View>
            <Text className='action-btn action-btn-blue'>前往 ›</Text>
          </View>
        </View> */}
      </View>

      {/* 底部 */}
      <View className='footer'>
        <Text className='footer-brand mono'>AI ANALYST</Text>
        <Text className='footer-slogan'>理性观赛 · 享受足球</Text>
      </View>
    </View>
  )
}
