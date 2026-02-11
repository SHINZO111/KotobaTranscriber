<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { startMonitor, stopMonitor, getMonitorStatus } from "../../lib/api";
  import { ws, getEventData } from "../../lib/websocket";
  import { monitorStatus, addToast } from "../../lib/stores";
  import type { NewFilesDetectedEventData } from "../../lib/types";

  let folderPath = $state("");
  let checkInterval = $state(10);
  let enableDiarization = $state(false);
  let autoMove = $state(false);
  let completedFolder = $state("");
  let error = $state<string | null>(null);
  let recentFiles = $state<Array<{ name: string; time: string }>>([]);

  let unsubNewFiles: (() => void) | null = null;
  let unsubStatus: (() => void) | null = null;

  onMount(async () => {
    try {
      const status = await getMonitorStatus();
      $monitorStatus = status;
      if (status.folder_path) folderPath = status.folder_path;
      checkInterval = status.check_interval;
    } catch {
      // API not connected yet
    }

    unsubNewFiles = ws.on("new_files_detected", (e) => {
      const data = getEventData<NewFilesDetectedEventData>(e);
      const files = data.files ?? [];
      const now = new Date().toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' });
      const newEntries = files.map((f: string) => ({
        name: f.split(/[\\/]/).pop() ?? f,
        time: now,
      }));
      recentFiles = [...newEntries, ...recentFiles].slice(0, 30);
    });
    unsubStatus = ws.on("status_update", (_e) => {
      // Status updates
    });
  });

  onDestroy(() => {
    unsubNewFiles?.();
    unsubStatus?.();
  });

  async function selectFolder() {
    try {
      const path = await invoke<string | null>("select_folder");
      if (path) folderPath = path;
    } catch (e) {
      console.error("Folder selection failed:", e);
    }
  }

  async function selectCompletedFolder() {
    try {
      const path = await invoke<string | null>("select_folder");
      if (path) completedFolder = path;
    } catch (e) {
      console.error("Folder selection failed:", e);
    }
  }

  async function toggleMonitor() {
    error = null;
    try {
      if ($monitorStatus.is_running) {
        await stopMonitor();
        $monitorStatus = { ...$monitorStatus, is_running: false };
        addToast("info", "フォルダ監視を停止しました");
      } else {
        if (!folderPath) {
          error = "監視フォルダを選択してください";
          return;
        }
        await startMonitor({
          folder_path: folderPath,
          check_interval: checkInterval,
          enable_diarization: enableDiarization,
          auto_move: autoMove,
          completed_folder: completedFolder || null,
        });
        $monitorStatus = { ...$monitorStatus, is_running: true, folder_path: folderPath };
        addToast("success", "フォルダ監視を開始しました");
      }
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
      addToast("error", "監視の切り替えに失敗しました");
    }
  }
</script>

<div class="page animate-fadeInUp">
  <!-- Page Header -->
  <header class="page-header">
    <div class="page-header-text">
      <h2 class="page-title">フォルダ監視</h2>
      <p class="page-description">フォルダ内の新規ファイルを自動で文字起こし</p>
    </div>
    {#if $monitorStatus.is_running}
      <div class="monitor-indicator">
        <span class="monitor-dot"></span>
        <span class="monitor-text">監視中</span>
      </div>
    {/if}
  </header>

  <!-- Statistics -->
  <section class="stats-section animate-fadeInUp stagger-1" aria-label="統計情報">
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon" aria-hidden="true" style="color: var(--success)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
          </svg>
        </div>
        <div class="stat-data">
          <span class="stat-value">{$monitorStatus.total_processed}</span>
          <span class="stat-label">処理済み</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" aria-hidden="true" style="color: var(--error)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </div>
        <div class="stat-data">
          <span class="stat-value" style="color: {$monitorStatus.total_failed > 0 ? 'var(--error)' : 'var(--text-primary)'}">{$monitorStatus.total_failed}</span>
          <span class="stat-label">失敗</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon" aria-hidden="true" style="color: var(--brand)">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <div class="stat-data">
          <span class="stat-value">{checkInterval}</span>
          <span class="stat-label">秒間隔</span>
        </div>
      </div>
    </div>
  </section>

  <!-- Configuration -->
  <section class="section animate-fadeInUp stagger-2" aria-label="監視設定">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          監視設定
        </h3>
      </div>

      <div class="settings-list">
        <!-- Watch folder -->
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">監視フォルダ</span>
            <span class="setting-desc">音声ファイルを検出するフォルダ</span>
          </div>
          <div class="setting-control">
            <button
              class="btn btn-outline btn-sm"
              onclick={selectFolder}
              disabled={$monitorStatus.is_running}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              選択
            </button>
          </div>
        </div>
        {#if folderPath}
          <div class="folder-path-display">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--brand)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="truncate" title={folderPath}>{folderPath}</span>
          </div>
        {/if}

        <hr class="divider" />

        <!-- Check interval -->
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">チェック間隔</span>
            <span class="setting-desc">新規ファイルの確認頻度</span>
          </div>
          <div class="setting-control setting-input-group">
            <input
              type="number"
              bind:value={checkInterval}
              min={5}
              max={60}
              disabled={$monitorStatus.is_running}
              aria-label="チェック間隔（秒）"
            />
            <span class="input-suffix">秒</span>
          </div>
        </div>

        <hr class="divider" />

        <!-- Diarization -->
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">話者分離</span>
            <span class="setting-desc">複数の話者を自動識別</span>
          </div>
          <label class="setting-control">
            <div class="toggle" class:active={enableDiarization} onclick={() => { if (!$monitorStatus.is_running) enableDiarization = !enableDiarization; }} role="switch" aria-checked={enableDiarization} aria-label="話者分離の切り替え" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (!$monitorStatus.is_running) enableDiarization = !enableDiarization; }}}></div>
          </label>
        </div>

        <hr class="divider" />

        <!-- Auto move -->
        <div class="setting-row">
          <div class="setting-info">
            <span class="setting-name">自動移動</span>
            <span class="setting-desc">処理済みファイルを別フォルダに移動</span>
          </div>
          <label class="setting-control">
            <div class="toggle" class:active={autoMove} onclick={() => { if (!$monitorStatus.is_running) autoMove = !autoMove; }} role="switch" aria-checked={autoMove} aria-label="自動移動の切り替え" tabindex="0" onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (!$monitorStatus.is_running) autoMove = !autoMove; }}}></div>
          </label>
        </div>

        {#if autoMove}
          <div class="setting-sub animate-fadeIn">
            <div class="setting-row">
              <div class="setting-info">
                <span class="setting-name">移動先フォルダ</span>
              </div>
              <button
                class="btn btn-outline btn-sm"
                onclick={selectCompletedFolder}
                disabled={$monitorStatus.is_running}
              >
                選択
              </button>
            </div>
            {#if completedFolder}
              <div class="folder-path-display">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                </svg>
                <span class="truncate" title={completedFolder}>{completedFolder}</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  </section>

  <!-- Action -->
  <section class="actions-section animate-fadeInUp stagger-3">
    <button
      class="btn btn-lg"
      class:btn-primary={!$monitorStatus.is_running}
      class:btn-danger={$monitorStatus.is_running}
      onclick={toggleMonitor}
    >
      {#if $monitorStatus.is_running}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <rect x="6" y="6" width="12" height="12" rx="2"/>
        </svg>
        監視停止
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
        </svg>
        監視開始
      {/if}
    </button>
  </section>

  <!-- Error -->
  {#if error}
    <section class="error-section animate-fadeInUp" role="alert">
      <div class="error-banner">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
        <span>{error}</span>
        <button class="error-dismiss" onclick={() => error = null} aria-label="閉じる">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </section>
  {/if}

  <!-- Recent Files -->
  <section class="recent-section animate-fadeInUp stagger-4" aria-label="検出されたファイル">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          アクティビティ
        </h3>
        {#if recentFiles.length > 0}
          <span class="card-badge">{recentFiles.length}</span>
        {/if}
      </div>

      {#if recentFiles.length > 0}
        <ul class="activity-list" role="list">
          {#each recentFiles as file, i}
            <li class="activity-item" style="animation-delay: {i * 30}ms">
              <div class="activity-icon" aria-hidden="true">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
                </svg>
              </div>
              <span class="activity-name">{file.name}</span>
              <span class="activity-time">{file.time}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <div class="activity-empty">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
          </svg>
          <span>検出されたファイルはまだありません</span>
        </div>
      {/if}
    </div>
  </section>
</div>

<style>
  .page { max-width: 720px; margin: 0 auto; }

  .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; }
  .page-header-text { display: flex; flex-direction: column; gap: 4px; }
  .page-title { font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.02em; }
  .page-description { font-size: 13px; color: var(--text-tertiary); margin: 0; }

  .section { margin-bottom: 16px; }
  .card { padding: 20px; }
  .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .card-title { font-size: 14px; font-weight: 600; margin: 0; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
  .card-badge { background: var(--brand-subtle); color: var(--brand); font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 9999px; }

  /* Monitor indicator */
  .monitor-indicator {
    display: flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 9999px;
    background: var(--success-bg); border: 1px solid var(--success-border);
  }
  .monitor-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--monitoring-color);
    animation: pulse 2.5s ease-in-out infinite;
  }
  .monitor-text {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--success-text);
  }

  /* Stats */
  .stats-section { margin-bottom: 16px; }
  .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
  .stat-card {
    display: flex; align-items: center; gap: 12px;
    padding: 16px; background: var(--bg-surface);
    border: 1px solid var(--border-default); border-radius: 12px;
    box-shadow: var(--shadow-xs); transition: all 0.2s ease;
  }
  .stat-card:hover { box-shadow: var(--shadow-sm); }
  .stat-icon { flex-shrink: 0; }
  .stat-data { display: flex; flex-direction: column; }
  .stat-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--text-primary); }
  .stat-label { font-size: 11px; font-weight: 500; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }

  /* Settings list */
  .settings-list { display: flex; flex-direction: column; }
  .setting-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
  .setting-info { display: flex; flex-direction: column; gap: 2px; }
  .setting-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
  .setting-desc { font-size: 11px; color: var(--text-muted); }
  .setting-control { display: flex; align-items: center; }
  .setting-input-group { display: flex; align-items: center; gap: 6px; }
  .setting-input-group input { width: 70px; text-align: center; }
  .input-suffix { font-size: 12px; color: var(--text-muted); }
  .setting-sub { padding-left: 16px; border-left: 2px solid var(--brand-muted); margin-top: 8px; margin-bottom: 8px; }

  .folder-path-display {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; background: var(--bg-surface-hover);
    border-radius: 6px; margin-top: 8px; margin-bottom: 8px;
    font-size: 12px; color: var(--text-secondary);
  }

  /* Actions */
  .actions-section { margin-bottom: 16px; }

  /* Error */
  .error-section { margin-bottom: 16px; }
  .error-banner { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 10px; color: var(--error-text); font-size: 13px; }
  .error-banner span { flex: 1; }
  .error-dismiss { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: none; border: none; border-radius: 4px; color: var(--error-text); cursor: pointer; opacity: 0.6; transition: opacity 0.15s ease; padding: 0; }
  .error-dismiss:hover { opacity: 1; }

  /* Activity */
  .recent-section { margin-bottom: 16px; }
  .activity-list { list-style: none; padding: 0; margin: 0; max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
  .activity-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 10px; border-radius: 8px;
    transition: background 0.15s ease; animation: fadeInUp 0.3s ease both;
  }
  .activity-item:hover { background: var(--bg-surface-hover); }
  .activity-icon { flex-shrink: 0; }
  .activity-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .activity-time { flex-shrink: 0; font-size: 11px; color: var(--text-muted); font-variant-numeric: tabular-nums; }

  .activity-empty {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 32px 16px; color: var(--text-muted); opacity: 0.5; text-align: center;
  }
  .activity-empty span { font-size: 13px; }
</style>
