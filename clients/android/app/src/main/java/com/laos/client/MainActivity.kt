package com.laos.client

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import androidx.activity.ComponentActivity

/**
 * laos 安卓客户端——最小 WebView 壳（约 40 行）。
 *
 * 架构取经 nanoMuse（GPL-3.0，只学设计零代码拷贝）：完整 UI 在服务端
 * （laosweb 一套 Web 面板服务所有端），每端只留一个薄壳——本壳只做三件事：
 * 全屏 WebView + JS/DOM 开关（PWA 数据）+ 返回键网页回退。语音/通知/
 * 保活等原生桥是后续项（见 README 路线图）。
 */
class MainActivity : ComponentActivity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = WebView(this)
        web.settings.apply {
            javaScriptEnabled = true          // laosweb 是纯 JS 面板
            domStorageEnabled = true          // PWA/会话状态
            cacheMode = WebSettings.LOAD_DEFAULT
        }
        web.loadUrl(BuildConfig.LAOSWEB_URL)
        setContentView(web)
    }

    /** 返回键 = 网页历史回退；退到底才退出 App（手机单手习惯）。 */
    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (this::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        if (this::web.isInitialized) web.destroy()
        super.onDestroy()
    }
}
