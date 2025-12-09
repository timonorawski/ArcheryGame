<script>
  export let currentPacing = 'throwing';
  export let onSelect = () => {};

  const pacings = [
    { id: 'archery', label: 'Archery', icon: '🏹', desc: 'Slow (3-8s)' },
    { id: 'throwing', label: 'Throwing', icon: '🎯', desc: 'Medium (1-2s)' },
    { id: 'blaster', label: 'Blaster', icon: '⚡', desc: 'Fast (0.3-0.5s)' },
  ];

  function selectPacing(id) {
    if (id !== currentPacing) {
      onSelect(id);
    }
  }
</script>

<div class="card">
  <h2>Pacing</h2>

  <div class="pacings">
    {#each pacings as pacing}
      <button
        class="pacing-btn"
        class:selected={currentPacing === pacing.id}
        on:click={() => selectPacing(pacing.id)}
      >
        <span class="icon">{pacing.icon}</span>
        <span class="label">{pacing.label}</span>
        <span class="desc">{pacing.desc}</span>
      </button>
    {/each}
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

  .pacings {
    display: flex;
    gap: 8px;
  }

  .pacing-btn {
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

  .pacing-btn:active {
    transform: scale(0.95);
  }

  .pacing-btn.selected {
    border-color: #ff9800;
    background: rgba(255, 152, 0, 0.1);
  }

  .pacing-btn .icon {
    font-size: 24px;
  }

  .pacing-btn .label {
    color: #fff;
    font-weight: 600;
    font-size: 14px;
  }

  .pacing-btn .desc {
    color: #888;
    font-size: 10px;
  }
</style>
