import math
import struct
import wave
import os
import msvcrt
import winsound

def generate_wav(filename, duration_sec, sample_rate=44100, wave_type='sine', freqs=[440], env='flat'):
    """Generate a simple wav file with given parameters."""
    num_samples = int(duration_sec * sample_rate)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            t = float(i) / sample_rate
            sample = 0.0
            
            if wave_type == 'sine':
                # Sum of frequencies
                for f in freqs:
                    sample += math.sin(2.0 * math.pi * f * t)
                sample /= len(freqs)
            elif wave_type == 'chirp_up':
                f = freqs[0] + (freqs[1] - freqs[0]) * (t / duration_sec)
                sample = math.sin(2.0 * math.pi * f * t)
            elif wave_type == 'bloop':
                f = freqs[0] * math.exp(-t * 20)
                sample = math.sin(2.0 * math.pi * f * t)
            elif wave_type == 'arpeggio':
                step = duration_sec / len(freqs)
                idx = min(int(t / step), len(freqs)-1)
                sample = math.sin(2.0 * math.pi * freqs[idx] * t)
                
            # Envelope
            volume = 32000.0
            if env == 'decay':
                volume *= math.exp(-t * 10)
            elif env == 'fast_decay':
                volume *= math.exp(-t * 30)
            elif env == 'bell':
                volume *= math.exp(-t * 4)
            elif env == 'pop':
                volume *= math.exp(-t * 50)
            elif env == 'flat':
                # quick fade out to prevent clicks
                if i > num_samples - 400:
                    volume *= (num_samples - i) / 400.0
                if i < 400:
                    volume *= i / 400.0
                    
            sample_val = int(sample * volume)
            # clamp
            sample_val = max(-32767, min(32767, sample_val))
            
            wav_file.writeframes(struct.pack('h', sample_val))

print("Generando 50 sonidos de prueba (100% libres de derechos)...")

os.makedirs('sounds', exist_ok=True)

sounds = []

# Helper to add sound
def add_sound(idx, name, dur, freqs, wave_t, env):
    filename = f'sounds/{idx}_{name.replace(" ", "_")}.wav'
    generate_wav(filename, dur, freqs=freqs, wave_type=wave_t, env=env)
    sounds.append((filename, name))

# --- CATEGORY 1: Pops & Clicks (1-10) ---
add_sound(1, "Pop sutil agudo", 0.03, [1200], 'sine', 'pop')
add_sound(2, "Pop sutil grave", 0.04, [600], 'sine', 'pop')
add_sound(3, "Click mecanico", 0.02, [2500], 'sine', 'pop')
add_sound(4, "Click de madera", 0.04, [800], 'sine', 'fast_decay')
add_sound(5, "Doble click", 0.08, [1500, 2000], 'arpeggio', 'pop')
add_sound(6, "Burbuja rapida", 0.06, [900], 'bloop', 'decay')
add_sound(7, "Burbuja lenta", 0.1, [600], 'bloop', 'decay')
add_sound(8, "Tap en cristal", 0.05, [2200], 'sine', 'fast_decay')
add_sound(9, "Tap seco", 0.03, [400], 'sine', 'fast_decay')
add_sound(10, "Pop organico", 0.05, [500], 'bloop', 'pop')

# --- CATEGORY 2: Blips & UI Tones (11-20) ---
add_sound(11, "Blip basico", 0.1, [800], 'sine', 'flat')
add_sound(12, "Doble Blip ascendente", 0.15, [600, 800], 'arpeggio', 'flat')
add_sound(13, "Doble Blip descendente", 0.15, [800, 600], 'arpeggio', 'flat')
add_sound(14, "Triple Blip", 0.2, [600, 800, 1000], 'arpeggio', 'flat')
add_sound(15, "Blip amigable", 0.1, [1046.50], 'sine', 'decay')
add_sound(16, "Blip suave", 0.15, [700], 'sine', 'bell')
add_sound(17, "Notificacion corta", 0.2, [880, 1108.73], 'arpeggio', 'decay')
add_sound(18, "Tono de alerta", 0.15, [1000], 'sine', 'decay')
add_sound(19, "Aviso leve", 0.2, [500, 750], 'arpeggio', 'bell')
add_sound(20, "Ding digital", 0.1, [1400], 'sine', 'fast_decay')

# --- CATEGORY 3: Success & Chords (21-30) ---
add_sound(21, "Arpegio de exito menor", 0.3, [440, 523.25, 659.25], 'arpeggio', 'decay')
add_sound(22, "Arpegio de exito mayor", 0.3, [523.25, 659.25, 783.99], 'arpeggio', 'decay')
add_sound(23, "Acorde de cristal 1", 0.4, [1046.50, 1318.51, 1567.98], 'sine', 'bell') # C major
add_sound(24, "Acorde de cristal 2", 0.4, [880, 1108.73, 1318.51], 'sine', 'bell') # A major
add_sound(25, "Subida magica", 0.3, [600, 800, 1000, 1200], 'arpeggio', 'decay')
add_sound(26, "Confirmacion organica", 0.25, [500, 800], 'arpeggio', 'bell')
add_sound(27, "Desbloqueo", 0.2, [800, 1200], 'arpeggio', 'pop')
add_sound(28, "Resuelto", 0.3, [600, 900], 'arpeggio', 'decay')
add_sound(29, "Acorde magico", 0.5, [1200, 1500, 1900], 'sine', 'decay')
add_sound(30, "Victoria rapida", 0.2, [1046.50, 1567.98], 'arpeggio', 'bell')

# --- CATEGORY 4: Sci-Fi & Swipes (31-40) ---
add_sound(31, "Chirp Swipe Up", 0.1, [400, 1000], 'chirp_up', 'flat')
add_sound(32, "Chirp Swipe Down", 0.1, [1000, 400], 'chirp_up', 'flat')
add_sound(33, "Laser corto", 0.08, [1500, 500], 'chirp_up', 'pop')
add_sound(34, "Fuerza Sci-fi", 0.15, [300, 800], 'chirp_up', 'decay')
add_sound(35, "Teletransporte", 0.2, [100, 1200], 'chirp_up', 'fast_decay')
add_sound(36, "Zap galactico", 0.1, [2000, 200], 'chirp_up', 'pop')
add_sound(37, "Zumbido digital", 0.15, [200, 400], 'chirp_up', 'decay')
add_sound(38, "Transicion holografica", 0.2, [800, 1600], 'chirp_up', 'bell')
add_sound(39, "Swoosh agudo", 0.15, [1000, 2500], 'chirp_up', 'flat')
add_sound(40, "Swoosh grave", 0.15, [500, 1000], 'chirp_up', 'flat')

# --- CATEGORY 5: Thumps & Percussion (41-50) ---
add_sound(41, "Marimba grave", 0.15, [300], 'sine', 'fast_decay')
add_sound(42, "Marimba media", 0.15, [500], 'sine', 'fast_decay')
add_sound(43, "Marimba aguda", 0.15, [800], 'sine', 'fast_decay')
add_sound(44, "Thump sordo lento", 0.15, [100], 'sine', 'decay')
add_sound(45, "Thump rapido", 0.05, [150], 'sine', 'pop')
add_sound(46, "Gota percusiva", 0.08, [400], 'bloop', 'fast_decay')
add_sound(47, "Toque en madera", 0.06, [600], 'sine', 'pop')
add_sound(48, "Toque en metal", 0.1, [1800], 'sine', 'fast_decay')
add_sound(49, "Bombo digital", 0.15, [80], 'sine', 'decay')
add_sound(50, "Caja de ritmos", 0.05, [300, 600], 'chirp_up', 'pop')

print("\n--- TEST DE SONIDOS SATISFACTORIOS (50 OPCIONES) ---")
print("Escribe un numero del 1 al 50 y presiona ENTER.")
print("Escribe 'Q' para salir.\n")

import sys

for i, (path, desc) in enumerate(sounds):
    print(f"[{i+1:2d}] {desc}")

while True:
    print("\nElige un sonido (1-50) o Q: ", end="", flush=True)
    val = sys.stdin.readline().strip().lower()
    
    if val == 'q':
        break
        
    if val.isdigit():
        idx = int(val) - 1
        if 0 <= idx < 50:
            path, desc = sounds[idx]
            print(f"--> Reproduciendo: {desc}")
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            print("Numero fuera de rango.")

print("Saliendo del test...")
