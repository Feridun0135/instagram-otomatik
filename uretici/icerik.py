"""Günün konusunu ve video metnini Gemini API ile üretir."""
import json
import random
import time
from datetime import date

import requests

from . import ayarlar

KATEGORILER = {
    "teknoloji_bilgisi": "günlük teknoloji bilgisi (ilginç bir teknoloji gerçeği, yeni bir gelişme veya kavramın sade anlatımı)",
    "urun_tanitimi": "teknoloji ürünü tanıtımı (bilinen bir telefon, bilgisayar, aksesuar veya uygulama)",
    "ipucu": "telefon veya bilgisayar kullanımını kolaylaştıran pratik bir ipucu",
}

GECMIS_DOSYASI = ayarlar.VERI / "gecmis.json"


def gecmisi_oku() -> list[dict]:
    if GECMIS_DOSYASI.exists():
        return json.loads(GECMIS_DOSYASI.read_text(encoding="utf-8"))
    return []


def gecmise_ekle(icerik: dict) -> None:
    gecmis = gecmisi_oku()
    gecmis.append({"tarih": date.today().isoformat(), "kategori": icerik["kategori"], "konu": icerik["konu"]})
    GECMIS_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    GECMIS_DOSYASI.write_text(json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8")


def kategori_sec(gecmis: list[dict]) -> str:
    """Son iki günde kullanılmayan kategorilerden birini seçer; böylece içerik türleri dönüşümlü olur."""
    son = [g["kategori"] for g in gecmis[-2:]]
    adaylar = [k for k in KATEGORILER if k not in son] or list(KATEGORILER)
    return random.choice(adaylar)


def _istem(kategori: str, eski_konular: list[str]) -> str:
    eskiler = "\n".join(f"- {k}" for k in eski_konular[-60:]) or "- (henüz yok)"
    return f"""Türkçe bir Instagram Reels teknoloji hesabı için içerik hazırla.

İçerik türü: {KATEGORILER[kategori]}

Daha önce işlenen konular (bunları ve çok benzerlerini TEKRARLAMA):
{eskiler}

Kurallar:
- Seslendirme metni 60-90 kelime olsun (yaklaşık 25-35 saniye). Kısa, tempolu cümleler kur.
- İlk cümle izleyiciyi durduracak güçlü bir kanca olsun.
- Sade, samimi, günlük Türkçe kullan; "sen" diye hitap et.
- Kesin olarak doğru olduğundan emin olmadığın bilgiyi yazma.
- Fiyat, kampanya, çıkış tarihi gibi hızla değişen bilgileri YAZMA.
- Ürün tanıtımında yalnızca yaygın olarak bilinen, kalıcı özelliklerden bahset.
- Metinde emoji, madde işareti veya parantez kullanma (seslendirilecek).
- Son cümle takip etmeye veya kaydetmeye davet etsin.

Yalnızca şu JSON'u döndür:
{{
  "konu": "kısa konu başlığı",
  "kanca": "ekranın üstünde ilk saniyelerde görünecek en fazla 6 kelimelik başlık",
  "metin": "seslendirilecek tam metin",
  "aciklama": "Instagram gönderi açıklaması, 2-3 cümle, sonunda soru",
  "etiketler": ["8-12 adet", "Türkçe ve İngilizce", "# olmadan"],
  "gorsel_aramalari": ["stok video aramak için 4 kısa, birbirinden farklı İngilizce arama ifadesi"],
  "ekran_notlari": [
    {{"metin": "ekranda animasyonla çıkacak en fazla 5 kelimelik kilit bilgi", "cumle_baslangici": "bu bilginin geçtiği cümlenin metindeki ilk 3 kelimesi, birebir aynı"}}
  ]
}}

ekran_notlari 3-4 madde olsun; metindeki önemli bilgileri, adımları veya rakamları özetlesin."""


# Geçici yoğunluk / kota hatalarında beklenip tekrar denenir.
_GECICI_HATALAR = {429, 500, 502, 503, 504}
_BEKLEMELER = [10, 30, 60]  # saniye


def _gemini_cagir(govde: dict) -> str:
    """Ana modeli dener; geçici hatalarda bekleyip tekrarlar, olmazsa yedek modellere geçer."""
    modeller = [ayarlar.GEMINI_MODEL] + [m for m in ayarlar.GEMINI_YEDEK_MODELLER if m != ayarlar.GEMINI_MODEL]
    son_hata = ""
    for model in modeller:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for deneme in range(len(_BEKLEMELER) + 1):
            try:
                yanit = requests.post(url, headers={"x-goog-api-key": ayarlar.GEMINI_API_KEY}, json=govde, timeout=120)
            except requests.RequestException as hata:
                son_hata = f"{model}: bağlantı hatası {hata}"
                durum = None
            else:
                if yanit.status_code == 200:
                    return yanit.json()["candidates"][0]["content"]["parts"][0]["text"]
                durum = yanit.status_code
                son_hata = f"{model}: {durum} {yanit.text[:300]}"
                if durum in (400, 401, 403):  # anahtar veya istek hatası; tekrar denemek işe yaramaz
                    raise RuntimeError(f"Gemini API hatası {son_hata}")
                if durum not in _GECICI_HATALAR:  # ör. 404: model yok, sıradaki modele geç
                    break
            if deneme < len(_BEKLEMELER):
                print(f"    Gemini yoğun ({durum or 'bağlantı'}); {_BEKLEMELER[deneme]} sn sonra tekrar denenecek...")
                time.sleep(_BEKLEMELER[deneme])
        print(f"    {model} yanıt vermedi, sıradaki model deneniyor...")
    raise RuntimeError(f"Gemini API şu an yanıt vermiyor. Biraz sonra tekrar deneyin. Son hata: {son_hata}")


def icerik_uret() -> dict:
    if not ayarlar.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil. .env dosyasına ekleyin.")

    gecmis = gecmisi_oku()
    kategori = kategori_sec(gecmis)
    govde = {
        "contents": [{"parts": [{"text": _istem(kategori, [g["konu"] for g in gecmis])}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
    }
    metin = _gemini_cagir(govde)
    icerik = json.loads(metin)
    for alan in ("konu", "kanca", "metin", "aciklama", "etiketler", "gorsel_aramalari"):
        if alan not in icerik:
            raise RuntimeError(f"Yapay zekâ yanıtında '{alan}' alanı eksik: {metin[:300]}")
    icerik["kategori"] = kategori
    return icerik


def instagram_aciklamasi(icerik: dict) -> str:
    etiketler = " ".join("#" + e.lstrip("#").replace(" ", "") for e in icerik["etiketler"])
    return f"{icerik['aciklama']}\n\n{etiketler}"
