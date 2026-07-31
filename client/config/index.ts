import path from 'path'
import { defineConfig } from '@tarojs/cli'

export default defineConfig(async (merge, { command, mode }) => {
  const baseConfig = {
    projectName: 'world-cup-predictor',
    date: '2026-7-31',
    designWidth: 750,
    deviceRatio: { 640: 2.34 / 2, 750: 1, 828: 1.81 / 2, 375: 2 / 1 },
    sourceRoot: 'src',
    outputRoot: 'dist',
    // 路径别名：Taro 4 不会自动读取 tsconfig 的 paths，必须显式声明
    alias: {
      '@': path.resolve(process.cwd(), 'src')
    },
    plugins: ['@tarojs/plugin-framework-react'],
    defineConstants: {},
    copy: { patterns: [], options: {} },
    framework: 'react',
    compiler: 'webpack5',
    cache: { enable: false },
    // 全局 SCSS 变量自动注入到每个页面样式，避免 $bg-primary 等 Undefined variable
    sass: { resource: ['src/styles/variables.scss'] },
    mini: {
      webpackChain(chain) {},
      postcss: {
        pxtransform: { enable: true, config: {} }
      }
    },
    h5: {
      publicPath: '/',
      staticDirectory: 'static',
      output: {
        filename: 'js/[name].[hash:8].js',
        chunkFilename: 'js/[name].[chunkhash:8].js'
      },
      miniCssExtractPluginOption: {
        ignoreOrder: true,
        filename: 'css/[name].[hash].css'
      },
      postcss: { autoprefixer: { enable: true } },
      devServer: {
        port: 10086,
        host: '0.0.0.0',
        open: false,
        https: false
      }
    }
  }

  if (process.env.NODE_ENV === 'development') {
    // 开发环境无需特殊覆盖
  }

  return baseConfig
})
