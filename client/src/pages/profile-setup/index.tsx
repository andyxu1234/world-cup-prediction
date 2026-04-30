import { useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

// 获取导航栏高度（状态栏 + 胶囊按钮区域）
function getNavHeight() {
  const sysInfo = Taro.getSystemInfoSync()
  const statusBarHeight = sysInfo.statusBarHeight || 20
  // 胶囊按钮信息（基础库 2.1.0+）
  let menuButtonTop = statusBarHeight + 4
  let menuButtonHeight = 32
  try {
    const menuBtn = Taro.getMenuButtonBoundingClientRect()
    menuButtonTop = menuBtn.top
    menuButtonHeight = menuBtn.height
  } catch {}
  return statusBarHeight + (menuButtonTop - statusBarHeight) * 2 + menuButtonHeight
}

export default function ProfileSetup() {
  const { user, updateProfile } = useUserStore()
  const [avatarUrl, setAvatarUrl] = useState('')
  const [nickname, setNickname] = useState('')
  const [saving, setSaving] = useState(false)
  const navHeight = getNavHeight()

  const handleChooseAvatar = async (e: any) => {
    const url = e.detail?.avatarUrl
    if (!url || !user?.id) return
    try {
      const res = await api.uploadAvatar(url, user.id)
      if (res.avatar_url) {
        setAvatarUrl(res.avatar_url)
      }
    } catch (err) {
      console.error('[ProfileSetup] avatar upload failed:', err)
      setAvatarUrl(url)
    }
  }

  const handleSave = async () => {
    if (!nickname.trim()) {
      Taro.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }
    const finalAvatar = avatarUrl || ''
    if (!finalAvatar) {
      Taro.showToast({ title: '请选择头像', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      await updateProfile(nickname.trim(), avatarUrl || '')
      Taro.showToast({ title: '设置成功！', icon: 'success' })
      setTimeout(() => {
        Taro.switchTab({ url: '/pages/index/index' })
      }, 500)
    } catch (err) {
      console.error('save profile error:', err)
      Taro.showToast({ title: '保存失败', icon: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const displayAvatar = resolveAvatarUrl(avatarUrl)
  // 保存条件：昵称和头像都必填
  const isReady = nickname.trim().length > 0 && avatarUrl.length > 0 && !saving

  return (
    <View className='setup-page'>
      {/* 自定义导航栏 */}
      <View className='custom-nav' style={{ height: `${navHeight}px` }}>
        <Text className='custom-nav-title'>完善资料</Text>
      </View>
      {/* ===== 背景装饰 ===== */}
      <View className='setup-bg'>
        <View className='setup-bg-circle c1' />
        <View className='setup-bg-circle c2' />
        <View className='setup-bg-circle c3' />
        {/* 足球场纹理线条 */}
        <View className='setup-field-lines'>
          <View className='field-line center-circle' />
          <View className='field-line center-line-v' />
          <View className='field-line center-line-h' />
        </View>
      </View>

      {/* ===== 主内容区 ===== */}
      <View className='setup-content'>
        {/* 顶部品牌区域 */}
        <View className='setup-hero'>
          <View className='hero-badge'>
            <Text className='badge-text'>2026</Text>
            <Text className='badge-icon'>🏆</Text>
          </View>
          <Text className='hero-title'>加入世界杯预测</Text>
          <Text className='hero-desc'>选择你的头像和昵称，开启预测之旅</Text>
        </View>

        {/* 头像选择 */}
        <View className='setup-avatar-section'>
          <View className='section-tag'>
            <Text className='tag-num'>01</Text>
            <Text className='tag-label'>头像</Text>
          </View>
          <Button
            className={`avatar-picker ${displayAvatar ? 'has-avatar' : ''}`}
            openType='chooseAvatar'
            onChooseAvatar={handleChooseAvatar}
          >
            {displayAvatar ? (
              <Image className='avatar-img' src={displayAvatar} mode='aspectFill' />
            ) : (
              <View className='avatar-empty'>
                <View className='avatar-ring'>
                  <Text className='avatar-plus'>+</Text>
                </View>
                <Text className='avatar-hint'>点击选择微信头像</Text>
              </View>
            )}
          </Button>
        </View>

        {/* 昵称输入 */}
        <View className='setup-nick-section'>
          <View className='section-tag'>
            <Text className='tag-num'>02</Text>
            <Text className='tag-label'>昵称</Text>
          </View>
          <View className='nick-input-wrap'>
            <Input
              className='nick-input'
              type='nickname'
              placeholder='你的昵称'
              value={nickname}
              onInput={(e) => setNickname(e.detail.value || '')}
              placeholderClass='nick-ph'
              maxlength={16}
              confirmType='done'
            />
            {nickname.length > 0 && (
              <View className='input-counter'>
                <Text className={`counter-text ${nickname.length > 12 ? 'warn' : ''}`}>{nickname.length}/16</Text>
              </View>
            )}
          </View>
        </View>

        {/* 操作按钮 */}
        <View className='setup-actions'>
          <View
            className={`submit-btn ${isReady ? 'active' : ''}`}
            onClick={isReady ? handleSave : undefined}
          >
            {saving ? (
              <View className='btn-loading'>
                <View className='loading-spinner' />
                <Text>提交中...</Text>
              </View>
            ) : (
              <Text>{isReady ? '开始预测 →' : (nickname.trim() ? '请选择头像' : '先填写昵称吧')}</Text>
            )}
          </View>
        </View>

        {/* 底部装饰文字 */}
        <View className='setup-footer-deco'>
          <Text className='deco-text'>WORLD CUP PREDICTION LEAGUE</Text>
        </View>
      </View>
    </View>
  )
}
