<script>
  export let gameState = 'idle';
  export let actions = [];  // Available game actions from server
  export let onPause = () => {};
  export let onResume = () => {};
  export let onRetrieval = () => {};
  export let onAction = (actionId) => {};  // Handler for game actions

  $: isPlaying = gameState === 'playing';
  $: isPaused = gameState === 'paused';
  $: isRetrieval = gameState === 'retrieval';
  $: showControls = isPlaying || isPaused || isRetrieval || actions.length > 0;
</script>

{#if showControls}
  <div class="card">
    <h2>Controls</h2>

    <div class="controls">
      {#if isPlaying}
        <button class="control-btn pause" on:click={onPause}>
          <span class="icon">⏸</span>
          <span class="label">Pause</span>
        </button>
        <button class="control-btn retrieval" on:click={onRetrieval}>
          <span class="icon">🎯</span>
          <span class="label">Retrieve</span>
        </button>
      {:else if isPaused}
        <button class="control-btn resume" on:click={onResume}>
          <span class="icon">▶️</span>
          <span class="label">Resume</span>
        </button>
        <button class="control-btn retrieval" on:click={onRetrieval}>
          <span class="icon">🎯</span>
          <span class="label">Retrieve</span>
        </button>
      {:else if isRetrieval}
        <button class="control-btn resume" on:click={onResume}>
          <span class="icon">▶️</span>
          <span class="label">Resume</span>
        </button>
        <p class="retrieval-hint">Retrieve your projectiles, then tap Resume</p>
      {/if}

      <!-- Game-specific actions -->
      {#each actions as action (action.id)}
        <button
          class="control-btn action {action.style || 'secondary'}"
          on:click={() => onAction(action.id)}
        >
          <span class="label">{action.label}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .card {
    background: #16213e;
    border-radius: 16px;
    padding: 20px;
  }

  h2 {
    color: #00d9ff;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin-bottom: 16px;
    opacity: 0.8;
  }

  .controls {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }

  .control-btn {
    flex: 1;
    min-width: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    padding: 20px 16px;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .control-btn:active {
    transform: scale(0.95);
  }

  .control-btn .icon {
    font-size: 32px;
  }

  .control-btn .label {
    font-weight: 600;
    font-size: 14px;
  }

  .control-btn.pause {
    background: #ffab00;
    color: #000;
  }

  .control-btn.resume {
    background: #00c853;
    color: #000;
  }

  .control-btn.retrieval {
    background: #7c4dff;
    color: #fff;
  }

  /* Game action styles */
  .control-btn.action.primary {
    background: #00d9ff;
    color: #000;
  }

  .control-btn.action.secondary {
    background: rgba(255, 255, 255, 0.1);
    color: #ccc;
  }

  .control-btn.action.danger {
    background: #ff5252;
    color: #fff;
  }

  .retrieval-hint {
    width: 100%;
    text-align: center;
    color: #888;
    font-size: 14px;
    margin-top: 8px;
  }
</style>
