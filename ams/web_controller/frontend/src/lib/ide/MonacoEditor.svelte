<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { configureMonacoYaml } from 'monaco-yaml';

  export let value = '';
  export let language = 'yaml';
  export let theme = 'vs-dark';
  export let readOnly = false;
  export let filePath = '';  // Used for schema matching
  export let filetypes = []; // File type registry with schemas

  const dispatch = createEventDispatcher();

  let container;
  let editor;
  let monaco;
  let yamlWorker = null;

  onMount(async () => {
    // Configure MonacoEnvironment for worker loading before importing Monaco
    // This is required for monaco-yaml and other plugins that use web workers
    if (!self.MonacoEnvironment) {
      self.MonacoEnvironment = {
        getWorker: function (workerId, label) {
          // Use dynamic imports for workers - Vite will handle bundling
          if (label === 'yaml') {
            return new Worker(
              new URL('monaco-yaml/yaml.worker.js', import.meta.url),
              { type: 'module' }
            );
          }
          if (label === 'json') {
            return new Worker(
              new URL('monaco-editor/esm/vs/language/json/json.worker.js', import.meta.url),
              { type: 'module' }
            );
          }
          if (label === 'css' || label === 'scss' || label === 'less') {
            return new Worker(
              new URL('monaco-editor/esm/vs/language/css/css.worker.js', import.meta.url),
              { type: 'module' }
            );
          }
          if (label === 'html' || label === 'handlebars' || label === 'razor') {
            return new Worker(
              new URL('monaco-editor/esm/vs/language/html/html.worker.js', import.meta.url),
              { type: 'module' }
            );
          }
          if (label === 'typescript' || label === 'javascript') {
            return new Worker(
              new URL('monaco-editor/esm/vs/language/typescript/ts.worker.js', import.meta.url),
              { type: 'module' }
            );
          }
          // Default editor worker
          return new Worker(
            new URL('monaco-editor/esm/vs/editor/editor.worker.js', import.meta.url),
            { type: 'module' }
          );
        }
      };
    }

    // Dynamically import Monaco
    monaco = await import('monaco-editor');

    // Configure YAML with schema validation from filetypes registry
    if (language === 'yaml') {
      // Get base URL for schema resolution (needed for $ref in schemas)
      const baseUrl = window.location.origin;

      // Build schema config from filetypes
      const schemas = filetypes
        .filter(ft => ft.schema && ft.fileMatch)
        .map(ft => ({
          // Make schema URIs absolute for proper $ref resolution
          uri: ft.schema.startsWith('http') ? ft.schema : `${baseUrl}${ft.schema}`,
          fileMatch: ft.fileMatch
        }));

      yamlWorker = configureMonacoYaml(monaco, {
        enableSchemaRequest: true,
        hover: true,
        completion: true,
        validate: true,
        format: true,
        schemas: schemas.length > 0 ? schemas : [
          // Fallback if filetypes not loaded yet - use absolute URLs
          { uri: `${baseUrl}/api/schemas/game.schema.json`, fileMatch: ['**/game.yaml'] },
          { uri: `${baseUrl}/api/schemas/level.schema.json`, fileMatch: ['**/levels/*.yaml'] },
          { uri: `${baseUrl}/api/schemas/lua_script.schema.json`, fileMatch: ['**/*.lua.yaml'] }
        ]
      });
    }

    // Create model with URI for schema matching
    const modelUri = monaco.Uri.parse(`file:///${filePath || 'untitled.yaml'}`);
    let model = monaco.editor.getModel(modelUri);
    if (!model) {
      model = monaco.editor.createModel(value, language, modelUri);
    } else {
      model.setValue(value);
    }

    editor = monaco.editor.create(container, {
      model,
      theme,
      readOnly,
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
    if (yamlWorker) {
      yamlWorker.dispose();
    }
  });

  // Update editor when value prop changes externally
  $: if (editor && value !== editor.getValue()) {
    const position = editor.getPosition();
    editor.getModel()?.setValue(value);
    if (position) {
      editor.setPosition(position);
    }
  }

  // Update model when filePath changes (for schema matching)
  $: if (editor && monaco && filePath) {
    const newUri = monaco.Uri.parse(`file:///${filePath}`);
    const currentModel = editor.getModel();
    if (currentModel && currentModel.uri.toString() !== newUri.toString()) {
      let newModel = monaco.editor.getModel(newUri);
      if (!newModel) {
        newModel = monaco.editor.createModel(value, language, newUri);
      } else {
        newModel.setValue(value);
      }
      editor.setModel(newModel);
    }
  }

  // Update language when it changes
  $: if (editor && monaco) {
    const model = editor.getModel();
    if (model) {
      monaco.editor.setModelLanguage(model, language);
    }
  }

  // Update readOnly when it changes
  $: if (editor) {
    editor.updateOptions({ readOnly });
  }
</script>

<div class="editor-wrapper" bind:this={container}></div>

<style>
  .editor-wrapper {
    width: 100%;
    height: 100%;
  }
</style>
