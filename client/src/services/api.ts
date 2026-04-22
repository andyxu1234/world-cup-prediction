import Taro from '@tarojs/taro'

// H5 开发模式通过 devServer proxy 走同域 /api 代理，避免跨域
// 微信小程序开发模式直连 127.0.0.1:8000（需在微信开发者工具中勾选"不校验合法域名"）
// 注意：小程序中 localhost 可能解析到 IPv6 ::1 导致连接失败，必须用 127.0.0.1
// 生产环境需替换为实际后端域名
const BASE_URL = process.env.NODE_ENV === 'production'
  ? 'https://your-domain.com/api/v1'
  : process.env.TARO_ENV === 'h5'
    ? '/api/v1'
    : 'http://127.0.0.1:8000/api/v1'
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
      throw new Error(`API Error: ${res.statusCode}`)
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

export function getMatches(params?: { status?: string; round?: string[] | string; date?: string }) {
  // 手动构建 query string，确保数组参数正确序列化为 ?round=xxx&round=yyy
  let qs = ''
  if (params) {
    const parts: string[] = []
    if (params.status) parts.push(`status=${encodeURIComponent(params.status)}`)
    if (params.round) {
      const rounds = Array.isArray(params.round) ? params.round : [params.round]
      rounds.forEach(r => parts.push(`round=${encodeURIComponent(r)}`))
    }
    if (params.date) parts.push(`date=${encodeURIComponent(params.date)}`)
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
}

export function getHomeStats() {
  return request<HomeStats>({ url: '/matches/stats' })
}

export function getMatchDetail(id: number) {
  return request<Match>({ url: `/matches/${id}` })
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

// ==================== 打脸合集 ====================

export interface FaceSlap {
  prediction_id: number
  model_name: string
  model_avatar: string | null
  match_id: number
  home_team: string          // 主队中文名
  away_team: string          // 客队中文名
  home_team_flag: string | null   // 主队国旗
  away_team_flag: string | null   // 客队国旗
  predicted_result: string
  predicted_score: string
  actual_result: string
  actual_score: string
  confidence: number | null
  analysis: string | null
  face_slap_index: number
  score_absurdity: number
  match_time: string | null
}

export type FaceSlapSort = 'latest' | 'confidence' | 'absurdity'

export function getFaceSlaps(sort: FaceSlapSort = 'latest', limit = 20) {
  return request<FaceSlap[]>({ url: '/predictions/face-slaps', data: { sort, limit } })
}

// ==================== 排行榜 ====================

export interface AILeaderboardItem {
  model_id: number
  name: string
  avatar_url: string | null
  style_tags: Record<string, any> | null
  total: number
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
  correct_result: number
  result_accuracy: number
  correct_score: number
  score_accuracy: number
}

export interface MyRankItem extends HumanUserRankItem {
  _rank?: number | null
}

export interface HumanLeaderboardOut {
  human: {
    name: string
    total: number
    correct_result: number
    result_accuracy: number
    correct_score: number
    score_accuracy: number
  }
  ai_models: AILeaderboardItem[]
  top_users: HumanUserRankItem[]
  my_rank: MyRankItem | null
}

export function getAILeaderboard(round?: string) {
  return request<AILeaderboardItem[]>({ url: '/leaderboard/ai', data: round ? { round } : {} })
}

export function getHumanLeaderboard(userId?: number) {
  return request<HumanLeaderboardOut>({ url: '/leaderboard/human', data: userId ? { user_id: userId } : {} })
}

/** 上传头像文件，返回永久 URL */
export function uploadAvatar(filePath: string, userId: number) {
  const BASE_URL = process.env.NODE_ENV === 'production'
    ? 'https://your-domain.com/api/v1'
    : process.env.TARO_ENV === 'h5'
      ? '/api/v1'
      : 'http://127.0.0.1:8000/api/v1'
  return new Promise<{ avatar_url: string }>((resolve, reject) => {
    Taro.uploadFile({
      url: `${BASE_URL}/users/upload-avatar?user_id=${userId}`,
      filePath,
      name: 'file',
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(res.data))
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
}

export function wxLogin(code: string) {
  return request<{ token: string; user: UserProfile }>({ url: '/users/login', method: 'POST', data: { code } })
}

export function getUserProfile(userId: number) {
  return request<UserProfile>({ url: `/users/profile?user_id=${userId}` })
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

export function getUserVoteHistory(userId: number, limit = 50, offset = 0) {
  return request<VoteHistoryItem[]>({ url: `/users/votes?user_id=${userId}&limit=${limit}&offset=${offset}` })
}

export function votePrediction(userId: number, matchId: number, predictedResult: string, homeScore: number, awayScore: number) {
  return request<any>({
    url: `/users/vote?user_id=${userId}`,
    method: 'POST',
    data: { match_id: matchId, result: predictedResult, score_home: homeScore, score_away: awayScore }
  })
}

// ==================== 分享卡片 ====================

export interface ShareCard {
  match_id: number
  home_team: string
  home_flag: string
  away_team: string
  away_flag: string
  match_time: string
  round: string
  status: string
  home_score: number | null
  away_score: number | null
  predictions: any[]
}

export function getShareCard(matchId: number) {
  return request<ShareCard>({ url: `/share/card/${matchId}` })
}

export function getShareCardImage(matchId: number) {
  return `${BASE_URL}/share/card/${matchId}/image`
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

// ==================== 管理 ====================

export function syncMatches() {
  return request<any>({ url: '/admin/matches/sync', method: 'POST' })
}

export function generatePredictions(matchId?: number) {
  const url = matchId ? `/admin/predictions/generate/${matchId}` : '/admin/predictions/generate'
  return request<any>({ url, method: 'POST' })
}

export function evaluatePredictions() {
  return request<any>({ url: '/admin/predictions/evaluate', method: 'POST' })
}
