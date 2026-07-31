import { useState } from 'react'
import { View, Text, Image } from '@tarojs/components'
import Taro from '@tarojs/taro'
import { useLeagueStore } from '@/stores'
import './index.scss'

/** 联赛多选触发器 + 弹窗，首页与排行页复用 */
export default function LeaguePicker() {
  const leagues = useLeagueStore((s) => s.leagues)
  const selectedLeagueIds = useLeagueStore((s) => s.selectedLeagueIds)
  const setSelectedLeagues = useLeagueStore((s) => s.setSelectedLeagues)

  const [pickerOpen, setPickerOpen] = useState(false)
  const [tempSelected, setTempSelected] = useState<number[]>(selectedLeagueIds)
  const [triggerRect, setTriggerRect] = useState<{ top: number; left: number; width: number; height: number } | null>(null)

  const currentLeague = leagues.find((l) => l.id === selectedLeagueIds[0]) || null
  const allSelected = leagues.length > 0 && selectedLeagueIds.length === leagues.length
  const multiSelected = selectedLeagueIds.length > 1

  const openPicker = () => {
    const query = Taro.createSelectorQuery()
    query.select('.league-trigger').boundingClientRect()
    query.exec((res) => {
      const rect = res[0]
      if (rect) {
        setTriggerRect({ top: rect.top, left: rect.left, width: rect.width, height: rect.height })
      }
      setTempSelected(selectedLeagueIds)
      setPickerOpen(true)
    })
  }
  const toggle = (id: number) => {
    setTempSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }
  const toggleAll = () => {
    setTempSelected((prev) => (prev.length === leagues.length ? [] : leagues.map((l) => l.id)))
  }
  const confirm = () => {
    // 不允许空选：至少保留一个赛事
    if (tempSelected.length === 0) {
      Taro.showToast({ title: '请至少选择一个赛事', icon: 'none', duration: 2000 })
      return
    }
    setSelectedLeagues(tempSelected)
    setPickerOpen(false)
  }

  const triggerLabel = allSelected
    ? `全部赛事（${selectedLeagueIds.length}）`
    : multiSelected
      ? `我的关注（${selectedLeagueIds.length}）`
      : currentLeague?.cn_name || '选择赛事'

  return (
    <>
      <View className='league-trigger no-avatar' onClick={openPicker}>
        <Text className='league-trigger-name'>{triggerLabel}</Text>
        <Text className='league-trigger-arrow'>▾</Text>
      </View>

      {pickerOpen && (
        <View className='league-modal-mask' onClick={() => setPickerOpen(false)}>
          <View
            className='league-modal'
            style={triggerRect ? { top: triggerRect.top + triggerRect.height + 8, left: triggerRect.left, minWidth: Math.max(triggerRect.width, 150) } : {}}
            onClick={(e) => e.stopPropagation()}
          >
            <View className='league-modal-list'>
              <View className='league-list'>
                {leagues.map((lg) => {
                  const checked = tempSelected.includes(lg.id)
                  return (
                    <View
                      key={lg.id}
                      className={`league-row ${checked ? 'checked' : ''}`}
                      onClick={() => toggle(lg.id)}
                    >
                      <View className='league-row-main'>
                        {lg.logo ? (
                          <Image className='league-row-logo' src={lg.logo} mode='aspectFit' />
                        ) : (
                          <View className='league-row-logo fallback'>
                            <Text className='league-row-logo-text'>{(lg.cn_name || '?').slice(0, 1)}</Text>
                          </View>
                        )}
                        <Text className='league-row-name'>{lg.cn_name || lg.name}</Text>
                      </View>
                      <View className='league-row-check'>
                        <View className='league-row-check-inner' />
                      </View>
                    </View>
                  )
                })}
              </View>
            </View>
            <View className='league-modal-ft'>
              <Text className='league-modal-all' onClick={toggleAll}>
                {tempSelected.length === leagues.length ? '清空' : '全选'}
              </Text>
              <View className='league-modal-btn confirm' onClick={confirm}>
                <Text>确定 ({tempSelected.length})</Text>
              </View>
            </View>
          </View>
        </View>
      )}
    </>
  )
}
