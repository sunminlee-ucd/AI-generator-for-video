plugins { id("com.android.application") }

android {
    namespace = "com.sunminlee.aieditor"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.sunminlee.aieditor"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release { isMinifyEnabled = false }
    }
}
