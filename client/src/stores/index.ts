import { create } from 'zustand'
import Taro from '@tarojs/taro'
import type { Match, Prediction, AILeaderboardItem, HumanUserRankItem, ComparePredictionsOut, HomeStats, StandingsOut, HomeTabItem, League, CnMapping } from '@/services/api'
import * as api from '@/services/api'

// ==================== 联赛状态 ====================

const SELECTED_LEAGUE_IDS_KEY = 'selected_league_ids'

function readSelectedLeagueIdsFromCache(): number[] {
  try {
    const cached = Taro.getStorageSync(SELECTED_LEAGUE_IDS_KEY)
    if (Array.isArray(cached)) return cached as number[]
  } catch {}
  return []
}

interface LeagueState {
  leagues: League[]
  // 首页数据筛选依据：可同时选中多个联赛（混合展示）
  selectedLeagueIds: number[]
  loading: boolean
  fetchLeagues: () => Promise<void>
  setSelectedLeagues: (ids: number[]) => void
}

export const useLeagueStore = create<LeagueState>((set, get) => ({
  leagues: [],
  // 启动时读取本地缓存的多选联赛集合
  selectedLeagueIds: readSelectedLeagueIdsFromCache(),
  loading: false,

  fetchLeagues: async () => {
    set({ loading: true })
    try {
      const leagues = await api.getLeagues()
      // 只保留启用的联赛用于切换
      const active = leagues.filter(l => l.is_active)
      const list = active.length > 0 ? active : leagues
      set({ leagues: list, loading: false })
      // 用本地缓存/当前选中的联赛 ID 与后端列表做校验，失效则回退到第一个
      const { selectedLeagueIds } = get()
      const cachedIds = selectedLeagueIds.length > 0 ? selectedLeagueIds : readSelectedLeagueIdsFromCache()
      const validIds = cachedIds.filter(id => list.some(l => l.id === id))
      if (validIds.length > 0) {
        set({ selectedLeagueIds: validIds })
      } else if (list.length > 0) {
        // 首次进入（无缓存）默认全选所有联赛
        set({ selectedLeagueIds: list.map(l => l.id) })
      }
    } catch {
      set({ loading: false })
    }
  },

  // 多选：设置选中的联赛集合
  setSelectedLeagues: (ids) => {
    const next = ids.length > 0 ? ids : []
    set({ selectedLeagueIds: next })
    try { Taro.setStorageSync(SELECTED_LEAGUE_IDS_KEY, next) } catch {}
  },
}))

/** 当前主联赛 id = selectedLeagueIds 第一个，供单联赛视角的页面使用 */
export function usePrimaryLeagueId(): number | null {
  return useLeagueStore((s) => (s.selectedLeagueIds.length > 0 ? s.selectedLeagueIds[0] : null))
}

// ==================== 比赛状态 ====================

interface MatchState {
  matches: Match[]
  currentMatch: Match | null
  predictions: ComparePredictionsOut['predictions']
  homeStats: HomeStats | null
  standings: StandingsOut | null
  homeTabs: HomeTabItem[]
  loading: boolean
  fetchMatches: (params?: { league_id?: number; league_ids?: number[]; status?: string; round?: string[] | string; date?: string; sort_order?: 'asc' | 'desc'; limit?: number }) => Promise<void>
  fetchMatchDetail: (id: number) => Promise<void>
  fetchPredictions: (matchId: number) => Promise<void>
  fetchHomeStats: (leagueIds?: number[]) => Promise<void>
  fetchStandings: (leagueId: number) => Promise<void>
  fetchHomeTabs: (leagueIds?: number[]) => Promise<void>
}

export const useMatchStore = create<MatchState>((set) => ({
  matches: [],
  currentMatch: null,
  predictions: [],
  homeStats: null,
  standings: null,
  homeTabs: [],
  loading: false,

  fetchMatches: async (params) => {
    set({ loading: true })
    try {
      const matches = await api.getMatches(params)
      set({ matches, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchMatchDetail: async (id) => {
    set({ loading: true })
    try {
      const match = await api.getMatchDetail(id)
      set({ currentMatch: match, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchPredictions: async (matchId) => {
    try {
      const data = await api.comparePredictions(matchId)
      set({ predictions: data.predictions })
    } catch {
      // ignore
    }
  },

  fetchHomeStats: async (leagueIds) => {
    try {
      const homeStats = await api.getHomeStats(leagueIds)
      set({ homeStats })
    } catch {
      // ignore, keep default
    }
  },

  fetchStandings: async (leagueId) => {
    try {
      const standings = await api.getStandings(leagueId)
      set({ standings })
    } catch {
      // ignore, keep default
    }
  },

  fetchHomeTabs: async (leagueIds) => {
    try {
      const data = await api.getHomeTabs(leagueIds)
      set({ homeTabs: data.tabs })
    } catch {
      // ignore, keep default empty
    }
  },
}))

// ==================== 排行榜状态 ====================

interface LeaderboardState {
  activeTab: 'ai' | 'human'
  sortMode: 'composite' | 'field'
  sortBy: 'composite' | 'result_accuracy' | 'score_accuracy'
  sortOrder: 'asc' | 'desc'
  entries: AILeaderboardItem[]
  topUsers: HumanUserRankItem[]
  loading: boolean
  setActiveTab: (tab: 'ai' | 'human') => void
  setSortMode: (mode: 'composite' | 'field') => void
  setSort: (sortBy: 'result_accuracy' | 'score_accuracy', sortOrder: 'asc' | 'desc') => void
  fetchLeaderboard: () => Promise<void>
}

/** 对 entries 做客户端排序 */
function applySort(entries: AILeaderboardItem[], sortBy: 'composite' | 'result_accuracy' | 'score_accuracy', sortOrder: 'asc' | 'desc'): AILeaderboardItem[] {
  const dir = sortOrder === 'asc' ? 1 : -1
  return [...entries].sort((a, b) => {
    // 综合排序：票数 → 比分命中率 → 胜负正确率
    if (sortBy === 'composite') {
      const diff1 = (b.total ?? 0) - (a.total ?? 0)
      if (diff1 !== 0) return diff1
      const diff2 = (b.score_accuracy ?? 0) - (a.score_accuracy ?? 0)
      if (diff2 !== 0) return diff2
      return (b.result_accuracy ?? 0) - (a.result_accuracy ?? 0)
    }
    // 其他排序：主排序 → 副排序 → 票数
    const diff = (a[sortBy] ?? 0) - (b[sortBy] ?? 0)
    if (diff !== 0) return diff * dir
    // 相同时按另一字段降序，再按票数降序
    const subKey = sortBy === 'result_accuracy' ? 'score_accuracy' : 'result_accuracy'
    const diff2 = (a[subKey] ?? 0) - (b[subKey] ?? 0)
    if (diff2 !== 0) return -diff2  // 副排始终降序
    return (b.total ?? 0) - (a.total ?? 0)
  })
}

/** 对用户排行做同样的排序逻辑 */
function applyUserSort(entries: HumanUserRankItem[], sortBy: 'result_accuracy' | 'score_accuracy', sortOrder: 'asc' | 'desc'): HumanUserRankItem[] {
  const dir = sortOrder === 'asc' ? 1 : -1
  return [...entries].sort((a, b) => {
    const diff = (a[sortBy] ?? 0) - (b[sortBy] ?? 0)
    if (diff !== 0) return diff * dir
    const subKey = sortBy === 'result_accuracy' ? 'score_accuracy' : 'result_accuracy'
    const diff2 = (a[subKey] ?? 0) - (b[subKey] ?? 0)
    if (diff2 !== 0) return -diff2
    return (b.total ?? 0) - (a.total ?? 0)
  })
}

export const useLeaderboardStore = create<LeaderboardState>((set, get) => ({
  activeTab: 'ai',
  sortMode: 'composite',   // 默认综合排序
  sortBy: 'composite',  // 默认综合排序：票数 → 比分命中率 → 胜负正确率
  sortOrder: 'desc',
  entries: [],
  topUsers: [],
  loading: false,

  setActiveTab: (tab) => {
    set({ activeTab: tab })
    get().fetchLeaderboard()
  },


  setSortMode: (mode) => {
    if (mode === 'composite') {
      set({ sortMode: 'composite', sortBy: 'composite', sortOrder: 'desc' })
      const { entries, topUsers } = get()
      const newEntries = applySort(entries, 'composite', 'desc')
      // 综合模式：人类排行也按 预测总数 → 比分命中率 → 胜负命中率 排序
      let newTopUsers = [...topUsers].sort((a, b) => {
        const d1 = (b.total ?? 0) - (a.total ?? 0)
        if (d1 !== 0) return d1
        const d2 = (b.score_accuracy ?? 0) - (a.score_accuracy ?? 0)
        if (d2 !== 0) return d2
        return (b.result_accuracy ?? 0) - (a.result_accuracy ?? 0)
      })
      // 当前置顶
      const meIdx = newTopUsers.findIndex(u => u.is_me)
      if (meIdx > 0) {
        const [me] = newTopUsers.splice(meIdx, 1)
        newTopUsers.unshift(me)
      }
      set({ entries: newEntries, topUsers: newTopUsers })
    } else {
      set({ sortMode: 'field' })
      const { entries, topUsers, sortBy, sortOrder } = get()
      const newEntries = applySort(entries, sortBy, sortOrder)
      let newTopUsers = applyUserSort(topUsers, sortBy, sortOrder)
      // 当前置顶
      const meIdx = newTopUsers.findIndex(u => u.is_me)
      if (meIdx > 0) {
        const [me] = newTopUsers.splice(meIdx, 1)
        newTopUsers.unshift(me)
      }
      set({ entries: newEntries, topUsers: newTopUsers })
    }
  },

  setSort: (sortBy, sortOrder) => {
    const { entries, topUsers } = get()
    const newEntries = applySort(entries, sortBy, sortOrder)
    let newTopUsers = applyUserSort(topUsers, sortBy, sortOrder)
    // 当前置顶
    const meIdx = newTopUsers.findIndex(u => u.is_me)
    if (meIdx > 0) {
      const [me] = newTopUsers.splice(meIdx, 1)
      newTopUsers.unshift(me)
    }
    set({
      sortMode: 'field', sortBy, sortOrder,
      entries: newEntries,
      topUsers: newTopUsers,
    })
  },

  fetchLeaderboard: async () => {
    const { activeTab, sortBy, sortOrder } = get()
    // 按当前选中的多个联赛筛选（空数组=全部联赛）
    const leagueIds = useLeagueStore.getState().selectedLeagueIds
    set({ loading: true })
    try {
      if (activeTab === 'ai') {
        const rawEntries = await api.getAILeaderboard(leagueIds)
        set({
          entries: applySort(rawEntries as AILeaderboardItem[], sortBy, sortOrder),
          topUsers: [],
          loading: false,
        })
      } else {
        const userId = useUserStore.getState().user?.id
        const humanData = await api.getHumanLeaderboard(userId, leagueIds)
        set({
          entries: [],
          topUsers: humanData.top_users as HumanUserRankItem[],
          loading: false,
        })
      }
    } catch {
      set({ loading: false })
    }
  }
}))

// ==================== 用户状态 ====================

interface UserState {
  user: api.UserProfile | null
  token: string | null
  myVote: api.VoteOut | null
  profileSetup: boolean
  loginReady: boolean
  isVip: boolean
  vipExpireAt: string | null
  vipPlanType: string | null
  vipDaysRemaining: number
  setLoginReady: () => void
  login: (code: string) => Promise<void>
  fetchProfile: (userId: number) => Promise<void>
  updateProfile: (nickname: string, avatarUrl: string) => Promise<void>
  fetchVote: (userId: number, matchId: number) => Promise<void>
  vote: (matchId: number, result: string, homeScore: number, awayScore: number) => Promise<void>
  fetchVipStatus: () => Promise<void>
  logout: () => void
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  token: null,
  myVote: null,
  profileSetup: false,
  loginReady: true, // 启动即放行，登录在后台静默完成
  isVip: false,
  vipExpireAt: null,
  vipPlanType: null,
  vipDaysRemaining: 0,

  setLoginReady: () => {
    if (!get().loginReady) {
      set({ loginReady: true })
    }
  },

  login: async (code) => {
    const res = await api.wxLogin(code)
    const profileSetup = res.profile_setup ?? false
    // 不再通过 loginReady 控制页面放行（app.ts 已启动即放行）
    set({ user: res.user, token: res.token, profileSetup, loginReady: true })
    Taro.setStorageSync('token', res.token)
    Taro.setStorageSync('profile_setup', profileSetup)
    // 登录后刷新排行榜（获取我的排名）
    useLeaderboardStore.getState().fetchLeaderboard()
    // 登录后获取 VIP 状态
    get().fetchVipStatus()
    return res
  },

  fetchProfile: async (userId) => {
    const data = await api.getUserProfile(userId)
    set({ user: data.user })
  },

  updateProfile: async (nickname, avatarUrl) => {
    const user = get().user
    if (!user) throw new Error('NOT_LOGGED_IN')
    const updated = await api.updateUserProfile(user.id, nickname, avatarUrl)
    const profileSetup = true
    set({ user: updated, profileSetup, loginReady: true })
    Taro.setStorageSync('profile_setup', profileSetup)
  },

  fetchVote: async (userId, matchId) => {
    try {
      const vote = await api.getUserVote(userId, matchId)
      set({ myVote: vote })
    } catch {
      set({ myVote: null })
    }
  },

  vote: async (matchId, result, homeScore, awayScore) => {
    const user = get().user
    if (!user) throw new Error('NOT_LOGGED_IN')
    const voteOut = await api.votePrediction(user.id, matchId, result, homeScore, awayScore)
    set({ myVote: voteOut })
  },

  fetchVipStatus: async () => {
    const user = get().user
    if (!user) {
      set({ isVip: false, vipExpireAt: null, vipPlanType: null, vipDaysRemaining: 0 })
      return
    }
    try {
      const status = await api.getVipStatus(user.id)
      set({
        isVip: status.is_vip,
        vipExpireAt: status.expire_at,
        vipPlanType: status.plan_type,
        vipDaysRemaining: status.days_remaining,
      })
    } catch {
      set({ isVip: false, vipExpireAt: null, vipPlanType: null, vipDaysRemaining: 0 })
    }
  },

  logout: () => {
    set({
      user: null,
      token: null,
      profileSetup: false,
      loginReady: false,
      isVip: false,
      vipExpireAt: null,
      vipPlanType: null,
    })
    Taro.removeStorageSync('token')
    Taro.removeStorageSync('profile_setup')
  }
}))

// ==================== 通用中英文映射 ====================

interface RoundState {
  translations: CnMapping[]
  ready: boolean
  fetchRoundTranslations: () => Promise<void>
}

/** 模块级缓存：round key -> 映射条目，避免每次渲染重复构建 */
let _roundMap: Record<string, CnMapping> = {}

/** 根据映射条目与原始 round 渲染中文标签 */
function renderRound(t: CnMapping, raw: string, suffix?: string): string {
  if (t.is_series) {
    const n = suffix ?? (raw.includes(' - ') ? raw.split(' - ').pop()! : '')
    return t.cn_value.replace('{n}', n)
  }
  return t.cn_value
}

/** 全局统一的 round 中文翻译函数（替代各页面硬编码的 ROUND_CN_MAP） */
export function getRoundLabel(round: string): string {
  if (!round) return round
  // 1. 精确匹配（如 Final / Semi-finals）
  if (_roundMap[round]) return renderRound(_roundMap[round], round)
  // 2. 带数字后缀的系列轮次：Group Stage - 3 → 取 base key
  const idx = round.lastIndexOf(' - ')
  if (idx > 0) {
    const baseKey = round.slice(0, idx)
    const suffix = round.slice(idx + 3)
    if (_roundMap[baseKey]) return renderRound(_roundMap[baseKey], round, suffix)
  }
  // 未命中映射：返回原始英文（数据加载完成前也用此兜底）
  return round
}

export const useRoundStore = create<RoundState>((set) => ({
  translations: [],
  ready: false,

  fetchRoundTranslations: async () => {
    try {
      // 只拉取 round 类别，供全站 round 标签翻译
      const data = await api.getCnMappings('round')
      _roundMap = {}
      data.forEach(t => { _roundMap[t.key] = t })
      set({ translations: data, ready: true })
    } catch {
      // 拉取失败也不阻塞页面，保留英文兜底
      set({ ready: true })
    }
  },
}))
