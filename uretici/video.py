"""Ses, stok klipler ve animasyonlu yazılardan 1080x1920 dikey Reels videosu oluşturur (FFmpeg ile).

Arka plan: kısa çekimler, her çekimde yavaş yakınlaşma/uzaklaşma ve çekimler arası geçişler.
Yazılar (ASS altyazı biçimi): açılış başlığı, kelime kelime vurgulanan altyazı,
kayarak gelen bilgi kartları ve alttaki ilerleme çubuğu.
"""
import json
import math
import random
import re
import subprocess
from pathlib import Path

from . import ayarlar

G, Y, FPS = ayarlar.VIDEO_GENISLIK, ayarlar.VIDEO_YUKSEKLIK, ayarlar.VIDEO_FPS

SARI = "&H0000D7FF&"     # ASS renkleri BGR sırasındadır: altın sarısı
BEYAZ = "&H00FFFFFF&"
YESIL = "&H0032A02E&"    # artı (BGR)
KIRMIZI = "&H002E2ED6&"  # eksi (BGR)
# Yumuşak geçişler (sert kayma ve gösterişli şekiller yok); "fade" iki kat olasılıkla seçilir.
GECISLER = ["fade", "fade", "smoothleft", "smoothright", "smoothup"]


# ---------- yardımcılar ----------

def sure_olc(dosya: Path) -> float:
    cikti = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(dosya)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(cikti)["format"]["duration"])


def _zaman(sn: float) -> str:
    sn = max(sn, 0)
    s, kalan = divmod(sn, 3600)
    d, kalan = divmod(kalan, 60)
    return f"{int(s)}:{int(d):02d}:{kalan:05.2f}"


def tr_buyuk(metin: str) -> str:
    """Türkçe kurallarına uygun büyük harf (i -> İ, ı -> I)."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


def _tr_kucuk(metin: str) -> str:
    return metin.replace("İ", "i").replace("I", "ı").lower()


def _temiz(metin: str) -> str:
    return metin.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def _normal(kelime: str) -> str:
    return re.sub(r"[^\wçğıöşü]", "", _tr_kucuk(kelime))


# ---------- bilgi kartlarının zamanlaması ----------

def not_zamanlari(notlar: list[dict], kelimeler: list[dict], toplam: float,
                  ilk: float = 3.2) -> list[dict]:
    """Her bilgi kartını, metinde geçtiği cümlenin başladığı ana yerleştirir.

    Cümle bulunamazsa kartlar videonun gövdesine eşit aralıklarla dağıtılır.
    """
    notlar = [n for n in notlar if isinstance(n, dict) and n.get("metin")]
    if not notlar:
        return []
    normal = [_normal(k["metin"]) for k in kelimeler]

    def bul(cumle: str) -> float | None:
        aranan = [_normal(k) for k in cumle.split()][:3]
        aranan = [a for a in aranan if a]
        if not aranan:
            return None
        for uzunluk in (len(aranan), 2, 1):
            parca = aranan[:uzunluk]
            for i in range(len(normal) - len(parca) + 1):
                if normal[i:i + len(parca)] == parca:
                    return kelimeler[i]["baslangic"]
        return None

    baslangiclar = [bul(n.get("cumle_baslangici", "")) for n in notlar]
    if any(b is None for b in baslangiclar) or len(set(baslangiclar)) < len(baslangiclar):
        aralik = (toplam - 2.0 - ilk) / len(notlar)
        baslangiclar = [ilk + i * aralik for i in range(len(notlar))]

    sirali = sorted(zip(baslangiclar, notlar), key=lambda x: x[0])
    # Başlık ekrandayken veya birbirine çok yakın gelen maddeleri kaydır (en az 1,3 sn arayla).
    onceki = ilk - 1.3
    duzeltilmis = []
    for bas, n in sirali:
        bas = max(bas, ilk, onceki + 1.3)
        duzeltilmis.append((bas, n))
        onceki = bas
    sirali = duzeltilmis
    sonuc = []
    for i, (bas, n) in enumerate(sirali):
        sonraki = sirali[i + 1][0] if i + 1 < len(sirali) else toplam - 0.5
        bitis = min(bas + 4.5, sonraki - 0.15, toplam - 0.3)
        sonuc.append({"baslangic": bas, "bitis": bitis, "metin": n["metin"], "sira": len(sonuc) + 1,
                      "tur": n.get("tur")})
    return sonuc


# Ürün vitrini düzeni: ürün görseli solda, özellik listesi sağda.
VITRIN_GORSEL = (600, 1150)   # ürün görselinin sığacağı alan (genişlik, yükseklik)
VITRIN_OK_X = 600             # okun başladığı x
VITRIN_LISTE_X = 700          # özellik yazılarının başladığı x
VITRIN_EN_FAZLA = 6           # en fazla 6 madde (4 artı + 2 eksi)
VITRIN_UST = 360              # ilk başlığın y'si
VITRIN_BASLIK_ARALIK = 100
VITRIN_MADDE_ARALIK = 132
VITRIN_GRUP_BOSLUK = 30


def vitrin_plani(kartlar: list[dict], toplam: float) -> dict | None:
    """Ürün özelliklerinin sırayla listeleneceği zaman aralığını çıkarır (en az 2 özellik gerekir)."""
    maddeler = [{"baslangic": k["baslangic"], "metin": k["metin"], "tur": k.get("tur")}
                for k in kartlar][:VITRIN_EN_FAZLA]
    if len(maddeler) < 2:
        return None
    bas = max(maddeler[0]["baslangic"] - 0.3, 3.1)
    bit = min(maddeler[-1]["baslangic"] + 4.0, toplam - 0.3)
    if bit - bas < 3:
        return None
    return {"baslangic": bas, "bitis": bit, "maddeler": maddeler}


def vitrin_satirlari(vitrin: dict) -> list[dict]:
    """Vitrindeki satırlar (başlıklar ve maddeler), ekrandaki y konumları ve görünme zamanlarıyla.

    Artı/eksi varsa iki ayrı başlık olur: ARTILAR ilk artıyla, EKSİLER ilk eksiden hemen önce gelir.
    """
    maddeler = vitrin["maddeler"]
    ayri = any(m.get("tur") == "eksi" for m in maddeler) and any(m.get("tur") == "arti" for m in maddeler)
    satirlar: list[dict] = []
    y = VITRIN_UST
    if not ayri:
        satirlar.append({"tip": "baslik", "metin": "ÖNE ÇIKANLAR", "tur": None,
                         "baslangic": vitrin["baslangic"], "y": y})
        y += VITRIN_BASLIK_ARALIK
    onceki_tur, onceki_zaman = None, vitrin["baslangic"]
    for m in maddeler:
        tur = m.get("tur")
        if ayri and tur in ("arti", "eksi") and tur != onceki_tur:
            if onceki_tur is not None:
                y += VITRIN_GRUP_BOSLUK
            zaman = max(m["baslangic"] - (0.0 if onceki_tur is None else 0.5), onceki_zaman + 0.3)
            satirlar.append({"tip": "baslik", "metin": "ARTILAR" if tur == "arti" else "EKSİLER",
                             "tur": tur, "baslangic": zaman, "y": y})
            y += VITRIN_BASLIK_ARALIK
            onceki_tur = tur
        bas = max(m["baslangic"], satirlar[-1]["baslangic"] + 0.35) if satirlar else m["baslangic"]
        satirlar.append({"tip": "madde", "metin": m["metin"], "tur": tur, "baslangic": bas, "y": y})
        onceki_zaman = bas
        y += VITRIN_MADDE_ARALIK
    return satirlar


# ---------- kutulu cümle altyazısı ----------

VURGU = "&H000C59E8&"   # turuncu (BGR); altyazıda önemli kelimeler
KOYU = "&H00262626&"


def _yazi_genisligi(metin: str, boyut: int) -> float:
    """Kalın yazı tipinde yaklaşık piksel genişliği (kutuyu yazıya göre boyutlandırmak için)."""
    g = 0.0
    for ch in metin:
        if ch == " ":
            g += 0.28
        elif ch in ".,:;!'|ıil":
            g += 0.30
        elif ch.isupper() or ch in "mwMW":
            g += 0.70
        elif ch.isdigit():
            g += 0.56
        else:
            g += 0.55
    return g * boyut


def _yuvarlak_kutu(gen: float, yuk: float, r: float = 26) -> str:
    """ASS çizim komutuyla köşeleri yuvarlatılmış dikdörtgen (sol üst köşe 0,0)."""
    w, h = int(gen), int(yuk)
    return (f"m {r} 0 l {w - r} 0 b {w} 0 {w} 0 {w} {r} l {w} {h - r} b {w} {h} {w} {h} {w - r} {h} "
            f"l {r} {h} b 0 {h} 0 {h} 0 {h - r} l 0 {r} b 0 0 0 0 {r} 0")


def _normal_kok(kelime: str) -> str:
    return _normal(kelime)


def _dengeli_bol(kelimeler: list[dict], parca_sayisi: int, boyut: int) -> list[list[dict]]:
    """Kelimeleri genişliği birbirine yakın `parca_sayisi` parçaya böler (sırayı korur)."""
    if parca_sayisi <= 1 or len(kelimeler) <= 1:
        return [kelimeler]
    genislikler = [_yazi_genisligi(k["metin"] + " ", boyut) for k in kelimeler]
    hedef = sum(genislikler) / parca_sayisi
    parcalar, mevcut, birikim = [], [], 0.0
    for k, g in zip(kelimeler, genislikler):
        kalan_parca = parca_sayisi - len(parcalar) - 1
        if mevcut and birikim + g / 2 > hedef and kalan_parca > 0:
            parcalar.append(mevcut)
            mevcut, birikim = [], 0.0
        mevcut.append(k)
        birikim += g
    parcalar.append(mevcut)
    return parcalar


def cumle_parcalari(kelimeler: list[dict], satir_px: int = 860, boyut: int = 50, en_fazla_satir: int = 2) -> list[dict]:
    """Kelimeleri ekranda kutu içinde gösterilecek parçalara böler.

    Her cümle, en fazla 2 satırlık ve birbirine yakın uzunlukta parçalara ayrılır; böylece tek kelimelik
    "yetim" parçalar oluşmaz. Her parçanın satırları da dengeli bölünür.
    """
    import math

    cumleler, mevcut = [], []
    for k in kelimeler:
        mevcut.append(k)
        if k["metin"][-1:] in ".!?…":
            cumleler.append(mevcut)
            mevcut = []
    if mevcut:
        cumleler.append(mevcut)

    sonuc = []
    for cumle in cumleler:
        toplam = _yazi_genisligi(" ".join(k["metin"] for k in cumle), boyut)
        adet = max(1, math.ceil(toplam / (satir_px * en_fazla_satir * 0.92)))
        for parca in _dengeli_bol(cumle, adet, boyut):
            gen = _yazi_genisligi(" ".join(k["metin"] for k in parca), boyut)
            satirlar = _dengeli_bol(parca, min(en_fazla_satir, math.ceil(gen / satir_px)), boyut)
            sonuc.append({"satirlar": satirlar, "baslangic": parca[0]["baslangic"], "bitis": parca[-1]["bitis"]})
    return sonuc


# ---------- ASS yazı katmanı ----------

def ass_yaz(gruplar: list[list[dict]], kanca: str, kartlar: list[dict], toplam: float,
            yol: Path, kanca_suresi: float = 3.0, vitrin: dict | None = None,
            vurgular: list[str] | None = None) -> None:
    font = ayarlar.ALTYAZI_FONT
    bicim = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
             "Alignment, MarginL, MarginR, MarginV, Encoding")
    satirlar = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {G}", f"PlayResY: {Y}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]", bicim,
        # Altyazı: beyaz, kalın siyah kenarlı, alt-orta.
        f"Style: Altyazi,{font},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,8,3,2,70,70,600,1",
        # Açılış başlığı: sarı zemin üzerinde siyah.
        f"Style: Kanca,{font},96,&H00000000,&H00000000,&H0000D7FF,&H0000D7FF,-1,0,0,0,100,100,0,0,3,26,0,8,90,90,300,1",
        # Kutulu cümle altyazısı ve kutusu, hesap etiketi.
        f"Style: KutuYazi,{font},50,{KOYU[:-1]},{KOYU[:-1]},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1",
        f"Style: Cizim,{font},20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Hesap,{font},30,{KOYU[:-1]},{KOYU[:-1]},&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1",
        # Bilgi kartı: koyu zemin üzerinde beyaz.
        f"Style: Kart,{font},80,&H00FFFFFF,&H00FFFFFF,&H28201812,&H00000000,-1,0,0,0,100,100,0,0,3,34,0,5,100,100,0,1",
        # Kart etiketi: sarı zemin üzerinde siyah, küçük.
        f"Style: Etiket,{font},52,&H00000000,&H00000000,&H0000D7FF,&H00000000,-1,0,0,0,100,100,2,0,3,14,0,5,0,0,0,1",
        # Ürün vitrini: sağdaki özellik maddeleri ve başlık.
        f"Style: Ozellik,{font},42,&H00FFFFFF,&H00FFFFFF,&H28201812,&H00000000,-1,0,0,0,100,100,0,0,3,18,0,4,{VITRIN_LISTE_X},30,0,1",
        f"Style: VitrinBaslik,{font},46,&H00000000,&H00000000,&H0000D7FF,&H00000000,-1,0,0,0,100,100,3,0,3,14,0,4,{VITRIN_LISTE_X},30,0,1",
        f"Style: Ok,{font},20,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,4,0,0,0,1",
        f"Style: Cubuk,{font},20,&H0000D7FF,&H0000D7FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def olay(katman, bas, bit, stil, metin):
        satirlar.append(f"Dialogue: {katman},{_zaman(bas)},{_zaman(bit)},{stil},,0,0,0,,{metin}")

    # Açılış başlığı: büyüyerek "pop" yapar.
    olay(3, 0, kanca_suresi, "Kanca",
         r"{\fscx40\fscy40\t(0,180,\fscx108\fscy108)\t(180,280,\fscx100\fscy100)\fad(0,200)}"
         + tr_buyuk(_temiz(kanca)))

    if ayarlar.ALTYAZI_STILI == "kutu":
        # Hesap etiketi: üstte küçük, yarı saydam beyaz kapsül.
        if ayarlar.HESAP_ETIKETI:
            hg = _yazi_genisligi(ayarlar.HESAP_ETIKETI, 30) + 44
            olay(4, 0, toplam, "Cizim",
                 rf"{{\pos({int((G - hg) / 2)},{150 - 27})\1a&H40&\p1}}{_yuvarlak_kutu(hg, 54, 27)}{{\p0}}")
            olay(5, 0, toplam, "Hesap", rf"{{\pos({G // 2},150)}}" + _temiz(ayarlar.HESAP_ETIKETI))

        # Kutulu cümle altyazısı: beyaz yuvarlak kutu, koyu yazı, önemli kelimeler turuncu.
        vurgu_kokleri = {_normal(w) for v in (vurgular or []) for w in str(v).split() if _normal(w)}
        kelimeler = [k for grup in gruplar for k in grup]
        parcalar = cumle_parcalari(kelimeler)
        y_merkez = 1500
        for pi, parca in enumerate(parcalar):
            bas = parca["baslangic"]
            bit = parcalar[pi + 1]["baslangic"] if pi + 1 < len(parcalar) else parca["bitis"] + 0.4
            if bit - parca["bitis"] > 0.8:
                bit = parca["bitis"] + 0.5
            if bit <= bas:
                continue
            satir_metinleri, en_genis = [], 0.0
            for satir in parca["satirlar"]:
                en_genis = max(en_genis, _yazi_genisligi(" ".join(k["metin"] for k in satir), 50))
                kelimeler_yazi = []
                for k in satir:
                    yazi = _temiz(k["metin"])
                    if _normal(k["metin"]) in vurgu_kokleri:
                        yazi = f"{{\\c{VURGU}}}{yazi}{{\\c{KOYU}}}"
                    kelimeler_yazi.append(yazi)
                satir_metinleri.append(" ".join(kelimeler_yazi))
            kg = min(en_genis + 72, G - 60)
            ky_ = 50 * 1.22 * len(satir_metinleri) + 44
            olay(0, bas, bit, "Cizim",
                 rf"{{\pos({int((G - kg) / 2)},{int(y_merkez - ky_ / 2)})\1a&H08&\fad(90,60)\p1}}"
                 + _yuvarlak_kutu(kg, ky_) + "{\\p0}")
            olay(1, bas, bit, "KutuYazi",
                 rf"{{\q2\pos({G // 2},{y_merkez})\fad(90,60)}}" + "\\N".join(satir_metinleri))
    else:
        for gi, grup in enumerate(gruplar):
            grup_sonu = grup[-1]["bitis"]
            if gi + 1 < len(gruplar) and gruplar[gi + 1][0]["baslangic"] - grup_sonu < 0.4:
                grup_sonu = gruplar[gi + 1][0]["baslangic"]  # gruplar arasında titreme olmasın
            for wi, kelime in enumerate(grup):
                bas = kelime["baslangic"]
                bit = grup[wi + 1]["baslangic"] if wi + 1 < len(grup) else grup_sonu
                if bit <= bas:
                    continue
                parcalar = []
                for wj, k in enumerate(grup):
                    yazi = tr_buyuk(_temiz(k["metin"]))
                    parcalar.append(f"{{\\c{SARI}}}{yazi}{{\\c{BEYAZ}}}" if wj == wi else yazi)
                pop = r"{\fscx70\fscy70\t(0,90,\fscx100\fscy100)}" if wi == 0 else ""
                olay(0, bas, bit, "Altyazi", pop + " ".join(parcalar))


    # Bilgi kartları: soldan kayarak gelir, sağa kayarak çıkar.
    ky = 560
    for kart in ([] if vitrin else kartlar):
        bas, bit = kart["baslangic"], kart["bitis"]
        if bit - bas < 1.5:  # çok kısa kalan kart gösterilmez
            continue
        ms = int((bit - bas) * 1000)
        olay(2, bas, bit, "Etiket",
             rf"{{\move(-300,{ky - 150},540,{ky - 150},60,340)\t({ms - 250},{ms},\alpha&HFF&)}}"
             f"BİLGİ {kart['sira']}")
        olay(1, bas, bit, "Kart",
             rf"{{\move(-700,{ky},540,{ky},0,300)\t({ms - 250},{ms},\alpha&HFF&)}}"
             + tr_buyuk(_temiz(kart["metin"])))

    # Ürün vitrini: sağda başlık, ardından her özellik oktan çıkarak sırayla eklenir ve listede kalır.
    if vitrin:
        vs = vitrin["bitis"]
        for satir in vitrin_satirlari(vitrin):
            sb, y = satir["baslangic"], satir["y"]
            ms = int((vs - sb) * 1000)
            kaybol = rf"\t({ms - 250},{ms},\alpha&HFF&)"
            tur = satir.get("tur")
            renk = YESIL if tur == "arti" else KIRMIZI if tur == "eksi" else SARI
            if satir["tip"] == "baslik":
                # Başlık: ARTILAR (yeşil) / EKSİLER (kırmızı) / ÖNE ÇIKANLAR (sarı); büyüyerek belirir.
                yazi_rengi = BEYAZ if tur in ("arti", "eksi") else "&H00000000&"
                olay(2, sb, vs, "VitrinBaslik",
                     rf"{{\q2\pos({VITRIN_LISTE_X},{y})\1c{yazi_rengi}\3c{renk}\fscx40\fscy40"
                     rf"\t(0,160,\fscx100\fscy100){kaybol}}}" + satir["metin"])
                continue
            on_ek = "+ " if tur == "arti" else "- " if tur == "eksi" else ""
            kutu = rf"\3c{renk}" if tur in ("arti", "eksi") else ""
            # Ok: soldan sağa doğru çizilir.
            olay(2, sb, vs, "Ok",
                 rf"{{\pos({VITRIN_OK_X},{y})\c{renk}\fscx0\t(0,180,\fscx100){kaybol}\p1}}"
                 "m 0 -5 l 66 -5 l 66 -17 l 92 0 l 66 17 l 66 5 l 0 5{\\p0}")
            # Özellik yazısı: sağdan kayarak gelir, hafifçe büyüyüp yerine oturur.
            # Uzun madde en fazla 2 satıra sığsın diye yazı boyutu küçültülür (alttaki maddeye taşmasın).
            yazi = on_ek + tr_buyuk(_temiz(satir["metin"]))
            genislik = _yazi_genisligi(yazi, 42)
            boyut = 42 if genislik <= 2 * 300 else max(30, int(42 * 2 * 300 / genislik))
            olay(2, sb + 0.12, vs, "Ozellik",
                 rf"{{\fs{boyut}\move({G + 40},{y},{VITRIN_LISTE_X},{y},0,220)\t(220,320,\fscx106\fscy106)"
                 rf"\t(320,420,\fscx100\fscy100){kutu}{kaybol}}}" + yazi)

    # İlerleme çubuğu: video boyunca soldan sağa dolar.
    olay(4, 0, toplam, "Cubuk",
         rf"{{\pos(0,{Y - 14})\fscx0\t(0,{int(toplam * 1000)},\fscx100)\p1}}m 0 0 l {G} 0 l {G} 14 l 0 14{{\p0}}")

    yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")


# ---------- arka plan ve birleştirme ----------

def _sureler(dosyalar: list[Path]) -> list[tuple[Path, float]]:
    sonuc = []
    for k in dosyalar:
        try:
            sonuc.append((k, sure_olc(k)))
        except (subprocess.CalledProcessError, KeyError, ValueError):
            pass
    return [(k, s) for k, s in sonuc if s > 0.5]


def _cekim_sirasi(n: int, klip_sayisi: int, resim_sayisi: int) -> list[tuple[str, int]]:
    """Hangi çekimde ne gösterileceği: ürün görseli varsa ilk çekim ve sonra her iki çekimden biri görsel."""
    sira = []
    for i in range(n):
        if resim_sayisi and (not klip_sayisi or i % 2 == 0):
            sira.append(("resim", (i // (1 if not klip_sayisi else 2)) % resim_sayisi))
        else:
            sira.append(("klip", (i // (2 if resim_sayisi else 1)) % klip_sayisi))
    return sira


def _efekt_dosyalari(klasor: Path) -> dict[str, Path]:
    """Telifsiz ses efektlerini FFmpeg ile sentezler (indirme gerekmez)."""
    tarifler = {
        # Kısa, aşağı doğru kayan "pop".
        "pop": ["-f", "lavfi", "-i", "aevalsrc=0.7*sin(2*PI*(1500-5200*t)*t)*exp(-26*t):s=44100:d=0.18"],
        # Eksiler için daha pes bir "tık".
        "pop_eksi": ["-f", "lavfi", "-i", "aevalsrc=0.7*sin(2*PI*(650-1800*t)*t)*exp(-22*t):s=44100:d=0.2"],
        # Yumuşak "whoosh": filtrelenmiş pembe gürültü.
        "whoosh": ["-f", "lavfi", "-i", "anoisesrc=d=0.45:c=pink:a=0.6:r=44100",
                   "-af", "bandpass=f=1800:width_type=h:w=1600,afade=t=in:d=0.2,afade=t=out:st=0.2:d=0.25"],
    }
    dosyalar = {}
    for ad, girdi in tarifler.items():
        hedef = klasor / f"efekt_{ad}.wav"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *girdi, "-ac", "1", str(hedef)],
                       check=True)
        dosyalar[ad] = hedef
    return dosyalar


# Görsel çekimlerinde kamera hareketleri: (başlangıç zoom, bitiş zoom, yatay kayma oranı).
# Hepsi yavaş ve doğrusal; ardışık çekimlerde hareket türü değişir.
KAMERA_HAREKETLERI = [(1.00, 1.10, 0.0), (1.08, 1.08, 0.05), (1.10, 1.02, 0.0), (1.08, 1.08, -0.05)]


def _sabit_kare(resim: Path, tur: str, hedef: Path) -> Path:
    """Görseli bulanık arka plan üzerine yerleştirilmiş tek bir kareye çevirir (2 kat çözünürlükte).

    Kamera hareketi bu kare üzerinde zoompan ile yapılır; yüksek çözünürlük sayesinde hareket titremez.
    """
    if hedef.exists():
        return hedef
    G2, Y2 = 2 * G, 2 * Y
    if tur == "vitrin":
        vg, vy = 2 * VITRIN_GORSEL[0], 2 * VITRIN_GORSEL[1]
        on = f"scale={vg}:{vy}:force_original_aspect_ratio=decrease"
        konum = f"x=({vg}-w)/2+20:y=(H-h)/2-120"
        karartma = "-0.30"
    else:
        on = f"scale={G2 - 160}:{int(Y2 * 0.62)}:force_original_aspect_ratio=decrease"
        konum = "x=(W-w)/2:y=(H-h)/2-120"
        karartma = "-0.18"
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(resim), "-filter_complex",
        f"[0:v]format=rgb24,split[b][f];"
        f"[b]scale={G2}:{Y2}:force_original_aspect_ratio=increase,crop={G2}:{Y2},boxblur=60:3,"
        f"eq=brightness={karartma}[bb];[f]{on}[ff];[bb][ff]overlay={konum}",
        "-frames:v", "1", str(hedef)], check=True)
    return hedef


def _kamera(i: int, tur: str, kare_sayisi: int) -> str:
    """zoompan ifadesi: yavaş, doğrusal yakınlaşma/uzaklaşma veya yatay kayma."""
    if tur == "vitrin":
        z0, z1, kay = 1.00, 1.04, 0.0
    else:
        z0, z1, kay = KAMERA_HAREKETLERI[i % len(KAMERA_HAREKETLERI)]
    ilerleme = f"(on/{max(1, kare_sayisi - 1)})"
    z = f"{z0}+({z1 - z0:.4f})*{ilerleme}"
    x = f"(iw-iw/zoom)/2+({kay}*iw/zoom)*({ilerleme}-0.5)"
    return f"zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)/2':d=1:s={G}x{Y}:fps={FPS}"


def _ses_karistir(girdiler: list[str], filtreler: list[str], ses_indeksi: int, toplam: float,
                  muzik: Path | None, olaylar: list[tuple[str, float, float]], klasor: Path) -> str:
    """Konuşma + (konuşurken kendiliğinden kısılan) arka plan müziği + efektler. Ses çıkışının etiketini döndürür."""
    karisim: list[str] = []
    sonraki = ses_indeksi + 1
    konusma = f"[{ses_indeksi}:a]"
    if muzik:
        girdiler += ["-stream_loop", "-1", "-i", str(Path(muzik).resolve())]
        filtreler.append(f"[{ses_indeksi}:a]asplit=2[konus][yan]")
        filtreler.append(
            f"[{sonraki}:a]aformat=sample_rates=44100:channel_layouts=mono,atrim=0:{toplam:.3f},"
            f"volume={ayarlar.MUZIK_SEVIYE},afade=t=in:d=1,afade=t=out:st={max(toplam - 1.5, 0):.3f}:d=1.5[m0]"
        )
        # Konuşma varken müziği biraz daha kıs (sidechain ducking).
        filtreler.append("[m0][yan]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=400[muz]")
        konusma = "[konus]"
        karisim.append("[muz]")
        sonraki += 1
    if olaylar:
        efekt = _efekt_dosyalari(klasor)
        for k, (ad, zaman, seviye) in enumerate(olaylar):
            girdiler += ["-i", str(efekt[ad].resolve())]
            ms = int(zaman * 1000)
            filtreler.append(f"[{sonraki}:a]adelay={ms}|{ms},volume={seviye}[e{k}]")
            karisim.append(f"[e{k}]")
            sonraki += 1
    if karisim:
        filtreler.append(f"{konusma}{''.join(karisim)}amix=inputs={len(karisim) + 1}:"
                         f"duration=first:dropout_transition=0:normalize=0[ses]")
        ses_cikisi = "[ses]"
    else:
        ses_cikisi = f"{ses_indeksi}:a"

    return ses_cikisi


def video_olustur(ses: Path, klipler: list[Path], altyazi: Path, cikti: Path,
                  resimler: list[Path] | None = None, vitrin: dict | None = None,
                  ses_efektleri: bool = True, muzik: Path | None = None) -> Path:
    """Arka plan çekimlerini (stok klipler ve ürün görselleri) geçişlerle birleştirir, yazıları ve sesi ekler.

    Altyazı dosyası ile çıktı aynı klasörde olmalı; FFmpeg o klasörde çalıştırılır
    (Windows'ta altyazı yolundaki ':' karakteri sorun çıkarmasın diye).
    """
    toplam = sure_olc(ses) + 0.5
    L, XF = ayarlar.CEKIM_SURESI, ayarlar.GECIS_SURESI
    girdiler: list[str] = []
    filtreler: list[str] = []

    klip_sure = _sureler(klipler or [])
    resimler = list(resimler or [])

    if klip_sure or resimler:
        n = max(1, math.ceil((toplam - XF) / L))
        rastgele = random.Random(str(ses))
        kullanim: dict[int, int] = {}
        d = f"{L + XF:.3f}"
        sira = _cekim_sirasi(n, len(klip_sure), len(resimler))
        if vitrin and resimler:
            # Özellikler anlatılırken arka planda hep ürünün kendisi olsun (vitrin düzeni).
            vitrin_sayac = 0
            for i in range(n):
                if i * L + L + XF > vitrin["baslangic"] and i * L < vitrin["bitis"]:
                    sira[i] = ("vitrin", (vitrin_sayac // 2) % len(resimler))
                    vitrin_sayac += 1
        if resimler and sira and sira[-1][0] != "vitrin":
            # Kapanış her zaman ürünün ana görseliyle (haberin kapak görseli) bitsin.
            sira[-1] = ("resim", 0)
        kare_sayisi = round((L + XF) * FPS)
        for i, (tur, j) in enumerate(sira):
            if tur in ("vitrin", "resim"):
                kare = _sabit_kare(resimler[j], tur, cikti.parent / f"kare_{tur}_{j}.png")
                girdiler += ["-loop", "1", "-framerate", str(FPS), "-t", d, "-i", str(kare.resolve())]
                filtreler.append(
                    f"[{i}:v]setpts=PTS-STARTPTS,{_kamera(i, tur, kare_sayisi)},"
                    f"setsar=1,format=yuv420p,settb=AVTB[c{i}]"
                )
            else:
                klip, sure = klip_sure[j]
                tekrar = kullanim.get(j, 0)
                kullanim[j] = tekrar + 1
                bos = max(sure - (L + XF), 0.0)
                ofset = (tekrar * (L + XF) * 0.9) % bos if bos > 0 else 0.0
                girdiler += ["-stream_loop", "-1", "-ss", f"{ofset:.2f}", "-t", d, "-i", str(klip.resolve())]
                if resimler:
                    # Ürün videosu (çoğu yatay): kırpmadan, bulanık arka plan üzerinde tam görünür.
                    filtreler.append(
                        f"[{i}:v]setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,split[b{i}][f{i}];"
                        f"[b{i}]scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},"
                        f"boxblur=30:3,eq=brightness=-0.18[bb{i}];"
                        f"[f{i}]scale={G}:{int(Y * 0.62)}:force_original_aspect_ratio=decrease[ff{i}];"
                        f"[bb{i}][ff{i}]overlay=x=(W-w)/2:y=(H-h)/2-60,setsar=1,format=yuv420p,settb=AVTB[c{i}]"
                    )
                else:
                    # Stok klip: ekranı doldurur; kendi hareketi olduğu için ayrıca zoom yapılmaz (titremez).
                    filtreler.append(
                        f"[{i}:v]setpts=PTS-STARTPTS,fps={FPS},"
                        f"scale={G}:{Y}:force_original_aspect_ratio=increase,crop={G}:{Y},"
                        + ("colorbalance=rs=0.07:gs=0.02:bs=-0.08:rm=0.05:gm=0.01:bm=-0.06,eq=saturation=1.05,"
                           if ayarlar.SICAK_FILTRE else "")
                        + f"setsar=1,format=yuv420p,settb=AVTB[c{i}]"
                    )
        onceki = "c0"
        for i in range(1, n):
            gecis = rastgele.choice(GECISLER)
            filtreler.append(f"[{onceki}][c{i}]xfade=transition={gecis}:duration={XF}:offset={i * L:.3f}[x{i}]")
            onceki = f"x{i}"
        filtreler.append(f"[{onceki}]eq=brightness=-0.05:saturation=1.1[arka]")
        ses_indeksi = n
    else:
        girdiler += ["-f", "lavfi", "-i", f"color=c=0x101828:s={G}x{Y}:r={FPS}:d={toplam:.3f}"]
        filtreler.append("[0:v]setsar=1[arka]")
        ses_indeksi = 1

    girdiler += ["-i", str(ses.resolve())]
    filtreler.append(f"[arka]subtitles={altyazi.name}[son]")

    # Ses efektleri: geçişlerde hafif whoosh, vitrindeki her özellikte pop.
    olaylar: list[tuple[str, float, float]] = []
    if ses_efektleri:
        if klip_sure or resimler:
            olaylar += [("whoosh", max(i * L - 0.15, 0), 0.16) for i in range(1, n)]
        if vitrin:
            for satir in vitrin_satirlari(vitrin):
                ses_adi = "pop_eksi" if satir.get("tur") == "eksi" else "pop"
                if satir["tip"] == "baslik":
                    olaylar.append((ses_adi, satir["baslangic"], 0.35))
                else:
                    olaylar.append((ses_adi, satir["baslangic"] + 0.12, 0.55))
    ses_cikisi = _ses_karistir(girdiler, filtreler, ses_indeksi, toplam, muzik, olaylar, altyazi.parent)

    komut = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *girdiler,
        "-filter_complex", ";".join(filtreler),
        "-map", "[son]", "-map", ses_cikisi,
        "-t", f"{toplam:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        cikti.name,
    ]
    subprocess.run(komut, cwd=altyazi.parent, check=True)
    return cikti


def animasyonlu_birlestir(taban: Path, ses: Path, altyazi: Path, cikti: Path, olaylar: list[tuple[str, float, float]],
                          muzik: Path | None = None) -> Path:
    """Animasyon videosunun üzerine yazıları (altyazı, başlık) basar; konuşma, müzik ve efektleri karıştırır."""
    toplam = sure_olc(ses) + 0.5
    girdiler = ["-i", str(Path(taban).resolve()), "-i", str(Path(ses).resolve())]
    filtreler = [f"[0:v]fps={FPS},format=yuv420p,subtitles={altyazi.name}[son]"]
    ses_cikisi = _ses_karistir(girdiler, filtreler, 1, toplam, muzik, olaylar, altyazi.parent)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *girdiler,
        "-filter_complex", ";".join(filtreler), "-map", "[son]", "-map", ses_cikisi, "-t", f"{toplam:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", cikti.name,
    ], cwd=altyazi.parent, check=True)
    return cikti
