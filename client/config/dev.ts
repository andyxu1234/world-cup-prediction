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
      // 单页应用路由回退：所有路径都落到 index.html，由 React Router 处理。
      // 必须用相对路径 './index.html'：webpack-dev-server 会按 publicPath 解析内存里
      // HtmlWebpackPlugin 注入的 index.html；绝对路径 '/index.html' 在 serveIndex:false
      // 下无法 resolve，会回退到 'Cannot GET /' 错误。
      historyApiFallback: { rewrites: [{ from: /^\/.*/, to: './index.html' }] },
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    }
  }
} satisfies UserConfigExport
