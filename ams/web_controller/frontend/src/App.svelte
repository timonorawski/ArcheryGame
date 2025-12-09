<script>
  import { onMount, onDestroy } from 'svelte';
  import GameState from './lib/GameState.svelte';
  import SessionInfo from './lib/SessionInfo.svelte';
  import ConnectionStatus from './lib/ConnectionStatus.svelte';
  import BackendSelector from './lib/BackendSelector.svelte';
  import PacingSelector from './lib/PacingSelector.svelte';
  import GameLauncher from './lib/GameLauncher.svelte';
  import GameControls from './lib/GameControls.svelte';
  import GameConfig from './lib/GameConfig.svelte';

  let ws = null;
  let reconnectInterval = null;
  let connected = false;

  // State from server
  let gameState = {
    game_name: 'No Game',
    level_name: '',
    state: 'idle',
    score: 0,
    time_elapsed: 0,
    hits: 0,
    misses: 0,
    extra: {},
  };

  let sessionInfo = {
    available_games: [],      // List of game slugs
    game_info: {},            // Map of slug -> { name, description, arguments }
    current_game: null,
    detection_backend: 'mouse',
    pacing: 'throwing',
    calibrated: false,
  };

  // Config screen state
  let configuringGame = null;  // Game object being configured, or null

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    console.log('Connecting to WebSocket:', wsUrl);
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      connected = true;
      if (reconnectInterval) {
        clearInterval(reconnectInterval);
        reconnectInterval = null;
      }
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      connected = false;
      // Reconnect after 2 seconds
      if (!reconnectInterval) {
        reconnectInterval = setInterval(connect, 2000);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleMessage(data);
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };
  }

  function handleMessage(data) {
    if (data.type === 'state') {
      if (data.game) {
        gameState = { ...gameState, ...data.game };
      }
      if (data.session) {
        sessionInfo = { ...sessionInfo, ...data.session };
      }
    } else if (data.type === 'command_response') {
      console.log('Command response:', data);
    }
  }

  function sendCommand(command, payload = {}) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ command, payload }));
    }
  }

  // Command handlers
  function handleSelectBackend(backend) {
    sendCommand('set_backend', { backend });
  }

  function handleCalibrate() {
    sendCommand('calibrate');
  }

  function handleGameSelect(gameSlug) {
    // Show config screen for this game
    const info = sessionInfo.game_info?.[gameSlug];
    if (info) {
      configuringGame = {
        slug: gameSlug,
        name: info.name,
        description: info.description,
        arguments: info.arguments || [],
      };
    } else {
      // No info available, launch directly with defaults
      sendCommand('launch_game', { game: gameSlug });
    }
  }

  function handleLaunchWithConfig(gameSlug, config) {
    // Launch game with configuration
    sendCommand('launch_game', { game: gameSlug, config });
    configuringGame = null;
  }

  function handleCancelConfig() {
    configuringGame = null;
  }

  function handleStopGame() {
    sendCommand('stop_game');
  }

  function handlePause() {
    sendCommand('pause');
  }

  function handleResume() {
    sendCommand('resume');
  }

  function handleRetrieval() {
    sendCommand('retrieval');
  }

  function handleGameAction(actionId) {
    sendCommand('game_action', { action: actionId });
  }

  function handleSelectPacing(pacing) {
    sendCommand('set_pacing', { pacing });
  }

  onMount(() => {
    connect();
  });

  onDestroy(() => {
    if (reconnectInterval) {
      clearInterval(reconnectInterval);
    }
    if (ws) {
      ws.close();
    }
  });

  // Derived state
  $: isGameRunning = gameState.state !== 'idle' && gameState.state !== 'ended';
</script>

<main>
  <header>
    <h1>AMS Controller</h1>
    <ConnectionStatus {connected} />
  </header>

  <div class="content">
    <!-- Backend and pacing selection (only when no game running) -->
    {#if !isGameRunning}
      <div class="settings-row">
        <BackendSelector
          currentBackend={sessionInfo.detection_backend}
          calibrated={sessionInfo.calibrated}
          onSelect={handleSelectBackend}
          onCalibrate={handleCalibrate}
        />
        <PacingSelector
          currentPacing={sessionInfo.pacing}
          onSelect={handleSelectPacing}
        />
      </div>
    {/if}

    <!-- Game launcher / current game -->
    <GameLauncher
      availableGames={sessionInfo.available_games}
      currentGame={sessionInfo.current_game}
      gameState={gameState.state}
      onLaunch={handleGameSelect}
      onStop={handleStopGame}
    />

    <!-- Game controls (pause/resume/retrieval + game actions) -->
    <GameControls
      gameState={gameState.state}
      actions={gameState.extra?.actions || []}
      onPause={handlePause}
      onResume={handleResume}
      onRetrieval={handleRetrieval}
      onAction={handleGameAction}
    />

    <!-- Game state display (when running) -->
    {#if isGameRunning}
      <GameState {gameState} />
    {/if}

    <!-- Session info (collapsible, less prominent) -->
    <details class="session-details">
      <summary>Session Info</summary>
      <SessionInfo {sessionInfo} />
    </details>
  </div>
</main>

<!-- Game config overlay -->
{#if configuringGame}
  <GameConfig
    game={configuringGame}
    pacing={sessionInfo.pacing}
    onLaunch={handleLaunchWithConfig}
    onCancel={handleCancelConfig}
  />
{/if}

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
    -webkit-tap-highlight-color: transparent;
  }

  main {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    padding: 16px;
    max-width: 480px;
    margin: 0 auto;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  h1 {
    color: #00d9ff;
    font-size: 24px;
    font-weight: 700;
  }

  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .settings-row {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .session-details {
    margin-top: 8px;
  }

  .session-details summary {
    color: #888;
    font-size: 14px;
    cursor: pointer;
    padding: 8px 0;
  }

  .session-details summary:hover {
    color: #aaa;
  }

  .session-details[open] summary {
    margin-bottom: 12px;
  }
</style>
