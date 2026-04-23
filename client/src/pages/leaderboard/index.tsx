import { useEffect, useState } from 'react'
import { View, Text, ScrollView, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useLeaderboardStore, useUserStore } from '@/stores'
import type { MixedRankItem } from '@/stores'
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
  { key: 'human' as const, label: '人机对决' },
]

const ROUNDS = ['全部', '小组赛', '淘汰赛']

/** 排序按钮配置 */
type SortByType = 'default' | 'result_accuracy' | 'score_accuracy'
const SORT_OPTIONS: { by: SortByType; label: string }[] = [
  { by: 'default', label: '综合' },
  { by: 'result_accuracy', label: '胜率' },
  { by: 'score_accuracy', label: '比分' },
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
  // 预设头像：preset://emoji 格式
  if (fullUrl && fullUrl.startsWith('preset://')) {
    const emoji = fullUrl.replace('preset://', '')
    return <View className='model-av lb-av preset-avatar'>{emoji}</View>
  }
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

/** 混合排行条目（人机合一） */
function MixedRankRow({ item, rank }: { item: MixedRankItem; rank: number }) {
  const isMe = !!item.isMe
  const hasResult = item.total > 0

  return (
    <View key={`${item.type}-${item.user_id ?? item.model_id}`} className={`lb-item ${isMe ? 'lb-item-me' : ''} ${rank <= 3 && !isMe ? 'lb-item-top3' : ''}`}>
      <View className='lb-rank'>
        <Text className='lb-rank-badge'>#{rank}</Text>
      </View>

      {item.type === 'human' ? (
        <UserAvatar avatarUrl={item.avatar_url} nickname={item.nickname} />
      ) : (
        <ModelAvatar name={item.name || ''} size={rank === 1 && !isMe ? 'lb-av-top1' : rank <= 3 && !isMe ? 'lb-av-top3' : 'lb-av'} />
      )}

      <View className='lb-body'>
        <View className='lb-header'>
          <Text className='lb-name'>{item.name}{isMe ? ' (我)' : ''}</Text>
          {item.type === 'ai' && (
            <View className='lb-tags'>
              {renderStyleTags(item.style_tags)}
            </View>
          )}
        </View>
        <View className='lb-metrics'>
          <View className='metric-group'>
            {hasResult ? (
              <>
                <Text className='metric-text'>胜率：</Text>
                <Text className={`metric-num metric-ok`}>{item.result_accuracy}%</Text>
              </>
            ) : (
              <>
                <Text className='metric-text'>胜率：</Text>
                <Text className={`metric-num metric-none`}>-</Text>
              </>
            )}
          </View>
          {hasResult && (
            <View className='metric-group'>
              <Text className='metric-text'>比分命中：</Text>
              <Text className={`metric-num metric-sub`}>{item.score_accuracy}%</Text>
            </View>
          )}
          {item.total > 0 && (
            <View className='metric-group'>
              <Text className='metric-text'>{item.type === 'human' ? '投票' : '预测场次'}：</Text>
              <Text className='metric-total'>{item.total}{item.type === 'human' ? '场' : '场'}</Text>
            </View>
          )}
        </View>
      </View>
    </View>
  )
}

export default function Leaderboard() {
  const {
    activeTab, activeRound, sortMode, sortBy, sortOrder, entries, humanData, mixedRank,
    setActiveTab, setActiveRound, setSortMode, setSort, fetchLeaderboard,
  } = useLeaderboardStore()

  useEffect(() => {
    fetchLeaderboard()
  }, [])

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

      {/* 人机对决特有：人类统计卡片 */}
      {activeTab === 'human' && humanData && (
        <View className='human-card'>
          <View className='human-av'>👥</View>
          <View className='human-info'>
            <Text className='human-name'>{humanData.human.name}</Text>
            <View className='human-metrics'>
              <View className='metric-item'>
                <Text className='metric-num metric-ok'>{humanData.human.result_accuracy}%</Text>
                <Text className='metric-label'>胜率</Text>
              </View>
              <Text className='metric-divider'>·</Text>
              <View className='metric-item'>
                <Text className='metric-num metric-sub'>{humanData.human.score_accuracy}%</Text>
                <Text className='metric-label'>比分</Text>
              </View>
            </View>
          </View>
          <View className='human-votes'>
            <Text className='human-votes-num mono'>{humanData.human.total}</Text>
            <Text className='human-votes-label'>投票</Text>
          </View>
        </View>
      )}

      {/* 人机对决：混合排行列表 */}
      {activeTab === 'human' && (
        <ScrollView scrollY className='lb-list'>
          {mixedRank.length === 0 && !useLeaderboardStore.getState().loading && (
            <View className='empty'>
              <Text className='empty-icon'>⚔️</Text>
              <Text className='empty-text'>暂无人机对战数据</Text>
            </View>
          )}
          {mixedRank.map((item, idx) => (
            <MixedRankRow key={`${item.type}-${item.user_id ?? item.model_id}`} item={item} rank={idx + 1} />
          ))}
        </ScrollView>
      )}

      {/* AI 排行：纯 AI 列表 */}
      {activeTab === 'ai' && (
        <ScrollView scrollY className='lb-list'>
          {entries.length === 0 && !useLeaderboardStore.getState().loading && (
            <View className='empty'>
              <Text className='empty-icon'>🏆</Text>
              <Text className='empty-text'>暂无排行数据</Text>
            </View>
          )}
          {entries.map((entry, idx) => {
            const hasResult = entry.total > 0
            const rank = idx + 1
            return (
              <View key={idx} className={`lb-item ${rank <= 3 ? 'lb-item-top3' : ''}`}>
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
                    <View className='metric-group'>
                      {hasResult ? (
                        <>
                          <Text className='metric-text'>胜率：</Text>
                          <Text className={`metric-num metric-ok`}>{entry.result_accuracy}%</Text>
                        </>
                      ) : (
                        <>
                          <Text className='metric-text'>胜率：</Text>
                          <Text className={`metric-num ${entry.total > 0 ? 'metric-pending' : 'metric-none'}`}>-</Text>
                        </>
                      )}
                    </View>
                    {(hasResult || entry.total > 0) && (
                      <View className='metric-group'>
                        {hasResult ? (
                          <>
                            <Text className='metric-text'>比分命中：</Text>
                            <Text className={`metric-num metric-sub`}>{entry.score_accuracy}%</Text>
                          </>
                        ) : (
                          <>
                            <Text className='metric-text'>比分命中：</Text>
                            <Text className={`metric-num metric-pending`}>--</Text>
                          </>
                        )}
                      </View>
                    )}
                    {entry.total > 0 && (
                      <View className='metric-group'>
                        <Text className='metric-text'>预测场次：</Text>
                        <Text className='metric-total'>{entry.total}场</Text>
                      </View>
                    )}
                  </View>
                </View>
              </View>
            )
          })}
        </ScrollView>
      )}
    </View>
  )
}
