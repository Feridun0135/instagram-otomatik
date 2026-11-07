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
        bosluk = np.zeros(int(0.12 * sr), dtype=np.float32)

        parcalar, bolumler, t = [], [], 0.0
        for cumle in _cumlelere_bol(metin):
            with torch.inference_mode():
                wav = model.generate(cumle, language_id="tr", audio_prompt_path=str(ornek),
                                     exaggeration=float(os.getenv("KLON_COSKU", "0.55")),
                                     cfg_weight=float(os.getenv("KLON_CFG", "0.5")))
            x = wav.squeeze().detach().cpu().numpy().astype(np.float32)
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
