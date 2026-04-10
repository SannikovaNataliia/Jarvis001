import whisper
import sounddevice as sd
import scipy.io.wavfile as wav
import anthropic
import os
import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model
import time
import torch
import warnings
from kokoro_onnx import Kokoro
from commands import handle_command, good_morning, startup_setup, open_chrome, open_discord, tell_me_about_bts
import threading
import sys
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY")

print("Loading Whisper...")
device = "cuda" if torch.cuda.is_available() else "cpu"
whisper_model = whisper.load_model("base", device=device)
print(f"Whisper running on: {device}")

print("Loading Kokoro...")
kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

print("Loading wake word model...")
openwakeword.utils.download_models()
oww_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

client = anthropic.Anthropic(api_key=API_KEY)
history = []

FAREWELL_WORDS = ["thank you", "thanks", "bye", "that's all", "no thanks", "nothing", "okay thank you"]
STOP_WORDS = ["stop", "shut up", "quiet", "enough"]
SHUTDOWN_WORDS = ["shutdown jarvis", "turn off jarvis", "close jarvis", "goodbye jarvis", "go offline"]
INTERRUPT_THRESHOLD = 800


def get_microphone_device():
    devices = sd.query_devices()
    target = "FIFINE"
    for i, device in enumerate(devices):
        if target.lower() in device['name'].lower() and device['max_input_channels'] > 0:
            print(f"🎙️ Using: {device['name']}")
            return i
    print("🎙️ FIFINE not found, using default microphone")
    return None


def record_audio(seconds=5, samplerate=16000):
    device = get_microphone_device()
    print("🎤 Speak now...")
    audio = sd.rec(int(seconds * samplerate), samplerate=samplerate, channels=1, dtype='int16', device=device)
    sd.wait()
    print("✅ Recorded")
    wav.write("input.wav", samplerate, audio)


def transcribe():
    result = whisper_model.transcribe("input.wav", language="en")
    return result["text"].strip()


def is_farewell(text):
    return any(word in text.lower() for word in FAREWELL_WORDS)


def is_empty(text):
    return len(text.strip()) < 3


def is_stop(text):
    return any(word in text.lower() for word in STOP_WORDS)


def is_shutdown(text):
    return any(word in text.lower() for word in SHUTDOWN_WORDS)


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
    clean_text = text.replace("##", "").replace("**", "").replace("*", "").strip()
    print(f"Jarvis: {clean_text}")
    samples, sample_rate = kokoro.create(clean_text, voice="am_echo", speed=1.0, lang="en-us")
    sd.play(samples, sample_rate)
    sd.wait()


def speak(text):
    clean_text = text.replace("##", "").replace("**", "").replace("*", "").strip()
    print(f"Jarvis: {clean_text}")

    sentences = clean_text.replace("!", ".").replace("?", ".").split(".")
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return False

    interrupted = [False]

    def generate(sentence):
        return kokoro.create(sentence, voice="am_echo", speed=1.0, lang="en-us")

    def monitor_interrupt():
        pa = pyaudio.PyAudio()
        stream = pa.open(rate=16000, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=1024)
        time.sleep(0.8)
        while True:
            try:
                chunk = np.frombuffer(stream.read(1024, exception_on_overflow=False), dtype=np.int16)
                if interrupted[0]:
                    break
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

    while True:
        record_audio(seconds=5)

        print("🔍 Transcribing...")
        text = transcribe()
        print(f"You: {text}")

        if is_empty(text):
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
            continue

        if "tell me about bts" in text.lower() or "bts" in text.lower():
            reply = tell_me_about_bts()
            interrupted = speak(reply)
            result = handle_after_speak(interrupted, text)
            if result == "sleep":
                return
            speak_simple("Anything else?")
            continue

        success, message = handle_command(text)
        if success:
            speak_simple(message)
            speak_simple("Anything else?")
            continue

        print("🧠 Thinking...")
        reply = ask_claude(text)
        interrupted = speak(reply)
        result = handle_after_speak(interrupted, text)
        if result == "sleep":
            return
        speak_simple("Anything else?")


def main():
    print("🤖 Jarvis is ready! Say 'Hey Jarvis' to activate, Ctrl+C to exit")
    speak_simple("Jarvis is online and ready.")
    while True:
        listen_for_wakeword()
        run_conversation()


if __name__ == "__main__":
    main()