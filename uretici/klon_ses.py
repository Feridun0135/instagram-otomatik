"""Kullanıcının kendi sesiyle seslendirme (Chatterbox Multilingual, açık kaynak).

Şifreli ses örneği `veri/ses_ornegi.enc` dosyasındadır; şifre SES_SIFRESI ortam değişkeninden okunur.
Ağır bir modeldir (PyTorch); yalnızca SES_MOTORU=klon olduğunda yüklenir.
"""
import os
import re
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from . import ayarlar

SIFRELI_ORNEK = ayarlar.VERI / "ses_ornegi.enc"


def hazir_mi() -> bool:
    return SIFRELI_ORNEK.exists() and bool(os.getenv("SES_SIFRESI", "").strip())


def _ornegi_coz(hedef: Path) -> Path:
    from cryptography.fernet import Fernet

    hedef.write_bytes(Fernet(os.environ["SES_SIFRESI"].strip().encode()).decrypt(SIFRELI_ORNEK.read_bytes()))
    return hedef


def _cumlelere_bol(metin: str) -> list[str]:
    parcalar = re.split(r"(?<=[.!?…])\s+", metin.strip())
    return [p.strip() for p in parcalar if p.strip()]


# Duraklama düzeni (saniye): virgülde çok kısa bir es, cümle sonunda biraz daha uzun.
VIRGUL_ESI = float(os.getenv("KLON_VIRGUL_ESI", "0.14"))
CUMLE_ESI = float(os.getenv("KLON_CUMLE_ESI", "0.24"))
_KENAR = 0.03          # kelimenin başı/sonu kesilmesin diye bırakılan pay
_PENCERE = 0.01        # sessizlik ölçüm penceresi


def _sessizlikleri_duzenle(x: np.ndarray, sr: int, virgul_sayisi: int) -> np.ndarray:
    """Cümle içi duraklamaları noktalamaya göre düzenler.

    Baştaki/sondaki sessizlik kırpılır. Cümle içindeki duraklamalardan en uzun `virgul_sayisi` tanesi
    virgül esi kabul edilip VIRGUL_ESI uzunluğuna getirilir; geri kalan (anlamsız) duraklamalar
    akışı bozmayacak kadar kısaltılır. Böylece model virgül olmayan yerde durursa cümle kopmaz.
    """
    p = max(1, int(_PENCERE * sr))
    n = len(x) // p
    if n < 3:
        return x
    enerji = np.sqrt(np.mean(x[: n * p].reshape(n, p) ** 2, axis=1))
    esik = max(np.max(enerji) * 0.03, 1e-4)
    sesli = enerji > esik
    if not sesli.any():
        return x
    ilk, son = int(np.argmax(sesli)), int(n - np.argmax(sesli[::-1]))
    kenar = int(_KENAR / _PENCERE)
    bas, bit = max(0, ilk - kenar) * p, min(len(x), (son + kenar) * p)

    # Cümle içindeki sessiz bölgeler (pencere indeksleriyle).
    bolgeler, i = [], ilk
    while i < son:
        if not sesli[i]:
            j = i
            while j < son and not sesli[j]:
                j += 1
            bolgeler.append((i, j))
            i = j
        else:
            i += 1
    en_kisa = int(0.06 / _PENCERE)                              # kelime içi doğal boşluklara dokunma
    adaylar = sorted((b for b in bolgeler if b[1] - b[0] > en_kisa), key=lambda b: b[0] - b[1])
    virgul = set(adaylar[:virgul_sayisi])
    parcalar, imlec = [], bas
    for b0, b1 in sorted(adaylar):
        hedef = VIRGUL_ESI if (b0, b1) in virgul else 0.06
        uzunluk = (b1 - b0) * p
        istenen = int(hedef * sr)
        if uzunluk <= istenen:
            continue
        # Sessizliğin yalnızca istenen kadarını bırak (yarısı başta, yarısı sonda).
        parcalar.append(x[imlec: b0 * p + istenen // 2])
        imlec = b1 * p - (istenen - istenen // 2)
    parcalar.append(x[imlec:bit])
    return np.concatenate(parcalar)


def seslendir(metin: str, ses_yolu: Path) -> list[dict]:
    """Metni kullanıcının sesiyle seslendirir; cümle zamanlamalarını döndürür."""
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    torch.set_num_threads(max(1, os.cpu_count() or 1))
    with tempfile.TemporaryDirectory() as gecici:
        gecici = Path(gecici)
        ornek = _ornegi_coz(gecici / "ornek.wav")
        print("    Kendi sesin için model yükleniyor (ilk seferde birkaç dakika sürebilir)...")
        model = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
        sr = model.sr
        bosluk = np.zeros(int(CUMLE_ESI * sr), dtype=np.float32)

        parcalar, bolumler, t = [], [], 0.0
        for cumle in _cumlelere_bol(metin):
            with torch.inference_mode():
                wav = model.generate(cumle, language_id="tr", audio_prompt_path=str(ornek),
                                     exaggeration=float(os.getenv("KLON_COSKU", "0.65")),
                                     cfg_weight=float(os.getenv("KLON_CFG", "0.4")))
            x = wav.squeeze().detach().cpu().numpy().astype(np.float32)
            x = _sessizlikleri_duzenle(x, sr, cumle.count(",") + cumle.count(";") + cumle.count(":"))
            sure = len(x) / sr
            bolumler.append({"baslangic": t, "bitis": t + sure, "metin": cumle})
            parcalar += [x, bosluk]
            t += sure + len(bosluk) / sr

        ses = np.concatenate(parcalar)
        ses = ses / (np.max(np.abs(ses)) or 1.0) * 0.9
        ham = gecici / "ham.wav"
        with wave.open(str(ham), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes((ses * 32767).astype("<i2").tobytes())

        # İstenirse biraz hızlandır (KLON_HIZ=1.0 hızlandırmaz); zamanlamalar da aynı oranda kısalır.
        hiz = float(os.getenv("KLON_HIZ", "1.08"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(ham), "-af",
                        f"atempo={hiz},loudnorm=I=-16:TP=-1.5", "-ar", "44100", "-b:a", "160k", str(ses_yolu)],
                       check=True)
    return [{"baslangic": b["baslangic"] / hiz, "bitis": b["bitis"] / hiz, "metin": b["metin"]} for b in bolumler]
