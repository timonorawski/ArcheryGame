<script>
  export let connected = false;
</script>

<div class="status" class:connected class:disconnected={!connected}>
  {connected ? 'Connected' : 'Disconnected'}
</div>

<style>
  .status {
    display: inline-block;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .connected {
    background: #00c853;
    color: #000;
  }

  .disconnected {
    background: #ff5252;
    color: #fff;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
</style>
