import { useEffect, useState, useCallback, useRef } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { useMatchStore, useUserStore, useLeaderboardStore } from '@/stores'
import { shallow } from 'zustand/shallow'
import './index.scss'

const CHIPS = ['小组赛', '淘汰赛', '今日', '明日', '已结束']

// 默认 fallback 图标（当 flag_url 为空或加载失败时使用）
const DEFAULT_FLAG_ICON = '⚽'

/** 国旗图片组件：直接用外部 URL，加载失败回退 */
function FlagImage({ src, className }: { src: string; className: string }) {
  const [failed, setFailed] = useState(false)
  if (failed || !src) return <View className={`${className.replace('flag-img', 'flag-fallback')}`}>{DEFAULT_FLAG_ICON}</View>
  return <Image className={className} src={src} mode='aspectFit' onError={() => setFailed(true)} />
}

const ROUND_CN_MAP: Record<string, string> = {
  'Group Stage - 1': '小组赛第1轮',
  'Group Stage - 2': '小组赛第2轮',
  'Group Stage - 3': '小组赛第3轮',
  'Round of 32': '三十二强赛',
  'Round of 16': '十六强赛',
  'Quarter-finals': '四分之一决赛',
  'Semi-finals': '半决赛',
  '3rd Place Final': '季军赛',
  'Final': '决赛',
}

function getRoundLabel(round: string): string {
  return ROUND_CN_MAP[round] || round
}

function formatMatchTime(timeStr: string | null): string {
  if (!timeStr) return '待定'
  const d = new Date(timeStr)
  const month = d.getMonth() + 1
  const day = d.getDate()
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekDays[d.getDay()]
  const hour24 = d.getHours()
  const min = d.getMinutes().toString().padStart(2, '0')
  const period = hour24 < 6 ? '凌晨' : hour24 < 12 ? '上午' : hour24 < 14 ? '中午' : hour24 < 18 ? '下午' : '晚上'
  const hour12 = hour24 === 0 ? 12 : hour24 > 12 ? hour24 - 12 : hour24
  return `${month}月${day}日 ${weekday} ${period}${hour12.toString().padStart(2, '0')}:${min}`
}

function formatVoteCount(count: number): string {
  if (count >= 1000) return `${(count / 1000).toFixed(count % 1000 === 0 ? 0 : 1)}K`
  return String(count)
}

function getStatusLabel(status: string) {
  if (status === 'finished') return { text: '已结束', cls: 'badge-red' }
  if (status === 'live') return { text: '进行中', cls: 'badge-green' }
  return null
}

export default function Index() {
  // 使用 shallow 浅比较：只有 matches 数组引用变化时才重渲染
  const matches = useMatchStore((s) => s.matches, shallow)
  const homeStats = useMatchStore((s) => s.homeStats)
  const fetchMatches = useMatchStore((s) => s.fetchMatches)
  const fetchHomeStats = useMatchStore((s) => s.fetchHomeStats)
  const loginReady = useUserStore((s) => s.loginReady)
  const [activeChip, setActiveChip] = useState('小组赛')
  const navigatingRef = useRef<Set<number>>(new Set())

  // 所有 hooks 必须在条件返回之前调用（React Rules of Hooks）
  useEffect(() => {
    if (!loginReady) return
    fetchHomeStats()
  }, [fetchHomeStats, loginReady])

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
    title: 'AI 预测世界杯 · 和 AI 一起预测比赛结果',
    path: '/pages/index/index',
  }))

  // 分享到朋友圈
  useShareTimeline(() => ({
    title: 'AI 预测世界杯 · 和 AI 一起预测比赛结果',
    query: '',
  }))

  useEffect(() => {
    if (!loginReady) return
    const params: any = {}
    // 已结束：只展示所有已完成的比赛（不限轮次、不限日期）
    if (activeChip === '已结束') {
      params.status = 'finished'
    } else {
      // 其余标签：全部排除已结束的比赛，只显示未开始/进行中的比赛
      params.status_not = 'finished'
    }
    if (activeChip === '小组赛') params.round = ['Group Stage - 1', 'Group Stage - 2', 'Group Stage - 3']
    if (activeChip === '淘汰赛') params.round = ['Round of 32', 'Round of 16', 'Quarter-finals', 'Semi-finals', '3rd Place Final', 'Final']
    if (activeChip === '今日') params.date = new Date().toISOString().slice(0, 10)
    if (activeChip === '明日') {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      params.date = d.toISOString().slice(0, 10)
    }
    fetchMatches(params)
  }, [activeChip, fetchMatches, loginReady])

  // ===== loginReady 为 false 时返回加载页 =====
  if (!loginReady) {
    return (
      <View className='index-page loading-page'>
        <Text className='loading-text'>加载中...</Text>
      </View>
    )
  }

  return (
    <View className='index-page'>
      {/* Hero 区域 */}
      <View className='hero'>
        <View className='hero-glow' />
        <View className='hero-title-row'>
          <Text className='hero-title'>2026 世界杯</Text>
          <Text className='hero-logo'>🏆</Text>
        </View>
        <Text className='hero-sub'>{homeStats?.active_ai_models ?? '--'} 个 AI 模型 · 智能预测 · 人机对决</Text>
        <View className='hero-stats'>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>104</Text>
            <Text className='hero-stat-label'>总场次</Text>
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
            <Text className='hero-stat-label'>AI预测总数</Text>
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

      {/* 筛选条 */}
      <ScrollView scrollX className='chips-scroll'>
        <View className='chips'>
          {CHIPS.map((chip) => (
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

      {/* 比赛列表 */}
      <ScrollView scrollY className='match-list'>
        {matches.length === 0 && (
          <View className='empty'>
            <Text className='empty-icon'>⚽</Text>
            <Text className='empty-text'>暂无比赛数据</Text>
          </View>
        )}
        {matches.map((match) => {
          const statusInfo = getStatusLabel(match.status)
          return (
            <View key={match.id} className='m-card'>
              <View className='m-card-hd'>
                <Text className='m-round'>{getRoundLabel(match.round)}</Text>
                {statusInfo ? (
                  <Text className={`badge ${statusInfo.cls}`}>{statusInfo.text}</Text>
                ) : (
                  <Text className='m-time'>{formatMatchTime(match.match_time)}</Text>
                )}
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
                  AI 共识：<Text className='highlight'>{match.summary?.short_summary || '--'}</Text>
                </Text>
                <Text
                  className='m-action'
                  onClick={(e) => {
                    e.stopPropagation()
                    goToDetail(match.id)
                  }}
                >查看预测 ›</Text>
              </View>
            </View>
          )
        })}
      </ScrollView>
    </View>
  )
}
