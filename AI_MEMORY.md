AI Project Memory
DO NOT ALTER OR DELETE EXISTING ENTRIES. APPEND ONLY.
This document serves as a persistent, immutable memory bank for any AI assistant working on this
project. It contains a log of critical architectural decisions, user preferences, and environmental
constraints.

ENTRY 1: CORE ARCHITECTURE
TIMESTAMP: 2025-06-19 00:08:00 UTC
DECISION: The project is a client-server application. The server is a Dockerized Python/FastAPI
backend handling the pwncat logic. The client is a multi-platform Flutter application for the GUI.
REASONING: This model is required to support a unified GUI client across desktop (
Windows/macOS/Linux) and mobile (iOS/Android) platforms.
STATUS: OBSOLETE

ENTRY 2: HOSTING MODEL
TIMESTAMP: 2025-06-19 00:18:00 UTC
DECISION: The developer (AI) is not responsible for providing a hosted SaaS. The application will be
distributed as software that the user hosts themselves. The Flutter client must contain a settings
page for the user to enter the address of their self-hosted server instance.
REASONING: The user does not want to pay server fees for every end-user of the application. This
model places the operational cost and security responsibility on the individual user, which is
appropriate for this type of tool.
STATUS: OBSOLETE

ENTRY 3: UI/UX PHILOSOPHY
TIMESTAMP: 2025-06-19 00:26:00 UTC
DECISION: The primary user interaction model is "command-less." The GUI must be designed so that the
user never needs to type a command, instead interacting directly with the results of a perpetual,
automatic enumeration engine. Functionality should not be sacrificed.
REASONING: Explicit user request to eliminate typing and build a point-and-click interface.
STATUS: ACTIVE

ENTRY 4: DEVELOPMENT ENVIRONMENT
TIMESTAMP: 2025-06-19 01:35:00 UTC
DECISION: The canonical development environment is a cloud-based IDE (e.g., Firebase Studio) that
provides a full Linux VM. This environment requires a .idx/dev.nix configuration file to enable the
Docker daemon service. Build dependencies for Python C extensions (like gcc and build-essential)
must be included in the server's Dockerfile.
REASONING: Established to solve user-encountered, environment-specific build and runtime errors
related to the Docker daemon and missing C compilers.
STATUS: OBSOLETE

ENTRY 5: LAYOUT STRATEGY
TIMESTAMP: 2025-06-19 02:02:00 UTC
DECISION: The application must have an adaptive layout. Use a LayoutBuilder to switch between a
multi-pane desktop view for screens wider than 800px and a BottomNavigationBar-based mobile view for
screens narrower than 800px. Utilize Material 3 / Expressive patterns for modern, fluid UI.
REASONING: The initial static four-pane layout is unusable on mobile devices. A dedicated, adaptive
UI is required for a true multi-platform experience.
STATUS: OBSOLETE

ENTRY 6: PLATFORM PIVOT
TIMESTAMP: 2025-06-19 21:24:00 UTC
DECISION: The project will be a native Android application, not a multi-platform Flutter app. The
Python server will be embedded directly into the Android app using Chaquopy.
REASONING: Direct user request to abandon Flutter and build a native Android app that integrates the
server, despite the technical challenges.
STATUS: ACTIVE

ENTRY 7: ARCHITECTURE & PHILOSOPHY PIVOT
TIMESTAMP: 2025-06-20 22:43:00 UTC
DECISION: The project will use the Chaquopy/Android architecture but will be redesigned to align
with the original "command-less" UI philosophy. A perpetual, background enumeration engine will be
the primary driver of the user interface. The engine will automatically find and display loot and
privesc vulnerabilities. The interactive terminal will be demoted to a secondary tool within the
session view, rather than being the central focus.
REASONING: The user confirmed that the core vision of the app is a point-and-click, auto-enumerating
tool, not just a GUI for a terminal. This decision realigns the technical architecture with the
foundational user experience goals.
STATUS: ACTIVE

ENTRY 8: NATIVE DEPENDENCY MANAGEMENT
TIMESTAMP: 2025-06-20 23:58:20 UTC
DECISION: The `pwncat-cs` dependency will be vendored directly into the project's source code
instead
of being installed from PyPI. The `python-rapidjson` dependency, which requires a C compiler, will
be
removed from `pwncat-cs`'s `pyproject.toml` to allow it to fall back to the standard `json` library.
REASONING: The Chaquopy build environment cannot compile C extensions like `python-rapidjson` out of
the box. All attempts to install `pwncat-cs` directly from `pip` failed due to this issue. Vendoring
the dependency and modifying it to remove the C extension is the most robust solution to this
problem, as it avoids the need for a complex cross-compilation toolchain.
STATUS: ACTIVE