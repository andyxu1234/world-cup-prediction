import { useEffect, useState } from 'react'
import { View, Text, Image, ScrollView } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useUserStore } from '@/stores'
import { getUserVoteHistory, VoteHistoryItem } from '@/services/api'
import './index.scss'

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
  const key = result.replace('PredictionResult.', '')
  const map: Record<string, string> = {
    home_win: '主胜',
    away_win: '客胜',
    draw: '平局',
  }
  return map[key] ?? key
}

function getStatusBadge(item: VoteHistoryItem) {
  if (item.match_status !== 'finished') {
    return { className: 'tag-pending', text: '待揭晓' }
  }
  if (item.is_correct_score) {
    return { className: 'tag-score', text: '比分命中' }
  }
  if (item.is_correct_result) {
    return { className: 'tag-result', text: '胜负正确' }
  }
  return { className: 'tag-wrong', text: '未命中' }
}

function getTopbarClass(item: VoteHistoryItem): string {
  if (item.match_status !== 'finished') return 'pending'
  return item.is_correct_result ? 'correct' : 'wrong'
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

export default function VoteHistory() {
  const { user } = useUserStore()
  const [list, setList] = useState<VoteHistoryItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!user?.id) return
    setLoading(true)
    getUserVoteHistory(user.id, 50)
      .then(setList)
      .catch(() => Taro.showToast({ title: '加载失败', icon: 'none' }))
      .finally(() => setLoading(false))
  }, [user?.id])

  const correctResults = list.filter((i) => i.is_correct_result).length
  const correctScores = list.filter((i) => i.is_correct_score).length
  const accuracy = list.length > 0 ? Math.round((correctResults / list.length) * 100) : 0

  return (
    <View className='vote-history-page'>
      {/* 顶部统计区域 */}
      <View className='vh-hero'>
        <View className='vh-hero-glow' />
        <Text className='vh-hero-title'>我的战绩</Text>
        <Text className='vh-hero-sub'>预测表现 · 数据追踪</Text>
        <View className='vh-hero-stats'>
          <View className='vh-hero-stat'>
            <Text className='vh-hero-stat-num'>{list.length}</Text>
            <Text className='vh-hero-stat-label'>总预测比赛</Text>
          </View>
          <View className='vh-hero-stat'>
            <Text className='vh-hero-stat-num'>{accuracy}%</Text>
            <Text className='vh-hero-stat-label'>胜负命中率</Text>
          </View>
          <View className='vh-hero-stat'>
            <Text className='vh-hero-stat-num'>{correctScores}%</Text>
            <Text className='vh-hero-stat-label'>比分命中率</Text>
          </View>
        </View>
      </View>

      {/* 列表 */}
      <ScrollView scrollY className='vh-list' enableBackToTop>
        {loading ? (
          <View className='vh-loading'>加载中...</View>
        ) : list.length === 0 ? (
          <View className='vh-empty'>
            <View className='vh-empty-icon'>📋</View>
            <Text className='vh-empty-text'>还没有投票记录，快去预测比赛吧！</Text>
          </View>
        ) : (
          list.map((item) => {
            const badge = getStatusBadge(item)
            return (
              <View key={item.id} className='vh-card'>
                <View className='vh-card-hd'>
                  <Text className='vh-round'>{getRoundLabel(item.round)}</Text>
                  <View className='vh-badges'>
                    <Text className={`vh-badge ${badge.className}`}>{badge.text}</Text>
                  </View>
                </View>
                <View className='vh-card-bd'>
                  {/* 主队 vs 客队 */}
                  <View className='vh-teams'>
                    <View className='vh-team'>
                      {item.home_team_flag ? (
                        <Image
                          className='vh-team-flag'
                          src={item.home_team_flag}
                          mode='aspectFill'
                        />
                      ) : (
                        <View className='vh-team-flag-fallback'>⚽</View>
                      )}
                      <Text className='vh-team-name'>{item.home_team_name}</Text>
                    </View>

                    <View className='vh-score-area'>
                      {/* 比赛结果 */}
                      {item.match_home_score !== null ? (
                        <>
                          <Text className='vh-score mono'>{item.match_home_score} - {item.match_away_score}</Text>
                          <Text className='vh-score-label'>赛果</Text>
                        </>
                      ) : (
                        <>
                          <Text className='vh-vs mono'>VS</Text>
                          <Text className='vh-status-label'>
                            {item.match_status === 'live' ? '进行中' : '未开始'}
                          </Text>
                        </>
                      )}
                    </View>

                    <View className='vh-team'>
                      {item.away_team_flag ? (
                        <Image
                          className='vh-team-flag'
                          src={item.away_team_flag}
                          mode='aspectFill'
                        />
                      ) : (
                        <View className='vh-team-flag-fallback'>⚽</View>
                      )}
                      <Text className='vh-team-name'>{item.away_team_name}</Text>
                    </View>
                  </View>
                </View>
                <View className='vh-card-ft'>
                  <Text className='vh-prediction'>
                    预测：{getResultLabel(item.predicted_result)}
                    {item.predicted_home_score !== null
                      ? ` ${item.predicted_home_score}-${item.predicted_away_score}`
                      : ''}
                  </Text>
                  <View className='vh-time-wrapper'>
                    <Text className='vh-time-label'>比赛时间：</Text>
                    <Text className='vh-time'>
                      {item.match_time ? formatTime(item.match_time) : '--'}
                    </Text>
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
