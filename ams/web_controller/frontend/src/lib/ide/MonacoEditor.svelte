<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';

  export let value = '';
  export let language = 'yaml';
  export let theme = 'vs-dark';

  const dispatch = createEventDispatcher();

  let container;
  let editor;
  let monaco;

  onMount(async () => {
    // Dynamically import Monaco
    monaco = await import('monaco-editor');

    // Configure YAML defaults
    if (language === 'yaml') {
      // Monaco doesn't have native YAML schema support,
      // but we can add it via monaco-yaml package later
    }

    editor = monaco.editor.create(container, {
      value,
      language,
      theme,
      automaticLayout: true,
      minimap: { enabled: false },
      fontSize: 14,
      lineNumbers: 'on',
      scrollBeyondLastLine: false,
      wordWrap: 'on',
      tabSize: 2,
      insertSpaces: true,
      renderWhitespace: 'selection',
      bracketPairColorization: { enabled: true },
      padding: { top: 10 },
    });

    // Listen for changes
    editor.onDidChangeModelContent(() => {
      const newValue = editor.getValue();
      dispatch('change', { value: newValue });
    });
  });

  onDestroy(() => {
    if (editor) {
      editor.dispose();
    }
  });

  // Update editor when value prop changes externally
  $: if (editor && value !== editor.getValue()) {
    const position = editor.getPosition();
    editor.setValue(value);
    if (position) {
      editor.setPosition(position);
    }
  }

  // Update language when it changes
  $: if (editor && monaco) {
    const model = editor.getModel();
    if (model) {
      monaco.editor.setModelLanguage(model, language);
    }
  }
</script>

<div class="editor-wrapper" bind:this={container}></div>

<style>
  .editor-wrapper {
    width: 100%;
    height: 100%;
  }
</style>
