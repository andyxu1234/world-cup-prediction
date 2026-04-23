import { useState } from 'react'
import { View, Text, Input, Button, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import * as api from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

const PRESET_AVATARS = [
  { key: '⚽', label: '足球' },
  { key: '🏆', label: '奖杯' },
  { key: '🇧🇷', label: '巴西' },
  { key: '🇦🇷', label: '阿根廷' },
  { key: '🇫🇷', label: '法国' },
  { key: '🇩🇪', label: '德国' },
  { key: '🇪🇸', label: '西班牙' },
  { key: '🇬🇧', label: '英格兰' },
  { key: '🇵🇹', label: '葡萄牙' },
  { key: '🇳🇱', label: '荷兰' },
  { key: '🇮🇹', label: '意大利' },
  { key: '🇯🇵', label: '日本' },
]

export default function ProfileSetup() {
  const { user, updateProfile } = useUserStore()
  const [avatarKey, setAvatarKey] = useState('')
  const [wechatAvatar, setWechatAvatar] = useState('')
  const [nickname, setNickname] = useState('')
  const [saving, setSaving] = useState(false)

  const handleChooseAvatar = async (e: any) => {
    const url = e.detail?.avatarUrl
    if (!url || !user?.id) return
    try {
      const res = await api.uploadAvatar(url, user.id)
      if (res.avatar_url) {
        setWechatAvatar(res.avatar_url)
        setAvatarKey('')
      }
    } catch (err) {
      console.error('[ProfileSetup] avatar upload failed:', err)
    }
  }

  const handleChooseAvatarError = () => {
    console.warn('[ProfileSetup] chooseAvatar not supported')
  }

  const handlePresetAvatar = (key: string) => {
    setAvatarKey(key)
    setWechatAvatar('')
  }

  const handleSave = async () => {
    if (!nickname.trim()) {
      Taro.showToast({ title: '请填写昵称', icon: 'none' })
      return
    }
    setSaving(true)
    try {
      // 头像：优先微信头像，其次预设头像编码
      const finalAvatar = wechatAvatar || (avatarKey ? `preset://${avatarKey}` : '')
      await updateProfile(nickname.trim(), finalAvatar)
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

  // 当前显示的头像
  const displayAvatar = resolveAvatarUrl(wechatAvatar)

  return (
    <View className='setup-page'>
      <View className='setup-header'>
        <Text className='setup-title'>欢迎来到世界杯预测！</Text>
        <Text className='setup-subtitle'>设置你的昵称和头像，让大家认识你</Text>
      </View>

      {/* ====== 头像选择 ====== */}
      <View className='setup-section'>
        <Text className='setup-label'>选择头像</Text>

        {/* 微信头像选择 */}
        <View className='setup-wechat-avatar'>
          <Button
            className='setup-avatar-btn'
            openType='chooseAvatar'
            onChooseAvatar={handleChooseAvatar}
            onError={handleChooseAvatarError}
          >
            {displayAvatar ? (
              <Image className='setup-avatar-img' src={displayAvatar} mode='aspectFill' />
            ) : (
              <View className='setup-avatar-placeholder'>
                <Text className='setup-avatar-icon'>📷</Text>
                <Text className='setup-avatar-text'>微信头像</Text>
              </View>
            )}
          </Button>
        </View>

        <Text className='setup-or'>或选择一个球队头像</Text>

        {/* 预设头像列表 */}
        <View className='setup-presets'>
          {PRESET_AVATARS.map((item) => (
            <View
              key={item.key}
              className={`setup-preset-item ${avatarKey === item.key ? 'active' : ''}`}
              onClick={() => handlePresetAvatar(item.key)}
            >
              <Text className='setup-preset-emoji'>{item.key}</Text>
              <Text className='setup-preset-label'>{item.label}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* ====== 昵称输入 ====== */}
      <View className='setup-section'>
        <Text className='setup-label'>你的昵称</Text>
        <Input
          className='setup-nick-input'
          type='nickname'
          placeholder='点击获取微信昵称，或自行输入'
          value={nickname}
          onInput={(e) => setNickname(e.detail.value || '')}
          placeholderClass='setup-nick-ph'
        />
      </View>

      {/* ====== 操作按钮 ====== */}
      <View className='setup-actions'>
        <View
          className={`setup-save-btn ${nickname.trim() && !saving ? 'ready' : ''}`}
          onClick={nickname.trim() && !saving ? handleSave : undefined}
        >
          <Text>{saving ? '保存中...' : nickname.trim() ? '开始预测' : '请填写昵称'}</Text>
        </View>
        <Text className='setup-skip' onClick={handleSkip}>稍后再说</Text>
      </View>
    </View>
  )
}
