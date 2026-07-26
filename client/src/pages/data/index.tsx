import { useEffect, useMemo, useRef, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import {
  getLeagues,
  getMatches,
  getPlayerRankings,
  getStandings,
  League,
  Match,
  PlayerRankingType,
  PlayerRankingsOut,
  StandingsOut,
  TeamStandingOut,
  proxiedSofifa,
} from '@/services/api'
import { getRoundLabel, useRoundStore } from '@/stores'
import { formatDateTime } from '@/utils/time'
import './index.scss'

type SubTab = 'standings' | 'players' | 'teams' | 'schedule'

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: 'standings', label: '积分' },
  { key: 'players', label: '球员榜' },
  { key: 'teams', label: '球队榜' },
  { key: 'schedule', label: '赛程' },
]

const TEAM_METRICS: { key: string; label: string }[] = [
  { key: 'points', label: '积分' },
  { key: 'goals_for', label: '进球' },
  { key: 'goals_against', label: '失球' },
  { key: 'goal_diff', label: '净胜球' },
  { key: 'won', label: '胜场' },
  { key: 'win_rate', label: '胜率' },
]

const PLAYER_TYPES: { key: PlayerRankingType; label: string; valueLabel: string }[] = [
  { key: 'goals', label: '射手榜', valueLabel: '进球' },
  { key: 'assists', label: '助攻榜', valueLabel: '助攻' },
  { key: 'yellow_cards', label: '黄牌', valueLabel: '黄牌' },
  { key: 'red_cards', label: '红牌', valueLabel: '红牌' },
]

const DEFAULT_WORLD_CUP_ID = 1

/** 图片（球队旗/球员头像）带失败兜底，优先用 team_logo 做二次降级 */
function SafeImage({ src, fallbackSrc, fallbackText, className }: {
  src: string | null | undefined
  fallbackSrc?: string | null | undefined
  fallbackText: string
  className: string
}) {
  const [err1, setErr1] = useState(false)
  const [err2, setErr2] = useState(false)
  if ((!src && !fallbackSrc) || err2) {
    return (
      <View className={`safe-img-fallback ${className}`}>
        <Text className='safe-img-letter'>{fallbackText.slice(0, 1).toUpperCase()}</Text>
      </View>
    )
  }
  if (!src || err1) {
    return <Image className={className} src={proxiedSofifa(fallbackSrc)} mode='aspectFit' onError={() => setErr2(true)} />
  }
  return <Image className={className} src={proxiedSofifa(src)} mode='aspectFit' onError={() => setErr1(true)} />
}

/** 根据所有联赛数据推导默认赛季：优先有活跃联赛的最近赛季 */
function resolveDefaultSeason(leagues: League[]): number | null {
  if (!leagues.length) return null
  const seasons = Array.from(new Set(leagues.map((l) => l.season).filter((s) => s != null)))
  if (!seasons.length) return null
  seasons.sort((a, b) => b - a)
  const seasonWithActive = seasons.find((s) => leagues.some((l) => l.season === s && l.is_active))
  if (seasonWithActive) return seasonWithActive
  return seasons[0]
}

function resolveDefaultLeagueId(leagues: League[]) {
  if (!leagues.length) return null
  const worldCup = leagues.find(
    (l) => l.id === DEFAULT_WORLD_CUP_ID || l.cn_name.includes('世界杯') || l.name.toLowerCase().includes('world cup')
  )
  return worldCup ? worldCup.id : leagues[0].id
}

function seasonLabel(season: number) {
  if (!season) return ''
  const s = String(season)
  const short = s.slice(2)
  const next = String(season + 1).slice(2)
  return `${short}/${next}`
}

/** 联赛选择条只显示名称，不附带赛季后缀（赛季由下方独立选择器控制） */
function leagueTabName(lg: League) {
  return lg.cn_name || lg.name
}

/**
 * 按名称去重后的联赛列表（用于顶部联赛条，始终展示所有联赛名）
 * 保留每个名称下 first 出现的 league 对象（用于渲染 id 等）
 */
function buildUniqueLeagues(all: League[]): League[] {
  const seen = new Set<string>()
  const result: League[] = []
  // 按原始顺序遍历，保证稳定性
  for (const lg of all) {
    const name = leagueTabName(lg)
    if (!seen.has(name)) {
      seen.add(name)
      result.push(lg)
    }
  }
  return result
}

/** 根据联赛名 + 赛季，找到精确匹配的 league 行 id；赛季不存在时返回 null */
function resolveLeagueIdByNameAndSeason(leagues: League[], name: string, season: number | null): number | null {
  const candidates = leagues.filter(
    (l) => leagueTabName(l) === name && (season == null || l.season === season),
  )
  if (candidates.length > 0) return candidates[0].id
  return null
}

function formatScore(m: Match) {
  if (m.status === 'finished') return `${m.home_score ?? 0} : ${m.away_score ?? 0}`
  if (m.status === 'live') return '进行中'
  return '—'
}

export default function DataPage() {
  // 订阅轮次中英文映射加载（确保 getRoundLabel 可用）
  useRoundStore((s) => s.ready)

  // 请求竞态保护：只有最新一次请求能写入状态
  const latestReq = useRef(0)

  // 赛季切换器状态（赛季列表由 useMemo 根据当前联赛动态推导）
  const [selectedSeason, setSelectedSeason] = useState<number | null>(null)
  const [seasonPickerOpen, setSeasonPickerOpen] = useState(false)
  const [seasonTriggerRect, setSeasonTriggerRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null)

  const openSeasonPicker = () => {
    const query = Taro.createSelectorQuery()
    query.select('.data-season-trigger').boundingClientRect()
    query.exec((res) => {
      const rect = res[0] as unknown as { top: number; left: number; width: number; height: number } | undefined
      if (rect) setSeasonTriggerRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height })
      setSeasonPickerOpen(true)
    })
  }

  // 顶部联赛选择
  const [leagues, setLeagues] = useState<League[]>([])
  const [selectedLeagueId, setSelectedLeagueId] = useState<number | null>(null)
  const [selectedLeagueName, setSelectedLeagueName] = useState<string>('')
  const [leagueExpanded, setLeagueExpanded] = useState(false)
  const [leagueOverflow, setLeagueOverflow] = useState(false)
  const scrollIntoViewId = useMemo(() => (selectedLeagueId ? `league-${selectedLeagueId}` : ''), [selectedLeagueId])

  // Tab 与数据
  const [activeTab, setActiveTab] = useState<SubTab>('standings')
  const [teamMetric, setTeamMetric] = useState<string>('points')
  const [playerType, setPlayerType] = useState<PlayerRankingType>('goals')

  const [standings, setStandings] = useState<StandingsOut | null>(null)
  const [playerData, setPlayerData] = useState<PlayerRankingsOut | null>(null)
  const [matches, setMatches] = useState<Match[]>([])
  const [loading, setLoading] = useState(false)

  const selectedLeague = useMemo(
    () => leagues.find((l) => l.id === selectedLeagueId) ?? null,
    [leagues, selectedLeagueId],
  )

  // 联赛条：展示全部联赛（按名称去重），不受赛季筛选影响
  const visibleLeagues = useMemo(() => buildUniqueLeagues(leagues), [leagues])

  // 根据当前选中联赛，动态推导可用赛季列表（只显示该联赛实际存在的赛季）
  const seasons = useMemo(() => {
    if (!selectedLeague) return []
    const lgSeasons = leagues
      .filter((l) => l.cn_name === selectedLeague.cn_name || l.name === selectedLeague.name)
      .map((l) => l.season)
      .filter((s): s is number => s != null)
    return Array.from(new Set(lgSeasons)).sort((a, b) => b - a)
  }, [leagues, selectedLeague])

  // 加载所有联赛，推导可用赛季与默认值
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const list = await getLeagues()
        if (!cancelled) {
          setLeagues(list)
          const defaultSeason = resolveDefaultSeason(list)
          setSelectedSeason(defaultSeason)
          const seasonLeagues = defaultSeason != null ? list.filter((l) => l.season === defaultSeason) : list
          const active = seasonLeagues.filter((l) => l.is_active)
          const defaultId = resolveDefaultLeagueId(active.length ? active : seasonLeagues)
          setSelectedLeagueId(defaultId)
          if (defaultId != null) {
            const defaultLg = list.find((l) => l.id === defaultId)
            setSelectedLeagueName(defaultLg ? leagueTabName(defaultLg) : '')
          }
        }
      } catch {
        if (!cancelled) {
          setLeagues([])
          setSelectedSeason(null)
          setSelectedLeagueId(null)
        }
      }
    })()
    return () => { cancelled = true }
  }, [])

  // 联赛切换时，自动选中该联赛下最合适的赛季，并同步更新 leagueId
  useEffect(() => {
    if (!selectedLeague || seasons.length === 0) return
    // 优先保留当前已选的赛季（如果新联赛也有该赛季）
    if (selectedSeason && seasons.includes(selectedSeason)) return
    // 否则选该联赛最新的赛季（或活跃赛季）
    const withActive = seasons.find((s) =>
      leagues.some((l) => (l.cn_name === selectedLeague.cn_name || l.name === selectedLeague.name) && l.season === s && l.is_active),
    )
    const targetSeason = withActive ?? seasons[0]
    setSelectedSeason(targetSeason)
    // 关键：同时把 leagueId 切到该名+新赛季对应的精确行
    if (targetSeason != null && selectedLeagueName) {
      const exact = leagues.find(
        (l) => (l.cn_name === selectedLeague.cn_name || l.name === selectedLeague.name) && l.season === targetSeason,
      )
      if (exact?.id) setSelectedLeagueId(exact.id)
    }
  }, [selectedLeague?.id, seasons])

  // 检测顶部联赛条是否溢出
  useEffect(() => {
    if (visibleLeagues.length === 0) return
    const timer = setTimeout(() => {
      const query = Taro.createSelectorQuery()
      query.select('.data-league-scroll').boundingClientRect()
      query.select('.data-league-tabs').boundingClientRect()
      query.exec((res) => {
        const wrap = (res && res[0]) as unknown as { width: number } | undefined
        const tabs = (res && res[1]) as unknown as { width: number } | undefined
        if (wrap && tabs) setLeagueOverflow(tabs.width > wrap.width + 2)
      })
    }, 150)
    return () => clearTimeout(timer)
  }, [visibleLeagues])

  // 切换联赛时立即清空旧数据，避免看到上一个联赛/赛季的数据
  useEffect(() => {
    setStandings(null)
    setPlayerData(null)
    setMatches([])
    setLoading(false)
  }, [selectedLeagueId])

  // 切换联赛或 Tab 时加载对应数据
  useEffect(() => {
    if (selectedLeagueId == null) return
    latestReq.current += 1
    const reqId = latestReq.current
    setLoading(true)

    const load = async () => {
      try {
        if (activeTab === 'standings') {
          const st = await getStandings(selectedLeagueId)
          if (reqId !== latestReq.current) return
          setStandings(st)
        } else if (activeTab === 'players') {
          const pr = await getPlayerRankings(selectedLeagueId, playerType)
          if (reqId !== latestReq.current) return
          setPlayerData(pr)
        } else if (activeTab === 'teams') {
          const st = await getStandings(selectedLeagueId)
          if (reqId !== latestReq.current) return
          setStandings(st)
        } else if (activeTab === 'schedule') {
          const ms = await getMatches({ league_id: selectedLeagueId, sort_order: 'asc', limit: 200 })
          if (reqId !== latestReq.current) return
          setMatches(ms)
        }
      } catch {
        if (reqId !== latestReq.current) return
        if (activeTab === 'standings' || activeTab === 'teams') setStandings(null)
        if (activeTab === 'players') setPlayerData(null)
        if (activeTab === 'schedule') setMatches([])
      } finally {
        if (reqId === latestReq.current) setLoading(false)
      }
    }

    load()
  }, [selectedLeagueId, activeTab, playerType])

  const sortedTeams = useMemo(() => {
    if (!standings) return []
    const raw = standings.groups.flatMap((g) => g.standings)
    // 去重：同球队可能出现在多个分组中（如世界杯多小组、或同一联赛多条同步数据）
    // team_id 可能为 0（无有效 id），回退用归一化队名作为去重键
    const seen = new Map<string, TeamStandingOut>()
    for (const t of raw) {
      const key = t.team_id && t.team_id > 0 ? `id:${t.team_id}` : `name:${(t.team_cn_name || t.team_name).trim().toLowerCase()}`
      if (!seen.has(key)) {
        seen.set(key, t)
      }
    }
    const all = Array.from(seen.values())
    if (teamMetric === 'win_rate') {
      return [...all].sort((a, b) => b.won / Math.max(b.played, 1) - a.won / Math.max(a.played, 1))
    }
    return [...all].sort(
      (a, b) => (b[teamMetric as keyof TeamStandingOut] as number) - (a[teamMetric as keyof TeamStandingOut] as number),
    )
  }, [standings, teamMetric])

  const metricLabel = TEAM_METRICS.find((m) => m.key === teamMetric)?.label ?? ''
  const playerTypeValueLabel = PLAYER_TYPES.find((p) => p.key === playerType)?.valueLabel ?? ''

  useShareAppMessage(() => ({
    title: '数据中心 · 赛事数据一览',
    path: '/pages/data/index',
  }))
  useShareTimeline(() => ({
    title: '数据中心 · 赛事数据一览',
    query: '',
  }))

  // 选择赛季后，保持当前联赛名不变，自动切换到该名+新赛季的联赛行
  const handleSelectSeason = (season: number) => {
    setSelectedSeason(season)
    if (selectedLeagueName) {
      const newId = resolveLeagueIdByNameAndSeason(leagues, selectedLeagueName, season)
      setSelectedLeagueId(newId)
    } else {
      // 还没选过联赛时，走默认逻辑
      const seasonLeagues = leagues.filter((l) => l.season === season)
      const active = seasonLeagues.filter((l) => l.is_active)
      const defaultId = resolveDefaultLeagueId(active.length ? active : seasonLeagues)
      setSelectedLeagueId(defaultId)
      if (defaultId != null) {
        const defaultLg = leagues.find((l) => l.id === defaultId)
        setSelectedLeagueName(defaultLg ? leagueTabName(defaultLg) : '')
      }
    }
    setLeagueExpanded(false)
  }

  // 点击联赛条：优先保持当前赛季；当前赛季不存在时取活跃/最新赛季并同步赛季显示
  const handleSelectLeague = (lg: League) => {
    const name = leagueTabName(lg)
    setSelectedLeagueName(name)
    const candidates = leagues.filter((l) => leagueTabName(l) === name)
    const target = candidates.find((l) => l.season === selectedSeason)
      ?? candidates.find((l) => l.is_active)
      ?? candidates[candidates.length - 1]
    setSelectedLeagueId(target?.id ?? null)
    if (target && selectedSeason != null && !candidates.some((l) => l.season === selectedSeason)) {
      setSelectedSeason(target.season)
    }
  }

  return (
    <View className='data-page'>
      {/* ── 第一行：联赛选择条（不含赛季）─────────────────── */}
      <View className='data-league-bar'>
        <ScrollView scrollX className='data-league-scroll' scrollIntoView={scrollIntoViewId} scrollWithAnimation>
          <View className={`data-league-tabs ${leagueOverflow ? 'has-overflow' : ''}`}>
            {/* 展示所有联赛（按名称去重），点击时结合当前赛季定位到具体联赛行 */}
            {visibleLeagues.map((lg) => {
              const name = leagueTabName(lg)
              const isActive = name === selectedLeagueName
              return (
                <View
                  key={lg.id}
                  id={`league-${lg.id}`}
                  className={`data-league-tab ${isActive ? 'active' : ''}`}
                  onClick={() => handleSelectLeague(lg)}
                >
                  <Text className='data-league-tab-text'>{name}</Text>
                </View>
              )
            })}
          </View>
        </ScrollView>
        {leagueOverflow && (
          <View className='data-league-toggle' onClick={() => setLeagueExpanded((v) => !v)}>
            <View className={`data-league-arrow ${leagueExpanded ? 'up' : 'down'}`} />
          </View>
        )}
        {leagueExpanded && (
          <View className='data-league-dropdown'>
            <View className='data-league-dropdown-grid'>
              {visibleLeagues.map((lg) => {
                const name = leagueTabName(lg)
                return (
                  <View
                    key={lg.id}
                    className={`data-league-dropdown-item ${name === selectedLeagueName ? 'active' : ''}`}
                    onClick={() => {
                      handleSelectLeague(lg)
                      setLeagueExpanded(false)
                    }}
                  >
                    <Text className='data-league-dropdown-text'>{leagueTabName(lg)}</Text>
                  </View>
                )
              })}
            </View>
          </View>
        )}
      </View>

      {/* ── 第二行：赛季选择器（picker） + 子 Tab 同级栏 ────── */}
      <View className='data-toolbar'>
        <View className='data-toolbar-inner'>
          {/* 赛季下拉选择器 — 与子 Tab 平级，参考首页「我的关注」下拉设计 */}
          {seasons.length > 1 && (
            <View className='data-season-picker-wrap'>
              <View className='data-season-trigger' onClick={openSeasonPicker}>
                <Text className='data-season-trigger-text'>{selectedSeason ? seasonLabel(selectedSeason) : '赛季'}</Text>
                <Text className='data-season-trigger-arrow'>▾</Text>
              </View>

              {seasonPickerOpen && (
                <View className='data-season-mask' onClick={() => setSeasonPickerOpen(false)}>
                  <View
                    className='data-season-modal'
                    style={seasonTriggerRect
                      ? { top: seasonTriggerRect.top + seasonTriggerRect.height + 8, left: seasonTriggerRect.left, minWidth: Math.max(seasonTriggerRect.width, 120) }
                      : {}}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <View className='data-season-list'>
                      {seasons.map((s) => {
                        const active = s === selectedSeason
                        return (
                          <View
                            key={s}
                            className={`data-season-row ${active ? 'active' : ''}`}
                            onClick={() => {
                              handleSelectSeason(s)
                              setSeasonPickerOpen(false)
                            }}
                          >
                            <Text className='data-season-row-text'>{seasonLabel(s)}</Text>
                            {active && <Text className='data-season-row-check'>✓</Text>}
                          </View>
                        )
                      })}
                    </View>
                  </View>
                </View>
              )}
            </View>
          )}

          {/* 子 Tab：积分 / 球员榜 / 球队榜 / 赛程 */}
          <View className='data-sub-tabs'>
            {SUB_TABS.map((t) => (
              <View
                key={t.key}
                className={`data-sub-tab ${activeTab === t.key ? 'active' : ''}`}
                onClick={() => {
                  if (activeTab === t.key) return
                  setActiveTab(t.key)
                  setStandings(null)
                  setPlayerData(null)
                  setMatches([])
                }}
              >
                <Text>{t.label}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* ══════════════ 内容区 ══════════════ */}

      {/* 积分榜 */}
      {activeTab === 'standings' && (
        <ScrollView scrollY className='data-content'>
          {loading && <View className='data-loading'><Text>加载中...</Text></View>}
          {!loading && (standings == null || standings.groups.length === 0) && (
            <View className='data-empty'>
              <Text className='data-empty-icon'>⏳</Text>
              <Text className='data-empty-title'>{selectedSeason ? `${seasonLabel(selectedSeason)} 赛季尚未开始` : '当前赛季尚未开始'}</Text>
              <Text className='data-empty-desc'>积分榜将在赛季开启、首批比赛结束后自动生成；可切换赛季查看历史数据</Text>
            </View>
          )}
          {!loading && standings && standings.groups.length > 0 && (standings.groups.length > 1 ? standings.groups.slice(0, -1) : standings.groups).map((g) => (
            <View className='standings-group' key={g.group_name}>
              {standings.groups.length > 1 && (
                <View className='standings-group-title'>
                  <Text>{g.group_name}</Text>
                </View>
              )}
              <View className='standings-table'>
                <View className='standings-row standings-head'>
                  <Text className='c-rank'>#</Text>
                  <Text className='c-team'>球队</Text>
                  <Text className='c-num'>赛</Text>
                  <Text className='c-num'>胜</Text>
                  <Text className='c-num'>平</Text>
                  <Text className='c-num'>负</Text>
                  <Text className='c-num c-gf-ga'>进/失</Text>
                  <Text className='c-pts'>积分</Text>
                </View>
                {g.standings.map((t) => (
                  <View
                    className='standings-row'
                    key={t.team_id ? `team-${t.team_id}` : `name-${t.team_name}`}
                  >
                    <Text className={`c-rank ${t.rank <= 4 ? 'top' : ''}`}>{t.rank}</Text>
                    <View className='c-team'>
                      <SafeImage src={t.flag_url} fallbackText={t.team_cn_name || t.team_name} className='c-flag' />
                      <Text className='c-team-name'>{t.team_cn_name || t.team_name}</Text>
                    </View>
                    <Text className='c-num'>{t.played}</Text>
                    <Text className='c-num'>{t.won}</Text>
                    <Text className='c-num'>{t.draw}</Text>
                    <Text className='c-num'>{t.lost}</Text>
                    <Text className='c-num c-gf-ga'>{t.goals_for}/{t.goals_against}</Text>
                    <Text className='c-pts'>{t.points}</Text>
                  </View>
                ))}
              </View>
            </View>
          ))}
        </ScrollView>
      )}

      {/* 球队榜 */}
      {activeTab === 'teams' && (
        <View className='rank-layout'>
          <View className='rank-sidebar'>
            {TEAM_METRICS.map((m) => (
              <View
                key={m.key}
                className={`rank-sidebar-item ${teamMetric === m.key ? 'active' : ''}`}
                onClick={() => setTeamMetric(m.key)}
              >
                <Text>{m.label}</Text>
              </View>
            ))}
          </View>
          <View className='rank-main'>
            <View className='rank-thead'>
              <View className='rank-th rank-th-no' />
              <View className='rank-th rank-th-avatar' />
              <Text className='rank-th rank-th-name'>球队</Text>
              <Text className='rank-th rank-th-value'>{metricLabel}</Text>
            </View>
            <ScrollView scrollY className='rank-list'>
              {loading && <View className='rank-loading'><Text>加载中...</Text></View>}
              {!loading && sortedTeams.length === 0 && (
                <View className='data-empty'>
                  <Text className='data-empty-icon'>📈</Text>
                  <Text className='data-empty-title'>{selectedSeason ? `${seasonLabel(selectedSeason)} 赛季尚未开始` : '当前赛季尚未开始'}</Text>
                  <Text className='data-empty-desc'>球队数据将在赛季开启、首批比赛结束后自动生成，请稍后再来查看</Text>
                </View>
              )}
              {!loading && sortedTeams.map((t, idx) => {
                const val =
                  teamMetric === 'win_rate'
                    ? `${Math.round((t.won / Math.max(t.played, 1)) * 100)}%`
                    : (t[teamMetric as keyof TeamStandingOut] as number)
                return (
                  <View
                    className='rank-row'
                    key={t.team_id ? `team-${t.team_id}` : `name-${t.team_name}`}
                  >
                    <Text className={`rank-no ${idx < 3 ? 'top' : ''}`}>{idx + 1}</Text>
                    <SafeImage src={t.flag_url} fallbackText={t.team_cn_name || t.team_name} className='rank-logo' />
                    <Text className='rank-name'>{t.team_cn_name || t.team_name}</Text>
                    <Text className='rank-value'>{val}</Text>
                  </View>
                )
              })}
            </ScrollView>
          </View>
        </View>
      )}

      {/* 球员榜 */}
      {activeTab === 'players' && (
        <View className='rank-layout'>
          <View className='rank-sidebar'>
            {PLAYER_TYPES.map((p) => (
              <View
                key={p.key}
                className={`rank-sidebar-item ${playerType === p.key ? 'active' : ''}`}
                onClick={() => setPlayerType(p.key)}
              >
                <Text>{p.label}</Text>
              </View>
            ))}
          </View>
          <View className='rank-main'>
            <View className='rank-thead'>
              <View className='rank-th rank-th-no' />
              <View className='rank-th rank-th-avatar' />
              <Text className='rank-th rank-th-name'>球员</Text>
              <Text className='rank-th rank-th-team'>球队</Text>
              <Text className='rank-th rank-th-value'>{playerTypeValueLabel}</Text>
            </View>
            <ScrollView scrollY className='rank-list'>
              {loading && <View className='rank-loading'><Text>加载中...</Text></View>}
              {!loading && (playerData?.items.length ?? 0) === 0 && (
                <View className='data-empty'>
                  <Text className='data-empty-icon'>⚽</Text>
                  <Text className='data-empty-title'>{selectedSeason ? `${seasonLabel(selectedSeason)} 赛季尚未开始` : '当前赛季尚未开始'}</Text>
                  <Text className='data-empty-desc'>球员数据将在赛季开启、首批比赛结束后自动生成，请稍后再来查看</Text>
                </View>
              )}
              {!loading && playerData?.items.map((p) => (
                <View
                  className='rank-row'
                  key={p.player_id}
                  hoverClassName='row-hover'
                  onClick={() =>
                    Taro.navigateTo({
                      url: `/pages/player-detail/index?id=${p.player_id}&league_id=${selectedLeagueId}`,
                    })
                  }
                >
                  <Text className={`rank-no ${p.rank <= 3 ? 'top' : ''}`}>{p.rank}</Text>
                  <SafeImage
                    src={p.player_logo}
                    fallbackSrc={p.team_logo}
                    fallbackText={p.player_name}
                    className='rank-avatar'
                  />
                  <Text className='rank-name'>{p.player_cn_name || p.player_name}</Text>
                  <Text className='rank-team'>{p.team_cn_name || p.team_name || '—'}</Text>
                  <Text className='rank-value'>{(p as any)[playerType]}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        </View>
      )}

      {/* 赛程 */}
      {activeTab === 'schedule' && (
        <ScrollView scrollY className='data-content'>
          {loading && <View className='data-loading'><Text>加载中...</Text></View>}
          {!loading && matches.length === 0 && (
            <View className='data-empty'>
              <Text className='data-empty-icon'>📅</Text>
              <Text className='data-empty-title'>暂无赛程</Text>
            </View>
          )}
          {!loading && matches.map((m) => (
            <View
              className='schedule-card'
              key={m.id}
              onClick={() => Taro.navigateTo({ url: `/pages/match-detail/index?id=${m.id}` })}
            >
              <View className='schedule-meta'>
                <Text className='schedule-round'>{getRoundLabel(m.round) || '赛程'}</Text>
                <Text className='schedule-time'>{formatDateTime(m.match_time)}</Text>
              </View>
              <View className='schedule-teams'>
                <View className='schedule-team'>
                  <SafeImage
                    src={m.home_team.flag_url}
                    fallbackText={m.home_team.cn_name || m.home_team.name}
                    className='schedule-logo'
                  />
                  <Text className='schedule-team-name'>{m.home_team.cn_name || m.home_team.name}</Text>
                </View>
                <View className='schedule-score'>
                  <Text className={`schedule-score-text ${m.status === 'live' ? 'live' : ''}`}>{formatScore(m)}</Text>
                  <Text className='schedule-status'>
                    {m.status === 'upcoming' ? '未开始' : m.status === 'live' ? '进行中' : '已结束'}
                  </Text>
                </View>
                <View className='schedule-team away'>
                  <SafeImage
                    src={m.away_team.flag_url}
                    fallbackText={m.away_team.cn_name || m.away_team.name}
                    className='schedule-logo'
                  />
                  <Text className='schedule-team-name'>{m.away_team.cn_name || m.away_team.name}</Text>
                </View>
              </View>
            </View>
          ))}
        </ScrollView>
      )}
    </View>
  )
}
