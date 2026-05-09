# 世界杯预测小程序广告接入方案

## Goal

接入两个广告位：首页信息流原生模板广告、赛事详情页激励视频解锁 AI 预测。

## 广告位 ID

| 广告位 | 类型 | unit-id |
|--------|------|---------|
| 首页信息流 | 原生模板广告（横板卡片） | `adunit-cc88b6b1fc979d32` |
| 赛事详情解锁 | 激励视频广告 | `adunit-5106ca47d68823d5` |

## 用户确认的关键规则

- 已结束的比赛不需要看广告
- AI 预测未生成的比赛不需要看广告
- 同一场比赛只需解锁一次（本地缓存），后续进入直接展示
- 开屏广告已砍掉，由微信平台封面广告覆盖

## Plan

### Step 1: 创建广告工具模块 `client/src/utils/ad.ts`（新建）

- 集中管理 2 个广告位 `unit-id` 常量（feed / rewardedVideo）
- 封装 `createRewardedVideoAd()` 单例工厂
- 封装 `showRewardedVideo()` Promise 化方法，返回 `{ completed: boolean }`
- 封装 `isAdUnlocked(matchId)` / `setAdUnlocked(matchId)` 用 `Taro.setStorageSync` 持久化
- **Verify:** TS import 无报错

### Step 2: 首页信息流广告 `client/src/pages/index/index.tsx` + `index.scss`

- `matches.map()` 中 `(idx + 1) % 5 === 0` 时插入广告：
  ```tsx
  {(idx + 1) % 5 === 0 && (
    <View className='ad-feed-wrap'>
      <ad-custom unit-id={AD_UNIT_IDS.feed} />
    </View>
  )}
  ```
- SCSS `.ad-feed-wrap` 与赛事卡片同宽/圆角/间距，加"广告"小标签
- **Verify:** 列表每 5 张卡片出现一条广告位

### Step 3: 赛事详情激励视频 `client/src/pages/match-detail/index.tsx` + `index.scss`

- 新增 state: `predictionsUnlocked`
- 进入页面判断：
  - `isAdUnlocked(matchId)` → 直接解锁
  - `currentMatch.status === 'finished'` → 直接解锁
  - `predictions.length === 0` → 直接解锁（无预测数据）
  - 否则 → 显示锁定状态
- 锁定状态：毛玻璃遮罩 + 锁图标 + "观看短视频解锁全部 AI 预测"按钮
- 点击按钮 → `showRewardedVideo()` → 成功后 `setAdUnlocked(matchId)` + 解锁
- AI 综合分析卡片（summary-card）保持可见作为预览
- 投票区域始终可见
- SCSS: `.ad-lock-overlay` 毛玻璃 + `.ad-unlock-btn` 渐变按钮
- **Verify:** 未解锁 → 遮罩 → 观看视频 → 解锁；再次进入同场比赛无需看广告；已结束比赛直接展示

### Step 4: 边界情况处理

- 激励视频加载失败 → 直接解锁（降级策略）
- 激励视频 3 秒超时未加载 → 直接解锁
- **Verify:** 各异常场景手动验证

## Risks & mitigations

| 风险 | 缓解 |
|------|------|
| ad-custom 在 Taro 中未正确映射 | 先最小示例验证；必要时用 ad 组件降级 |
| 激励视频广告位未填充 | 3 秒超时直接解锁 |
| 用户流失 | 已解锁状态持久化；已结束/无预测免广告 |

## Rollback

在 `ad.ts` 中将 `AD_UNIT_IDS` 全部设为空字符串，广告组件不加载，零代码回滚。
