<script>
  export let gameState = {};

  $: formattedTime = formatTime(gameState.time_elapsed || 0);
  $: accuracy = calculateAccuracy(gameState.hits, gameState.misses);

  function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  function calculateAccuracy(hits, misses) {
    const total = hits + misses;
    if (total === 0) return '-';
    return Math.round((hits / total) * 100) + '%';
  }

  function getStateClass(state) {
    return state || 'idle';
  }
</script>

<div class="card">
  <h2>Game State</h2>

  <div class="game-header">
    <div class="game-name">{gameState.game_name || 'No Game'}</div>
    {#if gameState.level_name}
      <div class="level-name">{gameState.level_name}</div>
    {/if}
  </div>

  <div class="state-badge-container">
    <span class="state-badge {getStateClass(gameState.state)}">
      {gameState.state || 'idle'}
    </span>
  </div>

  <div class="stats-grid">
    <div class="stat">
      <div class="stat-value">{gameState.score || 0}</div>
      <div class="stat-label">Score</div>
    </div>
    <div class="stat">
      <div class="stat-value">{formattedTime}</div>
      <div class="stat-label">Time</div>
    </div>
    <div class="stat">
      <div class="stat-value">{gameState.hits || 0}</div>
      <div class="stat-label">Hits</div>
    </div>
    <div class="stat">
      <div class="stat-value">{accuracy}</div>
      <div class="stat-label">Accuracy</div>
    </div>
  </div>
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

  .game-header {
    margin-bottom: 12px;
  }

  .game-name {
    font-size: 22px;
    font-weight: 700;
    color: #fff;
  }

  .level-name {
    font-size: 14px;
    color: #888;
    margin-top: 4px;
  }

  .state-badge-container {
    margin-bottom: 20px;
  }

  .state-badge {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .state-badge.idle {
    background: #444;
    color: #aaa;
  }

  .state-badge.playing {
    background: #00d9ff;
    color: #000;
  }

  .state-badge.paused {
    background: #ffab00;
    color: #000;
  }

  .state-badge.retrieval {
    background: #9c27b0;
    color: #fff;
  }

  .state-badge.ended {
    background: #666;
    color: #fff;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }

  .stat {
    text-align: center;
    padding: 12px;
    background: rgba(0, 217, 255, 0.05);
    border-radius: 12px;
  }

  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #fff;
  }

  .stat-label {
    font-size: 11px;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 4px;
  }
</style>
