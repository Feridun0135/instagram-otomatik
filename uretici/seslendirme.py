"""Metni edge-tts ile Türkçe seslendirir ve altyazı zamanlamalarını çıkarır."""
import asyncio
import re
from pathlib import Path

from . import ayarlar

# edge-tts zamanları 100 nanosaniye birimiyle verir.
_BIRIM = 10_000_000


def noktalamayi_duzelt(metin: str) -> str:
    """Seslendirmede anlamsız duraklamaya yol açan işaretleri temizler, noktalamayı düzenler.

    Tire ve üç nokta virgül/noktaya çevrilir; parantez, tırnak ve emoji kaldırılır; çift işaretler sadeleşir;
    son cümle noktalamasız kaldıysa nokta eklenir.
    """
    m = metin.strip()
    m = re.sub(r"[\u2600-\u27BF\U0001F000-\U0001FAFF\uFE0F\u200d]", "", m)       # emoji
    m = re.sub(r"[()\[\]{}\"“”«»*_#]", "", m)
    m = re.sub(r"\s*(\.{3}|…)\s*(?=\S)", ". ", m)                                 # üç nokta -> cümle sonu
    m = re.sub(r"(\.{3}|…)\s*$", ".", m)
    m = re.sub(r"\s+[-–—]+\s+|[–—]", ", ", m)                                       # tire -> kısa es
    m = re.sub(r"\s+([,.!?;:])", r"\1", m)                                          # işaretten önce boşluk olmaz
    m = re.sub(r",\s*([.!?])", r"\1", m)                                            # ", ." -> "."
    m = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", m)                                   # ",," -> ","
    m = re.sub(r"([.!?])\1+", r"\1", m)                                             # "!!" -> "!"
    m = re.sub(r"([,.!?;:])(?=[^\s\d,.!?;:])", r"\1 ", m)                          # işaretten sonra boşluk
    m = re.sub(r"\s{2,}", " ", m).strip(" ,;:")
    if m and m[-1] not in ".!?":
        m += "."
    return m


_UNLULER = "aeıioöuüAEIİOÖUÜ"
_DAR = {"a": "ı", "ı": "ı", "e": "i", "i": "i", "o": "u", "u": "u", "ö": "ü", "ü": "ü"}
_KUCUK = str.maketrans("AEIİOÖUÜ", "aeıioöuü")
# kök + (y) + acak/ecek/acağ/eceğ + ekler  (ör. yap|acağ|ım, söyle|y|ecek, ol|acak|sın)
_GELECEK = re.compile(r"^(?P<kok>[^\W\d_]*?)(?P<y>y?)(?P<un>[aeAE])(?P<c>[cC])(?P<un2>[aeAE])(?P<k>[kğKĞ])(?P<ek>[^\W\d_]*)$")


def _gelecek_zamani_konus(kelime: str) -> str:
    """yapacağım -> yapıcam, gideceğim -> gidicem, olacak -> olucak, söyleyeceğim -> söylicem, başlayacak -> başlıcak."""
    m = _GELECEK.match(kelime)
    if not m:
        return kelime
    kok, y, ek = m["kok"], m["y"], m["ek"]
    unluler = [h for h in kok if h in _UNLULER]
    if not unluler or len(kok) < 2:
        return kelime                       # "bacak", "acak" gibi fiil olmayan kelimeler
    son_unlu = unluler[-1].translate(_KUCUK)
    if y:                                   # ünlüyle biten kök: başla-y-acak -> başlı-cak
        if kok[-1] not in _UNLULER:
            return kelime
        govde = kok[:-1] + _DAR[kok[-1].translate(_KUCUK)]
    else:                                   # ünsüzle biten kök: yap-acak -> yapı-cak
        if kok[-1] in _UNLULER:
            return kelime
        govde = kok + _DAR[son_unlu]
    kuyruk = (m["c"] + m["un2"] + m["k"] + ek).lower()
    # -acağım -> -cam, -acağız -> -caz (ve kalın/ince karşılıkları)
    for uzun, kisa in (("cağım", "cam"), ("ceğim", "cem"), ("cağız", "caz"), ("ceğiz", "cez")):
        if kuyruk.startswith(uzun):
            kuyruk = kisa + kuyruk[len(uzun):]
            break
    return govde + kuyruk


def konusma_diline_cevir(metin: str) -> str:
    """Seslendirme metnini konuşulduğu gibi yazar (yazım kuralına göre değil).

    Gelecek zaman: yapacağım -> yapıcam, gideceğim -> gidicem, olacak -> olucak.
    değil -> diil (değilim -> diilim, değildi -> diildi).
    Kelime sayısı değişmez; altyazı eşleşmesi bozulmaz.
    """
    def cevir(m: re.Match) -> str:
        k = m.group(0)
        if k[:5] in ("değil", "Değil", "DEĞİL"):
            return ("D" if k[0] == "D" else "d") + "iil" + k[5:].lower()
        return _gelecek_zamani_konus(k)
    return re.sub(r"[^\W\d_]+", cevir, metin)


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
    """Ses dosyasını yazar; kelime veya cümle zamanlamalarını döndürür.

    SES_MOTORU=klon ise kullanıcının kendi sesi kullanılır; bir sorun olursa o gün hazır sese geri dönülür,
    böylece paylaşım aksamaz.
    """
    if ayarlar.SES_MOTORU == "klon":
        from . import klon_ses
        if klon_ses.hazir_mi():
            try:
                return klon_ses.seslendir(metin, ses_yolu)
            except Exception as hata:  # model indirilemedi, bellek yetmedi vb.
                print(f"    Uyarı: kendi sesinle seslendirme başarısız ({type(hata).__name__}: {hata}); hazır ses kullanılıyor.")
        else:
            print("    Uyarı: şifreli ses örneği veya SES_SIFRESI yok; hazır ses kullanılıyor.")
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


def _cumleler(metin: str) -> list[list[str]]:
    import re
    return [c.split() for c in re.split(r"(?<=[.!?…])\s+", metin.strip()) if c.split()]


def yaziya_esle(kelimeler: list[dict], konusma_metni: str, yazi_metni: str) -> list[dict]:
    """Konuşma diliyle seslendirilmiş kelimelerin zamanlamasını düzgün yazımlı metne aktarır (altyazı için).

    Cümle sayıları tutarsa her cümlenin süresi, yazılı cümlenin kelimelerine uzunluklarına göre dağıtılır.
    Tutmazsa konuşma dilindeki kelimeler olduğu gibi kullanılır.
    """
    konusma, yazi = _cumleler(konusma_metni), _cumleler(yazi_metni)
    if not kelimeler or len(konusma) != len(yazi) or sum(len(c) for c in konusma) != len(kelimeler):
        return kelimeler
    sonuc, i = [], 0
    for k_cumle, y_cumle in zip(konusma, yazi):
        parca = kelimeler[i:i + len(k_cumle)]
        i += len(k_cumle)
        bas, bit = parca[0]["baslangic"], parca[-1]["bitis"]
        toplam_harf = sum(len(w) for w in y_cumle) or 1
        t = bas
        for w in y_cumle:
            pay = (bit - bas) * len(w) / toplam_harf
            sonuc.append({"baslangic": t, "bitis": t + pay, "metin": w})
            t += pay
    return sonuc
