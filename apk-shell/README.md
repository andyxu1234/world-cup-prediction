# WorldCup APK 套壳（WebView Shell）

纯技术脚手架：一个 Android `WebView` 工程，加载你在 `app/build.gradle` 里配置的 H5 地址，
把网页打包成可直装的 APK。**不修改任何现有 `client/` 或 `server/` 代码。**

## 1. 构建离线版 H5（默认流程）

`MainActivity` 已默认加载 APK 内置的 `file:///android_asset/index.html`。
离线模式必须用**相对路径** publicPath，否则 `file://` 下绝对路径资源会加载失败：

```bash
cd client
npm install
# Windows PowerShell
$env:TARO_H5_OFFLINE=1; npm run build:h5
# macOS / Linux
TARO_H5_OFFLINE=1 npm run build:h5
```

> 不带该环境变量构建的是绝对路径版（用于 dev / 远程部署），离线打进 APK 必须用离线版。

## 2. 把产物拷进 APK 的 assets

```bash
# 把 client/dist/ 下所有文件拷到 apk-shell/app/src/main/assets/
# （assets/ 下的 index.html、js/、css/、static/、chunk/ 都会被打包进 APK）
robocopy client\dist apk-shell\app\src\main\assets /E /R:1 /W:1
```

> 每次重新 `build:h5` 后都要重拷一次。若目录不存在先 `mkdir apk-shell\app\src\main\assets`。

## 3. 打包 APK

### 方式 A（推荐）：Android Studio
1. 安装 [Android Studio](https://developer.android.com/studio)（自带 JDK17 + SDK Manager）。
2. `File → Open` 选择 `apk-shell/` 目录，等待 Gradle 同步。
3. `Build → Build Bundle(s) / APK(s) → Build APK(s)`。
4. 产物：`apk-shell/app/build/outputs/apk/debug/app-debug.apk`。

### 方式 B：命令行（需本地装 JDK 17 + Android SDK + Gradle 8.5）
```bash
cd apk-shell
gradle assembleDebug          # 已装 gradle 8.5 直接跑；否则先 gradle wrapper --gradle-version 8.5 再用 gradlew.bat
```
产物同上。需先在 SDK Manager 安装 **Android SDK Platform 34** 与 **Build-Tools 34.0.0**。

## 4. 发别人用

- `debug` 包可直接发，手机「设置 → 允许未知来源」安装即可。
- 正式分发建议 `assembleRelease` + 自签名 keystore（自行搜索 `apksigner` 用法）。

## 5. 可选：改用远程加载

不想内置 H5、想实时更新内容时：
1. 把 `dist/` 部署到任意静态服务器 / 后端 FastAPI 的 `static/`；
2. 改 `app/build.gradle` 的 `APP_URL` 为该地址；
3. 把 `MainActivity.java` 的 `webView.loadUrl("file:///android_asset/index.html")` 改回 `webView.loadUrl(BuildConfig.APP_URL)`。

## 6. 备注

- 工程包名 `com.andyyu.worldcup`，如冲突改 `app/build.gradle` 的 `applicationId`。
- 启动图标是占位 vector，替换 `app/src/main/res/drawable/ic_launcher.xml` 或加 mipmap 即可。
- 此工程本身不含任何业务逻辑，所有内容由内置 H5（或 `APP_URL`）决定。
