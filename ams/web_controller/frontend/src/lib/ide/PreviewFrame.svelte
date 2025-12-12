<script>
  import { onMount, onDestroy } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import yaml from 'js-yaml';

  const dispatch = createEventDispatcher();

  // Project files as YAML strings (keyed by path)
  // e.g., { 'game.yaml': '...', 'levels/level1.yaml': '...' }
  export let projectFiles = {};

  // Static engine URL (CDN or local build)
  export let engineUrl = '/pygbag/';

  let iframe;
  let isLoading = true;
  let engineReady = false;
  let error = null;
  let reloadTimeout;

  // Debounced send when projectFiles changes
  $: if (projectFiles && iframe && engineReady) {
    clearTimeout(reloadTimeout);
    reloadTimeout = setTimeout(() => {
      sendProjectFiles();
    }, 500);
  }

  /**
   * Convert YAML files to JSON and send to engine
   */
  function sendProjectFiles() {
    if (!iframe?.contentWindow) return;

    try {
      // Convert YAML files to JSON objects
      const jsonFiles = {};
      for (const [path, content] of Object.entries(projectFiles)) {
        if (path.endsWith('.yaml') || path.endsWith('.yml')) {
          // Parse YAML and store as JSON
          const jsonPath = path.replace(/\.ya?ml$/, '.json');
          try {
            const parsed = yaml.load(content);
            jsonFiles[jsonPath] = parsed;
          } catch (e) {
            console.error(`Failed to parse YAML: ${path}`, e);
            dispatch('parseError', { path, error: e.message });
            continue;
          }
        } else {
          // Non-YAML files (like .lua) pass through as strings
          jsonFiles[path] = content;
        }
      }

      // Send to engine via postMessage
      iframe.contentWindow.postMessage({
        source: 'ams_ide',
        type: 'project_files',
        files: jsonFiles
      }, '*');

      console.log('[PreviewFrame] Sent project files:', Object.keys(jsonFiles));
    } catch (e) {
      console.warn('Could not send project files:', e);
      error = e.message;
    }
  }

  /**
   * Send reload request to engine
   */
  function requestReload() {
    if (!iframe?.contentWindow) return;

    iframe.contentWindow.postMessage({
      source: 'ams_ide',
      type: 'reload'
    }, '*');
  }

  /**
   * Handle messages from the game engine
   */
  function handleMessage(event) {
    const msg = event.data;
    if (!msg || typeof msg !== 'object') return;

    // Only handle messages from our engine
    if (msg.source !== 'ams_engine') return;

    console.log('[PreviewFrame] Engine message:', msg.type);

    switch (msg.type) {
      case 'ready':
        // Engine is ready to receive files
        engineReady = true;
        isLoading = false;
        // Send initial project files
        if (Object.keys(projectFiles).length > 0) {
          sendProjectFiles();
        }
        break;

      case 'files_received':
        // Files were written, trigger reload
        console.log('[PreviewFrame] Files received:', msg.filesWritten);
        requestReload();
        break;

      case 'reloaded':
        // Game reloaded successfully
        error = null;
        dispatch('reloaded');
        break;

      case 'error':
        // Engine reported an error
        error = msg.message;
        dispatch('error', {
          message: msg.message,
          file: msg.file,
          line: msg.line
        });
        break;

      case 'log':
        // Forward logs to parent
        dispatch('log', { level: msg.level, message: msg.message });
        break;

      case 'pong':
        // Health check response
        console.log('[PreviewFrame] Engine alive, IDE mode:', msg.ideMode);
        break;
    }
  }

  function handleLoad() {
    // iframe loaded, but engine might not be ready yet
    console.log('[PreviewFrame] iframe loaded');
  }

  function handleError() {
    error = 'Failed to load game preview';
    isLoading = false;
  }

  function reload() {
    error = null;
    isLoading = true;
    engineReady = false;
    if (iframe) {
      iframe.src = iframe.src;
    }
  }

  onMount(() => {
    window.addEventListener('message', handleMessage);
  });

  onDestroy(() => {
    window.removeEventListener('message', handleMessage);
    clearTimeout(reloadTimeout);
  });
</script>

<div class="preview-container">
  <div class="preview-toolbar">
    <span class="preview-title">Preview</span>
    <div class="preview-status">
      {#if engineReady}
        <span class="status-dot ready"></span>
        <span>Ready</span>
      {:else if isLoading}
        <span class="status-dot loading"></span>
        <span>Loading...</span>
      {:else}
        <span class="status-dot disconnected"></span>
        <span>Disconnected</span>
      {/if}
    </div>
    <div class="preview-actions">
      <button class="preview-btn" on:click={sendProjectFiles} title="Send Files" disabled={!engineReady}>
        Send
      </button>
      <button class="preview-btn" on:click={reload} title="Reload">
        Reload
      </button>
    </div>
  </div>

  <div class="preview-content">
    {#if error}
      <div class="error-overlay">
        <div class="error-message">
          <h3>Error</h3>
          <pre>{error}</pre>
          <button class="btn" on:click={reload}>Retry</button>
        </div>
      </div>
    {/if}

    {#if isLoading && !engineReady}
      <div class="loading-overlay">
        <div class="spinner"></div>
        <p>Loading game engine...</p>
      </div>
    {/if}

    <iframe
      bind:this={iframe}
      src={engineUrl}
      title="Game Preview"
      on:load={handleLoad}
      on:error={handleError}
      sandbox="allow-scripts allow-same-origin"
    ></iframe>
  </div>
</div>

<style>
  .preview-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #1e1e1e;
  }

  .preview-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.375rem 0.75rem;
    background: #2d2d2d;
    border-bottom: 1px solid #3d3d3d;
    gap: 1rem;
  }

  .preview-title {
    font-size: 0.8125rem;
    color: #9d9d9d;
    text-transform: uppercase;
    font-weight: 500;
  }

  .preview-status {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 0.75rem;
    color: #9d9d9d;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }

  .status-dot.ready {
    background: #4ec9b0;
  }

  .status-dot.loading {
    background: #dcdcaa;
    animation: pulse 1s ease-in-out infinite;
  }

  .status-dot.disconnected {
    background: #f14c4c;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .preview-actions {
    display: flex;
    gap: 0.5rem;
  }

  .preview-btn {
    padding: 0.25rem 0.5rem;
    border: none;
    background: transparent;
    color: #9d9d9d;
    font-size: 0.75rem;
    cursor: pointer;
    border-radius: 3px;
  }

  .preview-btn:hover:not(:disabled) {
    background: #3d3d3d;
    color: #d4d4d4;
  }

  .preview-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .preview-content {
    flex: 1;
    position: relative;
    overflow: hidden;
  }

  iframe {
    width: 100%;
    height: 100%;
    border: none;
    background: #000;
  }

  .loading-overlay, .error-overlay {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(30, 30, 30, 0.95);
    z-index: 10;
  }

  .loading-overlay p {
    margin-top: 1rem;
    color: #9d9d9d;
  }

  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid #3d3d3d;
    border-top-color: #0e639c;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-message {
    text-align: center;
    padding: 2rem;
    max-width: 400px;
  }

  .error-message h3 {
    color: #f14c4c;
    margin-bottom: 1rem;
  }

  .error-message pre {
    background: #2d2d2d;
    padding: 1rem;
    border-radius: 4px;
    text-align: left;
    overflow-x: auto;
    margin-bottom: 1rem;
    font-size: 0.8125rem;
    color: #d4d4d4;
  }

  .btn {
    padding: 0.5rem 1rem;
    border: 1px solid #3d3d3d;
    background: #2d2d2d;
    color: #d4d4d4;
    border-radius: 4px;
    cursor: pointer;
  }

  .btn:hover {
    background: #3d3d3d;
  }
</style>
