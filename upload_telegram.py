import os
import shutil
import subprocess
import hashlib
import sqlite3
import time
import logging
import argparse
import glob
from pyrogram import Client

# --- KONFIGURASI ---
SOURCE_DIR = r"D:\PowerPro\Record"
ARCHIVE_DIR = r"D:\PowerPro\Record\Zip\ARCHIVE"
SEVEN_ZIP = r"D:\PowerPro\AutoBackupRestore_OK\7-Zip\7z.exe"
DB_FILE = "file_status.db"
LOG_FILE = "automation.log"

# --- TELEGRAM CONFIG (Diisi dari my.telegram.org & @BotFather) ---
API_ID = 39182435                   
API_HASH = "239d53bcbbbdc55decc56ca84ac37dea"    
BOT_TOKEN = "8027739654:AAFBOBtOv89c41AtX0qXgOP204J3Odw_JBQ"  
CHAT_ID = "6888495331"             

DRY_RUN = False  # Flag global default

# Logging ke file + console dengan UTF-8
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# [REVISI]: Membungkam spam log internal (Disconnect/Connect) dari Pyrogram
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# Inisialisasi Pyrogram Client
app = Client("powerpro_uploader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


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


# [REVISI]: Variabel global dan modifikasi fungsi progress_callback 
# untuk mencegah layar kedap-kedip dan bottleneck terminal
last_print_time = 0

def progress_callback(current, total, filename):
    global last_print_time
    current_time = time.time()
    
    # Hanya update teks terminal setiap 2 detik atau jika sudah 100%
    if (current_time - last_print_time) > 2 or current == total:
        percent = (current / total) * 100
        current_mb = current / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        print(f"Uploading {filename}: {percent:.1f}% ({current_mb:.1f}/{total_mb:.1f} MB)   ", end="\r")
        last_print_time = current_time


def upload_to_telegram(filepath, retries=3, delay=5):
    filename = os.path.basename(filepath)
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would upload {filename} to Telegram")
        return True

    for attempt in range(1, retries + 1):
        try:
            logging.info(f"Mengirim {filename} ke Telegram via Pyrogram (Max 2GB)...")
            app.send_document(
                chat_id=int(CHAT_ID) if CHAT_ID.lstrip('-').isdigit() else CHAT_ID,
                document=filepath,
                caption=f"Archive: {filename}",
                progress=lambda current, total: progress_callback(current, total, filename)
            )
            print()  # Newline setelah progress bar selesai
            logging.info(f"✅ Upload sukses: {filename}")
            return True
        except Exception as e:
            print()
            logging.error(f"Error upload {filename} (Percobaan {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(delay * attempt)

    return False


def send_message(text):
    if DRY_RUN:
        logging.info(f"[DRY-RUN] Would send notification: {text}")
        return
    try:
        app.send_message(
            chat_id=int(CHAT_ID) if CHAT_ID.lstrip('-').isdigit() else CHAT_ID,
            text=text
        )
        logging.info(f"📢 Notifikasi terkirim: {text}")
    except Exception as e:
        logging.error(f"Error kirim notifikasi: {e}")


def process_existing_zips():
    current_month = time.strftime("%m-%Y")
    for file_name in os.listdir(ARCHIVE_DIR):
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

        try:
            # [REVISI]: Menurunkan ukuran split zip dari -v1900m menjadi -v500m 
            # agar upload lebih stabil dan tidak rawan putus koneksi di tengah jalan
            cmd = [SEVEN_ZIP, "a", "-tzip", "-mx=1", "-v500m", zip_base] + new_files
            logging.info(f"Compressing {folder_name} (split @ 500MB max)...")

            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

            # Cari file zip / part zip hasil kompresi (.zip, .zip.001, dll)
            created_archives = sorted(glob.glob(os.path.join(ARCHIVE_DIR, f"{folder_name}.zip*")))

            # Verifikasi integritas kompresi
            if created_archives and test_zip_integrity(created_archives[0]):
                # Hapus file sumber .tvs jika kompresi sukses
                for fpath in new_files:
                    try:
                        os.remove(fpath)
                        logging.info(f"Removed source file: {os.path.basename(fpath)}")
                    except Exception as e:
                        logging.error(f"Failed to remove source file {fpath}: {e}")

                # Upload setiap part archive hasil kompresi
                for arch_file in created_archives:
                    file_hash = get_file_hash(arch_file)
                    arch_name = os.path.basename(arch_file)

                    if not is_uploaded(file_hash):
                        if upload_to_telegram(arch_file):
                            mark_as_uploaded(file_hash)
                            logging.info(f"✅ Uploaded archive: {arch_name}")
                            send_message(f"✅ Upload sukses: {arch_name}")
                            try:
                                os.remove(arch_file)
                                logging.info(f"🗑️ Deleted archive after upload: {arch_name}")
                            except Exception as e:
                                logging.error(f"Failed to delete archive {arch_name}: {e}")
                        else:
                            logging.error(f"❌ Failed to upload archive: {arch_name}")
                            send_message(f"❌ Upload gagal: {arch_name}")
            else:
                logging.error(f"Integrity check failed for archive {folder_name}")

        except Exception as e:
            logging.error(f"Compression failed for {folder_name}: {e}")
            continue

    # 3. Process zip lama yang sudah ada di folder ARCHIVE
    process_existing_zips()

    logging.info("=== Program selesai ===")
    print("Program selesai. Semua proses sudah dijalankan.")


if __name__ == "__main__":
    init_db()
    parser = argparse.ArgumentParser(description="Run Telegram upload automation")
    parser.add_argument("--dry-run", action="store_true", help="Simulate run without uploading")
    args = parser.parse_args()

    DRY_RUN = args.dry_run

    if DRY_RUN:
        run_automation()
    else:
        with app:
            run_automation()