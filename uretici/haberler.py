"""Teknoloji haber sitelerinin RSS akışlarından son haberleri toplar (anahtar gerektirmez).

Yeni çıkan / duyurulan ürünleri analiz eden videolar için ham bilgi kaynağıdır.
Bir akış çalışmazsa atlanır; hiçbiri çalışmazsa boş liste döner.
"""
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

AKISLAR = {
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Engadget": "https://www.engadget.com/rss.xml",
    "TechCrunch": "https://techcrunch.com/feed/",
    "GSMArena": "https://www.gsmarena.com/rss-news-reviews.php3",
    "Webtekno": "https://www.webtekno.com/rss.xml",
    "ShiftDelete.Net": "https://shiftdelete.net/feed",
    "DonanımHaber": "https://www.donanimhaber.com/rss/tum/",
}

_BASLIK = {"User-Agent": "Mozilla/5.0 (compatible; gunluk-reels/1.0)"}
_ATOM = "{http://www.w3.org/2005/Atom}"
_MEDIA = "{http://search.yahoo.com/mrss/}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
_IMG_RE = re.compile(r"""<img[^>]+(?:data-src|data-original|src)=["']([^"']+)["']""", re.I)
_META_RE = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:og:image|twitter:image)(?::src)?["'][^>]*content=["']([^"']+)["']""", re.I)
_META_RE2 = re.compile(
    r"""<meta[^>]+content=["']([^"']+)["'][^>]*(?:property|name)=["'](?:og:image|twitter:image)["']""", re.I)
_RESIM_UZANTI = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
_ISTENMEYEN = re.compile(r"(logo|avatar|icon|sprite|favicon|emoji|placeholder|pixel|banner|/reklam/|/ads?/)", re.I)


def _temizle(metin: str, uzunluk: int = 600) -> str:
    metin = html.unescape(re.sub(r"<[^>]+>", " ", metin or ""))
    metin = re.sub(r"\s+", " ", metin).strip()
    return metin[:uzunluk]


def _tarih(metin: str | None) -> datetime | None:
    if not metin:
        return None
    try:
        t = parsedate_to_datetime(metin)
    except (TypeError, ValueError):
        try:
            t = datetime.fromisoformat(metin.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _item_gorselleri(item) -> list[str]:
    """RSS öğesindeki görsel adresleri: enclosure, media:content/thumbnail ve metindeki <img>."""
    adresler = []
    for e in item.findall("enclosure"):
        if (e.get("type") or "").startswith("image") and e.get("url"):
            adresler.append(e.get("url"))
    for etiket in (f"{_MEDIA}content", f"{_MEDIA}thumbnail"):
        for m in item.iter(etiket):
            if m.get("url") and (m.get("medium") in (None, "image") or _RESIM_UZANTI.search(m.get("url"))):
                adresler.append(m.get("url"))
    for metin in (item.findtext("description") or "", item.findtext(f"{_CONTENT}encoded") or ""):
        adresler += _IMG_RE.findall(metin)
    return adresler


def _ayristir(xml_metni: bytes, kaynak: str) -> list[dict]:
    kok = ET.fromstring(xml_metni)
    haberler = []
    for item in kok.iter("item"):  # RSS 2.0
        haberler.append({
            "baslik": _temizle(item.findtext("title"), 200),
            "ozet": _temizle(item.findtext("description")),
            "link": (item.findtext("link") or "").strip(),
            "tarih": _tarih(item.findtext("pubDate")),
            "kaynak": kaynak,
            "gorseller": _item_gorselleri(item),
        })
    for entry in kok.iter(f"{_ATOM}entry"):  # Atom
        link = entry.find(f"{_ATOM}link")
        haberler.append({
            "baslik": _temizle(entry.findtext(f"{_ATOM}title"), 200),
            "ozet": _temizle(entry.findtext(f"{_ATOM}summary") or entry.findtext(f"{_ATOM}content")),
            "link": link.get("href", "") if link is not None else "",
            "tarih": _tarih(entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")),
            "kaynak": kaynak,
            "gorseller": _IMG_RE.findall(entry.findtext(f"{_ATOM}content") or ""),
        })
    return [h for h in haberler if h["baslik"]]


def son_haberler(gun: int = 4, en_fazla: int = 40) -> list[dict]:
    """Son `gun` gündeki haberleri, en yeniden eskiye sıralı döndürür."""
    sinir = datetime.now(timezone.utc) - timedelta(days=gun)
    tum: list[dict] = []
    for kaynak, url in AKISLAR.items():
        try:
            yanit = requests.get(url, headers=_BASLIK, timeout=30)
            yanit.raise_for_status()
            haberler = _ayristir(yanit.content, kaynak)
            print(f"    Haber kaynağı {kaynak}: {len(haberler)} haber")
            tum.extend(haberler)
        except (requests.RequestException, ET.ParseError) as hata:
            print(f"    Uyarı: {kaynak} okunamadı ({type(hata).__name__})")

    gorulen: set[str] = set()
    sonuc = []
    for h in sorted(tum, key=lambda x: x["tarih"] or sinir, reverse=True):
        anahtar = h["baslik"].lower()
        if anahtar in gorulen or (h["tarih"] and h["tarih"] < sinir):
            continue
        gorulen.add(anahtar)
        sonuc.append(h)
    return sonuc[:en_fazla]


# ---------- seçilen haberin ürün görselleri ----------

_IMG_ETIKETI = re.compile(r"<img\b[^>]*>", re.I)
_ALT_RE = re.compile(r"""\b(?:alt|title)=["']([^"']*)["']""", re.I)
# Haber metninin bittiği yerler: buradan sonraki görseller başka haberlere, yazara, reklama aittir.
_GOVDE_SONU = re.compile(
    r"</article>|<aside\b|<footer\b|<section[^>]*(?:related|ilgili|benzer|comment|yorum|recommend|onerilen)"
    r"|<div[^>]*class=[\"'][^\"']*(?:related|ilgili|benzer|comment|yorum|recommend|onerilen|author|yazar|share|tags)",
    re.I)
_GENEL_KELIMELER = set("""yeni tanıtıldı tanitildi duyuruldu işte iste özellikleri ozellikleri fiyatı fiyati fiyat çıktı cikti
geliyor geldi resmi resmen satışa satisa sunuldu türkiye turkiye ile için icin ve the new with and for from announced
launch launches review hands price specs features its are has now officially analiz incelemesi inceleme""".split())


def _anahtar_kelimeler(*metinler: str) -> set[str]:
    """Ürünü tanımlayan kelimeler (ör. "AirPods 4 tanıtıldı" -> {"airpods"})."""
    kelimeler = set()
    for metin in metinler:
        for k in re.findall(r"[^\W_]+", _kucult(metin)):
            if len(k) >= 3 and not k.isdigit() and k not in _GENEL_KELIMELER:
                kelimeler.add(k)
    return kelimeler


def _ilgili_mi(etiket: str, adres: str, anahtarlar: set[str]) -> bool:
    """Sayfa içi görselin dosya adı veya açıklaması ürünle ilgili mi?"""
    if not anahtarlar:
        return False
    alt = " ".join(_ALT_RE.findall(etiket)).lower()
    dosya = adres.rsplit("/", 1)[-1].lower()
    return any(k in alt or k in dosya for k in anahtarlar)


_VIDEO_META = re.compile(
    r"""<meta[^>]+(?:property|name)=["'](?:og:video(?::url|:secure_url)?|twitter:player:stream)["'][^>]*content=["']([^"']+)["']""",
    re.I)
_VIDEO_ETIKETI = re.compile(r"""<(?:video|source)\b[^>]*\bsrc=["']([^"']+)["']""", re.I)
_VIDEO_UZANTI = re.compile(r"\.(mp4|webm|mov|m4v)(\?|$)", re.I)
# Başka platformların videoları kullanılmaz (kural: YouTube vb. indirilmez).
_VIDEO_PLATFORMLARI = ("youtube.com", "youtu.be", "youtube-nocookie.com", "googlevideo.com", "vimeo.com",
                       "vimeocdn.com", "dailymotion.com", "facebook.com", "fbcdn.net", "twitter.com", "twimg.com",
                       "x.com", "tiktok.com", "tiktokcdn.com", "instagram.com", "cdninstagram.com")


_VARYANTLAR = {"pro", "max", "ultra", "plus", "mini", "lite", "fe", "air", "se", "edge", "fold", "flip", "neo"}


def _kucult(metin: str) -> str:
    """Türkçeye uygun küçük harf (İ -> i, I -> ı); str.lower() "İ" harfini bozar."""
    return (metin or "").replace("İ", "i").replace("I", "ı").lower()


def _urun_kelimeleri(metin: str) -> set[str]:
    return {k for k in re.findall(r"[^\W_]+", _kucult(metin))
            if (len(k) >= 2 or k.isdigit()) and k not in _GENEL_KELIMELER}


def ilgili_haberler(secilen: dict, haberler: list[dict], en_fazla: int = 4) -> list[dict]:
    """Aynı ürünü anlatan diğer haberler (başka sitelerden daha fazla ürün görseli için).

    Karışmaması için: başlıktaki model numaraları (rakam içeren kelimeler, ör. "4", "s26") birebir geçmeli,
    sürüm kelimeleri (Pro, Ultra, Max, Plus...) aynı olmalı ve en az 2 ürün kelimesi ortak olmalı.
    Böylece "AirPods 4" haberine "AirPods Pro 3", "Galaxy S26 Ultra" haberine "Galaxy S26" karışmaz.
    """
    hedef = _urun_kelimeleri(secilen.get("baslik", ""))
    modeller = {k for k in hedef if any(c.isdigit() for c in k)}
    varyantlar = hedef & _VARYANTLAR
    if not hedef:
        return []
    sonuc = []
    for h in haberler:
        if h.get("link") == secilen.get("link"):
            continue
        aday = _urun_kelimeleri(h.get("baslik", ""))
        ortak = hedef & aday
        if modeller:
            uygun = modeller <= aday and (aday & _VARYANTLAR) == varyantlar and len(ortak) >= 2
        else:
            uygun = (aday & _VARYANTLAR) == varyantlar and len(ortak) >= max(2, -(-len(hedef) * 3 // 4))
        if uygun:
            sonuc.append({"link": h["link"], "gorseller": h.get("gorseller", []), "baslik": h.get("baslik", "")})
        if len(sonuc) >= en_fazla:
            break
    return sonuc


def _platform_videosu_mu(adres: str) -> bool:
    from urllib.parse import urlparse
    host = (urlparse(adres).hostname or "").lower()
    return any(host == a or host.endswith("." + a) for a in _VIDEO_PLATFORMLARI)


def _adres_duzelt(a: str) -> str:
    a = html.unescape(a.strip())
    return "https:" + a if a.startswith("//") else a


def _sayfa_medyasi(haber: dict) -> tuple[list[str], list[str]]:
    """Haberin ürün görseli ve ürün videosu adresleri, güvenilirlik sırasıyla.

    Görseller: 1) sayfanın ana görseli (og:image) ve RSS'teki haber görseli her zaman alınır;
    2) haber metnindeki diğer görseller yalnızca metin bitmeden önce geçiyorsa VE dosya adı ya da açıklaması
    ürün adını içeriyorsa alınır. "İlgili haberler", yazar, reklam alanlarındaki görseller alınmaz.
    Videolar: sayfanın kendi video dosyaları (og:video, metin içindeki <video>); YouTube vb. platformlar alınmaz.
    """
    gorseller: list[str] = []
    videolar: list[str] = []
    anahtarlar = _anahtar_kelimeler(haber.get("baslik", ""), haber.get("konu", ""))
    sayfa = ""
    try:
        sayfa = requests.get(haber["link"], headers=_BASLIK, timeout=30).text
        gorseller += _META_RE.findall(sayfa) + _META_RE2.findall(sayfa)
        videolar += _VIDEO_META.findall(sayfa)
    except requests.RequestException as hata:
        print(f"    Uyarı: haber sayfası okunamadı ({type(hata).__name__})")
    gorseller += haber.get("gorseller", [])[:1]
    if sayfa:
        govde = sayfa.split("<article", 1)[1] if "<article" in sayfa else sayfa
        govde = _GOVDE_SONU.split(govde, 1)[0]
        for etiket in _IMG_ETIKETI.findall(govde):
            bulunan = _IMG_RE.findall(etiket)
            if bulunan and _ilgili_mi(etiket, bulunan[0], anahtarlar):
                gorseller.append(bulunan[0])
        videolar += _VIDEO_ETIKETI.findall(govde)

    def ayikla(adresler, uygun):
        sonuc, gorulen = [], set()
        for a in map(_adres_duzelt, adresler):
            if a.startswith("http") and a not in gorulen and uygun(a):
                gorulen.add(a)
                sonuc.append(a)
        return sonuc

    return (ayikla(gorseller, lambda a: not _ISTENMEYEN.search(a)),
            ayikla(videolar, lambda a: _VIDEO_UZANTI.search(a) and not _platform_videosu_mu(a)
                   and not _ISTENMEYEN.search(a)))


def _gorsel_adresleri(haber: dict) -> list[str]:
    return _sayfa_medyasi(haber)[0]


def urun_medyasini_indir(haber: dict, klasor, ilgili: list[dict] | None = None, en_fazla_gorsel: int = 8,
                         en_fazla_video: int = 3) -> tuple[list, list]:
    """Seçilen haberden ve aynı ürünü anlatan diğer haberlerden ürün görsellerini ve videolarını indirir.

    Videolarda insan yüzü görünüyorsa video kullanılmaz (uretici/yuz.py).
    """
    from pathlib import Path

    klasor = Path(klasor)
    gorsel_adresleri, video_adresleri = [], []
    for h in [haber] + list(ilgili or []):
        g, v = _sayfa_medyasi(h)
        gorsel_adresleri += [a for a in g if a not in gorsel_adresleri]
        video_adresleri += [a for a in v if a not in video_adresleri]
    gorseller = _gorselleri_indir(gorsel_adresleri, klasor, en_fazla_gorsel)
    videolar = _videolari_indir(video_adresleri, klasor / "videolar", en_fazla_video)
    print(f"    Ürün görseli: {len(gorseller)} adet, ürün videosu: {len(videolar)} adet")
    return gorseller, videolar


def _videolari_indir(adresler: list[str], klasor, en_fazla: int, en_buyuk_mb: int = 60) -> list:
    import subprocess
    from pathlib import Path

    from . import yuz

    klasor = Path(klasor)
    if not adresler:
        return []
    if not yuz.hazir_mi():
        print("    Uyarı: yüz denetimi yapılamıyor (OpenCV yok); ürün videoları kullanılmayacak.")
        return []
    klasor.mkdir(parents=True, exist_ok=True)
    sonuc = []
    for adres in adresler[:10]:
        if len(sonuc) >= en_fazla:
            break
        hedef = klasor / f"urun_video_{len(sonuc) + 1}.mp4"
        try:
            with requests.get(adres, headers=_BASLIK, timeout=60, stream=True) as r:
                r.raise_for_status()
                if not r.headers.get("Content-Type", "video").split(";")[0].startswith(("video", "application/octet")):
                    continue
                boyut = 0
                with open(hedef, "wb") as f:
                    for parca in r.iter_content(1 << 16):
                        boyut += len(parca)
                        if boyut > en_buyuk_mb << 20:
                            raise ValueError("çok büyük")
                        f.write(parca)
        except (requests.RequestException, ValueError):
            hedef.unlink(missing_ok=True)
            continue
        try:
            sure = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "default=nw=1:nk=1", str(hedef)], capture_output=True, text=True,
                                        check=True).stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            sure = 0.0
        if sure < 3:
            hedef.unlink(missing_ok=True)
            continue
        if yuz.videoda_yuz_var(hedef, sure):
            print(f"    Ürün videosu atlandı: insan yüzü görünüyor ({adres.rsplit('/', 1)[-1][:60]})")
            hedef.unlink(missing_ok=True)
            continue
        sonuc.append(hedef)
    return sonuc


def urun_gorsellerini_indir(haber: dict, klasor, en_fazla: int = 8, en_kucuk: int = 600) -> list:
    """(Geriye dönük uyumluluk) Yalnızca seçilen haberin ürün görsellerini indirir."""
    from pathlib import Path
    return _gorselleri_indir(_gorsel_adresleri(haber), Path(klasor), en_fazla, en_kucuk)


def _gorselleri_indir(adresler: list[str], klasor, en_fazla: int = 8, en_kucuk: int = 600) -> list:
    """Görselleri indirir; küçük/bozuk ve aynı görselleri eler, JPEG'e çevirir."""
    import hashlib
    import json as _json
    import subprocess
    from pathlib import Path

    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    indirilen, ozetler = [], set()
    for adres in adresler[:40]:
        if len(indirilen) >= en_fazla:
            break
        try:
            r = requests.get(adres, headers=_BASLIK, timeout=30)
            r.raise_for_status()
        except requests.RequestException:
            continue
        if not r.headers.get("Content-Type", "image").startswith("image") or len(r.content) < 15_000:
            continue
        ozet = hashlib.md5(r.content).hexdigest()
        if ozet in ozetler:
            continue
        hedef = klasor / f"urun_{len(indirilen) + 1}.img"
        hedef.write_bytes(r.content)
        try:
            bilgi = _json.loads(subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                 "-of", "json", str(hedef)], capture_output=True, text=True, check=True).stdout)["streams"][0]
        except (subprocess.CalledProcessError, KeyError, IndexError, ValueError):
            hedef.unlink(missing_ok=True)
            continue
        if min(bilgi.get("width", 0), bilgi.get("height", 0)) < en_kucuk * 0.6 or bilgi.get("width", 0) < en_kucuk:
            hedef.unlink(missing_ok=True)
            continue
        # Her biçimi (webp, png...) FFmpeg'in döngüyle okuyabileceği JPEG'e çevir.
        jpg = hedef.with_suffix(".jpg")
        donustur = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(hedef), "-frames:v", "1",
                                   "-q:v", "2", str(jpg)], capture_output=True)
        hedef.unlink(missing_ok=True)
        if donustur.returncode != 0 or not jpg.exists():
            continue
        ozetler.add(ozet)
        indirilen.append(jpg)
    return indirilen
