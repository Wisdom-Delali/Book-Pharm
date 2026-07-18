const { contextBridge, ipcRenderer } = require('electron');

// The only bridge between the sandboxed renderer and Node/Electron APIs.
// Deliberately narrow: device config (apiBaseUrl + token) is the one thing
// that needs OS-keychain-backed storage (safeStorage), so it's the one
// thing exposed. Everything else (HTTP calls, printing) uses standard web
// APIs already available to the renderer.
contextBridge.exposeInMainWorld('deviceConfig', {
  get: () => ipcRenderer.invoke('device-config:get'),
  set: (config) => ipcRenderer.invoke('device-config:set', config),
  clear: () => ipcRenderer.invoke('device-config:clear'),
});
