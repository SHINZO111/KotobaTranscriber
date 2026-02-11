<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";

  let {
    selectedFile = $bindable(""),
    disabled = false,
    label = "ファイルを選択",
    accept = "音声ファイル",
  }: {
    selectedFile: string;
    disabled?: boolean;
    label?: string;
    accept?: string;
  } = $props();

  let isDragOver = $state(false);

  async function selectFile() {
    try {
      const path = await invoke<string | null>("select_file");
      if (path) {
        selectedFile = path;
      }
    } catch (e) {
      console.error("File selection failed:", e);
    }
  }

  const fileName = $derived(
    selectedFile ? selectedFile.split(/[\\/]/).pop() || selectedFile : ""
  );

  const fileExt = $derived(
    fileName ? fileName.split(".").pop()?.toUpperCase() || "" : ""
  );

  function clearFile(e: Event) {
    e.stopPropagation();
    selectedFile = "";
  }
</script>

<div
  class="file-selector"
  class:has-file={!!selectedFile}
  class:disabled
  class:drag-over={isDragOver}
  role="button"
  tabindex={disabled ? -1 : 0}
  aria-label={selectedFile ? `選択済み: ${fileName}` : label}
  onclick={() => !disabled && selectFile()}
  onkeydown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !disabled) { e.preventDefault(); selectFile(); }}}
  ondragover={(e) => { e.preventDefault(); if (!disabled) isDragOver = true; }}
  ondragleave={() => isDragOver = false}
  ondrop={(e) => {
    e.preventDefault();
    isDragOver = false;
    if (disabled) return;
    const files = e.dataTransfer?.files;
    if (files && files.length > 0) {
      const file = files[0];
      // Tauri webview: file.path may contain the native path
      const path = (file as any).path || file.name;
      if (path) selectedFile = path;
    }
  }}
>
  {#if selectedFile}
    <!-- File selected state -->
    <div class="file-info">
      <div class="file-icon-wrapper">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--brand)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9 18V5l12-2v13"/>
          <circle cx="6" cy="18" r="3"/>
          <circle cx="18" cy="16" r="3"/>
        </svg>
      </div>
      <div class="file-details">
        <span class="file-name" title={selectedFile}>{fileName}</span>
        <span class="file-path" title={selectedFile}>{selectedFile}</span>
      </div>
      {#if fileExt}
        <span class="file-badge">{fileExt}</span>
      {/if}
      {#if !disabled}
        <button
          class="file-clear"
          onclick={clearFile}
          aria-label="選択を解除"
          title="選択を解除"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      {/if}
    </div>
  {:else}
    <!-- Empty state -->
    <div class="file-empty">
      <div class="file-empty-icon" aria-hidden="true">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
      </div>
      <div class="file-empty-text">
        <span class="file-empty-title">{label}</span>
        <span class="file-empty-hint">クリックまたはドラッグ&ドロップで{accept}を選択</span>
      </div>
    </div>
  {/if}
</div>

<style>
  .file-selector {
    border: 2px dashed var(--border-default);
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    background: var(--bg-surface);
    position: relative;
  }

  .file-selector:hover:not(.disabled) {
    border-color: var(--brand);
    background: var(--brand-subtle);
  }

  .file-selector:focus-visible {
    border-color: var(--brand);
    box-shadow: var(--shadow-focus);
  }

  .file-selector.drag-over {
    border-color: var(--brand);
    background: var(--brand-subtle);
    transform: scale(1.01);
  }

  .file-selector.has-file {
    border-style: solid;
    border-color: var(--border-default);
    background: var(--bg-surface);
    cursor: default;
  }

  .file-selector.has-file:hover:not(.disabled) {
    border-color: var(--border-medium);
    background: var(--bg-surface-hover);
  }

  .file-selector.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* --- File info (selected) --- */
  .file-info {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .file-icon-wrapper {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    background: var(--brand-subtle);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .file-details {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .file-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-path {
    font-size: 11px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .file-badge {
    flex-shrink: 0;
    padding: 2px 8px;
    background: var(--brand-subtle);
    color: var(--brand);
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.05em;
    border-radius: 4px;
    text-transform: uppercase;
  }

  .file-clear {
    flex-shrink: 0;
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
    transition: all 0.15s ease;
    padding: 0;
  }

  .file-clear:hover {
    background: var(--error-bg);
    color: var(--error);
  }

  /* --- Empty state --- */
  .file-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 12px 0;
  }

  .file-empty-icon {
    color: var(--text-muted);
    opacity: 0.5;
    transition: opacity 0.2s ease, color 0.2s ease;
  }

  .file-selector:hover:not(.disabled) .file-empty-icon {
    opacity: 0.8;
    color: var(--brand);
  }

  .file-empty-text {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }

  .file-empty-title {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .file-empty-hint {
    font-size: 12px;
    color: var(--text-muted);
  }
</style>
