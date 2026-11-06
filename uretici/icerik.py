"""Günün konusunu ve video metnini Gemini API ile üretir."""
import json
import time
from datetime import date

import requests

from . import ayarlar

KATEGORILER = {
    "yeni_urun": "yeni çıkan veya yeni duyurulan bir teknoloji ürününün analizi",
    "ipucu": "telefon veya bilgisayar kullanımını kolaylaştıran pratik bir ipucu",
    "teknoloji_bilgisi": "günlük teknoloji bilgisi (ilginç bir teknoloji gerçeği, yeni bir gelişme veya kavramın sade anlatımı)",
}
# Günlerin yarısı yeni ürün analizi olsun: yeni ürün, ipucu, yeni ürün, bilgi, ...
DONGU = ["yeni_urun", "ipucu", "yeni_urun", "teknoloji_bilgisi"]

GECMIS_DOSYASI = ayarlar.VERI / "gecmis.json"


def gecmisi_oku() -> list[dict]:
    if GECMIS_DOSYASI.exists():
        return json.loads(GECMIS_DOSYASI.read_text(encoding="utf-8"))
    return []


def gecmise_ekle(icerik: dict) -> None:
    gecmis = gecmisi_oku()
    kayit = {"tarih": date.today().isoformat(), "kategori": icerik["kategori"], "konu": icerik["konu"]}
    if icerik.get("kaynak_link"):
        kayit["kaynak_link"] = icerik["kaynak_link"]
    gecmis.append(kayit)
    GECMIS_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
    GECMIS_DOSYASI.write_text(json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8")


def kategori_sec(gecmis: list[dict]) -> str:
    return DONGU[len(gecmis) % len(DONGU)]


_ORTAK_KURALLAR = """Kurallar:
- Seslendirme metni 60-90 kelime olsun (yaklaşık 25-35 saniye). Kısa, tempolu cümleler kur.
- İlk cümle izleyiciyi durduracak güçlü bir kanca olsun (merak, şaşırtıcı bilgi veya doğrudan fayda).
- Sade, samimi, günlük Türkçe kullan; "sen" diye hitap et.
- Kesin olarak doğru olduğundan emin olmadığın bilgiyi yazma.
- Metinde emoji, madde işareti veya parantez kullanma (seslendirilecek).
- Son cümle takip etmeye veya kaydetmeye davet etsin.

Instagram açıklaması (aciklama) kuralları:
- İlk satır tek başına okunduğunda kaydırmayı durduracak, en fazla 120 karakterlik çarpıcı bir kanca cümlesi olsun.
- Sonra boş satır ve 2-4 kısa satırda videonun özü (her satır en fazla bir emoji ile başlayabilir).
- Ardından kısa bir harekete geçirici çağrı (ör. "Kaydet, lazım olacak" veya "Takip et, her gün bir yenisi").
- En sonda yorum yapmaya teşvik eden bir soru.
- Açıklamaya etiket (#) yazma; etiketler ayrı alanda.

Etiket kuralları (Instagram gönderi başına en fazla 5 etiket kabul ediyor):
- Tam olarak 5 etiket: 1 konuya özel, 2 Türkçe teknoloji topluluğu, 1 genel kategori, 1 İngilizce.
- Çok genel ve anlamsız etiketlerden kaçın; içerikle doğrudan ilgili olsun."""

_JSON_SEMASI = """{{
  "konu": "kısa konu başlığı",
  "kanca": "ekranın üstünde ilk saniyelerde görünecek en fazla 6 kelimelik başlık",
  "metin": "seslendirilecek tam metin",
  "aciklama": "kurallara uygun Instagram açıklaması (satır sonları \\n ile)",
  "etiketler": ["tam 5 etiket, # olmadan, boşluksuz"],
  "gorsel_aramalari": ["stok video aramak için 4 kısa, birbirinden farklı İngilizce arama ifadesi"],
  "ekran_notlari": [
    {{"metin": "ekranda animasyonla çıkacak en fazla 5 kelimelik kilit bilgi", "cumle_baslangici": "bu bilginin geçtiği cümlenin metindeki ilk 3 kelimesi, birebir aynı"}}
  ]{ek}
}}

ekran_notlari 3-4 madde olsun; metindeki önemli bilgileri, özellikleri, adımları veya rakamları özetlesin."""


def _istem(kategori: str, eski_konular: list[str]) -> str:
    eskiler = "\n".join(f"- {k}" for k in eski_konular[-60:]) or "- (henüz yok)"
    return f"""Türkçe bir Instagram Reels teknoloji hesabı için içerik hazırla.

İçerik türü: {KATEGORILER[kategori]}

Daha önce işlenen konular (bunları ve çok benzerlerini TEKRARLAMA):
{eskiler}

{_ORTAK_KURALLAR}
- Fiyat, kampanya, çıkış tarihi gibi hızla değişen bilgileri YAZMA.

Yalnızca şu JSON'u döndür:
{_JSON_SEMASI.format(ek="")}"""


def _urun_istemi(haberler: list[dict], eski_konular: list[str], eski_linkler: set[str]) -> str:
    satirlar = []
    for i, h in enumerate(haberler, 1):
        if h["link"] in eski_linkler:
            continue
        tarih = h["tarih"].strftime("%Y-%m-%d") if h.get("tarih") else "?"
        satirlar.append(f"[{i}] ({h['kaynak']}, {tarih}) {h['baslik']}\n    {h['ozet']}\n    {h['link']}")
    eskiler = "\n".join(f"- {k}" for k in eski_konular[-60:]) or "- (henüz yok)"
    return f"""Türkçe bir Instagram Reels teknoloji hesabı için YENİ ÇIKAN BİR ÜRÜNÜN ANALİZİ videosu hazırla.

Aşağıda son günlerin teknoloji haberleri var. Bunlardan, izleyicinin en çok ilgisini çekecek
yeni çıkmış veya yeni duyurulmuş TEK bir ürünü seç (telefon, bilgisayar, tablet, kulaklık, saat,
aksesuar, oyun konsolu, yapay zekâ cihazı veya uygulaması gibi). Söylenti ve sızıntıları seçme.

Haberler:
{chr(10).join(satirlar)}

Daha önce işlenen konular (TEKRARLAMA):
{eskiler}

Analiz şunları içersin: ürün ne, öne çıkan 2-3 özelliği, bir artısı ve bir eksisi ya da dikkat edilecek nokta,
kimler için mantıklı olduğu.

ÇOK ÖNEMLİ doğruluk kuralları:
- Yalnızca seçtiğin haberde yazan bilgileri kullan; haberde olmayan özellik, rakam veya fiyat UYDURMA.
- Fiyat yalnızca haberde açıkça yazıyorsa ve "açıklanan fiyat" diye belirtilerek söylenebilir.
- Emin olmadığın şeyi söyleme; "duyuruldu", "tanıtıldı" gibi haberdeki duruma uygun ifadeler kullan.

{_ORTAK_KURALLAR}

Yalnızca şu JSON'u döndür:
{_JSON_SEMASI.format(ek=',\n  "kaynak_no": seçtiğin haberin köşeli parantez içindeki numarası (sayı)')}"""


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


def _gemini_json(istem: str) -> dict:
    govde = {
        "contents": [{"parts": [{"text": istem}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
    }
    metin = _gemini_cagir(govde)
    icerik = json.loads(metin)
    for alan in ("konu", "kanca", "metin", "aciklama", "etiketler", "gorsel_aramalari"):
        if alan not in icerik:
            raise RuntimeError(f"Yapay zekâ yanıtında '{alan}' alanı eksik: {metin[:300]}")
    return icerik


def icerik_uret() -> dict:
    if not ayarlar.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil. .env dosyasına ekleyin.")

    gecmis = gecmisi_oku()
    kategori = kategori_sec(gecmis)
    eski_konular = [g["konu"] for g in gecmis]

    if kategori == "yeni_urun":
        from . import haberler as haber_modulu
        print("    Son teknoloji haberleri toplanıyor...")
        haberler = haber_modulu.son_haberler()
        eski_linkler = {g.get("kaynak_link") for g in gecmis if g.get("kaynak_link")}
        if haberler:
            icerik = _gemini_json(_urun_istemi(haberler, eski_konular, eski_linkler))
            try:
                secilen = haberler[int(icerik.get("kaynak_no")) - 1]
                icerik["kaynak_adi"] = secilen["kaynak"]
                icerik["kaynak_link"] = secilen["link"]
            except (TypeError, ValueError, IndexError):
                pass
            icerik["kategori"] = kategori
            return icerik
        print("    Uyarı: haber alınamadı; bugün teknoloji bilgisi videosu üretilecek.")
        kategori = "teknoloji_bilgisi"

    icerik = _gemini_json(_istem(kategori, eski_konular))
    icerik["kategori"] = kategori
    return icerik


def instagram_aciklamasi(icerik: dict) -> str:
    """Açıklama + (varsa) kaynak + en fazla 5 etiket. Instagram 5'ten fazla etiketi kabul etmiyor."""
    etiketler = []
    for e in icerik.get("etiketler", []):
        e = "#" + str(e).strip().lstrip("#").replace(" ", "")
        if len(e) > 1 and e.lower() not in [x.lower() for x in etiketler]:
            etiketler.append(e)
    parcalar = [icerik["aciklama"].strip()]
    if icerik.get("kaynak_adi"):
        parcalar.append(f"Kaynak: {icerik['kaynak_adi']}")
    parcalar.append(" ".join(etiketler[:5]))
    return "\n\n".join(p for p in parcalar if p)
