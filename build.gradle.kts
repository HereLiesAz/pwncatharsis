plugins {
    id("com.android.application") version "8.10.1" apply false
    id("com.android.library") version "8.10.1" apply false
    id("org.jetbrains.kotlin.android") version "2.1.21" apply false
    id("com.chaquo.python") version "16.1.0" apply false
    alias(libs.plugins.compose.compiler) apply false
    id("org.jetbrains.kotlin.plugin.serialization") version "2.1.21" apply false
}