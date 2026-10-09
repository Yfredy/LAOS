package com.laos.client

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import androidx.activity.ComponentActivity

/**
 * laos 安卓客户端——最小 WebView 壳 + 语音桥。
 *
 * 架构取经 nanoMuse（GPL-3.0，只学设计零代码拷贝）：完整 UI 在服务端
 * （laosweb 一套 Web 面板服务所有端），每端只留一个薄壳——壳做四件事：
 * 全屏 WebView + JS/DOM 开关（PWA 数据）+ 返回键回退 + laosBridge 语音桥
 * （AudioRecord WAV，绕开 http 局域网下 getUserMedia 的安全上下文限制）。
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    lateinit var voice: VoiceBridge

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        voice = VoiceBridge(this)
        voice.requestPermissionIfNeeded()   // 首启即弹一次麦克风授权（拒绝也不挡面板）
        web = WebView(this)
        web.settings.apply {
            javaScriptEnabled = true          // laosweb 是纯 JS 面板
            domStorageEnabled = true          // PWA/会话状态（TTS 开关也在这）
            mediaPlaybackRequiresUserGesture = false  // TTS 朗读不要求手势
            cacheMode = WebSettings.LOAD_DEFAULT
        }
        web.addJavascriptInterface(voice, "laosBridge")
        web.loadUrl(BuildConfig.LAOSWEB_URL)
        setContentView(web)
    }

    /** 返回键 = 网页历史回退；退到底才退出 App（手机单手习惯）。 */
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (this::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int, permissions: Array<out String>, grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        // 授权结果不强制刷新——前端每次 micStart 前经 hasMic() 现查
    }

    override fun onDestroy() {
        if (this::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
