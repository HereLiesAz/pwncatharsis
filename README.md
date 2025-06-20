# pwncatharsis

*A GUI for ruin.*

## I. Overview

**pwncat: catharsis** is a graphical interface for the `pwncat` post-exploitation toolkit. It is
designed to automate and visualize common post-exploitation tasks, providing an information-driven
cockpit rather than a traditional command-line.

The interface is built with the philosophy that the user should never need to type a command.
Instead, the backend engine perpetually enumerates the target, and the GUI provides a
point-and-click interface to browse and interact with the results.

## II. Architecture

This project is a **client-server application**. The two components are separate and independent.

### The Server (The Engine)

* **Technology:** Python, FastAPI
* **Packaging:** Docker
* **Role:** The server is the headless engine that runs the `pwncat-cs` library. It manages
  listeners, sessions, and executes all commands on the target. It exposes its functionality over a
  secure REST API.

### The Client (The GUI)

* **Technology:** Flutter, Material 3
* **Role:** The client is a multi-platform graphical application that provides the user interface.
  It runs on Windows, macOS, Linux, Android, and iOS. It is entirely stateless and communicates with
  a self-hosted server instance configured by the user.

