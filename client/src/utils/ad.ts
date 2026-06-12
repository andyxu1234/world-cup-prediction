import Taro from '@tarojs/taro'

/** 广告位 ID 常量 */
export const AD_UNIT_IDS = {
  feed: 'adunit-cc88b6b1fc979d32',
  rewardedVideo: 'adunit-5106ca47d68823d5',
} as const

/** 广告结果 */
export interface AdResult {
  completed: boolean  // 用户是否完整看完视频
  available: boolean  // 广告是否可用（有广告返回）
}

// ==================== 激励视频广告 ====================

/**
 * 创建激励视频广告实例
 * 必须在页面组件内调用，确保广告与页面绑定
 * @returns 广告实例和清理函数
 */
export function createRewardedVideoAd() {
  const ad = Taro.createRewardedVideoAd({ adUnitId: AD_UNIT_IDS.rewardedVideo })

  const destroy = () => {
    try {
      ad.destroy()
    } catch {
      // ignore destroy errors
    }
  }

  return { ad, destroy }
}

/**
 * 展示激励视频广告（使用已创建的广告实例）
 * @param ad 已创建的广告实例（必须在当前页面创建）
 * @returns completed: 用户是否完整看完视频, available: 广告是否可用
 */
export function showRewardedVideo(ad: any): Promise<AdResult> {
  return new Promise((resolve) => {
    const onRes = (res: any) => {
      cleanup()
      resolve({ completed: res?.isEnded === true, available: true })
    }

    const onErr = (err: any) => {
      console.warn('[Ad] Rewarded video error:', err)
      cleanup()
      // 区分无广告返回和其他错误
      // err.errCode === 1004 表示无广告返回
      const isNoAd = err?.errCode === 1004
      resolve({ completed: false, available: !isNoAd })
    }

    const cleanup = () => {
      ad.offClose(onRes)
      ad.offError(onErr)
    }

    ad.onClose(onRes)
    ad.onError(onErr)

    ad.show().catch(() => {
      ad.load()
        .then(() => ad.show())
        .catch((loadErr: any) => {
          console.warn('[Ad] Rewarded video load failed:', loadErr)
          cleanup()
          const isNoAd = loadErr?.errCode === 1004
          resolve({ completed: false, available: !isNoAd })
        })
    })
  })
}

// ==================== 解锁状态缓存 ====================

const STORAGE_KEY = 'ad_unlocked_matches'

/** 检查某场比赛的 AI 预测是否已解锁 */
export function isAdUnlocked(matchId: number): boolean {
  try {
    const list: number[] = Taro.getStorageSync(STORAGE_KEY) || []
    return list.includes(matchId)
  } catch {
    return false
  }
}

/** 标记某场比赛的 AI 预测已解锁 */
export function setAdUnlocked(matchId: number): void {
  try {
    const list: number[] = Taro.getStorageSync(STORAGE_KEY) || []
    if (!list.includes(matchId)) {
      list.push(matchId)
      Taro.setStorageSync(STORAGE_KEY, list)
    }
  } catch {
    // storage write failed, ignore
  }
}
