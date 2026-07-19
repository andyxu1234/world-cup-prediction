import { useEffect, useState } from 'react'
import { View, Text, Image, ScrollView } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { getTeamDetail, TeamDetailOut, resolveAvatarUrl } from '@/services/api'
import './index.scss'

function SafeImage({ src, fallbackText, className }: { src: string | null | undefined; fallbackText: string; className?: string }) {
  const [err, setErr] = useState(false)
  const url = src ? resolveAvatarUrl(src) : ''
  if (!url || err) {
    return (
      <View className={`safe-img-fallback ${className || ''}`}>
        <Text className='safe-img-letter'>{fallbackText.slice(0, 1).toUpperCase()}</Text>
      </View>
    )
  }
  return <Image className={className} src={url} mode='aspectFit' onError={() => setErr(true)} />
}

function toText(value: any, fallback = ''): string {
  if (value == null) return fallback
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  return fallback
}

interface StatRow { leagueName?: string; total?: Record<string, any> }

export default function TeamDetailPage() {
  const router = useRouter()
  const id = Number(router.params.id)
  const [data, setData] = useState<TeamDetailOut | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const d = await getTeamDetail(id)
        if (!cancelled) setData(d)
      } catch {
        if (!cancelled) setData(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [id])

  useEffect(() => {
    if (data) Taro.setNavigationBarTitle({ title: data.cn_name || data.name })
  }, [data])

  const seasonStats: StatRow[] = Array.isArray(data?.season_stats) ? (data!.season_stats as StatRow[]) : []
  const formMatches: any[] = (data?.recent_form && (data.recent_form as any).matches) || []

  const formResults = formMatches.map((m) => {
    const isHome = m.home === data?.name
    const score = (m.score || '').toString()
    const mm = score.match(/(\d+)\D+(\d+)/)
    let result = ''
    if (mm) {
      const a = Number(mm[1])
      const b = Number(mm[2])
      if (a === b) result = 'D'
      else if (isHome ? a > b : a < b) result = 'W'
      else result = 'L'
    }
    return { ...m, result }
  })

  useShareAppMessage(() => ({
    title: `${data?.cn_name || data?.name || '球队'} 数据`,
    path: `/pages/team-detail/index?id=${id}`,
  }))
  useShareTimeline(() => ({
    title: `${data?.cn_name || data?.name || '球队'} 数据`,
    query: `id=${id}`,
  }))

  return (
    <View className='detail-page'>
      {loading && <View className='detail-loading'><Text>加载中...</Text></View>}
      {!loading && !data && (
        <View className='detail-empty'><Text>未找到该球队信息</Text></View>
      )}
      {!loading && data && (
        <ScrollView scrollY className='detail-scroll'>
          <View className='detail-header'>
            <SafeImage src={data.flag_url} fallbackText={toText(data.cn_name || data.name, '?')} className='detail-avatar' />
            <View className='detail-title'>
              <Text className='detail-name'>{toText(data.cn_name || data.name)}</Text>
              {data.fifa_rank != null && <Text className='detail-sub'>FIFA 排名 #{toText(data.fifa_rank)}</Text>}
              {data.group_name && <Text className='detail-sub'>小组：{toText(data.group_name)}</Text>}
            </View>
          </View>

          <View className='detail-section'>
            <Text className='detail-section-title'>赛季统计</Text>
            {seasonStats.length === 0 && <Text className='detail-hint'>暂无数据</Text>}
            {seasonStats.map((s, i) => {
              const t = s.total || {}
              return (
                <View className='stat-card' key={i}>
                  <Text className='stat-card-league'>{toText(s.leagueName, '赛事')}</Text>
                  <View className='stat-card-grid'>
                    <View className='stat-cell'><Text className='stat-cell-num'>{toText(t.games ?? 0)}</Text><Text className='stat-cell-label'>赛</Text></View>
                    <View className='stat-cell'><Text className='stat-cell-num'>{toText(t.wins ?? 0)}</Text><Text className='stat-cell-label'>胜</Text></View>
                    <View className='stat-cell'><Text className='stat-cell-num'>{toText(t.draws ?? 0)}</Text><Text className='stat-cell-label'>平</Text></View>
                    <View className='stat-cell'><Text className='stat-cell-num'>{toText(t.loses ?? 0)}</Text><Text className='stat-cell-label'>负</Text></View>
                    <View className='stat-cell'>
                      <Text className='stat-cell-num'>{toText(t.scoredGoals ?? 0)}/{toText(t.receivedGoals ?? 0)}</Text>
                      <Text className='stat-cell-label'>进/失</Text>
                    </View>
                  </View>
                </View>
              )
            })}
          </View>

          <View className='detail-section'>
            <Text className='detail-section-title'>近期战绩</Text>
            {formResults.length === 0 && <Text className='detail-hint'>暂无数据</Text>}
            <View className='form-list'>
              {formResults.map((m, i) => (
                <View className='form-item' key={i}>
                  <Text className={`form-badge ${m.result ? m.result.toLowerCase() : ''}`}>{toText(m.result, '-')}</Text>
                  <View className='form-match'>
                    <Text className='form-team'>{toText(m.home)}</Text>
                    <Text className='form-score'>{toText(m.score, '-')}</Text>
                    <Text className='form-team'>{toText(m.away)}</Text>
                  </View>
                  <Text className='form-date'>{toText(m.date)}</Text>
                </View>
              ))}
            </View>
          </View>
        </ScrollView>
      )}
    </View>
  )
}
