import { useEffect, useState } from 'react'
import { View, Text, Image, ScrollView } from '@tarojs/components'
import Taro, { useRouter } from '@tarojs/taro'
import { getAIDetail, AIDetailPrediction, AIDetailOut } from '@/services/api'
import { resolveAvatarUrl } from '@/services/api'
import deepseekImg from '@/assets/aimodels/deepseek.svg'
import qwenImg from '@/assets/aimodels/qwen.svg'
import claudeImg from '@/assets/aimodels/claude.svg'
import openaiImg from '@/assets/aimodels/openai.svg'
import geminiImg from '@/assets/aimodels/gemini.svg'
import glmImg from '@/assets/aimodels/glm.svg'
import doubaoImg from '@/assets/aimodels/doubao.svg'
import kimiImg from '@/assets/aimodels/kimi.svg'
import minimaxImg from '@/assets/aimodels/minimax.svg'
import grokImg from '@/assets/aimodels/grok.svg'
import hunyuanImg from '@/assets/aimodels/hunyuan.svg'
import xiaomimimoImg from '@/assets/aimodels/xiaomimimo.svg'
import './index.scss'

const MODEL_AVATARS: Record<string, string> = {
  'DeepSeek': deepseekImg,
  '通义千问': qwenImg,
  'Claude': claudeImg,
  'GPT': openaiImg,
  'Gemini': geminiImg,
  '智谱 GLM': glmImg,
  '豆包': doubaoImg,
  'Kimi': kimiImg,
  'MiniMax': minimaxImg,
  'Grok': grokImg,
  '混元': hunyuanImg,
  '小米 mimo': xiaomimimoImg,
}

const MODEL_FALLBACKS: Record<string, { gradient: string; letter: string }> = {
  '智谱GLM': { gradient: 'linear-gradient(135deg, #0d9488, #2dd4bf)', letter: 'Z' },
}

function ModelAvatar({ name, size = '' }: { name: string; size?: string }) {
  const url = MODEL_AVATARS[name]
  if (url) {
    return <Image className={`model-av-img ${size}`} src={url} mode='aspectFit' />
  }
  const fb = MODEL_FALLBACKS[name] || { gradient: 'linear-gradient(135deg, #666, #999)', letter: '?' }
  return <View className={`model-av ${size}`} style={{ background: fb.gradient }}>{fb.letter}</View>
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

function getResultLabel(result: string): string {
  // 处理枚举值（如 PredictionResult.home_win）和短值（home_win）
  const key = result.replace('PredictionResult.', '')
  const map: Record<string, string> = {
    home_win: '主胜',
    away_win: '客胜',
    draw: '平局',
  }
  return map[key] ?? key
}

function getStatusBadge(item: AIDetailPrediction) {
  if (item.match_status !== 'finished') {
    return { className: 'tag-pending', text: '未结束' }
  }
  if (item.is_correct_score) {
    return { className: 'tag-score', text: '比分命中' }
  }
  if (item.is_correct_result) {
    return { className: 'tag-result', text: '胜负正确' }
  }
  return { className: 'tag-wrong', text: '预测失误' }
}

function formatTime(iso: string | null): string {
  if (!iso) return '--'
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

export default function AIDetail() {
  const router = useRouter()
  const modelId = Number(router.params.modelId || 0)

  const [detail, setDetail] = useState<AIDetailOut | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!modelId) return
    setLoading(true)
    getAIDetail(modelId)
      .then(setDetail)
      .catch(() => Taro.showToast({ title: '加载失败', icon: 'none' }))
      .finally(() => setLoading(false))
  }, [modelId])

  if (!modelId) {
    return (
      <View className='ai-detail-page'>
        <View className='ad-empty'><Text>参数错误</Text></View>
      </View>
    )
  }

  if (loading) {
    return (
      <View className='ai-detail-page'>
        <View className='ad-loading'><Text>加载中...</Text></View>
      </View>
    )
  }

  if (!detail) {
    return (
      <View className='ai-detail-page'>
        <View className='ad-empty'>
          <Text className='ad-empty-icon'>🤖</Text>
          <Text className='ad-empty-text'>暂无该 AI 模型的数据</Text>
        </View>
      </View>
    )
  }

  const predictions = detail.predictions || []

  return (
    <View className='ai-detail-page'>
      {/* Hero 区域 */}
      <View className='ad-hero'>
        <View className='ad-hero-glow' />
        <View className='ad-hero-model'>
          <ModelAvatar name={detail.name} size='ad-av' />
          <View className='ad-hero-info'>
            <Text className='ad-hero-name'>{detail.name}</Text>
            <Text className='ad-hero-sub'>AI 预测详情 · 数据追踪</Text>
          </View>
        </View>
        <View className='ad-hero-stats'>
          <View className='ad-hero-stat'>
            <Text className='ad-hero-stat-num'>{detail.total_predictions}</Text>
            <Text className='ad-hero-stat-label'>预测场次</Text>
          </View>
          <View className='ad-hero-stat'>
            <Text className='ad-hero-stat-num'>{detail.result_accuracy}%</Text>
            <Text className='ad-hero-stat-label'>胜负命中率</Text>
          </View>
          <View className='ad-hero-stat'>
            <Text className='ad-hero-stat-num'>{detail.score_accuracy}%</Text>
            <Text className='ad-hero-stat-label'>比分命中率</Text>
          </View>
        </View>
      </View>

      {/* 预测列表 */}
      <ScrollView scrollY className='ad-list' enableBackToTop>
        {predictions.length === 0 ? (
          <View className='ad-empty'>
            <View className='ad-empty-icon'>📋</View>
            <Text className='ad-empty-text'>该模型还没有预测记录</Text>
          </View>
        ) : (
          predictions.map((item) => {
            const badge = getStatusBadge(item)
            return (
              <View key={item.prediction_id} className='ad-card'>
                <View className='ad-card-hd'>
                  <Text className='ad-round'>{getRoundLabel(item.round)}</Text>
                  <View className='ad-badges'>
                    <Text className={`ad-badge ${badge.className}`}>{badge.text}</Text>
                  </View>
                </View>
                <View className='ad-card-bd'>
                  <View className='ad-teams'>
                    <View className='ad-team'>
                      {item.home_team_flag ? (
                        <Image className='ad-team-flag' src={item.home_team_flag} mode='aspectFill' />
                      ) : (
                        <View className='ad-flag-fb'>⚽</View>
                      )}
                      <Text className='ad-team-name'>{item.home_team_name}</Text>
                    </View>

                    <View className='ad-score-area'>
                      {item.match_home_score !== null ? (
                        <>
                          <Text className='ad-score mono'>{item.match_home_score} - {item.match_away_score}</Text>
                          <Text className='ad-score-label'>赛果</Text>
                        </>
                      ) : (
                        <>
                          <Text className='ad-vs mono'>VS</Text>
                          <Text className='ad-status-label'>
                            {item.match_status === 'live' ? '进行中' : '未开始'}
                          </Text>
                        </>
                      )}
                    </View>

                    <View className='ad-team'>
                      {item.away_team_flag ? (
                        <Image className='ad-team-flag' src={item.away_team_flag} mode='aspectFill' />
                      ) : (
                        <View className='ad-flag-fb'>⚽</View>
                      )}
                      <Text className='ad-team-name'>{item.away_team_name}</Text>
                    </View>
                  </View>
                </View>
                <View className='ad-card-ft'>
                  <Text className='ad-prediction'>
                    预测：{getResultLabel(item.predicted_result)}
                    {item.predicted_home_score != null
                      ? ` ${item.predicted_home_score}-${item.predicted_away_score}`
                      : ''}
                  </Text>
                  <View className='ad-time-wrapper'>
                    <Text className='ad-time-label'>比赛时间：</Text>
                    <Text className='ad-time'>{formatTime(item.match_time)}</Text>
                  </View>
                </View>
              </View>
            )
          })
        )}
      </ScrollView>
    </View>
  )
}
