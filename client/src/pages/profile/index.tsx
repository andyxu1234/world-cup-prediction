import { useEffect, useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline, useDidShow } from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

const MENU_ITEMS = [
  { icon: '🏆', label: '我的战绩', color: 'rgba(0,255,135,0.1)', textColor: '#00ff87' },
  { icon: '🔗', label: '分享给好友', color: 'rgba(168,85,247,0.1)', textColor: '#a855f7' },
  { icon: 'ℹ️', label: '关于小程序', color: 'rgba(59,130,246,0.1)', textColor: '#3b82f6' },
  { icon: '💬', label: '联系作者', color: 'rgba(16,185,129,0.1)', textColor: '#10b981' },
  { icon: '⚠️', label: '免责声明', color: 'rgba(251,191,36,0.1)', textColor: '#fbbf24' },
]

const DEFAULT_AI_RANKING = [
  { name: 'DeepSeek', result_accuracy: 82.3 },
  { name: 'GPT-4o', result_accuracy: 78.1 },
  { name: 'Claude', result_accuracy: 75.6 },
]

/** 调用 DeepSeek 动态生成趣闻（全局共享，不区分用户） */
async function fetchFunFactFromAPI(): Promise<api.FunFact> {
  try {
    return await api.getFunFact()
  } catch {
    return { icon: '⚽', title: '足球小知识', text: '精彩内容正在生成中，稍后再来试试吧~' }
  }
}

export default function Profile() {
  const { user, token, profileSetup, fetchProfile, login, updateProfile } = useUserStore()
  const [avatarUrl, setAvatarUrl] = useState('')
  const [nickname, setNickname] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [pickingAvatar, setPickingAvatar] = useState(false)
  const [funFact, setFunFact] = useState<api.FunFact>({ icon: '🎵', title: '你知道吗？', text: '' })

  // 分享给好友成功回调
  const handleShared = () => Taro.showToast({ title: '已分享', icon: 'success' })

  // 微信分享配置（点击"分享给好友"或右上角转发时使用）
  useShareAppMessage(() => {
    const count = user?.total_votes ?? 0
    return {
      title: `我在AI预测世界杯完成了${count}场预测，快来和我一起参与吧`,
      path: '/pages/index/index',
    }
  })

  // 分享到朋友圈
  useShareTimeline(() => {
    const count = user?.total_votes ?? 0
    return {
      title: `我在AI预测世界杯完成了${count}场预测，快来和我一起参与吧`,
      query: '',
    }
  })

  useEffect(() => {
    if (user?.id) {
      fetchProfile(user.id)
    }
    const savedAvatar = Taro.getStorageSync('tmp_avatar_url')
    const savedNick = Taro.getStorageSync('tmp_nickname')
    if (savedAvatar) setAvatarUrl(savedAvatar)
    if (savedNick) setNickname(savedNick)
  }, [user?.id])

  // 切回 Tab 时刷新用户数据（已预测数等）
  useDidShow(() => {
    if (user?.id) {
      fetchProfile(user.id)
    }
  })

  // 不强制进入编辑模式，用户可通过点击头像手动编辑

  // 动态趣闻：全局共享，进入页面时获取一次
  useEffect(() => {
    fetchFunFactFromAPI().then(f => setFunFact(f))
  }, [])

  const handleReLogin = () => {
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            await login(res.code)
            Taro.showToast({ title: '登录成功', icon: 'success' })
          } catch {
            Taro.showToast({ title: '登录失败，请重试', icon: 'none' })
          }
        }
      },
    })
  }

  const handleChooseAvatar = async (e: any) => {
    const url = e.detail?.avatarUrl
    if (!url || !user?.id) return
    try {
      const res = await api.uploadAvatar(url, user.id)
      if (res.avatar_url) {
        setAvatarUrl(res.avatar_url)
        Taro.setStorageSync('tmp_avatar_url', res.avatar_url)
      }
    } catch (err) {
      console.error('[Profile] avatar upload failed:', err)
      setAvatarUrl(url)
      Taro.setStorageSync('tmp_avatar_url', url)
    } finally {
      setPickingAvatar(false)
    }
  }

  const handleChooseAvatarError = () => {
    console.warn('[chooseAvatar] 模拟器可能不支持头像选择，真机正常')
    setPickingAvatar(false)
  }

  const handleNicknameBlur = (e: any) => {
    const val = e.detail.value || ''
    setNickname(val)
    Taro.setStorageSync('tmp_nickname', val)
  }

  const handleNicknameInput = (e: any) => {
    setNickname(e.detail.value || '')
  }

  const handleSaveProfile = async () => {
    if (!nickname.trim()) {
      Taro.showToast({ title: '请先填写昵称', icon: 'none' })
      return
    }
    const finalAvatar = avatarUrl || (user?.avatar_url || '')
    if (!finalAvatar) {
      Taro.showToast({ title: '请先选择头像', icon: 'none' })
      return
    }
    const uid = user!.id
    setSaving(true)
    try {
      await updateProfile(nickname.trim(), finalAvatar)
      Taro.removeStorageSync('tmp_avatar_url')
      Taro.removeStorageSync('tmp_nickname')
      setAvatarUrl('')
      setEditing(false)
      Taro.showToast({ title: '保存成功！', icon: 'success' })
      fetchProfile(uid)
    } catch (err) {
      console.error('save profile error:', err)
      Taro.showToast({ title: '保存失败，请重试', icon: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const handleMenuClick = (label: string) => {
    if (label === '分享给好友') {
      // 由 Button openType='share' 直接处理
      return
    }
    if (label === '我的战绩') {
      Taro.navigateTo({ url: '/pages/vote-history/index' })
      return
    }
    if (label === '关于小程序') {
      Taro.navigateTo({ url: '/pages/about/index' })
      return
    }
    if (label === '联系作者') {
      Taro.navigateTo({ url: '/pages/contact/index' })
      return
    }
    if (label === '免责声明') {
      Taro.navigateTo({ url: '/pages/disclaimer/index' })
      return
    }
    if (!token && label !== '设置' && label !== '关于小程序') {
      Taro.showToast({ title: '请先登录', icon: 'none' })
      return
    }
  }

  const isLoggedIn = !!user && !!token
  // 始终优先使用服务端返回的用户数据，不依赖 profileSetup 标志判断是否展示
  const displayAvatar = editing
    ? resolveAvatarUrl(avatarUrl || (user?.avatar_url || ''))
    : resolveAvatarUrl(user?.avatar_url || '')
  const displayName = user?.nickname || nickname || '微信用户'
  // 保存条件：昵称不为空 且 有头像（新选的 或 已有的均可）
  const hasAvatar = avatarUrl.length > 0 || (user?.avatar_url?.length > 0)
  const canSave = nickname.trim().length > 0 && hasAvatar

  return (
    <View className='profile-page'>
      <View className='prof-hd'>
        {/* 未登录 */}
        {!isLoggedIn && (
          <View className='prof-hd-center' onClick={handleReLogin}>
            <View className='prof-av'>
              <Text className='prof-av-icon'>👤</Text>
            </View>
            <Text className='prof-name'>点击登录</Text>
            <Text className='prof-tip'>授权微信登录以使用全部功能</Text>
          </View>
        )}

        {/* 编辑资料中 */}
        {isLoggedIn && editing && (
          <View className='prof-hd-center'>
            <Button
              className='prof-avatar-picker'
              openType='chooseAvatar'
              onChooseAvatar={handleChooseAvatar}
              onError={handleChooseAvatarError}
              onTap={() => setPickingAvatar(true)}
            >
              {displayAvatar ? (
                <Image className='prof-avatar-img' src={displayAvatar} mode='aspectFill' />
              ) : (
                <>
                  <Text className='prof-avatar-placeholder'>+</Text>
                  <Text className='prof-avatar-label'>选择头像</Text>
                </>
              )}
            </Button>

            <Input
              className='prof-nick-input'
              type='nickname'
              placeholder='请输入你的昵称'
              value={nickname}
              onInput={handleNicknameInput}
              onBlur={handleNicknameBlur}
              placeholderClass='prof-nick-ph'
            />

            <View
              className={`prof-save-btn ${canSave && !saving ? 'ready' : ''}`}
              onClick={canSave && !saving ? handleSaveProfile : undefined}
            >
              <Text>{saving ? '保存中...' : '保存'}</Text>
            </View>

            {!canSave && (
              <Text className='prof-edit-tip'>{hasAvatar ? '请填写昵称' : '请选择头像并填写昵称'}</Text>
            )}
          </View>
        )}

        {/* 已完善资料 → 展示模式 */}
        {isLoggedIn && !editing && (
          <View className='prof-hd-center' onClick={() => {
            setNickname(user?.nickname || '')
            setAvatarUrl('')
            setEditing(true)
          }}>
            <View className='prof-av prof-av-clickable'>
              {displayAvatar ? (
                <Image className='prof-avatar-img' src={displayAvatar} mode='aspectFill' />
              ) : (
                <Text className='prof-av-icon'>👤</Text>
              )}
            </View>
            <Text className='prof-name'>{displayName}</Text>
            <Text className='prof-tip'>点击修改资料</Text>
          </View>
        )}
      </View>

      <View className='prof-stats'>
        <View className='prof-stat prof-stat-clickable' onClick={() => Taro.navigateTo({ url: '/pages/vote-history/index' })}>
          <Text className='prof-stat-num mono'>{isLoggedIn ? (user?.total_votes ?? 0) : '-'}</Text>
          <Text className='prof-stat-label'>已预测</Text>
        </View>
        <View className='prof-stat-divider' />
        <View className='prof-stat'>
          <Text className='prof-stat-num mono'>{isLoggedIn ? (user?.correct_results ?? 0) : '-'}</Text>
          <Text className='prof-stat-label'>胜负正确</Text>
        </View>
        <View className='prof-stat-divider' />
        <View className='prof-stat'>
          <Text className='prof-stat-num mono'>{isLoggedIn ? (user?.correct_scores ?? 0) : '-'}</Text>
          <Text className='prof-stat-label'>比分命中</Text>
        </View>
      </View>

      <View className='prof-menu'>
        {MENU_ITEMS.map((item) => (
          item.label === '分享给好友' ? (
            <Button
              key={item.label}
              className='prof-menu-item'
              openType='share'
              onShareAppMessageSuccess={handleShared}
            >
              <View className='prof-menu-left'>
                <View className='prof-menu-icon' style={{ background: item.color, color: item.textColor }}>
                  <Text>{item.icon}</Text>
                </View>
                <Text className='prof-menu-text'>{item.label}</Text>
              </View>
              <Text className='prof-menu-arrow'>›</Text>
            </Button>
          ) : (
          <View
            key={item.label}
            className='prof-menu-item'
            onClick={() => handleMenuClick(item.label)}
          >
            <View className='prof-menu-left'>
              <View className='prof-menu-icon' style={{ background: item.color, color: item.textColor }}>
                <Text>{item.icon}</Text>
              </View>
              <Text className='prof-menu-text'>{item.label}</Text>
            </View>
            <Text className='prof-menu-arrow'>›</Text>
          </View>
          )
        ))}
      </View>

      <View className='fun-fact'>
        <View className='fun-fact-header'>
          <Text className='fun-fact-title'>{funFact.icon} {funFact.title}</Text>
        </View>
        <Text className='fun-fact-text'>{funFact.text}</Text>
      </View>


      {pickingAvatar && (
        <View
          className='avatar-picker-mask'
          onClick={() => setPickingAvatar(false)}
        />
      )}
    </View>
  )
}
