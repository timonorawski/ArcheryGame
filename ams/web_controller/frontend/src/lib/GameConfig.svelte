<script>
  export let game = null;  // { slug, name, description, arguments }
  export let pacing = 'throwing';  // Global pacing from session
  export let onLaunch = () => {};
  export let onCancel = () => {};

  // Current configuration values - keyed by argument name
  let config = {};
  let lastGameSlug = null;  // Track which game we initialized for

  // Initialize config with defaults only when game actually changes
  $: if (game && game.slug !== lastGameSlug) {
    lastGameSlug = game.slug;
    const newConfig = {};
    for (const arg of game.arguments || []) {
      const key = argNameToKey(arg.name);
      // Use global pacing for --pacing arg, otherwise use arg default
      if (arg.name === '--pacing') {
        newConfig[key] = pacing;
      } else {
        newConfig[key] = arg.default;
      }
    }
    config = newConfig;
  }

  // Convert --arg-name to arg_name (Python kwarg format)
  function argNameToKey(name) {
    return name.replace(/^--/, '').replace(/-/g, '_');
  }

  // Get display label from arg name
  function argLabel(name) {
    return name
      .replace(/^--/, '')
      .replace(/-/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  }

  // Filter out pacing (handled globally) and action args (like --list-levels)
  $: visibleArgs = (game?.arguments || []).filter(arg =>
    arg.name !== '--pacing' && !arg.action
  );

  // Get the input type for an argument
  function getInputType(arg) {
    if (arg.choices && arg.choices.length > 0) {
      return 'select';
    }
    const type = arg.type?.toLowerCase?.() || arg.type;
    if (type === 'int' || type === 'float') {
      return 'number';
    }
    if (type === 'bool') {
      return 'checkbox';
    }
    return 'text';
  }

  // Handle input changes manually for proper reactivity
  function handleChange(argName, value, argType) {
    const key = argNameToKey(argName);
    // Convert string to number for int/float types
    const type = argType?.toLowerCase?.() || argType;
    if ((type === 'int' || type === 'float') && value !== '' && value !== null) {
      config[key] = type === 'int' ? parseInt(value, 10) : parseFloat(value);
    } else {
      config[key] = value;
    }
    // Trigger reactivity by reassigning
    config = config;
  }

  // Handle checkbox changes
  function handleCheckbox(argName, checked) {
    const key = argNameToKey(argName);
    config[key] = checked;
    config = config;
  }

  function handleLaunch() {
    // Filter out null/undefined values and convert to launch payload
    const cleanConfig = {};
    for (const [key, value] of Object.entries(config)) {
      if (value !== null && value !== undefined && value !== '') {
        cleanConfig[key] = value;
      }
    }
    onLaunch(game.slug, cleanConfig);
  }
</script>

<div class="config-overlay">
  <div class="config-card">
    <div class="header">
      <h2>{game?.name || 'Configure Game'}</h2>
      <p class="description">{game?.description || ''}</p>
    </div>

    <div class="config-form">
      {#if visibleArgs.length === 0}
        <p class="no-config">No configuration options for this game.</p>
      {:else}
        {#each visibleArgs as arg (arg.name)}
          {@const key = argNameToKey(arg.name)}
          {@const inputType = getInputType(arg)}
          <div class="form-group">
            <label for={arg.name}>{argLabel(arg.name)}</label>

            {#if inputType === 'select'}
              <!-- Dropdown for choices -->
              <select
                id={arg.name}
                value={config[key]}
                on:change={(e) => handleChange(arg.name, e.target.value, arg.type)}
              >
                {#each arg.choices as choice}
                  <option value={choice}>{choice}</option>
                {/each}
              </select>
            {:else if inputType === 'number'}
              <!-- Number input -->
              <input
                type="number"
                id={arg.name}
                value={config[key] ?? ''}
                on:input={(e) => handleChange(arg.name, e.target.value, arg.type)}
                placeholder={arg.default !== null ? String(arg.default) : 'default'}
                step={arg.type === 'float' ? '0.1' : '1'}
              />
            {:else if inputType === 'checkbox'}
              <!-- Checkbox -->
              <input
                type="checkbox"
                id={arg.name}
                checked={config[key] ?? false}
                on:change={(e) => handleCheckbox(arg.name, e.target.checked)}
              />
            {:else}
              <!-- Text input (string) -->
              <input
                type="text"
                id={arg.name}
                value={config[key] ?? ''}
                on:input={(e) => handleChange(arg.name, e.target.value, arg.type)}
                placeholder={arg.default || 'default'}
              />
            {/if}

            {#if arg.help}
              <span class="help">{arg.help}</span>
            {/if}
          </div>
        {/each}
      {/if}
    </div>

    <div class="actions">
      <button class="cancel-btn" on:click={onCancel}>Cancel</button>
      <button class="launch-btn" on:click={handleLaunch}>Launch Game</button>
    </div>
  </div>
</div>

<style>
  .config-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    z-index: 100;
  }

  .config-card {
    background: #16213e;
    border-radius: 16px;
    padding: 24px;
    width: 100%;
    max-width: 400px;
    max-height: 80vh;
    overflow-y: auto;
  }

  .header {
    margin-bottom: 20px;
  }

  .header h2 {
    color: #00d9ff;
    font-size: 20px;
    margin-bottom: 8px;
  }

  .header .description {
    color: #888;
    font-size: 14px;
  }

  .config-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-bottom: 24px;
  }

  .no-config {
    color: #666;
    text-align: center;
    padding: 20px;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .form-group label {
    color: #ccc;
    font-size: 14px;
    font-weight: 600;
  }

  .form-group input[type="text"],
  .form-group input[type="number"],
  .form-group select {
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 8px;
    padding: 10px 12px;
    color: #fff;
    font-size: 14px;
  }

  .form-group input[type="text"]:focus,
  .form-group input[type="number"]:focus,
  .form-group select:focus {
    outline: none;
    border-color: #00d9ff;
  }

  .form-group input[type="checkbox"] {
    width: 20px;
    height: 20px;
    cursor: pointer;
  }

  .form-group .help {
    color: #666;
    font-size: 12px;
  }

  .actions {
    display: flex;
    gap: 12px;
  }

  .cancel-btn {
    flex: 1;
    background: rgba(255, 255, 255, 0.1);
    color: #ccc;
    border: none;
    border-radius: 8px;
    padding: 12px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .cancel-btn:active {
    transform: scale(0.95);
    background: rgba(255, 255, 255, 0.15);
  }

  .launch-btn {
    flex: 2;
    background: #00d9ff;
    color: #000;
    border: none;
    border-radius: 8px;
    padding: 12px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .launch-btn:active {
    transform: scale(0.95);
    background: #00b8d9;
  }
</style>
