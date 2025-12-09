<script>
  import GameCanvas from './lib/GameCanvas.svelte';
  import GameSelector from './lib/GameSelector.svelte';

  let selectedGame = null;
  let selectedLevel = null;
  let selectedLevelGroup = null;
  let gameState = null;
  let gameCanvas;

  function handleGameSelect(event) {
    selectedGame = event.detail.game;
    selectedLevel = event.detail.level;
    selectedLevelGroup = event.detail.levelGroup;
  }

  function handleStateChange(event) {
    gameState = event.detail;
  }

  function handleAction(actionId) {
    gameCanvas?.executeAction(actionId);
  }

  function backToSelection() {
    selectedGame = null;
    selectedLevel = null;
    selectedLevelGroup = null;
    gameState = null;
  }
</script>

<main>
  <header>
    <h1>AMS Games</h1>
    {#if selectedGame}
      <button class="back-btn" on:click={backToSelection}>
        <span class="arrow">&larr;</span> Games
      </button>
    {:else}
      <a href="/" class="controller-link">Controller</a>
    {/if}
  </header>

  <div class="content">
    {#if !selectedGame}
      <GameSelector on:select={handleGameSelect} />
    {:else}
      <div class="game-view">
        <GameCanvas
          bind:this={gameCanvas}
          game={selectedGame}
          level={selectedLevel}
          levelGroup={selectedLevelGroup}
          on:stateChange={handleStateChange}
        />

        {#if gameState}
          <div class="game-info">
            <div class="score">Score: {gameState.score || 0}</div>
            <div class="state-badge" class:playing={gameState.state === 'playing'}>
              {gameState.state || 'loading'}
            </div>

            {#if gameState.actions?.length}
              <div class="actions">
                {#each gameState.actions as action}
                  <button
                    class="action-btn"
                    class:primary={action.style === 'primary'}
                    on:click={() => handleAction(action.id)}
                  >
                    {action.label}
                  </button>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</main>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1a1a2e;
    color: #eee;
    min-height: 100vh;
  }

  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    padding: 20px;
    max-width: 1200px;
    margin: 0 auto;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }

  h1 {
    color: #00d9ff;
    font-size: 28px;
    font-weight: 700;
  }

  .back-btn {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #ccc;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-family: inherit;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.2s;
  }

  .back-btn:hover {
    background: rgba(255, 255, 255, 0.15);
    border-color: #00d9ff;
    color: #00d9ff;
  }

  .arrow {
    font-size: 16px;
  }

  .controller-link {
    color: #888;
    text-decoration: none;
    font-size: 14px;
    padding: 8px 16px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    transition: all 0.2s;
  }

  .controller-link:hover {
    color: #00d9ff;
    border-color: #00d9ff;
  }

  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .game-view {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .game-info {
    display: flex;
    gap: 16px;
    align-items: center;
    flex-wrap: wrap;
    padding: 16px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 8px;
  }

  .score {
    font-size: 24px;
    font-weight: 600;
    color: #00d9ff;
  }

  .state-badge {
    font-size: 14px;
    padding: 4px 12px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.1);
    color: #888;
    text-transform: capitalize;
  }

  .state-badge.playing {
    background: rgba(0, 255, 100, 0.2);
    color: #0f0;
  }

  .actions {
    display: flex;
    gap: 8px;
    margin-left: auto;
  }

  .action-btn {
    padding: 8px 16px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    cursor: pointer;
    font-size: 14px;
    font-family: inherit;
    background: rgba(255, 255, 255, 0.1);
    color: #ccc;
    transition: all 0.2s;
  }

  .action-btn:hover {
    background: rgba(255, 255, 255, 0.15);
  }

  .action-btn.primary {
    background: #00d9ff;
    color: #000;
    border-color: #00d9ff;
  }

  .action-btn.primary:hover {
    background: #00c4e6;
  }

  @media (max-width: 600px) {
    main {
      padding: 16px;
    }

    h1 {
      font-size: 22px;
    }

    .game-info {
      flex-direction: column;
      align-items: flex-start;
    }

    .actions {
      margin-left: 0;
      width: 100%;
    }

    .action-btn {
      flex: 1;
    }
  }
</style>
