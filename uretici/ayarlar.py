"""Ayarları .env dosyasından ve ortam değişkenlerinden okur."""
import os
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "cikti"
VERI = KOK / "veri"


def _env_dosyasini_yukle() -> None:
    """Basit .env okuyucu (ek paket gerektirmez). Ortamda zaten olan değerleri ezmez."""
    yol = KOK / ".env"
    if not yol.exists():
        return
    for satir in yol.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#") or "=" not in satir:
            continue
        anahtar, deger = satir.split("=", 1)
        os.environ.setdefault(anahtar.strip(), deger.strip().strip('"').strip("'"))


_env_dosyasini_yukle()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
# Ana model yoğunsa sırayla denenecek yedek modeller (virgülle ayrılmış).
GEMINI_YEDEK_MODELLER = [
    m.strip()
    for m in os.getenv("GEMINI_YEDEK_MODELLER", "gemini-flash-lite-latest,gemini-2.5-flash,gemini-2.5-flash-lite").split(",")
    if m.strip()
]
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
TTS_SES = os.getenv("TTS_SES", "tr-TR-AhmetNeural")
# Konuşma hızı: "+0%" normal, "+15%" biraz hızlı, "+25%" hızlı.
TTS_HIZ = os.getenv("TTS_HIZ", "+15%")
ALTYAZI_FONT = os.getenv("ALTYAZI_FONT", "Arial" if os.name == "nt" else "DejaVu Sans")

VIDEO_GENISLIK = 1080
VIDEO_YUKSEKLIK = 1920
VIDEO_FPS = 30
# Her arka plan çekiminin ekranda kalma süresi (saniye) ve geçiş süresi.
CEKIM_SURESI = float(os.getenv("CEKIM_SURESI", "2.2"))
GECIS_SURESI = 0.3
KLIP_SAYISI = int(os.getenv("KLIP_SAYISI", "6"))
# Arka plan müziği: MUZIK=0 kapatır; MUZIK_SEVIYE müziğin ses seviyesi (konuşma sırasında ayrıca kısılır).
MUZIK = os.getenv("MUZIK", "1") != "0"
MUZIK_SEVIYE = float(os.getenv("MUZIK_SEVIYE", "0.14"))
