<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import Sidebar from "./components/Sidebar.svelte";
  import Toast from "./components/Toast.svelte";
  import TranscribePage from "./routes/transcribe/+page.svelte";
  import BatchPage from "./routes/batch/+page.svelte";
  import RealtimePage from "./routes/realtime/+page.svelte";
  import MonitorPage from "./routes/monitor/+page.svelte";
  import SettingsPage from "./routes/settings/+page.svelte";
  import {
    currentRoute,
    theme,
    apiConnected,
    wsConnected,
    sidebarCollapsed,
  } from "./lib/stores";
  import { setBaseUrl, getHealth } from "./lib/api";
  import { ws } from "./lib/websocket";

  let connectionError = $state("");
  let retryCount = $state(0);
  let appReady = $state(false);

  /** Configure API and WebSocket connection to a given port */
  function connectToBackend(port: number) {
    setBaseUrl(`http://127.0.0.1:${port}`);
    ws.connect(`ws://127.0.0.1:${port}/ws`);
  }

  onMount(async () => {
    let unlistenReady: (() => void) | null = null;
    let unlistenError: (() => void) | null = null;

    try {
      // First, check if the port is already available (sidecar started before frontend)
      const port = await invoke<number | null>("get_api_port");
      if (port) {
        connectToBackend(port);
      } else {
        // Port not ready yet — listen for the Tauri event from the sidecar startup
        unlistenReady = await listen<number>("backend-ready", (event) => {
          connectToBackend(event.payload);
        });
        unlistenError = await listen<string>("backend-error", (event) => {
          connectionError = `バックエンド起動エラー: ${event.payload}`;
          $apiConnected = false;
        });
      }
    } catch {
      // Dev mode (no Tauri runtime): use default port
      setBaseUrl("http://127.0.0.1:8000");
      ws.connect("ws://127.0.0.1:8000/ws");
    }

    // Connection health check with adaptive interval
    const checkConnection = async () => {
      try {
        await getHealth();
        $apiConnected = true;
        connectionError = "";
        retryCount = 0;
      } catch {
        $apiConnected = false;
        retryCount++;
        connectionError = "バックエンドに接続できません";
      }
    };

    await checkConnection();

    // Self-scheduling health check: only schedules the next check after the
    // current one completes, preventing overlapping requests during downtime.
    let healthCheckTimer: ReturnType<typeof setTimeout> | null = null;
    let stopped = false;
    const scheduleNextCheck = () => {
      if (stopped) return;
      healthCheckTimer = setTimeout(async () => {
        await checkConnection();
        scheduleNextCheck();
      }, 5000);
    };
    scheduleNextCheck();

    // Initialize theme from localStorage
    const saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark") {
      $theme = saved;
    }

    // Initialize sidebar from localStorage
    const savedSidebar = localStorage.getItem("sidebar-collapsed");
    if (savedSidebar === "true") {
      $sidebarCollapsed = true;
    }

    // Fade in app
    requestAnimationFrame(() => {
      appReady = true;
    });

    return () => {
      stopped = true;
      if (healthCheckTimer) clearTimeout(healthCheckTimer);
      ws.disconnect();
      unlistenReady?.();
      unlistenError?.();
    };
  });

  // Persist theme
  $effect(() => {
    localStorage.setItem("theme", $theme);
  });

  // Persist sidebar state
  $effect(() => {
    localStorage.setItem("sidebar-collapsed", String($sidebarCollapsed));
  });

  // Page titles for ARIA
  const pageTitles: Record<string, string> = {
    transcribe: "文字起こし",
    batch: "バッチ処理",
    realtime: "リアルタイム",
    monitor: "フォルダ監視",
    settings: "設定",
  };
</script>

<div class="app-shell" class:ready={appReady}>
  <!-- Sidebar -->
  <Sidebar />

  <!-- Main Content -->
  <div class="main-wrapper">
    <!-- Connection Banner -->
    {#if connectionError && !$apiConnected}
      <div class="connection-banner" role="status" aria-live="polite">
        <div class="connection-content">
          <div class="connection-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="1" y1="1" x2="23" y2="23"/>
              <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/>
              <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/>
              <path d="M10.71 5.05A16 16 0 0 1 22.56 9"/>
              <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/>
              <path d="M8.53 16.11a6 6 0 0 1 6.95 0"/>
              <line x1="12" y1="20" x2="12.01" y2="20"/>
            </svg>
          </div>
          <div class="connection-text">
            <span class="connection-message">{connectionError}</span>
            <span class="connection-retry">再接続を試行中... ({retryCount}回)</span>
          </div>
        </div>
        <div class="connection-spinner" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="spin-icon">
            <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
          </svg>
        </div>
      </div>
    {/if}

    <!-- Page Content -->
    <main
      class="main-content"
      aria-label={pageTitles[$currentRoute] || "ページ"}
    >
      {#if $currentRoute === "transcribe"}
        <TranscribePage />
      {:else if $currentRoute === "batch"}
        <BatchPage />
      {:else if $currentRoute === "realtime"}
        <RealtimePage />
      {:else if $currentRoute === "monitor"}
        <MonitorPage />
      {:else if $currentRoute === "settings"}
        <SettingsPage />
      {/if}
    </main>

    <!-- Status Bar -->
    <footer class="status-bar" role="contentinfo">
      <div class="status-left">
        <div class="status-indicator" class:connected={$apiConnected} aria-label={$apiConnected ? "API接続中" : "API未接続"}>
          <span class="status-dot-small"></span>
          <span>API</span>
        </div>
        <div class="status-indicator" class:connected={$wsConnected} aria-label={$wsConnected ? "WebSocket接続中" : "WebSocket未接続"}>
          <span class="status-dot-small"></span>
          <span>WS</span>
        </div>
      </div>
      <div class="status-right">
        <span class="status-version">KotobaTranscriber v2.2</span>
      </div>
    </footer>
  </div>

  <!-- Toast Notifications -->
  <Toast />
</div>

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
    opacity: 0;
    transition: opacity 0.4s ease;
  }

  .app-shell.ready {
    opacity: 1;
  }

  .main-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
    transition: background-color 0.3s ease;
  }

  .main-content {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 28px 32px;
    scroll-behavior: smooth;
  }

  /* --- Connection Banner --- */
  .connection-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 20px;
    margin: 12px 16px 0;
    background: var(--warning-bg);
    border: 1px solid var(--warning-border);
    border-radius: 10px;
    animation: fadeInDown 0.4s ease both;
    flex-shrink: 0;
  }

  .connection-content {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .connection-icon {
    flex-shrink: 0;
    color: var(--warning);
  }

  .connection-text {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .connection-message {
    font-size: 13px;
    font-weight: 500;
    color: var(--warning-text);
  }

  .connection-retry {
    font-size: 11px;
    color: var(--warning-text);
    opacity: 0.7;
    font-variant-numeric: tabular-nums;
  }

  .connection-spinner {
    flex-shrink: 0;
    color: var(--warning);
  }

  .spin-icon {
    animation: spin 1s linear infinite;
  }

  /* --- Status Bar --- */
  .status-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 16px;
    border-top: 1px solid var(--border-light);
    background: var(--bg-surface);
    flex-shrink: 0;
    height: 28px;
    transition: background-color 0.3s ease, border-color 0.3s ease;
  }

  .status-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .status-right {
    display: flex;
    align-items: center;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
    letter-spacing: 0.02em;
    transition: color 0.3s ease;
  }

  .status-indicator.connected {
    color: var(--success);
  }

  .status-dot-small {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--text-muted);
    transition: background 0.3s ease;
  }

  .status-indicator.connected .status-dot-small {
    background: var(--success);
  }

  .status-version {
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.01em;
  }
</style>
