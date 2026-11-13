"""Günün içeriğini üretir: metin -> seslendirme -> stok görüntü -> video.

Kullanım:
    python calistir.py              Günün videosunu üretir (paylaşım henüz eklenmedi)
    python calistir.py --deneme     Yapay zekâ ve Pexels anahtarı olmadan örnek metinle video üretir
    python calistir.py --sabah      Sabah bilgilendirme Reels'ini üretir (fotoğraf + tek tek gelen 6-7 madde)
"""
import argparse
import json
import shutil
import sys
import traceback
from datetime import datetime

from uretici import ayarlar, gorseller, icerik, seslendirme, video

ORNEK_ICERIK = {
    "kategori": "ipucu",
    "konu": "Telefonda ekran görüntüsünden metin kopyalama",
    "kanca": "Bunu bilen çok az kişi var",
    "metin": (
        "Telefonundaki bir fotoğraftaki yazıyı tek tek yazmakla uğraşma. "
        "Galeride fotoğrafı aç, yazının üzerine basılı tut ve metni seç. "
        "Artık kopyalayıp istediğin yere yapıştırabilirsin. "
        "Bu özellik hem iPhone'da hem de çoğu Android telefonda var. "
        "Bu tarz pratik ipuçları için takip etmeyi unutma."
    ),
    "aciklama": "Fotoğraftaki yazıyı saniyeler içinde kopyala. Sen bu özelliği biliyor muydun?",
    "etiketler": ["teknoloji", "ipucu", "telefon", "iphone", "android", "techtips"],
    "gorsel_aramalari": ["smartphone hand", "phone screen scrolling", "person using phone", "photo gallery phone"],
    "ekran_notlari": [
        {"metin": "Fotoğrafı galeride aç", "cumle_baslangici": "Galeride fotoğrafı aç"},
        {"metin": "Yazıya basılı tut", "cumle_baslangici": "yazının üzerine basılı"},
        {"metin": "Kopyala ve yapıştır", "cumle_baslangici": "Artık kopyalayıp istediğin"},
        {"metin": "iPhone ve Android'de var", "cumle_baslangici": "Bu özellik hem"},
    ],
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Instagram günlük video üretici")
    ap.add_argument("--deneme", action="store_true", help="Örnek metinle, yapay zekâ kullanmadan video üret")
    ap.add_argument("--sabah", action="store_true", help="Sabah bilgilendirme Reels'ini üret")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("Hata: FFmpeg bulunamadı. Kurulum için KURULUM.md dosyasına bakın.")
        return 1

    klasor = ayarlar.CIKTI / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    klasor.mkdir(parents=True, exist_ok=True)

    if args.sabah:
        return sabah(klasor)

    try:
        print("1/4 İçerik hazırlanıyor...")
        veri = ORNEK_ICERIK if args.deneme else icerik.icerik_uret()
        print(f"    Konu: {veri['konu']} ({veri['kategori']})")

        print("2/4 Seslendiriliyor...")
        ses = klasor / "ses.mp3"
        konusma = seslendirme.konusma_diline_cevir(seslendirme.ingilizce_okunus(seslendirme.sayilari_oku(
            seslendirme.noktalamayi_duzelt(veri.get("seslendirme_metni") or veri["metin"]))))
        bolumler = seslendirme.seslendir(konusma, ses)
        kelimeler = seslendirme.yaziya_esle(seslendirme.kelimelere_bol(bolumler), konusma,
                                            seslendirme.noktalamayi_duzelt(veri["metin"]))
        gruplar = seslendirme.gruplara_ayir(kelimeler)

        if ayarlar.ANIMASYON and not args.deneme:
            try:
                return _animasyonlu(veri, klasor, ses, kelimeler, gruplar, konusma)
            except Exception:
                # Animasyon üretilemezse o gün eski yöntemle (stok görüntü / ürün görseli) devam et; paylaşım aksamasın.
                print("    Uyarı: animasyon üretilemedi, eski yönteme geçiliyor:\n" + traceback.format_exc())

        print("3/4 Stok görüntüler indiriliyor...")
        urun_gorselleri, urun_videolari = [], []
        if veri.get("kaynak_link"):
            from uretici import haberler
            urun_gorselleri, urun_videolari = haberler.urun_medyasini_indir(
                {"link": veri["kaynak_link"], "gorseller": veri.get("kaynak_gorselleri", []),
                 "baslik": veri.get("kaynak_baslik", ""), "konu": veri.get("konu", "")},
                klasor / "urun_gorselleri", ilgili=veri.get("ilgili_kaynaklar", []))
            veri["urun_gorseli_var"] = bool(urun_gorselleri)
        if urun_gorselleri:
            # Ürün analizinde yalnızca ürünün kendi görselleri ve videoları; ilgisiz stok görüntü yok.
            klipler = urun_videolari
        else:
            klipler = gorseller.videolari_indir(veri["gorsel_aramalari"], klasor / "klipler",
                                               adet=ayarlar.KLIP_SAYISI)

        print("4/4 Video oluşturuluyor...")
        altyazi = klasor / "altyazi.ass"
        toplam = video.sure_olc(ses) + 0.5
        kartlar = video.not_zamanlari(veri.get("ekran_notlari") or [], kelimeler, toplam)
        vitrin = video.vitrin_plani(kartlar, toplam) if urun_gorselleri else None
        muzik_dosyasi = None
        if ayarlar.MUZIK:
            from uretici import muzik
            muzik_dosyasi = muzik.muzik_hazirla(veri["kategori"], toplam, klasor / "muzik.wav")
        video.ass_yaz(gruplar, veri["kanca"], kartlar, toplam, altyazi, vitrin=vitrin,
                      vurgular=veri.get("vurgular"))
        cikti = video.video_olustur(ses, klipler, altyazi, klasor / "video.mp4", resimler=urun_gorselleri,
                                    vitrin=vitrin, muzik=muzik_dosyasi)

        (klasor / "aciklama.txt").write_text(icerik.instagram_aciklamasi(veri), encoding="utf-8")
        (klasor / "icerik.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.deneme:
            icerik.gecmise_ekle(veri)

        print(f"Tamam: {cikti}")
    except Exception:
        hata = traceback.format_exc()
        (klasor / "hata.txt").write_text(hata, encoding="utf-8")
        print(hata)
        print(f"HATA: Ayrıntılar şu dosyaya yazıldı: {klasor / 'hata.txt'}")
        return 1
    return 0


def _animasyonlu(veri, klasor, ses, kelimeler, gruplar, konusma) -> int:
    """Animasyonlu video: her cümle için yapay zekânın seçtiği sahne, üstüne altyazı ve ses."""
    from uretici import animasyon

    print("3/4 Animasyon hazırlanıyor...")
    urun_gorselleri = []
    if veri.get("kaynak_link"):
        from uretici import haberler
        urun_gorselleri, _ = haberler.urun_medyasini_indir(
            {"link": veri["kaynak_link"], "gorseller": veri.get("kaynak_gorselleri", []),
             "baslik": veri.get("kaynak_baslik", ""), "konu": veri.get("konu", "")},
            klasor / "urun_gorselleri", ilgili=veri.get("ilgili_kaynaklar", []), en_fazla_video=0)
        veri["urun_gorseli_var"] = bool(urun_gorselleri)
    toplam = video.sure_olc(ses) + 0.5
    yazi = seslendirme.noktalamayi_duzelt(veri["metin"])
    zamanlar = animasyon.cumle_zamanlari(kelimeler, [yazi, konusma], toplam)
    basliklar = [" ".join(c.split()[:3]) for c in seslendirme._cumleler_metin(yazi)]
    sahneler = animasyon.sahneleri_hazirla(veri.get("sahneler") or [], zamanlar, toplam, basliklar)
    (klasor / "sahneler.json").write_text(animasyon.plan_json(sahneler), encoding="utf-8")
    taban = animasyon.video_uret(sahneler, toplam, klasor / "animasyon.mp4", gorseller=urun_gorselleri)

    print("4/4 Video oluşturuluyor...")
    altyazi = klasor / "altyazi.ass"
    muzik_dosyasi = None
    if ayarlar.MUZIK:
        from uretici import muzik
        muzik_dosyasi = muzik.muzik_hazirla(veri["kategori"], toplam, klasor / "muzik.wav")
    video.ass_yaz(gruplar, veri["kanca"], [], toplam, altyazi, vurgular=veri.get("vurgular"))
    cikti = video.animasyonlu_birlestir(taban, ses, altyazi, klasor / "video.mp4",
                                        animasyon.efekt_olaylari(sahneler), muzik=muzik_dosyasi)
    (klasor / "aciklama.txt").write_text(icerik.instagram_aciklamasi(veri), encoding="utf-8")
    (klasor / "icerik.json").write_text(json.dumps(veri, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    icerik.gecmise_ekle(veri)
    print(f"Tamam: {cikti}")
    return 0


def sabah(klasor) -> int:
    """Sabah bilgilendirme Reels'i: video.mp4 ve aciklama.txt aynı klasöre yazılır (paylaşım adımı aynıdır)."""
    from uretici import bilgi

    try:
        veri = bilgi.uret(klasor)
        (klasor / "aciklama.txt").write_text(bilgi.instagram_aciklamasi(veri), encoding="utf-8")
        veri_kayit = {k: v for k, v in veri.items()}
        (klasor / "icerik.json").write_text(json.dumps(veri_kayit, ensure_ascii=False, indent=2, default=str),
                                            encoding="utf-8")
        bilgi.sabah_gecmise_ekle(veri)
        print(f"Tamam: {klasor / 'video.mp4'}")
    except Exception:
        hata = traceback.format_exc()
        (klasor / "hata.txt").write_text(hata, encoding="utf-8")
        print(hata)
        print(f"HATA: Ayrıntılar şu dosyaya yazıldı: {klasor / 'hata.txt'}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
