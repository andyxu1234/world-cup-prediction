export default defineAppConfig({
  lazyCodeLoading: 'requiredComponents',
  pages: [
    'pages/index/index',
    'pages/match-detail/index',
    'pages/leaderboard/index',
    'pages/data/index',
    'pages/team-detail/index',
    'pages/player-detail/index',
    'pages/profile/index',
    'pages/profile-setup/index',
    'pages/vote-history/index',
    'pages/ai-detail/index',
    'pages/about/index',
    'pages/disclaimer/index',
    'pages/contact/index',
    'pages/webview/index',
    'pages/admin/index'
  ],
  window: {
    backgroundTextStyle: 'light',
    navigationBarBackgroundColor: '#ffffff',
    navigationBarTitleText: 'AI 预测世界杯',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f5f7fa'
  },
  tabBar: {
    color: '#94a3b8',
    selectedColor: '#10b981',
    backgroundColor: '#ffffff',
    borderStyle: 'white',
    list: [
      {
        pagePath: 'pages/index/index',
        text: '首页',
        iconPath: 'assets/tab-home.png',
        selectedIconPath: 'assets/tab-home-active.png'
      },
      {
        pagePath: 'pages/leaderboard/index',
        text: '排行',
        iconPath: 'assets/tab-rank.png',
        selectedIconPath: 'assets/tab-rank-active.png'
      },
      {
        pagePath: 'pages/data/index',
        text: '数据',
        iconPath: 'assets/tab-data.png',
        selectedIconPath: 'assets/tab-data-active.png'
      },
      {
        pagePath: 'pages/profile/index',
        text: '我的',
        iconPath: 'assets/tab-me.png',
        selectedIconPath: 'assets/tab-me-active.png'
      }
    ]
  }
})
