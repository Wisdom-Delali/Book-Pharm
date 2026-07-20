const { app, BrowserWindow, ipcMain, safeStorage } = require('electron');
const fs = require('fs');
const path = require('path');
const db = require('./db');

const CONFIG_PATH = () => path.join(app.getPath('userData'), 'device-config.enc');
const userDataPath = () => app.getPath('userData');

function readConfig() {
  try {
    const encrypted = fs.readFileSync(CONFIG_PATH());
    if (!safeStorage.isEncryptionAvailable()) return null;
    const json = safeStorage.decryptString(encrypted);
    return JSON.parse(json);
  } catch (err) {
    return null;
  }
}

function writeConfig(config) {
  if (!safeStorage.isEncryptionAvailable()) {
    throw new Error('OS-level credential encryption is not available on this machine.');
  }
  const encrypted = safeStorage.encryptString(JSON.stringify(config));
  fs.writeFileSync(CONFIG_PATH(), encrypted);
}

function clearConfig() {
  try {
    fs.unlinkSync(CONFIG_PATH());
  } catch (err) {
    // nothing to clear
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 1024,
    minHeight: 700,
    title: 'Book Pharm POS',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

ipcMain.handle('device-config:get', () => readConfig());
ipcMain.handle('device-config:set', (_event, config) => {
  writeConfig(config);
  return true;
});
ipcMain.handle('device-config:clear', () => {
  clearConfig();
  return true;
});

// ---------- Local SQLite mirror + outbox (CLAUDE.md §7) ----------
// The renderer is sandboxed with no Node access, so every SQLite operation
// is a thin IPC round-trip into db.js here.

ipcMain.handle('db:upsertBooks', (_event, books) => db.upsertBooks(userDataPath(), books));
ipcMain.handle('db:searchLocalBooks', (_event, query) => db.searchLocalBooks(userDataPath(), query));
ipcMain.handle('db:lookupLocalBook', (_event, code) => db.lookupLocalBook(userDataPath(), code));
ipcMain.handle('db:adjustLocalStock', (_event, bookId, delta) => db.adjustLocalStock(userDataPath(), bookId, delta));
ipcMain.handle('db:getSyncMeta', (_event, key) => db.getSyncMeta(userDataPath(), key));
ipcMain.handle('db:setSyncMeta', (_event, key, value) => db.setSyncMeta(userDataPath(), key, value));
ipcMain.handle('db:addToOutbox', (_event, offlineUuid, payload) => db.addToOutbox(userDataPath(), offlineUuid, payload));
ipcMain.handle('db:getPendingOutbox', () => db.getPendingOutbox(userDataPath()));
ipcMain.handle('db:getOutboxPendingCount', () => db.getOutboxPendingCount(userDataPath()));
ipcMain.handle('db:getTodayOutbox', () => db.getTodayOutbox(userDataPath()));
ipcMain.handle('db:getBooksByIds', (_event, ids) => db.getBooksByIds(userDataPath(), ids));
ipcMain.handle('db:markOutboxSynced', (_event, offlineUuid, serverResponse) => db.markOutboxSynced(userDataPath(), offlineUuid, serverResponse));
ipcMain.handle('db:markOutboxFailed', (_event, offlineUuid, errorMessage) => db.markOutboxFailed(userDataPath(), offlineUuid, errorMessage));

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
