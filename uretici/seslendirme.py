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


_BIRLER = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_ONLAR = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]
_BUYUKLER = ["", "bin", "milyon", "milyar", "trilyon"]


def _uc_basamak(n: int) -> list[str]:
    y, o, b = n // 100, n // 10 % 10, n % 10
    sozler = []
    if y:
        sozler += ([] if y == 1 else [_BIRLER[y]]) + ["yüz"]
    if o:
        sozler.append(_ONLAR[o])
    if b:
        sozler.append(_BIRLER[b])
    return sozler


def sayiyi_yaziya(n: int) -> str:
    """256 -> "iki yüz elli altı", 1500 -> "bin beş yüz", 2026 -> "iki bin yirmi altı"."""
    if n == 0:
        return "sıfır"
    sozler, i = [], 0
    while n and i < len(_BUYUKLER):
        grup = n % 1000
        if grup:
            parca = _uc_basamak(grup)
            if i == 1 and grup == 1:
                parca = []                       # "bir bin" değil "bin"
            sozler = parca + ([_BUYUKLER[i]] if i else []) + sozler
        n //= 1000
        i += 1
    return " ".join(sozler)


def _ondalik_yaziya(tam: str, kesir: str) -> str:
    """6,1 -> "altı virgül bir"; 1,05 -> "bir virgül sıfır beş"; 2,25 -> "iki virgül yirmi beş"."""
    sifirlar = len(kesir) - len(kesir.lstrip("0"))
    kalan = kesir.lstrip("0")
    return " ".join([sayiyi_yaziya(int(tam)), "virgül"] + ["sıfır"] * sifirlar
                    + ([sayiyi_yaziya(int(kalan))] if kalan else []))


_SAYI = re.compile(
    r"(?P<yuzde>%\s?)?"
    r"(?P<sayi>\d{1,3}(?:\.\d{3})+|\d+)(?:(?P<ayirac>[.,])(?P<kesir>\d+))?"
    r"(?P<yuzde2>\s?%)?"
    r"(?:'(?P<ek>[^\W\d_]+))?")


def sayilari_oku(metin: str) -> str:
    """Seslendirme metnindeki sayıları Türkçe okunuşlarıyla yazar.

    256 -> iki yüz elli altı, 1.500 -> bin beş yüz, 6,1 -> altı virgül bir, %20 -> yüzde yirmi,
    2026'da -> iki bin yirmi altıda, 18:47 -> on sekiz kırk yedi, S25 -> S yirmi beş.
    Bir sayıdan sonra kesme işaretiyle gelen ek okunuşa bitişik yazılır.
    """
    def cevir(m: re.Match) -> str:
        sayi = m["sayi"].replace(".", "")
        if m["kesir"] is not None and not (m["ayirac"] == "." and len(m["kesir"]) == 3 and "." not in m["sayi"]):
            soz = _ondalik_yaziya(sayi, m["kesir"])
        elif m["kesir"] is not None:               # "1.500" -> binlik ayıracı
            soz = sayiyi_yaziya(int(sayi + m["kesir"]))
        else:
            soz = sayiyi_yaziya(int(sayi))
        if m["yuzde"] or m["yuzde2"]:
            soz = "yüzde " + soz
        on = " " if m.start() > 0 and (metin[m.start() - 1].isalpha()) else ""   # S25 -> S yirmi beş
        return on + soz + (m["ek"] or "")

    metin = re.sub(r"(\d{1,2}):(\d{2})\b", r"\1 \2", metin)       # saat: 18:47 -> 18 47
    return _SAYI.sub(cevir, metin)


# İngilizce kelime ve markaların İngilizce okunuşu, Türkçe harflerle (Türkçe ses modeli böylece İngilizce aksanla okur).
# Türkçede zaten yazıldığı gibi okunanlar (Samsung, Android, Instagram, Tesla...) listede yoktur.
INGILIZCE_OKUNUS = {
    "iphone": "ayfon", "ipad": "aypad", "airpods": "erpods", "airtag": "ertag", "macbook": "mekbuk",
    "imac": "aymek", "mac": "mek", "apple": "epıl", "watch": "voç", "vision": "vijın", "magsafe": "megseyf",
    "google": "gugıl", "pixel": "piksıl", "gemini": "cemini", "youtube": "yutub", "chrome": "krom",
    "galaxy": "gelaksi", "buds": "badz", "microsoft": "maykrosoft", "windows": "vindovs", "xbox": "ekboks",
    "copilot": "kopaylıt", "surface": "sörfıs", "outlook": "autluk", "playstation": "pleysteyşın",
    "switch": "sviç", "whatsapp": "vatsap", "facebook": "feysbuk", "threads": "tredz", "netflix": "netfliks",
    "spotify": "spotifay", "kindle": "kindıl", "bluetooth": "bılutut", "wifi": "vayfay", "wi-fi": "vayfay",
    "chatgpt": "çetcipiti", "openai": "opınay", "nothing": "nating", "phone": "fon", "oneplus": "vanplas",
    "xiaomi": "şaomi", "huawei": "huavey", "realme": "rilmi", "nvidia": "envidia", "geforce": "ciforz",
    "ryzen": "rayzın", "snapdragon": "snepdragın", "qualcomm": "kualkom", "dolby": "dolbi", "max": "meks",
    "plus": "plas", "air": "er", "lite": "layt", "edge": "ec", "note": "nout", "home": "houm", "touch": "taç",
    "face": "feys", "steam": "stim", "deck": "dek", "quest": "kuest", "laptop": "leptop", "gaming": "geyming",
    "cloud": "klaud", "update": "apdeyt", "smartwatch": "smartvoç", "headphones": "hedfons",
}


def ingilizce_okunus(metin: str) -> str:
    """Seslendirme metnindeki bilinen İngilizce kelimeleri okunuşlarıyla yazar (iPhone'un -> ayfon'un).

    Kelime sayısı değişmez; ekrandaki altyazı orijinal yazımla kalır.
    """
    def cevir(m: re.Match) -> str:
        k = m.group(0)
        yeni = INGILIZCE_OKUNUS.get(k.lower())
        if not yeni:
            return k
        return yeni[0].upper() + yeni[1:] if k[0].isupper() and m.start() == 0 else yeni

    metin = re.sub(r"(?<![^\s(\"'])[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z]+)?", cevir, metin)
    # Cümle başındaki kelime küçük harfe döndüyse büyüt.
    tr_buyuk = {"i": "İ", "ı": "I"}
    return re.sub(r"(^|[.!?]\s+)([a-zçğıöşü])",
                  lambda m: m.group(1) + tr_buyuk.get(m.group(2), m.group(2).upper()), metin)


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


def _cumleler_metin(metin: str) -> list[str]:
    import re
    return [c for c in re.split(r"(?<=[.!?…])\s+", metin.strip()) if c.split()]


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
