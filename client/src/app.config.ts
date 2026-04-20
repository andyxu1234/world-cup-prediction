export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/match-detail/index',
    'pages/leaderboard/index',
    'pages/face-slap/index',
    'pages/profile/index',
    'pages/share-card/index',
    'pages/vote-history/index',
    'pages/about/index'
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
        pagePath: 'pages/face-slap/index',
        text: '打脸',
        iconPath: 'assets/tab-face.png',
        selectedIconPath: 'assets/tab-face-active.png'
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
