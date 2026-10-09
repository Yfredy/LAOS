package com.laos.client

import android.annotation.SuppressLint
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.util.Base64
import android.webkit.JavascriptInterface
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.io.ByteArrayOutputStream

/**
 * 语音桥：window.laosBridge（AudioRecord 16kHz 单声道 PCM16 → WAV → base64）。
 *
 * 为什么是原生桥而不是 getUserMedia：Chromium 的安全上下文策略把
 * http 局域网源上的 getUserMedia 一律禁掉——laosweb 正是跑在电脑的
 * http://<局域网IP>:8800。原生 AudioRecord 不受限，且这正是 nanoMuse
 * "每端薄桥"架构的本义（设备能力走原生，逻辑全在 Web UI）。
 * 音频只在按下期间进内存，松手即上传转 base64 返回——不落盘。
 */
class VoiceBridge(private val activity: MainActivity) {
    private var recorder: AudioRecord? = null
    private var thread: Thread? = null
    private val pcm = ByteArrayOutputStream()

    companion object {
        const val SAMPLE_RATE = 16000
        const val PERMISSION = android.Manifest.permission.RECORD_AUDIO
    }

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(activity, PERMISSION) ==
                PackageManager.PERMISSION_GRANTED

    /** 首次用麦前调用：无权限则弹系统授权框（结果在 MainActivity.onRequestPermissionsResult）。 */
    fun requestPermissionIfNeeded() {
        if (!hasPermission()) {
            ActivityCompat.requestPermissions(activity, arrayOf(PERMISSION), 1001)
        }
    }

    @JavascriptInterface
    fun hasMic(): Boolean = hasPermission()

    @SuppressLint("MissingPermission") // startRecord 前置 hasMic() 检查（JS 侧先问）
    @JavascriptInterface
    fun startRecord(): Boolean {
        if (!hasPermission()) return false
        stopQuietly()
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = AudioRecord(
            MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuf, 8192))
        if (rec.state != AudioRecord.STATE_INITIALIZED) {
            rec.release(); return false
        }
        pcm.reset()
        val buf = ShortArray(2048)
        rec.startRecording()
        recorder = rec
        thread = Thread {
            while (recorder === rec) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) break
                val bytes = ByteArray(n * 2)
                for (i in 0 until n) {
                    // Little-Endian PCM16
                    bytes[i * 2] = (buf[i].toInt() and 0xFF).toByte()
                    bytes[i * 2 + 1] = (buf[i].toInt() shr 8 and 0xFF).toByte()
                }
                synchronized(pcm) { pcm.write(bytes) }
            }
        }.also { it.start() }
        return true
    }

    /** 停止并返回 base64 WAV；没录上/无权限返回空串。 */
    @JavascriptInterface
    fun stopRecord(): String {
        val rec = recorder ?: return ""
        stopQuietly()
        val data = synchronized(pcm) { pcm.toByteArray() }
        pcm.reset()
        if (data.isEmpty()) return ""
        val wav = wavHeader(data.size) + data
        return Base64.encodeToString(wav, Base64.NO_WRAP)
    }

    private fun stopQuietly() {
        recorder = null            // 采集线程见到换代即退出
        try { thread?.join(500) } catch (_: InterruptedException) {}
        thread = null
    }

    private fun wavHeader(dataLen: Int): ByteArray {
        val totalLen = 36 + dataLen
        val h = ByteArray(44)
        fun putStr(o: Int, s: String) {
            for (i in s.indices) h[o + i] = s[i].code.toByte()
        }
        fun putInt(o: Int, v: Int) {
            h[o] = (v and 0xFF).toByte(); h[o + 1] = (v shr 8 and 0xFF).toByte()
            h[o + 2] = (v shr 16 and 0xFF).toByte(); h[o + 3] = (v shr 24 and 0xFF).toByte()
        }
        fun putShort(o: Int, v: Int) {
            h[o] = (v and 0xFF).toByte(); h[o + 1] = (v shr 8 and 0xFF).toByte()
        }
        putStr(0, "RIFF"); putInt(4, totalLen); putStr(8, "WAVE")
        putStr(12, "fmt "); putInt(16, 16); putShort(20, 1)      // PCM
        putShort(22, 1)                                          // mono
        putInt(24, SAMPLE_RATE); putInt(28, SAMPLE_RATE * 2)     // byte rate
        putShort(32, 2); putShort(34, 16)                        // block align / bits
        putStr(36, "data"); putInt(40, dataLen)
        return h
    }
}
