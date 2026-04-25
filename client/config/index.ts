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
        chain.module.rule('asset')
          .set('parser', { dataUrlCondition: { maxSize: 0 } })
      }
    },
    h5: {
      publicPath: '/',
      staticDirectory: 'static',
      webpackChain(chain) {
        chain.resolve.alias.set('@', path.resolve(__dirname, '..', 'src'))
        // 同上：禁止 asset 内联为 base64
        chain.module.rule('asset')
          .set('parser', { dataUrlCondition: { maxSize: 0 } })
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
