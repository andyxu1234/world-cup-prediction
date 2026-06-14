import { useEffect, useState, useRef } from 'react'
import { View, Text, Input, ScrollView, Image, Button } from '@tarojs/components'
import Taro, { useRouter, useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { useMatchStore, useUserStore } from '@/stores'
import { AD_UNIT_IDS, isAdUnlocked, showRewardedVideo, setAdUnlocked, createRewardedVideoAd, shouldShowAd } from '@/utils/ad'
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
import shareIcon from '@/assets/share.svg'
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
  const [voteValidationError, setVoteValidationError] = useState('')
  // 广告解锁 — 显式三态状态机，无中间态
  // 'cinema' = 广告加载中(影院动画) | 'locked' = 锁+按钮 | 'unlocked' = 预测数据
  const [adPhase, setAdPhase] = useState<'cinema' | 'locked' | 'unlocked'>('cinema')
  // 防止广告并发重入
  const adPlayingRef = useRef(false)
  // 广告实例引用（在页面内创建，避免页面上下文不一致问题）
  const adInstanceRef = useRef<any>(null)
  // 动态计算 AI 预测列表区高度，解决 iOS 设备底部空白导致预测表单被推到屏幕外的问题
  // 根因：CSS 中 calc(100vh - 400px) 的 400px 是硬编码 CSS px，
  //       页面元素全部用 rpx 编写，不同设备 rpx→px 转换比例不同（尤其 iOS）
  const [predListHeight, setPredListHeight] = useState<string>('')

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

  // 页面卸载时销毁广告实例
  useEffect(() => {
    return () => {
      if (adInstanceRef.current) {
        adInstanceRef.current.destroy()
        adInstanceRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (user && matchId) {
      fetchVote(user.id, matchId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, matchId])

  // 已有投票时回填状态；无投票时重置默认
  useEffect(() => {
    if (myVote) {
      setSelectedResult(myVote.result)
      setHomeScore(String(myVote.score_home ?? 0))
      setAwayScore(String(myVote.score_away ?? 0))
    } else {
      // 未投票：默认 0:0，无选中
      setSelectedResult('')
      setHomeScore('0')
      setAwayScore('0')
    }
  }, [myVote])

  // 实时校验：胜负平与比分一致性
  useEffect(() => {
    if (!selectedResult) { setVoteValidationError(''); return }
    const h = Number(homeScore) || 0
    const a = Number(awayScore) || 0
    if (selectedResult === 'home_win' && h <= a) {
      setVoteValidationError(`「主胜」与比分 ${h}:${a} 不一致`)
    } else if (selectedResult === 'draw' && h !== a) {
      setVoteValidationError(`「平局」与比分 ${h}:${a} 不一致`)
    } else if (selectedResult === 'away_win' && h >= a) {
      setVoteValidationError(`「客胜」与比分 ${h}:${a} 不一致`)
    } else {
      setVoteValidationError('')
    }
  }, [selectedResult, homeScore, awayScore])

  // 微信分享注册（用户通过右上角...转发或点击分享按钮时使用）
  useShareAppMessage(() => {
    const home = currentMatch?.home_team.cn_name || currentMatch?.home_team.name || ''
    const away = currentMatch?.away_team.cn_name || currentMatch?.away_team.name || ''
    return {
      title: `${home} vs ${away} · AI 预测对战卡`,
      path: `/pages/index/index`,
    }
  })

  // 分享到朋友圈
  useShareTimeline(() => {
    const home = currentMatch?.home_team.cn_name || currentMatch?.home_team.name || ''
    const away = currentMatch?.away_team.cn_name || currentMatch?.away_team.name || ''
    return {
      title: `${home} vs ${away} · AI 预测世界杯`,
      query: '',
    }
  })

  // 动态计算主内容滚动区高度（仅测量 Hero，summary+预测+投票统一在内部滚动）
  useEffect(() => {
    if (!pageReady || !currentMatch) return
    const timer = setTimeout(() => {
      try {
        const query = Taro.createSelectorQuery()
        query.select('.match-hero').boundingClientRect()
        query.exec((res) => {
          const heroRect = res[0]
          if (!heroRect) {
            setPredListHeight('calc(100vh - 280px)')
            return
          }
          const sysInfo = Taro.getSystemInfoSync()
          const { windowHeight } = sysInfo
          // 主滚动区高度 = 屏幕高度 - Hero高度 - 间距余量
          const available = Math.max(windowHeight - heroRect.height - 10, 300)
          setPredListHeight(`${available}px`)
        })
      } catch {
        setPredListHeight('calc(100vh - 280px)')
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [pageReady, currentMatch])

  // 广告解锁逻辑 — 显式三态状态机，无中间态闪烁
  // adPhase: 'cinema'(影院加载) | 'locked'(锁+按钮) | 'unlocked'(预测数据)
  useEffect(() => {
    if (!pageReady || !currentMatch) return
    if (adPlayingRef.current) return

    // 获取 VIP 状态
    const { isVip, vipExpireAt } = useUserStore.getState()

    // 无需广告：已结束 / 无预测 / 已缓存解锁 / 首场免费 / VIP 用户 → 直接到预测数据页
    if (
      currentMatch.status === 'finished' ||
      predictions.length === 0 ||
      isAdUnlocked(matchId) ||
      matchId === 72 || // 墨西哥 VS 南非 — 首场免费，新用户体验用
      !shouldShowAd(isVip, vipExpireAt) // VIP 用户跳过广告
    ) {
      setAdPhase('unlocked')
      return
    }

    // 需要广告：自动播放（当前已在 cinema 态，无需再设置）
    const playAd = async () => {
      adPlayingRef.current = true
      try {
        // 确保广告实例已创建（在当前页面上下文中）
        if (!adInstanceRef.current) {
          const { ad, destroy } = createRewardedVideoAd()
          adInstanceRef.current = ad
          // 注意：destroy 会在页面卸载时调用
        }
        const { completed, available } = await showRewardedVideo(adInstanceRef.current)
        await new Promise(r => setTimeout(r, 150))
        if (completed || !available) {
          setAdUnlocked(matchId)
          setAdPhase('unlocked')  // 看完/无广告 → 直接切到预测数据，无中间态
        } else {
          setAdPhase('locked')    // 未看完 → 切到锁+按钮
        }
      } catch {
        await new Promise(r => setTimeout(r, 200))
        setAdUnlocked(matchId)
        setAdPhase('unlocked')    // 广告失败 → 降级解锁
      } finally {
        adPlayingRef.current = false
      }
    }
    playAd()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageReady, currentMatch, matchId])

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

    // 校验：胜负平选择必须与比分一致
    const h = Number(homeScore)
    const a = Number(awayScore)
    let valid = true
    let errMsg = ''

    if (selectedResult === 'home_win') {
      if (h <= a) { valid = false; errMsg = `选择了「主胜」但比分 ${h}:${a} 不支持主胜，请检查` }
    } else if (selectedResult === 'draw') {
      if (h !== a) { valid = false; errMsg = `选择了「平局」但比分 ${h}:${a} 不是平局，请检查` }
    } else if (selectedResult === 'away_win') {
      if (h >= a) { valid = false; errMsg = `选择了「客胜」但比分 ${h}:${a} 不支持客胜，请检查` }
    }

    if (!valid) {
      Taro.showToast({ title: errMsg, icon: 'none', duration: 2500 })
      return
    }

    try {
      await vote(matchId, selectedResult, Number(homeScore), Number(awayScore))
      Taro.showToast({ title: myVote ? '预测已更新！' : '预测已提交！', icon: 'success' })
    } catch (err: any) {
      Taro.showToast({ title: err?.message || '提交失败', icon: 'none', duration: 2000 })
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
          {(() => {
            if (!currentMatch.match_time) return '待定'
            const d = new Date(currentMatch.match_time)
            const month = d.getMonth() + 1
            const day = d.getDate()
            const weekDays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
            const weekday = weekDays[d.getDay()]
            const hour24 = d.getHours()
            const period = hour24 < 6 ? '凌晨' : hour24 < 12 ? '上午' : hour24 < 14 ? '中午' : hour24 < 18 ? '下午' : '晚上'
            const hour12 = hour24 === 0 ? 12 : hour24 > 12 ? hour24 - 12 : hour24
            return `${month}月${day}日 ${weekday} ${period}${hour12.toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
          })()}
        </Text>
      </View>

      {/* 风险提醒 — 顶部醒目位置 */}
      <View className='risk-reminder'>
        <Text className='risk-reminder-icon'>⚠️</Text>
        <Text className='risk-reminder-text'>AI预测仅供参考，不构成投注建议，请理性娱乐</Text>
      </View>

      {/* VIP 用户专属提示 */}
      {useUserStore.getState().isVip && adPhase === 'unlocked' && (
        <View className='vip-hint'>
          <Text className='vip-hint-icon'>👑</Text>
          <Text className='vip-hint-text'>尊贵的VIP用户，已为您去除广告</Text>
        </View>
      )}

      {/* 主内容区 — 统一滚动：AI综合分析 + AI预测列表 + 投票区域 一起下滑 */}
      <ScrollView scrollY className='main-scroll' style={predListHeight ? { height: predListHeight } : undefined}>
        {/* AI 综合总结 */}
        {adPhase === 'unlocked' && currentMatch?.summary && (
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
              {/* 综合信心 */}
              {currentMatch.summary.confidence != null && (
                <View className='pred-conf'>
                  <View className='pred-conf-hd'>
                    <Text>综合信心</Text>
                    <Text style={{ color: (currentMatch.summary.confidence || 0) >= 7 ? '#00ff87' : '#ffd700' }}>
                      {currentMatch.summary.confidence}/10
                    </Text>
                  </View>
                  <View className='conf-bar'>
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
              {/* 备选比分 */}
              {currentMatch.summary.score_alt_home != null && currentMatch.summary.score_alt_away != null && (
                <View className='pred-alt-score'>
                  <Text className='pred-alt-label'>备选：{currentMatch.summary.score_alt_home}:{currentMatch.summary.score_alt_away}</Text>
                </View>
              )}
            </>
          )}
          {currentMatch.summary.summary && (
            <Text className='summary-text'>{currentMatch.summary.summary}</Text>
          )}
        </View>
      )}

      {/* 信息流广告 */}
      <ad unit-id={AD_UNIT_IDS.feed} ad-intervals={30} />

      {/* AI 预测卡片 — 三态显式切换，无中间态 */}
      {adPhase === 'unlocked' ? (
        <>
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
                      <Text className='pred-alt-label'>备选：{pred.score_alt}</Text>
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
        </>
      ) : adPhase === 'cinema' ? (
        <View className='ad-cinema-wrap'>
          <View className='cinema-bg-glow' />
          <View className='cinema-spinner-ring'>
            <View className='cinema-spinner-core' />
            <View className='cinema-spinner-orbit' />
          </View>
          <Text className='cinema-title'>广告加载中</Text>
          <Text className='cinema-subtitle'>观看完短视频即可解锁 AI 预测</Text>
          <View className='cinema-progress'>
            <View className='cinema-progress-bar' />
          </View>
        </View>
      ) : (
        <View className='ad-lock-wrap'>
          <View className='ad-lock-overlay'>
            <Text className='ad-lock-icon'>🔒</Text>
            <Text className='ad-lock-title'>观看视频解锁 AI 预测</Text>
            <Text className='ad-lock-desc'>完整观看短视频即可解锁全部 AI 模型预测结果</Text>
            <View className='ad-unlock-btn' onClick={async () => {
              if (adPlayingRef.current) return
              adPlayingRef.current = true
              setAdPhase('cinema')  // 先切到影院加载态
              try {
                // 确保广告实例已创建（在当前页面上下文中）
                if (!adInstanceRef.current) {
                  const { ad } = createRewardedVideoAd()
                  adInstanceRef.current = ad
                }
                const { completed, available } = await showRewardedVideo(adInstanceRef.current)
                await new Promise(r => setTimeout(r, 150))
                if (completed || !available) {
                  setAdUnlocked(matchId)
                  setAdPhase('unlocked')
                } else {
                  setAdPhase('locked')
                }
              } catch {
                await new Promise(r => setTimeout(r, 200))
                setAdUnlocked(matchId)
                setAdPhase('unlocked')
              } finally {
                adPlayingRef.current = false
              }
            }}>
              <Text className='ad-unlock-btn-text'>观看视频解锁</Text>
            </View>
            {/* 引流入口 */}
            <View className='ad-skip-hint' onClick={() => Taro.navigateTo({ url: '/pages/contact/index' })}>
              <Text className='ad-skip-text'>不想看广告？ →</Text>
            </View>
          </View>
        </View>
      )}

      {/* 投票区域：比赛未结束时允许修改预测 */}
      <View className='vote-card'>
        {(!!myVote && currentMatch?.status === 'finished') ? (
          <>
            <Text className='vote-title'>✅ 你的预测</Text>
            <View className='vote-opts'>
              {['home_win', 'draw', 'away_win'].map((opt) => {
                const label = opt === 'home_win' ? '主胜' : opt === 'draw' ? '平局' : '客胜'
                return (
                  <View key={opt} className={`vote-btn ${myVote!.result === opt ? 'sel' : ''} voted`}>
                    <Text>{label}</Text>
                  </View>
                )
              })}
            </View>
            <View className='vote-score'>
              <Text className='sc-display mono'>{myVote!.score_home ?? 0}</Text>
              <Text className='sc-colon mono'>:</Text>
              <Text className='sc-display mono'>{myVote!.score_away ?? 0}</Text>
            </View>
            <View className='vote-submitted'><Text>✓ 已提交</Text></View>
          </>
        ) : (
          <>
            <Text className='vote-title'>{myVote ? '✅ 修改你的预测' : '✏️ 投出你的预测'}</Text>
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
              <Input className='sc-input mono' type='number' value={homeScore} onInput={(e) => setHomeScore(e.detail.value)} />
              <Text className='sc-colon mono'>:</Text>
              <Input className='sc-input mono' type='number' value={awayScore} onInput={(e) => setAwayScore(e.detail.value)} />
            </View>
            {voteValidationError ? (
              <Text className='vote-error-hint'>{voteValidationError}</Text>
            ) : null}
            <View className='vote-submit' onClick={handleVote}>
              <Text>{myVote ? '修改预测' : '提交预测'}</Text>
            </View>
          </>
        )}
      </View>

      {/* 主内容区滚动结束 */}
      </ScrollView>

      {/* 分享按钮（固定右下角，直接转发小程序） */}
      <View className='share-fab-wrap'>
        <View className='share-fab-glow' />
        <Button
          className='share-fab'
          openType='share'
          onShareAppMessageSuccess={() => Taro.showToast({ title: '已分享', icon: 'success' })}
        >
          <View className='share-fab-inner'>
            <Image className='share-fab-img' src={shareIcon} mode='aspectFit' />
            <Text className='share-fab-text'>分享</Text>
          </View>
        </Button>
      </View>
    </View>
  )
}
