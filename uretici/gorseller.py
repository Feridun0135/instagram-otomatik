"""Telifsiz stok videolar indirir: önce Pexels, Pexels anahtarı yoksa Pixabay."""
from pathlib import Path

import requests

from . import ayarlar


def _indir(url: str, hedef: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(hedef, "wb") as f:
            for blok in r.iter_content(1 << 20):
                f.write(blok)


# ---------- Pexels ----------

def _pexels_adaylari(arama: str) -> list[dict]:
    yanit = requests.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": ayarlar.PEXELS_API_KEY},
        params={"query": arama, "orientation": "portrait", "per_page": 10},
        timeout=60,
    )
    if yanit.status_code != 200:
        print(f"Uyarı: Pexels araması başarısız ({arama}): {yanit.status_code}")
        return []
    adaylar = []
    for video in yanit.json().get("videos", []):
        dosyalar = [f for f in video.get("video_files", [])
                    if f.get("width") and f.get("height") and f["height"] > f["width"] and f["height"] >= 1280]
        if dosyalar:
            en_iyi = min(dosyalar, key=lambda f: abs(f["height"] - ayarlar.VIDEO_YUKSEKLIK))
            adaylar.append({"id": f"pexels-{video['id']}", "url": en_iyi["link"]})
    return adaylar


# ---------- Pixabay ----------

def _pixabay_adaylari(arama: str) -> list[dict]:
    yanit = requests.get(
        "https://pixabay.com/api/videos/",
        params={"key": ayarlar.PIXABAY_API_KEY, "q": arama, "per_page": 20, "safesearch": "true"},
        timeout=60,
    )
    if yanit.status_code != 200:
        print(f"Uyarı: Pixabay araması başarısız ({arama}): {yanit.status_code}")
        return []
    adaylar = []
    for video in yanit.json().get("hits", []):
        boyutlar = [v for v in (video.get("videos") or {}).values() if v and v.get("url") and v.get("height")]
        if not boyutlar:
            continue
        dikey = any(v["height"] > v["width"] for v in boyutlar)
        # 1920 yüksekliğe en yakın, en az 720 piksel olan dosyayı seç.
        uygunlar = [v for v in boyutlar if v["height"] >= 720] or boyutlar
        en_iyi = min(uygunlar, key=lambda v: abs(max(v["height"], v["width"]) - ayarlar.VIDEO_YUKSEKLIK))
        adaylar.append({"id": f"pixabay-{video['id']}", "url": en_iyi["url"], "dikey": dikey})
    # Dikey videolar öne (yatay videolar ortadan kırpılır, daha az görüntü kalır).
    adaylar.sort(key=lambda a: not a["dikey"])
    return adaylar


def videolari_indir(aramalar: list[str], klasor: Path, adet: int = 4) -> list[Path]:
    """Arama ifadelerinden toplam `adet` kadar farklı video indirir. Anahtar yoksa boş liste döner."""
    if ayarlar.PEXELS_API_KEY:
        kaynak = _pexels_adaylari
    elif ayarlar.PIXABAY_API_KEY:
        kaynak = _pixabay_adaylari
    else:
        print("Uyarı: PEXELS_API_KEY veya PIXABAY_API_KEY yok; düz renkli arka plan kullanılacak.")
        return []

    klasor.mkdir(parents=True, exist_ok=True)
    indirilen: list[Path] = []
    gorulen: set[str] = set()

    for arama in aramalar:
        if len(indirilen) >= adet:
            break
        bu_aramadan = 0
        for aday in kaynak(arama):
            if len(indirilen) >= adet or bu_aramadan >= 2:  # her aramadan en fazla 2 klip, çeşitlilik için
                break
            if aday["id"] in gorulen:
                continue
            gorulen.add(aday["id"])
            hedef = klasor / f"klip_{len(indirilen) + 1}.mp4"
            try:
                _indir(aday["url"], hedef)
            except requests.RequestException as hata:
                print(f"Uyarı: klip indirilemedi: {hata}")
                continue
            indirilen.append(hedef)
            bu_aramadan += 1
    return indirilen
