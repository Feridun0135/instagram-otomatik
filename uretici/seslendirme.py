"""Metni edge-tts ile Türkçe seslendirir ve altyazı zamanlamalarını çıkarır."""
import asyncio
from pathlib import Path

from . import ayarlar

# edge-tts zamanları 100 nanosaniye birimiyle verir.
_BIRIM = 10_000_000


async def _seslendir(metin: str, ses_yolu: Path) -> list[dict]:
    import edge_tts

    try:
        iletisim = edge_tts.Communicate(metin, ayarlar.TTS_SES, rate=ayarlar.TTS_HIZ, boundary="WordBoundary")
    except TypeError:  # eski sürümlerde boundary parametresi yok
        iletisim = edge_tts.Communicate(metin, ayarlar.TTS_SES, rate=ayarlar.TTS_HIZ)

    bolumler = []
    with open(ses_yolu, "wb") as f:
        async for parca in iletisim.stream():
            if parca["type"] == "audio":
                f.write(parca["data"])
            elif parca["type"] in ("WordBoundary", "SentenceBoundary"):
                bolumler.append({
                    "baslangic": parca["offset"] / _BIRIM,
                    "bitis": (parca["offset"] + parca["duration"]) / _BIRIM,
                    "metin": parca["text"],
                })
    return bolumler


def seslendir(metin: str, ses_yolu: Path) -> list[dict]:
    """Ses dosyasını yazar; kelime veya cümle zamanlamalarını döndürür."""
    return asyncio.run(_seslendir(metin, ses_yolu))


def kelimelere_bol(bolumler: list[dict]) -> list[dict]:
    """Zamanlamaları kelime kelime listeye çevirir.

    Cümle zamanlaması geldiyse cümle süresi kelimelere uzunluklarına göre orantılı dağıtılır.
    """
    kelimeler = []
    for b in bolumler:
        parcalar = b["metin"].split()
        if not parcalar:
            continue
        if len(parcalar) == 1:
            kelimeler.append(b)
            continue
        toplam_harf = sum(len(k) for k in parcalar)
        sure = b["bitis"] - b["baslangic"]
        t = b["baslangic"]
        for k in parcalar:
            pay = sure * len(k) / toplam_harf
            kelimeler.append({"baslangic": t, "bitis": t + pay, "metin": k})
            t += pay
    return kelimeler


def gruplara_ayir(kelimeler: list[dict], en_fazla: int = 3, duraklama: float = 0.35) -> list[list[dict]]:
    """Kelimeleri ekranda birlikte görünecek kısa gruplara ayırır (noktalama veya duraklamada böler)."""
    gruplar: list[list[dict]] = []
    grup: list[dict] = []
    for i, k in enumerate(kelimeler):
        grup.append(k)
        sonraki = kelimeler[i + 1] if i + 1 < len(kelimeler) else None
        if (len(grup) >= en_fazla or k["metin"][-1:] in ".!?,;:"
                or (sonraki and sonraki["baslangic"] - k["bitis"] > duraklama)):
            gruplar.append(grup)
            grup = []
    if grup:
        gruplar.append(grup)
    return gruplar
