import time
import speech_recognition as sr
import pyautogui

pyautogui.PAUSE = 0
recognizer = sr.Recognizer()
mic = sr.Microphone()

print("Calibrating for background noise...", flush=True)
with mic as source:
    recognizer.adjust_for_ambient_noise(source, duration=1)

print("Ready.", flush=True)
print("Press Enter, THEN switch focus to wherever you want the text typed", flush=True)
print("(you have a moment before it starts listening), then speak.", flush=True)

while True:
    input("\nPress Enter to start listening...")
    print("Listening... (speak now)", flush=True)
    with mic as source:
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            print("(no speech detected, timed out)", flush=True)
            continue

    print("Transcribing...", flush=True)
    try:
        text = recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        print("(couldn't understand audio -- try again)", flush=True)
        continue
    except sr.RequestError as e:
        print(f"(speech service error: {e})", flush=True)
        continue

    print(f"Heard: {text}", flush=True)
    # Deliberately NOT auto-pressing Enter after typing -- lets you see/edit
    # the transcription before it actually gets sent anywhere.
    pyautogui.typewrite(text, interval=0.01)
