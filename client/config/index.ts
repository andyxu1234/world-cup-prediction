import { defineConfig } from '@tarojs/cli'
import devConfig from './dev'
import path from 'path'

export default defineConfig(async (merge) => {
  const baseConfig = {
    projectName: 'world-cup-predictor',
    date: '2026-4-10',
    designWidth: 750,
    deviceRatio: {
      640: 2.34 / 2,
      750: 1,
      375: 2,
      828: 1.81 / 2
    },
    sourceRoot: 'src',
    outputRoot: 'dist',
    plugins: ['@tarojs/plugin-framework-react'],
    defineConstants: {},
    copy: { patterns: [], options: {} },
    framework: 'react',
    compiler: {
      type: 'webpack5',
      prebundle: { enable: false }
    },
    alias: {
      '@': path.resolve(__dirname, '..', 'src')
    },
    sass: {
      data: '@use "@/styles/variables" as *;',
      projectDirectory: path.resolve(__dirname, '..')
    },
    mini: {
      postcss: {
        pxtransform: { enable: true, config: {} },
        cssModules: {
          enable: false,
          config: {
            namingPattern: 'module',
            generateScopedName: '[name]__[local]___[hash:base64:5]'
          }
        }
      },
      webpackChain(chain) {
        chain.resolve.alias.set('@', path.resolve(__dirname, '..', 'src'))
        // 禁止 asset 内联为 base64：将 maxSize 设为 0，强制所有文件作为独立资源输出
        // 避免 SVG 头像被转成超长 data URI 导致 "image src 数据量过大" 警告
        // 必须限定 test + type:'asset'，否则该 rule 会匹配所有模块（含 .json），
        // 把 dataUrlCondition 泄漏给 JsonModulesPlugin，触发 webpack 5.91 schema 校验报错
        chain.module.rule('noInlineAsset')
          .test(/\.(png|jpe?g|gif|svg|webp|woff2?|eot|ttf|mp4|ico)$/)
          .set('type', 'asset')
          .set('parser', { dataUrlCondition: { maxSize: 0 } })
      }
    },
    h5: {
      // 默认 '/' 用于 dev/远程部署；离线打包进 APK 时用 TARO_H5_OFFLINE=1 切到相对路径 './'，
      // 否则 file:// 协议下绝对路径资源(/js/app.js)会指向文件系统根而加载失败
      publicPath: process.env.TARO_H5_OFFLINE ? './' : '/',
      staticDirectory: 'static',
      webpackChain(chain) {
        chain.resolve.alias.set('@', path.resolve(__dirname, '..', 'src'))
        // dev 模式避免 eval-source-map：浏览器 CSP 会拦截 eval，导致 runtime 无法执行而白屏
        chain.devtool(process.env.NODE_ENV === 'production' ? false : 'cheap-module-source-map')
        // 同上：禁止 asset 内联为 base64
        chain.module.rule('noInlineAsset')
          .test(/\.(png|jpe?g|gif|svg|webp|woff2?|eot|ttf|mp4|ico)$/)
          .set('type', 'asset')
          .set('parser', { dataUrlCondition: { maxSize: 0 } })
        // 调高 webpack 体积告警阈值：当前 app 入口 ~401KiB、app.js 266KiB 略超默认 244KiB 推荐值，
        // 属正常体积。仅消除性能建议告警，不影响产物；如需真正缩包再走 splitChunks/懒加载
        chain.performance
          .maxAssetSize(512 * 1024)
          .maxEntrypointSize(512 * 1024)
      },
      postcss: {
        autoprefixer: { enable: true, config: {} },
        cssModules: {
          enable: false,
          config: {
            namingPattern: 'module',
            generateScopedName: '[name]__[local]___[hash:base64:5]'
          }
        }
      }
    }
  }

  if (process.env.NODE_ENV === 'development') {
    return merge({}, baseConfig, devConfig)
  }
  return baseConfig
})
