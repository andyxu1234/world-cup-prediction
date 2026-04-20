import { useEffect, useState, useCallback, useRef } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useMatchStore } from '@/stores'
import { shallow } from 'zustand/shallow'
import './index.scss'

const CHIPS = ['今日', '明日', '小组赛', '淘汰赛', '已结束']

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
  const hour = d.getHours().toString().padStart(2, '0')
  const min = d.getMinutes().toString().padStart(2, '0')
  return `${month}月${day}日 ${hour}:${min}`
}

function getStatusLabel(status: string) {
  if (status === 'finished') return { text: '已结束', cls: 'badge-red' }
  if (status === 'live') return { text: '进行中', cls: 'badge-green' }
  return null
}

export default function Index() {
  // 使用 shallow 浅比较：只有 matches 数组引用变化时才重渲染
  const matches = useMatchStore((s) => s.matches, shallow)
  const fetchMatches = useMatchStore((s) => s.fetchMatches)
  const [activeChip, setActiveChip] = useState('今日')
  const navigatingRef = useRef<Set<number>>(new Set())

  const goToDetail = useCallback((id: number) => {
    if (navigatingRef.current.has(id)) return
    navigatingRef.current.add(id)
    Taro.navigateTo({
      url: `/pages/match-detail/index?id=${id}`,
      complete: () => { navigatingRef.current.delete(id) },
      fail: () => { navigatingRef.current.delete(id) },
    })
  }, [])

  useEffect(() => {
    const params: any = {}
    if (activeChip === '已结束') params.status = 'finished'
    if (activeChip === '小组赛') params.round = ['Group Stage - 1', 'Group Stage - 2', 'Group Stage - 3']
    if (activeChip === '淘汰赛') params.round = ['Round of 32', 'Round of 16', 'Quarter-finals', 'Semi-finals', '3rd Place Final', 'Final']
    if (activeChip === '今日') params.date = new Date().toISOString().slice(0, 10)
    if (activeChip === '明日') {
      const d = new Date()
      d.setDate(d.getDate() + 1)
      params.date = d.toISOString().slice(0, 10)
    }
    fetchMatches(params)
  }, [activeChip, fetchMatches])

  return (
    <View className='index-page'>
      {/* 导航栏 */}
      <View className='nav'>
        <Text className='nav-title'>AI PREDICTOR</Text>
      </View>

      {/* Hero 区域 */}
      <View className='hero'>
        <View className='hero-glow' />
        <Text className='hero-title'>2026 FIFA WORLD CUP</Text>
        <Text className='hero-sub'>5 个 AI 模型 · 实时预测 · 人机对决</Text>
        <View className='hero-stats'>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>104</Text>
            <Text className='hero-stat-label'>总场次</Text>
          </View>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>5</Text>
            <Text className='hero-stat-label'>AI 选手</Text>
          </View>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>520</Text>
            <Text className='hero-stat-label'>预测总数</Text>
          </View>
          <View className='hero-stat'>
            <Text className='hero-stat-num'>12K</Text>
            <Text className='hero-stat-label'>人类投票</Text>
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
