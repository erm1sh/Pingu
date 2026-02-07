"""Generate a short beep WAV for alert sound (stdlib only)."""
import math
import wave
import struct
from pathlib import Path

out = Path(__file__).resolve().parent.parent / "resources" / "alert.wav"
out.parent.mkdir(parents=True, exist_ok=True)
sample_rate = 22050
duration_s = 0.25
freq = 440
n = int(sample_rate * duration_s)
data = []
for i in range(n):
    t = i / sample_rate
    # Fade in/out
    env = 1.0
    if i < sample_rate * 0.02:
        env = i / (sample_rate * 0.02)
    elif i > n - sample_rate * 0.02:
        env = (n - i) / (sample_rate * 0.02)
    v = int(32767 * 0.3 * env * math.sin(2 * math.pi * freq * t))
    data.append(struct.pack("<h", v))
with wave.open(str(out), "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(sample_rate)
    for d in data:
        w.writeframes(d)
print("Wrote", out)
