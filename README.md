# **pwncatharsis**

**pwncatharsis** is a native Android graphical interface for post-exploitation frameworks. It embeds
the power of session management and automation tools into a mobile, command-less UI.

## **Philosophy**

The primary goal is a **"point-and-click"** post-exploitation experience. Instead of requiring
manual command entry, **pwncatharsis** leverages a **perpetual enumeration engine** that works in
the background to automatically find and present actionable intelligence.

The interactive terminal is still available as a powerful tool, but it is treated as a fallback, not
the primary means of interaction.

## **Architecture**

This application is a self-contained native Android app that bundles the Python backend directly.

* **Client:** The UI is built entirely with modern, native Android components using **Jetpack
  Compose** and a custom Material 3 expressive theme.
* **Backend:** The powerful `pwncat` script by cytopia runs in a background thread within the
  Android app itself, enabled by the **Chaquopy** Python integration library.
* **Communication:** A **Direct API Bridge** is used for communication between the Kotlin frontend
  and the embedded Python backend. This eliminates network overhead and provides a fast, stable, and
  efficient connection between the UI and the backend engine.

## **Key Features**

* **Perpetual Enumeration:** Once a session is active, a background engine automatically and
  continuously runs enumeration modules.
* **Real-time Intelligence:** Watch discovered loot and vulnerabilities appear in a clean,
  card-based UI as they are found—no manual refreshes needed.
* **Listener & Session Management:** A full graphical interface for creating, viewing, and managing
  listeners and active sessions.
* **Integrated Terminal:** A raw, interactive terminal is available for every session, allowing for
  manual intervention and command execution when necessary.
* **Automation Engine:** A "Chorus" system allows for creating, saving, and executing multi-command
  scripts.
* **Reverse Shell Generation:** Integrated reverse shell generator functionality, inspired by
  0dayCTF's generator.
* **(Planned) Website Cloning & Payload Injection:** Generate cloned websites with embedded reverse
  shell payloads, based on `makephish`.

*This project is an exploration of mobile-first, GUI-driven offensive security tooling.*

## **Credits**

* This project is built upon the original `pwncat` script by **cytopia**. Many thanks for their
  foundational work. You can find the original project at https://github.com/cytopia/pwncat.
* The reverse shell generator is inspired by the work
  of [0dayCTF/reverse-shell-generator](https://github.com/0dayCTF/reverse-shell-generator).
* Phishing page generation will be based on the work
  of [andpalmier/makephish](https://github.com/andpalmier/makephish).

<!-- end list -->