import { View, Text, Button } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

/**
 * 告别引导弹窗页 — 世界杯落幕，引导用户收藏小程序以便后续承接五大联赛/欧冠等赛事。
 *
 * 实现为「全屏遮罩 + 居中卡片」的弹窗形态：
 * - 点击右上角 x 或底部「进入小程序」按钮 → switchTab 到首页
 * - 展示次数由 app.ts 在 onLaunch 时控制（本地计数 + 后端配置）
 */
export default function Welcome() {
  const handleClose = () => {
    Taro.switchTab({ url: '/pages/index/index' })
  }

  return (
    <View className='welcome-mask' catchMove>
      <View className='welcome-card'>
        {/* 关闭按钮 */}
        <View className='close-btn' onClick={handleClose}>×</View>

        {/* 标题 */}
        <View className='hero-title'>世界杯会落幕，但精彩不会</View>

        {/* 正文 */}
        <View className='essay'>
          <Text className='essay-line'>有人迎来了最后一舞，</Text>
          <Text className='essay-line'>有人完成了梦想，</Text>
          <Text className='essay-line'>有人一战成名，</Text>
          <Text className='essay-line'>有人遗憾离场。</Text>
          <View className='essay-gap' />
          <Text className='essay-line'>谢谢这个夏天，</Text>
          <Text className='essay-line'>陪我们一起见证足球最美好的模样。</Text>
        </View>

        {/* 下一站 */}
        <View className='upcoming'>
          <View className='upcoming-label'>⚽ 更多联赛接入中</View>
          <View className='upcoming-leagues'>
            英超｜西甲｜德甲｜意甲｜法甲｜欧冠……
          </View>
        </View>

        {/* 结尾寄语 */}
        <Text className='blessing'>愿未来的每一场比赛，我们都还在</Text>

        {/* 收藏引导 */}
        <View className='favorite-tip'>
          <Text className='favorite-heart'>❤️</Text>
          <View className='favorite-content'>
            <Text className='favorite-main'>点击右上角 ··· 添加到我的小程序</Text>
            <Text className='favorite-sub'>(本提示仅展示 5 次)</Text>
          </View>
        </View>

        {/* 进入按钮 */}
        <Button className='enter-btn' onClick={handleClose}>进入小程序</Button>
      </View>
    </View>
  )
}
