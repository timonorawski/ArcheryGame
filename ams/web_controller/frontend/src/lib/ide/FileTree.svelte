<script>
  import { createEventDispatcher } from 'svelte';

  export let files = [];

  const dispatch = createEventDispatcher();

  let expandedFolders = new Set(['levels/', 'lua/', 'lua/behaviors/']);

  function toggleFolder(path) {
    if (expandedFolders.has(path)) {
      expandedFolders.delete(path);
    } else {
      expandedFolders.add(path);
    }
    expandedFolders = expandedFolders; // trigger reactivity
  }

  function selectFile(path) {
    dispatch('select', { path });
  }

  function getIcon(file) {
    if (file.type === 'folder') {
      return expandedFolders.has(file.name) ? '📂' : '📁';
    }
    if (file.name.endsWith('.yaml') || file.name.endsWith('.yml')) {
      return '📄';
    }
    if (file.name.endsWith('.lua')) {
      return '🌙';
    }
    return '📄';
  }
</script>

<div class="file-tree">
  <div class="tree-header">Explorer</div>
  <div class="tree-content">
    {#each files as file}
      <div class="tree-item">
        {#if file.type === 'folder'}
          <button
            class="folder-btn"
            on:click={() => toggleFolder(file.name)}
          >
            <span class="icon">{getIcon(file)}</span>
            <span class="name">{file.name}</span>
          </button>
          {#if expandedFolders.has(file.name) && file.children}
            <div class="children">
              {#each file.children as child}
                {#if child.type === 'folder'}
                  <button
                    class="folder-btn"
                    on:click={() => toggleFolder(child.name)}
                  >
                    <span class="icon">{getIcon(child)}</span>
                    <span class="name">{child.name}</span>
                  </button>
                {:else}
                  <button
                    class="file-btn"
                    on:click={() => selectFile(`${file.name}${child.name}`)}
                  >
                    <span class="icon">{getIcon(child)}</span>
                    <span class="name">{child.name}</span>
                  </button>
                {/if}
              {/each}
            </div>
          {/if}
        {:else}
          <button
            class="file-btn"
            on:click={() => selectFile(file.name)}
          >
            <span class="icon">{getIcon(file)}</span>
            <span class="name">{file.name}</span>
          </button>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  .file-tree {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .tree-header {
    padding: 0.5rem;
    font-size: 0.75rem;
    text-transform: uppercase;
    color: #6d6d6d;
    font-weight: 600;
  }

  .tree-content {
    flex: 1;
    overflow-y: auto;
    padding: 0 0.25rem;
  }

  .tree-item {
    user-select: none;
  }

  .folder-btn, .file-btn {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    width: 100%;
    padding: 0.25rem 0.5rem;
    border: none;
    background: transparent;
    color: #cccccc;
    font-size: 0.8125rem;
    text-align: left;
    cursor: pointer;
    border-radius: 3px;
  }

  .folder-btn:hover, .file-btn:hover {
    background: #2a2d2e;
  }

  .icon {
    font-size: 0.875rem;
    width: 1rem;
    text-align: center;
  }

  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .children {
    padding-left: 1rem;
  }
</style>
