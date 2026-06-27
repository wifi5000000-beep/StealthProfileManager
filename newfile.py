import os

project_files = {
    "settings.gradle.kts": """
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "StealthManager"
include(":app")
""",

    "build.gradle.kts": """
plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
}
""",

    "gradle.properties": """
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRclass=true
""",

    "app/build.gradle.kts": """
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-kapt")
}

android {
    namespace = "com.stealth.manager"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.stealth.manager"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.8"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.7.0")
    implementation("androidx.activity:activity-compose:1.8.2")
    implementation(platform("androidx.compose:compose-bom:2024.02.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.material3:material3")
    
    val roomVersion = "2.6.1"
    implementation("androidx.room:room-runtime:$roomVersion")
    implementation("androidx.room:room-ktx:$roomVersion")
    kapt("androidx.room:room-compiler:$roomVersion")
    
    implementation("androidx.webkit:webkit:1.10.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
}
""",

    "app/src/main/AndroidManifest.xml": """
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:allowBackup="false"
        android:icon="@mipmap/ic_launcher"
        android:label="Stealth Manager"
        android:theme="@style/Theme.MaterialComponents.DayNight.NoActionBar">

        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        
        <activity android:name=".StealthWebViewActivity" android:exported="false" />
    </application>
</manifest>
""",

    "app/src/main/java/com/stealth/manager/ProfileEntity.kt": """
package com.stealth.manager

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "profiles")
data class ProfileEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val targetUrl: String,
    val proxyHost: String,
    val proxyPort: Int,
    val proxyUser: String,
    val proxyPass: String,
    val deviceModel: String, 
    val hardwareConcurrency: Int, 
    val deviceMemory: Int
)
""",

    "app/src/main/java/com/stealth/manager/AppDatabase.kt": """
package com.stealth.manager

import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import android.content.Context

@Database(entities = [ProfileEntity::class], version = 1)
abstract class AppDatabase : RoomDatabase() {
    abstract fun profileDao(): ProfileDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "stealth_db"
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}

@androidx.room.Dao
interface ProfileDao {
    @androidx.room.Insert
    suspend fun insertProfile(profile: ProfileEntity)

    @androidx.room.Query("SELECT * FROM profiles")
    fun getAllProfiles(): kotlinx.coroutines.flow.Flow<List<ProfileEntity>>

    @androidx.room.Delete
    suspend fun deleteProfile(profile: ProfileEntity)
}
""",

    "app/src/main/java/com/stealth/manager/ProxyHandler.kt": """
package com.stealth.manager

import okhttp3.*
import java.net.InetSocketAddress
import java.net.Proxy

object ProxyHandler {
    fun createOkHttpClientForProxy(host: String, port: Int, user: String, pass: String): OkHttpClient {
        val proxy = Proxy(Proxy.Type.SOCKS, InetSocketAddress(host, port))
        
        val proxySelector = object : ProxySelector() {
            override fun select(uri: java.net.URI?): MutableList<Proxy> {
                return mutableListOf(proxy)
            }
            override fun connectFailed(uri: java.net.URI?, socketAddress: java.net.SocketAddress?, e: java.io.IOException?) {}
        }

        val authenticator = okhttp3.Authenticator { route, response ->
            val credential = okhttp3.Credentials.basic(user, pass)
            response.request().newBuilder()
                .header("Proxy-Authorization", credential)
                .build()
        }

        return OkHttpClient.Builder()
            .proxySelector(proxySelector)
            .authenticator(authenticator)
            .connectTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .readTimeout(30, java.util.concurrent.TimeUnit.SECONDS)
            .build()
    }
}
""",

    "app/src/main/java/com/stealth/manager/StealthWebViewClient.kt": """
package com.stealth.manager

import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayInputStream

class StealthWebViewClient(
    private val profile: ProfileEntity
) : WebViewClient() {

    private val httpClient: OkHttpClient = ProxyHandler.createOkHttpClientForProxy(
        profile.proxyHost, profile.proxyPort, profile.proxyUser, profile.proxyPass
    )

    override fun shouldInterceptRequest(view: WebView?, request: WebResourceRequest?): WebResourceResponse? {
        if (request == null || request.url.toString().startsWith("about:")) return null

        val okRequest = Request.Builder()
            .url(request.url.toString())
            .method(request.method, request.requestBody?.let { okhttp3.RequestBody.create(null, it) })
            .apply {
                request.requestHeaders.forEach { (key, value) -> addHeader(key, value) }
            }.build()

        return try {
            val response = httpClient.newCall(okRequest).execute()
            val mimeType = response.header("Content-Type") ?: "text/html"
            WebResourceResponse(
                mimeType.split(";")[0],
                response.header("Content-Encoding"),
                response.body?.byteStream()
            )
        } catch (e: Exception) {
            null
        }
    }

    override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
        super.onPageStarted(view, url, favicon)
        view?.evaluateJavascript(generateJsSpoofer(), null)
    }

    private fun generateJsSpoofer(): String {
        return \"\"\"
            (function() {
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => ${profile.hardwareConcurrency} });
                Object.defineProperty(navigator, 'deviceMemory', { get: () => ${profile.deviceMemory} });
                
                const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
                CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {
                    const imageData = originalGetImageData.call(this, x, y, w, h);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] = Math.min(255, imageData.data[i] + Math.floor(Math.random() * 2));
                    }
                    return imageData;
                };
                
                if (typeof RTCPeerConnection !== 'undefined') {
                    window.RTCPeerConnection = function() { return { createDataChannel: function() {} }; };
                }
            })();
        \"\"\".trimIndent()
    }
}
""",

    "app/src/main/java/com/stealth/manager/StealthWebViewActivity.kt": """
package com.stealth.manager

import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebSettings
import androidx.appcompat.app.AppCompatActivity

class StealthWebViewActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_webview)

        val profile = intent.getSerializableExtra("PROFILE") as ProfileEntity
        val webView = findViewById<WebView>(R.id.webView)

        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            setUserAgentString(profile.deviceModel)
            cacheMode = WebSettings.LOAD_NO_CACHE
        }

        webView.webViewClient = StealthWebViewClient(profile)
        webView.loadUrl(profile.targetUrl)
    }
}
""",

    "app/src/main/java/com/stealth/manager/MainActivity.kt": """
package com.stealth.manager

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    private lateinit var db: AppDatabase

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        db = AppDatabase.getInstance(this)

        setContent {
            MaterialTheme(colorScheme = darkColorScheme()) {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    DashboardScreen(db)
                }
            }
        }
    }
}

@Composable
fun DashboardScreen(db: AppDatabase) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()
    var profiles by remember { mutableStateOf(emptyList<ProfileEntity>()) }

    LaunchedEffect(Unit) {
        db.profileDao().getAllProfiles().collect { list ->
            profiles = list
        }
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = { /* منطق إضافة بروكسي جديد */ }) {
                Text("+")
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).padding(16.dp)) {
            Text(
                text = "Stealth Profiles",
                fontSize = 28.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(16.dp))

            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(profiles) { profile ->
                    ProfileCard(profile, onLaunch = {
                        val intent = Intent(context, StealthWebViewActivity::class.java)
                        intent.putExtra("PROFILE", profile)
                        context.startActivity(intent)
                    }, onDelete = {
                        coroutineScope.launch(Dispatchers.IO) {
                            db.profileDao().deleteProfile(profile)
                        }
                    })
                }
            }
        }
    }
}

@Composable
fun ProfileCard(profile: ProfileEntity, onLaunch: () -> Unit, onDelete: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(profile.name, style = MaterialTheme.typography.titleLarge)
            Text("URL: ${profile.targetUrl}", style = MaterialTheme.typography.bodySmall)
            Text("Proxy: ${profile.proxyHost}:${profile.proxyPort} (${profile.deviceModel})", style = MaterialTheme.typography.bodySmall)
            
            Spacer(modifier = Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
                Button(onClick = onLaunch, modifier = Modifier.weight(1f)) {
                    Text("Launch Stealth")
                }
                Spacer(modifier = Modifier.width(8.dp))
                OutlinedButton(onClick = onDelete, colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) {
                    Text("Delete")
                }
            }
        }
    }
}
""",

    "app/src/main/res/layout/activity_webview.xml": """
<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    <WebView android:id="@+id/webView"
        android:layout_width="match_parent"
        android:layout_height="match_parent" />
</FrameLayout>
""",

    "gradle/wrapper/gradle-wrapper.properties": """
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.10-bin.zip
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
""",

    ".github/workflows/build.yml": """
name: Build Android APK
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    - name: Set up JDK 17
      uses: actions/setup-java@v4
      with:
        java-version: '17'
        distribution: 'temurin'
    - name: Setup Gradle 8.10 (Force Fresh)
      uses: gradle/actions/setup-gradle@v3
      with:
        gradle-version: '8.10'
        cache-disabled: true
    - name: Build Debug APK
      run: ./gradlew assembleDebug
    - name: Upload APK
      uses: actions/upload-artifact@v4
      with:
        name: Stealth-APK
        path: app/build/outputs/apk/debug/app-debug.apk
"""
}

output_dir = "StealthManager"
for file_path, content in project_files.items():
    full_path = os.path.join(output_dir, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content.strip())

print(f"✅ تم الإنشاء بنجاح! مجلد المشروع اسمه: '{output_dir}'")
print("🔹 روح على GitHub، وعمل Upload Files للمجلد ده كله مرة واحدة.")
