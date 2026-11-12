"""Konuyla ilgili GERÇEK bir fotoğraf bulur ve yapay zekâ ile doğrular; uygun yoksa hiçbir şey döndürmez.

Kaynaklar (ücretsiz): Pixabay (anahtar gerekir, atıf zorunlu değil) ve Wikimedia Commons (atıf zorunlu;
açıklamaya eser sahibi ve lisans yazılır). Her aday Gemini'ye gösterilir: konudaki nesneyi/ekranı gerçekten
gösteriyor mu, gerçek fotoğraf mı, filigran/reklam/alakasız içerik var mı. Puanı yetersizse kullanılmaz.
"""
import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

import requests

from . import ayarlar, icerik

_BASLIK = {"User-Agent": "feriduntalak-icerik-ureticisi/1.0 (https://github.com/Feridun0135/instagram-otomatik)"}
ESIK = 7            # 10 üzerinden en az bu puan
EN_FAZLA_DENEME = 6 # en fazla bu kadar aday yapay zekâya gösterilir


def _pixabay(arama: str) -> list[dict]:
    if not ayarlar.PIXABAY_API_KEY:
        return []
    try:
        r = requests.get("https://pixabay.com/api/", timeout=30, params={
            "key": ayarlar.PIXABAY_API_KEY, "q": arama, "image_type": "photo", "per_page": 8,
            "safesearch": "true", "min_width": 900})
        r.raise_for_status()
    except requests.RequestException:
        return []
    return [{"url": h.get("largeImageURL") or h.get("webformatURL"), "kaynak": "Pixabay"}
            for h in r.json().get("hits", []) if h.get("largeImageURL") or h.get("webformatURL")]


def _temiz_html(metin: str) -> str:
    return re.sub(r"<[^>]+>", "", metin or "").strip()


def _wikimedia(arama: str) -> list[dict]:
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", headers=_BASLIK, timeout=30, params={
            "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
            "gsrsearch": f"{arama} filetype:bitmap", "gsrlimit": 8, "prop": "imageinfo",
            "iiprop": "url|extmetadata|size", "iiurlwidth": 1400})
        r.raise_for_status()
    except requests.RequestException:
        return []
    adaylar = []
    for sayfa in (r.json().get("query", {}).get("pages", {}) or {}).values():
        bilgi = (sayfa.get("imageinfo") or [{}])[0]
        meta = bilgi.get("extmetadata", {})
        lisans = _temiz_html(meta.get("LicenseShortName", {}).get("value", ""))
        if not bilgi.get("thumburl") or not lisans or "fair use" in lisans.lower():
            continue
        sahibi = _temiz_html(meta.get("Artist", {}).get("value", ""))[:60] or "bilinmiyor"
        adaylar.append({"url": bilgi["thumburl"], "kaynak": f"Wikimedia Commons, {sahibi}, {lisans}"})
    return adaylar


def _indir(url: str, hedef: Path) -> Path | None:
    try:
        r = requests.get(url, headers=_BASLIK, timeout=45)
        r.raise_for_status()
    except requests.RequestException:
        return None
    ham = hedef.with_suffix(".ham")
    ham.write_bytes(r.content)
    try:
        boyut = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height", "-of", "csv=p=0", str(ham)],
                               capture_output=True, text=True, check=True).stdout.strip().split(",")
        if min(int(boyut[0]), int(boyut[1])) < 500:
            return None
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ham), "-frames:v", "1",
                        "-vf", "scale='min(1600,iw)':-2", "-q:v", "3", str(hedef)], check=True)
        return hedef
    except (subprocess.CalledProcessError, ValueError, IndexError):
        return None
    finally:
        ham.unlink(missing_ok=True)


def _puanla(resim: Path, konu: str, nesne: str) -> tuple[int, str]:
    istem = (f"Bir teknoloji bilgilendirme videosu için fotoğraf seçiyoruz. Konu: \"{konu}\". "
             f"Fotoğrafta açıkça görünmesi gereken: \"{nesne}\".\n"
             "Bu görseli değerlendir ve yalnızca şu JSON'u döndür: "
             '{"uygun": true/false, "puan": 0-10, "neden": "kısa açıklama"}.\n'
             "Puanlama: konudaki nesneyi/ekranı net ve doğrudan gösteren gerçek bir fotoğraf veya gerçek ekran görüntüsü "
             "8-10; ilgili ama genel 5-7; ilgisiz 0-4. Çizim, illüstrasyon, yapay görünümlü görsel, filigran, reklam, "
             "üzerinde çok yazı olan görsel, yüzü öne çıkan insan portresi veya konuyla ilgisi zayıf görsel 'uygun': false olsun.")
    govde = {
        "contents": [{"parts": [
            {"text": istem},
            {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(resim.read_bytes()).decode()}},
        ]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.0},
    }
    try:
        cevap = json.loads(icerik._gemini_cagir(govde))
        puan = int(cevap.get("puan", 0)) if cevap.get("uygun") else 0
        return puan, str(cevap.get("neden", ""))[:120]
    except Exception as hata:  # değerlendirilemeyen görsel kullanılmaz
        return 0, f"değerlendirilemedi ({type(hata).__name__})"


def dogrulanmis_foto(konu: str, nesne: str, aramalar: list[str], klasor: Path) -> dict | None:
    """Konuya uygunluğu doğrulanmış en iyi fotoğrafı döndürür: {"yol", "kaynak", "puan"} veya None."""
    if not nesne or not aramalar:
        return None
    klasor.mkdir(parents=True, exist_ok=True)
    adaylar, gorulen = [], set()
    for arama in aramalar[:3]:
        for aday in _pixabay(arama)[:3] + _wikimedia(arama)[:3]:
            if aday["url"] not in gorulen:
                gorulen.add(aday["url"])
                adaylar.append(aday)
    # Kaynakları karıştırarak sırala: her aramadan önce en iyi eşleşmeler.
    en_iyi, denenen, ozetler = None, 0, set()
    for aday in adaylar:
        if denenen >= EN_FAZLA_DENEME:
            break
        yol = _indir(aday["url"], klasor / f"aday_{denenen + 1}.jpg")
        if not yol:
            continue
        ozet = hashlib.md5(yol.read_bytes()).hexdigest()
        if ozet in ozetler:
            continue
        ozetler.add(ozet)
        denenen += 1
        puan, neden = _puanla(yol, konu, nesne)
        print(f"    Aday {denenen}: puan {puan}/10 ({aday['kaynak'][:40]}) {neden}")
        if puan >= ESIK and (not en_iyi or puan > en_iyi["puan"]):
            en_iyi = {"yol": yol, "kaynak": aday["kaynak"], "puan": puan}
            if puan >= 9:
                break
    return en_iyi
