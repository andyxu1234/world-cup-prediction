import { create } from 'zustand'
import Taro from '@tarojs/taro'
import type { Match, Prediction, AILeaderboardItem, HumanUserRankItem, ComparePredictionsOut, HomeStats } from '@/services/api'
import * as api from '@/services/api'

// ==================== 比赛状态 ====================

interface MatchState {
  matches: Match[]
  currentMatch: Match | null
  predictions: ComparePredictionsOut['predictions']
  homeStats: HomeStats | null
  loading: boolean
  fetchMatches: (params?: { status?: string; round?: string[] | string; date?: string }) => Promise<void>
  fetchMatchDetail: (id: number) => Promise<void>
  fetchPredictions: (matchId: number) => Promise<void>
  fetchHomeStats: () => Promise<void>
}

export const useMatchStore = create<MatchState>((set) => ({
  matches: [],
  currentMatch: null,
  predictions: [],
  homeStats: null,
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

  fetchHomeStats: async () => {
    try {
      const homeStats = await api.getHomeStats()
      set({ homeStats })
    } catch {
      // ignore, keep default
    }
  },
}))

// ==================== 排行榜状态 ====================

/** 中文轮次标签 → 数据库实际 round 英文值 */
const LEADERBOARD_ROUND_MAP: Record<string, string> = {
  '小组赛': 'Group Stage - 1,Group Stage - 2,Group Stage - 3',
  '淘汰赛': 'Round of 32,Round of 16,Quarter-finals,Semi-finals,3rd Place Final,Final',
}

/** 解析排行榜 activeRound 为 API 需要的英文 round 字符串 */
function resolveLeaderboardRound(activeRound: string): string {
  return LEADERBOARD_ROUND_MAP[activeRound] || ''
}

interface LeaderboardState {
  activeTab: 'ai' | 'human'
  activeRound: string
  sortMode: 'composite' | 'field'
  sortBy: 'result_accuracy' | 'score_accuracy'
  sortOrder: 'asc' | 'desc'
  entries: AILeaderboardItem[]
  topUsers: HumanUserRankItem[]
  loading: boolean
  setActiveTab: (tab: 'ai' | 'human') => void
  setActiveRound: (round: string) => void
  setSortMode: (mode: 'composite' | 'field') => void
  setSort: (sortBy: 'result_accuracy' | 'score_accuracy', sortOrder: 'asc' | 'desc') => void
  fetchLeaderboard: () => Promise<void>
}

/** 对 entries 做客户端排序 */
function applySort(entries: AILeaderboardItem[], sortBy: 'result_accuracy' | 'score_accuracy', sortOrder: 'asc' | 'desc'): AILeaderboardItem[] {
  const dir = sortOrder === 'asc' ? 1 : -1
  return [...entries].sort((a, b) => {
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
  activeRound: '全部',
  sortMode: 'composite',   // 默认综合排序
  sortBy: 'score_accuracy',  // 默认以比分命中率排序
  sortOrder: 'desc',
  entries: [],
  humanData: null,
  topUsers: [],
  mixedRank: [],
  loading: false,

  setActiveTab: (tab) => {
    set({ activeTab: tab })
    get().fetchLeaderboard()
  },

  setActiveRound: (round) => {
    set({ activeRound: round })
    get().fetchLeaderboard()
  },

  setSortMode: (mode) => {
    if (mode === 'composite') {
      set({ sortMode: 'composite', sortBy: 'score_accuracy', sortOrder: 'desc' })
    } else {
      set({ sortMode: 'field' })
    }
    const { entries, topUsers } = get()
    const sb = get().sortBy
    const so = get().sortOrder
    const newEntries = applySort(entries, sb, so)
    let newTopUsers = applyUserSort(topUsers, sb, so)
    // 当前置顶
    const meIdx = newTopUsers.findIndex(u => u.is_me)
    if (meIdx > 0) {
      const [me] = newTopUsers.splice(meIdx, 1)
      newTopUsers.unshift(me)
    }
    set({ entries: newEntries, topUsers: newTopUsers })
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
    const { activeTab, activeRound, sortBy, sortOrder } = get()
    const resolvedRound = resolveLeaderboardRound(activeRound)
    set({ loading: true })
    try {
      if (activeTab === 'ai') {
        const rawEntries = await api.getAILeaderboard(resolvedRound)
        set({
          entries: applySort(rawEntries as AILeaderboardItem[], sortBy, sortOrder),
          topUsers: [],
          loading: false,
        })
      } else {
        const userId = useUserStore.getState().user?.id
        const humanData = await api.getHumanLeaderboard(userId, resolvedRound)
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
