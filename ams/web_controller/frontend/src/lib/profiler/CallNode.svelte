<script>
  import { createEventDispatcher } from 'svelte';

  export let call;
  export let totalDuration;
  export let depth = 0;
  export let selectedId = null;

  const dispatch = createEventDispatcher();

  function formatDuration(ms) {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
    if (ms < 1000) return `${ms.toFixed(2)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  }

  function getCallColor(call) {
    if (call.lua_callback) return 'bg-purple-600';
    if (call.lua_code) return 'bg-blue-600';
    if (call.module === 'game_engine') return 'bg-green-600';
    if (call.module === 'lua_api') return 'bg-yellow-600';
    if (call.module === 'lua_engine') return 'bg-cyan-600';
    return 'bg-gray-600';
  }

  function handleClick() {
    dispatch('select', call);
  }

  function handleChildSelect(event) {
    dispatch('select', event.detail);
  }

  $: widthPercent = Math.max((call.duration / totalDuration) * 100, 8);
  $: isSelected = selectedId === call.id;
</script>

<div class="call-node" style="margin-left: {depth * 16}px">
  <button
    class="flex items-center gap-2 px-2 py-1 rounded text-sm text-white cursor-pointer hover:opacity-90 text-left {getCallColor(call)}"
    class:ring-2={isSelected}
    class:ring-white={isSelected}
    style="width: {widthPercent}%"
    on:click={handleClick}
  >
    <span class="truncate flex-1 font-mono text-xs">{call.label}</span>
    <span class="text-xs opacity-75 shrink-0">{formatDuration(call.duration)}</span>
  </button>

  {#if call.children && call.children.length > 0}
    <div class="mt-0.5 space-y-0.5">
      {#each call.children as child}
        <svelte:self call={child} {totalDuration} depth={depth + 1} {selectedId} on:select={handleChildSelect} />
      {/each}
    </div>
  {/if}
</div>

<style>
  .call-node {
    min-width: 100px;
  }
</style>
