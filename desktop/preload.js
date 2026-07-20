const { contextBridge, ipcRenderer } = require('electron');

// The bridge between the sandboxed renderer and Node/Electron APIs.
// Deliberately narrow: device config (needs safeStorage), the local
// SQLite mirror/outbox (needs Node's node:sqlite), and printer selection
// (getPrintersAsync()/print() with a specific deviceName are main-process-
// only) are the things the renderer can't do itself. Everything else
// (HTTP calls) uses standard web APIs already available to the renderer.
contextBridge.exposeInMainWorld('deviceConfig', {
  get: () => ipcRenderer.invoke('device-config:get'),
  set: (config) => ipcRenderer.invoke('device-config:set', config),
  clear: () => ipcRenderer.invoke('device-config:clear'),
});

contextBridge.exposeInMainWorld('printerApi', {
  list: () => ipcRenderer.invoke('printer:list'),
  print: (options) => ipcRenderer.invoke('printer:print', options),
});

contextBridge.exposeInMainWorld('localDb', {
  upsertBooks: (books) => ipcRenderer.invoke('db:upsertBooks', books),
  searchLocalBooks: (query) => ipcRenderer.invoke('db:searchLocalBooks', query),
  lookupLocalBook: (code) => ipcRenderer.invoke('db:lookupLocalBook', code),
  adjustLocalStock: (bookId, delta) => ipcRenderer.invoke('db:adjustLocalStock', bookId, delta),
  getSyncMeta: (key) => ipcRenderer.invoke('db:getSyncMeta', key),
  setSyncMeta: (key, value) => ipcRenderer.invoke('db:setSyncMeta', key, value),
  addToOutbox: (offlineUuid, payload) => ipcRenderer.invoke('db:addToOutbox', offlineUuid, payload),
  getPendingOutbox: () => ipcRenderer.invoke('db:getPendingOutbox'),
  getOutboxPendingCount: () => ipcRenderer.invoke('db:getOutboxPendingCount'),
  getTodayOutbox: () => ipcRenderer.invoke('db:getTodayOutbox'),
  getBooksByIds: (ids) => ipcRenderer.invoke('db:getBooksByIds', ids),
  markOutboxSynced: (offlineUuid, serverResponse) => ipcRenderer.invoke('db:markOutboxSynced', offlineUuid, serverResponse),
  markOutboxFailed: (offlineUuid, errorMessage) => ipcRenderer.invoke('db:markOutboxFailed', offlineUuid, errorMessage),
});
