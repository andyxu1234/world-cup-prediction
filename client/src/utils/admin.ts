/**
 * 管理员判断工具
 * 硬编码管理员 openid，仅指定用户可见管理后台
 */

// 管理员 openid 列表
const ADMIN_OPENIDS: string[] = [
  'o24Jj3Rhq9G6fE8ml0jwSRvKEHWk',
  'o24Jj3ee8VsFcTrNTDYowHFFs6QE',
]

/**
 * 判断当前用户是否是管理员
 * @param openid 用户的 openid
 * @returns 是否是管理员
 */
export function isAdmin(openid: string | undefined | null): boolean {
  if (!openid) return false
  return ADMIN_OPENIDS.includes(openid)
}
