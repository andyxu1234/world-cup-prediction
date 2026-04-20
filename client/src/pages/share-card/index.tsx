import { useEffect, useState } from 'react'
import { View, Text, Image } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { getShareCard, getShareCardImage } from '@/services/api'
import type { ShareCard } from '@/services/api'
import './index.scss'

const MODEL_COLORS: Record<string, { gradient: string; letter: string }> = {
  'DeepSeek': { gradient: 'linear-gradient(135deg, #7c3aed, #a855f7)', letter: 'D' },
  '通义千问': { gradient: 'linear-gradient(135deg, #059669, #34d399)', letter: 'Q' },
  '智谱 GLM': { gradient: 'linear-gradient(135deg, #0d9488, #2dd4bf)', letter: 'Z' },
  'Claude': { gradient: 'linear-gradient(135deg, #d97706, #fbbf24)', letter: 'C' },
  'GPT': { gradient: 'linear-gradient(135deg, #2563eb, #60a5fa)', letter: 'G' },
}

function getResultLabel(result: string) {
  if (result === 'home_win') return { text: '主胜', cls: 'pred-home' }
  if (result === 'draw') return { text: '平局', cls: 'pred-draw' }
  return { text: '客胜', cls: 'pred-away' }
}

/** 格式化时间显示 */
function formatTime(iso: string | null | undefined): string {
  if (!iso) return '待定'
  const d = new Date(iso)
  const month = d.getMonth() + 1
  const day = d.getDate()
  const hour = d.getHours().toString().padStart(2, '0')
  const min = d.getMinutes().toString().padStart(2, '0')
  return `${month}月${day}日 ${hour}:${min}`
}

const FLAG_MAP: Record<string, string> = {
  'Brazil': '🇧🇷', 'Germany': '🇩🇪', 'Argentina': '🇦🇷', 'France': '🇫🇷',
  'Mexico': '🇲🇽', 'Japan': '🇯🇵', 'England': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'USA': '🇺🇸',
  'Spain': '🇪🇸', 'Portugal': '🇵🇹', 'Italy': '🇮🇹', 'Netherlands': '🇳🇱',
}

export default function ShareCardPage() {
  const router = useRouter()
  const matchId = Number(router.params.matchId || 1)
  const [cardData, setCardData] = useState<ShareCard | null>(null)
  const [imageUrl, setImageUrl] = useState('')

  useEffect(() => {
    getShareCard(matchId).then(setCardData).catch(() => {})
    setImageUrl(getShareCardImage(matchId))
  }, [matchId])

  const handleSave = () => {
    Taro.showToast({ title: '长按图片保存', icon: 'none' })
  }

  const handleShare = () => {
    Taro.showShareMenu({ withShareTicket: true })
  }

  return (
    <View className='share-page'>
      {/* 导航 */}
      <View className='nav'>
        <View className='nav-back' onClick={() => Taro.navigateBack()}>
          <Text className='nav-back-icon'>‹</Text>
        </View>
        <Text className='nav-title'>分享预测</Text>
        <Text className='nav-save' onClick={handleSave}>保存图片</Text>
      </View>

      {/* 分享卡片预览 */}
      <View className='share-preview'>
        {/* 使用服务端生成的图片 */}
        {imageUrl && (
          <Image
            className='share-image'
            src={imageUrl}
            mode='widthFix'
          />
        )}

        {/* 如果图片加载失败，显示本地渲染的卡片 */}
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
              <Text className='share-card-meta'>{cardData.round} · {formatTime(cardData.match_time)}</Text>
            </View>
            <View className='share-card-body'>
              {cardData.predictions?.map((pred: any, idx: number) => {
                const modelInfo = MODEL_COLORS[pred.model_name] || { gradient: 'linear-gradient(135deg, #666, #999)', letter: '?' }
                const resultInfo = getResultLabel(pred.predicted_result)
                return (
                  <View key={idx} className='share-card-model'>
                    <View className='model-av share-model-av' style={{ background: modelInfo.gradient }}>
                      {modelInfo.letter}
                    </View>
                    <Text className='share-model-name'>{pred.model_name}</Text>
                    <Text className={`share-model-result ${resultInfo.cls}`}>{resultInfo.text}</Text>
                    <Text className='share-model-score mono'>{pred.predicted_home_score}:{pred.predicted_away_score}</Text>
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

      {/* 操作按钮 */}
      <View className='share-actions'>
        <View className='share-btn-primary' onClick={handleShare}>
          <Text>分享给好友</Text>
        </View>
        <View className='share-btn-row'>
          <View className='share-btn-secondary' onClick={handleSave}>
            <Text>保存图片</Text>
          </View>
          <View className='share-btn-secondary' onClick={handleShare}>
            <Text>发朋友圈</Text>
          </View>
        </View>
      </View>
    </View>
  )
}
