"""Sabah bilgilendirme Reels'i: konuyla ilgili gerçek bir fotoğraf + tek tek gelip okunan 6-7 madde.

Akış: Gemini ile madde listesi -> (varsa) konuyla doğrulanmış gerçek fotoğraf -> seslendirme ->
maddeler konuşuldukça ekrana gelen dikey video. Uygun fotoğraf bulunamazsa fotoğraf koyulmaz.
"""
import json
import random
import subprocess
from datetime import date
from pathlib import Path

from . import ayarlar, icerik, seslendirme, video
from .animasyon import SAHNE_TURLERI
from .video import FPS, G, Y, SARI, BEYAZ, KOYU, tr_buyuk, _temiz, _yazi_genisligi, _yuvarlak_kutu, _zaman

SABAH_GECMIS = ayarlar.VERI / "sabah_gecmis.json"
IMZA = "Takipte kal, akşam yine buradayım."

# ---------- içerik ----------

_SABAH_JSON = """{
  "konu": "kısa konu başlığı",
  "baslik": "ekranın üstünde video boyunca kalacak başlık, en fazla 6 kelime (ör. 'Telefonunda kapatman gereken 7 ayar')",
  "giris": "ilk cümle: izleyiciyi durduran kanca, düzgün yazımla",
  "giris_konusma": "aynı cümle, konuşma dilinde",
  "maddeler": [
    {"ekran": "ekranda görünecek en fazla 5 kelimelik madde", "cumle": "maddeyi anlatan TEK cümle, en fazla 14 kelime, düzgün yazımla", "cumle_konusma": "aynı cümle, konuşma dilinde", "sahne": {"tur": "bu maddeyi canlandıran sahne"}}
  ],
  "giris_sahne": {"tur": "giriş cümlesini canlandıran sahne"},
  "kapanis_sahne": {"tur": "kapanış cümlesini canlandıran sahne"},
  "kapanis": "tek cümlelik kapanış; en sonda imza cümlesi ayrıca eklenecek, sen yazma",
  "kapanis_konusma": "aynı cümle, konuşma dilinde",
  "aciklama": "kurallara uygun Instagram açıklaması (satır sonları \\n ile)",
  "etiketler": ["tam 5 etiket, # olmadan, boşluksuz"],
  "gorsel": {
    "nesne": "fotoğrafta açıkça görünmesi gereken şey, Türkçe (ör. 'akıllı telefonun ayarlar ekranı', 'elektrikli araç şarj ederken', 'araç içi navigasyon cihazı')",
    "aramalar": ["bu gerçek fotoğrafı bulmak için 3 kısa İngilizce arama ifadesi"]
  }
}"""


def _sabah_istemi(eski_konular: list[str]) -> str:
    eskiler = "\n".join(f"- {k}" for k in eski_konular[-60:]) or "- (yok)"
    return f"""Sen @feriduntalak adlı Türkçe teknoloji Instagram hesabının içerik yazarısın.
Bu sabah paylaşılacak BİLGİLENDİRME LİSTESİ hazırlıyorsun: telefon, bilgisayar, internet, akıllı ev, elektrikli araç,
navigasyon, giyilebilir cihaz gibi günlük teknolojide işe yarayan 7 maddelik bir liste (ör. "Telefonunda kapatman gereken
7 ayar", "Elektrikli araç alırken bakman gereken 7 şey", "Bilgisayarın yavaşladıysa yapman gereken 7 şey").

Daha önce işlenen konular (TEKRARLAMA, benzerini de seçme):
{eskiler}

Liste kuralları:
- Tam 7 madde (en az 6). Her madde farklı, somut ve uygulanabilir bir bilgi olsun; aynı şeyi iki kez söyleme.
- Yalnızca kesin doğru, genel geçer bilgiler; sürüme göre değişen menü yolu veya uydurma rakam verme. Cihaza/sürüme göre
  değişiyorsa bunu cümlede kısaca belirt.
- "ekran" alanı en fazla 5 kelime, büyük harfe çevrilecek, ekranda tek satıra sığsın.
- Her "cumle" tek bir cümle olsun; içinde nokta, soru veya ünlem işaretiyle ikinci bir cümle başlamasın.
- Toplam konuşma 100-130 kelime (yaklaşık 40-50 saniye) olsun.
- Fotoğraf: konunun gerçek bir fotoğrafı neyi göstermeliyse "gorsel.nesne" alanına yaz (telefon içeriğiyse ilgili ekran,
  değilse ilgili cihaz). Aramalar gerçek fotoğraf sitelerinde (Pixabay, Wikimedia Commons) bulunabilecek kadar sade olsun.

{icerik._ORTAK_KURALLAR}

Bu içeriğe özel istisnalar: uzunluk kuralı yukarıdaki liste kurallarıdır; imza cümlesini sen yazma (sistem
"{IMZA}" cümlesini kendisi ekler); "metin", "seslendirme_metni", "vurgular", "gorsel_aramalari" ve "ekran_notlari"
alanları bu içerikte YOK.

ANİMASYON: Görüntü animasyonla anlatılır. Giriş, her madde ve kapanış için o cümlenin anlattığını canlandıran bir sahne seç
("giris_sahne", maddelerdeki "sahne", "kapanis_sahne"). Sahne küçük bir alanda gösterilecek: telefon_ayar, kisayol, pil, rakam,
ikon, adimlar, uyari, hiz, karsilastirma gibi sade sahneleri tercih et; "urun" sahnesini kullanma.
{SAHNE_TURLERI}

Yalnızca şu JSON'u döndür:
{_SABAH_JSON}"""


def sabah_gecmisi() -> list[dict]:
    if SABAH_GECMIS.exists():
        return json.loads(SABAH_GECMIS.read_text(encoding="utf-8"))
    return []


def sabah_gecmise_ekle(veri: dict) -> None:
    gecmis = sabah_gecmisi()
    gecmis.append({"tarih": date.today().isoformat(), "kategori": "bilgi_listesi", "konu": veri["konu"]})
    SABAH_GECMIS.parent.mkdir(parents=True, exist_ok=True)
    SABAH_GECMIS.write_text(json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8")


def icerik_uret() -> dict:
    if not ayarlar.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY tanımlı değil.")
    eski = [g["konu"] for g in sabah_gecmisi()] + [g["konu"] for g in icerik.gecmisi_oku()]
    govde = {
        "contents": [{"parts": [{"text": _sabah_istemi(eski) + icerik._trend_rehberi()}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0},
    }
    metin = icerik._gemini_cagir(govde)
    veri = json.loads(metin)
    for alan in ("konu", "baslik", "giris", "maddeler", "kapanis", "aciklama", "etiketler"):
        if alan not in veri:
            raise RuntimeError(f"Yapay zekâ yanıtında '{alan}' alanı eksik: {metin[:300]}")
    veri["maddeler"] = [m for m in veri["maddeler"] if m.get("ekran") and m.get("cumle")][:7]
    if len(veri["maddeler"]) < 6:
        raise RuntimeError(f"Bilgilendirme en az 6 madde olmalı, {len(veri['maddeler'])} geldi.")
    veri["kategori"] = "bilgi_listesi"
    return veri


def konusma_parcalari(veri: dict) -> tuple[list[str], list[str]]:
    """Seslendirilecek parçalar (konuşma dili, kurallar uygulanmış) ve aynı parçaların düzgün yazımı.

    Parça sırası: giriş, maddeler (her biri tek cümle), kapanış, imza.
    """
    yazi = [veri["giris"]] + [m["cumle"] for m in veri["maddeler"]] + [veri["kapanis"], IMZA]
    ham = ([veri.get("giris_konusma") or veri["giris"]]
           + [m.get("cumle_konusma") or m["cumle"] for m in veri["maddeler"]]
           + [veri.get("kapanis_konusma") or veri["kapanis"], IMZA])
    konusma = [seslendirme.konusma_diline_cevir(seslendirme.ingilizce_okunus(seslendirme.sayilari_oku(
        seslendirme.noktalamayi_duzelt(p)))) for p in ham]
    return konusma, [seslendirme.noktalamayi_duzelt(p) for p in yazi]


def parca_zamanlari(parcalar: list[str], kelimeler: list[dict], toplam: float) -> list[float]:
    """Her parçanın konuşmada başladığı an (kelime sayısına göre; sayılar tutmazsa orantılı)."""
    sayilar = [len(p.split()) for p in parcalar]
    toplam_kelime = sum(sayilar)
    zamanlar, i = [], 0
    for s in sayilar:
        if kelimeler:
            j = i if len(kelimeler) == toplam_kelime else int(i * len(kelimeler) / max(1, toplam_kelime))
            zamanlar.append(kelimeler[min(j, len(kelimeler) - 1)]["baslangic"])
        else:
            zamanlar.append(toplam * i / max(1, toplam_kelime))
        i += s
    return zamanlar


def instagram_aciklamasi(veri: dict) -> str:
    metin = icerik.instagram_aciklamasi(veri)
    if veri.get("foto_kaynak"):
        govde, _, etiketler = metin.rpartition("\n\n")
        metin = f"{govde}\n\nGörsel: {veri['foto_kaynak']}\n\n{etiketler}"
    return metin


# ---------- görüntü ----------

BASLIK_Y = 300
FOTO_ALAN = (900, 520)        # fotoğraf kartının en büyük boyutu
FOTO_MERKEZ_Y = 690
MADDE_X = 175                 # madde yazısının başladığı x
NO_X = 110                    # numara rozetinin merkezi


def _madde_yerlesimi(foto_var: bool, adet: int) -> tuple[int, int]:
    if foto_var:
        return 1030, 112 if adet >= 7 else 128
    return 560, 150


def ass_yaz(veri: dict, zamanlar: list[float], toplam: float, yol: Path, foto_var: bool) -> list[float]:
    """Başlık, hesap etiketi ve konuşuldukça tek tek gelen maddeler. Maddelerin geliş anlarını döndürür."""
    font = ayarlar.ALTYAZI_FONT
    bicim = ("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
             "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
             "Alignment, MarginL, MarginR, MarginV, Encoding")
    s = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {G}", f"PlayResY: {Y}", "WrapStyle: 0",
        "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", bicim,
        f"Style: Baslik,{font},62,&H00000000,&H00000000,&H0000D7FF,&H00000000,-1,0,0,0,100,100,0,0,3,22,0,5,80,80,0,1",
        f"Style: Madde,{font},46,&H00FFFFFF,&H00FFFFFF,&H30201812,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,4,{MADDE_X},50,0,1",
        f"Style: No,{font},46,&H00000000,&H00000000,&H0000D7FF,&H00000000,-1,0,0,0,100,100,0,0,3,14,0,5,0,0,0,1",
        f"Style: Cizim,{font},20,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1",
        f"Style: Hesap,{font},30,{KOYU[:-1]},{KOYU[:-1]},&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,0,0,5,0,0,0,1",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    def olay(katman, bas, bit, stil, metin):
        s.append(f"Dialogue: {katman},{_zaman(bas)},{_zaman(bit)},{stil},,0,0,0,,{metin}")

    if ayarlar.HESAP_ETIKETI:
        hg = _yazi_genisligi(ayarlar.HESAP_ETIKETI, 30) + 44
        olay(4, 0, toplam, "Cizim", rf"{{\pos({int((G - hg) / 2)},{150 - 27})\1a&H40&\p1}}{_yuvarlak_kutu(hg, 54, 27)}{{\p0}}")
        olay(5, 0, toplam, "Hesap", rf"{{\pos({G // 2},150)}}" + _temiz(ayarlar.HESAP_ETIKETI))

    # Başlık: video boyunca üstte; açılışta büyüyerek gelir.
    olay(3, 0, toplam, "Baslik", rf"{{\pos({G // 2},{BASLIK_Y})\fscx40\fscy40\t(0,180,\fscx106\fscy106)"
                                 rf"\t(180,280,\fscx100\fscy100)}}" + tr_buyuk(_temiz(veri["baslik"])))

    maddeler = veri["maddeler"]
    y0, aralik = _madde_yerlesimi(foto_var, len(maddeler))
    gelisler = []
    onceki = 1.2
    for i, m in enumerate(maddeler):
        bas = max(zamanlar[1 + i], onceki + 0.6)
        onceki = bas
        gelisler.append(bas)
    for i, m in enumerate(maddeler):
        bas, y = gelisler[i], y0 + i * aralik
        sonraki = gelisler[i + 1] if i + 1 < len(maddeler) else zamanlar[1 + len(maddeler)]
        yazi = tr_buyuk(_temiz(m["ekran"]))
        genislik = _yazi_genisligi(yazi, 46)
        boyut = 46 if genislik <= G - MADDE_X - 60 else max(32, int(46 * (G - MADDE_X - 60) / genislik))
        # Numara rozeti: büyüyerek belirir.
        olay(2, bas, toplam, "No", rf"{{\pos({NO_X},{y})\fscx30\fscy30\t(0,160,\fscx100\fscy100)}}{i + 1}")
        # Madde: sağdan kayarak gelir; okunurken sarı, sonra beyaz.
        giris = rf"\move({G + 40},{y},{MADDE_X},{y},0,240)"
        olay(2, bas, max(sonraki, bas + 0.3), "Madde", rf"{{\fs{boyut}{giris}\1c{SARI}}}" + yazi)
        if sonraki < toplam:
            olay(2, sonraki, toplam, "Madde", rf"{{\fs{boyut}\pos({MADDE_X},{y})\1c{BEYAZ}}}" + yazi)
    yol.write_text("\n".join(s) + "\n", encoding="utf-8")
    return gelisler


def _arka_plan_karesi(foto: Path, hedef: Path) -> Path:
    """Bulanık fotoğraf zemini üzerinde beyaz çerçeveli fotoğraf kartı (2 kat çözünürlükte)."""
    G2, Y2 = 2 * G, 2 * Y
    fg, fy = 2 * FOTO_ALAN[0], 2 * FOTO_ALAN[1]
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(foto), "-filter_complex",
        f"[0:v]format=rgb24,split[b][f];"
        f"[b]scale={G2}:{Y2}:force_original_aspect_ratio=increase,crop={G2}:{Y2},boxblur=60:3,eq=brightness=-0.35[bb];"
        f"[f]scale={fg}:{fy}:force_original_aspect_ratio=decrease,pad=iw+20:ih+20:10:10:white[ff];"
        f"[bb][ff]overlay=x=(W-w)/2:y={2 * FOTO_MERKEZ_Y}-h/2",
        "-frames:v", "1", str(hedef)], check=True)
    return hedef


def video_olustur(ses: Path, altyazi: Path, cikti: Path, gelisler: list[float], foto: Path | None = None,
                  muzik: Path | None = None, taban: Path | None = None) -> Path:
    toplam = video.sure_olc(ses) + 0.5
    kare = round(toplam * FPS)
    girdiler: list[str] = []
    if taban:
        # Animasyonlu zemin (sahneler animasyon motorunda çizildi).
        girdiler += ["-i", str(Path(taban).resolve())]
        arka_filtre = f"[0:v]fps={FPS},format=yuv420p"
    elif foto:
        arka = _arka_plan_karesi(foto, altyazi.parent / "bilgi_arka.png")
        girdiler += ["-loop", "1", "-framerate", str(FPS), "-t", f"{toplam:.3f}", "-i", str(arka.resolve())]
        arka_filtre = (f"[0:v]zoompan=z='1+0.05*on/{kare}':x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':"
                       f"d=1:s={G}x{Y}:fps={FPS},format=yuv420p")
    else:
        # Fotoğraf yoksa: yavaşça akan koyu renk geçişi.
        girdiler += ["-f", "lavfi", "-i",
                     f"gradients=s={G}x{Y}:c0=0x0b1220:c1=0x1d2b53:c2=0x0f3b46:c3=0x231a3d:n=4:speed=0.004:"
                     f"d={toplam:.3f}:r={FPS}"]
        arka_filtre = "[0:v]format=yuv420p"
    filtreler = [f"{arka_filtre},subtitles={altyazi.name}[son]"]
    girdiler += ["-i", str(ses.resolve())]
    ses_i, sonraki = 1, 2
    karisim, konusma = [], f"[{ses_i}:a]"
    if muzik:
        girdiler += ["-stream_loop", "-1", "-i", str(Path(muzik).resolve())]
        filtreler.append(f"[{ses_i}:a]asplit=2[konus][yan]")
        filtreler.append(f"[{sonraki}:a]aformat=sample_rates=44100:channel_layouts=mono,atrim=0:{toplam:.3f},"
                         f"volume={ayarlar.MUZIK_SEVIYE},afade=t=in:d=1,afade=t=out:st={max(toplam - 1.5, 0):.3f}:d=1.5[m0]")
        filtreler.append("[m0][yan]sidechaincompress=threshold=0.02:ratio=4:attack=20:release=400[muz]")
        konusma, sonraki = "[konus]", sonraki + 1
        karisim.append("[muz]")
    efekt = video._efekt_dosyalari(altyazi.parent)
    olaylar = [("whoosh", 0.0, 0.16)] + [("pop", t, 0.5) for t in gelisler]
    for k, (ad, zaman, seviye) in enumerate(olaylar):
        girdiler += ["-i", str(efekt[ad].resolve())]
        ms = int(zaman * 1000)
        filtreler.append(f"[{sonraki}:a]adelay={ms}|{ms},volume={seviye}[e{k}]")
        karisim.append(f"[e{k}]")
        sonraki += 1
    filtreler.append(f"{konusma}{''.join(karisim)}amix=inputs={len(karisim) + 1}:duration=first:"
                     f"dropout_transition=0:normalize=0[ses]")
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *girdiler,
        "-filter_complex", ";".join(filtreler), "-map", "[son]", "-map", "[ses]", "-t", f"{toplam:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-movflags", "+faststart", cikti.name,
    ], cwd=altyazi.parent, check=True)
    return cikti


SAHNE_ALANI = {"x": 60, "y": 375, "w": 960, "h": 625}   # maddelerin üstündeki animasyon alanı


def _animasyon_tabani(veri: dict, zamanlar: list[float], toplam: float, klasor: Path, foto: Path | None) -> Path:
    """Giriş, her madde ve kapanış için sahne; doğrulanmış gerçek fotoğraf varsa girişte o gösterilir."""
    from . import animasyon

    giris = {"tur": "urun", "gorsel": 0} if foto else (veri.get("giris_sahne") or {})
    plan = [giris] + [m.get("sahne") or {} for m in veri["maddeler"]] + [veri.get("kapanis_sahne") or {}]
    plan = [p if p.get("tur") != "urun" or (foto and i == 0) else {} for i, p in enumerate(plan)]
    basliklar = [""] + [m["ekran"] for m in veri["maddeler"]] + [""]
    # Kapanış ve imza aynı sahnede kalır.
    sahneler = animasyon.sahneleri_hazirla(plan, zamanlar[:len(plan)], toplam, basliklar)
    (klasor / "sahneler.json").write_text(animasyon.plan_json(sahneler), encoding="utf-8")
    return animasyon.video_uret(sahneler, toplam, klasor / "animasyon.mp4", alan=SAHNE_ALANI,
                                gorseller=[foto] if foto else [])


def uret(klasor: Path) -> dict:
    """Sabah bilgilendirme videosunu üretir; içerik verisini döndürür (video: klasor/video.mp4)."""
    from . import foto as foto_modulu

    print("1/4 Bilgilendirme listesi hazırlanıyor...")
    veri = icerik_uret()
    print(f"    Konu: {veri['konu']} ({len(veri['maddeler'])} madde)")

    print("2/4 Konuyla ilgili gerçek fotoğraf aranıyor...")
    g = veri.get("gorsel") or {}
    bulunan = foto_modulu.dogrulanmis_foto(veri["konu"], g.get("nesne", ""), g.get("aramalar", []),
                                           klasor / "foto")
    foto = None
    if bulunan:
        foto, veri["foto_kaynak"] = bulunan["yol"], bulunan["kaynak"]
        print(f"    Fotoğraf: {bulunan['kaynak']}")
    else:
        print("    Uygun fotoğraf bulunamadı; fotoğrafsız tasarım kullanılacak.")

    print("3/4 Seslendiriliyor...")
    ses = klasor / "ses.mp3"
    konusma, _ = konusma_parcalari(veri)
    bolumler = seslendirme.seslendir(" ".join(konusma), ses)
    kelimeler = seslendirme.kelimelere_bol(bolumler)
    toplam = video.sure_olc(ses) + 0.5
    zamanlar = parca_zamanlari(konusma, kelimeler, toplam)

    print("4/4 Video oluşturuluyor...")
    altyazi = klasor / "altyazi.ass"
    taban = None
    if ayarlar.ANIMASYON:
        try:
            taban = _animasyon_tabani(veri, zamanlar, toplam, klasor, foto)
        except Exception as hata:  # animasyon olmazsa fotoğraflı/sade tasarımla devam
            print(f"    Uyarı: animasyon üretilemedi ({type(hata).__name__}: {hata}); sade tasarım kullanılacak.")
    gelisler = ass_yaz(veri, zamanlar, toplam, altyazi, foto_var=bool(foto) or bool(taban))
    muzik_dosyasi = None
    if ayarlar.MUZIK:
        from . import muzik
        muzik_dosyasi = muzik.muzik_hazirla("ipucu", toplam, klasor / "muzik.wav",
                                            tohum=random.randrange(1 << 30))
    video_olustur(ses, altyazi, klasor / "video.mp4", gelisler, foto=foto, muzik=muzik_dosyasi, taban=taban)
    return veri
