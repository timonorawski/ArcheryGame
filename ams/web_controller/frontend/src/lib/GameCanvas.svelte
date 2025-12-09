<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';

  // Props
  export let game = 'containment';
  export let level = null;
  export let levelGroup = null;
  export let levelYaml = null;  // For authoring mode - YAML string to load
  export let pygbagUrl = '/pygbag/';  // Base URL for pygbag build

  const dispatch = createEventDispatcher();

  let iframe;
  let ready = false;
  let loading = true;
  let error = null;

  // Build URL with parameters
  $: iframeSrc = buildUrl(game, level, levelGroup);

  function buildUrl(game, level, levelGroup) {
    let url = `${pygbagUrl}index.html`;
    const params = new URLSearchParams();
    if (game) params.set('game', game);
    if (level) params.set('level', level);
    if (levelGroup) params.set('level_group', levelGroup);
    const qs = params.toString();
    return qs ? `${url}?${qs}` : url;
  }

  function sendToGame(message) {
    if (iframe?.contentWindow && ready) {
      iframe.contentWindow.postMessage(JSON.stringify(message), '*');
    }
  }

  // When levelYaml changes (authoring mode), send to game
  $: if (levelYaml && ready) {
    sendToGame({ type: 'load_level', yaml: levelYaml });
  }

  function handleMessage(event) {
    // Only process messages from our iframe
    if (event.source !== iframe?.contentWindow) return;

    try {
      const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;

      if (data.type === 'ready') {
        ready = true;
        loading = false;
        dispatch('ready');
      } else if (data.type === 'game_state') {
        dispatch('stateChange', data.data);
      } else if (data.type === 'level_applied') {
        dispatch('levelApplied', data.data);
      } else if (data.type === 'level_error') {
        dispatch('levelError', data.data);
      }
    } catch (e) {
      // Not a JSON message, ignore
    }
  }

  function handleIframeLoad() {
    // iframe loaded, but game may still be initializing
    // The 'ready' message from Python will confirm when it's fully ready
    setTimeout(() => {
      if (!ready) {
        // Give it some time, pygbag takes a while to initialize
        loading = true;
      }
    }, 100);
  }

  function handleIframeError() {
    error = 'Failed to load game';
    loading = false;
  }

  onMount(() => {
    window.addEventListener('message', handleMessage);
  });

  onDestroy(() => {
    window.removeEventListener('message', handleMessage);
  });

  // Expose methods to parent
  export function executeAction(actionId) {
    sendToGame({ type: 'action', action: actionId });
  }

  export function loadGame(gameSlug, levelSlug = null) {
    sendToGame({ type: 'load_game', game: gameSlug, level: levelSlug });
  }

  export function reload() {
    ready = false;
    loading = true;
    error = null;
    if (iframe) {
      iframe.src = iframeSrc;
    }
  }
</script>

<div class="game-canvas-container">
  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <span>Loading game...</span>
    </div>
  {/if}

  {#if error}
    <div class="error">
      <span>{error}</span>
      <button on:click={reload}>Retry</button>
    </div>
  {/if}

  <iframe
    bind:this={iframe}
    src={iframeSrc}
    title="AMS Game"
    class="game-iframe"
    class:hidden={loading || error}
    allow="autoplay; fullscreen"
    on:load={handleIframeLoad}
    on:error={handleIframeError}
  />
</div>

<style>
  .game-canvas-container {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #1a1a2e;
    border-radius: 8px;
    overflow: hidden;
  }

  .game-iframe {
    width: 100%;
    height: 100%;
    border: none;
  }

  .game-iframe.hidden {
    visibility: hidden;
  }

  .loading, .error {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    color: #888;
    font-size: 16px;
  }

  .spinner {
    width: 40px;
    height: 40px;
    border: 3px solid rgba(0, 217, 255, 0.2);
    border-top-color: #00d9ff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error {
    color: #ff6b6b;
  }

  .error button {
    padding: 8px 16px;
    background: #00d9ff;
    color: #000;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
  }

  .error button:hover {
    background: #00c4e6;
  }
</style>
