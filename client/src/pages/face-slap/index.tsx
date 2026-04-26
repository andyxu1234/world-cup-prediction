import { useEffect, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { getFaceSlaps, FaceSlap, FaceSlapSort } from '@/services/api'
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

const CHIPS: { key: FaceSlapSort; label: string; icon: string }[] = [
  { key: 'latest', label: '最新', icon: '🔥' },
  { key: 'confidence', label: '高信心翻车', icon: '💥' },
  { key: 'absurdity', label: '比分离谱', icon: '🤯' },
]

const RESULT_LABELS: Record<string, string> = {
  home_win: '主胜',
  draw: '平局',
  away_win: '客胜',
}

function formatMatchTime(timeStr: string | null): string {
  if (!timeStr) return ''
  try {
    const d = new Date(timeStr)
    const month = d.getMonth() + 1
    const day = d.getDate()
    const hour = String(d.getHours()).padStart(2, '0')
    const minute = String(d.getMinutes()).padStart(2, '0')
    return `${month}月${day}日 ${hour}:${minute}`
  } catch {
    return ''
  }
}

export default function FaceSlapPage() {
  const [faceSlaps, setFaceSlaps] = useState<FaceSlap[]>([])
  const [activeSort, setActiveSort] = useState<FaceSlapSort>('latest')
  const [loading, setLoading] = useState(false)
  
  // 分批渲染：控制当前渲染的卡片数量
  const [visibleCount, setVisibleCount] = useState(8)
  const visibleSlaps = faceSlaps.slice(0, visibleCount)

  const fetchData = async (sort: FaceSlapSort) => {
    setLoading(true)
    try {
      const data = await getFaceSlaps(sort)
      setFaceSlaps(data)
    } catch {
      setFaceSlaps([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(activeSort)
  }, [])

  // 分享给好友
  useShareAppMessage(() => ({
    title: 'AI 打脸合集 · 谁的预测最离谱？',
    path: '/pages/face-slap/index',
  }))

  // 分享到朋友圈
  useShareTimeline(() => ({
    title: 'AI 打脸合集 · 谁的预测最离谱？',
    query: '',
  }))

  const handleChipClick = (sort: FaceSlapSort) => {
    if (sort === activeSort) return
    setActiveSort(sort)
    // 不再立即清空数据，保持旧数据可见，loading 时显示加载指示
    setVisibleCount(8)
    setLoading(true)
    fetchData(sort)
  }
  
  // 滚动到底部时加载更多
  const handleScrollToLower = () => {
    if (visibleCount < faceSlaps.length) {
      setVisibleCount(prev => Math.min(prev + 8, faceSlaps.length))
    }
  }

  return (
    <View className='fs-page'>
      {/* 导航栏 */}
      <View className='fs-header'>
        <Text className='fs-title'>😂 打脸合集</Text>
        <Text className='fs-subtitle'>AI 翻车现场大赏</Text>
      </View>

      {/* 筛选条 */}
      <ScrollView scrollX className='fs-chips-scroll'>
        <View className='fs-chips'>
          {CHIPS.map((chip) => (
            <View
              key={chip.key}
              className={`fs-chip ${activeSort === chip.key ? 'fs-chip--active' : ''}`}
              onClick={() => handleChipClick(chip.key)}
            >
              <Text className='fs-chip-icon'>{chip.icon}</Text>
              <Text className={`fs-chip-text`}>{chip.label}</Text>
            </View>
          ))}
        </View>
      </ScrollView>

      {/* 卡片列表 */}
      <ScrollView 
        scrollY 
        className='fs-list' 
        scrollWithAnimation
        onScrollToLower={handleScrollToLower}
        lowerThreshold={100}
      >
        {/* Loading 状态 */}
        {loading && (
          <View className='fs-loading'>
            <Text className='fs-loading-text'>加载中...</Text>
          </View>
        )}

        {/* 数据列表 */}
        {!loading && visibleSlaps.length > 0 && (
          <View className='fs-card-wrap'>
          {visibleSlaps.map((fs, idx) => {
            try {
              const avatarUrl = MODEL_AVATARS[fs.model_name] || ''
              const fallback = MODEL_FALLBACKS[fs.model_name] || { gradient: 'linear-gradient(135deg, #ef4444, #f97316)', letter: '?' }
              const predScore = fs.predicted_score || '-'
              const actScore = fs.actual_score || '-'
              const predResult = RESULT_LABELS[fs.predicted_result] || fs.predicted_result || ''
              const actResult = RESULT_LABELS[fs.actual_result] || fs.actual_result || ''
              const conf = typeof fs.confidence === 'number' ? fs.confidence : null
              return (
                <View key={fs.prediction_id || idx} className='fs-card'>

                  {/* 顶部红条 */}
                  <View className='fs-card-bar' />

                  {/* 头部：模型 + 比赛信息 */}
                  <View className='fs-head'>
                    {/* 模型头像 */}
                    {avatarUrl ? (
                      <Image className='fs-avatar-img' src={avatarUrl} mode='aspectFit' />
                    ) : (
                      <View className='fs-avatar-fb' style={{ background: fallback.gradient }}>
                        <Text className='fs-avatar-letter'>{fallback.letter}</Text>
                      </View>
                    )}

                    {/* 模型名 + 比赛 */}
                    <View className='fs-head-main'>
                      <Text className='fs-model-name'>{fs.model_name || '未知模型'}</Text>
                      <View className='fs-match-row'>
                        {fs.home_team_flag ? (
                          <Image className='fs-flag' src={fs.home_team_flag} mode='aspectFit' />
                        ) : null}
                        <Text className='fs-match-teams'>{fs.home_team || ''} vs {fs.away_team || ''}</Text>
                        {fs.away_team_flag ? (
                          <Image className='fs-flag' src={fs.away_team_flag} mode='aspectFit' />
                        ) : null}
                      </View>
                      {fs.match_time && (
                        <Text className='fs-match-time'>⏰ {formatMatchTime(fs.match_time)}</Text>
                      )}
                    </View>

                    {/* 排序标签 */}
                    {activeSort === 'confidence' && conf != null && (
                      <View className='fs-tag fs-tag--red'>
                        <Text className='fs-tag-text'>💥 {conf}/10</Text>
                      </View>
                    )}
                    {activeSort === 'absurdity' && (
                      <View className='fs-tag fs-tag--purple'>
                        <Text className='fs-tag-text'>偏差{fs.score_absurdity ?? 0}球</Text>
                      </View>
                    )}
                    {activeSort === 'latest' && (
                      <View className='fs-tag fs-tag--gold'>
                        <Text className='fs-tag-text'>#{idx + 1}</Text>
                      </View>
                    )}
                  </View>

                  {/* 比分对比区 */}
                  <View className='fs-score-section'>
                    {/* 预测 */}
                    <View className='fs-score-block'>
                      <Text className='fs-score-label'>{fs.model_name || ''} 预测</Text>
                      <Text className='fs-score-num fs-score-num--wrong'>{predScore}</Text>
                      <Text className='fs-score-result-label'>
                        {predResult}{conf != null ? ` (信心${conf})` : ''}
                      </Text>
                    </View>

                    {/* 箭头 */}
                    <View className='fs-arrow-box'>
                      <Text className='fs-arrow-icon'>→</Text>
                    </View>

                    {/* 实际 */}
                    <View className='fs-score-block'>
                      <Text className='fs-score-label'>实际结果</Text>
                      <Text className='fs-score-num fs-score-num--right'>{actScore}</Text>
                      <Text className='fs-score-result-label'>
                        {actResult}
                      </Text>
                    </View>
                  </View>

                  {/* 信心进度条 */}
                  {conf != null && (
                    <View className='fs-conf-row'>
                      <Text className='fs-conf-label'>信心指数</Text>
                      <View className='fs-conf-bar-track'>
                        <View
                          className='fs-conf-bar-fill'
                          style={{
                            width: `${Math.min(conf * 10, 100)}%`,
                            background: conf >= 7
                              ? 'linear-gradient(90deg, #ef4444, #f97316)'
                              : conf >= 4
                                ? 'linear-gradient(90deg, #f59e0b, #eab308)'
                                : 'linear-gradient(90deg, #22c55e, #84cc16)',
                          }}
                        />
                      </View>
                      <Text className='fs-conf-value'>{conf}/10</Text>
                    </View>
                  )}

                </View>
              )
            } catch (cardErr) {
              // 单张卡片渲染异常时跳过，避免整页白屏
              console.warn('[face-slap] card render error:', cardErr, fs)
              return null
            }
          })}
          </View>
        )}
        
        {/* 加载更多提示 */}
        {!loading && visibleCount < faceSlaps.length && (
          <View className='fs-load-more'>
            <Text className='fs-load-more-text'>上拉加载更多</Text>
          </View>
        )}

        {/* 空状态 */}
        {!loading && faceSlaps.length === 0 && (
          <View className='fs-empty'>
            <Text className='fs-empty-icon'>🤖</Text>
            <Text className='fs-empty-text'>暂无打脸数据，比赛还没开始呢</Text>
          </View>
        )}
      </ScrollView>
    </View>
  )
}
