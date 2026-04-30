import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import moneyImg from '@/assets/money.png'
import './index.scss'

export default function Support() {
  return (
    <View className='support-page'>
      <View className='body'>
        {/* Hero 区域 */}
        <View className='hero'>
          <View className='hero-orb hero-orb-1' />
          <View className='hero-orb hero-orb-2' />
          <View className='hero-grid-bg' />
          <View className='hero-content'>
            <Text className='hero-badge'>SUPPORT</Text>
            <Text className='hero-title'>支持开发者</Text>
            <Text className='hero-sub'>你的支持是我们最大的鼓励</Text>
          </View>
          <View className='hero-deco-line' />
        </View>

        {/* 支持说明卡片 */}
        <View className='card card-support'>
          <View className='card-tag-row'>
            <View className='tag tag-amber'><Text>COFFEE</Text></View>
          </View>
          <Text className='card-head'>请我喝杯咖啡 ☕</Text>
          <Text className='card-body-text'>
            如果这个小工具为你带来了便利或乐趣，可以考虑请我喝杯咖啡。每一份支持都是持续迭代的动力。
          </Text>

          {/* 收款码 */}
          <View className='qr-zone'>
            <View className='qr-frame'>
              <Image
                className='qr-img'
                src={moneyImg}
                mode='aspectFit'
                showMenuByLongpress
              />
            </View>
            <Text className='qr-hint'>长按保存收款码</Text>
          </View>

          {/* 支持用途说明 */}
          <View className='support-list'>
            <View className='support-item'>
              <View className='dot dot-1' />
              <Text>所有打赏将用于服务器与模型 API 费用</Text>
            </View>
            <View className='support-item'>
              <View className='dot dot-2' />
              <Text>持续优化 AI 预测准确度与交互体验</Text>
            </View>
            <View className='support-item'>
              <View className='dot dot-3' />
              <Text>你的支持是我们最大的鼓励 ❤️</Text>
            </View>
          </View>
        </View>

        {/* 感谢语 */}
        <View className='card card-thanks'>
          <View className='thanks-icon'>
            <Text className='thanks-emoji'>🙏</Text>
          </View>
          <Text className='thanks-title'>感谢每一位支持者</Text>
          <Text className='thanks-text'>
            无论是一杯咖啡还是一个 Star，都是对我最大的肯定。我会继续努力，让这个小程序越来越好用！
          </Text>
        </View>
      </View>

      {/* 底部签名 */}
      <View className='footer'>
        <View className='footer-line' />
        <Text className='footer-brand'>⚽ AI PREDICTOR</Text>
        <Text className='footer-slogan'>预测快乐 · 理性观赛</Text>
      </View>
    </View>
  )
}
