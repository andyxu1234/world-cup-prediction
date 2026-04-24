import { useEffect, useState } from 'react'
import { View, Text, Input, ScrollView, Image } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage } from '@tarojs/taro'
import { useMatchStore, useUserStore } from '@/stores'
import { getShareCardImage } from '@/services/api'
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

function getResultLabel(result: string) {
  if (result === 'home_win') return { text: '主胜', cls: 'pred-home' }
  if (result === 'draw') return { text: '平局', cls: 'pred-draw' }
  return { text: '客胜', cls: 'pred-away' }
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

function FlagImage({ src, className }: { src: string; className: string }) {
  const [failed, setFailed] = useState(false)
  if (failed || !src) return <View className='flag-fallback'>⚽</View>
  return <Image className={className} src={src} mode='aspectFit' onError={() => setFailed(true)} />
}

function TeamInfo({ team }: { team: { name: string; cn_name: string | null; flag_url: string | null; group_name: string | null; fifa_rank: number | null } }) {
  const displayName = team.cn_name || team.name
  const groupTag = team.group_name ? `${team.group_name}组` : ''
  const fifaTag = team.fifa_rank ? `FIFA #${team.fifa_rank}` : ''
  return (
    <View className='match-hero-team'>
      <FlagImage src={team.flag_url || ''} className='flag flag-lg' />
      <Text className='match-hero-team-name'>{displayName}</Text>
      <View className='match-hero-team-tags'>
        {groupTag && <Text className='team-tag tag-group'>{groupTag}</Text>}
        {fifaTag && <Text className='team-tag tag-rank'>{fifaTag}</Text>}
      </View>
    </View>
  )
}

export default function MatchDetail() {
  const router = useRouter()
  const matchId = Number(router.params.id)
  const { currentMatch, predictions, fetchMatchDetail, fetchPredictions } = useMatchStore()
  const { user, myVote, fetchVote, vote } = useUserStore()
  const [selectedResult, setSelectedResult] = useState<string>('')
  const [homeScore, setHomeScore] = useState('0')
  const [awayScore, setAwayScore] = useState('0')
  const [pageReady, setPageReady] = useState(false)
  const [showShareSheet, setShowShareSheet] = useState(false)
  const [shareImgUrl, setShareImgUrl] = useState('')
  const [showSharePreview, setShowSharePreview] = useState(false)

  useEffect(() => {
    if (matchId) {
      setPageReady(false)  // 进入页面时先设置为未就绪
      // 先清空旧数据
      useMatchStore.setState({ currentMatch: null, predictions: [] })
      
      Promise.all([
        fetchMatchDetail(matchId),
        fetchPredictions(matchId)
      ]).finally(() => {
        setPageReady(true)  // 数据加载完成后才设置为就绪
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchId])

  useEffect(() => {
    if (user && matchId) {
      fetchVote(user.id, matchId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, matchId])

  // 已有投票时回填状态
  useEffect(() => {
    if (myVote) {
      setSelectedResult(myVote.result)
      setHomeScore(String(myVote.score_home ?? 0))
      setAwayScore(String(myVote.score_away ?? 0))
    }
  }, [myVote])

  // 微信分享注册（用户通过右上角...转发时使用）
  useShareAppMessage(() => {
    const home = currentMatch?.home_team.cn_name || currentMatch?.home_team.name || ''
    const away = currentMatch?.away_team.cn_name || currentMatch?.away_team.name || ''
    return {
      title: `${home} vs ${away} · AI 预测对战卡`,
      path: `/pages/index/index`,
      imageUrl: getShareCardImage(matchId),
    }
  })

  // 分享面板操作
  const handleOpenShareSheet = () => {
    setShowShareSheet(true)
  }

  const handleCloseShareSheet = () => {
    setShowShareSheet(false)
  }

  // 预测分享图 → 当前页悬浮预览
  const handleShareImage = async () => {
    setShowShareSheet(false)
    const url = getShareCardImage(matchId)
    setShareImgUrl(url)
    setShowSharePreview(true)
  }

  const handleClosePreview = () => {
    setShowSharePreview(false)
  }

  // 长按图片 → 保存到相册
  const handleLongPressSave = (imgUrl: string) => {
    Taro.showActionSheet({
      itemList: ['保存图片到相册'],
      success: () => {
        Taro.showLoading({ title: '保存中...' })
        Taro.downloadFile({
          url: imgUrl,
          success: (res) => {
            if (res.statusCode === 200) {
              Taro.saveImageToPhotosAlbum({
                filePath: res.tempFilePath,
                success: () => { Taro.hideLoading(); Taro.showToast({ title: '已保存', icon: 'success' }) },
                fail: () => { Taro.hideLoading(); Taro.showToast({ title: '保存失败', icon: 'none' }) },
              })
            } else {
              Taro.hideLoading()
              Taro.showToast({ title: '下载失败', icon: 'none' })
            }
          },
          fail: () => { Taro.hideLoading(); Taro.showToast({ title: '下载失败', icon: 'none' }) },
        })
      },
    })
  }

  // 长按保存图片到相册
  const handleSaveShareImage = () => {
    Taro.showToast({ title: '长按图片可保存到相册', icon: 'none', duration: 2000 })
  }

  // 分享给朋友 → 引导使用微信原生分享
  const handleShareToFriend = () => {
    setShowShareSheet(false)
    setTimeout(() => {
      Taro.showToast({ title: '请点击右上角「...」转发给好友', icon: 'none', duration: 2000 })
    }, 300)
  }

  if (!pageReady || !currentMatch) {
    return <View className='detail-page'><Text className='loading'>加载中...</Text></View>
  }

  const handleVote = async () => {
    if (!selectedResult) {
      Taro.showToast({ title: '请选择预测结果', icon: 'none' })
      return
    }
    if (!user) {
      Taro.showToast({ title: '请先登录后再投票', icon: 'none' })
      return
    }
    try {
      await vote(matchId, selectedResult, Number(homeScore), Number(awayScore))
      Taro.showToast({ title: '预测已提交！', icon: 'success' })
    } catch {
      Taro.showToast({ title: '提交失败', icon: 'error' })
    }
  }

  return (
    <View className='detail-page'>
      {/* 比赛头部 */}
      <View className='match-hero'>
        <Text className='match-hero-round'>{getRoundLabel(currentMatch.round)}</Text>
        <View className='match-hero-teams'>
          <TeamInfo team={currentMatch.home_team} />
          <Text className='match-hero-vs mono'>VS</Text>
          <TeamInfo team={currentMatch.away_team} />
        </View>
        <Text className='match-hero-meta'>
          {currentMatch.match_time ? new Date(currentMatch.match_time).toLocaleDateString('zh-CN') : '待定'} · {currentMatch.venue || 'TBD'}
        </Text>
      </View>

      {/* AI 综合总结 — 放在头部和预测列表之间 */}
      {currentMatch?.summary && (
        <View className='summary-card'>
          <View className='summary-hd'>
            <Text className='summary-title'>📊 AI 综合分析</Text>
          </View>
          {/* AI 共识（简短结论） */}
          {currentMatch.summary.short_summary && (
            <View className='summary-short-row'>
              <Text className='summary-short-label'>AI 共识</Text>
              <Text className='summary-short-text'>{currentMatch.summary.short_summary}</Text>
            </View>
          )}
          {currentMatch.summary.score_home != null && currentMatch.summary.score_away != null && (
            <>
              <View className='summary-score'>
                <Text className='summary-sc-big mono' style={{ color: '#00ff87' }}>{currentMatch.summary.score_home}</Text>
                <Text className='summary-colon mono'>:</Text>
                <Text className='summary-sc-big mono' style={{ color: '#00b4d8' }}>{currentMatch.summary.score_away}</Text>
              </View>
              {/* 备选比分 */}
              {currentMatch.summary.score_alt_home != null && currentMatch.summary.score_alt_away != null && (
                <Text className='summary-alt-score'>备选：{currentMatch.summary.score_alt_home}:{currentMatch.summary.score_alt_away}</Text>
              )}
            </>
          )}
          {currentMatch.summary.confidence != null && (
            <View className='summary-conf-row'>
              <Text className='summary-conf-label'>综合信心</Text>
              <Text className='summary-conf-val' style={{ color: (currentMatch.summary.confidence || 0) >= 7 ? '#00ff87' : '#ffd700' }}>
                {currentMatch.summary.confidence}/10
              </Text>
              <View className='conf-bar-sm'>
                <View
                  className='conf-fill'
                  style={{
                    width: `${(currentMatch.summary.confidence || 0) * 10}%`,
                    background: (currentMatch.summary.confidence || 0) >= 7 ? '#00ff87' : '#ffd700'
                  }}
                />
              </View>
            </View>
          )}
          {currentMatch.summary.summary && (
            <Text className='summary-text'>{currentMatch.summary.summary}</Text>
          )}
        </View>
      )}

      {/* AI 预测卡片 */}
      <ScrollView scrollY className='pred-list'>
        {predictions.length === 0 && (
          <View className='pred-empty'>
            <Text className='pred-empty-icon'>🤖</Text>
            <Text className='pred-empty-title'>AI 预测尚未生成</Text>
            <Text className='pred-empty-desc'>AI 分析结果将于比赛前三天生成，届时将为你呈现多模型智能预测</Text>
          </View>
        )}
        {predictions.map((pred, idx) => {
          const avatarUrl = MODEL_AVATARS[pred.model_name]
          const fallback = MODEL_FALLBACKS[pred.model_name] || { gradient: 'linear-gradient(135deg, #666, #999)', letter: '?' }
          const resultInfo = getResultLabel(pred.result)
          const confColor = (pred.confidence || 5) >= 7 ? '#00ff87' : (pred.confidence || 5) >= 5 ? '#ffd700' : '#ff3b5c'
          const scores = (pred.score || '0:0').split(':')
          return (
            <View key={idx} className='pred-card'>
              <View className='pred-hd'>
                <View className='pred-model'>
                  {avatarUrl ? (
                    <Image className='model-av-img' src={avatarUrl} mode='aspectFit' />
                  ) : (
                    <View className='model-av' style={{ background: fallback.gradient }}>
                      {fallback.letter}
                    </View>
                  )}
                  <View>
                    <Text className='pred-name'>{pred.model_name}</Text>
                  </View>
                </View>
                <Text className={`pred-result ${resultInfo.cls}`}>{resultInfo.text}</Text>
              </View>
              <View className='pred-score-area'>
                <View className='pred-score-col'>
                  <Text className='pred-score-big' style={{ color: '#00ff87' }}>{scores[0] || '0'}</Text>
                  <Text className='pred-score-label'>{currentMatch.home_team.cn_name || currentMatch.home_team.name}</Text>
                  {currentMatch.home_team.group_name && (
                    <Text className='pred-team-sub'>{currentMatch.home_team.group_name}组 · FIFA #{currentMatch.home_team.fifa_rank || '?'}</Text>
                  )}
                </View>
                <Text className='pred-colon mono'>:</Text>
                <View className='pred-score-col'>
                  <Text className='pred-score-big' style={{ color: '#00b4d8' }}>{scores[1] || '0'}</Text>
                  <Text className='pred-score-label'>{currentMatch.away_team.cn_name || currentMatch.away_team.name}</Text>
                  {currentMatch.away_team.group_name && (
                    <Text className='pred-team-sub'>{currentMatch.away_team.group_name}组 · FIFA #{currentMatch.away_team.fifa_rank || '?'}</Text>
                  )}
                </View>
              </View>
              <View className='pred-conf'>
                <View className='pred-conf-hd'>
                  <Text>信心指数</Text>
                  <Text style={{ color: confColor }}>{pred.confidence || '-'}/10</Text>
                </View>
                <View className='conf-bar'>
                  <View className='conf-fill' style={{ width: `${(pred.confidence || 0) * 10}%`, background: confColor }} />
                </View>
                {/* 备选分数 */}
                {pred.score_alt && (
                  <View className='pred-alt-score'>
                    <Text className='pred-alt-label'>备选：{pred.score_alt} ({pred.score_alt_prob ? pred.score_alt_prob.toFixed(0) : 0}%)</Text>
                  </View>
                )}
              </View>
              {/* AI 分析 */}
              {pred.analysis && (
                <Text className='pred-analysis'>{pred.analysis}</Text>
              )}
            </View>
          )
        })}
      </ScrollView>

      {/* 投票区域 */}
      <View className='vote-card'>
        {myVote ? (
          <>
            <Text className='vote-title'>✅ 你的预测</Text>
            <View className='vote-opts'>
              {['home_win', 'draw', 'away_win'].map((opt) => {
                const label = opt === 'home_win' ? '主胜' : opt === 'draw' ? '平局' : '客胜'
                return (
                  <View
                    key={opt}
                    className={`vote-btn ${myVote.result === opt ? 'sel' : ''} voted`}
                  >
                    <Text>{label}</Text>
                  </View>
                )
              })}
            </View>
            <View className='vote-score'>
              <Text className='sc-display mono'>{myVote.score_home ?? 0}</Text>
              <Text className='sc-colon mono'>:</Text>
              <Text className='sc-display mono'>{myVote.score_away ?? 0}</Text>
            </View>
            <View className='vote-submitted'>
              <Text>✓ 已提交</Text>
            </View>
          </>
        ) : (
          <>
            <Text className='vote-title'>✏️ 投出你的预测</Text>
            <View className='vote-opts'>
              {['home_win', 'draw', 'away_win'].map((opt) => {
                const label = opt === 'home_win' ? '主胜' : opt === 'draw' ? '平局' : '客胜'
                return (
                  <View
                    key={opt}
                    className={`vote-btn ${selectedResult === opt ? 'sel' : ''}`}
                    onClick={() => setSelectedResult(opt)}
                  >
                    <Text>{label}</Text>
                  </View>
                )
              })}
            </View>
            <View className='vote-score'>
              <Input
                className='sc-input mono'
                type='number'
                value={homeScore}
                onInput={(e) => setHomeScore(e.detail.value)}
              />
              <Text className='sc-colon mono'>:</Text>
              <Input
                className='sc-input mono'
                type='number'
                value={awayScore}
                onInput={(e) => setAwayScore(e.detail.value)}
              />
            </View>
            <View className='vote-submit' onClick={handleVote}>
              <Text>提交预测</Text>
            </View>
          </>
        )}
      </View>

      {/* 分享按钮（固定右下角） */}
      <View className='share-fab' onClick={handleOpenShareSheet}>
        <Text className='share-fab-icon'>⤴</Text>
      </View>

      {/* 分享底部弹出面板 */}
      {showShareSheet && (
        <>
          <View className='share-mask' onClick={handleCloseShareSheet} />
          <View className='share-sheet'>
            <View className='share-sheet-hd'>
              <Text className='share-sheet-title'>分享到</Text>
              <View className='share-sheet-close' onClick={handleCloseShareSheet}>
                <Text>✕</Text>
              </View>
            </View>
            <View className='share-sheet-options'>
              <View className='share-sheet-item' onClick={handleShareImage}>
                <View className='share-sheet-icon-wrap'>
                  <Text className='share-sheet-icon'>🖼</Text>
                </View>
                <Text className='share-sheet-label'>预测分享图</Text>
              </View>
              <View className='share-sheet-item' onClick={handleShareToFriend}>
                <View className='share-sheet-icon-wrap'>
                  <Text className='share-sheet-icon'>📤</Text>
                </View>
                <Text className='share-sheet-label'>分享给朋友</Text>
              </View>
            </View>
            <View className='share-sheet-cancel' onClick={handleCloseShareSheet}>
              <Text>取消</Text>
            </View>
          </View>
        </>
      )}

      {/* 分享图悬浮预览（居中弹窗，浮在当前页之上） */}
      {showSharePreview && (
        <>
          <View className='preview-mask' onClick={handleClosePreview} />
          <View className='preview-popup'>
            {/* 关闭按钮 */}
            <View className='preview-close-btn' onClick={handleClosePreview}>
              <Text className='preview-close-icon'>✕</Text>
            </View>
            {/* 分享卡片图片 */}
            {shareImgUrl && (
              <Image
                className='preview-img'
                src={shareImgUrl}
                mode='widthFix'
                onLongPress={() => handleLongPressSave(shareImgUrl)}
                onClick={() => Taro.previewImage({ urls: [shareImgUrl] })}
              />
            )}
            {/* 底部提示 */}
            <View className='preview-hint'>
              <Text className='preview-hint-text'>长按图片保存或分享给好友</Text>
            </View>
          </View>
        </>
      )}
    </View>
  )
}
