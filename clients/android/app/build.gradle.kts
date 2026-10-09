plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.laos.client"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.laos.client"
        minSdk = 24
        targetSdk = 35
        versionCode = 2
        versionName = "0.2.1"
        // laosweb 地址：首次启动会弹框让用户输入（存 SharedPreferences），
        // 此值仅作输入框的默认预填——预编译 APK 不再依赖构建期改码。
        buildConfigField("String", "LAOSWEB_URL", "\"http://192.168.1.100:8800/\"")
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { buildConfig = true }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.12.1")
}
