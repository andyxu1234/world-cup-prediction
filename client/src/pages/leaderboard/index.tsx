import { useEffect, useState, useRef } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro, { useShareAppMessage, useShareTimeline } from '@tarojs/taro'
import { useLeaderboardStore, useUserStore, useMatchStore, useLeagueStore } from '@/stores'
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

/** origin -> 地区显示名映射 */
const ORIGIN_LABELS: Record<string, string> = {
  cn: '🇨🇳 中国',
  us: '🇺🇸 美国',
}

const TABS = [
  { key: 'ai' as const, label: 'AI 排行' },
  { key: 'human' as const, label: '人类排行' },
]

const ROUNDS = ['全部', '小组赛', '淘汰赛']

/** 排序按钮配置 */
type SortByType = 'default' | 'result_accuracy' | 'score_accuracy'
const SORT_OPTIONS: { by: SortByType; label: string }[] = [
  { by: 'default', label: '综合' },
  { by: 'score_accuracy', label: '比分' },
  { by: 'result_accuracy', label: '胜负' },
]

function ModelAvatar({ name, size = '' }: { name: string; size?: string }) {
  const url = MODEL_AVATARS[name]
  if (url) {
    return <Image className={`model-av-img ${size}`} src={url} mode='aspectFit' />
  }
  const fb = MODEL_FALLBACKS[name] || { gradient: 'linear-gradient(135deg, #666, #999)', letter: '?' }
  return <View className={`model-av ${size}`} style={{ background: fb.gradient }}>{fb.letter}</View>
}

/** 检测是否为有效的可加载图片 URL */
function isValidImageUrl(url: string | undefined | null): boolean {
  if (!url) return false
  // 微信临时文件路径、空值等不可作为网络图片加载
  if (/^https?:\/\/tmp/i.test(url)) return false
  if (/^\/?tmp/i.test(url)) return false
  // 必须是 http(s) 开头的完整 URL
  if (!/^https?:\/\//i.test(url)) return false
  return true
}

function UserAvatar({ avatarUrl, nickname }: { avatarUrl?: string | null; nickname?: string }) {
  const [imgErr, setImgErr] = useState(false)
  const fullUrl = resolveAvatarUrl(avatarUrl)
  if (isValidImageUrl(fullUrl) && !imgErr) {
    return <Image className='model-av-img lb-av' src={fullUrl} mode='aspectFill' onError={() => setImgErr(true)} />
  }
  const letter = (nickname || '?').charAt(0).toUpperCase()
  return <View className='model-av lb-av' style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}>{letter}</View>
}

/** 解析 style_tags 为语义化标签列表 */
function renderStyleTags(tags: Record<string, any> | null | undefined) {
  if (!tags || typeof tags !== 'object') return null
  return Object.entries(tags).map(([key, val]) => {
    const k = String(key).toLowerCase()
    const v = String(val)
    if (k === 'origin') {
      return <Text key={key} className='lb-tag lb-tag-origin'>{ORIGIN_LABELS[v] ?? v}</Text>
    }
    if (k === 'style') {
      return <Text key={key} className='lb-tag lb-tag-style'>{v}</Text>
    }
    return <Text key={key} className='lb-tag'>{v}</Text>
  })
}

/** 计算距离世界杯开幕的倒计时（2026-06-11 开幕） */
function getCountdown(): { days: number; hours: number; mins: number; secs: number } {
  // 使用 Date 构造函数避免时区解析差异（月份从0开始）
  const target = new Date(Date.UTC(2026, 5, 11, 21, 0, 0))
  const now = new Date()
  const diff = Math.max(0, target.getTime() - now.getTime())
  return {
    days: Math.floor(diff / (1000 * 60 * 60 * 24)),
    hours: Math.floor((diff / (1000 * 60 * 60)) % 24),
    mins: Math.floor((diff / (1000 * 60)) % 60),
    secs: Math.floor((diff / 1000) % 60),
  }
}

const pad2 = (n: number) => String(n).padStart(2, '0')

/** 单个翻页数字 — CSS 3D 翻转动画 */
function FlipDigit({ value, prevValue }: { value: string; prevValue: string }) {
  const isFlipping = value !== prevValue
  return (
    <View className='flip-digit'>
      {/* 静态当前数字 */}
      <Text className={`flip-digit-num ${isFlipping ? 'flip-out' : ''}`}>{prevValue}</Text>
      {isFlipping && (
        <>
          {/* 上半部分翻下 */}
          <View className='flip-digit-top'>
            <Text className='flip-digit-text'>{prevValue}</Text>
          </View>
          {/* 下半部分 */}
          <View className='flip-digit-bottom'>
            <Text className='flip-digit-text'>{value}</Text>
          </View>
        </>
      )}
      <Text className={`flip-digit-new ${isFlipping ? 'flip-in' : ''}`}>{value}</Text>
    </View>
  )
}

/** 时间单元：两位数字 + 标签 */
function FlipUnit({ value, label }: { value: string; label: string }) {
  const [prevVal, setPrevVal] = useState(value)
  // 数字变化时触发翻转
  useEffect(() => { if (value !== prevVal) setPrevVal(value) }, [value])
  return (
    <View className='flip-unit'>
      <View className='flip-unit-digits'>
        <FlipDigit value={value[0]} prevValue={prevVal[0]} />
        <FlipDigit value={value[1]} prevValue={prevVal[1]} />
      </View>
      <Text className='flip-unit-label'>{label}</Text>
    </View>
  )
}

/** 世界杯倒计时横幅 */
function WorldCupCountdown() {
  const cd = getCountdown()
  const d = pad2(cd.days)
  const h = pad2(cd.hours)
  const m = pad2(cd.mins)
  const s = pad2(cd.secs)
  // 用 ref 追踪上一秒值来触发翻转
  const prevRef = useRef({ d, h, m, s })
  const [, force] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      prevRef.current = { d, h, m, s }
      force(n => n + 1)
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  const prev = prevRef.current
  return (
    <View className='countdown-banner'>
      <View className='countdown-banner-bg' />
      <View className='countdown-header'>
        <Text className='countdown-title-icon'>🏆</Text>
        <Text className='countdown-title'>2026 世界杯开幕倒计时</Text>
      </View>
      <View className='countdown-flips'>
        <FlipUnit value={d} label='天' />
        <View className='flip-sep'><Text className='flip-dot'></Text></View>
        <FlipUnit value={h} label='时' />
        <View className='flip-sep'><Text className='flip-dot'></Text></View>
        <FlipUnit value={m} label='分' />
        <View className='flip-sep'><Text className='flip-dot'></Text></View>
        <FlipUnit value={s} label='秒' />
      </View>
    </View>
  )
}

export default function Leaderboard() {
  const {
    activeTab, activeRound, sortMode, sortBy, sortOrder, entries, topUsers,
    setActiveTab, setActiveRound, setSortMode, setSort, fetchLeaderboard,
  } = useLeaderboardStore()
  const loginReady = useUserStore((s) => s.loginReady)
  const homeStats = useMatchStore((s) => s.homeStats)
  // 多联赛：当前选中联赛（切换后重新拉取排行）
  const currentLeagueId = useLeagueStore((s) => s.currentLeagueId)
  const fetchLeagues = useLeagueStore((s) => s.fetchLeagues)
  // 动态计算列表高度，解决 iOS 设备底部空白问题
  const [listHeight, setListHeight] = useState<string>('')

  useEffect(() => {
    fetchLeagues()
  }, [fetchLeagues])

  useEffect(() => {
    if (loginReady) fetchLeaderboard()
  }, [loginReady, currentLeagueId])

  // 动态测量 Tabs+Controls 高度（高度随 Tab/轮次变化）
  useEffect(() => {
    const timer = setTimeout(() => {
      try {
        const query = Taro.createSelectorQuery()
        query.select('.lb-tabs').boundingClientRect()
        query.select('.lb-controls').boundingClientRect()
        query.exec((res) => {
          const tabRect = res[0]
          const ctrlRect = res[1]
          if (!tabRect || !ctrlRect) { setListHeight('calc(100vh - 290px)'); return }
          const { windowHeight } = Taro.getSystemInfoSync()
          setListHeight(`${Math.max(windowHeight - tabRect.height - ctrlRect.height - 20, 200)}px`)
        })
      } catch { setListHeight('calc(100vh - 290px)') }
    }, 300)
    return () => clearTimeout(timer)
  }, [activeTab, activeRound])

  // 分享给好友
  useShareAppMessage(() => ({
    title: 'AI 排行榜 · 谁是预测之王？',
    path: '/pages/leaderboard/index',
  }))

  // 分享到朋友圈
  useShareTimeline(() => ({
    title: 'AI 排行榜 · 谁是预测之王？',
    query: '',
  }))

  /** 切换排序 */
  const handleSortClick = (by: SortByType) => {
    if (by === 'default') {
      setSortMode('composite')
    } else if (by === sortBy && sortMode === 'field') {
      setSort(by, sortOrder === 'desc' ? 'asc' : 'desc')
    } else {
      setSort(by, 'desc')
    }
  }

  return (
    <View className='lb-page'>
      {/* Tab 切换 */}
      <View className='lb-tabs'>
        {TABS.map((tab) => (
          <View
            key={tab.key}
            className={`lb-tab ${activeTab === tab.key ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.key)}
          >
            <Text>{tab.label}</Text>
          </View>
        ))}
      </View>

      {/* 轮次筛选 + 排序控件 */}
      <View className='lb-controls'>
        <View className='lb-rounds'>
          {ROUNDS.map((round) => (
            <View
              key={round}
              className={`lb-round ${activeRound === round ? 'active' : ''}`}
              onClick={() => setActiveRound(round)}
            >
              <Text>{round}</Text>
            </View>
          ))}
        </View>

        {(activeTab === 'ai' || activeTab === 'human') && (
          <View className='lb-sort-bar'>
            {SORT_OPTIONS.map((opt) => {
              const isActive = (opt.by === 'default' && sortMode === 'composite')
                || (opt.by !== 'default' && sortBy === opt.by && sortMode === 'field')
              return (
                <View
                  key={opt.by}
                  className={`lb-sort-btn ${isActive ? 'active' : ''}`}
                  onClick={() => handleSortClick(opt.by)}
                >
                  <Text>{opt.label}</Text>
                  {opt.by !== 'default' && (
                    <Text className={`lb-sort-arrow ${isActive ? (sortOrder === 'desc' ? 'desc' : 'asc') : ''}`}>
                      {isActive ? (sortOrder === 'desc' ? '↓' : '↑') : '↕'}
                    </Text>
                  )}
                </View>
              )
            })}
          </View>
        )}
      </View>

      {/* 世界杯倒计时翻页：仅在没有预测数据时显示 */}
      {entries.length === 0 && topUsers.length === 0 && (
        <WorldCupCountdown />
      )}

      {/* 人类排行 */}
      {activeTab === 'human' && (
        <ScrollView scrollY className='lb-list' style={listHeight ? { height: listHeight } : undefined}>
          {topUsers.length === 0 && !useLeaderboardStore.getState().loading && (
            <View className='rich-empty'>
              <View className='rich-empty-glow' />
              <Text className='rich-empty-icon'>👥</Text>
              <Text className='rich-empty-title'>暂无投票数据</Text>
              <Text className='rich-empty-desc'>比赛开始后，人类投票排行将在这里实时更新</Text>
            </View>
          )}
          {topUsers.map((item, idx) => {
            const isMe = !!item.is_me
            const hasResult = item.total > 0
            const rank = item.real_rank || idx + 1  // 使用真实排名
            return (
              <View
                key={item.user_id}
                className={`lb-item lb-item-clickable ${isMe ? 'lb-item-me' : ''} ${rank <= 3 && !isMe ? 'lb-item-top3' : ''}`}
                onClick={() => {
                  // 非VIP只能看自己的预测
                  if (!isMe && !useUserStore.getState().isVip) return
                  Taro.navigateTo({ url: `/pages/vote-history/index?userId=${item.user_id}` })
                }}
              >
                <View className='lb-rank'>
                  <Text className='lb-rank-badge'>#{rank}</Text>
                </View>

                <UserAvatar avatarUrl={item.avatar_url} nickname={item.nickname} />

                <View className='lb-body'>
                  <View className='lb-header'>
                    <Text className='lb-name'>{item.nickname}{isMe ? ' (我)' : ''}</Text>
                  </View>
                  <View className='lb-metrics'>
                    <View className='metric-row'>
                      <View className='metric-group'>
                        {hasResult ? (
                          <>
                            <Text className='metric-text'>比分命中率：</Text>
                            <Text className={`metric-num metric-ok`}>{item.score_accuracy}%</Text>
                          </>
                        ) : (
                          <>
                            <Text className='metric-text'>比分：</Text>
                            <Text className={`metric-num metric-none`}>-</Text>
                          </>
                        )}
                      </View>
                      {hasResult && (
                        <View className='metric-group'>
                          <Text className='metric-text'>胜负命中率：</Text>
                          <Text className={`metric-num metric-sub`}>{item.result_accuracy}%</Text>
                        </View>
                      )}
                    </View>
                    <View className='metric-row'>
                      {item.total > 0 && (
                        <View className='metric-group'>
                          <Text className='metric-text'>投票：</Text>
                          <Text className='metric-total'>{item.total}场</Text>
                        </View>
                      )}
                      {item.settled > 0 && (
                        <View className='metric-group'>
                          <Text className='metric-text'>已结束：</Text>
                          <Text className='metric-total'>{item.settled}场</Text>
                        </View>
                      )}
                    </View>
                  </View>
                </View>
              </View>
            )
          })}
          <View className='lb-footnote'>
            <Text className='lb-footnote-text'>* 比分/胜负命中率仅对已结束的比赛进行统计</Text>
          </View>
        </ScrollView>
      )}

      {/* AI 排行：纯 AI 列表 */}
      {activeTab === 'ai' && (
        <ScrollView scrollY className='lb-list' style={listHeight ? { height: listHeight } : undefined}>
          {entries.length === 0 && !useLeaderboardStore.getState().loading && (
            <View className='rich-empty'>
              <View className='rich-empty-glow' />
              <Text className='rich-empty-icon'>🏆</Text>
              <Text className='rich-empty-title'>排行榜即将揭晓</Text>
              <Text className='rich-empty-desc'>比赛开始后，AI 预测实力排行将在这里实时更新</Text>
              <Text className='rich-empty-tip'>
                💡 已有 {homeStats?.active_ai_models ?? 0} 个 AI 模型蓄势待发
              </Text>
            </View>
          )}
          {entries.map((entry, idx) => {
            const hasResult = entry.total > 0
            const rank = idx + 1
            return (
              <View key={idx} className={`lb-item ${rank <= 3 ? 'lb-item-top3' : ''} lb-item-clickable`} onClick={() => Taro.navigateTo({ url: `/pages/ai-detail/index?modelId=${entry.model_id}${currentLeagueId != null ? `&leagueId=${currentLeagueId}` : ''}` })}>
                <View className='lb-rank'>
                  <Text className='lb-rank-badge'>#{rank}</Text>
                </View>
                <ModelAvatar name={entry.name || ''} size={rank === 1 ? 'lb-av-top1' : rank <= 3 ? 'lb-av-top3' : 'lb-av'} />
                <View className='lb-body'>
                  <View className='lb-header'>
                    <Text className='lb-name'>{entry.name}</Text>
                    <View className='lb-tags'>
                      {renderStyleTags(entry.style_tags)}
                    </View>
                  </View>
                  <View className='lb-metrics'>
                    <View className='metric-row'>
                      <View className='metric-group'>
                        {hasResult ? (
                          <>
                            <Text className='metric-text'>比分命中率：</Text>
                            <Text className={`metric-num metric-ok`}>{entry.score_accuracy}%</Text>
                          </>
                        ) : (
                          <>
                            <Text className='metric-text'>比分：</Text>
                            <Text className={`metric-num ${entry.total > 0 ? 'metric-pending' : 'metric-none'}`}>-</Text>
                          </>
                        )}
                      </View>
                      {(hasResult || entry.total > 0) && (
                        <View className='metric-group'>
                          {hasResult ? (
                            <>
                              <Text className='metric-text'>胜负命中率：</Text>
                              <Text className={`metric-num metric-sub`}>{entry.result_accuracy}%</Text>
                            </>
                          ) : (
                            <>
                              <Text className='metric-text'>胜负命中率：</Text>
                              <Text className={`metric-num metric-pending`}>--</Text>
                            </>
                          )}
                        </View>
                      )}
                    </View>
                    <View className='metric-row'>
                      {entry.total > 0 && (
                        <View className='metric-group'>
                          <Text className='metric-text'>总预测：</Text>
                          <Text className='metric-total'>{entry.total}场</Text>
                        </View>
                      )}
                      {entry.settled > 0 && (
                        <View className='metric-group'>
                          <Text className='metric-text'>已结束：</Text>
                          <Text className='metric-total'>{entry.settled}场</Text>
                        </View>
                      )}
                    </View>
                  </View>
                </View>
              </View>
            )
          })}
          <View className='lb-footnote'>
            <Text className='lb-footnote-text'>* 比分/胜负命中率仅对已结束的比赛进行统计</Text>
          </View>
        </ScrollView>
      )}
    </View>
  )
}
