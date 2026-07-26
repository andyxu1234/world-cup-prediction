/**
 * Polymarket 通用市场 API 服务
 *
 * 提供市场查询、筛选、同步等功能
 */

import { get, post } from './api'

// ── 类型定义 ─────────────────────────────────────────────────────

export interface StandaloneMarket {
  id: number
  slug: string
  condition_id: string | null
  question: string | null
  yes_token_id: string | null
  no_token_id: string | null
  yes_price: number | null
  no_price: number | null
  volume: number | null
  liquidity: number | null
  min_order_size: number | null
  category: string | null
  event_slug: string | null
  end_date: string | null
  end_ts: number | null
  is_eligible: boolean
  no_entry_price: number | null
  last_synced_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface MarketListResponse {
  markets: StandaloneMarket[]
  total: number
  limit: number
  offset: number
}

export interface Category {
  name: string
  count: number
}

export interface MarketStats {
  total_markets: number
  active_markets: number
  eligible_markets: number
  avg_no_price: number | null
  total_volume: number
}

export interface SyncResult {
  status: string
  message: string
  detail: {
    total_fetched: number
    total_filtered: number
    new_markets: number
    updated_markets: number
    expired_removed: number
    eligible_count: number
  }
}

// ── API 函数 ─────────────────────────────────────────────────────

/**
 * 获取市场列表
 */
export async function getMarkets(params?: {
  category?: string
  is_eligible?: boolean
  max_price?: number
  min_volume?: number
  min_liquidity?: number
  sort_by?: 'volume' | 'liquidity' | 'no_price' | 'end_ts'
  sort_order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}): Promise<MarketListResponse> {
  const queryParams = new URLSearchParams()
  if (params?.category) queryParams.append('category', params.category)
  if (params?.is_eligible !== undefined) queryParams.append('is_eligible', String(params.is_eligible))
  if (params?.max_price !== undefined) queryParams.append('max_price', String(params.max_price))
  if (params?.min_volume !== undefined) queryParams.append('min_volume', String(params.min_volume))
  if (params?.min_liquidity !== undefined) queryParams.append('min_liquidity', String(params.min_liquidity))
  if (params?.sort_by) queryParams.append('sort_by', params.sort_by)
  if (params?.sort_order) queryParams.append('sort_order', params.sort_order)
  if (params?.limit !== undefined) queryParams.append('limit', String(params.limit))
  if (params?.offset !== undefined) queryParams.append('offset', String(params.offset))

  const query = queryParams.toString()
  return get<MarketListResponse>(`/polymarket/standalone/markets${query ? '?' + query : ''}`)
}

/**
 * 获取符合条件的市场（NO farming 候选）
 */
export async function getEligibleMarkets(params?: {
  max_price?: number
  min_volume?: number
  sort_by?: string
  limit?: number
  offset?: number
}): Promise<MarketListResponse> {
  const queryParams = new URLSearchParams()
  if (params?.max_price !== undefined) queryParams.append('max_price', String(params.max_price))
  if (params?.min_volume !== undefined) queryParams.append('min_volume', String(params.min_volume))
  if (params?.sort_by) queryParams.append('sort_by', params.sort_by)
  if (params?.limit !== undefined) queryParams.append('limit', String(params.limit))
  if (params?.offset !== undefined) queryParams.append('offset', String(params.offset))

  const query = queryParams.toString()
  return get<MarketListResponse>(`/polymarket/standalone/markets/eligible${query ? '?' + query : ''}`)
}

/**
 * 根据 slug 获取单个市场详情
 */
export async function getMarketBySlug(slug: string): Promise<StandaloneMarket> {
  return get<StandaloneMarket>(`/polymarket/standalone/markets/${encodeURIComponent(slug)}`)
}

/**
 * 获取所有市场类别
 */
export async function getCategories(): Promise<{ categories: Category[]; total_categories: number }> {
  return get('/polymarket/standalone/categories')
}

/**
 * 获取市场统计信息
 */
export async function getStats(): Promise<MarketStats> {
  return get('/polymarket/standalone/stats')
}

/**
 * 手动触发市场同步
 */
export async function triggerSync(): Promise<SyncResult> {
  return post('/polymarket/standalone/sync')
}
