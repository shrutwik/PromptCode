try {
  const [
    {EditorView, basicSetup},
    {EditorState},
    {python: pythonLang},
    {javascript: jsLang},
    {java: javaLang},
    {cpp: cppLang},
    {rust: rustLang},
    {oneDark},
    {keymap},
    {indentWithTab},
  ] = await Promise.all([
    import('https://esm.sh/codemirror@6.0.1?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/state@6.7.6'),
    import('https://esm.sh/@codemirror/lang-python@6.1.6?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/lang-javascript@6.2.2?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/lang-java@6.0.1?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/lang-cpp@6.0.2?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/lang-rust@6.0.2?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/theme-one-dark@6.1.2?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
    import('https://esm.sh/@codemirror/view@6.43.13?deps=@codemirror/state@6.7.6'),
    import('https://esm.sh/@codemirror/commands@6.8.0?deps=@codemirror/state@6.7.6,@codemirror/view@6.43.13'),
  ]);

  window._CM = {
    langExtensions: {
      python: () => pythonLang(),
      javascript: () => jsLang(),
      typescript: () => jsLang({typescript: true}),
      java: () => javaLang(),
      cpp: () => cppLang(),
      c: () => cppLang(),
      rust: () => rustLang(),
      go: () => jsLang(),
    },
    customTheme: EditorView.theme({
      '&': { height: '100%', fontSize: '13px', fontFamily: 'var(--pc-font-mono)', backgroundColor: 'var(--pc-bg)' },
      '.cm-content': { caretColor: 'var(--pc-accent)', padding: '16px 16px 16px 8px', lineHeight: '1.7', fontFamily: 'var(--pc-font-mono)' },
      '.cm-gutters': { backgroundColor: 'var(--pc-bg)', borderRight: '1px solid var(--pc-border)', color: 'var(--pc-faint)', minWidth: '44px', fontFamily: 'var(--pc-font-mono)', fontSize: '11px' },
      '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--pc-text-secondary)' },
      '.cm-activeLine': { backgroundColor: 'rgba(17,17,15,0.04)' },
      '.cm-cursor': { borderLeftColor: 'var(--pc-accent)' },
      '.cm-selectionBackground': { backgroundColor: 'rgba(17,17,15,0.12) !important' },
      '&.cm-focused .cm-selectionBackground': { backgroundColor: 'rgba(17,17,15,0.16) !important' },
      '&.cm-focused': { outline: 'none' },
      '.cm-scroller': { overflow: 'auto', fontFamily: 'var(--pc-font-mono)' },
    }),
    EditorView, EditorState, basicSetup, oneDark, keymap, indentWithTab,
  };
} catch (e) {
  console.warn('CodeMirror failed to load, using textarea fallback:', e);
  window._cmFailed = true;
}

if (typeof window._cmReadyCallback === 'function') {
  window._cmReadyCallback();
} else {
  window._cmReady = true;
}
