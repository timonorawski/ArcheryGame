<script>
  import { onMount } from 'svelte';

  // Components (to be created)
  import MonacoEditor from './lib/ide/MonacoEditor.svelte';
  import FileTree from './lib/ide/FileTree.svelte';
  import PreviewFrame from './lib/ide/PreviewFrame.svelte';

  // Project files as YAML strings (keyed by path)
  let projectFiles = {
    'game.yaml': `# My Game
name: My First Game
description: A simple game created in the AMS editor

screen_width: 800
screen_height: 600
background_color: [30, 30, 46]

entity_types:
  target:
    width: 50
    height: 50
    color: red
    health: 1
    points: 10
    tags: [target]

default_layout:
  entities:
    - type: target
      x: 400
      y: 300
`
  };

  let currentFile = 'game.yaml';

  // Reactive getter for current file content
  $: editorContent = projectFiles[currentFile] || '';
  let files = [
    { name: 'game.yaml', type: 'yaml' },
    { name: 'levels/', type: 'folder', children: [
      { name: 'level1.yaml', type: 'yaml' }
    ]},
    { name: 'lua/', type: 'folder', children: [
      { name: 'behaviors/', type: 'folder', children: [] }
    ]}
  ];

  let splitPosition = 50; // percentage
  let isDragging = false;

  function handleEditorChange(event) {
    // Update projectFiles with new content for current file
    projectFiles[currentFile] = event.detail.value;
    projectFiles = projectFiles; // Trigger reactivity
  }

  function handleFileSelect(event) {
    currentFile = event.detail.path;
    // TODO: Load file content
  }

  function handleDragStart(e) {
    isDragging = true;
    document.addEventListener('mousemove', handleDrag);
    document.addEventListener('mouseup', handleDragEnd);
  }

  function handleDrag(e) {
    if (!isDragging) return;
    const container = document.querySelector('.editor-container');
    const rect = container.getBoundingClientRect();
    const x = e.clientX - rect.left;
    splitPosition = Math.min(80, Math.max(20, (x / rect.width) * 100));
  }

  function handleDragEnd() {
    isDragging = false;
    document.removeEventListener('mousemove', handleDrag);
    document.removeEventListener('mouseup', handleDragEnd);
  }
</script>

<div class="ide-container">
  <header class="toolbar">
    <div class="logo">AMS Editor</div>
    <div class="file-info">{currentFile}</div>
    <div class="actions">
      <button class="btn" on:click={() => console.log('Run')}>Run</button>
      <button class="btn btn-primary" on:click={() => console.log('Save')}>Save</button>
    </div>
  </header>

  <div class="main-content">
    <aside class="sidebar">
      <FileTree {files} on:select={handleFileSelect} />
    </aside>

    <div class="editor-container">
      <div class="editor-pane" style="width: {splitPosition}%">
        <MonacoEditor
          value={editorContent}
          language="yaml"
          on:change={handleEditorChange}
        />
      </div>

      <div
        class="divider"
        class:dragging={isDragging}
        on:mousedown={handleDragStart}
        role="separator"
        aria-orientation="vertical"
        tabindex="0"
      ></div>

      <div class="preview-pane" style="width: {100 - splitPosition}%">
        <PreviewFrame {projectFiles} />
      </div>
    </div>
  </div>

  <footer class="statusbar">
    <span class="status-item">Ready</span>
    <span class="status-item">YAML</span>
    <span class="status-item">UTF-8</span>
  </footer>
</div>

<style>
  .ide-container {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: #1e1e1e;
  }

  .toolbar {
    display: flex;
    align-items: center;
    padding: 0.5rem 1rem;
    background: #2d2d2d;
    border-bottom: 1px solid #3d3d3d;
    gap: 1rem;
  }

  .logo {
    font-weight: 600;
    color: #4ec9b0;
  }

  .file-info {
    flex: 1;
    color: #9d9d9d;
    font-size: 0.875rem;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
  }

  .btn {
    padding: 0.375rem 0.75rem;
    border: 1px solid #3d3d3d;
    background: #2d2d2d;
    color: #d4d4d4;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.875rem;
  }

  .btn:hover {
    background: #3d3d3d;
  }

  .btn-primary {
    background: #0e639c;
    border-color: #0e639c;
  }

  .btn-primary:hover {
    background: #1177bb;
  }

  .main-content {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .sidebar {
    width: 200px;
    background: #252526;
    border-right: 1px solid #3d3d3d;
    overflow-y: auto;
  }

  .editor-container {
    flex: 1;
    display: flex;
    overflow: hidden;
  }

  .editor-pane, .preview-pane {
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .divider {
    width: 4px;
    background: #3d3d3d;
    cursor: col-resize;
    transition: background 0.2s;
  }

  .divider:hover, .divider.dragging {
    background: #0e639c;
  }

  .statusbar {
    display: flex;
    padding: 0.25rem 1rem;
    background: #007acc;
    color: white;
    font-size: 0.75rem;
    gap: 1rem;
  }

  .status-item {
    opacity: 0.9;
  }
</style>
