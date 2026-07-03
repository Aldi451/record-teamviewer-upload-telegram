import os
import shutil
import subprocess
import hashlib
import sqlite3
import time
import requests
import logging
import argparse

# --- KONFIGURASI ---
SOURCE_DIR = r"D:\PowerPro\Record"
ARCHIVE_DIR = r"D:\PowerPro\Record\Zip\ARCHIVE"
SEVEN_ZIP = r"D:\PowerPro\AutoBackupRestore_OK\7-Zip\7z.exe"
DB_FILE = "file_status.db"
LOG_FILE = "automation.log"
BOT_TOKEN = "8027739654:AAErfj0mBCFGjuGC7eSN4rCSP1jiHSS6VFo"
CHAT_ID = "6888495331"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Logging ke file + console dengan UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS uploads (file_hash TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def is_uploaded(file_hash):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT 1 FROM uploads WHERE file_hash = ?", (file_hash,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def mark_as_uploaded(file_hash):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO uploads (file_hash) VALUES (?)", (file_hash,))
    conn.commit()
    conn.close()

def get_file_hash(filepath):
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def is_file_locked(filepath):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'a'):
                pass
        return False
    except (OSError, IOError):
        return True

def test_zip_integrity(zip_base):
    try:
        cmd = [SEVEN_ZIP, "t", zip_base]
        res = subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return res.returncode == 0
    except Exception:
        return False

def upload_to_telegram(filepath, retries=3, delay=5):
    filename = os.path.basename(filepath)
    if DRY_RUN:
        logging.info(f"[DRY‑RUN] Would upload {filename} to Telegram")
        return True
    for attempt in range(1, retries + 1):
        try:
            with open(filepath, "rb") as f:
                response = requests.post(
                    f"{BASE_URL}/sendDocument",
                    data={"chat_id": CHAT_ID, "caption": f"Archive: {filename}"},
                    files={"document": f},
                    timeout=600,
                    verify=False   # bypass SSL check
                )
                if response.status_code == 200:
                    logging.info(f"✅ Upload sukses: {filename}")
                    return True
                else:
                    logging.error(f"Upload gagal {filename} (HTTP {response.status_code}) - {response.text}")
        except Exception as e:
            logging.error(f"Error upload {filename}: {e}")
        if attempt < retries:
            time.sleep(delay * attempt)
    return False

def send_message(text):
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text},
            timeout=30,
            verify=False
        )
        if response.status_code == 200:
            logging.info(f"📢 Notifikasi terkirim: {text}")
        else:
            logging.error(f"Gagal kirim notifikasi: {response.text}")
    except Exception as e:
        logging.error(f"Error kirim notifikasi: {e}")

def get_folder_size(folder_path):
    total_size = 0
    for f in os.listdir(folder_path):
        fp = os.path.join(folder_path, f)
        if os.path.isfile(fp):
            total_size += os.path.getsize(fp)
    return total_size

def process_existing_zips():
    current_month = time.strftime("%m-%Y")
    for file_name in os.listdir(ARCHIVE_DIR):
        # cek file zip normal atau part zip
        if not (file_name.endswith(".zip") or ".zip." in file_name):
            continue
        if file_name.startswith(current_month):  # skip bulan berjalan
            continue

        zip_path = os.path.join(ARCHIVE_DIR, file_name)
        if os.path.isdir(zip_path):
            continue

        file_hash = get_file_hash(zip_path)

        if not is_uploaded(file_hash):
            logging.info(f"Found archive {file_name}, uploading...")
            if upload_to_telegram(zip_path):
                mark_as_uploaded(file_hash)
                logging.info(f"✅ Uploaded archive: {file_name}")
                send_message(f"✅ Upload sukses: {file_name}")
                try:
                    os.remove(zip_path)
                    logging.info(f"🗑️ Deleted archive after upload: {file_name}")
                except Exception as e:
                    logging.error(f"Failed to delete archive {file_name}: {e}")
            else:
                logging.error(f"❌ Failed to upload archive: {file_name}")
                send_message(f"❌ Upload gagal: {file_name}")
        else:
            logging.info(f"Skipping already uploaded archive: {file_name}")

def run_automation():
    logging.info("Starting automation cycle...")
    os.makedirs(SOURCE_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    # 1. Group .tvs files by mm-yyyy
    for file_name in os.listdir(SOURCE_DIR):
        if not file_name.lower().endswith(".tvs"):
            continue
        file_path = os.path.join(SOURCE_DIR, file_name)
        if is_file_locked(file_path):
            continue
        try:
            date_str = time.strftime("%m-%Y", time.localtime(os.path.getctime(file_path)))
            target_dir = os.path.join(ARCHIVE_DIR, date_str)
            os.makedirs(target_dir, exist_ok=True)
            shutil.move(file_path, os.path.join(target_dir, file_name))
            logging.info(f"Moved {file_name} to {target_dir}")
        except Exception as e:
            logging.error(f"Error grouping file {file_name}: {e}")

    # 2. Process each month folder (skip current month)
    current_month = time.strftime("%m-%Y")
    for folder_name in os.listdir(ARCHIVE_DIR):
        if folder_name == current_month:
            logging.info(f"Skipping current month folder: {folder_name}")
            continue

        folder_path = os.path.join(ARCHIVE_DIR, folder_name)
        if not os.path.isdir(folder_path):
            continue

        source_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        if not source_files:
            continue

        active_files = [f for f in source_files if not is_file_locked(f)]
        if not active_files:
            continue

        new_files = [f for f in active_files if not is_uploaded(get_file_hash(f))]
        if not new_files:
            logging.info(f"No new files for {folder_name}, skipping compression")
            continue

        zip_base = os.path.join(ARCHIVE_DIR, f"{folder_name}.zip")
        folder_size = get_folder_size(folder_path)

        try:
            if folder_size > 2 * 1024 * 1024 * 1024:
                cmd = [SEVEN_ZIP, "a", "-tzip", "-mx=1", "-v2000m", zip_base] + new_files
                logging.info(f"Compressing {folder_name} with split (>2GB)")
            else:
                cmd = [SEVEN_ZIP, "a", "-tzip", "-mx=1", zip_base] + new_files
                logging.info(f"Compressing {folder_name} without split (≤2GB)")

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

            if test_zip_integrity(zip_base):
                for fpath in new_files:
                    os.remove(fpath)
                    logging.info(f"Removed source file: {os.path.basename(fpath)}")

                file_hash = get_file_hash(zip_base)
                if not is_uploaded(file_hash):
                    if upload_to_telegram(zip_base):
                        mark_as_uploaded(file_hash)
                        logging.info(f"✅ Uploaded archive: {folder_name}.zip")
                        send_message(f"✅ Upload sukses: {folder_name}")
                        try:
                            os.remove(zip_base)
                            logging.info(f"🗑️ Deleted archive after upload: {folder_name}.zip")
                        except Exception as e:
                            logging.error(f"Failed to delete archive {folder_name}.zip: {e}")
                    else:
                        logging.error(f"❌ Failed to upload archive: {folder_name}.zip")
            else:
                logging.error(f"Integrity check failed for {zip_base}")
        except Exception as e:
            logging.error(f"Compression failed for {folder_name}: {e}")
            continue

    # 3. Process zip lama yang sudah ada
    process_existing_zips()

    # Setelah semua selesai, tampilkan pesan akhir
    logging.info("=== Program selesai ===")
    print("Program selesai. Semua proses sudah dijalankan.")


if __name__ == "__main__":
    init_db()
    parser = argparse.ArgumentParser(description="Run Telegram upload automation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate run without uploading")
    args = parser.parse_args()
    
    DRY_RUN = args.dry_run
    run_automation()
