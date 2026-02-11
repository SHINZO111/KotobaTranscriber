<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import ProgressBar from "../../components/ProgressBar.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { batchTranscribe, cancelBatch } from "../../lib/api";
  import { ws, getEventData } from "../../lib/websocket";
  import {
    isBatchProcessing,
    batchProgress,
    batchResults,
    addToast,
  } from "../../lib/stores";
  import type { BatchProgressEventData, FileFinishedEventData, AllFinishedEventData } from "../../lib/types";

  let selectedFiles = $state<string[]>([]);
  let enableDiarization = $state(false);
  let removeFillers = $state(true);
  let addPunctuation = $state(true);
  let maxWorkers = $state(3);
  let error = $state<string | null>(null);

  let unsubProgress: (() => void) | null = null;
  let unsubFileFinished: (() => void) | null = null;
  let unsubAllFinished: (() => void) | null = null;

  onMount(() => {
    unsubProgress = ws.on("batch_progress", (e) => {
      const data = getEventData<BatchProgressEventData>(e);
      $batchProgress = {
        completed: data.completed ?? 0,
        total: data.total ?? 0,
        filename: data.filename ?? "",
      };
    });
    unsubFileFinished = ws.on("file_finished", (e) => {
      const data = getEventData<FileFinishedEventData>(e);
      $batchResults = [
        ...$batchResults,
        {
          file_path: data.file_path ?? "",
          text: data.text ?? "",
          success: data.success ?? false,
        },
      ];
    });
    unsubAllFinished = ws.on("all_finished", (e) => {
      $isBatchProcessing = false;
      const data = getEventData<AllFinishedEventData>(e);
      const success = data.success_count ?? 0;
      const failed = data.failed_count ?? 0;
      addToast("success", `バッチ処理完了: ${success}件成功、${failed}件失敗`);
    });
  });

  onDestroy(() => {
    unsubProgress?.();
    unsubFileFinished?.();
    unsubAllFinished?.();
  });

  async function selectFiles() {
    try {
      const paths = await invoke<string[]>("select_files");
      if (paths.length > 0) {
        selectedFiles = [...selectedFiles, ...paths];
      }
    } catch (e) {
      console.error("File selection failed:", e);
    }
  }

  function removeFile(index: number) {
    selectedFiles = selectedFiles.filter((_, i) => i !== index);
  }

  async function startBatch() {
    if (selectedFiles.length === 0) return;
    $isBatchProcessing = true;
    $batchProgress = { completed: 0, total: selectedFiles.length, filename: "" };
    $batchResults = [];
    error = null;

    try {
      await batchTranscribe({
        file_paths: selectedFiles,
        enable_diarization: enableDiarization,
        max_workers: maxWorkers,
        remove_fillers: removeFillers,
        add_punctuation: addPunctuation,
      });
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : String(e);
      $isBatchProcessing = false;
      addToast("error", "バッチ処理の開始に失敗しました");
    }
  }

  async function cancel() {
    try {
      await cancelBatch();
      $isBatchProcessing = false;
      addToast("warning", "バッチ処理をキャンセルしました");
    } catch {
      $isBatchProcessing = false;
      addToast("error", "キャンセルに失敗しました");
    }
  }

  function clearAll() {
    selectedFiles = [];
    $batchResults = [];
    error = null;
  }

  const successCount = $derived($batchResults.filter((r) => r.success).length);
  const failedCount = $derived($batchResults.filter((r) => !r.success).length);

  function getFileName(path: string): string {
    return path.split(/[\\/]/).pop() || path;
  }

  function getFileExt(name: string): string {
    return name.split(".").pop()?.toUpperCase() || "";
  }
</script>

<div class="page animate-fadeInUp">
  <!-- Page Header -->
  <header class="page-header">
    <div class="page-header-text">
      <h2 class="page-title">バッチ処理</h2>
      <p class="page-description">複数の音声ファイルを一括で文字起こし</p>
    </div>
    {#if $isBatchProcessing}
      <span class="badge badge-warning">処理中</span>
    {:else if $batchResults.length > 0}
      <span class="badge badge-success">完了</span>
    {/if}
  </header>

  <!-- File Selection -->
  <section class="section animate-fadeInUp stagger-1" aria-label="ファイル選択">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">ファイル一覧</h3>
        <div class="card-actions">
          <button
            class="btn btn-outline btn-sm"
            onclick={selectFiles}
            disabled={$isBatchProcessing}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            追加
          </button>
          {#if selectedFiles.length > 0}
            <button
              class="btn btn-ghost btn-sm"
              onclick={clearAll}
              disabled={$isBatchProcessing}
            >
              クリア
            </button>
          {/if}
        </div>
      </div>

      {#if selectedFiles.length > 0}
        <div class="file-list-wrapper">
          <ul class="file-list" role="list" aria-label="選択されたファイル">
            {#each selectedFiles as file, i}
              {@const name = getFileName(file)}
              {@const ext = getFileExt(name)}
              <li class="file-list-item" style="animation-delay: {i * 30}ms">
                <div class="file-list-icon" aria-hidden="true">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>
                  </svg>
                </div>
                <span class="file-list-name" title={file}>{name}</span>
                {#if ext}
                  <span class="file-list-ext">{ext}</span>
                {/if}
                {#if !$isBatchProcessing}
                  <button
                    class="file-list-remove"
                    onclick={() => removeFile(i)}
                    aria-label="ファイルを削除: {name}"
                    title="削除"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </button>
                {/if}
              </li>
            {/each}
          </ul>
        </div>
        <div class="file-count">
          {selectedFiles.length}個のファイルが選択されています
        </div>
      {:else}
        <div class="empty-inline" role="button" tabindex="0" onclick={selectFiles} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFiles(); } }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            <line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>
          </svg>
          <span>クリックしてファイルを追加</span>
        </div>
      {/if}
    </div>
  </section>

  <!-- Options -->
  <section class="section animate-fadeInUp stagger-2" aria-label="バッチオプション">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">オプション</h3>
      </div>
      <div class="options-row">
        <label class="option-inline">
          <input type="checkbox" bind:checked={removeFillers} disabled={$isBatchProcessing} />
          <span>フィラー除去</span>
        </label>
        <label class="option-inline">
          <input type="checkbox" bind:checked={addPunctuation} disabled={$isBatchProcessing} />
          <span>句読点付与</span>
        </label>
        <label class="option-inline">
          <input type="checkbox" bind:checked={enableDiarization} disabled={$isBatchProcessing} />
          <span>話者分離</span>
        </label>
        <div class="option-number">
          <label for="batch-workers">並列数:</label>
          <input
            id="batch-workers"
            type="number"
            bind:value={maxWorkers}
            min={1}
            max={8}
            disabled={$isBatchProcessing}
          />
        </div>
      </div>
    </div>
  </section>

  <!-- Actions -->
  <section class="actions-section animate-fadeInUp stagger-3">
    {#if $isBatchProcessing}
      <button class="btn btn-danger btn-lg" onclick={cancel}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        </svg>
        キャンセル
      </button>
    {:else}
      <button
        class="btn btn-primary btn-lg"
        onclick={startBatch}
        disabled={selectedFiles.length === 0}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        バッチ処理開始 ({selectedFiles.length}件)
      </button>
    {/if}
  </section>

  <!-- Progress -->
  {#if $isBatchProcessing}
    <section class="progress-section animate-fadeInUp" aria-label="進捗">
      <ProgressBar
        value={$batchProgress.completed}
        max={$batchProgress.total || 1}
        label={$batchProgress.filename ? `処理中: ${getFileName($batchProgress.filename)}` : "処理中..."}
        animated
      />
      <div class="progress-detail">
        {$batchProgress.completed} / {$batchProgress.total} 完了
      </div>
    </section>
  {/if}

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

  <!-- Results -->
  {#if $batchResults.length > 0}
    <section class="results-section animate-fadeInUp" aria-label="バッチ結果">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">結果</h3>
          <div class="result-stats">
            <span class="stat-badge stat-success">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
              {successCount}
            </span>
            {#if failedCount > 0}
              <span class="stat-badge stat-error">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                {failedCount}
              </span>
            {/if}
          </div>
        </div>
        <ul class="results-list" role="list">
          {#each $batchResults as result, i}
            <li class="result-item" class:success={result.success} class:failed={!result.success} style="animation-delay: {i * 40}ms">
              <div class="result-status" aria-hidden="true">
                {#if result.success}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--error)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                {/if}
              </div>
              <span class="result-name">{getFileName(result.file_path)}</span>
              <span class="result-label" aria-label={result.success ? "成功" : "失敗"}>
                {result.success ? "完了" : "失敗"}
              </span>
            </li>
          {/each}
        </ul>
      </div>
    </section>
  {/if}
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
  .card-actions { display: flex; gap: 6px; }

  /* File list */
  .file-list-wrapper { max-height: 240px; overflow-y: auto; margin: 0 -4px; padding: 0 4px; }
  .file-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
  .file-list-item {
    display: flex; align-items: center; gap: 10px; padding: 8px 10px;
    border-radius: 8px; transition: background 0.15s ease; animation: fadeInUp 0.3s ease both;
  }
  .file-list-item:hover { background: var(--bg-surface-hover); }
  .file-list-icon { flex-shrink: 0; color: var(--text-muted); }
  .file-list-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-list-ext { flex-shrink: 0; font-size: 10px; font-weight: 700; color: var(--brand); background: var(--brand-subtle); padding: 1px 6px; border-radius: 3px; letter-spacing: 0.04em; }
  .file-list-remove {
    flex-shrink: 0; display: flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; background: none; border: none; border-radius: 6px;
    color: var(--text-muted); cursor: pointer; opacity: 0; transition: all 0.15s ease; padding: 0;
  }
  .file-list-item:hover .file-list-remove { opacity: 1; }
  .file-list-remove:hover { background: var(--error-bg); color: var(--error); }

  .file-count { padding-top: 12px; border-top: 1px solid var(--border-light); margin-top: 12px; font-size: 12px; color: var(--text-muted); text-align: center; }

  .empty-inline {
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 24px; color: var(--text-muted); cursor: pointer; border-radius: 8px;
    transition: all 0.2s ease; border: 2px dashed var(--border-default);
  }
  .empty-inline:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-subtle); }
  .empty-inline span { font-size: 13px; }

  /* Options */
  .options-row { display: flex; flex-wrap: wrap; gap: 16px; align-items: center; }
  .option-inline { display: flex; align-items: center; gap: 8px; font-size: 13px; cursor: pointer; user-select: none; color: var(--text-secondary); }
  .option-number { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-secondary); margin-left: auto; }
  .option-number input { width: 60px; text-align: center; }

  /* Actions */
  .actions-section { margin-bottom: 16px; }

  /* Progress */
  .progress-section { margin-bottom: 16px; padding: 16px 20px; background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 12px; }
  .progress-detail { margin-top: 8px; font-size: 12px; color: var(--text-muted); text-align: center; font-variant-numeric: tabular-nums; }

  /* Error */
  .error-section { margin-bottom: 16px; }
  .error-banner { display: flex; align-items: center; gap: 10px; padding: 12px 16px; background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 10px; color: var(--error-text); font-size: 13px; }
  .error-banner span { flex: 1; }
  .error-dismiss { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: none; border: none; border-radius: 4px; color: var(--error-text); cursor: pointer; opacity: 0.6; transition: opacity 0.15s ease; padding: 0; }
  .error-dismiss:hover { opacity: 1; }

  /* Results */
  .results-section { margin-bottom: 16px; }
  .result-stats { display: flex; gap: 8px; }
  .stat-badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 9999px; font-size: 12px; font-weight: 600; }
  .stat-success { background: var(--success-bg); color: var(--success-text); }
  .stat-error { background: var(--error-bg); color: var(--error-text); }

  .results-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
  .result-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; animation: fadeInUp 0.3s ease both; }
  .result-item:hover { background: var(--bg-surface-hover); }
  .result-status { flex-shrink: 0; }
  .result-name { flex: 1; font-size: 13px; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .result-label { flex-shrink: 0; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em; }
  .result-item.success .result-label { color: var(--success-text); }
  .result-item.failed .result-label { color: var(--error-text); }
</style>
