import { useEffect, useState, useRef } from 'react'
import { View, Text, Image } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage } from '@tarojs/taro'
import {
  getShareCard, getShareCardImage,
  getInviteCardImageUrl
} from '@/services/api'
import type { ShareCard } from '@/services/api'
import { useUserStore } from '@/stores'
import { resolveAvatarUrl } from '@/services/api'
import './index.scss'

const MODEL_COLORS: Record<string, { gradient: string; letter: string }> = {
  'DeepSeek': { gradient: 'linear-gradient(135deg, #7c3aed, #a855f7)', letter: 'D' },
  '通义千问': { gradient: 'linear-gradient(135deg, #059669, #34d399)', letter: 'Q' },
  '智谱 GLM': { gradient: 'linear-gradient(135deg, #0d9488, #2dd4bf)', letter: 'Z' },
  'Claude': { gradient: 'linear-gradient(135deg, #d97706, #fbbf24)', letter: 'C' },
  'GPT': { gradient: 'linear-gradient(135deg, #2563eb, #60a5fa)', letter: 'G' },
}

const ROUND_CN_MAP: Record<string, string> = {
  'Group Stage - 1': '小组赛第1轮',
  'Group Stage - 2': '小组赛第2轮',
  'Group Stage - 3': '小组赛第3轮',
  'Round of 32': '三十二强赛',
  'Round of 16': '十六强赛',
  'Quarter-finals': '四分之一决赛',
  'Semi-finals': '半决赛',
  '3rd Place Final': '季军赛',
  'Final': '决赛',
}

function getRoundLabel(round: string): string {
  return ROUND_CN_MAP[round] || round
}

function getResultLabel(result: string) {
  const key = result.replace('PredictionResult.', '')
  if (key === 'home_win') return { text: '主胜', cls: 'pred-home' }
  if (key === 'draw') return { text: '平局', cls: 'pred-draw' }
  return { text: '客胜', cls: 'pred-away' }
}

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '待定'
  const d = new Date(iso)
  const month = d.getMonth() + 1
  const day = d.getDate()
  const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
  const weekday = weekDays[d.getDay()]
  const hour24 = d.getHours()
  const min = d.getMinutes().toString().padStart(2, '0')
  const period = hour24 < 6 ? '凌晨' : hour24 < 12 ? '上午' : hour24 < 14 ? '中午' : hour24 < 18 ? '下午' : '晚上'
  const hour12 = hour24 === 0 ? 12 : hour24 > 12 ? hour24 - 12 : hour24
  return `${month}月${day}日 ${weekday} ${period}${hour12.toString().padStart(2, '0')}:${min}`
}

const FLAG_MAP: Record<string, string> = {
  'Brazil': '🇧🇷', 'Germany': '🇩🇪', 'Argentina': '🇦🇷', 'France': '🇫🇷',
  'Mexico': '🇲🇽', 'Japan': '🇯🇵', 'England': '🏴', 'USA': '🇺🇸',
  'Spain': '🇪🇸', 'Portugal': '🇵🇹', 'Italy': '🇮🇹', 'Netherlands': '🇳🇱',
}

// AI 排行默认数据（前端兜底）
const DEFAULT_AI_RANKING = [
  { name: 'DeepSeek', result_accuracy: 82.3 },
  { name: 'GPT-4o', result_accuracy: 78.1 },
  { name: 'Claude', result_accuracy: 75.6 },
]

type ShareMode = 'match' | 'invite'

export default function ShareCardPage() {
  const router = useRouter()
  const mode = (router.params.mode || 'match') as ShareMode
  const matchId = Number(router.params.matchId || 0)
  const userStore = useUserStore()

  // --- match 模式状态 ---
  const [cardData, setCardData] = useState<ShareCard | null>(null)
  const [imageUrl, setImageUrl] = useState('')

  // --- invite 模式状态 ---
  const [inviteImageUrl, setInviteImageUrl] = useState('')
  const [nickname, setNickname] = useState('预言家')
  const [avatarDisplay, setAvatarDisplay] = useState('')

  // 长按定时器（绕开 Taro onLongPress 编译问题）
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const longPressImgUrl = useRef<string>('')

  /** 手动长按检测：touchstart 开始计时 */
  const handleTouchStart = (imgUrl: string) => {
    longPressImgUrl.current = imgUrl
    longPressTimer.current = setTimeout(() => {
      handleLongPressSave(imgUrl)
    }, 500)
  }

  /** touchend / touchcancel 取消计时 */
  const handleTouchEnd = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current)
      longPressTimer.current = null
    }
  }

  useEffect(() => {
    if (mode === 'match' && matchId > 0) {
      getShareCard(matchId).then(setCardData).catch(() => {})
      setImageUrl(getShareCardImage(matchId))
      return
    }

    if (mode === 'invite') {
      const u = userStore.user
      const nick = u?.nickname || '预言家'
      setNickname(nick)
      setAvatarDisplay(resolveAvatarUrl(u?.avatar_url || ''))

      const url = getInviteCardImageUrl({
        nickname: nick,
        avatarUrl: resolveAvatarUrl(u?.avatar_url || ''),
        totalVotes: u?.total_votes ?? 0,
        correctResults: u?.correct_results ?? 0,
        correctScores: u?.correct_scores ?? 0,
      })
      setInviteImageUrl(url)
    }
  }, [mode, matchId])

  const currentImageUrl = mode === 'invite' ? inviteImageUrl : imageUrl

  // 微信分享注册
  useShareAppMessage(() => ({
    title: mode === 'invite'
      ? `${nickname} 邀你挑战 AI 世界杯预测！`
      : cardData
        ? `${cardData.home_team} vs ${cardData.away_team} · AI 预测对战卡`
        : 'AI 预测世界杯',
    path: '/pages/index/index',
    imageUrl: currentImageUrl,
  }))

  const handleSaveImage = () => {
    Taro.showToast({ title: '长按图片保存到相册', icon: 'none' })
  }

  const handleShareFriend = () => {
    Taro.showToast({ title: '请点击右上角「...」分享给好友', icon: 'none' })
  }

  const handleCopyLink = () => {
    Taro.setClipboardData({
      data: '快来参加 AI 预测世界杯，和 DeepSeek、GPT 一决高下！',
      success: () => Taro.showToast({ title: '已复制邀请文案', icon: 'success' }),
    })
  }

  /** 长按图片 → 保存到相册 / 转发好友 / 分享小程序 */
  const handleLongPressSave = (imgUrl: string) => {
    Taro.showActionSheet({
      itemList: ['保存图片到相册', '转发给微信好友', '分享小程序'],
      success: (res) => {
        // res.tapIndex 返回用户点击的按钮索引，从 0 开始
        if (res.tapIndex === 0) {
          // 保存图片到相册
          Taro.showLoading({ title: '保存中...' })
          Taro.downloadFile({
            url: imgUrl,
            success: (downloadRes) => {
              if (downloadRes.statusCode === 200) {
                Taro.saveImageToPhotosAlbum({
                  filePath: downloadRes.tempFilePath,
                  success: () => {
                    Taro.hideLoading()
                    Taro.showToast({ title: '已保存到相册', icon: 'success' })
                  },
                  fail: () => {
                    Taro.hideLoading()
                    Taro.showToast({ title: '保存失败，请重试', icon: 'none' })
                  },
                })
              } else {
                Taro.hideLoading()
                Taro.showToast({ title: '下载失败', icon: 'none' })
              }
            },
            fail: () => {
              Taro.hideLoading()
              Taro.showToast({ title: '下载失败', icon: 'none' })
            },
          })
        } else if (res.tapIndex === 1) {
          // 转发给微信好友
          Taro.showToast({ 
            title: '请点击右上角「...」转发', 
            icon: 'none',
            duration: 2000
          })
        } else if (res.tapIndex === 2) {
          // 分享小程序
          Taro.showToast({ 
            title: '请点击右上角「...」分享', 
            icon: 'none',
            duration: 2000
          })
        }
      },
      fail: (err) => {
        // 用户取消操作（正常行为，不提示）
        if (!err?.errMsg?.includes('cancel')) {
          console.error('showActionSheet fail:', err)
        }
      },
    })
  }

  /** 直接转发给微信好友 */
  const handleForwardToFriend = () => {
    Taro.showActionSheet({
      itemList: ['转发给微信好友', '分享小程序'],
      success: (res) => {
        if (res.tapIndex === 0) {
          Taro.showToast({ 
            title: '请点击右上角「...」转发', 
            icon: 'none',
            duration: 2000
          })
        } else if (res.tapIndex === 1) {
          Taro.showToast({ 
            title: '请点击右上角「...」分享', 
            icon: 'none',
            duration: 2000
          })
        }
      },
    })
  }

  return (
    <View className='share-page'>
      {/* 导航栏 */}
      <View className='nav'>
        <View className='nav-back' onClick={() => Taro.navigateBack()}>
          <Text className='nav-back-icon'>‹</Text>
        </View>
        <Text className='nav-title'>
          {mode === 'invite' ? '邀请好友' : '分享预测'}
        </Text>
        <Text className='nav-save' onClick={handleSaveImage}>保存图片</Text>
      </View>

      {/* ======== 邀请模式 UI ======== */}
      {mode === 'invite' && (
        <>
          {/* 卡片预览 */}
          <View className='share-preview invite-preview'>
            {inviteImageUrl && (
              <View
                className='share-image-wrapper share-bg-image'
                style={{ backgroundImage: `url(${inviteImageUrl})` }}
                onTouchStart={() => handleTouchStart(inviteImageUrl)}
                onTouchEnd={handleTouchEnd}
                onTouchCancel={handleTouchEnd}
              />
            )}
            {!inviteImageUrl && (
              <View className='invite-fallback'>
                <View className='invite-brand'>🏆</View>
                <Text className='invite-brand-text'>AI 预测世界杯</Text>
                <View className='invite-avatar-area'>
                  {avatarDisplay ? (
                    <Image className='invite-av-img' src={avatarDisplay} mode='aspectFill' />
                  ) : (
                    <View className='invite-av-placeholder'><Text>?</Text></View>
                  )}
                </View>
                <Text className='invite-name'>{nickname}</Text>
                <Text className='invite-tagline'>邀你挑战 AI 预测！</Text>

                <View className='invite-stats-row'>
                  <View className='invite-stat-item'>
                    <Text className='invite-stat-num'>{userStore.user?.total_votes ?? 0}</Text>
                    <Text className='invite-stat-label'>已投票</Text>
                  </View>
                  <View className='invite-stat-item'>
                    <Text className='invite-stat-num'>{userStore.user?.correct_results ?? 0}</Text>
                    <Text className='invite-stat-label'>胜负正确</Text>
                  </View>
                  <View className='invite-stat-item'>
                    <Text className='invite-stat-num'>{userStore.user?.correct_scores ?? 0}</Text>
                    <Text className='invite-stat-label'>比分命中</Text>
                  </View>
                </View>

                <View className='invite-ai-rank'>
                  <Text className='invite-ai-title'>🤖 AI 先知排行榜 TOP3</Text>
                  {DEFAULT_AI_RANKING.map((ai, i) => (
                    <View key={i} className='invite-ai-row'>
                      <View className={`invite-ai-rank-badge ${i === 0 ? 'gold' : i === 1 ? 'silver' : 'bronze'}`}>
                        <Text>{i + 1}</Text>
                      </View>
                      <Text className='invite-ai-name'>{ai.name}</Text>
                      <Text className='invite-ai-score'>{ai.result_accuracy}%</Text>
                    </View>
                  ))}
                </View>

                <View className='invite-cta-btn'>
                  <Text className='invite-cta-text'>你的预言能打败 AI ？</Text>
                  <Text className='invite-cta-sub'>立即加入挑战 →</Text>
                </View>
              </View>
            )}
          </View>

          {/* 操作按钮 */}
          <View className='share-actions'>
            <View className='share-btn-primary' onClick={handleForwardToFriend}>
              <Text>转发给好友 / 分享</Text>
            </View>
            <View className='share-btn-row'>
              <View className='share-btn-secondary' onClick={() => handleLongPressSave(inviteImageUrl)}>
                <Text>长按保存图片</Text>
              </View>
              <View className='share-btn-secondary' onClick={handleCopyLink}>
                <Text>复制文案</Text>
              </View>
            </View>
          </View>
        </>
      )}

      {/* ======== 比赛对战模式 UI ======== */}
      {mode === 'match' && (
        <>
          <View className='share-preview'>
            {imageUrl && (
              <View
                className='share-image-wrapper share-bg-image'
                style={{ backgroundImage: `url(${imageUrl})` }}
                onTouchStart={() => handleTouchStart(imageUrl)}
                onTouchEnd={handleTouchEnd}
                onTouchCancel={handleTouchEnd}
              />
            )}
            {!imageUrl && cardData && (
              <View className='share-card'>
                <View className='share-card-top'>
                  <Text className='share-card-logo'>AI PREDICTOR · 2026 WORLD CUP</Text>
                  <View className='share-card-match'>
                    <View className='share-card-team'>
                      <View className='flag'>{FLAG_MAP[cardData.home_team] || '⚽'}</View>
                      <Text className='share-card-team-name'>{cardData.home_team}</Text>
                    </View>
                    <Text className='share-card-vs mono'>VS</Text>
                    <View className='share-card-team'>
                      <View className='flag'>{FLAG_MAP[cardData.away_team] || '⚽'}</View>
                      <Text className='share-card-team-name'>{cardData.away_team}</Text>
                    </View>
                  </View>
                  <Text className='share-card-meta'>{getRoundLabel(cardData.round)} · {formatTime(cardData.match_time)}</Text>
                </View>
                <View className='share-card-body'>
                  {cardData.predictions?.map((pred: any, idx: number) => {
                    const modelInfo = MODEL_COLORS[pred.model_name] || { gradient: 'linear-gradient(135deg, #666, #999)', letter: '?' }
                    const resultInfo = getResultLabel(pred.result)
                    return (
                      <View key={idx} className='share-card-model'>
                        <View className='model-av share-model-av' style={{ background: modelInfo.gradient }}>
                          {modelInfo.letter}
                        </View>
                        <Text className='share-model-name'>{pred.model_name}</Text>
                        <Text className={`share-model-result ${resultInfo.cls}`}>{resultInfo.text}</Text>
                        <Text className='share-model-score mono'>{pred.score_home}:{pred.score_away}</Text>
                      </View>
                    )
                  })}
                </View>
                <View className='share-card-btm'>
                  <View className='share-card-slogan'>
                    <Text className='slogan-bold'>AI 预测世界杯</Text>
                    <Text className='slogan-sub'>谁才是最强预言家？</Text>
                  </View>
                  <View className='share-card-qr'>
                    <Text className='qr-text'>小程序码</Text>
                  </View>
                </View>
              </View>
            )}
          </View>

          <View className='share-actions'>
            <View className='share-btn-primary' onClick={handleForwardToFriend}>
              <Text>转发给好友 / 分享</Text>
            </View>
            <View className='share-btn-row'>
              <View className='share-btn-secondary' onClick={() => handleLongPressSave(imageUrl)}>
                <Text>长按保存图片</Text>
              </View>
              <View className='share-btn-secondary' onClick={handleSaveImage}>
                <Text>发朋友圈</Text>
              </View>
            </View>
          </View>
        </>
      )}
    </View>
  )
}
