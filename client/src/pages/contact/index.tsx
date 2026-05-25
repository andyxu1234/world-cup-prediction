import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

const WECHAT_ID = 'AndyXu2020May'
const EMAIL = 'andyxu199510@gmail.com'
const OFFICIAL_ACCOUNT_NAME = 'AI足球先知'
const OFFICIAL_ARTICLE_URL = 'https://mp.weixin.qq.com/s/7Pe3v1qGNt66adAR2vvp_A'

export default function Contact() {
  const handleCopyWechat = () => {
    Taro.setClipboardData({
      data: WECHAT_ID,
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
        {/* 微信号 */}
        <View className='card'>
          <Text className='card-title'>添加作者微信</Text>
          <Text className='card-desc'>
            点击下方微信号即可复制，打开微信搜索添加好友。备注技术交流或者世界杯交流，加你进群。
          </Text>
          <View className='action-box' onClick={handleCopyWechat}>
            <View className='action-left'>
              <View className='action-icon-wrap'>
                <Text className='action-icon'>💬</Text>
              </View>
              <View className='action-info'>
                <Text className='action-label'>微信号</Text>
                <Text className='action-value mono'>{WECHAT_ID}</Text>
              </View>
            </View>
            <Text className='action-btn'>点击复制</Text>
          </View>
        </View>

        {/* 邮箱 */}
        <View className='card'>
          <Text className='card-title'>发送邮件</Text>
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
            点击下方按钮阅读公众号文章，在文章页面即可关注公众号，获取最新世界杯动态和AI预测分析。
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
        <Text className='footer-brand mono'>AI PREDICTOR</Text>
        <Text className='footer-slogan'>预测快乐 · 理性观赛</Text>
      </View>
    </View>
  )
}
