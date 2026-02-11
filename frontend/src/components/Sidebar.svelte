<script lang="ts">
  import { currentRoute, isProcessing, realtimeStatus, monitorStatus, sidebarCollapsed, theme } from "../lib/stores";
  import type { Route } from "../lib/types";

  type NavItem = {
    route: Route;
    label: string;
    labelShort: string;
    svgIcon: string;
  };

  const navItems: NavItem[] = [
    {
      route: "transcribe",
      label: "文字起こし",
      labelShort: "文字",
      svgIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
    },
    {
      route: "batch",
      label: "バッチ処理",
      labelShort: "バッチ",
      svgIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>`,
    },
    {
      route: "realtime",
      label: "リアルタイム",
      labelShort: "録音",
      svgIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`,
    },
    {
      route: "monitor",
      label: "フォルダ監視",
      labelShort: "監視",
      svgIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
    },
    {
      route: "settings",
      label: "設定",
      labelShort: "設定",
      svgIcon: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
    },
  ];

  function navigate(route: Route) {
    $currentRoute = route;
  }

  function toggleCollapse() {
    $sidebarCollapsed = !$sidebarCollapsed;
  }

  function toggleTheme() {
    $theme = $theme === "dark" ? "light" : "dark";
  }

  function handleKeydown(event: KeyboardEvent) {
    // Ctrl+B to toggle sidebar collapse
    if (event.ctrlKey && event.key === "b") {
      event.preventDefault();
      toggleCollapse();
      return;
    }

    // Arrow key navigation within the nav list
    const target = event.target as HTMLElement;
    if (!target.closest(".nav-list")) return;

    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const items = Array.from(
        target.closest(".nav-list")!.querySelectorAll<HTMLButtonElement>(".nav-item")
      );
      const currentIndex = items.indexOf(target as HTMLButtonElement);
      if (currentIndex === -1) return;
      const nextIndex =
        event.key === "ArrowDown"
          ? (currentIndex + 1) % items.length
          : (currentIndex - 1 + items.length) % items.length;
      items[nextIndex].focus();
    }

    if (event.key === "Home") {
      event.preventDefault();
      const items = target.closest(".nav-list")!.querySelectorAll<HTMLButtonElement>(".nav-item");
      items[0]?.focus();
    }

    if (event.key === "End") {
      event.preventDefault();
      const items = target.closest(".nav-list")!.querySelectorAll<HTMLButtonElement>(".nav-item");
      items[items.length - 1]?.focus();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<nav
  class="sidebar"
  class:collapsed={$sidebarCollapsed}
  aria-label="メインナビゲーション"
>
  <!-- Header -->
  <div class="sidebar-header">
    <div class="brand">
      <div class="brand-icon" aria-hidden="true">
        <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
          <rect width="32" height="32" rx="8" fill="var(--brand)"/>
          <path d="M8 10h4v12H8V10zm6 4h4v8h-4v-8zm6-2h4v10h-4V12z" fill="white" opacity="0.9"/>
        </svg>
      </div>
      {#if !$sidebarCollapsed}
        <div class="brand-text">
          <span class="brand-name">Kotoba</span>
          <span class="brand-version">v2.2</span>
        </div>
      {/if}
    </div>
    <button
      class="collapse-btn"
      onclick={toggleCollapse}
      aria-label={$sidebarCollapsed ? "サイドバーを展開" : "サイドバーを折りたたむ"}
      title={$sidebarCollapsed ? "展開" : "折りたたむ"}
    >
      <svg
        width="16" height="16" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        class="collapse-icon"
        class:rotated={$sidebarCollapsed}
      >
        <polyline points="15 18 9 12 15 6"/>
      </svg>
    </button>
  </div>

  <!-- Navigation -->
  <ul class="nav-list" role="list" aria-label="ページナビゲーション">
    {#each navItems as item, i}
      <li>
        <button
          class="nav-item"
          class:active={$currentRoute === item.route}
          onclick={() => navigate(item.route)}
          aria-current={$currentRoute === item.route ? "page" : undefined}
          title={$sidebarCollapsed ? item.label : undefined}
          style="animation-delay: {i * 30}ms"
        >
          <span class="nav-icon" aria-hidden="true">
            {@html item.svgIcon}
          </span>
          {#if !$sidebarCollapsed}
            <span class="nav-label">{item.label}</span>
          {/if}
          {#if item.route === "realtime" && $realtimeStatus.is_running}
            <span class="status-indicator recording" aria-label="録音中">
              <span class="status-dot"></span>
            </span>
          {/if}
          {#if item.route === "monitor" && $monitorStatus.is_running}
            <span class="status-indicator monitoring" aria-label="監視中">
              <span class="status-dot"></span>
            </span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>

  <!-- Footer -->
  <div class="sidebar-footer">
    <button
      class="theme-btn"
      onclick={toggleTheme}
      aria-label={$theme === "dark" ? "ライトモードに切り替え" : "ダークモードに切り替え"}
      title={$theme === "dark" ? "ライトモード" : "ダークモード"}
    >
      {#if $theme === "dark"}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      {:else}
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      {/if}
      {#if !$sidebarCollapsed}
        <span class="theme-label">{$theme === "dark" ? "ライト" : "ダーク"}</span>
      {/if}
    </button>
  </div>
</nav>

<style>
  .sidebar {
    width: 220px;
    min-width: 220px;
    height: 100vh;
    background: var(--sidebar-bg);
    border-right: 1px solid var(--sidebar-border);
    display: flex;
    flex-direction: column;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1),
                background-color 0.3s ease;
    position: relative;
    z-index: 10;
  }

  .sidebar.collapsed {
    width: 64px;
    min-width: 64px;
  }

  /* --- Header --- */
  .sidebar-header {
    padding: 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border-light);
    min-height: 60px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
  }

  .brand-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  .brand-text {
    display: flex;
    align-items: baseline;
    gap: 6px;
    white-space: nowrap;
    overflow: hidden;
  }

  .brand-name {
    font-size: 17px;
    font-weight: 700;
    color: var(--brand);
    letter-spacing: -0.02em;
  }

  .brand-version {
    font-size: 10px;
    font-weight: 500;
    color: var(--text-muted);
    padding: 1px 5px;
    background: var(--bg-surface-hover);
    border-radius: 4px;
    letter-spacing: 0.02em;
  }

  .collapse-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s ease;
    flex-shrink: 0;
    padding: 0;
  }

  .collapse-btn:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
  }

  .collapse-icon {
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .collapse-icon.rotated {
    transform: rotate(180deg);
  }

  .collapsed .sidebar-header {
    padding: 16px 12px;
    justify-content: center;
  }

  .collapsed .collapse-btn {
    position: absolute;
    right: 6px;
    top: 18px;
  }

  .collapsed .brand {
    justify-content: center;
  }

  /* --- Navigation --- */
  .nav-list {
    list-style: none;
    padding: 8px;
    margin: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 12px;
    background: transparent;
    border: none;
    border-radius: 8px;
    color: var(--text-tertiary);
    font-family: inherit;
    font-size: 13px;
    font-weight: 450;
    cursor: pointer;
    transition: all 0.2s ease;
    text-align: left;
    position: relative;
    white-space: nowrap;
    overflow: hidden;
  }

  .nav-item:hover {
    background: var(--sidebar-item-hover);
    color: var(--text-primary);
  }

  .nav-item.active {
    background: var(--sidebar-item-active-bg);
    color: var(--sidebar-item-active-text);
    font-weight: 550;
  }

  .nav-item.active::before {
    content: "";
    position: absolute;
    left: 0;
    top: 6px;
    bottom: 6px;
    width: 3px;
    background: var(--sidebar-item-active-indicator);
    border-radius: 0 3px 3px 0;
    animation: fadeIn 0.2s ease both;
  }

  .nav-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    opacity: 0.75;
    transition: opacity 0.2s ease;
  }

  .nav-item:hover .nav-icon,
  .nav-item.active .nav-icon {
    opacity: 1;
  }

  .nav-label {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .collapsed .nav-item {
    justify-content: center;
    padding: 10px;
  }

  .collapsed .nav-item.active::before {
    top: 8px;
    bottom: 8px;
  }

  /* --- Status indicators --- */
  .status-indicator {
    margin-left: auto;
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .collapsed .status-indicator {
    position: absolute;
    top: 6px;
    right: 6px;
    margin-left: 0;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    position: relative;
  }

  .recording .status-dot {
    background: var(--recording-color);
    animation: pulseGlow 2s ease-in-out infinite;
    box-shadow: 0 0 0 0 var(--recording-glow);
  }

  .monitoring .status-dot {
    background: var(--monitoring-color);
    animation: pulse 2.5s ease-in-out infinite;
  }

  /* --- Footer --- */
  .sidebar-footer {
    padding: 12px;
    border-top: 1px solid var(--border-light);
  }

  .theme-btn {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    background: none;
    border: none;
    border-radius: 8px;
    color: var(--text-tertiary);
    font-family: inherit;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
    overflow: hidden;
  }

  .theme-btn:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
  }

  .collapsed .theme-btn {
    justify-content: center;
    padding: 8px;
  }

  .theme-label {
    opacity: 0.85;
  }
</style>
