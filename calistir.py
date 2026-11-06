"""Günün içeriğini üretir: metin -> seslendirme -> stok görüntü -> video.

Kullanım:
    python calistir.py              Günün videosunu üretir (paylaşım henüz eklenmedi)
    python calistir.py --deneme     Yapay zekâ ve Pexels anahtarı olmadan örnek metinle video üretir
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
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("Hata: FFmpeg bulunamadı. Kurulum için KURULUM.md dosyasına bakın.")
        return 1

    klasor = ayarlar.CIKTI / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    klasor.mkdir(parents=True, exist_ok=True)

    try:
        print("1/4 İçerik hazırlanıyor...")
        veri = ORNEK_ICERIK if args.deneme else icerik.icerik_uret()
        print(f"    Konu: {veri['konu']} ({veri['kategori']})")

        print("2/4 Seslendiriliyor...")
        ses = klasor / "ses.mp3"
        bolumler = seslendirme.seslendir(veri["metin"], ses)
        kelimeler = seslendirme.kelimelere_bol(bolumler)
        gruplar = seslendirme.gruplara_ayir(kelimeler)

        print("3/4 Stok görüntüler indiriliyor...")
        klipler = gorseller.videolari_indir(veri["gorsel_aramalari"], klasor / "klipler",
                                           adet=ayarlar.KLIP_SAYISI)

        print("4/4 Video oluşturuluyor...")
        altyazi = klasor / "altyazi.ass"
        toplam = video.sure_olc(ses) + 0.5
        kartlar = video.not_zamanlari(veri.get("ekran_notlari") or [], kelimeler, toplam)
        video.ass_yaz(gruplar, veri["kanca"], kartlar, toplam, altyazi)
        cikti = video.video_olustur(ses, klipler, altyazi, klasor / "video.mp4")

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


if __name__ == "__main__":
    sys.exit(main())
