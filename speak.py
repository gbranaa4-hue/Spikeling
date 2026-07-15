import sys
import pyttsx3

text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Test. Can you hear me?"
engine = pyttsx3.init()
engine.say(text)
engine.runAndWait()
