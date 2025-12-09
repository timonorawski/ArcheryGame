<script>
  export let availableGames = [];
  export let currentGame = null;
  export let gameState = 'idle';
  export let onLaunch = () => {};
  export let onStop = () => {};

  $: isRunning = gameState === 'playing' || gameState === 'paused' || gameState === 'retrieval';
</script>

<div class="card">
  <h2>Games</h2>

  {#if isRunning && currentGame}
    <div class="current-game">
      <div class="game-info">
        <span class="game-name">{currentGame}</span>
        <span class="game-status badge {gameState}">{gameState}</span>
      </div>
      <button class="stop-btn" on:click={onStop}>
        Stop Game
      </button>
    </div>
  {:else}
    <div class="games-grid">
      {#each availableGames as game}
        <button class="game-btn" on:click={() => onLaunch(game)}>
          <span class="game-name">{game}</span>
          <span class="play-icon">▶</span>
        </button>
      {:else}
        <p class="no-games">No games available</p>
      {/each}
    </div>
  {/if}
</div>

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

  .games-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .game-btn {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .game-btn:active {
    transform: scale(0.98);
    background: rgba(0, 217, 255, 0.1);
  }

  .game-btn .game-name {
    color: #fff;
    font-weight: 600;
    font-size: 16px;
  }

  .game-btn .play-icon {
    color: #00d9ff;
    font-size: 18px;
  }

  .no-games {
    color: #666;
    text-align: center;
    padding: 20px;
  }

  .current-game {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(0, 217, 255, 0.1);
    border: 1px solid rgba(0, 217, 255, 0.3);
    border-radius: 12px;
    padding: 16px;
  }

  .game-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .game-info .game-name {
    color: #fff;
    font-weight: 600;
    font-size: 16px;
  }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    width: fit-content;
  }

  .badge.playing {
    background: #00d9ff;
    color: #000;
  }

  .badge.paused {
    background: #ffab00;
    color: #000;
  }

  .badge.retrieval {
    background: #7c4dff;
    color: #fff;
  }

  .badge.idle {
    background: #666;
    color: #fff;
  }

  .stop-btn {
    background: #ff5252;
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .stop-btn:active {
    transform: scale(0.95);
    background: #ff1744;
  }
</style>
