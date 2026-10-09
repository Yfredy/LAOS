package com.laos.client

import android.annotation.SuppressLint
import android.os.Bundle
import android.text.InputType
import android.webkit.WebSettings
import android.webkit.WebView
import android.widget.EditText
import androidx.appcompat.app.AlertDialog
import androidx.activity.ComponentActivity

/**
 * laos 安卓客户端——最小 WebView 壳 + 语音桥 + 运行时地址配置。
 *
 * 架构取经 nanoMuse（GPL-3.0，只学设计零代码拷贝）：完整 UI 在服务端
 * （laosweb 一套 Web 面板服务所有端），每端只留一个薄壳——壳做五件事：
 * 全屏 WebView + JS/DOM 开关 + 返回键回退 + laosBridge 语音桥 +
 * 首启地址输入（预编译 APK 的 URL 不再焊死在构建里，存 SharedPreferences）。
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
        val saved = prefs().getString("url", null)
        if (saved.isNullOrBlank()) askUrl(first = true) else web.loadUrl(saved)
        setContentView(web)
    }

    private fun prefs() = getSharedPreferences("laos", MODE_PRIVATE)

    /** 首启（或长按返回清空后）输入 laosweb 地址；预编译 APK 的关键自由度。 */
    private fun askUrl(first: Boolean) {
        val input = EditText(this)
        input.inputType = InputType.TYPE_TEXT_VARIATION_URI
        input.setText(prefs().getString("url", null) ?: BuildConfig.LAOSWEB_URL)
        input.hint = "http://<电脑IP>:8800"
        AlertDialog.Builder(this)
            .setTitle("laosweb 地址")
            .setMessage("电脑上运行 python bin/laosweb.py 后的局域网地址" +
                        "（改地址：系统设置 → 应用 → laos → 清除存储）")
            .setView(input)
            .setCancelable(false)
            .setPositiveButton("连接") { _, _ ->
                val u = input.text.toString().trim()
                    .ifEmpty { BuildConfig.LAOSWEB_URL }
                prefs().edit().putString("url", u).apply()
                web.loadUrl(u)
            }
            .show()
        if (first) web.loadUrl(BuildConfig.LAOSWEB_URL)  // 对话框下先垫一层默认
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
