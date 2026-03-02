#!/usr/bin/env python3
"""
Kilo Desktop Eyes - Enhanced with Visual Context Capture
Monitors desktop activity and captures screenshots for intelligent analysis.
"""

import os
import time
import logging
import requests
import subprocess
import threading
import base64
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from io import BytesIO

# Configuration
USER_HOME = os.path.expanduser("~")
DOWNLOADS_DIR = os.path.join(USER_HOME, "Downloads")
SCREENSHOT_DIR = os.path.join(USER_HOME, ".kilo_screenshots")

# Ensure screenshot directory exists
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Kilo AI Brain running on HP k3s cluster
UNIFIED_AGENT_NOTIFY_URL   = "http://192.168.68.57:30002/api/ai_brain/observations"
SCREENSHOT_ENDPOINT        = "http://192.168.68.57:30002/api/ai_brain/analyze_screen"
VISION_ANALYZE_URL         = "http://192.168.68.57:30002/api/ai_brain/vision/analyze"
FINANCIAL_TRANSACTIONS_URL = "http://192.168.68.57:30002/api/financial/transactions"
POLL_INTERVAL = 5  # Seconds between window checks

# Windows that trigger screenshot + Gemini Vision analysis
FINANCIAL_PATTERNS = [
    "bank", "banking", "chase", "wells fargo", "bofa", "account",
    "paypal", "venmo", "zelle", "credit card", "transaction",
    "mint", "quickbooks", "expense", "receipt", "invoice",
    "register", "ledger", "balance", "statement"
]
EMAIL_PATTERNS = [
    "gmail", "inbox", "mail", "outlook", "thunderbird",
    "yahoo mail", "protonmail", "email"
]
ACTIONABLE_PATTERNS = FINANCIAL_PATTERNS + [
    "amazon", "shopping", "checkout", "cart"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KiloDesktopEnhanced")

import cv2 as _cv2
import numpy as _np

_cam_lock = threading.Lock()
_CASCADE_PATH = _cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

def _capture_frame():
    """Open webcam, grab one frame (1 warmup), release. Returns numpy frame or None."""
    with _cam_lock:
        if not os.path.exists("/dev/video0"):
            return None
        cap = _cv2.VideoCapture(0)
        if not cap.isOpened():
            return None
        try:
            cap.read()  # one warmup frame
            ret, frame = cap.read()
            if not ret or frame is None or frame.shape[0] < 10:
                return None
            if _np.mean(frame) <= 8:
                return None  # dark/covered
            return frame
        finally:
            cap.release()

def send_to_unified_agent(payload: dict):
    """Sends a notification payload to the Unified Agent in a non-blocking way."""
    def _task():
        try:
            payload.setdefault("timestamp", datetime.now().isoformat())

            logger.info(f"Sending payload to Unified Agent: {payload.get('type')[:30]}...")
            resp = requests.post(UNIFIED_AGENT_NOTIFY_URL, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info(f"Unified Agent replied with status: {resp.status_code}")
        except Exception as e:
            logger.error(f"Error sending to Unified Agent: {e}")

    threading.Thread(target=_task, daemon=True).start()

def capture_screenshot():
    """Capture a screenshot using scrot or gnome-screenshot."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"kilo_capture_{timestamp}.png")

    try:
        # Try scrot first (faster)
        result = subprocess.run(
            ["scrot", "-o", screenshot_path],
            capture_output=True,
            timeout=5
        )

        if result.returncode != 0:
            # Fallback to gnome-screenshot
            result = subprocess.run(
                ["gnome-screenshot", "-f", screenshot_path],
                capture_output=True,
                timeout=5
            )

        if result.returncode == 0 and os.path.exists(screenshot_path):
            logger.info(f"📸 Screenshot captured: {screenshot_path}")
            return screenshot_path
        else:
            logger.error(f"Screenshot failed: {result.stderr}")
            return None

    except FileNotFoundError:
        logger.error("Screenshot tool not found. Install scrot or gnome-screenshot.")
        return None
    except Exception as e:
        logger.error(f"Error capturing screenshot: {e}")
        return None

def send_screenshot_for_analysis(screenshot_path: str, window_title: str, context: str):
    """Send screenshot to AI Brain for visual analysis and data extraction."""
    def _task():
        try:
            # Read and encode screenshot
            with open(screenshot_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')

            payload = {
                "image_base64": image_data,
                "window_title": window_title,
                "context": context,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"🧠 Sending screenshot for analysis: {window_title[:50]}...")
            resp = requests.post(SCREENSHOT_ENDPOINT, json=payload, timeout=60)

            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"✅ Analysis complete: {result.get('summary', 'No summary')[:100]}")
            else:
                logger.error(f"Analysis failed: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            logger.error(f"Error sending screenshot for analysis: {e}")
        finally:
            # Cleanup screenshot after sending
            try:
                os.remove(screenshot_path)
            except:
                pass

    threading.Thread(target=_task, daemon=True).start()

def _extract_json(text: str):
    """Robustly extract JSON from a Gemini response that may contain markdown fences."""
    import json, re
    # Strip ```json ... ``` or ``` ... ``` code fences
    fence = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', text, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1))
        except json.JSONDecodeError:
            pass
    # Fall back to first {...} block
    brace = re.search(r'\{.*\}', text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group())
        except json.JSONDecodeError:
            pass
    return None


def send_financial_vision(screenshot_path: str, window_title: str):
    """Send a financial window screenshot to Gemini Vision, extract transactions, log them."""
    def _task():
        try:
            with open(screenshot_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            prompt = (
                "This is a screenshot of a bank register, transaction list, or financial page. "
                "Extract ALL visible transactions. For each return: date, description/merchant, "
                "amount (negative for debits, positive for credits). "
                "Respond as JSON: {\"transactions\": [{\"date\": \"YYYY-MM-DD\", "
                "\"description\": \"...\", \"amount\": -12.34, \"category\": \"...\"}]}. "
                "If no transactions visible, return {\"transactions\": []}."
            )
            resp = requests.post(VISION_ANALYZE_URL,
                json={"image_base64": image_data, "prompt": prompt, "source": "bank_screen"},
                timeout=30)
            if resp.status_code != 200:
                logger.warning(f"Vision analyze failed: {resp.status_code}")
                return
            result_text = resp.json().get("result", "")
            data = _extract_json(result_text)
            if not data:
                logger.info(f"No JSON in vision result: {result_text[:100]}")
                return
            transactions = data.get("transactions", [])
            if not transactions:
                logger.info("No transactions found in screenshot")
                return
            logger.info(f"Found {len(transactions)} transactions in screenshot")
            # Post as observation so Kilo knows
            requests.post(UNIFIED_AGENT_NOTIFY_URL, json={
                "content": f"[Bank screen] Saw {len(transactions)} transactions in {window_title[:50]}. "
                           f"Sample: {transactions[0].get('description','?')} {transactions[0].get('amount','?')}",
                "source": "screen_vision",
                "type": "financial_screen",
                "priority": "normal",
                "metadata": {"transactions": transactions, "window": window_title}
            }, timeout=10)
            # Log each transaction to financial service
            for tx in transactions:
                try:
                    requests.post(FINANCIAL_TRANSACTIONS_URL, json={
                        "date": tx.get("date", ""),
                        "description": tx.get("description", "unknown"),
                        "amount": float(tx.get("amount", 0)),
                        "category": tx.get("category", "bank_screen"),
                        "source": "screen_ocr"
                    }, timeout=5)
                except Exception as e:
                    logger.warning(f"Failed to log transaction: {e}")
        except Exception as e:
            logger.error(f"Financial vision error: {e}")
        finally:
            try:
                os.remove(screenshot_path)
            except:
                pass
    threading.Thread(target=_task, daemon=True).start()


def send_email_vision(screenshot_path: str, window_title: str):
    """Send an email inbox screenshot to Gemini Vision, extract subject lines, post as observation."""
    def _task():
        try:
            with open(screenshot_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            prompt = (
                "This is a screenshot of an email inbox. List ALL visible email subjects and senders. "
                "Flag any that look like bills, invoices, payment due, subscription renewal, or important notices. "
                "Respond as JSON: {\"emails\": [{\"subject\": \"...\", \"sender\": \"...\", "
                "\"is_bill\": true/false, \"bill_type\": \"electric/water/subscription/etc or null\"}]}."
            )
            resp = requests.post(VISION_ANALYZE_URL,
                json={"image_base64": image_data, "prompt": prompt, "source": "email_screen"},
                timeout=30)
            if resp.status_code != 200:
                return
            result_text = resp.json().get("result", "")
            data = _extract_json(result_text)
            if not data:
                logger.info(f"No JSON in email vision result: {result_text[:100]}")
                return
            emails = data.get("emails", [])
            bills = [e for e in emails if e.get("is_bill")]
            all_subjects = [e.get("subject", "") for e in emails[:10]]
            content = f"[Email inbox] {len(emails)} emails visible. Subjects: {'; '.join(all_subjects[:5])}"
            if bills:
                bill_desc = ", ".join(f"{b.get('bill_type','bill')}: {b.get('subject','?')}" for b in bills[:3])
                content += f". BILLS FLAGGED: {bill_desc}"
            requests.post(UNIFIED_AGENT_NOTIFY_URL, json={
                "content": content,
                "source": "screen_vision",
                "type": "email_screen",
                "priority": "high" if bills else "normal",
                "metadata": {"emails": emails, "bills": bills, "window": window_title}
            }, timeout=10)
            logger.info(f"Email vision: {len(emails)} emails, {len(bills)} bills flagged")
        except Exception as e:
            logger.error(f"Email vision error: {e}")
        finally:
            try:
                os.remove(screenshot_path)
            except:
                pass
    threading.Thread(target=_task, daemon=True).start()


def is_actionable_window(window_title: str) -> bool:
    """Check if window title matches actionable patterns."""
    if not window_title:
        return False

    window_lower = window_title.lower()
    return any(pattern in window_lower for pattern in ACTIONABLE_PATTERNS)

class KiloFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        filename = os.path.basename(event.src_path)

        payload = {
            "type": "file_observation",
            "content": f"New file downloaded: '{filename}'",
            "priority": "normal",
            "metadata": {"filename": filename, "path": event.src_path}
        }
        send_to_unified_agent(payload)

def get_active_window():
    """Get the currently focused/active window title."""
    try:
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        logger.error(f"Error getting active window: {e}")
    return None

def main():
    logger.info("🔥 Kilo Desktop Eyes ENHANCED - Visual Context Capture ENABLED 😈👁️")

    # Setup file system observer
    event_handler = KiloFileHandler()
    observer = Observer()
    if os.path.exists(DOWNLOADS_DIR):
        observer.schedule(event_handler, DOWNLOADS_DIR, recursive=False)
        observer.start()
        logger.info(f"📁 Watching: {DOWNLOADS_DIR}")

    # Track windows for smart deduplication
    seen_windows = {}
    last_active_window = None
    window_focus_start = None
    last_screenshot_time = {}  # Track when we last captured each window

    FOCUS_THRESHOLD = 10  # Seconds
    DEDUPE_WINDOW = 300  # 5 minutes
    SCREENSHOT_COOLDOWN = 60  # Don't screenshot same window more than once per minute

    ignore_patterns = ["Desktop @ QRect", "^Plasma$", "^Desktop$"]

    try:
        while True:
            active_window = get_active_window()

            if not active_window or any(pattern in active_window for pattern in ignore_patterns):
                time.sleep(POLL_INTERVAL)
                continue

            current_time = time.time()

            if active_window != last_active_window:
                last_active_window = active_window
                window_focus_start = current_time
                logger.info(f"Focus changed to: {active_window}")

                # Check if this is an actionable window
                if is_actionable_window(active_window):
                    logger.info(f"🎯 ACTIONABLE window detected: {active_window}")

            else:
                focus_duration = current_time - window_focus_start

                # Regular observation reporting
                if focus_duration >= FOCUS_THRESHOLD:
                    last_seen = seen_windows.get(active_window, 0)
                    time_since_last_report = current_time - last_seen

                    if time_since_last_report >= DEDUPE_WINDOW:
                        logger.info(f"👁️  Kilo watching: {active_window}")

                        payload = {
                            "type": "window_observation",
                            "content": f"Kyle is viewing: {active_window}",
                            "priority": "normal",
                            "metadata": {
                                "window_title": active_window,
                                "focus_duration": round(focus_duration, 1),
                                "actionable": is_actionable_window(active_window)
                            }
                        }
                        send_to_unified_agent(payload)
                        seen_windows[active_window] = current_time

                        # Vision analysis for financial and email windows
                        window_lower = active_window.lower()
                        is_financial = any(p in window_lower for p in FINANCIAL_PATTERNS)
                        is_email = any(p in window_lower for p in EMAIL_PATTERNS)

                        if is_financial or is_email:
                            last_screenshot = last_screenshot_time.get(active_window, 0)
                            if current_time - last_screenshot >= SCREENSHOT_COOLDOWN:
                                logger.info(f"Capturing screenshot for vision analysis: {active_window[:50]}")
                                screenshot_path = capture_screenshot()
                                if screenshot_path:
                                    if is_financial:
                                        send_financial_vision(screenshot_path, active_window)
                                    elif is_email:
                                        send_email_vision(screenshot_path, active_window)
                                    last_screenshot_time[active_window] = current_time

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Kilo Desktop Eyes interrupted. Shutting down.")
        observer.stop()
    except Exception as e:
        logger.critical(f"Kilo Desktop Eyes crashed: {e}", exc_info=True)
    finally:
        if 'observer' in locals() and observer.is_alive():
            observer.join()

def _analyze_mood(face_b64: str):
    """Send a face crop to Gemini Vision for mood/energy/stress estimation. Runs in a daemon thread."""
    def _task():
        try:
            prompt = (
                "This is a close-up of a person's face. "
                "Describe their emotional state in 2-3 words (e.g. 'focused and calm', 'tired', 'happy', 'stressed'). "
                "Rate energy 1-10 and stress 1-10. "
                "Respond ONLY as JSON: {\"mood\": \"...\", \"energy\": 7, \"stress\": 3}"
            )
            resp = requests.post(VISION_ANALYZE_URL,
                json={"image_base64": face_b64, "prompt": prompt, "source": "desk_webcam_mood"},
                timeout=30)
            if resp.status_code != 200:
                return
            data = _extract_json(resp.json().get("result", ""))
            if not data:
                return
            mood = data.get("mood", "unknown")
            energy = data.get("energy")
            stress = data.get("stress")
            content = f"Kyle's mood at desk: {mood}"
            if energy is not None:
                content += f" (energy {energy}/10, stress {stress}/10)"
            requests.post(UNIFIED_AGENT_NOTIFY_URL, json={
                "content": content, "source": "desk_webcam",
                "type": "mood_observation", "priority": "low",
                "metadata": {"mood": mood, "energy": energy, "stress": stress}
            }, timeout=10)
            logger.info(f"Mood observation posted: {mood}")
        except Exception as e:
            logger.warning(f"Mood analysis error: {e}")
    threading.Thread(target=_task, daemon=True).start()


def presence_loop():
    """Fast local presence detection — Haar cascade only, no network. Runs every 15s."""
    face_cascade = _cv2.CascadeClassifier(_CASCADE_PATH)
    _at_desk = None    # None=unknown, True=present, False=away
    _away_since = None
    AFK_TIMEOUT = 300  # 5 min without face → "stepped away"
    PRESENCE_INTERVAL = 15

    logger.info(f"Presence loop started — every {PRESENCE_INTERVAL}s (local only)")
    while True:
        try:
            frame = _capture_frame()
            if frame is not None:
                gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
                face_now = len(faces) > 0

                if face_now:
                    if _at_desk is not True:
                        _at_desk = True
                        _away_since = None
                        logger.info("Presence: Kyle sat down at desk")
                        requests.post(UNIFIED_AGENT_NOTIFY_URL, json={
                            "content": "Kyle sat down at the desk",
                            "source": "desk_webcam", "type": "presence", "priority": "low"
                        }, timeout=5)
                else:
                    if _away_since is None:
                        _away_since = time.time()
                    elif time.time() - _away_since >= AFK_TIMEOUT and _at_desk is not False:
                        _at_desk = False
                        logger.info("Presence: Kyle stepped away from desk")
                        requests.post(UNIFIED_AGENT_NOTIFY_URL, json={
                            "content": "Kyle stepped away from the desk",
                            "source": "desk_webcam", "type": "presence", "priority": "low"
                        }, timeout=5)
        except Exception as e:
            logger.warning(f"presence_loop error: {e}")
        time.sleep(PRESENCE_INTERVAL)


def activity_loop():
    """Slow Gemini activity + mood loop. Runs every 5 min; skips if scene unchanged."""
    CAM_ANALYZE_URL = "http://192.168.68.57:30002/api/cam/analyze_activity"
    MIN_JPEG_BYTES = 5000
    ACTIVITY_INTERVAL = 300   # 5 min between Gemini activity calls
    MOOD_INTERVAL = 600       # 10 min between mood reads
    CONFIRM_FRAMES = 2

    face_cascade = _cv2.CascadeClassifier(_CASCADE_PATH)
    last_activity = None
    pending_activity = None
    pending_count = 0
    _last_mood_time = 0
    _last_frame_gray = None   # for frame-diff gate

    logger.info(f"Activity loop started — Gemini every {ACTIVITY_INTERVAL}s")
    time.sleep(30)  # stagger startup so presence loop gets first camera grab
    while True:
        try:
            frame = _capture_frame()
            if frame is None:
                time.sleep(ACTIVITY_INTERVAL)
                continue

            # Frame-diff gate — skip Gemini if scene barely changed
            frame_small = _cv2.resize(
                _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY), (64, 48))
            if _last_frame_gray is not None:
                diff = float(_np.mean(_np.abs(
                    frame_small.astype(int) - _last_frame_gray.astype(int))))
                if diff < 8.0:
                    logger.info(f"Activity: scene unchanged (diff={diff:.1f}) — skipping Gemini")
                    time.sleep(ACTIVITY_INTERVAL)
                    continue
            _last_frame_gray = frame_small

            # Mood tracking (face crop → Gemini, every MOOD_INTERVAL)
            gray = _cv2.cvtColor(frame, _cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
            if len(faces) > 0 and time.time() - _last_mood_time >= MOOD_INTERVAL:
                x, y, w, h = faces[0]
                pad = 20
                y1 = max(0, y - pad);  y2 = min(frame.shape[0], y + h + pad)
                x1 = max(0, x - pad);  x2 = min(frame.shape[1], x + w + pad)
                face_crop = frame[y1:y2, x1:x2]
                ok2, buf2 = _cv2.imencode(".jpg", face_crop, [_cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok2 and buf2 is not None and len(buf2) > 1000:
                    _analyze_mood(base64.b64encode(buf2.tobytes()).decode())
                    _last_mood_time = time.time()

            # Gemini activity detection
            ok, buf = _cv2.imencode(".jpg", frame, [_cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ok or buf is None or len(buf) < MIN_JPEG_BYTES:
                logger.warning(f"Activity: JPEG encode failed or too small — skipping")
                time.sleep(ACTIVITY_INTERVAL)
                continue

            img_b64 = base64.b64encode(buf.tobytes()).decode()
            resp = requests.post(
                CAM_ANALYZE_URL,
                json={"image": img_b64, "label": "Beelink desk webcam", "location": "office/desk"},
                timeout=60)
            if resp.status_code == 200:
                activity = resp.json().get("activity", "")
                if activity:
                    if activity == pending_activity:
                        pending_count += 1
                    else:
                        pending_activity = activity
                        pending_count = 1
                    if pending_count >= CONFIRM_FRAMES and activity != last_activity:
                        logger.info(f"Activity confirmed ({pending_count}x): {activity}")
                        last_activity = activity
                        pending_count = 0
            else:
                logger.warning(f"analyze_activity returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"activity_loop error: {e}")
        time.sleep(ACTIVITY_INTERVAL)


if __name__ == "__main__":
    threading.Thread(target=presence_loop, daemon=True).start()
    threading.Thread(target=activity_loop, daemon=True).start()
    main()
