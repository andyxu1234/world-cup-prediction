import { View, Text } from '@tarojs/components'
import Taro from '@tarojs/taro'
import './index.scss'

const GITHUB_URL = 'https://github.com/AndyXu-Citi/world-cup-prediction'

const TABS = [
  {
    icon: '🏠',
    name: '首页',
    tag: '首页',
    tagColor: 'green',
    title: '比赛中心',
    desc: '实时查看 2026 世界杯全部 104 场比赛，获取 AI 智能预测分析。',
    features: [
      '数据总览：总场次、活跃 AI 模型数、AI/人类预测总数',
      '智能筛选：按小组赛、淘汰赛、今日、明日、已结束快速切换',
      '比赛卡片：对阵双方国旗、队名、比分或 VS、比赛时间、轮次',
      'AI 共识摘要：每场比赛展示 AI 综合预测结论',
      '点击进入详情：查看各 AI 模型的独立预测与信心指数',
    ],
  },
  {
    icon: '🏆',
    name: '排行',
    tag: '排行',
    tagColor: 'gold',
    title: 'AI 实力排行',
    desc: '多维度排名 10 个 AI 模型的预测准确率，支持人机对决。',
    features: [
      'AI 排行：展示各模型的胜负命中率、比分命中率、预测场次',
      '人机对决：AI 与人类用户混合排名，一决高下',
      '轮次筛选：全部、小组赛、淘汰赛三种统计范围',
      '排序模式：综合、胜负命中率、比分命中率（支持升降序）',
      '模型详情：点击 AI 条目查看专属预测历史与风格标签',
      '倒计时：比赛开始前展示 2026 世界杯开幕倒计时',
    ],
  },
  {
    icon: '😂',
    name: '打脸',
    tag: '打脸',
    tagColor: 'red',
    title: 'AI 翻车现场',
    desc: '收集 AI 预测中最离谱的翻车名场面，看看谁被打脸最惨。',
    features: [
      '三种排序：最新翻车、高信心翻车、比分离谱',
      '翻车卡片：AI 模型头像、比赛信息、预测 vs 实际比分对比',
      '信心指数：可视化展示 AI 当时的信心值（进度条 + 数值）',
      '偏差标签：显示比分偏差球数，越高越离谱',
      '10 个 AI 模型：DeepSeek、GPT、Claude、Gemini 等全覆盖',
      '无限滚动：分页加载，上拉查看更多翻车名场面',
    ],
  },
  {
    icon: '👤',
    name: '我的',
    tag: '我的',
    tagColor: 'blue',
    title: '个人中心',
    desc: '管理个人资料、查看预测战绩、分享小程序给好友。',
    features: [
      '资料管理：自定义头像和昵称',
      '战绩统计：已预测场次、胜负正确数、比分命中数',
      '我的战绩：查看完整预测历史记录',
      '分享功能：一键分享给好友或转发到朋友圈',
    ],
  },
]

export default function About() {
  const handleCopyGithub = () => {
    Taro.setClipboardData({
      data: GITHUB_URL,
      success: () => Taro.showToast({ title: 'GitHub地址已复制', icon: 'success' }),
    })
  }

  return (
    <View className='about-page'>
      <View className='content'>
        {/* Hero */}
        <View className='hero'>
          <View className='hero-glow' />
          <Text className='hero-title'>关于小程序</Text>
          <Text className='hero-sub'>AI 驱动的世界杯预测平台</Text>
        </View>

        {/* 简介 */}
        <View className='card'>
          <Text className='card-title'>AI 预测世界杯</Text>
          <Text className='card-desc'>
            本小程序汇聚 10 个主流 AI 模型，对 2026 世界杯全部 104 场比赛进行智能预测。你可以查看各 AI 的预测结果、对比准确率，也可以亲自下场预测，与 AI 一决高下。
          </Text>
        </View>

        {/* 四个 Tab 页面介绍 */}
        {TABS.map((tab) => (
          <View className='card card-tab' key={tab.tag}>
            <View className='card-header'>
              <View className={`card-tag tag-${tab.tagColor}`}>{tab.tag}</View>
            </View>
            <View className='tab-head'>
              <Text className='tab-icon'>{tab.icon}</Text>
              <Text className='tab-title'>{tab.title}</Text>
            </View>
            <Text className='card-desc'>{tab.desc}</Text>
            <View className='feature-list'>
              {tab.features.map((f, i) => (
                <View className='feature-item' key={i}>
                  <View className='feature-dot' />
                  <Text className='feature-text'>{f}</Text>
                </View>
              ))}
            </View>
          </View>
        ))}

        {/* 开源 */}
        <View className='card'>
          <View className='card-header'>
            <View className='card-tag tag-blue'>开源</View>
          </View>
          <Text className='card-title'>开源项目</Text>
          <Text className='card-desc'>
            本项目完全开源，欢迎参与贡献代码、提出 Issue 或 Pull Request。
          </Text>
          <View className='link-box' onClick={handleCopyGithub}>
            <View className='link-left'>
              <View className='link-icon-wrap'>
                <Text className='link-icon'>⌘</Text>
              </View>
              <View className='link-info'>
                <Text className='link-label'>GitHub Repository</Text>
                <Text className='link-url mono'>{GITHUB_URL}</Text>
              </View>
            </View>
            <Text className='link-action'>点击复制</Text>
          </View>
        </View>

        {/* 版本信息 */}
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
        </View>
      </View>

      {/* 底部 */}
      <View className='footer'>
        <Text className='footer-brand mono'>AI PREDICTOR</Text>
        <Text className='footer-slogan'>预测快乐 · 理性观赛</Text>
      </View>
    </View>
  )
}
