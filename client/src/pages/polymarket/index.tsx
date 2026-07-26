import { FC, useState, useEffect, useCallback } from 'react'
import Taro, { useDidShow } from '@tarojs/taro'
import { View, Text, ScrollView } from '@tarojs/components'
import './index.scss'

// ── 类型定义 ─────────────────────────────────────────────────────

interface StandaloneMarket {
  id: number
  slug: string
  question: string | null
  yes_price: number | null
  no_price: number | null
  volume: number | null
  liquidity: number | null
  category: string | null
  end_date: string | null
  is_eligible: boolean
}

interface MarketStats {
  total_markets: number
  active_markets: number
  eligible_markets: number
  avg_no_price: number | null
  total_volume: number
}

interface Category {
  name: string
  count: number
}

// ── 工具函数 ─────────────────────────────────────────────────────

const formatPrice = (price: number | null): string => {
  if (price === null || price === undefined) return '-'
  return `${(price * 100).toFixed(1)}¢`
}

const formatVolume = (volume: number | null): string => {
  if (volume === null || volume === undefined) return '-'
  if (volume >= 1000000) return `$${(volume / 1000000).toFixed(1)}M`
  if (volume >= 1000) return `$${(volume / 1000).toFixed(0)}K`
  return `$${volume.toFixed(0)}`
}

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
    })
  } catch {
    return '-'
  }
}

// ── 主页面组件 ───────────────────────────────────────────────────

const PolymarketPage: FC = () => {
  const [markets, setMarkets] = useState<StandaloneMarket[]>([])
  const [stats, setStats] = useState<MarketStats | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [showEligibleOnly, setShowEligibleOnly] = useState(false)
  const [loading, setLoading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [sortBy, setSortBy] = useState<'volume' | 'no_price' | 'liquidity'>('volume')

  // ── 数据加载 ───────────────────────────────────────────────────

  const loadMarkets = useCallback(async () => {
    setLoading(true)
    try {
      const baseUrl = process.env.TARO_APP_API_BASE_URL || 'http://localhost:8000/api/v1'
      const params = new URLSearchParams()

      if (selectedCategory) params.append('category', selectedCategory)
      if (showEligibleOnly) params.append('is_eligible', 'true')
      params.append('sort_by', sortBy)
      params.append('sort_order', 'asc')
      params.append('limit', '100')

      const response = await Taro.request({
        url: `${baseUrl}/polymarket/standalone/markets?${params.toString()}`,
        method: 'GET',
      })

      if (response.statusCode === 200) {
        setMarkets(response.data.markets || [])
      }
    } catch (error) {
      console.error('Failed to load markets:', error)
      Taro.showToast({ title: '加载失败', icon: 'none' })
    } finally {
      setLoading(false)
    }
  }, [selectedCategory, showEligibleOnly, sortBy])

  const loadStats = useCallback(async () => {
    try {
      const baseUrl = process.env.TARO_APP_API_BASE_URL || 'http://localhost:8000/api/v1'
      const response = await Taro.request({
        url: `${baseUrl}/polymarket/standalone/stats`,
        method: 'GET',
      })
      if (response.statusCode === 200) {
        setStats(response.data)
      }
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }, [])

  const loadCategories = useCallback(async () => {
    try {
      const baseUrl = process.env.TARO_APP_API_BASE_URL || 'http://localhost:8000/api/v1'
      const response = await Taro.request({
        url: `${baseUrl}/polymarket/standalone/categories`,
        method: 'GET',
      })
      if (response.statusCode === 200) {
        setCategories(response.data.categories || [])
      }
    } catch (error) {
      console.error('Failed to load categories:', error)
    }
  }, [])

  // ── 同步操作 ───────────────────────────────────────────────────

  const handleSync = async () => {
    setSyncing(true)
    try {
      const baseUrl = process.env.TARO_APP_API_BASE_URL || 'http://localhost:8000/api/v1'
      const response = await Taro.request({
        url: `${baseUrl}/polymarket/standalone/sync`,
        method: 'POST',
      })

      if (response.statusCode === 200) {
        const result = response.data
        Taro.showToast({
          title: `同步完成: ${result.detail.total_fetched} 个市场`,
          icon: 'success',
        })
        // 重新加载数据
        await Promise.all([loadMarkets(), loadStats(), loadCategories()])
      } else {
        Taro.showToast({ title: '同步失败', icon: 'none' })
      }
    } catch (error) {
      console.error('Sync failed:', error)
      Taro.showToast({ title: '同步失败', icon: 'none' })
    } finally {
      setSyncing(false)
    }
  }

  // ── 生命周期 ───────────────────────────────────────────────────

  useEffect(() => {
    Promise.all([loadMarkets(), loadStats(), loadCategories()])
  }, [loadMarkets, loadStats, loadCategories])

  useDidShow(() => {
    loadMarkets()
  })

  // ── 渲染 ───────────────────────────────────────────────────────

  return (
    <View className='polymarket-page'>
      {/* 头部统计 */}
      <View className='stats-section'>
        <View className='stats-header'>
          <Text className='stats-title'>Polymarket 市场</Text>
          <View
            className={`sync-btn ${syncing ? 'syncing' : ''}`}
            onClick={handleSync}
          >
            <Text className='sync-text'>{syncing ? '同步中...' : '🔄 同步'}</Text>
          </View>
        </View>
        {stats && (
          <View className='stats-grid'>
            <View className='stat-item'>
              <Text className='stat-value'>{stats.active_markets}</Text>
              <Text className='stat-label'>活跃市场</Text>
            </View>
            <View className='stat-item'>
              <Text className='stat-value highlight'>{stats.eligible_markets}</Text>
              <Text className='stat-label'>符合条件</Text>
            </View>
            <View className='stat-item'>
              <Text className='stat-value'>{formatPrice(stats.avg_no_price)}</Text>
              <Text className='stat-label'>平均 NO 价</Text>
            </View>
            <View className='stat-item'>
              <Text className='stat-value'>{formatVolume(stats.total_volume)}</Text>
              <Text className='stat-label'>总成交量</Text>
            </View>
          </View>
        )}
      </View>

      {/* 筛选栏 */}
      <View className='filter-section'>
        <ScrollView scrollX className='category-scroll'>
          <View
            className={`category-tag ${selectedCategory === '' ? 'active' : ''}`}
            onClick={() => setSelectedCategory('')}
          >
            <Text>全部</Text>
          </View>
          {categories.map((cat) => (
            <View
              key={cat.name}
              className={`category-tag ${selectedCategory === cat.name ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat.name)}
            >
              <Text>{cat.name} ({cat.count})</Text>
            </View>
          ))}
        </ScrollView>

        <View className='filter-row'>
          <View
            className={`filter-toggle ${showEligibleOnly ? 'active' : ''}`}
            onClick={() => setShowEligibleOnly(!showEligibleOnly)}
          >
            <Text>仅符合条件</Text>
          </View>

          <View className='sort-buttons'>
            {(['volume', 'no_price', 'liquidity'] as const).map((key) => (
              <View
                key={key}
                className={`sort-btn ${sortBy === key ? 'active' : ''}`}
                onClick={() => setSortBy(key)}
              >
                <Text>{key === 'volume' ? '成交量' : key === 'no_price' ? 'NO 价格' : '流动性'}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* 市场列表 */}
      <View className='markets-section'>
        {loading ? (
          <View className='loading'>
            <Text>加载中...</Text>
          </View>
        ) : markets.length === 0 ? (
          <View className='empty'>
            <Text className='empty-icon'>📊</Text>
            <Text className='empty-text'>暂无市场数据</Text>
            <Text className='empty-hint'>点击上方"同步"按钮拉取最新数据</Text>
          </View>
        ) : (
          <ScrollView scrollY className='markets-list'>
            {markets.map((market) => (
              <View key={market.id} className='market-card'>
                <View className='market-header'>
                  <View className='market-category'>
                    {market.category && (
                      <Text className='category-badge'>{market.category}</Text>
                    )}
                    {market.is_eligible && (
                      <Text className='eligible-badge'>✅ 符合</Text>
                    )}
                  </View>
                  <Text className='market-date'>{formatDate(market.end_date)}</Text>
                </View>

                <Text className='market-question'>{market.question}</Text>

                <View className='market-prices'>
                  <View className='price-item yes'>
                    <Text className='price-label'>YES</Text>
                    <Text className='price-value'>{formatPrice(market.yes_price)}</Text>
                  </View>
                  <View className='price-item no'>
                    <Text className='price-label'>NO</Text>
                    <Text className='price-value'>{formatPrice(market.no_price)}</Text>
                  </View>
                </View>

                <View className='market-meta'>
                  <Text className='meta-item'>成交量: {formatVolume(market.volume)}</Text>
                  <Text className='meta-item'>流动性: {formatVolume(market.liquidity)}</Text>
                </View>
              </View>
            ))}
          </ScrollView>
        )}
      </View>
    </View>
  )
}

export default PolymarketPage
