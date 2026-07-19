import Taro from '@tarojs/taro'

// dev: http://127.0.0.1:8000 / prod: https://marathoninfo.top
export const API_BASE_URL = process.env.NODE_ENV === 'production'
  ? 'https://marathoninfo.top'
  : 'http://127.0.0.1:8000'
const BASE_URL = `${API_BASE_URL}/api/v1`
const REQUEST_TIMEOUT = 15000 // 15 秒超时
const MAX_RETRY = 1 // 最大重试次数

interface RequestOptions {
  url: string
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  data?: any
  header?: Record<string, string>
  timeout?: number
  retry?: number
}

function getAuthHeader(): Record<string, string> {
  const token = Taro.getStorageSync('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function isRetryableError(err: any): boolean {
  const msg = String(err?.errMsg || err?.message || '').toLowerCase()
  return msg.includes('timeout') || msg.includes('network') || msg.includes('econnrefused')
}

/** 确保头像 URL 是完整路径（后端可能返回相对路径 /static/avatars/xxx） */
export function resolveAvatarUrl(url: string | null | undefined): string {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('preset://') || url.startsWith('wxfile://')) return url
  return `${API_BASE_URL}${url}`
}

/**
 * sofifa 头像直连会被 Cloudflare 防盗链 403（小程序 <image> 不带浏览器 UA/Referer）。
 * 改为走后端代理（已带正确 UA/Referer），其它域名原样返回。
 */
export function proxiedSofifa(url?: string | null): string {
  if (!url) return ''
  if (url.includes('cdn.sofifa.net')) {
    return `${API_BASE_URL}/api/v1/proxy/avatar?u=${encodeURIComponent(url)}`
  }
  return url
}

async function request<T = any>(options: RequestOptions): Promise<T> {
  const { url, method = 'GET', data, header = {}, timeout = REQUEST_TIMEOUT, retry = MAX_RETRY } = options
  const fullUrl = `${BASE_URL}${url}`

  for (let attempt = 0; attempt <= retry; attempt++) {
    try {
      const res = await Taro.request({
        url: fullUrl,
        method,
        data,
        timeout,
        header: {
          'Content-Type': 'application/json',
          ...getAuthHeader(),
          ...header
        }
      })
      if (res.statusCode >= 200 && res.statusCode < 300) {
        return res.data as T
      }
      if (res.statusCode === 401) {
        // token 过期，清除登录态
        Taro.removeStorageSync('token')
        Taro.showToast({ title: '登录已过期，请重新登录', icon: 'none' })
      }
      // 提取后端返回的错误信息
      const errorData = res.data as any
      const errorMsg = errorData?.detail || errorData?.message || `请求失败 (${res.statusCode})`
      const error = new Error(errorMsg)
      ;(error as any).statusCode = res.statusCode
      ;(error as any).data = errorData
      throw error
    } catch (err: any) {
      const isLastAttempt = attempt >= retry
      const msg = String(err?.errMsg || err?.message || '').toLowerCase()

      if (isLastAttempt || !isRetryableError(err)) {
        console.error(`Request failed [${method}] ${url}:`, err)
        // 超时/网络错误时给出友好提示
        if (msg.includes('timeout')) {
          Taro.showToast({ title: '请求超时，请检查网络', icon: 'none', duration: 2000 })
        } else if (msg.includes('fail') || msg.includes('network')) {
          Taro.showToast({ title: '网络异常，请稍后重试', icon: 'none', duration: 2000 })
        }
        throw err
      }

      // 重试前等待 1 秒
      console.warn(`Request retry [${attempt + 1}/${retry}] ${url}`)
      await new Promise(resolve => setTimeout(resolve, 1000))
    }
  }

  // 不应该到达这里，但 TypeScript 需要返回值
  throw new Error('Request failed after retries')
}

// ==================== 联赛相关 ====================

/** 比赛/预测响应中内嵌的联赛简要信息 */
export interface LeagueBrief {
  id: number
  name: string
  cn_name: string
  logo: string | null
  type: string
}

/** 联赛完整信息 */
export interface League {
  id: number
  name: string
  cn_name: string
  logo: string | null
  highlightly_league_id: number
  season: number
  type: string          // 'cup' | 'league'
  country: string | null
  is_active: boolean
  sort_order: number
}

/** 获取所有联赛列表（按 sort_order 排序，含 is_active 状态） */
export function getLeagues() {
  return request<League[]>({ url: '/leagues' })
}

/** 按赛季获取联赛列表 */
export function getLeaguesBySeason(season: number) {
  return request<League[]>({ url: `/leagues?season=${season}` })
}

/** 获取数据库中已有的所有赛季（降序） */
export function getLeagueSeasons() {
  return request<number[]>({ url: '/leagues/seasons/available' })
}

/** 获取单个联赛详情 */
export function getLeagueDetail(id: number) {
  return request<League>({ url: `/leagues/${id}` })
}

// ==================== 比赛相关 ====================

export interface Team {
  id: number
  name: string
  cn_name: string | null
  flag_url: string | null
  group_name: string | null
  fifa_rank: number | null
}

export interface Match {
  id: number
  match_day: number
  round: string
  match_time: string | null
  venue: string | null
  status: 'upcoming' | 'live' | 'finished'
  home_score: number | null
  away_score: number | null
  result: string | null
  league_id: number | null
  league?: LeagueBrief | null
  home_team: Team
  away_team: Team
  predictions?: Prediction[]
  summary?: PredictionSummary | null
}

export interface PredictionSummary {
  id: number
  match_id: number
  score_home: number | null
  score_away: number | null
  score_alt_home: number | null
  score_alt_away: number | null
  summary: string | null
  short_summary: string | null
  confidence: number | null
  created_at: string | null
}

export interface Prediction {
  id: number
  match_id: number
  model_id: number
  model_name: string | null
  model_avatar: string | null
  result: string
  score_home: number | null
  score_away: number | null
  score_alt_home: number | null
  score_alt_away: number | null
  score_alt_prob: number | null
  confidence: number | null
  analysis: string | null
  is_correct_result: boolean | null
  is_correct_score: boolean | null
  created_at: string | null
}

export function getMatches(params?: { league_id?: number; league_ids?: number[]; status?: string; status_not?: string; round?: string[] | string; date?: string; sort_order?: 'asc' | 'desc'; limit?: number }) {
  // 手动构建 query string，确保数组参数正确序列化为 ?round=xxx&round=yyy
  let qs = ''
  if (params) {
    const parts: string[] = []
    if (params.league_id != null) parts.push(`league_id=${params.league_id}`)
    if (params.league_ids && params.league_ids.length > 0) {
      params.league_ids.forEach(id => parts.push(`league_ids=${id}`))
    }
    if (params.status) parts.push(`status=${encodeURIComponent(params.status)}`)
    if (params.status_not) parts.push(`status_not=${encodeURIComponent(params.status_not)}`)
    if (params.round) {
      const rounds = Array.isArray(params.round) ? params.round : [params.round]
      rounds.forEach(r => parts.push(`round=${encodeURIComponent(r)}`))
    }
    if (params.date) parts.push(`date=${encodeURIComponent(params.date)}`)
    if (params.sort_order) parts.push(`sort_order=${encodeURIComponent(params.sort_order)}`)
    if (params.limit != null) parts.push(`limit=${params.limit}`)
    if (parts.length > 0) qs = '?' + parts.join('&')
  }
  return request<Match[]>({ url: `/matches${qs}` })
}

// ==================== 首页统计 ====================

export interface HomeStats {
  total_matches: number
  active_ai_models: number
  total_predictions: number
  total_users: number
  total_user_predictions: number
  total_leagues: number
}


export function getHomeStats(leagueIds?: number[]) {
  // 手动构建 query string，确保数组参数序列化为 ?league_ids=1&league_ids=2 形式
  // （直接传 data 给 GET 请求会被 Taro 序列化成 league_ids=[1,2] 导致后端 422）
  let qs = ''
  if (leagueIds && leagueIds.length > 0) {
    qs = '?' + leagueIds.map(id => `league_ids=${id}`).join('&')
  }
  return request<HomeStats>({ url: `/matches/stats${qs}` })
}

export interface HomeTabItem {
  key: string
  label: string
}

export interface HomeTabsOut {
  tabs: HomeTabItem[]
}

export function getHomeTabs(leagueIds?: number[]) {
  // 手动构建 query string，确保数组参数序列化为 ?league_ids=1&league_ids=2 形式
  // （直接传 data 给 GET 请求会被 Taro 序列化成 league_ids=[1,2] 导致后端 422）
  let qs = ''
  if (leagueIds && leagueIds.length > 0) {
    qs = '?' + leagueIds.map(id => `league_ids=${id}`).join('&')
  }
  return request<HomeTabsOut>({ url: `/matches/home-tabs${qs}` })
}

export function getMatchDetail(id: number) {
  return request<Match>({ url: `/matches/${id}` })
}

// ==================== 通用中英文映射 ====================

export interface CnMapping {
  id: number
  category: string
  key: string
  cn_value: string
  is_series: boolean
}

/** 获取通用中英文映射（可按 category 过滤，如 round / position） */
export function getCnMappings(category?: string) {
  const url = category ? `/cn-mappings?category=${encodeURIComponent(category)}` : '/cn-mappings'
  return request<CnMapping[]>({ url })
}

export function getMatchPredictions(matchId: number) {
  return request<Prediction[]>({ url: `/predictions/match/${matchId}` })
}

export interface ComparePredictionsOut {
  match_id: number
  result_distribution: { home_win: number; draw: number; away_win: number }
  predictions: {
    model_name: string
    result: string
    score: string
    score_alt: string | null
    score_alt_prob: number | null
    confidence: number | null
    analysis: string | null
  }[]
}

export function comparePredictions(matchId: number) {
  return request<ComparePredictionsOut>({ url: `/predictions/compare/${matchId}` })
}

// ==================== 数据 Tab — 球员榜 ====================

export type PlayerRankingType = 'goals' | 'assists' | 'yellow_cards' | 'red_cards'

export interface PlayerRankingItem {
  rank: number
  player_id: number
  player_name: string
  player_cn_name: string | null
  player_logo: string | null
  team_id: number | null
  team_name: string | null
  team_cn_name: string | null
  team_logo: string | null
  games_played: number
  minutes_played: number
  goals: number
  assists: number
  yellow_cards: number
  red_cards: number
  shots_total: number
  shots_on_target: number
}

export interface PlayerRankingsOut {
  league_id: number
  type: PlayerRankingType
  items: PlayerRankingItem[]
}

export function getPlayerRankings(leagueId?: number | null, type: PlayerRankingType = 'goals', limit = 50) {
  const data: Record<string, any> = { type, limit }
  if (leagueId != null) data.league_id = leagueId
  return request<PlayerRankingsOut>({ url: '/data/player-rankings', data })
}

// ==================== 排行榜 ====================

export interface AILeaderboardItem {
  model_id: number
  name: string
  avatar_url: string | null
  style_tags: Record<string, any> | null
  total: number
  settled: number
  correct_result: number
  result_accuracy: number
  correct_score: number
  score_accuracy: number
}

export interface HumanUserRankItem {
  user_id: number
  nickname: string
  avatar_url: string | null
  total: number
  settled: number
  correct_result: number
  result_accuracy: number
  correct_score: number
  score_accuracy: number
  is_me?: boolean
  real_rank: number
}

export interface MyRankItem extends HumanUserRankItem {
  _rank?: number | null
}

export interface HumanLeaderboardOut {
  top_users: HumanUserRankItem[]
  my_rank: MyRankItem | null
}

export function getAILeaderboard(leagueIds?: number[]) {
  // 手动构建 query string，确保数组参数正确序列化为 ?league_ids=1&league_ids=2
  // （直接传 data 给 GET 请求会被 Taro 序列化成 league_ids=[1,2] 导致后端 422）
  let qs = ''
  if (leagueIds && leagueIds.length > 0) {
    qs = '?' + leagueIds.map(id => `league_ids=${id}`).join('&')
  }
  return request<AILeaderboardItem[]>({ url: `/leaderboard/ai${qs}` })
}

export interface AIDetailPrediction {
  prediction_id: number
  match_id: number
  round: string
  match_time: string | null
  match_status: string
  home_team_name: string
  home_team_flag: string | null
  away_team_name: string
  away_team_flag: string | null
  match_result: string | null
  match_home_score: number | null
  match_away_score: number | null
  predicted_result: string
  predicted_home_score: number | null
  predicted_away_score: number | null
  score_alt_home: number | null
  score_alt_away: number | null
  score_alt_prob: number | null
  is_correct_result: boolean | null
  is_correct_score: boolean | null
  confidence: number | null
  created_at: string | null
}

export interface AIDetailOut {
  model_id: number
  name: string
  avatar_url: string | null
  style_tags: Record<string, any> | null
  total_predictions: number
  settled_predictions: number
  correct_results: number
  result_accuracy: float
  correct_scores: number
  score_accuracy: float
  predictions: AIDetailPrediction[]
}

export function getAIDetail(modelId: number, leagueIds?: number[]) {
  // 手动构建 query string，支持多个联赛 ID
  let qs = ''
  if (leagueIds && leagueIds.length > 0) {
    qs = '?' + leagueIds.map(id => `league_ids=${id}`).join('&')
  }
  return request<AIDetailOut>({ url: `/leaderboard/ai/${modelId}${qs}` })
}

export function getHumanLeaderboard(userId?: number, leagueIds?: number[]) {
  const parts: string[] = []
  if (userId != null) parts.push(`user_id=${userId}`)
  if (leagueIds && leagueIds.length > 0) leagueIds.forEach(id => parts.push(`league_ids=${id}`))
  const qs = parts.length > 0 ? '?' + parts.join('&') : ''
  return request<HumanLeaderboardOut>({ url: `/leaderboard/human${qs}` })
}

/** 上传头像文件，返回永久 URL */
export function uploadAvatar(filePath: string, userId: number) {
  const token = Taro.getStorageSync('token')
  return new Promise<{ avatar_url: string }>((resolve, reject) => {
    Taro.uploadFile({
      url: `${BASE_URL}/users/upload-avatar?user_id=${userId}`,
      filePath,
      name: 'file',
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            const data = JSON.parse(res.data)
            // 确保返回的 avatar_url 是完整 URL（后端可能返回相对路径）
            if (data.avatar_url && !data.avatar_url.startsWith('http') && !data.avatar_url.startsWith('preset://')) {
              data.avatar_url = `${API_BASE_URL}${data.avatar_url}`
            }
            resolve(data)
          } catch (e) {
            reject(new Error('解析响应失败'))
          }
        } else {
          reject(new Error(`上传失败: ${res.statusCode}`))
        }
      },
      fail: (err) => reject(err),
    })
  })
}

// ==================== 用户相关 ====================

export interface UserProfile {
  id: number
  nickname: string
  avatar_url: string
  total_votes: number
  correct_results: number
  correct_scores: number
  profile_setup?: boolean
}

export function wxLogin(code: string) {
  return request<{ token: string; user: UserProfile; profile_setup: boolean; is_new_user: boolean }>({ url: '/users/login', method: 'POST', data: { code } })
}

export function getUserProfile(userId: number, leagueId?: number) {
  const lq = leagueId != null ? `&league_id=${leagueId}` : ''
  return request<UserProfile>({ url: `/users/profile?user_id=${userId}${lq}` })
}

export function updateUserProfile(userId: number, nickname: string, avatarUrl: string) {
  return request<UserProfile>({
    url: `/users/profile?user_id=${userId}`,
    method: 'PUT',
    data: { nickname, avatar_url: avatarUrl },
  })
}

export function getUserVote(userId: number, matchId: number) {
  return request<VoteOut | null>({ url: `/users/vote?user_id=${userId}&match_id=${matchId}` })
}

export interface VoteOut {
  id: number
  match_id: number
  result: string
  score_home: number | null
  score_away: number | null
  is_correct_result: boolean | null
  is_correct_score: boolean | null
  created_at: string | null
}

export interface VoteHistoryItem {
  id: number
  match_id: number
  league_name: string | null
  round: string
  match_time: string | null
  home_team_name: string
  away_team_name: string
  home_team_flag: string | null
  away_team_flag: string | null
  match_status: string
  match_result: string | null
  match_home_score: number | null
  match_away_score: number | null
  predicted_result: string
  predicted_home_score: number | null
  predicted_away_score: number | null
  is_correct_result: boolean | null
  is_correct_score: boolean | null
  created_at: string | null
}

export function getUserVoteHistory(userId: number, limit = 50, offset = 0, leagueIds?: number[]) {
  const lq = leagueIds && leagueIds.length > 0
    ? leagueIds.map(id => `&league_ids=${id}`).join('')
    : ''
  return request<VoteHistoryItem[]>({ url: `/users/votes?user_id=${userId}&limit=${limit}&offset=${offset}${lq}` })
}


export function votePrediction(userId: number, matchId: number, predictedResult: string, homeScore: number, awayScore: number) {
  return request<any>({
    url: `/users/vote?user_id=${userId}`,
    method: 'POST',
    data: { match_id: matchId, result: predictedResult, score_home: homeScore, score_away: awayScore }
  })
}

// ==================== 长期预测 ====================

export interface LongTermPrediction {
  model_id: number
  model_name: string
  champion: string | null
  runner_up: string | null
  third_place: string | null
  analysis: string | null
}

export function getLongTermPredictions() {
  return request<LongTermPrediction[]>({ url: '/long-term-predictions' })
}

// ==================== 积分榜 ====================

export interface TeamStandingOut {
  rank: number
  team_id: number
  team_name: string
  team_cn_name: string | null
  flag_url: string | null
  fifa_rank: number | null
  played: number
  won: number
  draw: number
  lost: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
}

export interface GroupStandingOut {
  group_name: string
  standings: TeamStandingOut[]
}

export interface StandingsOut {
  groups: GroupStandingOut[]
  /** 联赛类型：'cup'（多组）| 'league'（单组），前端据此切换积分榜布局 */
  type?: string
}

/** 单个联赛的积分榜（含联赛元信息），用于「全部联赛」聚合视图 */
export interface LeagueStandingsOut {
  league_id: number
  league_name: string
  type: string
  groups: GroupStandingOut[]
}

/** 全部（活跃）联赛的积分榜 */
export interface AllStandingsOut {
  leagues: LeagueStandingsOut[]
}

export function getStandings(leagueId: number) {
  return request<StandingsOut>({ url: '/standings', data: { league_id: leagueId } })
}

/** 数据 Tab：获取所有活跃联赛的积分榜（不按用户选择过滤） */
export function getStandingsAll() {
  return request<AllStandingsOut>({ url: '/standings/all' })
}

// ==================== 球队 / 球员详情 ====================

export interface TeamDetailOut {
  id: number
  name: string
  cn_name: string | null
  flag_url: string | null
  group_name: string | null
  fifa_rank: number | null
  season_stats: any | null
  recent_form: any | null
}

/** 获取球队详情（基础信息 + 赛季统计 + 近期状态） */
export function getTeamDetail(id: number) {
  return request<TeamDetailOut>({ url: `/teams/${id}` })
}

export interface PlayerSeasonStatOut {
  league_id: number
  league_name: string | null
  season: number | null
  team_name: string | null
  team_cn_name: string | null
  team_logo: string | null
  position: string | null
  position_cn: string | null
  games_played: number
  minutes_played: number
  goals: number
  assists: number
  yellow_cards: number
  red_cards: number
  second_yellow: number
  shots_total: number
  shots_on_target: number
}

export interface PlayerDetailOut {
  id: number
  name: string
  cn_name: string | null
  full_name: string | null
  logo: string | null
  position_main: string | null
  position_main_cn: string | null
  position_secondary: string | null
  position_secondary_cn: string | null
  height: string | null
  citizenship: string | null
  birth_date: string | null
  club: string | null
  club_cn_name: string | null
  stats: PlayerSeasonStatOut[]
}


/** 获取球员详情（基础主数据 + 各联赛统计；leagueId 限定联赛） */
export function getPlayerDetail(id: number, leagueId?: number | null) {
  const qs = leagueId != null ? `?league_id=${leagueId}` : ''
  return request<PlayerDetailOut>({ url: `/players/${id}${qs}` })
}



// ==================== 管理 ====================

export function syncMatches() {
  return request<any>({ url: '/admin/matches/sync', method: 'POST' })
}

export function generatePredictions(matchId?: number) {
  const url = matchId ? `/admin/predictions/generate/${matchId}` : '/admin/predictions/generate'
  return request<any>({ url, method: 'POST' })
}

// ==================== VIP 管理 ====================

export interface VipStatus {
  is_vip: boolean
  plan_type: string | null
  expire_at: string | null
  days_remaining: number
}

export interface VipMember {
  id: number
  user_id: number
  openid: string
  nickname: string | null
  avatar_url: string | null
  plan_type: string
  start_at: string | null
  expire_at: string | null
  remark: string | null
  created_at: string | null
}

export interface VipStats {
  total: number
  monthly: number
  quarterly: number
  yearly: number
  permanent: number
}

export interface AddVipRequest {
  openid: string
  plan_type: string
  remark?: string
}

export interface RenewVipRequest {
  user_id: number
  plan_type: string
}

export function getVipStatus(userId: number) {
  return request<VipStatus>({ url: `/users/vip-status?user_id=${userId}` })
}

export function addVip(data: AddVipRequest) {
  return request<any>({ url: '/admin/vip/add', method: 'POST', data })
}

export function getVipList() {
  return request<VipMember[]>({ url: '/admin/vip/list' })
}

export function renewVip(data: RenewVipRequest) {
  return request<any>({ url: '/admin/vip/renew', method: 'POST', data })
}

export function deleteVip(memberId: number) {
  return request<any>({ url: `/admin/vip/${memberId}`, method: 'DELETE' })
}

export function getVipStats() {
  return request<VipStats>({ url: '/admin/vip/stats' })
}

// ==================== 用户搜索 ====================

export interface SearchResult {
  id: number
  openid: string
  nickname: string | null
  avatar_url: string | null
}

export function searchUsers(keyword: string) {
  return request<SearchResult[]>({ url: `/users/search?keyword=${encodeURIComponent(keyword)}` })
}

export function evaluatePredictions() {
  return request<any>({ url: '/admin/predictions/evaluate', method: 'POST' })
}

// ==================== 应用配置 ====================

// 已移除：世界杯落幕引导页相关接口（getAppConfig / welcome）
// 如需动态应用配置，可在此处重新扩展。

