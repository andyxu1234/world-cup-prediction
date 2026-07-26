/**
 * 时间处理工具
 *
 * 后端 match_time 一律按北京时间（UTC+8）存储（naive datetime，字符串形如
 * "2026-07-22 00:00:00" 或 "2026-07-22T00:00:00"）。为避免受设备本地时区影响，
 * 这里统一把字符串当作北京时间的“墙上时刻”处理，显示时用 UTC 方法还原，
 * 保证无论用户设备时区如何，展示的都与懂球帝等国内 App 一致（北京时间）。
 */

const WEEK_DAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/**
 * 把后端返回的时间字符串解析为一个内部 Date（其 UTC 分量即北京时间）。
 * 同时兼容带时区后缀（如 ...Z / +08:00）的情况，会自动换算回北京时间。
 */
export function parseBeijingTime(timeStr: string | null | undefined): Date | null {
  if (!timeStr) return null
  const str = timeStr.trim()

  // 情况1：带时区信息（如 ...Z 或 +08:00），按真实时刻解析后换算到北京时间
  if (/[zZ]$|[+-]\d{2}:?\d{2}$/.test(str)) {
    const d = new Date(str)
    if (Number.isNaN(d.getTime())) return null
    const beijing = new Date(d.getTime() + 8 * 60 * 60 * 1000)
    return new Date(
      Date.UTC(
        beijing.getUTCFullYear(),
        beijing.getUTCMonth(),
        beijing.getUTCDate(),
        beijing.getUTCHours(),
        beijing.getUTCMinutes(),
        beijing.getUTCSeconds(),
      ),
    )
  }

  // 情况2：无时区后缀（后端按北京时间存储），直接按墙上时刻解析
  const [datePart, timePart = '00:00:00'] = str.replace('T', ' ').split(' ')
  const [y, m, d] = datePart.split('-').map(Number)
  const [h, min, s = 0] = timePart.replace(/[zZ]$/, '').split(':').map(Number)
  if ([y, m, d, h, min].some((n) => Number.isNaN(n))) return null
  return new Date(Date.UTC(y, m - 1, d, h, min, s))
}

/** 格式化为：7月22日 周三 凌晨12:00 形式（北京时间） */
export function formatMatchTime(timeStr: string | null | undefined): string {
  const d = parseBeijingTime(timeStr)
  if (!d) return '待定'
  const month = d.getUTCMonth() + 1
  const day = d.getUTCDate()
  const weekday = WEEK_DAYS[d.getUTCDay()]
  const hour24 = d.getUTCHours()
  const min = d.getUTCMinutes().toString().padStart(2, '0')
  const period =
    hour24 < 6 ? '凌晨' : hour24 < 12 ? '上午' : hour24 < 14 ? '中午' : hour24 < 18 ? '下午' : '晚上'
  const hour12 = hour24 === 0 ? 12 : hour24 > 12 ? hour24 - 12 : hour24
  return `${month}月${day}日 ${weekday} ${period}${hour12.toString().padStart(2, '0')}:${min}`
}

/** 格式化为：MM-DD HH:mm 形式（北京时间） */
export function formatDateTime(timeStr: string | null | undefined): string {
  const d = parseBeijingTime(timeStr)
  if (!d) return '—'
  const month = `${d.getUTCMonth() + 1}`.padStart(2, '0')
  const day = `${d.getUTCDate()}`.padStart(2, '0')
  const hour = `${d.getUTCHours()}`.padStart(2, '0')
  const min = `${d.getUTCMinutes()}`.padStart(2, '0')
  return `${month}-${day} ${hour}:${min}`
}

/** 取得当前北京时间对应的 YYYY-MM-DD（用于“今日/明日”日期筛选） */
export function getBeijingDateStr(date: Date = new Date()): string {
  return new Date(date.getTime() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10)
}
