"""Ses örneğini şifreleyip `veri/ses_ornegi.enc` olarak kaydeder (depo herkese açık olduğu için).

Kullanım (proje klasöründe):
    python ses_sifrele.py "C:\\yol\\kaydim.m4a"
    python ses_sifrele.py            ses_ornegi/ klasöründeki ilk ses dosyasını kullanır

Şifre (SES_SIFRESI) .env dosyasında yoksa yeni bir şifre üretilip .env dosyasına eklenir.
Aynı şifreyi GitHub'da Settings > Secrets and variables > Actions altına SES_SIFRESI adıyla eklemelisin.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

from uretici import ayarlar  # .env dosyasını yükler

HEDEF = ayarlar.VERI / "ses_ornegi.enc"
UZANTILAR = (".m4a", ".mp3", ".wav", ".ogg", ".aac", ".flac")


def kaynak_bul() -> Path:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    klasor = ayarlar.KOK / "ses_ornegi"
    dosyalar = sorted(p for p in klasor.glob("*") if p.suffix.lower() in UZANTILAR) if klasor.is_dir() else []
    if not dosyalar:
        sys.exit("Hata: ses dosyası bulunamadı. Yol vererek çalıştırın: python ses_sifrele.py \"kayit.m4a\"")
    return dosyalar[0]


def sifre_al() -> bytes:
    sifre = os.getenv("SES_SIFRESI", "").strip()
    if sifre:
        return sifre.encode()
    yeni = Fernet.generate_key()
    with open(ayarlar.KOK / ".env", "a", encoding="utf-8") as f:
        f.write(f"\nSES_SIFRESI={yeni.decode()}\n")
    print("Yeni şifre üretildi ve .env dosyasına SES_SIFRESI olarak eklendi.")
    return yeni


def main() -> None:
    kaynak = kaynak_bul()
    print(f"Ses örneği: {kaynak}")
    with tempfile.TemporaryDirectory() as gecici:
        wav = Path(gecici) / "ornek.wav"
        # 24 kHz mono, en fazla 30 sn, ses seviyesi dengelenmiş WAV'a çevir.
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(kaynak), "-t", "30", "-ac", "1", "-ar", "24000",
                        "-af", "loudnorm=I=-18:TP=-2", str(wav)], check=True)
        veri = wav.read_bytes()
    HEDEF.parent.mkdir(parents=True, exist_ok=True)
    HEDEF.write_bytes(Fernet(sifre_al()).encrypt(veri))
    print(f"Şifreli ses örneği kaydedildi: {HEDEF}")
    print("Sıradaki adım: .env dosyasındaki SES_SIFRESI değerini GitHub'da SES_SIFRESI adıyla gizli ayar olarak ekle.")


if __name__ == "__main__":
    main()
