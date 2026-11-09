"""Ürün videolarında insan yüzü olup olmadığını denetler (OpenCV, ücretsiz ve çevrimdışı).

Videodan saniyede bir kare alınır; herhangi bir karede yüz bulunursa video kullanılmaz.
OpenCV kurulu değilse hazir_mi() False döner ve ürün videoları hiç kullanılmaz (güvenli taraf).
"""
import subprocess
import tempfile
from pathlib import Path

_SINIFLANDIRICILAR = ("haarcascade_frontalface_default.xml", "haarcascade_profileface.xml")


def _siniflandiricilar():
    import cv2

    sonuc = []
    for ad in _SINIFLANDIRICILAR:
        s = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / ad))
        if not s.empty():
            sonuc.append(s)
    return sonuc


def hazir_mi() -> bool:
    try:
        return bool(_siniflandiricilar())
    except Exception:  # cv2 yok veya sınıflandırıcı dosyaları eksik
        return False


def karede_yuz_var(resim_yolu: Path, siniflandiricilar=None) -> bool:
    import cv2

    kare = cv2.imread(str(resim_yolu))
    if kare is None:
        return False
    gri = cv2.equalizeHist(cv2.cvtColor(kare, cv2.COLOR_BGR2GRAY))
    en_kucuk = max(40, int(min(gri.shape[:2]) * 0.06))   # çok küçük/uzaktaki yanlış eşleşmeleri sayma
    for s in siniflandiricilar or _siniflandiricilar():
        for g in (gri, cv2.flip(gri, 1)):                  # profil sınıflandırıcısı tek yöne bakar
            if len(s.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(en_kucuk, en_kucuk))):
                return True
    return False


def videoda_yuz_var(video: Path, sure: float) -> bool:
    """Videodan saniyede bir kare alıp yüz arar. Kare çıkarılamazsa da güvenli tarafta kalıp True döner."""
    siniflandiricilar = _siniflandiricilar()
    with tempfile.TemporaryDirectory() as gecici:
        cikti = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", "fps=1,scale=640:-2",
                                "-frames:v", str(int(min(sure, 90)) + 1), str(Path(gecici) / "k%03d.jpg")],
                               capture_output=True)
        kareler = sorted(Path(gecici).glob("k*.jpg"))
        if cikti.returncode != 0 or not kareler:
            return True
        return any(karede_yuz_var(k, siniflandiricilar) for k in kareler)
