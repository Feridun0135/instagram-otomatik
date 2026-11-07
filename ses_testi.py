"""Kendi sesinle deneme seslendirmesi üretir; hiçbir şey paylaşmaz.

GitHub'daki "Ses Testi" görevi bunu çalıştırır ve çıkan ses dosyasını indirilebilir olarak saklar.
"""
import sys
from pathlib import Path

from uretici import klon_ses

METIN = ("Selam, bak şimdi bugün sana işine yarayacak bir şey anlatacağım. "
         "Telefonunun ayarlarında çoğu kişinin fark etmediği bir özellik var. "
         "Açık konuşayım, artısı da var eksisi de. Takipte kal, yarın yine buradayım.")

if __name__ == "__main__":
    if not klon_ses.hazir_mi():
        sys.exit("Hata: veri/ses_ornegi.enc veya SES_SIFRESI bulunamadı.")
    cikti = Path("cikti")
    cikti.mkdir(exist_ok=True)
    bolumler = klon_ses.seslendir(METIN, cikti / "ses_testi.mp3")
    for b in bolumler:
        print(f"{b['baslangic']:6.2f}-{b['bitis']:6.2f}  {b['metin']}")
    print("Tamam: cikti/ses_testi.mp3")
