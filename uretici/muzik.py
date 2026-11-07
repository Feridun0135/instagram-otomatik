"""Her video için telifsiz arka plan müziği sentezler (indirme gerekmez, telif sorunu yoktur).

İçerik türüne göre üç ruh hali vardır:
- yeni_urun:          tempolu, modern (pluck arpej + yumuşak davul)
- ipucu:              lo-fi, rahat (elektrik piyano akorları + fırça davul)
- teknoloji_bilgisi:  merak uyandıran ambiyans (sıcak pad + yumuşak arpej)

İstenirse `muzik/<icerik_turu>/` veya `muzik/` klasörüne konan kendi müzik dosyaların (mp3/wav)
sentez yerine kullanılır. Bu dosyaların lisansı senin sorumluluğundadır.
"""
import random
import wave
from pathlib import Path

import numpy as np

from . import ayarlar

SR = 44100


def _frekans(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _zarf(n: int, atak: float, birakma: float) -> np.ndarray:
    z = np.ones(n)
    a, b = max(1, int(atak * SR)), max(1, int(birakma * SR))
    a, b = min(a, n), min(b, n)
    z[:a] = np.linspace(0, 1, a)
    z[n - b:] *= np.linspace(1, 0, b)
    return z


def _ton(frekans: float, sure: float, harmonikler: int, egim: float, sonum: float = 0.0,
         detune: float = 0.0) -> np.ndarray:
    """Toplamsal sentez: harmonikler 1/n^egim genlikli; sonum>0 ise yüksek harmonikler daha hızlı söner."""
    t = np.arange(int(sure * SR)) / SR
    x = np.zeros_like(t)
    for d in ([0.0] if not detune else [-detune, detune]):
        f = frekans * (1 + d)
        for h in range(1, harmonikler + 1):
            if f * h > SR / 2.2:
                break
            g = 1 / h ** egim
            if sonum:
                g = g * np.exp(-sonum * h * t)
            x += g * np.sin(2 * np.pi * f * h * t + h)
    return x


def _kick(sure: float = 0.35) -> np.ndarray:
    t = np.arange(int(sure * SR)) / SR
    f = 45 + 75 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def _gurultu_vurus(sure: float, sonum: float, tiz: bool, rng: np.random.Generator) -> np.ndarray:
    n = int(sure * SR)
    g = rng.standard_normal(n)
    if tiz:
        g = np.diff(g, prepend=0.0)                       # basit yüksek geçiren
    else:
        g = np.convolve(g, np.ones(8) / 8, mode="same")   # basit alçak geçiren
    return g * np.exp(-np.arange(n) / SR * sonum)


def _yerlestir(iz: np.ndarray, ses: np.ndarray, zaman: float, seviye: float) -> None:
    i = int(zaman * SR)
    if i >= len(iz):
        return
    j = min(len(iz), i + len(ses))
    iz[i:j] += seviye * ses[: j - i]


def _yanki(x: np.ndarray, rng: np.random.Generator, sure: float = 1.4, oran: float = 0.25) -> np.ndarray:
    """FFT ile kısa, yumuşak bir oda yankısı."""
    n = int(sure * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR * 4.5)
    ir[0] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    uzunluk = len(x) + n
    boyut = 1 << (uzunluk - 1).bit_length()
    islak = np.fft.irfft(np.fft.rfft(x, boyut) * np.fft.rfft(ir, boyut), boyut)[: len(x)]
    return x + oran * islak


# Ruh hali tarifleri: akorlar MIDI nota numaralarıyla.
TARIFLER = {
    "yeni_urun": {
        "bpm": 104,
        "akorlar": [[48, 55, 60, 64], [43, 50, 59, 62], [45, 52, 57, 60], [41, 48, 57, 60]],  # C G Am F
        "pad": 0.10, "arp": 0.22, "arp_bolum": 4, "kick": [0, 2], "hat": True, "fircalama": False, "piyano": 0.0,
    },
    "ipucu": {
        "bpm": 84,
        "akorlar": [[41, 52, 57, 60, 64], [40, 50, 55, 59, 62], [38, 50, 53, 57, 60], [36, 48, 52, 55, 59]],
        "pad": 0.05, "arp": 0.0, "arp_bolum": 2, "kick": [0], "hat": True, "fircalama": True, "piyano": 0.20,
    },
    "teknoloji_bilgisi": {
        "bpm": 72,
        "akorlar": [[45, 52, 57, 60, 64], [41, 48, 57, 60, 65], [36, 48, 55, 60, 64], [43, 50, 55, 59, 62]],
        "pad": 0.20, "arp": 0.10, "arp_bolum": 4, "kick": [], "hat": False, "fircalama": False, "piyano": 0.0,
    },
}


def _sentezle(tur: str, sure: float, tohum: int) -> np.ndarray:
    tarif = TARIFLER.get(tur, TARIFLER["teknoloji_bilgisi"])
    rng = np.random.default_rng(tohum)
    vurus = 60 / tarif["bpm"]
    olcu = 4 * vurus
    n = int((sure + 2) * SR)
    iz = np.zeros(n)
    akorlar = tarif["akorlar"]
    kaydirma = int(rng.integers(0, len(akorlar)))

    m = 0
    while m * olcu < sure + 1:
        akor = akorlar[(m + kaydirma) % len(akorlar)]
        bas = m * olcu
        # Bas: akorun kök notası, bir oktav aşağıda.
        _yerlestir(iz, _ton(_frekans(akor[0] - 12), olcu + 0.35, 3, 1.5) * _zarf(int((olcu + 0.35) * SR), 0.03, 0.45),
                   bas, 0.18)
        if tarif["pad"]:
            for nota in akor[1:]:
                pad = _ton(_frekans(nota), olcu + 0.6, 6, 1.2, detune=0.003) * _zarf(int((olcu + 0.6) * SR), 0.5, 0.8)
                _yerlestir(iz, pad, bas, tarif["pad"] / len(akor))
        if tarif["piyano"]:
            for k, nota in enumerate(akor[1:]):
                ep = _ton(_frekans(nota), 1.8, 4, 1.6, sonum=1.6) * _zarf(int(1.8 * SR), 0.005, 0.4)
                _yerlestir(iz, ep, bas + 0.012 * k, tarif["piyano"] / len(akor))
                _yerlestir(iz, ep, bas + 2 * vurus + 0.012 * k, 0.7 * tarif["piyano"] / len(akor))
        if tarif["arp"]:
            adim = vurus / (tarif["arp_bolum"] / 2)
            notalar = akor[1:] + [akor[2] + 12]
            for a in range(int(olcu / adim)):
                nota = notalar[a % len(notalar)] + 12
                pluck = _ton(_frekans(nota), 0.5, 5, 1.0, sonum=5.0) * _zarf(int(0.5 * SR), 0.003, 0.2)
                _yerlestir(iz, pluck, bas + a * adim, tarif["arp"] * (0.8 + 0.2 * rng.random()))
        for v in range(4):
            t = bas + v * vurus
            if v in tarif["kick"]:
                _yerlestir(iz, _kick(), t, 0.55)
            if tarif["hat"]:
                _yerlestir(iz, _gurultu_vurus(0.05, 70, True, rng), t + vurus / 2, 0.05)
            if tarif["fircalama"] and v == 2:
                _yerlestir(iz, _gurultu_vurus(0.25, 14, False, rng), t, 0.10)
        m += 1

    iz = _yanki(iz, rng)
    iz = iz[: int(sure * SR)]
    iz *= _zarf(len(iz), 1.0, 1.5)
    tepe = np.max(np.abs(iz)) or 1.0
    return iz / tepe * 0.8


def _kullanici_muzigi(tur: str) -> Path | None:
    for klasor in (ayarlar.KOK / "muzik" / tur, ayarlar.KOK / "muzik"):
        if klasor.is_dir():
            dosyalar = sorted(p for p in klasor.iterdir() if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
            if dosyalar:
                return random.choice(dosyalar)
    return None


def muzik_hazirla(tur: str, sure: float, hedef: Path, tohum: int | None = None) -> Path:
    """Video için arka plan müziği dosyasını döndürür (kullanıcı müziği varsa o, yoksa sentez)."""
    hazir = _kullanici_muzigi(tur)
    if hazir:
        print(f"    Müzik: {hazir.name}")
        return hazir
    ses = _sentezle(tur, sure, tohum if tohum is not None else random.randrange(1 << 30))
    veri = (np.clip(ses, -1, 1) * 32767).astype("<i2")
    with wave.open(str(hedef), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(veri.tobytes())
    print(f"    Müzik: {tur} ruh halinde sentezlendi")
    return hedef
