<script lang="ts">
  let {
    value = 0,
    max = 100,
    label = "",
    showPercentage = true,
    variant = "brand",
    size = "md",
    animated = true,
    indeterminate = false,
  }: {
    value: number;
    max?: number;
    label?: string;
    showPercentage?: boolean;
    variant?: "brand" | "success" | "warning" | "error";
    size?: "sm" | "md" | "lg";
    animated?: boolean;
    indeterminate?: boolean;
  } = $props();

  const percentage = $derived(max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0);

  const heightMap: Record<string, string> = {
    sm: "4px",
    md: "8px",
    lg: "12px",
  };

  const colorMap: Record<string, string> = {
    brand: "var(--progress-fill)",
    success: "var(--progress-fill-success)",
    warning: "var(--warning)",
    error: "var(--error)",
  };
</script>

<div
  class="progress-container"
  role="progressbar"
  aria-valuenow={indeterminate ? undefined : percentage}
  aria-valuemin={0}
  aria-valuemax={100}
  aria-label={label || "進捗"}
>
  {#if label || showPercentage}
    <div class="progress-meta">
      {#if label}
        <span class="progress-label">{label}</span>
      {/if}
      {#if showPercentage && !indeterminate}
        <span class="progress-percentage">{percentage}%</span>
      {/if}
    </div>
  {/if}
  <div
    class="progress-track"
    style="height: {heightMap[size]}"
  >
    {#if indeterminate}
      <div
        class="progress-fill indeterminate"
        style="background: {colorMap[variant]}"
      ></div>
    {:else}
      <div
        class="progress-fill"
        class:animated
        style="width: {percentage}%; background: {colorMap[variant]}"
      ></div>
    {/if}
  </div>
</div>

<style>
  .progress-container {
    width: 100%;
    animation: fadeIn 0.3s ease both;
  }

  .progress-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .progress-label {
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .progress-percentage {
    font-size: 12px;
    font-weight: 600;
    color: var(--brand);
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    margin-left: 8px;
  }

  .progress-track {
    width: 100%;
    background: var(--progress-track);
    border-radius: 999px;
    overflow: hidden;
    position: relative;
  }

  .progress-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
  }

  .progress-fill.animated::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.15),
      transparent
    );
    animation: shimmer 2s ease-in-out infinite;
    background-size: 200% 100%;
  }

  .progress-fill.indeterminate {
    width: 40%;
    animation: indeterminate 1.5s ease-in-out infinite;
  }

  @keyframes indeterminate {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(350%); }
  }
</style>
