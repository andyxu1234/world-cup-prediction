# 分享卡片长按保存功能优化

## 优化内容

### 问题
用户需要先点开图片才能长按保存，操作不够便捷。

### 解决方案
为分享卡片图片添加多功能操作菜单，用户可以选择：
1. **保存图片到相册**
2. **转发给微信好友**
3. **分享小程序**

## 关键修复

### Taro Image 长按事件问题

在 Taro 小程序中，`Image` 组件的 `onLongPress` 事件**不会直接响应**。必须将 `Image` 包裹在 `View` 中，在 `View` 上绑定 `onLongPress` 事件。

### 正确的实现方式

```tsx
// ❌ 错误：直接在 Image 上绑定长按
<Image
  src={imageUrl}
  onLongPress={() => handleSave(imageUrl)}
/>

// ✅ 正确：用 View 包裹 Image，在 View 上绑定长按
<View onLongPress={() => handleSave(imageUrl)}>
  <Image src={imageUrl} />
</View>
```

## 实现细节

### 1. 长按保存函数（多功能菜单）
```typescript
const handleLongPressSave = (imgUrl: string) => {
  Taro.showActionSheet({
    itemList: ['保存图片到相册', '转发给微信好友', '分享小程序'],
    success: (res) => {
      // res.tapIndex 返回用户点击的按钮索引，从 0 开始
      if (res.tapIndex === 0) {
        // 保存图片到相册
        Taro.showLoading({ title: '保存中...' })
        Taro.downloadFile({
          url: imgUrl,
          success: (downloadRes) => {
            if (downloadRes.statusCode === 200) {
              Taro.saveImageToPhotosAlbum({
                filePath: downloadRes.tempFilePath,
                success: () => {
                  Taro.hideLoading()
                  Taro.showToast({ title: '已保存到相册', icon: 'success' })
                },
                fail: () => {
                  Taro.hideLoading()
                  Taro.showToast({ title: '保存失败，请重试', icon: 'none' })
                },
              })
            } else {
              Taro.hideLoading()
              Taro.showToast({ title: '下载失败', icon: 'none' })
            }
          },
          fail: () => {
            Taro.hideLoading()
            Taro.showToast({ title: '下载失败', icon: 'none' })
          },
        })
      } else if (res.tapIndex === 1) {
        // 转发给微信好友
        Taro.showToast({ 
          title: '请点击右上角「...」转发', 
          icon: 'none',
          duration: 2000
        })
      } else if (res.tapIndex === 2) {
        // 分享小程序
        Taro.showToast({ 
          title: '请点击右上角「...」分享', 
          icon: 'none',
          duration: 2000
        })
      }
    },
  })
}
```

### 2. 转发/分享函数
```typescript
const handleForwardToFriend = () => {
  Taro.showActionSheet({
    itemList: ['转发给微信好友', '分享小程序'],
    success: (res) => {
      if (res.tapIndex === 0) {
        Taro.showToast({ 
          title: '请点击右上角「...」转发', 
          icon: 'none',
          duration: 2000
        })
      } else if (res.tapIndex === 1) {
        Taro.showToast({ 
          title: '请点击右上角「...」分享', 
          icon: 'none',
          duration: 2000
        })
      }
    },
  })
}
```

### 2. 应用范围
为两种模式的图片都添加了长按保存功能：

#### 邀请模式（invite）
```tsx
<Image
  className='share-image invite-image'
  src={inviteImageUrl}
  mode='widthFix'
  onLongPress={() => handleLongPressSave(inviteImageUrl)}
/>
```

#### 比赛对战模式（match）
```tsx
<Image
  className='share-image'
  src={imageUrl}
  mode='widthFix'
  onLongPress={() => handleLongPressSave(imageUrl)}
/>
```

## 用户体验流程

### 长按图片流程
1. 用户进入分享页面
2. **长按图片**
3. 弹出操作菜单（3个选项）：
   - 保存图片到相册
   - 转发给微信好友
   - 分享小程序
4. 选择对应操作

### 点击按钮流程
1. 用户进入分享页面
2. **点击“转发给好友 / 分享”按钮**
3. 弹出操作菜单（2个选项）：
   - 转发给微信好友
   - 分享小程序
4. 选择对应操作
5. 提示用户点击右上角「...」进行操作

## 功能特性

✅ **多功能菜单**：长按图片弹出 3 个选项
  - 保存图片到相册
  - 转发给微信好友
  - 分享小程序
✅ **快捷按钮**：点击主按钮弹出 2 个选项
  - 转发给微信好友
  - 分享小程序
✅ **一键保存**：长按即可保存，无需额外操作
✅ **友好提示**：
  - 保存中显示 Loading
  - 保存成功显示“已保存到相册”
  - 保存失败显示错误提示
  - 转发/分享提示点击右上角「...」
✅ **双模式支持**：邀请模式和比赛模式都支持
✅ **操作菜单**：通过 ActionSheet 提供明确的操作选项
✅ **视觉反馈**：长按时图片透明度降低，提供交互反馈

## 技术要点

### Taro API 使用
- `Taro.showActionSheet`：显示操作菜单
- `Taro.downloadFile`：下载图片到临时文件
- `Taro.saveImageToPhotosAlbum`：保存图片到相册
- `Taro.showLoading` / `Taro.hideLoading`：加载提示
- `Taro.showToast`：操作结果提示

### 错误处理
- 下载失败提示
- 保存失败提示
- 状态码检查（200）

## 相关文件

- `client/src/pages/share-card/index.tsx` - 分享页面主文件

## 注意事项

1. 需要用户授权相册权限
2. 图片 URL 必须是有效的网络地址
3. 建议在真机上测试长按手势响应
