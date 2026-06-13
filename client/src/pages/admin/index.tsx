import { useEffect, useState, useRef } from 'react'
import { View, Text, Input, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import { isAdmin } from '@/utils/admin'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

const PLAN_OPTIONS = [
  { value: 'monthly', label: '月卡', price: '¥9.9', days: '30天' },
  { value: 'quarterly', label: '季卡', price: '¥19.9', days: '90天' },
  { value: 'yearly', label: '年卡', price: '¥69.9', days: '365天' },
  { value: 'permanent', label: '永久卡', price: '¥99.9', days: '永久' },
]

const PAYMENT_OPTIONS = [
  { value: '微信转账', label: '微信转账' },
  { value: '支付宝转账', label: '支付宝转账' },
]

export default function Admin() {
  const { user } = useUserStore()
  const [stats, setStats] = useState<any>(null)
  const [members, setMembers] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  // 搜索状态
  const [searchKeyword, setSearchKeyword] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedUser, setSelectedUser] = useState<any>(null)
  const [selectedPlan, setSelectedPlan] = useState(0)
  const [selectedPayment, setSelectedPayment] = useState(0)
  const searchTimer = useRef<any>(null)

  // 计算过滤后的会员列表（搜索时联动）
  const filteredMembers = searchKeyword.trim()
    ? members.filter(m =>
        m.nickname?.toLowerCase().includes(searchKeyword.toLowerCase()) ||
        m.openid.toLowerCase().includes(searchKeyword.toLowerCase())
      )
    : members

  // 检查用户是否已经是 VIP
  const isUserVip = (userId: number) => {
    return members.some(m => m.user_id === userId)
  }

  // 权限检查
  useEffect(() => {
    if (!isAdmin(user?.openid)) {
      Taro.showToast({ title: '无权限访问', icon: 'none' })
      setTimeout(() => Taro.navigateBack(), 1500)
    }
  }, [user?.openid])

  // 加载数据
  useEffect(() => {
    if (isAdmin(user?.openid)) {
      loadStats()
      loadMembers()
    }
  }, [user?.openid])

  const loadStats = async () => {
    try {
      setStats(await api.getVipStats())
    } catch (err) {
      console.error('加载统计失败:', err)
    }
  }

  const loadMembers = async () => {
    try {
      setMembers(await api.getVipList())
    } catch (err) {
      console.error('加载会员列表失败:', err)
    }
  }

  // 搜索用户（防抖）
  const handleSearchInput = (val: string) => {
    setSearchKeyword(val)
    setSelectedUser(null)
    if (searchTimer.current) clearTimeout(searchTimer.current)
    if (!val.trim()) {
      setSearchResults([])
      return
    }
    searchTimer.current = setTimeout(async () => {
      setSearching(true)
      try {
        const results = await api.searchUsers(val.trim())
        setSearchResults(results)
      } catch {
        setSearchResults([])
      } finally {
        setSearching(false)
      }
    }, 500)
  }

  const handleSelectUser = (u: any) => {
    setSelectedUser(u)
    setSearchKeyword(u.nickname || u.openid)
    setSearchResults([])
  }

  const handleClearSelection = () => {
    setSelectedUser(null)
    setSearchKeyword('')
    setSearchResults([])
    setSelectedPayment(0)
  }

  // 添加 VIP
  const handleAddVip = async () => {
    if (!selectedUser) {
      Taro.showToast({ title: '请先搜索并选择用户', icon: 'none' })
      return
    }
    setLoading(true)
    try {
      await api.addVip({
        openid: selectedUser.openid,
        plan_type: PLAN_OPTIONS[selectedPlan].value,
        remark: PAYMENT_OPTIONS[selectedPayment].value,
      })
      Taro.showToast({ title: '添加成功', icon: 'success' })
      handleClearSelection()
      loadStats()
      loadMembers()
    } catch (err: any) {
      const msg = err?.message || '添加失败'
      Taro.showToast({ title: msg, icon: 'error' })
    } finally {
      setLoading(false)
    }
  }

  // 删除 VIP
  const handleDeleteVip = async (id: number, nickname: string) => {
    const res = await Taro.showModal({
      title: '确认移除',
      content: `确定要移除「${nickname || '该用户'}」的 VIP 吗？`,
      confirmColor: '#ef4444',
    })
    if (res.confirm) {
      try {
        await api.deleteVip(id)
        Taro.showToast({ title: '已移除', icon: 'success' })
        loadStats()
        loadMembers()
      } catch {
        Taro.showToast({ title: '操作失败', icon: 'error' })
      }
    }
  }

  const formatDate = (d: string | null) => {
    if (!d) return '永久'
    const dt = new Date(d)
    return `${dt.getMonth() + 1}/${dt.getDate()}`
  }

  const getPlanLabel = (v: string) =>
    PLAN_OPTIONS.find(p => p.value === v)?.label || v

  const getPlanColor = (v: string) => {
    const map: Record<string, string> = {
      monthly: '#3b82f6',
      quarterly: '#8b5cf6',
      yearly: '#f59e0b',
      permanent: '#ef4444',
    }
    return map[v] || '#64748b'
  }

  // 统计卡片数据
  const statCards = [
    { key: 'total', label: '总会员', value: stats?.total ?? 0, accent: '#10b981' },
    { key: 'monthly', label: '月卡', value: stats?.monthly ?? 0, accent: '#3b82f6' },
    { key: 'quarterly', label: '季卡', value: stats?.quarterly ?? 0, accent: '#8b5cf6' },
    { key: 'yearly', label: '年卡', value: stats?.yearly ?? 0, accent: '#f59e0b' },
    { key: 'permanent', label: '永久', value: stats?.permanent ?? 0, accent: '#ef4444' },
  ]

  if (!isAdmin(user?.openid)) {
    return (
      <View className='admin-page'>
        <View className='admin-forbidden'>
          <Text className='admin-forbidden-icon'>🔒</Text>
          <Text className='admin-forbidden-text'>无权限访问</Text>
        </View>
      </View>
    )
  }

  return (
    <View className='admin-page'>
      {/* ── 顶部暗色区 ── */}
      <View className='admin-hero'>
        <View className='admin-hero-glow' />
        <Text className='admin-hero-title'>后台管理</Text>
        <Text className='admin-hero-sub'>VIP 会员控制台</Text>

        {/* 统计卡片横向滚动 */}
        <View className='admin-stats-scroll'>
          <View className='admin-stats-row'>
            {statCards.map((s) => (
              <View key={s.key} className='admin-stat-card'>
                <Text className='admin-stat-num' style={{ color: s.accent }}>{s.value}</Text>
                <Text className='admin-stat-label'>{s.label}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      {/* ── 搜索 + 添加 VIP ── */}
      <View className='admin-section'>
        <Text className='admin-section-title'>添加会员</Text>

        {/* 搜索框 */}
        <View className='admin-search-wrap'>
          <Text className='admin-search-icon'>🔍</Text>
          <Input
            className='admin-search-input'
            placeholder='输入用户昵称搜索'
            value={searchKeyword}
            onInput={(e) => handleSearchInput(e.detail.value)}
          />
          {(searchKeyword || selectedUser) && (
            <Text className='admin-search-clear' onClick={handleClearSelection}>✕</Text>
          )}
        </View>

        {/* 搜索结果下拉 */}
        {searchResults.length > 0 && !selectedUser && (
          <View className='admin-search-dropdown'>
            {searchResults.map((u) => {
              const isVip = isUserVip(u.id)
              return (
                <View
                  key={u.id}
                  className={`admin-search-item ${isVip ? 'is-vip' : ''}`}
                  onClick={() => handleSelectUser(u)}
                >
                  <Image
                    className='admin-search-avatar'
                    src={resolveAvatarUrl(u.avatar_url)}
                    mode='aspectFill'
                  />
                  <View className='admin-search-info'>
                    <View className='admin-search-name-row'>
                      <Text className='admin-search-name'>{u.nickname || '未设置昵称'}</Text>
                      {isVip && <Text className='admin-search-vip-tag'>VIP</Text>}
                    </View>
                    <Text className='admin-search-id'>ID: {u.id}</Text>
                  </View>
                </View>
              )
            })}
          </View>
        )}

        {searching && (
          <View className='admin-search-loading'>
            <Text>搜索中…</Text>
          </View>
        )}

        {searchKeyword && !searching && searchResults.length === 0 && !selectedUser && (
          <View className='admin-search-empty'>
            <Text>未找到匹配用户</Text>
          </View>
        )}

        {/* 已选用户 + 套餐选择 + 提交 */}
        {selectedUser && (
          <View className='admin-add-form'>
            {/* 已选用户卡片 */}
            <View className='admin-selected-user'>
              <Image
                className='admin-selected-avatar'
                src={resolveAvatarUrl(selectedUser.avatar_url)}
                mode='aspectFill'
              />
              <View className='admin-selected-info'>
                <Text className='admin-selected-name'>{selectedUser.nickname || '未设置昵称'}</Text>
                <Text className='admin-selected-openid'>openid: {selectedUser.openid}</Text>
              </View>
            </View>

            {/* 套餐选择 */}
            <Text className='admin-form-label'>选择套餐</Text>
            <View className='admin-plan-grid'>
              {PLAN_OPTIONS.map((p, i) => (
                <View
                  key={p.value}
                  className={`admin-plan-card ${selectedPlan === i ? 'active' : ''}`}
                  onClick={() => setSelectedPlan(i)}
                >
                  <Text className='admin-plan-name'>{p.label}</Text>
                  <Text className='admin-plan-price'>{p.price}</Text>
                  <Text className='admin-plan-days'>{p.days}</Text>
                </View>
              ))}
            </View>

            {/* 支付方式 */}
            <Text className='admin-form-label'>支付方式</Text>
            <View className='admin-payment-grid'>
              {PAYMENT_OPTIONS.map((p, i) => (
                <View
                  key={p.value}
                  className={`admin-payment-card ${selectedPayment === i ? 'active' : ''}`}
                  onClick={() => setSelectedPayment(i)}
                >
                  <Text className='admin-payment-icon'>{i === 0 ? '💚' : '🔵'}</Text>
                  <Text className='admin-payment-label'>{p.label}</Text>
                </View>
              ))}
            </View>

            {/* 提交按钮 */}
            <View
              className={`admin-submit-btn ${loading ? 'loading' : ''}`}
              onClick={!loading ? handleAddVip : undefined}
            >
              <Text className='admin-submit-text'>
                {loading ? '添加中…' : `添加 ${PLAN_OPTIONS[selectedPlan].label}`}
              </Text>
            </View>
          </View>
        )}
      </View>

      {/* ── 会员列表 ── */}
      <View className='admin-section'>
        <View className='admin-section-header'>
          <Text className='admin-section-title'>
            {searchKeyword.trim() ? '搜索结果' : '会员列表'}
          </Text>
          <Text className='admin-section-count'>
            {filteredMembers.length} 人
            {searchKeyword.trim() && ` / ${members.length} 人`}
          </Text>
        </View>

        {filteredMembers.length === 0 ? (
          <View className='admin-empty'>
            <Text className='admin-empty-icon'>📭</Text>
            <Text className='admin-empty-text'>
              {searchKeyword.trim() ? '未找到匹配的会员' : '暂无会员'}
            </Text>
          </View>
        ) : (
          <View className='admin-member-list'>
            {filteredMembers.map((m) => (
              <View key={m.id} className='admin-member-card'>
                <View className='admin-member-left'>
                  <Image
                    className='admin-member-avatar'
                    src={resolveAvatarUrl(m.avatar_url)}
                    mode='aspectFill'
                  />
                  <View className='admin-member-info'>
                    <Text className='admin-member-name'>{m.nickname || '未设置昵称'}</Text>
                    <View className='admin-member-meta'>
                      <Text
                        className='admin-member-tag'
                        style={{ color: getPlanColor(m.plan_type), background: `${getPlanColor(m.plan_type)}15` }}
                      >
                        {getPlanLabel(m.plan_type)}
                      </Text>
                      <Text className='admin-member-date'>
                        {m.plan_type === 'permanent' ? '永久有效' : `到期 ${formatDate(m.expire_at)}`}
                      </Text>
                    </View>
                    {m.remark && (
                      <Text className='admin-member-remark'>📝 {m.remark}</Text>
                    )}
                  </View>
                </View>
                <View
                  className='admin-member-del'
                  onClick={() => handleDeleteVip(m.id, m.nickname || m.openid)}
                >
                  <Text className='admin-member-del-text'>移除</Text>
                </View>
              </View>
            ))}
          </View>
        )}
      </View>

      {/* 底部安全区 */}
      <View style={{ height: '60px' }} />
    </View>
  )
}
