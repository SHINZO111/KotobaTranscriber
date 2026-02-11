<script lang="ts">
  let {
    level = 0,
    showLabel = true,
  }: {
    level: number;
    showLabel?: boolean;
  } = $props();

  const percentage = $derived(Math.min(100, Math.round(level * 200)));

  const barColor = $derived(
    percentage > 80 ? "var(--error)" :
    percentage > 60 ? "var(--warning)" :
    "var(--success)"
  );

  // Generate 20 bar segments for visualizer effect
  const segments = 20;
</script>

<div class="volume-container" role="meter" aria-valuenow={percentage} aria-valuemin={0} aria-valuemax={100} aria-label="入力音量">
  {#if showLabel}
    <div class="volume-header">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
        {#if percentage > 0}
          <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
        {/if}
        {#if percentage > 40}
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
        {/if}
      </svg>
      <span class="volume-label">音量</span>
      <span class="volume-value" style="color: {barColor}">{percentage}%</span>
    </div>
  {/if}

  <div class="volume-visualizer">
    {#each Array(segments) as _, i}
      {@const segmentThreshold = (i / segments) * 100}
      {@const isActive = percentage > segmentThreshold}
      {@const segColor =
        segmentThreshold > 80 ? "var(--error)" :
        segmentThreshold > 60 ? "var(--warning)" :
        "var(--success)"
      }
      <div
        class="volume-segment"
        class:active={isActive}
        style="background: {isActive ? segColor : 'var(--progress-track)'}"
      ></div>
    {/each}
  </div>
</div>

<style>
  .volume-container {
    animation: fadeIn 0.3s ease both;
  }

  .volume-header {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 8px;
    color: var(--text-tertiary);
  }

  .volume-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .volume-value {
    font-size: 12px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    margin-left: auto;
    transition: color 0.2s ease;
  }

  .volume-visualizer {
    display: flex;
    gap: 2px;
    height: 24px;
    align-items: flex-end;
  }

  .volume-segment {
    flex: 1;
    height: 100%;
    border-radius: 2px;
    transition: background 0.08s ease, transform 0.08s ease;
    min-width: 3px;
  }

  .volume-segment.active {
    animation: segmentPop 0.15s ease both;
  }

  @keyframes segmentPop {
    0% { transform: scaleY(0.6); }
    60% { transform: scaleY(1.1); }
    100% { transform: scaleY(1); }
  }
</style>
