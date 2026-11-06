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
        })
    for entry in kok.iter(f"{_ATOM}entry"):  # Atom
        link = entry.find(f"{_ATOM}link")
        haberler.append({
            "baslik": _temizle(entry.findtext(f"{_ATOM}title"), 200),
            "ozet": _temizle(entry.findtext(f"{_ATOM}summary") or entry.findtext(f"{_ATOM}content")),
            "link": link.get("href", "") if link is not None else "",
            "tarih": _tarih(entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")),
            "kaynak": kaynak,
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
