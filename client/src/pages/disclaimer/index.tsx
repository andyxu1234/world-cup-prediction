import { View, Text } from '@tarojs/components'
import './index.scss'

export default function Disclaimer() {
  return (
    <View className='disclaimer-page'>
      <View className='content'>
        {/* Hero */}
        <View className='hero'>
          <View className='hero-glow' />
          <Text className='hero-label'>DISCLAIMER</Text>
          <Text className='hero-title'>免责声明</Text>
          <Text className='hero-sub'>使用前请仔细阅读</Text>
        </View>
        {/* 免责条款 */}
        <View className='card'>
          <View className='card-header'>
            <View className='card-tag tag-warn'>重要声明</View>
          </View>
          <Text className='card-title'>免责条款</Text>

          <View className='clause-list'>
            {[
              { title: '分析性质声明', text: '本小程序所有 AI 分析内容均由人工智能模型基于公开数据自动生成，仅供研究与内容参考，不构成任何投资或决策建议。' },
              { title: '准确性声明', text: 'AI 分析存在不确定性，结果不保证准确。用户不应将分析内容作为任何投资或决策依据。' },
              { title: '责任限制', text: '用户因参考本小程序分析内容而产生的任何直接或间接损失（包括但不限于经济损失），本小程序开发者不承担任何法律责任。' },
              { title: '合法使用', text: '本小程序不鼓励、不支持任何违反法律法规的行为。用户应遵守所在地区法律法规，合法使用本小程序。' },
              { title: '同意条款', text: '使用本小程序即表示您已阅读、理解并同意本免责声明的全部内容。如不同意，请立即停止使用本小程序。' },
            ].map((item, i) => (
              <View className='clause-item' key={i}>
                <View className='clause-num'><Text>{i + 1}</Text></View>
                <View className='clause-body'>
                  <Text className='clause-title'>{item.title}</Text>
                  <Text className='clause-text'>{item.text}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        {/* 温馨提示 */}
        <View className='card'>
          <View className='card-header'>
            <View className='card-tag tag-green'>温馨提示</View>
          </View>
          <Text className='card-title'>理性观赛</Text>
          <Text className='card-desc'>
            足球比赛充满不确定性，这正是它的魅力所在。AI 分析只是基于历史数据和算法模型的推演结果，无法完全准确预判比赛走向。
          </Text>
          <Text className='card-desc'>
            我们鼓励用户将本小程序作为足球内容分析工具，享受足球带来的乐趣，而非任何投资或决策依据。请理性观赛。
          </Text>
          <View className='highlight-box'>
            <Text className='highlight-text'>享受足球，理性观赛</Text>
          </View>
        </View>

        {/* 版本信息 */}
        <View className='card card-meta'>
          <View className='meta-row'>
            <Text className='meta-label'>更新日期</Text>
            <Text className='meta-value'>2026年5月</Text>
          </View>
          <View className='meta-divider' />
          <View className='meta-row'>
            <Text className='meta-label'>适用范围</Text>
            <Text className='meta-value'>本小程序全部功能</Text>
          </View>
        </View>
      </View>

      {/* 底部 */}
      <View className='footer'>
        <Text className='footer-brand mono'>AI ANALYST</Text>
        <Text className='footer-slogan'>理性观赛 · 享受足球</Text>
      </View>
    </View>
  )
}
