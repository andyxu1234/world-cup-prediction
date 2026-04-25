# 分享卡片长按功能排查指南

## 问题描述
长按图片后，只显示"保存图片到相册"选项，没有显示"转发给微信好友"和"分享小程序"选项。

## 已确认的代码实现

### 代码检查 ✅
```typescript
const handleLongPressSave = (imgUrl: string) => {
  console.log('handleLongPressSave called with imgUrl:', imgUrl)
  Taro.showActionSheet({
    itemList: ['保存图片到相册', '转发给微信好友', '分享小程序'], // 3个选项
    success: (res) => {
      console.log('ActionSheet success, tapIndex:', res.tapIndex)
      // 根据 tapIndex 处理不同选项
    },
  })
}
```

代码本身是**正确的**，`itemList` 确实包含了3个选项。

## 可能的原因

### 1. 小程序缓存问题（最常见）⭐
**症状**：代码已更新，但长按后仍然只显示旧菜单

**解决方案**：
```bash
# 方法1：在微信开发者工具中
1. 点击"清缓存" → "全部清除"
2. 点击"编译"按钮重新编译
3. 重新测试长按功能

# 方法2：完全重启
1. 关闭微信开发者工具
2. 删除 client/dist 目录
3. 重新运行 npm run dev:weapp
4. 在微信开发者工具中重新导入项目
```

### 2. Taro 版本兼容性问题
**症状**：ActionSheet 显示不完整

**检查方法**：
```bash
# 查看 Taro 版本
cd client
npm list @tarojs/taro
```

**建议版本**：Taro 3.x

### 3. 微信小程序基础库版本问题
**检查方法**：
1. 打开微信开发者工具
2. 详情 → 本地设置
3. 查看"调试基础库"版本
4. 建议升级到最新版本

### 4. 真机调试问题
**症状**：开发者工具正常，但真机不正常

**解决方案**：
1. 在真机上清除小程序缓存
2. 删除小程序重新搜索进入
3. 使用"预览"功能而非"真机调试"

## 调试步骤

### Step 1: 查看控制台日志
在微信开发者工具的控制台中，长按图片后应该看到：
```
handleLongPressSave called with imgUrl: https://...
ActionSheet success, tapIndex: 0/1/2
```

如果**没有看到日志**，说明 `onLongPress` 事件没有触发。

### Step 2: 检查 View 包裹
确保图片被 View 正确包裹：
```tsx
<View 
  className='share-image-wrapper'
  onLongPress={() => handleLongPressSave(imageUrl)}
>
  <Image src={imageUrl} mode='widthFix' />
</View>
```

### Step 3: 测试 ActionSheet
添加一个简单的测试按钮：
```tsx
<Button onClick={() => {
  Taro.showActionSheet({
    itemList: ['选项1', '选项2', '选项3'],
    success: (res) => console.log(res.tapIndex)
  })
}}>
  测试 ActionSheet
</Button>
```

如果测试按钮正常显示3个选项，说明是长按事件的问题。

### Step 4: 检查样式冲突
检查 `share-image-wrapper` 样式：
```scss
.share-image-wrapper {
  width: 100%;
  max-width: 630px;
  display: block;
  
  &:active {
    opacity: 0.8;
  }
}
```

确保没有其他样式覆盖导致长按区域过小。

## 快速修复方案

如果以上方法都不行，尝试以下方案：

### 方案1: 强制刷新编译
```bash
# 在 client 目录
rm -rf dist
npm run build:weapp
```

### 方案2: 添加延迟触发
```typescript
const handleLongPressSave = (imgUrl: string) => {
  // 添加短暂延迟，确保事件正确触发
  setTimeout(() => {
    Taro.showActionSheet({
      itemList: ['保存图片到相册', '转发给微信好友', '分享小程序'],
      success: (res) => {
        // ...
      },
    })
  }, 100)
}
```

### 方案3: 使用 Touch 事件替代
```typescript
<View 
  className='share-image-wrapper'
  onTouchStart={() => console.log('touch start')}
  onTouchEnd={() => console.log('touch end')}
  onLongPress={() => handleLongPressSave(imageUrl)}
>
```

## 验证清单

- [ ] 代码已包含3个选项的 itemList
- [ ] 已清除小程序缓存
- [ ] 已重新编译项目
- [ ] 控制台有正确的日志输出
- [ ] Image 被 View 正确包裹
- [ ] 样式没有阻止长按事件
- [ ] 在真机上测试过

## 联系支持

如果以上方法都无法解决问题，请提供：
1. 微信开发者工具版本
2. Taro 版本
3. 小程序基础库版本
4. 控制台日志截图
5. 长按时的表现截图
