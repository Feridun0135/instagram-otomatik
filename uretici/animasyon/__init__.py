"""Animasyonlu anlatım: kodla çizilen hareketli sahneler (telefon, bilgisayar, tuş, pil, sayaç...).

motor.html içindeki sahne kütüphanesi Chromium'da (Playwright) açılır, her kare için zaman sarılıp
ekran görüntüsü alınır ve FFmpeg ile videoya çevrilir. Ücretsizdir, internet gerektirmez.

Sahne türleri ve alanları (yapay zekâ istemi de bunu kullanır): SAHNE_TURLERI.
"""
import json
import subprocess
import time
from pathlib import Path

MOTOR = Path(__file__).with_name("motor.html")
FPS = 30
G, Y = 1080, 1920

SAHNE_TURLERI = """Sahne türleri (her sahne bir JSON nesnesi; "tur" zorunlu, diğer alanlar türe göre):
- ikon: büyük ikonlu bilgi kartı. {"tur":"ikon","ikon":"<ikon adı>","baslik":"en fazla 4 kelime","alt":"en fazla 7 kelime",
  "etiket":"arti|eksi (yalnızca ürün artısı/eksisi anlatılırken)","renk":"sari|yesil|kirmizi|mavi|mor"}
- telefon_ayar: telefonda ayar ekranı, bir ayarın düğmesi açılır/kapanır. {"tur":"telefon_ayar","ekran":"ekran başlığı",
  "satirlar":[{"ad":"en fazla 3 kelime","ikon":"<ikon adı>","acik":true}], (3-5 satır) "hedef":değişen satırın sırası (0'dan),
  "yeni_durum":false (kapatılıyorsa) veya true (açılıyorsa)}
- telefon_bildirim: telefonda bildirimler düşer. {"tur":"telefon_bildirim","bildirimler":[{"uygulama":"ad","metin":"en fazla 5 kelime","ikon":"<ikon adı>"}]} (2-4 bildirim)
- bilgisayar: monitörde pencereler. {"tur":"bilgisayar","eylem":"bol|ac|kucult|kapat","pencereler":["ad","ad"],"baslik":"en fazla 4 kelime"}
  (bol: iki pencere ekranı ikiye böler)
- kisayol: klavye tuşlarına sırayla basılır. {"tur":"kisayol","tuslar":["Win","Shift","S"],"baslik":"en fazla 4 kelime","alt":"en fazla 6 kelime"}
- pil: pil göstergesi dolar/boşalır. {"tur":"pil","bas":20,"bit":80,"sarj":true|false,"etiket":"en fazla 6 kelime"}
- rakam: büyük sayı sayarak artar. {"tur":"rakam","deger":12000,"onek":"","sonek":" mAh","ondalik":0,"ikon":"<ikon adı>","etiket":"en fazla 4 kelime","alt":"en fazla 6 kelime"}
- karsilastirma: iki çubuk yarışır. {"tur":"karsilastirma","baslik":"en fazla 4 kelime","sol":{"ad":"A","deger":5},"sag":{"ad":"B","deger":8},
  "birim":"saat","iyi":"buyuk|kucuk","ondalik":0}
- adimlar: menü yolu / adımlar sırayla. {"tur":"adimlar","adimlar":["Ayarlar","Pil","Pil Sağlığı"]} (2-4 adım, her biri en fazla 3 kelime)
- kontrol_listesi: tik atılan liste. {"tur":"kontrol_listesi","baslik":"en fazla 4 kelime","maddeler":[{"ad":"en fazla 4 kelime","durum":"arti|eksi"}]} (2-5 madde)
- uyari: sallanan uyarı işareti. {"tur":"uyari","baslik":"en fazla 4 kelime","alt":"en fazla 7 kelime"}
- hiz: hız göstergesi. {"tur":"hiz","deger":120,"birim":"Hz","oran":0.8,"etiket":"en fazla 5 kelime"}
- urun: ürünün GERÇEK fotoğrafı (yalnızca ürün analizinde ve ürün görseli varken). {"tur":"urun","gorsel":0,"baslik":"ürün adı","alt":"en fazla 6 kelime"}
İkon adları: bilgi, pil, sarj, wifi, bluetooth, konum, kilit, kalkan, kamera, islemci, bulut, indir, hiz, uyari, onay, carpi,
para, sepet, etiket, harita, araba, priz, goz, zil, ayar, cop, foto, telefon, laptop, kulaklik, saat, akilli_saat, yapay_zeka,
depolama, sinyal, gunes, ay, sicaklik, yildiz, kalp, dunya, anahtar, kullanici, ses, oyun, tv, ev, yenile, mesaj, grafik, arama, hediye.
Sahne yazıları kısa olsun (ekranda büyük görünür), Türkçe yazım kurallarına uygun ve cümlenin anlattığını canlandırsın.
Rakam, değer ve oranlarda yalnızca metinde geçen veya kesin bilinen değerleri kullan; uydurma.
Aynı sahne türünü art arda iki kereden fazla kullanma; anlatımı en iyi canlandıran türü seç."""

TURLER = {"ikon", "telefon_ayar", "telefon_bildirim", "bilgisayar", "kisayol", "pil", "rakam", "karsilastirma",
          "adimlar", "kontrol_listesi", "uyari", "hiz", "urun"}


def cumle_zamanlari(kelimeler: list[dict], metinler: list[str], toplam: float) -> list[float]:
    """Her cümlenin konuşmada başladığı an.

    Kelime listesi hangi metinden geldiyse (düzgün yazım veya konuşma dili) onun cümle sınırları kullanılır;
    kelime sayısı hiçbiriyle tutmazsa sınırlar orantılı yerleştirilir.
    """
    import re

    def cumleler(m: str) -> list[list[str]]:
        return [c.split() for c in re.split(r"(?<=[.!?…])\s+", m.strip()) if c.split()]

    adaylar = [cumleler(m) for m in metinler if m]
    if not adaylar:
        return [0.0]
    secilen = next((c for c in adaylar if sum(map(len, c)) == len(kelimeler)), adaylar[0])
    toplam_kelime = max(1, sum(map(len, secilen)))
    zamanlar, i = [], 0
    for c in secilen:
        if kelimeler:
            j = i if sum(map(len, secilen)) == len(kelimeler) else int(i * len(kelimeler) / toplam_kelime)
            zamanlar.append(kelimeler[min(j, len(kelimeler) - 1)]["baslangic"])
        else:
            zamanlar.append(toplam * i / toplam_kelime)
        i += len(c)
    zamanlar[0] = 0.0
    return zamanlar


def efekt_olaylari(sahneler: list[dict]) -> list[tuple[str, float, float]]:
    """Sahne geçişlerinde hafif whoosh, sahne açılırken küçük pop (eksi sahnelerinde pes ton)."""
    olaylar = []
    for i, v in enumerate(sahneler):
        if i:
            olaylar.append(("whoosh", max(0.0, v["_bas"] - 0.05), 0.12))
        olaylar.append(("pop_eksi" if v.get("etiket") == "eksi" else "pop", v["_bas"] + 0.3, 0.32))
    return olaylar


def sahneleri_hazirla(sahneler: list, zamanlar: list[float], toplam: float, yedek_basliklar: list[str]) -> list[dict]:
    """Yapay zekânın sahne planını cümle zamanlarına oturtur; eksik/bozuk sahneleri ikon sahnesiyle tamamlar."""
    sonuc = []
    for i, bas in enumerate(zamanlar):
        v = sahneler[i] if i < len(sahneler) and isinstance(sahneler[i], dict) else {}
        if v.get("tur") not in TURLER:
            v = {"tur": "ikon", "ikon": "bilgi", "baslik": yedek_basliklar[i] if i < len(yedek_basliklar) else ""}
        bit = zamanlar[i + 1] if i + 1 < len(zamanlar) else toplam
        v = dict(v, _bas=round(max(0.0, bas - 0.15), 3), _bit=round(bit + 0.15, 3))
        sonuc.append(v)
    return sonuc


def video_uret(sahneler: list[dict], toplam: float, cikti: Path, alan: dict | None = None,
               gorseller: list[Path] | None = None) -> Path:
    """Sahneleri sessiz bir MP4'e çevirir (1080x1920, 30 fps)."""
    from playwright.sync_api import sync_playwright

    kare_sayisi = max(1, round(toplam * FPS))
    veri = {"sahneler": sahneler, "toplam": toplam, "alan": alan,
            "gorseller": [Path(g).resolve().as_uri() for g in (gorseller or [])]}
    ffmpeg = subprocess.Popen(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS),
         "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         str(cikti)], stdin=subprocess.PIPE)
    baslangic = time.time()
    try:
        with sync_playwright() as p:
            tarayici = p.chromium.launch(args=["--disable-gpu", "--font-render-hinting=none"])
            sayfa = tarayici.new_page(viewport={"width": G, "height": Y}, device_scale_factor=1)
            sayfa.goto(MOTOR.resolve().as_uri())
            sayfa.evaluate("veri => kur(veri)", veri)
            for k in range(kare_sayisi):
                sayfa.evaluate(f"seek({k / FPS:.4f})")
                ffmpeg.stdin.write(sayfa.screenshot(type="jpeg", quality=90))
            tarayici.close()
    finally:
        ffmpeg.stdin.close()
        ffmpeg.wait()
    if ffmpeg.returncode != 0:
        raise RuntimeError("Animasyon videosu kodlanamadı.")
    print(f"    Animasyon: {len(sahneler)} sahne, {kare_sayisi} kare, {time.time() - baslangic:.0f} sn")
    return cikti


def plan_json(sahneler: list[dict]) -> str:
    return json.dumps(sahneler, ensure_ascii=False, indent=2)
