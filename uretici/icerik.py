"""Günün konusunu ve video metnini Gemini API ile üretir."""
import json
import time
from datetime import date

import requests

from . import ayarlar
from .animasyon import SAHNE_TURLERI

KATEGORILER = {
    "yeni_urun": "yeni çıkan veya yeni duyurulan bir teknoloji ürününün analizi",
    "ipucu": "telefon veya bilgisayar kullanımını kolaylaştıran pratik bir ipucu",
    "teknoloji_bilgisi": "günlük teknoloji bilgisi (ilginç bir teknoloji gerçeği, yeni bir gelişme veya kavramın sade anlatımı)",
}
# Günlerin yarısı yeni ürün analizi olsun: yeni ürün, ipucu, yeni ürün, bilgi, ...
DONGU = ["yeni_urun", "ipucu", "yeni_urun", "teknoloji_bilgisi"]

GECMIS_DOSYASI = ayarlar.VERI / "gecmis.json"
# Trend rehberi: "teknoloji-trend-analizi" becerisiyle hazırlanır, kullanıcı onayıyla depoya eklenir.
TREND_REHBERI = ayarlar.VERI / "trend_rehberi.md"
TREND_GECERLILIK_GUN = 45   # daha eski rehber kullanılmaz (trendler eskir)


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


_ORTAK_KURALLAR = """Anlatıcı karakteri: samimi bir abi.
- Küçük kardeşine ya da yakın arkadaşına anlatır gibi sıcak, samimi ve enerjik konuşur; anlattığı şeye gerçekten
  heyecanlanmış, "bunu sana mutlaka göstermem lazım" havasında. Heyecan anlatımdan gelir; bağırmaz, ürünü abartmaz.
- "Bak şimdi", "açık konuşayım", "inanır mısın", "şuna bi bak", "bence", "ben olsam" gibi doğal günlük ifadeleri yerinde kullanır.
- Ünlem ve soru cümleleriyle tempoyu canlı tutar; ama her cümle ünlemle bitmez, dozunda kullanır.
- Objektif bir teknoloji kanalıdır: reklam ya da övgü dili kullanmaz, ürünün artısını da eksisini de aynı açıklıkla söyler,
  kime değer, kime değmez net söyler. Abartılı vaatlerde bulunmaz.
- Kapanışı her zaman şu imza cümlesiyle yapar: "Takipte kal, yarın yine buradayım."
- Yapay zekâ kalıpları YASAK: "dijital dünyada", "teknolojinin hızla geliştiği", "hayatınızı kolaylaştıracak",
  "unutmayın", "sonuç olarak", "heyecan verici", "devrim niteliğinde", "merhaba arkadaşlar".

Kurallar:
- Seslendirme metni 60-90 kelime olsun (yaklaşık 25-35 saniye). Kısa, tempolu cümleler kur.
- İlk cümle izleyiciyi durduracak güçlü bir kanca olsun (merak, şaşırtıcı bilgi veya doğrudan fayda).
- Sade, samimi, günlük Türkçe kullan; "sen" diye hitap et.
- Kesin olarak doğru olduğundan emin olmadığın bilgiyi yazma; yaygın teknoloji efsanelerini doğruymuş gibi anlatma.
- İpucu veya bilgi her cihazda/sürümde geçerli değilse bunu kısaca belirt.
- Metinde emoji, madde işareti, parantez, tire, üç nokta veya tırnak kullanma (seslendirilecek).

Noktalama kuralları (hem metin hem seslendirme_metni için; seslendirme noktalamaya göre duraklayacak):
- Türkçe yazım kurallarına uygun noktalama kullan; her cümle nokta, soru işareti veya ünlemle bitsin.
- Virgülü yalnızca konuşurken gerçekten kısa bir nefes alınacak yere koy: sıralamalarda, "ama, yani, bak" gibi
  bağlaçlardan sonra ve uzun cümlenin doğal bölündüğü yerde.
- Anlam bütününü bölecek yere virgül koyma: özne ile yüklemin, sıfat ile adın, fiil ile nesnesinin arasına asla virgül girmesin.
- Bir cümle tek bir düşünceyi baştan sona akıcı anlatsın; çok kısa kopuk parçalar ve çok uzun cümleler kurma (en fazla 15 kelime).
- Son cümle imza cümlesi olsun.

Konuşma dili (seslendirme_metni) kuralları:
- Bir dublaj sanatçısının doğal konuştuğu gibi, günlük konuşma Türkçesiyle yaz; okunduğu gibi seslendirilecek.
- Gelecek zaman eklerini İSTİSNASIZ her fiilde konuşulduğu gibi yaz: gideceğim -> gidicem, yapacağım -> yapıcam,
  olacak -> olucak, gelecek -> gelicek, göreceksin -> görüceksin, söyleyeceğim -> söylicem, edeceğiz -> edicez,
  anlatacağım -> anlatıcam, başlayacak -> başlıcak.
- "değil" kelimesini her zaman "diil" yaz (değilim -> diilim, değildi -> diildi).
- İngilizce kelime ve marka adlarını İngilizce okunuşuyla, Türkçe harflerle ve TEK kelime olarak yaz ki İngilizce aksanla
  okunsun: iPhone -> ayfon, AirPods -> erpods, MacBook -> mekbuk, Google -> gugıl, YouTube -> yutub, Windows -> vindovs,
  WhatsApp -> vatsap, Galaxy -> gelaksi, Nothing -> nating, Bluetooth -> bılutut. Ek gelirse kesme işaretinden sonra ekle
  (ayfon'un). Ekrandaki metin (metin alanı) orijinal yazımla kalır.
- "bir" belirsizlik anlamındaysa "bi" yaz (bir şey -> bi şey, bir de -> bi de); sayı anlamındaysa "bir" kalsın.
- Abartma: "yapıyorum" gibi zaten doğal olan kelimeleri bozma, argo ve yazım hatası ekleme, anlaşılırlığı koru.
- Rakamları ve kısaltmaları okunacağı gibi yaz (ör. "1,3 inç" -> "bir virgül üç inç", "GB" -> "gigabayt").

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
  "metin": "seslendirilecek tam metin, düzgün yazım kurallarıyla (ekranda altyazı olarak görünecek)",
  "seslendirme_metni": "metin ile AYNI cümleler, aynı sırada, aynı sayıda ve aynı noktalamayla; ama konuşma dilinde yazılmış hali",
  "vurgular": ["metinde birebir geçen, altyazıda renkli gösterilecek 5-8 önemli kelime (her cümleden en fazla 1-2)"],
  "aciklama": "kurallara uygun Instagram açıklaması (satır sonları \\n ile)",
  "etiketler": ["tam 5 etiket, # olmadan, boşluksuz"],
  "gorsel_aramalari": ["stok video aramak için 4 kısa, birbirinden farklı İngilizce arama ifadesi"],
  "ekran_notlari": [
    {{"metin": "ekranda animasyonla çıkacak en fazla 5 kelimelik kilit bilgi", "cumle_baslangici": "bu bilginin geçtiği cümlenin metindeki ilk 3 kelimesi, birebir aynı"}}
  ],
  "sahneler": [
    {{"tur": "sahne türü", "...": "türe göre alanlar"}}
  ]{ek}
}}

ekran_notlari 3-4 madde olsun; metindeki önemli bilgileri, özellikleri, adımları veya rakamları özetlesin.

ANİMASYON: Video stok görüntü yerine animasyonla anlatılır. "sahneler" listesinde metindeki HER cümle için tam bir sahne
olsun (cümle sayısı kadar sahne, aynı sırada). Her sahne o cümlenin anlattığı sistemi, ayarı, özelliği veya bilgiyi canlandırsın:
ayar anlatılıyorsa telefon_ayar, kısayol anlatılıyorsa kisayol, menü yolu anlatılıyorsa adimlar, sayı/değer söyleniyorsa rakam
veya karsilastirma, pil/şarj anlatılıyorsa pil, uyarı/istisna söyleniyorsa uyari. İmza cümlesi için hesabı hatırlatan bir ikon
sahnesi (ör. ikon "zil", baslik "Takipte kal") kullan.
""" + SAHNE_TURLERI.replace("{", "{{").replace("}", "}}")  # .format() ile kullanıldığı için


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


# f-string içinde ters bölü kullanılamadığı için (Python 3.11) ayrı tanımlanır.
_KAYNAK_NO_ALANI = ',\n  "kaynak_no": seçtiğin haberin köşeli parantez içindeki numarası (sayı)'


def _urun_istemi(haberler: list[dict], eski_konular: list[str], eski_linkler: set[str]) -> str:
    satirlar = []
    for i, h in enumerate(haberler, 1):
        if h["link"] in eski_linkler:
            continue
        tarih = h["tarih"].strftime("%Y-%m-%d") if h.get("tarih") else "?"
        gorsel = " [görsel var]" if h.get("gorseller") else ""
        satirlar.append(f"[{i}] ({h['kaynak']}, {tarih}){gorsel} {h['baslik']}\n    {h['ozet']}\n    {h['link']}")
    eskiler = "\n".join(f"- {k}" for k in eski_konular[-60:]) or "- (henüz yok)"
    return f"""Türkçe bir Instagram Reels teknoloji hesabı için YENİ ÇIKAN BİR ÜRÜNÜN ANALİZİ videosu hazırla.

Aşağıda son günlerin teknoloji haberleri var. Bunlardan, izleyicinin en çok ilgisini çekecek
yeni çıkmış veya yeni duyurulmuş TEK bir ürünü seç (telefon, bilgisayar, tablet, kulaklık, saat,
aksesuar, oyun konsolu, yapay zekâ cihazı veya uygulaması gibi). Söylenti ve sızıntıları seçme.
Videoda ürünün gerçek görselleri kullanılacağı için, mümkünse "[görsel var]" işaretli haberlerden seç.

Haberler:
{chr(10).join(satirlar)}

Daha önce işlenen konular (TEKRARLAMA):
{eskiler}

Analiz OBJEKTİF olsun ve şu sırayla ilerlesin: ürün ne (tek cümle), 4 artısı, 2 eksisi, kime değer / kime değmez.
Bu videoda seslendirme metni 85-110 kelime olabilir (4 artı ve 2 eksi sığsın diye); cümleler yine kısa ve tempolu olsun.
Sahneler: ilk cümlenin sahnesi "urun" olsun (ürünün gerçek fotoğrafı, baslik = ürün adı). Her artı cümlesinin sahnesinde
"etiket":"arti", her eksi cümlesinin sahnesinde "etiket":"eksi" olsun (ikon sahnesi ya da özelliği daha iyi canlandıran rakam,
pil, karsilastirma, hiz sahnesi; bu türlerde etiket gerekmez). "Kime değer" cümlesi için kontrol_listesi kullanabilirsin.
Ürünün adını ve model numarasını seçtiğin haberin başlığında ve özetinde geçtiği gibi BİREBİR kullan; model numarası uydurma
veya değiştirme (haber "AirPods 4" diyorsa "AirPods 5" yazma).
Artıların her biri farklı bir özellik olsun (aynı şeyi iki kez söyleme) ve yalnızca haberde geçen bilgilere dayansın.
Artılar ve eksiler dengeli olsun; eksileri yumuşatma, artıları abartma. Her artı ve eksiyi ayrı kısa bir cümleyle söyle.
Eksilere geçerken bunu sesli olarak da belirt (ör. "Gelelim eksilere", "Şimdi işin öbür tarafı"); ekranda o an EKSİLER başlığı çıkacak.

Eksiler için doğruluk kuralı: eksi uydurma. Eksi olarak yalnızca şunları kullan:
- haberde açıkça geçen bir dezavantaj (yüksek fiyat, eksik özellik, sınırlı satış bölgesi, abonelik şartı vb.),
- haberden çıkan dürüst bir belirsizlik (ör. "fiyatı henüz açıklanmadı", "Türkiye'ye gelip gelmeyeceği belli değil",
  "pil ömrü henüz bağımsız testlerle doğrulanmadı", "ilk nesil ürün, yazılım olgunlaşmamış olabilir").

Bu videoda ekran_notlari ARTI ve EKSİLERDİR: tam 6 madde, önce 4 artı sonra 2 eksi, metinde söylendikleri sırayla.
Her madde en fazla 4 kelime olsun (ör. "1,3 inç dokunmatik ekran", "Fiyatı henüz belli değil") ve ek olarak
"tur" alanı taşısın: artılar için "arti", eksiler için "eksi". Örnek:
{{"metin": "1,3 inç dokunmatik ekran", "cumle_baslangici": "metindeki cümlenin ilk 3 kelimesi", "tur": "arti"}}
Ekranda ürün görselinin yanında oklarla sırayla listelenecekler.

ÇOK ÖNEMLİ doğruluk kuralları:
- Yalnızca seçtiğin haberde yazan bilgileri kullan; haberde olmayan özellik, rakam veya fiyat UYDURMA.
- Fiyat yalnızca haberde açıkça yazıyorsa ve "açıklanan fiyat" diye belirtilerek söylenebilir.
- Emin olmadığın şeyi söyleme; "duyuruldu", "tanıtıldı" gibi haberdeki duruma uygun ifadeler kullan.

{_ORTAK_KURALLAR}

Yalnızca şu JSON'u döndür:
{_JSON_SEMASI.format(ek=_KAYNAK_NO_ALANI)}"""


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


def _trend_rehberi() -> str:
    """Güncel trend rehberini istemin sonuna eklenecek biçimde döndürür (yoksa veya eskiyse boş).

    Rehberin ilk satırlarında "Tarih: YYYY-AA-GG" bulunur; 45 günden eskiyse kullanılmaz.
    """
    import re

    if not TREND_REHBERI.exists():
        return ""
    metin = TREND_REHBERI.read_text(encoding="utf-8").strip()
    tarih = re.search(r"Tarih:\s*(\d{4}-\d{2}-\d{2})", metin[:300])
    if not tarih or (date.today() - date.fromisoformat(tarih.group(1))).days > TREND_GECERLILIK_GUN:
        print("    Uyarı: trend rehberi yok veya eskimiş; kullanılmadı.")
        return ""
    return ("\n\nGÜNCEL TREND REHBERİ (izleyicinin şu an en çok ilgilendiği konular ve tutan kanca/format kalıpları).\n"
            "Konu seçiminde ve kanca/akış kurarken buna yönel; ama yukarıdaki doğruluk, üslup, konuşma dili ve "
            "noktalama kurallarını DEĞİŞTİRMEZ. Başka içeriklerin cümlelerini kopyalama, kalıbı kendi konuna uyarla.\n"
            + metin[:6000])


def _gemini_json(istem: str) -> dict:
    istem = istem + _trend_rehberi()
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
                icerik["kaynak_gorselleri"] = secilen.get("gorseller", [])
                icerik["kaynak_baslik"] = secilen.get("baslik", "")
                # Aynı ürünü anlatan diğer sitelerin haberleri: daha fazla gerçek ürün görseli/videosu için.
                icerik["ilgili_kaynaklar"] = haber_modulu.ilgili_haberler(secilen, haberler)
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
        if icerik.get("urun_gorseli_var"):
            parcalar.append(f"Kaynak ve ürün görselleri: {icerik['kaynak_adi']}")
        else:
            parcalar.append(f"Kaynak: {icerik['kaynak_adi']}")
    parcalar.append(" ".join(etiketler[:5]))
    return "\n\n".join(p for p in parcalar if p)
