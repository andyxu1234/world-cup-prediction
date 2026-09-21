# 前端技术栈整理（world-cup-predictor / client）

> 整理日期：2026-08-11
> 配套图示：`docs/diagrams/frontend-stack.svg`

本项目前端是一套 **Taro 4 + React + TypeScript** 的轻量多端方案：没有引入重型 UI 库 / 状态管理 / 请求库，网络层和组件基本都靠 Taro 自带能力 + 自封装，整体很克制。

## 一、核心框架

| 技术 | 版本 | 说明 |
|---|---|---|
| **Taro** | 4.1.11 | 多端统一框架（React 语法），一套代码编译到多端 |
| **React** | 18.3.1 | UI 框架，`react-dom` 同版本 |
| **TypeScript** | 5.4 | 类型系统，配置在 `tsconfig.json` |

## 二、编译 / 构建链

- **webpack5**（Taro 4 默认编译器）
- **Babel**：`babel-preset-taro` + `@babel/preset-react` / `preset-typescript` / `transform-runtime`
- **Sass/SCSS**：`sass` 1.77，全局变量通过 `config/index.ts` 的 `sass.resource` 自动注入到每个页面（`src/styles/variables.scss`），避免 `$` 变量未定义
- **px 适配**：`pxtransform`（设计稿 `designWidth: 750`，`deviceRatio` 已配 375/640/750/828）

## 三、多端目标（`package.json` scripts）

- 微信小程序 `weapp`（主端）、**H5**（网页版）、支付宝 `alipay`、百度 `swan`、头条 `tt`
- 编译器插件：`@tarojs/plugin-framework-react` 及各平台 `plugin-platform-*`

## 四、状态管理

- **zustand** 4.5 —— 轻量 store，替代 Redux；`src/stores/index.ts` 里按"联赛筛选 / 用户 / 预测"等拆成多个 store，并用 `Taro.getStorageSync` 做本地缓存持久化

## 五、网络层（自封装，无第三方请求库）

- **`Taro.request`** 封装在 `src/services/api.ts`：统一 `API_BASE_URL=/api/v1`，自动带 `Bearer` token、15s 超时、最多 1 次重试（`isRetryableError` 识别 timeout/network）
- **`Taro.uploadFile`** 用于头像上传
- 无 axios / umi-request

## 六、UI 与样式

- **`@tarojs/components`**（Taro 自带组件库）—— **未引入任何第三方 UI 库**（无 NutUI / Taro UI / Vant / Taroify）
- 自定义业务组件仅 2 个：`LeaguePicker`（联赛多选弹窗）、`LeagueSwitcher`
- 样式：`global.scss` + `variables.scss`，全局 SCSS 变量

## 七、路由

- **Taro 内置路由**（基于 `src/app.config.ts` 的 `pages` 注册 + `Taro.navigateTo` 跳转）—— **没有用 react-router**
- 15 个页面：`index / match-detail / leaderboard / data / team-detail / player-detail / profile / profile-setup / vote-history / ai-detail / about / disclaimer / contact / webview / admin / polymarket`
- 底部 tabBar 4 个（首页/排行/数据/我的），`lazyCodeLoading: 'requiredComponents'` 按需加载

## 八、存储 & 其它工程约定

- 本地存储：`Taro.getStorageSync` / `setStorageSync`（token、多选联赛）
- 路径别名：`@` → `src`（在 `config/index.ts` 的 `alias` **显式声明**，因为 Taro 4 不读 tsconfig 的 paths；`tsconfig.json` 也同步配了 `paths`）
- 环境：dev 接口 `http://127.0.0.1:8000`、H5 dev 端口 `10086`；生产接口 `https://marathoninfo.top`
- 后端对接：所有请求走 `/api/v1`（FastAPI，与后端 `main.py` 前缀一致）

## 九、可视化现状

- 代码里**没有引入** echarts / F2 / antv 等图表库（grep 命中的 `canvas` 只是国旗 SVG 与资源目录），预测结果目前以文本/表格形式呈现，尚未做图形化图表。

## 十、关键结论

1. 整体是"Taro 4 + React 18 + TS 5.4 + zustand + Sass"的轻量多端方案，依赖面很小。
2. 没有重型第三方库，组件、请求、路由、存储均基于 Taro 自带能力 + 少量自封装（`services/api.ts`、`stores/index.ts`、两个业务组件）。
3. 若后续要让独立 APK / Web 版更丰富（如加图表、换 UI 组件库），可优先考虑在"UI 与样式"层引入 Taro 兼容的组件库 + 图表库，不影响现有分层。
