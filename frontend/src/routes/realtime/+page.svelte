<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import VolumeBar from "../../components/VolumeBar.svelte";
  import {
    startRealtime,
    stopRealtime,
    pauseRealtime,
    resumeRealtime,
  } from "../../lib/api";
  import { ws, getEventData } from "../../lib/websocket";
  import { realtimeStatus, realtimeText, realtimeVolume, addToast } from "../../lib/stores";
  import type { TextReadyEventData, VolumeChangedEventData, ErrorEventData } from "../../lib/types";

  let modelSize = $state("base");
  let device = $state("auto");
  let bufferDuration = $state(3.0);
  let error = $state<string | null>(null);
  let copied = $state(false);
  let elapsedSeconds = $state(0);
  let elapsedTimer: ReturnType<typeof setInterval> | null = null;

  let unsubText: (() => void) | null = null;
  let unsubVolume: (() => void) | null = null;
  let unsubStatus: (() => void) | null = null;
  let unsubError: (() => void) | null = null;

  onMount(() => {
    unsubText = ws.on("text_ready", (e) => {
      const data = getEventData<TextReadyEventData>(e);
      const text = data.text ?? "";
      $realtimeText = $realtimeText ? $realtimeText + "\n" + text : text;
    });
    unsubVolume = ws.on("volume_changed", (e) => {
      const data = getEventData<VolumeChangedEventData>(e);
      $realtimeVolume = data.level ?? 0;
    });
    unsubStatus = ws.on("status_changed", (_e) => {
      // Status updates handled via store
    });
    unsubError = ws.on("error", (e) => {
      const data = getEventData<ErrorEventData>(e);
      error = data.message ?? "エラーが発生しました";
      $realtimeStatus = { is_running: false, is_paused: false, model_size: null };
      stopTimer();
    });
  });

  onDestroy(() => {
    unsubText?.();
    unsubVolume?.();
    unsubStatus?.();
    unsubError?.();
    stopTimer();
  });

  function startTimer() {
    stopTimer();
    elapsedSeconds = 0;
    elapsedTimer = setInterval(() => {
      if (!$realtimeStatus.is_paused) {
        elapsedSeconds++;
      }
    }, 1000);
  }

  function stopTimer() {
    if (elapsedTimer) {
      clearInterval(elapsedTimer);
      elapsedTimer = null;
    }
  }

  function formatTime(seconds: number): string {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  async function start() {
    error = null;
    try {
      await startRealtime({
        model_size: modelSize,
        device: device,
        buffer_duration: bufferDuration,
        vad_threshold: 0.5,
      });
      $realtimeStatus = { is_running: true, is_paused: false, model_size: modelSize };
      startTimer();
      addToast("info", "リアルタイム文字起こしを開始しました");
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
      addToast("error", "リアルタイム文字起こしの開始に失敗しました");
    }
  }

  async function stop() {
    try {
      await stopRealtime();
      $realtimeStatus = { is_running: false, is_paused: false, model_size: null };
      $realtimeVolume = 0;
      stopTimer();
      addToast("info", "リアルタイム文字起こしを停止しました");
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  async function togglePause() {
    try {
      if ($realtimeStatus.is_paused) {
        await resumeRealtime();
        $realtimeStatus = { ...$realtimeStatus, is_paused: false };
      } else {
        await pauseRealtime();
        $realtimeStatus = { ...$realtimeStatus, is_paused: true };
      }
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  function clearText() {
    $realtimeText = "";
  }

  async function copyText() {
    try {
      await navigator.clipboard.writeText($realtimeText);
      copied = true;
      addToast("success", "クリップボードにコピーしました");
      setTimeout(() => copied = false, 2000);
    } catch {
      addToast("error", "コピーに失敗しました");
    }
  }

  const modelOptions = [
    { value: "tiny", label: "tiny", desc: "最速・低精度" },
    { value: "base", label: "base", desc: "速い・普通" },
    { value: "small", label: "small", desc: "普通・良精度" },
    { value: "medium", label: "medium", desc: "遅い・高精度" },
    { value: "large-v3", label: "large-v3", desc: "最遅・最高精度" },
  ];

  const deviceOptions = [
    { value: "auto", label: "自動検出" },
    { value: "cpu", label: "CPU" },
    { value: "cuda", label: "CUDA (GPU)" },
  ];

  const statusText = $derived(
    $realtimeStatus.is_paused ? "一時停止中" :
    $realtimeStatus.is_running ? "録音中" :
    "待機中"
  );

  const wordCount = $derived(
    $realtimeText ? $realtimeText.replace(/\s+/g, '').length : 0
  );
</script>

<div class="page animate-fadeInUp">
  <!-- Page Header -->
  <header class="page-header">
    <div class="page-header-text">
      <h2 class="page-title">リアルタイム文字起こし</h2>
      <p class="page-description">マイクから音声を直接テキストに変換</p>
    </div>
    {#if $realtimeStatus.is_running}
      <div class="live-indicator" class:paused={$realtimeStatus.is_paused}>
        <span class="live-dot"></span>
        <span class="live-text">{statusText}</span>
      </div>
    {/if}
  </header>

  <!-- Configuration -->
  <section class="section animate-fadeInUp stagger-1" aria-label="設定">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          設定
        </h3>
      </div>
      <div class="settings-grid">
        <div class="setting-field">
          <label for="rt-model" class="setting-label">モデル</label>
          <select id="rt-model" bind:value={modelSize} disabled={$realtimeStatus.is_running}>
            {#each modelOptions as opt}
              <option value={opt.value}>{opt.label} ({opt.desc})</option>
            {/each}
          </select>
        </div>
        <div class="setting-field">
          <label for="rt-device" class="setting-label">デバイス</label>
          <select id="rt-device" bind:value={device} disabled={$realtimeStatus.is_running}>
            {#each deviceOptions as opt}
              <option value={opt.value}>{opt.label}</option>
            {/each}
          </select>
        </div>
        <div class="setting-field">
          <label for="rt-buffer" class="setting-label">バッファ</label>
          <div class="setting-input-group">
            <input
              id="rt-buffer"
              type="number"
              bind:value={bufferDuration}
              min={1}
              max={10}
              step={0.5}
              disabled={$realtimeStatus.is_running}
            />
            <span class="input-suffix">秒</span>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Controls -->
  <section class="controls-section animate-fadeInUp stagger-2" aria-label="録音コントロール">
    <div class="controls-row">
      <div class="primary-controls">
        {#if $realtimeStatus.is_running}
          <button class="btn-record btn-stop" onclick={stop} aria-label="録音を停止">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          </button>
          <button
            class="btn btn-outline"
            onclick={togglePause}
            aria-label={$realtimeStatus.is_paused ? "録音を再開" : "録音を一時停止"}
          >
            {#if $realtimeStatus.is_paused}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              再開
            {:else}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>
              </svg>
              一時停止
            {/if}
          </button>
        {:else}
          <button class="btn-record btn-start" onclick={start} aria-label="録音を開始">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </button>
        {/if}
      </div>
      <div class="secondary-controls">
        <button class="btn btn-ghost btn-sm" onclick={clearText} disabled={!$realtimeText}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          クリア
        </button>
        <button class="btn btn-ghost btn-sm" onclick={copyText} disabled={!$realtimeText}>
          {#if copied}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            コピー済み
          {:else}
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            コピー
          {/if}
        </button>
      </div>
    </div>

    <!-- Live Status Bar -->
    {#if $realtimeStatus.is_running}
      <div class="live-status-bar animate-fadeIn">
        <div class="status-info">
          <span class="status-time">{formatTime(elapsedSeconds)}</span>
          <span class="status-divider">|</span>
          <span class="status-model">{$realtimeStatus.model_size}</span>
          {#if wordCount > 0}
            <span class="status-divider">|</span>
            <span class="status-chars">{wordCount}文字</span>
          {/if}
        </div>
        <div class="volume-wrapper">
          <VolumeBar level={$realtimeVolume} showLabel={false} />
        </div>
      </div>
    {/if}
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

  <!-- Transcript -->
  <section class="transcript-section animate-fadeInUp stagger-3" aria-label="文字起こし結果">
    <div class="card transcript-card">
      {#if $realtimeText}
        <textarea
          class="transcript-area selectable"
          readonly
          aria-label="リアルタイム文字起こし結果"
        >{$realtimeText}</textarea>
      {:else}
        <div class="transcript-empty">
          <div class="transcript-empty-icon" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
              <line x1="12" y1="19" x2="12" y2="23"/>
              <line x1="8" y1="23" x2="16" y2="23"/>
            </svg>
          </div>
          <p class="transcript-empty-title">
            {$realtimeStatus.is_running ? "音声を待機中..." : "録音ボタンを押して開始"}
          </p>
          <p class="transcript-empty-hint">
            {$realtimeStatus.is_running
              ? "マイクに向かって話してください"
              : "リアルタイムで音声がテキストに変換されます"
            }
          </p>
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

  /* Live indicator */
  .live-indicator {
    display: flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 9999px;
    background: var(--error-bg); border: 1px solid var(--error-border);
    animation: breathe 2s ease-in-out infinite;
  }
  .live-indicator.paused {
    background: var(--warning-bg); border-color: var(--warning-border);
    animation: none;
  }
  .live-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--recording-color);
    animation: pulse 1.5s ease-in-out infinite;
  }
  .live-indicator.paused .live-dot {
    background: var(--warning);
    animation: none;
  }
  .live-text {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.05em; color: var(--error-text);
  }
  .live-indicator.paused .live-text { color: var(--warning-text); }

  /* Settings */
  .settings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; }
  .setting-field { display: flex; flex-direction: column; gap: 6px; }
  .setting-label { font-size: 12px; font-weight: 500; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.04em; }
  .setting-input-group { display: flex; align-items: center; gap: 6px; }
  .setting-input-group input { flex: 1; }
  .input-suffix { font-size: 12px; color: var(--text-muted); }

  /* Controls */
  .controls-section { margin-bottom: 16px; }
  .controls-row { display: flex; align-items: center; justify-content: space-between; }
  .primary-controls { display: flex; align-items: center; gap: 12px; }
  .secondary-controls { display: flex; gap: 4px; }

  .btn-record {
    width: 56px; height: 56px; border-radius: 50%; border: none;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-md);
  }
  .btn-record:hover { transform: scale(1.05); }
  .btn-record:active { transform: scale(0.95); }

  .btn-start {
    background: var(--success); color: white;
  }
  .btn-start:hover { background: var(--success-hover); box-shadow: 0 4px 16px rgba(34, 197, 94, 0.4); }

  .btn-stop {
    background: var(--error); color: white;
    animation: pulseGlow 2s ease-in-out infinite;
  }
  .btn-stop:hover { background: var(--error-hover); }

  /* Live status bar */
  .live-status-bar {
    display: flex; align-items: center; justify-content: space-between; gap: 16px;
    margin-top: 16px; padding: 10px 16px;
    background: var(--bg-surface); border: 1px solid var(--border-default);
    border-radius: 10px;
  }
  .status-info { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--text-tertiary); }
  .status-time { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--text-primary); font-size: 13px; }
  .status-divider { color: var(--border-medium); }
  .status-model { text-transform: uppercase; font-weight: 500; letter-spacing: 0.03em; }
  .status-chars { font-variant-numeric: tabular-nums; }
  .volume-wrapper { flex: 1; max-width: 200px; }

  /* Error */
  .error-section { margin-bottom: 16px; }
  .error-banner { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 10px; color: var(--error-text); font-size: 13px; }
  .error-banner span { flex: 1; }
  .error-dismiss { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: none; border: none; border-radius: 4px; color: var(--error-text); cursor: pointer; opacity: 0.6; transition: opacity 0.15s ease; padding: 0; }
  .error-dismiss:hover { opacity: 1; }

  /* Transcript */
  .transcript-section { flex: 1; }
  .transcript-card { padding: 0; overflow: hidden; }

  .transcript-area {
    width: 100%; min-height: 300px; padding: 20px;
    border: none; border-radius: 0;
    background: var(--bg-input); color: var(--text-primary);
    font-family: 'Noto Sans JP', 'Inter', system-ui, sans-serif;
    font-size: 15px; line-height: 1.9; resize: vertical;
    box-shadow: none;
  }
  .transcript-area:focus { box-shadow: none; }

  .transcript-empty {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 48px 24px; text-align: center;
  }
  .transcript-empty-icon { color: var(--text-muted); opacity: 0.25; margin-bottom: 16px; }
  .transcript-empty-title { font-size: 15px; font-weight: 500; color: var(--text-secondary); margin: 0 0 6px; }
  .transcript-empty-hint { font-size: 13px; color: var(--text-muted); margin: 0; }
</style>
