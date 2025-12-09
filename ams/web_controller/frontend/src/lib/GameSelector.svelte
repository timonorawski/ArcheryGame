<script>
  import { onMount, createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher();

  // Hard-coded game list (matching build.py BROWSER_GAMES)
  // In a more advanced setup, this could come from an API
  const games = [
    { slug: 'balloonpop', name: 'Balloon Pop', description: 'Pop the balloons before they escape' },
    { slug: 'containment', name: 'Containment', description: 'Keep the ball inside the boundary' },
    { slug: 'duckhunt', name: 'Duck Hunt', description: 'Classic arcade shooting game' },
    { slug: 'fruitslice', name: 'Fruit Slice', description: 'Slice the fruit, avoid the bombs' },
    { slug: 'gradient', name: 'Gradient', description: 'Color gradient test game' },
    { slug: 'grouping', name: 'Grouping', description: 'Group matching targets together' },
    { slug: 'growingtargets', name: 'Growing Targets', description: 'Hit targets as they grow' },
    { slug: 'loveometer', name: 'Love-O-Meter', description: 'Carnival love meter challenge' },
    { slug: 'manytargets', name: 'Many Targets', description: 'Hit as many targets as you can' },
  ];

  let selectedGame = null;
  let levels = [];
  let groups = [];
  let loadingLevels = false;

  async function selectGame(game) {
    selectedGame = game;
    loadingLevels = true;

    // Try to fetch levels for this game from API
    try {
      const res = await fetch(`/api/levels/${game.slug}`);
      if (res.ok) {
        const data = await res.json();
        levels = data.levels || [];
        groups = data.groups || [];
      } else {
        levels = [];
        groups = [];
      }
    } catch (e) {
      // API not available, just launch without level selection
      levels = [];
      groups = [];
    }
    loadingLevels = false;
  }

  function launchGame(level = null, group = null) {
    dispatch('select', {
      game: selectedGame.slug,
      level: level,
      levelGroup: group
    });
  }

  function back() {
    selectedGame = null;
    levels = [];
    groups = [];
  }
</script>

<div class="selector">
  {#if !selectedGame}
    <h2>Select a Game</h2>
    <div class="game-grid">
      {#each games as game}
        <button class="game-card" on:click={() => selectGame(game)}>
          <h3>{game.name}</h3>
          <p>{game.description}</p>
        </button>
      {/each}
    </div>
  {:else}
    <button class="back-link" on:click={back}>
      <span class="arrow">&larr;</span> Back to Games
    </button>

    <div class="game-detail">
      <h2>{selectedGame.name}</h2>
      <p class="description">{selectedGame.description}</p>

      <button class="play-btn primary" on:click={() => launchGame()}>
        Play Now
      </button>

      {#if loadingLevels}
        <p class="loading">Loading levels...</p>
      {:else}
        {#if groups.length > 0}
          <h3>Level Groups</h3>
          <div class="level-grid">
            {#each groups as group}
              <button class="level-card" on:click={() => launchGame(null, group.slug)}>
                <strong>{group.name}</strong>
                <span class="level-count">{group.levels?.length || 0} levels</span>
              </button>
            {/each}
          </div>
        {/if}

        {#if levels.length > 0}
          <h3>Individual Levels</h3>
          <div class="level-grid">
            {#each levels as level}
              <button class="level-card" on:click={() => launchGame(level.slug)}>
                <strong>{level.name}</strong>
                {#if level.difficulty}
                  <span class="stars">{'*'.repeat(level.difficulty)}</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      {/if}
    </div>
  {/if}
</div>

<style>
  .selector {
    width: 100%;
  }

  h2 {
    color: #00d9ff;
    margin: 0 0 20px;
    font-size: 24px;
  }

  h3 {
    color: #888;
    margin: 24px 0 12px;
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .game-grid, .level-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 16px;
  }

  .game-card, .level-card {
    background: #16213e;
    border: 2px solid #0f3460;
    border-radius: 12px;
    padding: 20px;
    text-align: left;
    cursor: pointer;
    transition: all 0.2s;
    color: inherit;
    font-family: inherit;
  }

  .game-card:hover, .level-card:hover {
    border-color: #00d9ff;
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0, 217, 255, 0.15);
  }

  .game-card h3 {
    color: #00d9ff;
    margin: 0 0 8px;
    font-size: 18px;
    text-transform: none;
    letter-spacing: normal;
  }

  .game-card p {
    color: #888;
    margin: 0;
    font-size: 14px;
    line-height: 1.4;
  }

  .level-card {
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .level-card strong {
    color: #eee;
    font-size: 15px;
  }

  .level-count {
    color: #666;
    font-size: 13px;
  }

  .stars {
    color: #ffd700;
    font-size: 14px;
  }

  .back-link {
    background: none;
    border: none;
    color: #888;
    cursor: pointer;
    font-size: 14px;
    padding: 8px 0;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    font-family: inherit;
  }

  .back-link:hover {
    color: #00d9ff;
  }

  .arrow {
    font-size: 18px;
  }

  .game-detail {
    text-align: center;
  }

  .description {
    color: #888;
    margin: 0 0 24px;
    font-size: 16px;
  }

  .play-btn {
    padding: 16px 48px;
    font-size: 18px;
    font-weight: 600;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
  }

  .play-btn.primary {
    background: linear-gradient(135deg, #00d9ff 0%, #00a8cc 100%);
    color: #000;
    box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3);
  }

  .play-btn.primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 217, 255, 0.4);
  }

  .loading {
    color: #666;
    font-style: italic;
    margin-top: 16px;
  }

  @media (max-width: 600px) {
    .game-grid, .level-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
