import { useEffect, useState, useMemo } from 'react'
import { View, Text, Image, ScrollView } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { getPlayerDetail, PlayerDetailOut, PlayerSeasonStatOut, resolveAvatarUrl, proxiedSofifa } from '@/services/api'
import './index.scss'

function SafeImage({ src, fallbackSrc, fallbackText, className }: { src: string | null | undefined; fallbackSrc?: string | null | undefined; fallbackText: string; className?: string }) {
  const [err1, setErr1] = useState(false)
  const [err2, setErr2] = useState(false)
  const url1 = src ? proxiedSofifa(resolveAvatarUrl(src)) : ''
  const url2 = fallbackSrc ? proxiedSofifa(resolveAvatarUrl(fallbackSrc)) : ''

  if (!url1 || err1) {
    if (!url2 || err2) {
      return (
        <View className={`safe-img-fallback ${className || ''}`}>
          <Text className='safe-img-letter'>{fallbackText.slice(0, 1).toUpperCase()}</Text>
        </View>
      )
    }
    return <Image className={className} src={url2} mode='aspectFit' onError={() => setErr2(true)} />
  }

  return <Image className={className} src={url1} mode='aspectFit' onError={() => setErr1(true)} />
}

export default function PlayerDetailPage() {
  const router = useRouter()
  const id = Number(router.params.id)
  const leagueIdParam = router.params.league_id ? Number(router.params.league_id) : null
  const [data, setData] = useState<PlayerDetailOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(leagueIdParam)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const d = await getPlayerDetail(id, leagueIdParam)
        if (!cancelled) {
          setData(d)
          setSelectedLeagueId(leagueIdParam ?? (d.stats[0]?.league_id ?? null))
        }
      } catch {
        if (!cancelled) setData(null)
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [id])

  const currentStat: PlayerSeasonStatOut | null = useMemo(
    () => data?.stats.find((s) => s.league_id === selectedLeagueId) ?? data?.stats[0] ?? null,
    [data, selectedLeagueId],
  )

  const displayName = data?.cn_name || data?.name || '球员'

  useEffect(() => {
    if (data) Taro.setNavigationBarTitle({ title: displayName })
  }, [data, displayName])

  useShareAppMessage(() => ({
    title: `${displayName} 数据`,
    path: `/pages/player-detail/index?id=${id}&league_id=${leagueIdParam ?? ''}`,
  }))
  useShareTimeline(() => ({
    title: `${displayName} 数据`,
    query: `id=${id}&league_id=${leagueIdParam ?? ''}`,
  }))

  return (
    <View className='detail-page'>
      {loading && <View className='detail-loading'><Text>加载中...</Text></View>}
      {!loading && !data && (
        <View className='detail-empty'><Text>未找到该球员信息</Text></View>
      )}
      {!loading && data && (
        <ScrollView scrollY className='detail-scroll'>
          <View className='detail-header'>
            <SafeImage src={data.logo} fallbackSrc={currentStat?.team_logo} fallbackText={displayName} className='detail-avatar' />
            <View className='detail-title'>
              <Text className='detail-name'>{displayName}</Text>
              {data.full_name && <Text className='detail-sub'>{data.full_name}</Text>}
              {data.position_main && (
                <Text className='detail-sub'>
                  位置：{data.position_main_cn || data.position_main}
                  {data.position_secondary ? ` / ${data.position_secondary_cn || data.position_secondary}` : ''}
                </Text>
              )}
            </View>
          </View>

          <View className='detail-section'>
            <View className='info-grid'>
              {data.height && (
                <View className='info-cell'><Text className='info-label'>身高</Text><Text className='info-value'>{data.height}</Text></View>
              )}
              {data.citizenship && (
                <View className='info-cell'><Text className='info-label'>国籍</Text><Text className='info-value'>{data.citizenship}</Text></View>
              )}
              {data.birth_date && (
                <View className='info-cell'><Text className='info-label'>出生</Text><Text className='info-value'>{data.birth_date}</Text></View>
              )}
              {data.club && (
                <View className='info-cell'><Text className='info-label'>俱乐部</Text><Text className='info-value'>{data.club_cn_name || currentStat?.team_cn_name || data.club}</Text></View>
              )}
            </View>
            {!data.height && !data.citizenship && !data.birth_date && !data.club && (
              <Text className='detail-hint'>暂无更多资料</Text>
            )}
          </View>

          {data.stats.length > 1 && (
            <View className='detail-section'>
              <ScrollView scrollX className='league-switch' showScrollbar={false}>
                {data.stats.map((s) => (
                  <View
                    key={s.league_id}
                    className={`league-chip ${selectedLeagueId === s.league_id ? 'active' : ''}`}
                    onClick={() => setSelectedLeagueId(s.league_id)}
                  >
                    <Text>{s.league_name || `赛事${s.league_id}`}</Text>
                  </View>
                ))}
              </ScrollView>
            </View>
          )}

          <View className='detail-section'>
            <Text className='detail-section-title'>
              本赛季数据
              {currentStat?.league_name ? ` · ${currentStat.league_name}` : ''}
              {currentStat?.team_cn_name ? ` · ${currentStat.team_cn_name}` : ''}
            </Text>
            {!currentStat && <Text className='detail-hint'>暂无数据</Text>}
            {currentStat && (
              <View className='stat-grid'>
                <View className='stat-box'><Text className='stat-num'>{currentStat.games_played}</Text><Text className='stat-label'>出场</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.minutes_played}</Text><Text className='stat-label'>分钟</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.goals}</Text><Text className='stat-label'>进球</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.assists}</Text><Text className='stat-label'>助攻</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.yellow_cards}</Text><Text className='stat-label'>黄牌</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.red_cards}</Text><Text className='stat-label'>红牌</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.shots_total}</Text><Text className='stat-label'>射门</Text></View>
                <View className='stat-box'><Text className='stat-num'>{currentStat.shots_on_target}</Text><Text className='stat-label'>射正</Text></View>
              </View>
            )}
          </View>
        </ScrollView>
      )}
    </View>
  )
}
