import type { UserConfigExport } from '@tarojs/cli'

export default {
  logger: {
    quiet: false,
    stats: true
  },
  defineConstants: {
    API_BASE_URL: '"http://127.0.0.1:8000"'
  },
  mini: {},
  h5: {
    devServer: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true
        }
      }
    }
  }
} satisfies UserConfigExport
