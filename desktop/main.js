const { app, BrowserWindow, ipcMain, safeStorage } = require('electron');
const fs = require('fs');
const path = require('path');

const CONFIG_PATH = () => path.join(app.getPath('userData'), 'device-config.enc');

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

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
