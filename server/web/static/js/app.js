async function init() {
  wireEvents();
  await loadConfig();
  initWebSocket();
}

init();

