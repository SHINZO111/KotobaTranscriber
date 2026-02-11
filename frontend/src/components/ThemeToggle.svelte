<script lang="ts">
  import { theme } from "../lib/stores";

  function toggle() {
    $theme = $theme === "dark" ? "light" : "dark";
  }

  const isDark = $derived($theme === "dark");
</script>

<button
  class="theme-toggle"
  onclick={toggle}
  aria-label={isDark ? "ライトモードに切り替え" : "ダークモードに切り替え"}
  title={isDark ? "ライトモードに切り替え" : "ダークモードに切り替え"}
>
  <div class="toggle-track" class:dark={isDark}>
    <div class="toggle-thumb">
      {#if isDark}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      {:else}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      {/if}
    </div>
  </div>
  <span class="toggle-text">
    {isDark ? "ダークモード" : "ライトモード"}
  </span>
</button>

<style>
  .theme-toggle {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-primary);
    font-family: inherit;
  }

  .toggle-track {
    width: 48px;
    height: 26px;
    background: var(--border-medium);
    border-radius: 13px;
    position: relative;
    transition: background 0.3s ease;
    flex-shrink: 0;
  }

  .toggle-track.dark {
    background: var(--brand);
  }

  .toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 22px;
    height: 22px;
    background: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-sm);
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    color: var(--brand);
  }

  .toggle-track.dark .toggle-thumb {
    transform: translateX(22px);
  }

  .toggle-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
    transition: color 0.2s ease;
  }

  .theme-toggle:hover .toggle-text {
    color: var(--text-primary);
  }
</style>
