import re
import sounddevice as sd
import scipy.io.wavfile as wav
import anthropic
import os
import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model
import time
import warnings
import edge_tts
import soundfile as sf
import asyncio
import tempfile
from commands import handle_command, good_morning, startup_setup, open_chrome, open_discord, tell_me_about_bts
from router import route_request, groq_answer, groq_wrap, claude_web_search, claude_answer
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from groq import Groq
from dotenv import load_dotenv
from pynput import keyboard

warnings.filterwarnings("ignore")
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

VOICE = "en-US-EricNeural"

print("Loading wake word model...")
openwakeword.utils.download_models()
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

client = anthropic.Anthropic(api_key=API_KEY)
history = []
router_history = []

FAREWELL_WORDS = ["thank you", "thanks", "bye", "that's all", "no thanks", "nothing", "okay thank you"]
STOP_WORDS = ["stop", "shut up", "quiet", "enough"]
SHUTDOWN_WORDS = ["shutdown jarvis", "turn off jarvis", "close jarvis", "goodbye jarvis", "go offline"]
INTERRUPT_THRESHOLD = 800
recording_active = False
alt_pressed = False

def on_press(key):
    global alt_pressed
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        alt_pressed = True

def on_release(key):
    global alt_pressed
    if key in (keyboard.Key.alt_l, keyboard.Key.alt_r):
        alt_pressed = False

keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
keyboard_listener.daemon = True
keyboard_listener.start()


def get_microphone_device():
    devices = sd.query_devices()
    target = "FIFINE"
    for i, device in enumerate(devices):
        if target.lower() in device['name'].lower() and device['max_input_channels'] > 0:
            print(f"🎙️ Using: {device['name']}")
            return i
    print("🎙️ FIFINE not found, using default microphone")
    return None


def play_beep():
    sr, data = wav.read(r"C:\Jarvis\beep.wav")
    if data.ndim == 2:
        data = data.mean(axis=1).astype(np.float32) / 32768.0
    else:
        data = data.astype(np.float32) / 32768.0
    with sd.OutputStream(samplerate=sr, channels=1) as stream:
        stream.write(data)


def record_audio(seconds=7, samplerate=16000):
    global recording_active
    play_beep()
    recording_active = True
    device_idx = get_microphone_device()
    chunk_size = 1024
    pa = pyaudio.PyAudio()
    stream = pa.open(
        rate=samplerate, channels=1, format=pyaudio.paInt16,
        input=True, input_device_index=device_idx,
        frames_per_buffer=chunk_size
    )

    frames = []
    speaking_started = False
    silent_chunks = 0
    max_wait_chunks = int(seconds * samplerate / chunk_size)  # wait for speech start
    silence_chunks_needed = int(1.5 * samplerate / chunk_size)  # silence after speech
    voice_threshold = 300

    print("🎤 Speak now...")

    # Phase 1: wait for speech to start (max 7 sec)
    for _ in range(max_wait_chunks):
        chunk = stream.read(chunk_size, exception_on_overflow=False)
        frames.append(chunk)
        amplitude = np.abs(np.frombuffer(chunk, dtype=np.int16)).mean()
        if amplitude > voice_threshold:
            speaking_started = True
            break

    # Phase 2: record until 1.5s silence (no time limit)
    if speaking_started:
        while True:
            chunk = stream.read(chunk_size, exception_on_overflow=False)
            frames.append(chunk)
            amplitude = np.abs(np.frombuffer(chunk, dtype=np.int16)).mean()
            if amplitude < voice_threshold:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    break
            else:
                silent_chunks = 0

    stream.stop_stream()
    stream.close()
    pa.terminate()

    recording_active = False
    print("✅ Recorded")
    audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
    wav.write("input.wav", samplerate, audio_data)


def transcribe():
    with open("input.wav", "rb") as f:
        transcription = groq_client.audio.transcriptions.create(
            file=("input.wav", f.read()),
            model="whisper-large-v3-turbo",
            language="en",
            response_format="text"
        )
    return transcription.strip()


def is_farewell(text):
    return any(word in text.lower() for word in FAREWELL_WORDS)


def is_empty(text):
    return len(text.strip()) < 3


def is_stop(text):
    return any(word in text.lower() for word in STOP_WORDS)


def is_shutdown(text):
    return any(word in text.lower() for word in SHUTDOWN_WORDS)


def process_with_router(text):
    global router_history

    route = route_request(text)
    action = route.get("action")

    if action == "command":
        success, message = handle_command(text)
        if success:
            return message, False, True
        return groq_answer(text, router_history)["text"], False, True

    elif action == "answer":
        result = groq_answer(text, router_history)
        router_history.append({"role": "user", "content": text})
        router_history.append({"role": "assistant", "content": result["text"]})
        if len(router_history) > 20:
            router_history = router_history[-20:]
        return result["text"], result["has_question"], False

    elif action == "web_search":
        raw = claude_web_search(text)
        wrapped = groq_wrap(raw["text"], text)
        router_history.append({"role": "user", "content": text})
        router_history.append({"role": "assistant", "content": wrapped["text"]})
        if len(router_history) > 20:
            router_history = router_history[-20:]
        return wrapped["text"], wrapped["has_question"], False

    elif action == "ask_claude":
        speak_simple("This might need Claude. Should I ask?")
        play_beep()
        record_audio(seconds=3)
        answer = transcribe()
        if any(w in answer.lower() for w in ["yes", "sure", "yeah", "yep", "do it"]):
            result = claude_answer(text, router_history)
            router_history.append({"role": "user", "content": text})
            router_history.append({"role": "assistant", "content": result["text"]})
            return result["text"], result["has_question"], False
        else:
            return "Got it, skipping Claude.", False, False

    return groq_answer(text, router_history)["text"], False, False


def ask_claude(text):
    history.append({"role": "user", "content": text})
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system='''You are a personal assistant named Jarvis.

About the user:
- Name: Nata
- Location: Lviv, Ukraine
- Timezone: Europe/Kyiv (UTC+2 in winter, UTC+3 in summer, DST applies)

Rules:
- Always reply in the same language the user speaks
- Use metric system only (Celsius, km, kg)
- No markdown formatting in spoken responses
- Keep responses concise by default
- Give details only when the topic requires it or user asks
- For weather always use Celsius
- For time always use 12h format
''',
        messages=history,
        tools=[{"type": "web_search_20250305", "name": "web_search"}]
    )
    reply = ""
    for block in response.content:
        if hasattr(block, "text"):
            reply += block.text
    if not reply:
        reply = "I searched but couldn't find a clear answer."
    history.append({"role": "assistant", "content": reply})
    return reply


def speak_simple(text):
    clean = text.replace("##", "").replace("**", "").replace("*", "").strip()
    print(f"Jarvis: {clean}")
    async def _speak():
        communicate = edge_tts.Communicate(clean, VOICE)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp_path = f.name
        await communicate.save(tmp_path)
        data, sr = sf.read(tmp_path)
        sd.play(data, sr)
        sd.wait()
        os.remove(tmp_path)
    asyncio.run(_speak())


def speak(text):
    clean_text = text.replace("##", "").replace("**", "").replace("*", "").strip()
    print(f"Jarvis: {clean_text}")

    sentences = clean_text.replace("!", ".").replace("?", ".").split(".")
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return False

    interrupted = [False]

    def generate(sentence):
        async def _gen():
            communicate = edge_tts.Communicate(sentence, VOICE)
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                tmp_path = f.name
            await communicate.save(tmp_path)
            data, sr = sf.read(tmp_path)
            os.remove(tmp_path)
            return data, sr
        return asyncio.run(_gen())

    def monitor_interrupt():
        pa = pyaudio.PyAudio()
        stream = pa.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1024)
        time.sleep(0.8)
        while True:
            try:
                chunk = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                if interrupted[0]:
                    break
                if recording_active:
                    break
                if alt_pressed:
                    time.sleep(0.05)
                    continue
                if np.abs(chunk).mean() > INTERRUPT_THRESHOLD:
                    if not interrupted[0]:
                        print("⚡ Interrupted!")
                        sd.stop()
                        interrupted[0] = True
                    break
            except:
                break
        stream.stop_stream()
        stream.close()
        pa.terminate()

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            future = executor.submit(generate, sentences[0])

            for i, _ in enumerate(sentences):
                if interrupted[0]:
                    break

                samples, sample_rate = future.result()

                if i + 1 < len(sentences):
                    future = executor.submit(generate, sentences[i + 1])

                monitor_thread = threading.Thread(target=monitor_interrupt, daemon=True)
                monitor_thread.start()

                sd.play(samples, sample_rate)
                sd.wait()
                time.sleep(0.05)

                monitor_thread.join(timeout=0.1)
    except Exception:
        pass

    return interrupted[0]


def listen_for_wakeword():
    oww_model.reset()
    time.sleep(1)
    pa = pyaudio.PyAudio()
    stream = pa.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1280)
    print("👂 Listening for 'Hey Jarvis'...")
    while True:
        audio_chunk = np.frombuffer(stream.read(1280), dtype=np.int16)
        oww_model.predict(audio_chunk)
        for name, score in oww_model.prediction_buffer.items():
            if score[-1] > 0.5:
                print(f"✅ Wake word detected! ({name}: {score[-1]:.2f})")
                stream.stop_stream()
                stream.close()
                pa.terminate()
                return


def handle_after_interrupt():
    print("🎤 Recording after interrupt...")
    record_audio(seconds=5)
    print("🔍 Transcribing...")
    text = transcribe()
    print(f"You: {text}")
    return text


def handle_after_speak(interrupted, text):
    if interrupted:
        text = handle_after_interrupt()

        if is_empty(text):
            speak_simple("Going to sleep. Say Hey Jarvis to wake me up.")
            return "sleep"

        if is_shutdown(text):
            speak_simple("Shutting down. Goodbye Nata!")
            sys.exit()

        if is_farewell(text):
            speak_simple("Sure, I'll be here if you need me.")
            return "sleep"

        if is_stop(text):
            speak_simple("Okay.")
            return "continue"

        success, message = handle_command(text)
        if success:
            speak_simple(message)
            return "continue"

        print("🧠 Thinking...")
        reply = ask_claude(text)
        speak(reply)

    return "continue"


def run_conversation():
    speak_simple("Yes, I'm listening.")
    record_audio(seconds=5)

    while True:
        print("🔍 Transcribing...")
        text = transcribe()
        print(f"You: {text}")

        if is_empty(text) or len(text.strip().split()) < 2:
            speak_simple("Going to sleep. Say Hey Jarvis to wake me up.")
            return

        if is_shutdown(text):
            speak_simple("Shutting down. Goodbye Nata!")
            sys.exit()

        if is_farewell(text):
            speak_simple("Sure, I'll be here if you need me.")
            return

        if is_stop(text):
            speak_simple("Okay.")
            speak_simple("Anything else?")
            record_audio(seconds=7)
            continue

        if "good morning" in text.lower():
            result, time_str = good_morning()
            if result == "workday":
                t = threading.Thread(target=startup_setup)
                t.start()
                speak_simple(f"Good morning Nata! It's {time_str}, starting your workday setup.")
            else:
                t = threading.Thread(target=lambda: (open_chrome(), open_discord()))
                t.start()
                speak_simple(f"Good morning Nata! It's {time_str}, enjoy your weekend!")
            speak_simple("Anything else?")
            record_audio(seconds=7)
            continue

        if "tell me about bts" in text.lower() or "bts" in text.lower():
            reply = tell_me_about_bts()
            interrupted = speak(reply)
            result = handle_after_speak(interrupted, text)
            if result == "sleep":
                return
            speak_simple("Anything else?")
            record_audio(seconds=7)
            continue

        try:
            print("🧠 Thinking...")
            reply, has_question, is_command = process_with_router(text)
            interrupted = speak(reply) if reply else False
            print(f"DEBUG has_question: {has_question}")
            if interrupted:
                result = handle_after_speak(interrupted, text)
                if result == "sleep":
                    return
            elif not has_question:
                speak_simple("Anything else?")
            record_audio()
        except Exception as e:
            print(f"router error: {e}")
            import traceback
            traceback.print_exc()
            record_audio()


def main():
    print("🤖 Jarvis is ready! Say 'Hey Jarvis' to activate, Ctrl+C to exit")
    speak_simple("Jarvis is online and ready.")
    while True:
        listen_for_wakeword()
        try:
            run_conversation()
        except SystemExit:
            sys.exit()
        except Exception as e:
            print(f"run_conversation error: {e}")
            import traceback
            traceback.print_exc()
            continue


if __name__ == "__main__":
    main()