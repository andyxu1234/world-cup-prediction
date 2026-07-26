import type { UserConfigExport } from '@tarojs/cli'

export default {
  logger: {
    quiet: false,
    stats: true
  },
  mini: {},
  h5: {
    devServer: {
      // 关闭 webpack dev server 的目录索引，避免访问 / 时返回 dist 文件列表
      static: { serveIndex: false },
      // 单页应用路由回退：所有路径都落到 index.html，由 React Router 处理
      historyApiFallback: { rewrites: [{ from: /^\/.*/, to: '/index.html' }] },
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    }
  }
} satisfies UserConfigExport
