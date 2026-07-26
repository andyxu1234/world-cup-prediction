import { useEffect, useState, useCallback, useRef } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline, useDidShow } from '@tarojs/taro'
import { useMatchStore, useLeaderboardStore, useLeagueStore, useRoundStore, getRoundLabel } from '@/stores'
import { shallow } from 'zustand/shallow'
import LeaguePicker from '@/components/LeaguePicker'
import { formatMatchTime, getBeijingDateStr } from '@/utils/time'
import './index.scss'

// 默认 Tab 配置（后端接口失败时的 fallback，顺序与后端 get_home_tabs 一致）
const DEFAULT_CHIPS = ['近期赛事', '今日', '明日', '已结束']

// 默认 fallback 图标（当 flag_url 为空或加载失败时使用）
const DEFAULT_FLAG_ICON = '⚽'

// 首页比赛列表单次最多拉取条数，防止多联赛下一次性加载过多导致小程序卡顿
const MATCH_LIST_LIMIT = 50

/** 国旗图片组件：直接用外部 URL，加载失败回退 */
function FlagImage({ src, className }: { src: string; className: string }) {
  const [failed, setFailed] = useState(false)
  if (failed || !src) return <View className={`${className.replace('flag-img', 'flag-fallback')}`}>{DEFAULT_FLAG_ICON}</View>
  return <Image className={className} src={src} mode='aspectFit' onError={() => setFailed(true)} />
}

function formatVoteCount(count: number): string {
  return String(count)
}


function getStatusLabel(status: string) {
  if (status === 'finished') return { text: '已结束', cls: 'badge-red' }
  if (status === 'live') return { text: '进行中', cls: 'badge-green' }
  return null
}



export default function Index() {
  // 订阅轮次映射加载状态：数据到达后自动重渲染（映射函数本身用纯函数 getRoundLabel）
  useRoundStore((s) => s.ready)
  // 使用 shallow 浅比较：只有 matches 数组引用变化时才重渲染
  const matches = useMatchStore((s) => s.matches, shallow)
  const homeStats = useMatchStore((s) => s.homeStats)
  const homeTabs = useMatchStore((s) => s.homeTabs)
  const fetchMatches = useMatchStore((s) => s.fetchMatches)
  const fetchHomeStats = useMatchStore((s) => s.fetchHomeStats)
  const fetchHomeTabs = useMatchStore((s) => s.fetchHomeTabs)
  // 多联赛：当前选中联赛集合（可多选，混合展示）
  const fetchLeagues = useLeagueStore((s) => s.fetchLeagues)
  const selectedLeagueIds = useLeagueStore((s) => s.selectedLeagueIds, shallow)
  // 默认选中第一个 tab（近期赛事），后端 tabs 加载后自动同步
  const [activeChip, setActiveChip] = useState(DEFAULT_CHIPS[0])
  // 优先使用后端返回的 Tab 列表，未加载时使用默认配置
  const chips = homeTabs.length > 0 ? homeTabs.map(t => t.label) : DEFAULT_CHIPS

  // 后端 tabs 加载完成后，自动选中后端指定的第一个 tab
  useEffect(() => {
    if (homeTabs.length > 0) {
      setActiveChip(homeTabs[0].label)
    }
  }, [homeTabs])
  const navigatingRef = useRef<Set<number>>(new Set())
  // 动态计算 ScrollView 高度，精确适配不同设备屏幕（解决 iPhone 7 Plus 等设备底部留白问题）
  // 根因：CSS 中 calc(100vh - 560px) 的 560px 是 CSS px，但页面元素全部用 rpx，
  //       不同设备的 rpx→px 转换比例不同，导致固定 px 减去值在部分设备上不准确
  const [scrollHeight, setScrollHeight] = useState<string>('')
  // 所有 hooks 必须在条件返回之前调用（React Rules of Hooks）
  useEffect(() => {
    // 延迟到首帧渲染完成后查询布局，确保 DOM 已就位
    const timer = setTimeout(() => {
      try {
        const query = Taro.createSelectorQuery()
        query.select('.hero').boundingClientRect()
        query.select('.chips-scroll').boundingClientRect()
        query.select('.league-picker').boundingClientRect()
        query.exec((res) => {
          const heroRect = res[0]
          const chipsRect = res[1]
          const switcherRect = res[2]
          if (!heroRect || !chipsRect) {
            setScrollHeight('calc(100vh - 560px)')
            return
          }
          const sysInfo = Taro.getSystemInfoSync()
          const { windowHeight } = sysInfo
          // ScrollView 高度 = 屏幕可用高度 - Hero实际高度 - Chips实际高度 - 联赛切换器高度
          // 不再用硬编码像素值估算
          const switcherH = switcherRect ? switcherRect.height : 0
          const available = Math.max(
            windowHeight - heroRect.height - chipsRect.height - switcherH,
            200 // 兜底最小高度，防止极端情况
          )
          setScrollHeight(`${available}px`)
        })
      } catch {
        setScrollHeight('calc(100vh - 560px)')
      }
    }, 300) // 等待首帧渲染完成
    return () => clearTimeout(timer)
  }, [])
  // 首次加载联赛列表
  useEffect(() => {
    fetchLeagues()
  }, [fetchLeagues])

  useEffect(() => {
    fetchHomeStats()
    fetchHomeTabs(selectedLeagueIds.length > 0 ? selectedLeagueIds : undefined)
  }, [fetchHomeStats, fetchHomeTabs, selectedLeagueIds])


  const goToDetail = useCallback((id: number) => {
    if (navigatingRef.current.has(id)) return
    navigatingRef.current.add(id)
    Taro.navigateTo({
      url: `/pages/match-detail/index?id=${id}`,
      complete: () => { navigatingRef.current.delete(id) },
      fail: () => { navigatingRef.current.delete(id) },
    })
  }, [])

  // 分享给好友
  useShareAppMessage(() => ({
    title: 'AI 足球分析 · 多模型赛事解读',
    path: '/pages/index/index',
  }))

  // 分享到朋友圈
  useShareTimeline(() => ({
    title: 'AI 足球分析 · 多模型赛事解读',
    query: '',
  }))

  useEffect(() => {
    const params: any = {}
    if (selectedLeagueIds.length > 0) params.league_ids = selectedLeagueIds
    // 已结束：只展示所有已完成的比赛（不限轮次、不限日期），按时间倒序
    if (activeChip === '已结束') {
      params.status = 'finished'
      params.sort_order = 'desc'
    } else {
      // 其余标签（近期赛事/今日/明日）：全部排除已结束的比赛，只显示未开始/进行中的比赛
      params.status_not = 'finished'
    }
    if (activeChip === '今日') params.date = getBeijingDateStr()
    if (activeChip === '明日') {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      params.date = getBeijingDateStr(d)
    }
    params.limit = MATCH_LIST_LIMIT
    fetchMatches(params)
  }, [activeChip, fetchMatches, selectedLeagueIds])

  // Tab 切换回来时刷新数据
  useDidShow(() => {
    fetchHomeStats()
    const params: any = {}

    if (selectedLeagueIds.length > 0) params.league_ids = selectedLeagueIds
    if (activeChip === '已结束') {
      params.status = 'finished'
      params.sort_order = 'desc'
    } else {
      // 近期赛事/今日/明日：只显示未结束的比赛
      params.status_not = 'finished'
    }
    if (activeChip === '今日') params.date = getBeijingDateStr()
    if (activeChip === '明日') {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      params.date = getBeijingDateStr(d)
    }
    params.limit = MATCH_LIST_LIMIT
    fetchMatches(params)
  })

  // 渲染比赛列表
  const renderContent = () => {
    return (

      <View>
        {matches.length === 0 && (
          <View className='empty'>
            <Text className='empty-icon'>⚽</Text>
            <Text className='empty-text'>暂无比赛数据</Text>
          </View>
        )}
        {matches.map((match, idx) => {
          const statusInfo = getStatusLabel(match.status)
          return (
            <View key={match.id}>
              <View className='m-card' onClick={() => goToDetail(match.id)}>
                <View className='m-card-hd'>
                  <Text className='m-round'>
                    {match.league?.cn_name || match.league?.name ? (
                      <Text className='m-league'>{match.league?.cn_name || match.league?.name} </Text>
                    ) : null}
                    {getRoundLabel(match.round)}
                  </Text>
                  {statusInfo && (
                    <Text className={`badge ${statusInfo.cls}`}>{statusInfo.text}</Text>
                  )}
                  <Text className='m-time'>{formatMatchTime(match.match_time)}</Text>
                </View>
                <View className='m-teams'>
                  <View className='m-team'>
                    <FlagImage src={match.home_team.flag_url || ''} className='flag-img' />
                    <Text className='m-team-name'>{match.home_team.cn_name || match.home_team.name}</Text>
                  </View>
                  {match.status === 'finished' ? (
                    <Text className='m-score mono'>{match.home_score}:{match.away_score}</Text>
                  ) : (
                    <Text className='m-vs mono'>VS</Text>
                  )}
                  <View className='m-team'>
                    <FlagImage src={match.away_team.flag_url || ''} className='flag-img' />
                    <Text className='m-team-name'>{match.away_team.cn_name || match.away_team.name}</Text>
                  </View>
                </View>
                <View className='m-card-ft'>
                  <Text className='m-consensus'>
                    AI 观点：<Text className='highlight'>{match.summary?.short_summary || '--'}</Text>
                  </Text>
                  <Text className='m-action'>查看分析 ›</Text>
                </View>
              </View>
            </View>
          )
        })}
      </View>
    )
  }

  return (
    <View className='index-page'>
      {/* Hero 区域 */}
      <View className='hero'>
        <View className='hero-glow' />
        <View className='hero-title-row'>
          <Text className='hero-title'>AI足球分析</Text>
        </View>
        <Text className='hero-sub'>{homeStats?.total_leagues ?? '--'}大赛事 · {homeStats?.active_ai_models ?? '--'} 个 AI 模型 · 多模型赛事分析</Text>

        <View className='hero-stats'>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>{homeStats?.total_matches ?? '--'}</Text>
            <Text className='hero-stat-label'>总场次</Text>
          </View>
          <View
            className='hero-stat hero-stat-clickable'
            onClick={() => Taro.switchTab({ url: '/pages/data/index' })}
          >
            <Text className='hero-stat-num'>{homeStats?.total_leagues ?? '--'}</Text>
            <Text className='hero-stat-label'>赛事</Text>
          </View>
          <View
            className='hero-stat hero-stat-clickable'
            onClick={() => {
              useLeaderboardStore.getState().setActiveTab('ai')
              Taro.switchTab({ url: '/pages/leaderboard/index' })
            }}
          >
            <Text className='hero-stat-num'>{homeStats?.active_ai_models ?? '--'}</Text>
            <Text className='hero-stat-label'>AI 模型</Text>
          </View>

          <View
            className='hero-stat hero-stat-clickable'
            onClick={() => {
              useLeaderboardStore.getState().setActiveTab('ai')
              Taro.switchTab({ url: '/pages/leaderboard/index' })
            }}
          >
            <Text className='hero-stat-num'>{homeStats?.total_predictions ?? '--'}</Text>
            <Text className='hero-stat-label'>AI分析总数</Text>
          </View>
          <View
            className='hero-stat hero-stat-clickable'
            onClick={() => {
              useLeaderboardStore.getState().setActiveTab('human')
              Taro.switchTab({ url: '/pages/leaderboard/index' })
            }}
          >
            <Text className='hero-stat-num'>{formatVoteCount(homeStats?.total_user_predictions ?? 0)}</Text>
            <Text className='hero-stat-label'>人类预测总场次</Text>
          </View>
        </View>
      </View>

      {/* 筛选栏：联赛下拉 + 筛选 Tab 同一行 */}
      <View className='filter-row'>
        {selectedLeagueIds.length > 0 && (
          <LeaguePicker />
        )}
        <ScrollView scrollX className='chips-scroll'>
        <View className='chips'>
          {chips.map((chip) => (
            <View
              key={chip}
              className={`chip ${activeChip === chip ? 'active' : ''}`}
              onClick={() => setActiveChip(chip)}
            >
              <Text>{chip}</Text>
            </View>
          ))}
        </View>
        </ScrollView>
      </View>

      {/* 内容区域 */}
      <ScrollView scrollY className='match-list' style={scrollHeight ? { height: scrollHeight } : undefined}>
        {renderContent()}
      </ScrollView>
    </View>
  )
}
