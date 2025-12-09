<script>
  export let currentBackend = 'mouse';
  export let calibrated = false;
  export let onSelect = () => {};
  export let onCalibrate = () => {};

  const backends = [
    { id: 'mouse', label: 'Mouse', icon: '🖱️', desc: 'Development mode' },
    { id: 'laser', label: 'Laser', icon: '🔴', desc: 'Laser pointer' },
    { id: 'object', label: 'Object', icon: '🎯', desc: 'Darts/arrows' },
  ];

  function selectBackend(id) {
    if (id !== currentBackend) {
      onSelect(id);
    }
  }
</script>

<div class="card">
  <h2>Detection Backend</h2>

  <div class="backends">
    {#each backends as backend}
      <button
        class="backend-btn"
        class:selected={currentBackend === backend.id}
        on:click={() => selectBackend(backend.id)}
      >
        <span class="icon">{backend.icon}</span>
        <span class="label">{backend.label}</span>
        <span class="desc">{backend.desc}</span>
      </button>
    {/each}
  </div>

  <div class="calibration-row">
    <div class="calibration-status">
      {#if calibrated}
        <span class="badge success">Calibrated</span>
      {:else}
        <span class="badge warning">Not Calibrated</span>
      {/if}
    </div>
    {#if currentBackend !== 'mouse'}
      <button class="calibrate-btn" on:click={onCalibrate}>
        {calibrated ? 'Recalibrate' : 'Calibrate'}
      </button>
    {/if}
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

  .backends {
    display: flex;
    gap: 8px;
  }

  .backend-btn {
    flex: 1;
    background: rgba(255, 255, 255, 0.05);
    border: 2px solid transparent;
    border-radius: 12px;
    padding: 12px 8px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    transition: all 0.2s;
  }

  .backend-btn:active {
    transform: scale(0.95);
  }

  .backend-btn.selected {
    border-color: #00d9ff;
    background: rgba(0, 217, 255, 0.1);
  }

  .backend-btn .icon {
    font-size: 24px;
  }

  .backend-btn .label {
    color: #fff;
    font-weight: 600;
    font-size: 14px;
  }

  .backend-btn .desc {
    color: #888;
    font-size: 10px;
  }

  .calibration-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .badge {
    display: inline-block;
    padding: 4px 12px;
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

  .calibrate-btn {
    background: #00d9ff;
    color: #000;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .calibrate-btn:active {
    transform: scale(0.95);
    background: #00b8d9;
  }
</style>
