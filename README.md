# **pwncatharsis**

**pwncatharsis** is a native Android graphical interface for the pwncat-cs post-exploitation
framework. It embeds the power of pwncat's session management and automation tools into a mobile,
command-less UI.

## **Philosophy**

The primary goal is a **"point-and-click"** post-exploitation experience. Instead of requiring
manual command entry, **pwncatharsis** leverages a **perpetual enumeration engine** that works in
the background to automatically find and present actionable intelligence.

The interactive terminal is still available as a powerful tool, but it is treated as a fallback, not
the primary means of interaction.

## **Architecture**

This application is a self-contained native Android app that bundles the Python backend directly.

* **Client:** The UI is built entirely with modern, native Android components using **Jetpack
  Compose** and a Material 3 expressive theme.
* **Backend:** The powerful pwncat-cs engine runs in a background thread within the Android app
  itself, enabled by the **Chaquopy** Python integration library.
* **Communication:** A **Direct API Bridge** is used for communication between the Kotlin frontend
  and the embedded Python backend. This eliminates network overhead and provides a fast, stable, and
  efficient connection between the UI and the pwncat engine.

## **Key Features**

* **Perpetual Enumeration:** Once a session is active, a background engine automatically and
  continuously runs pwncat enumeration modules.
* **Real-time Intelligence:** Watch discovered loot and vulnerabilities appear in a clean,
  card-based UI as they are found—no manual refreshes needed.
* **Listener & Session Management:** A full graphical interface for creating, viewing, and managing
  listeners and active sessions.
* **Integrated Terminal:** A raw, interactive terminal is available for every session, allowing for
  manual intervention and command execution when necessary.

*This project is an exploration of mobile-first, GUI-driven offensive security tooling.*