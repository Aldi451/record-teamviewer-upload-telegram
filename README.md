# PowerPro Telegram Uploader

Script ini sudah diubah supaya bisa dibuat menjadi file .exe Windows dan dijalankan sebagai layanan Windows (service.msc) tanpa muncul prompt.

## Cara build menjadi .exe

1. Install dependencies:
   ```powershell
   py -m pip install -r requirements.txt
   ```

2. Build exe:
   ```powershell
   pyinstaller --noconsole --onefile --name powerpro_uploader_service service_runner.py --hidden-import pyrogram
   ```

3. Hasil build ada di folder `dist`.

## Cara install ke service.msc

Buka Command Prompt sebagai Administrator lalu jalankan:

```powershell
sc.exe create "PowerProTelegramUploader" binPath= "C:\path\ke\dist\powerpro_uploader_service.exe" start= auto
sc.exe start "PowerProTelegramUploader"
```

Setelah itu akan muncul di `services.msc`.

## Environment variables yang harus diisi

Sebelum service dijalankan, isi variabel environment berikut di Windows:

```powershell
setx TG_API_ID "39182435"
setx TG_API_HASH "your_api_hash"
setx TG_BOT_TOKEN "your_bot_token"
setx TG_CHAT_ID "your_chat_id"
setx POWERPRO_SOURCE_DIR "D:\PowerPro\Record"
setx POWERPRO_ARCHIVE_DIR "D:\PowerPro\Record\Zip\ARCHIVE"
setx POWERPRO_SEVEN_ZIP "D:\PowerPro\AutoBackupRestore_OK\7-Zip\7z.exe"
```

Catatan:
- `--noconsole` membuat exe tidak menampilkan prompt/console.
- Untuk service Windows, gunakan `service_runner.py` supaya bisa masuk ke `services.msc`.
- `--onefile` membuat file lebih ringkas dan tidak terlalu berat dibanding bundled folder.
