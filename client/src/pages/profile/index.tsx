import { useEffect, useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

const MENU_ITEMS = [
  { icon: '🏆', label: '我的战绩', color: 'rgba(0,255,135,0.1)', textColor: '#00ff87' },
  { icon: 'ℹ️', label: '关于小程序', color: 'rgba(59,130,246,0.1)', textColor: '#3b82f6' },
  { icon: '🔗', label: '分享给好友', color: 'rgba(168,85,247,0.1)', textColor: '#a855f7' },
  { icon: '⚙️', label: '设置', color: 'rgba(255,255,255,0.05)', textColor: '#8892a8' },
]

export default function Profile() {
  const { user, token, profileSetup, fetchProfile, login, updateProfile } = useUserStore()
  const [avatarUrl, setAvatarUrl] = useState('')
  const [nickname, setNickname] = useState('')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [pickingAvatar, setPickingAvatar] = useState(false)

  useEffect(() => {
    if (user?.id) {
      fetchProfile(user.id)
    }
    const savedAvatar = Taro.getStorageSync('tmp_avatar_url')
    const savedNick = Taro.getStorageSync('tmp_nickname')
    if (savedAvatar) setAvatarUrl(savedAvatar)
    if (savedNick) setNickname(savedNick)
  }, [user?.id])

  useEffect(() => {
    if (user && token && !profileSetup) {
      setEditing(true)
    }
  }, [user?.id, profileSetup])

  const handleReLogin = () => {
    Taro.login({
      success: async (res) => {
        if (res.code) {
          try {
            const loginRes = await login(res.code)
            Taro.showToast({ title: '登录成功', icon: 'success' })
            if (!loginRes.profileSetup) {
              Taro.navigateTo({ url: '/pages/profile-setup/index' })
            }
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
    const finalAvatar = avatarUrl || ''
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
      Taro.navigateTo({ url: '/pages/share-card/index' })
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
    if (!token && label !== '设置' && label !== '关于小程序') {
      Taro.showToast({ title: '请先登录', icon: 'none' })
      return
    }
  }

  const isLoggedIn = !!user && !!token
  const hasProfile = !!isLoggedIn && !!profileSetup
  const displayAvatar = resolveAvatarUrl(hasProfile ? (user!.avatar_url || '') : avatarUrl)
  const displayName = hasProfile ? (user!.nickname || '微信用户') : (nickname || '微信用户')
  const canSave = nickname.trim().length > 0

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
              <Text>{saving ? '保存中...' : canSave ? '✓ 保存' : '请填写昵称'}</Text>
            </View>

            <Text className='prof-edit-tip'>填写昵称即可保存，选择头像更佳</Text>
          </View>
        )}

        {/* 已完善资料 → 展示模式 */}
        {isLoggedIn && !editing && (
          <View className='prof-hd-center' onClick={() => setEditing(true)}>
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
        <View className='prof-stat'>
          <Text className='prof-stat-num mono'>{isLoggedIn ? (user?.total_votes ?? 0) : '-'}</Text>
          <Text className='prof-stat-label'>已投票</Text>
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
        ))}
      </View>

      <View className='fun-fact'>
        <Text className='fun-fact-title'>🎵 你知道吗？</Text>
        <Text className='fun-fact-text'>
          目前 DeepSeek 以 82.3 分领跑 AI 排行榜，但比赛才刚开始，随时可能翻盘！
        </Text>
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
