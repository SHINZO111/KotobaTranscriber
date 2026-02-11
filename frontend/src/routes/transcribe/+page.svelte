<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import FileSelector from "../../components/FileSelector.svelte";
  import ProgressBar from "../../components/ProgressBar.svelte";
  import { transcribe, cancelTranscription } from "../../lib/api";
  import { ws, getEventData } from "../../lib/websocket";
  import {
    isTranscribing,
    transcriptionProgress,
    transcriptionResult,
    transcriptionError,
    addToast,
  } from "../../lib/stores";
  import type { ProgressEventData, ErrorEventData } from "../../lib/types";

  let selectedFile = $state("");
  let enableDiarization = $state(false);
  let removeFillers = $state(true);
  let addPunctuation = $state(true);
  let formatParagraphs = $state(true);
  let useLLMCorrection = $state(false);
  let copied = $state(false);

  let unsubProgress: (() => void) | null = null;
  let unsubFinished: (() => void) | null = null;
  let unsubError: (() => void) | null = null;

  onMount(() => {
    unsubProgress = ws.on("progress", (e) => {
      const data = getEventData<ProgressEventData>(e);
      $transcriptionProgress = data.value ?? 0;
    });
    unsubFinished = ws.on("finished", (_e) => {
      // REST response is authoritative for result text (avoid race condition).
      // WS finished event is used only for progress indication.
      $transcriptionProgress = 100;
    });
    unsubError = ws.on("error", (e) => {
      const data = getEventData<ErrorEventData>(e);
      $transcriptionError = data.message ?? "エラーが発生しました";
      $isTranscribing = false;
    });
  });

  onDestroy(() => {
    unsubProgress?.();
    unsubFinished?.();
    unsubError?.();
  });

  async function startTranscription() {
    if (!selectedFile) return;
    $isTranscribing = true;
    $transcriptionProgress = 0;
    $transcriptionResult = "";
    $transcriptionError = null;

    try {
      const result = await transcribe({
        file_path: selectedFile,
        enable_diarization: enableDiarization,
        remove_fillers: removeFillers,
        add_punctuation: addPunctuation,
        format_paragraphs: formatParagraphs,
        use_llm_correction: useLLMCorrection,
      });
      $transcriptionResult = result.text;
      $transcriptionProgress = 100;
      addToast("success", "文字起こしが完了しました");
    } catch (e: unknown) {
      $transcriptionError = e instanceof Error ? e.message : String(e);
      addToast("error", "文字起こしに失敗しました");
    } finally {
      $isTranscribing = false;
    }
  }

  async function cancel() {
    try {
      await cancelTranscription();
      $isTranscribing = false;
      addToast("warning", "文字起こしをキャンセルしました");
    } catch {
      $isTranscribing = false;
      addToast("error", "キャンセルに失敗しました");
    }
  }

  async function copyResult() {
    try {
      await navigator.clipboard.writeText($transcriptionResult);
      copied = true;
      addToast("success", "クリップボードにコピーしました");
      setTimeout(() => copied = false, 2000);
    } catch {
      addToast("error", "コピーに失敗しました");
    }
  }

  function dismissError() {
    $transcriptionError = null;
  }

  const processingOptions = [
    { id: "fillers", label: "フィラー除去", desc: "「えー」「あの」などを除去", get: () => removeFillers, set: (v: boolean) => removeFillers = v },
    { id: "punctuation", label: "句読点付与", desc: "自動的に句読点を追加", get: () => addPunctuation, set: (v: boolean) => addPunctuation = v },
    { id: "paragraphs", label: "段落整形", desc: "文章を段落に分割", get: () => formatParagraphs, set: (v: boolean) => formatParagraphs = v },
    { id: "diarization", label: "話者分離", desc: "複数の話者を識別", get: () => enableDiarization, set: (v: boolean) => enableDiarization = v },
    { id: "llm", label: "LLM補正", desc: "AIによる文章校正", get: () => useLLMCorrection, set: (v: boolean) => useLLMCorrection = v },
  ];
</script>

<div class="page animate-fadeInUp">
  <!-- Page Header -->
  <header class="page-header">
    <div class="page-header-text">
      <h2 class="page-title">文字起こし</h2>
      <p class="page-description">音声ファイルをテキストに変換します</p>
    </div>
    {#if $isTranscribing}
      <span class="badge badge-warning">処理中</span>
    {/if}
  </header>

  <!-- File Selection -->
  <section class="section animate-fadeInUp stagger-1" aria-label="ファイル選択">
    <FileSelector
      bind:selectedFile
      disabled={$isTranscribing}
      label="音声ファイルを選択"
      accept="音声ファイル"
    />
  </section>

  <!-- Processing Options -->
  <section class="section animate-fadeInUp stagger-2" aria-label="処理オプション">
    <div class="card">
      <div class="card-header">
        <h3 class="card-title">処理オプション</h3>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/>
        </svg>
      </div>
      <div class="options-grid">
        {#each processingOptions as opt}
          <label class="option-card" class:active={opt.get()}>
            <input
              type="checkbox"
              checked={opt.get()}
              onchange={(e) => opt.set((e.target as HTMLInputElement).checked)}
              disabled={$isTranscribing}
            />
            <div class="option-text">
              <span class="option-label">{opt.label}</span>
              <span class="option-desc">{opt.desc}</span>
            </div>
          </label>
        {/each}
      </div>
    </div>
  </section>

  <!-- Actions -->
  <section class="actions-section animate-fadeInUp stagger-3">
    {#if $isTranscribing}
      <button class="btn btn-danger btn-lg" onclick={cancel}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
        </svg>
        キャンセル
      </button>
    {:else}
      <button
        class="btn btn-primary btn-lg"
        onclick={startTranscription}
        disabled={!selectedFile}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        文字起こし開始
      </button>
    {/if}
  </section>

  <!-- Progress -->
  {#if $isTranscribing}
    <section class="progress-section animate-fadeInUp" aria-label="進捗">
      <ProgressBar
        value={$transcriptionProgress}
        label="処理中..."
        animated
      />
    </section>
  {/if}

  <!-- Error -->
  {#if $transcriptionError}
    <section class="error-section animate-fadeInUp" role="alert">
      <div class="error-banner">
        <div class="error-content">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
          <span>{$transcriptionError}</span>
        </div>
        <button class="error-dismiss" onclick={dismissError} aria-label="エラーを閉じる">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </section>
  {/if}

  <!-- Result -->
  {#if $transcriptionResult}
    <section class="result-section animate-fadeInUp" aria-label="文字起こし結果">
      <div class="card">
        <div class="card-header">
          <h3 class="card-title">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--success)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
              <polyline points="22 4 12 14.01 9 11.01"/>
            </svg>
            結果
          </h3>
          <div class="result-actions">
            <button
              class="btn btn-outline btn-sm"
              onclick={copyResult}
            >
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
        <textarea
          class="result-textarea selectable"
          readonly
          aria-label="文字起こし結果"
        >{$transcriptionResult}</textarea>
      </div>
    </section>
  {:else if !$isTranscribing && !$transcriptionError}
    <!-- Empty State -->
    <section class="empty-state animate-fadeInUp stagger-4">
      <div class="empty-icon" aria-hidden="true">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </div>
      <p class="empty-title">音声ファイルを選択して文字起こしを開始</p>
      <p class="empty-hint">WAV, MP3, M4A, FLACなどの形式に対応</p>
    </section>
  {/if}
</div>

<style>
  .page {
    max-width: 720px;
    margin: 0 auto;
  }

  /* --- Header --- */
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 24px;
  }

  .page-header-text {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .page-title {
    font-size: 22px;
    font-weight: 700;
    margin: 0;
    letter-spacing: -0.02em;
    color: var(--text-primary);
  }

  .page-description {
    font-size: 13px;
    color: var(--text-tertiary);
    margin: 0;
  }

  /* --- Sections --- */
  .section {
    margin-bottom: 16px;
  }

  /* --- Card --- */
  .card {
    padding: 20px;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    margin: 0;
    color: var(--text-primary);
  }

  /* --- Options Grid --- */
  .options-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
  }

  .option-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border: 1px solid var(--border-light);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    user-select: none;
  }

  .option-card:hover {
    border-color: var(--border-medium);
    background: var(--bg-surface-hover);
  }

  .option-card.active {
    border-color: var(--brand-muted);
    background: var(--brand-subtle);
  }

  .option-text {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .option-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .option-desc {
    font-size: 11px;
    color: var(--text-muted);
  }

  /* --- Actions --- */
  .actions-section {
    margin-bottom: 16px;
  }

  /* --- Progress --- */
  .progress-section {
    margin-bottom: 16px;
    padding: 16px 20px;
    background: var(--bg-surface);
    border: 1px solid var(--border-default);
    border-radius: 12px;
  }

  /* --- Error --- */
  .error-section {
    margin-bottom: 16px;
  }

  .error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 12px 16px;
    background: var(--error-bg);
    border: 1px solid var(--error-border);
    border-radius: 10px;
  }

  .error-content {
    display: flex;
    align-items: center;
    gap: 10px;
    color: var(--error-text);
    font-size: 13px;
    min-width: 0;
  }

  .error-content svg {
    flex-shrink: 0;
  }

  .error-content span {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .error-dismiss {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: none;
    border: none;
    border-radius: 4px;
    color: var(--error-text);
    cursor: pointer;
    opacity: 0.6;
    transition: opacity 0.15s ease;
    padding: 0;
  }

  .error-dismiss:hover {
    opacity: 1;
  }

  /* --- Result --- */
  .result-section {
    margin-bottom: 16px;
  }

  .result-actions {
    display: flex;
    gap: 8px;
  }

  .result-textarea {
    width: 100%;
    min-height: 240px;
    padding: 16px;
    border: 1px solid var(--border-light);
    border-radius: 8px;
    background: var(--bg-input);
    color: var(--text-primary);
    font-family: 'Noto Sans JP', 'Inter', system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.8;
    resize: vertical;
  }

  /* --- Empty State --- */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px 24px;
    text-align: center;
  }

  .empty-icon {
    color: var(--text-muted);
    opacity: 0.3;
    margin-bottom: 16px;
  }

  .empty-title {
    font-size: 15px;
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0 0 6px;
  }

  .empty-hint {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
  }
</style>
