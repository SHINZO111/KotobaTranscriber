<script lang="ts">
  import { toasts, removeToast } from "../lib/stores";

  const iconMap: Record<string, string> = {
    success: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`,
    error: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    warning: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
    info: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };
</script>

<div class="toast-container" role="region" aria-label="通知" aria-live="polite">
  {#each $toasts as toast (toast.id)}
    <div
      class="toast toast-{toast.type}"
      role="alert"
      aria-atomic="true"
    >
      <span class="toast-icon" aria-hidden="true">
        {@html iconMap[toast.type] || iconMap.info}
      </span>
      <span class="toast-message">{toast.message}</span>
      <button
        class="toast-close"
        onclick={() => removeToast(toast.id)}
        aria-label="通知を閉じる"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </div>
  {/each}
</div>

<style>
  .toast-container {
    position: fixed;
    top: 16px;
    right: 16px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 400px;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    background: var(--toast-bg);
    border: 1px solid var(--toast-border);
    border-radius: 10px;
    box-shadow: var(--shadow-lg);
    animation: toastSlideIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) both;
    pointer-events: all;
    min-width: 280px;
  }

  .toast-success {
    border-left: 3px solid var(--success);
  }
  .toast-success .toast-icon { color: var(--success); }

  .toast-error {
    border-left: 3px solid var(--error);
  }
  .toast-error .toast-icon { color: var(--error); }

  .toast-warning {
    border-left: 3px solid var(--warning);
  }
  .toast-warning .toast-icon { color: var(--warning); }

  .toast-info {
    border-left: 3px solid var(--info);
  }
  .toast-info .toast-icon { color: var(--info); }

  .toast-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  .toast-message {
    flex: 1;
    font-size: 13px;
    line-height: 1.4;
    color: var(--text-primary);
  }

  .toast-close {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    background: none;
    border: none;
    border-radius: 6px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.15s ease;
    padding: 0;
  }

  .toast-close:hover {
    background: var(--bg-surface-hover);
    color: var(--text-primary);
  }
</style>
