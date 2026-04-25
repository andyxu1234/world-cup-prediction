import { create } from 'zustand'
import Taro from '@tarojs/taro'
import type { Match, Prediction, AILeaderboardItem, HumanLeaderboardOut, HumanUserRankItem, MyRankItem, ComparePredictionsOut, HomeStats } from '@/services/api'
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
  humanData: HumanLeaderboardOut | null
  topUsers: HumanUserRankItem[]
  mixedRank: MixedRankItem[]
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

/** 混合排行条目：人机合一 */
export interface MixedRankItem {
  type: 'human' | 'ai'
  name: string
  total: number
  result_accuracy: number
  score_accuracy: number
  // human 特有
  user_id?: number
  nickname?: string
  avatar_url?: string | null
  isMe?: boolean
  // ai 特有
  model_id?: number
  style_tags?: Record<string, any> | null
}

/** 合并并排序人机排行（取前20条） */
function buildMixedRank(
  users: HumanUserRankItem[],
  ais: AILeaderboardItem[],
  myRank: MyRankItem | null,
  currentUserId: number | undefined,
  sortBy: string,
  sortOrder: string,
): MixedRankItem[] {
  const humanItems: MixedRankItem[] = users.map(u => ({
    type: 'human' as const,
    name: u.nickname || '匿名用户',
    total: u.total,
    result_accuracy: u.result_accuracy,
    score_accuracy: u.score_accuracy,
    user_id: u.user_id,
    nickname: u.nickname || '匿名用户',
    avatar_url: u.avatar_url,
    isMe: currentUserId === u.user_id,
  }))

  // 如果我的排名不在 topUsers 中，追加进去
  if (myRank && !users.some(u => u.user_id === myRank.user_id)) {
    humanItems.push({
      type: 'human' as const,
      name: myRank.nickname || '我',
      total: myRank.total,
      result_accuracy: myRank.result_accuracy,
      score_accuracy: myRank.score_accuracy,
      user_id: myRank.user_id,
      nickname: myRank.nickname || '我',
      avatar_url: myRank.avatar_url,
      isMe: true,
    })
  }

  const aiItems: MixedRankItem[] = ais.map(a => ({
    type: 'ai' as const,
    name: a.name,
    total: a.total,
    result_accuracy: a.result_accuracy,
    score_accuracy: a.score_accuracy,
    model_id: a.model_id,
    style_tags: a.style_tags,
  }))

  const all = [...humanItems, ...aiItems]
  const dir = sortOrder === 'asc' ? 1 : -1
  const sortKey = sortBy as keyof Pick<MixedRankItem, 'result_accuracy' | 'score_accuracy'>
  const subKey = sortKey === 'result_accuracy' ? 'score_accuracy' : 'result_accuracy'

  all.sort((a, b) => {
    const diff = (a[sortKey] ?? 0) - (b[sortKey] ?? 0)
    if (diff !== 0) return diff * dir
    const diff2 = (a[subKey] ?? 0) - (b[subKey] ?? 0)
    if (diff2 !== 0) return -diff2
    return (b.total ?? 0) - (a.total ?? 0)
  })

  return all.slice(0, 20)
}

export const useLeaderboardStore = create<LeaderboardState>((set, get) => ({
  activeTab: 'ai',
  activeRound: '全部',
  sortMode: 'composite',   // 默认综合排序
  sortBy: 'result_accuracy',
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
      set({ sortMode: 'composite', sortBy: 'result_accuracy', sortOrder: 'desc' })
    } else {
      set({ sortMode: 'field' })
    }
    const { entries, topUsers, humanData, activeTab } = get()
    const sb = get().sortBy
    const so = get().sortOrder
    const newEntries = applySort(entries, sb, so)
    const newTopUsers = applyUserSort(topUsers, sb, so)
    let mr: MixedRankItem[] = []
    if (activeTab === 'human' && humanData) {
      const uid = useUserStore.getState().user?.id
      mr = buildMixedRank(topUsers, newEntries, humanData.my_rank ?? null, uid, sb, so)
    }
    set({ entries: newEntries, topUsers: newTopUsers, mixedRank: mr })
  },

  setSort: (sortBy, sortOrder) => {
    const { entries, topUsers, humanData, activeTab } = get()
    const newEntries = applySort(entries, sortBy, sortOrder)
    const newTopUsers = applyUserSort(topUsers, sortBy, sortOrder)
    let mr: MixedRankItem[] = []
    if (activeTab === 'human' && humanData) {
      const uid = useUserStore.getState().user?.id
      mr = buildMixedRank(topUsers, newEntries, humanData.my_rank ?? null, uid, sortBy, sortOrder)
    }
    set({
      sortMode: 'field', sortBy, sortOrder,
      entries: newEntries,
      topUsers: newTopUsers,
      mixedRank: mr,
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
          humanData: null,
          topUsers: [],
          mixedRank: [],
          loading: false,
        })
      } else {
        const userId = useUserStore.getState().user?.id
        const humanData = await api.getHumanLeaderboard(userId, resolvedRound)
        const sortedAis = applySort(humanData.ai_models as AILeaderboardItem[], sortBy, sortOrder)
        const sortedUsers = applyUserSort(humanData.top_users as HumanUserRankItem[], sortBy, sortOrder)
        const mixed = buildMixedRank(sortedUsers, sortedAis, humanData.my_rank ?? null, userId, sortBy, sortOrder)
        set({
          entries: sortedAis,
          topUsers: sortedUsers,
          mixedRank: mixed,
          humanData,
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
  setLoginReady: () => void
  login: (code: string) => Promise<void>
  fetchProfile: (userId: number) => Promise<void>
  updateProfile: (nickname: string, avatarUrl: string) => Promise<void>
  fetchVote: (userId: number, matchId: number) => Promise<void>
  vote: (matchId: number, result: string, homeScore: number, awayScore: number) => Promise<void>
  logout: () => void
}

export const useUserStore = create<UserState>((set, get) => ({
  user: null,
  token: Taro.getStorageSync('token') || null,
  myVote: null,
  profileSetup: Taro.getStorageSync('profile_setup') || false,
  loginReady: false, // 每次启动都从 false 开始，等 login 接口返回后再设为 true

  setLoginReady: () => {
    if (!get().loginReady) {
      set({ loginReady: true })
    }
  },

  login: async (code) => {
    const res = await api.wxLogin(code)
    const profileSetup = res.profile_setup ?? false
    // loginReady 跟随 profileSetup：未完善资料时不放行首页
    set({ user: res.user, token: res.token, profileSetup, loginReady: profileSetup })
    Taro.setStorageSync('token', res.token)
    Taro.setStorageSync('profile_setup', profileSetup)
    // 登录后刷新排行榜（获取我的排名）
    useLeaderboardStore.getState().fetchLeaderboard()
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

  logout: () => {
    set({ user: null, token: null, profileSetup: false, loginReady: false })
    Taro.removeStorageSync('token')
    Taro.removeStorageSync('profile_setup')
  }
}))
