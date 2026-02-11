<script lang="ts">
  import { onMount } from "svelte";
  import ThemeToggle from "../../components/ThemeToggle.svelte";
  import { getSettings, updateSettings, getHealth } from "../../lib/api";
  import { settings, theme, addToast } from "../../lib/stores";
  import { invoke } from "@tauri-apps/api/core";
  import type { HealthResponse } from "../../lib/types";

  let healthInfo = $state<HealthResponse | null>(null);
  let saving = $state(false);
  let outputDirectory = $state("");
  let loading = $state(true);

  onMount(async () => {
    try {
      const s = await getSettings();
      $settings = s;
      if (s.theme === "light" || s.theme === "dark") {
        $theme = s.theme;
      }
      outputDirectory = s.output_directory ?? "";
    } catch {
      // API not connected
    }

    try {
      healthInfo = await getHealth();
    } catch {
      // API not connected
    }

    loading = false;
  });

  async function selectOutputDir() {
    try {
      const path = await invoke<string | null>("select_folder");
      if (path) outputDirectory = path;
    } catch (e) {
      console.error("Folder selection failed:", e);
    }
  }

  async function saveSettings() {
    saving = true;
    try {
      await updateSettings({
        theme: $theme,
        output_directory: outputDirectory || undefined,
      });
      addToast("success", "設定を保存しました");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      addToast("error", `保存に失敗しました: ${msg}`);
    } finally {
      saving = false;
    }
  }

  function getEngineDisplayName(engine: string): string {
    const names: Record<string, string> = {
      "kotoba-whisper": "Kotoba-Whisper v2.2",
      "faster-whisper": "Faster-Whisper",
    };
    return names[engine] || engine;
  }
</script>

<div class="page animate-fadeInUp">
  <!-- Page Header -->
  <header class="page-header">
    <div class="page-header-text">
      <h2 class="page-title">設定</h2>
      <p class="page-description">アプリケーションの設定を管理</p>
    </div>
  </header>

  {#if loading}
    <div class="loading-state">
      <div class="skeleton" style="height: 120px; margin-bottom: 16px;"></div>
      <div class="skeleton" style="height: 180px; margin-bottom: 16px;"></div>
      <div class="skeleton" style="height: 160px;"></div>
    </div>
  {:else}
    <!-- Appearance -->
    <section class="section animate-fadeInUp stagger-1" aria-label="外観">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
            外観
          </h3>
        </div>
        <div class="settings-list">
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-name">テーマ</span>
              <span class="setting-desc">ダークモードとライトモードを切り替え</span>
            </div>
            <div class="setting-control">
              <ThemeToggle />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Output Settings -->
    <section class="section animate-fadeInUp stagger-2" aria-label="出力設定">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            出力設定
          </h3>
        </div>
        <div class="settings-list">
          <div class="setting-row">
            <div class="setting-info">
              <span class="setting-name">出力フォルダ</span>
              <span class="setting-desc">文字起こし結果の保存先</span>
            </div>
            <button class="btn btn-outline btn-sm" onclick={selectOutputDir}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              選択
            </button>
          </div>
          {#if outputDirectory}
            <div class="folder-display">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--brand)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
              </svg>
              <span class="truncate" title={outputDirectory}>{outputDirectory}</span>
              <button class="folder-clear" onclick={() => outputDirectory = ""} aria-label="出力フォルダをリセット">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>
          {:else}
            <div class="folder-default">
              デフォルト: 元ファイルと同じフォルダに保存
            </div>
          {/if}
        </div>
      </div>
    </section>

    <!-- System Info -->
    <section class="section animate-fadeInUp stagger-3" aria-label="システム情報">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            システム情報
          </h3>
        </div>

        {#if healthInfo}
          <div class="info-grid">
            <div class="info-row">
              <span class="info-label">バージョン</span>
              <span class="info-value">
                <span class="badge badge-brand">v{healthInfo.version}</span>
              </span>
            </div>
            <div class="info-row">
              <span class="info-label">ステータス</span>
              <span class="info-value">
                <span class="badge badge-success">{healthInfo.status}</span>
              </span>
            </div>
            <hr class="divider" />
            <h4 class="info-section-title">エンジン</h4>
            {#each Object.entries(healthInfo.engines) as [engine, available]}
              <div class="info-row">
                <span class="info-label">{getEngineDisplayName(engine)}</span>
                <span class="info-value">
                  {#if available}
                    <span class="engine-status available">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                      利用可能
                    </span>
                  {:else}
                    <span class="engine-status unavailable">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                      利用不可
                    </span>
                  {/if}
                </span>
              </div>
            {/each}
          </div>
        {:else}
          <div class="info-disconnected">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M10.71 5.05A16 16 0 0 1 22.56 9"/><path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/>
            </svg>
            <span>バックエンドに接続されていません</span>
          </div>
        {/if}
      </div>
    </section>

    <!-- Save Button -->
    <section class="save-section animate-fadeInUp stagger-4">
      <button
        class="btn btn-primary btn-lg"
        onclick={saveSettings}
        disabled={saving}
      >
        {#if saving}
          <span class="btn-spinner"></span>
          保存中...
        {:else}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>
          </svg>
          設定を保存
        {/if}
      </button>
    </section>
  {/if}
</div>

<style>
  .page { max-width: 640px; margin: 0 auto; }

  .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 24px; }
  .page-header-text { display: flex; flex-direction: column; gap: 4px; }
  .page-title { font-size: 22px; font-weight: 700; margin: 0; letter-spacing: -0.02em; }
  .page-description { font-size: 13px; color: var(--text-tertiary); margin: 0; }

  .section { margin-bottom: 16px; }
  .card { padding: 20px; }
  .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .card-title { font-size: 14px; font-weight: 600; margin: 0; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }

  /* Settings list */
  .settings-list { display: flex; flex-direction: column; gap: 4px; }
  .setting-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 4px 0; }
  .setting-info { display: flex; flex-direction: column; gap: 2px; }
  .setting-name { font-size: 13px; font-weight: 500; color: var(--text-primary); }
  .setting-desc { font-size: 11px; color: var(--text-muted); }
  .setting-control { flex-shrink: 0; }

  /* Folder display */
  .folder-display {
    display: flex; align-items: center; gap: 8px;
    padding: 8px 12px; background: var(--bg-surface-hover);
    border-radius: 6px; margin-top: 8px;
    font-size: 12px; color: var(--text-secondary);
  }
  .folder-clear {
    flex-shrink: 0; display: flex; align-items: center; justify-content: center;
    width: 20px; height: 20px; background: none; border: none; border-radius: 4px;
    color: var(--text-muted); cursor: pointer; transition: all 0.15s ease;
    padding: 0; margin-left: auto;
  }
  .folder-clear:hover { color: var(--error); background: var(--error-bg); }

  .folder-default {
    margin-top: 8px; padding: 8px 12px; font-size: 12px; color: var(--text-muted);
    font-style: italic; background: var(--bg-surface-hover); border-radius: 6px;
  }

  /* System info */
  .info-grid { display: flex; flex-direction: column; }
  .info-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
  .info-label { font-size: 13px; color: var(--text-secondary); }
  .info-value { display: flex; align-items: center; }
  .info-section-title { font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 4px; }

  .engine-status {
    display: inline-flex; align-items: center; gap: 4px; font-size: 12px; font-weight: 500;
  }
  .engine-status.available { color: var(--success); }
  .engine-status.unavailable { color: var(--error); }

  .info-disconnected {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 24px 16px; color: var(--text-muted); text-align: center;
  }
  .info-disconnected span { font-size: 13px; }

  /* Save */
  .save-section { margin-bottom: 24px; padding-top: 8px; }

  .btn-spinner {
    width: 16px; height: 16px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  /* Loading skeleton */
  .loading-state { animation: fadeIn 0.3s ease both; }
</style>
