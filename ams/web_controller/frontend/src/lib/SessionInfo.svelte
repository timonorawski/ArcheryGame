<script>
  export let sessionInfo = {};
</script>

<div class="card">
  <h2>Session Info</h2>

  <div class="info-list">
    <div class="info-item">
      <span class="info-label">Detection</span>
      <span class="info-value">{sessionInfo.detection_backend || '-'}</span>
    </div>

    <div class="info-item">
      <span class="info-label">Calibrated</span>
      <span class="info-value">
        {#if sessionInfo.calibrated}
          <span class="badge success">Yes</span>
        {:else}
          <span class="badge warning">No</span>
        {/if}
      </span>
    </div>

    <div class="info-item">
      <span class="info-label">Games Available</span>
      <span class="info-value">{(sessionInfo.available_games || []).length}</span>
    </div>

    {#if sessionInfo.current_game}
      <div class="info-item">
        <span class="info-label">Current Game</span>
        <span class="info-value">{sessionInfo.current_game}</span>
      </div>
    {/if}
  </div>

  {#if sessionInfo.available_games && sessionInfo.available_games.length > 0}
    <div class="games-list">
      <div class="games-label">Available:</div>
      <div class="games">
        {#each sessionInfo.available_games as game}
          <span class="game-tag">{game}</span>
        {/each}
      </div>
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

  .info-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .info-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .info-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .info-label {
    color: #888;
    font-size: 14px;
  }

  .info-value {
    color: #fff;
    font-weight: 600;
    font-size: 14px;
  }

  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }

  .badge.success {
    background: #00c853;
    color: #000;
  }

  .badge.warning {
    background: #ff9800;
    color: #000;
  }

  .games-list {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .games-label {
    color: #888;
    font-size: 12px;
    margin-bottom: 8px;
  }

  .games {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .game-tag {
    background: rgba(0, 217, 255, 0.15);
    color: #00d9ff;
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 13px;
  }
</style>
