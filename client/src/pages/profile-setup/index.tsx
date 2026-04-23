import { useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

export default function ProfileSetup() {
  const { user, updateProfile } = useUserStore()
  const [avatarUrl, setAvatarUrl] = useState('')
  const [nickname, setNickname] = useState('')
  const [saving, setSaving] = useState(false)

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

  const handleSkip = () => {
    Taro.switchTab({ url: '/pages/index/index' })
  }

  const displayAvatar = resolveAvatarUrl(avatarUrl)
  const isReady = nickname.trim().length > 0 && !saving

  return (
    <View className='setup-page'>
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
            <Text className='badge-icon'>⚽</Text>
            <Text className='badge-text'>2026</Text>
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
              <>
                <Image className='avatar-img' src={displayAvatar} mode='aspectFill' />
                <View className='avatar-edit-overlay'>
                  <Text className='edit-icon'>✎</Text>
                </View>
              </>
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
              placeholder='你的预测代号'
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
              <Text>{isReady ? '开始预测 →' : '先填写昵称吧'}</Text>
            )}
          </View>
          <View className='skip-row' onClick={handleSkip}>
            <Text className='skip-text'>稍后再设置</Text>
            <Text className='skip-arrow'>›</Text>
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
