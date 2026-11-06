"""Üretilen videoyu resmî Instagram API'si ile Reels olarak paylaşır.

Instagram videoyu herkese açık bir internet adresinden indirir; bu adres GitHub Pages ile sağlanır.

Kullanım:
    python paylas.py --video-url https://.../video.mp4 --aciklama cikti/<klasor>/aciklama.txt
    python paylas.py --kontrol      Yalnızca anahtarın çalıştığını ve hangi hesaba bağlı olduğunu gösterir
"""
import argparse
import os
import sys
import time

import requests

from uretici import ayarlar  # .env dosyasını da yükler

SURUM = os.getenv("IG_API_SURUM", "v26.0")


def _token() -> str:
    return os.environ["IG_ACCESS_TOKEN"].strip()


def _api_adresi() -> str:
    """Instagram girişi token'ları "IG" ile başlar ve graph.instagram.com'u kullanır.
    Birleşik giriş / sistem kullanıcısı token'ları (ör. "EAA...") graph.facebook.com'u kullanır."""
    if _token().startswith("IG"):
        return f"https://graph.instagram.com/{SURUM}"
    return f"https://graph.facebook.com/{SURUM}"


def _istek(yontem: str, yol: str, **params) -> dict:
    params["access_token"] = _token()
    yanit = requests.request(yontem, f"{_api_adresi()}/{yol}", params=params, timeout=120)
    try:
        veri = yanit.json()
    except ValueError:
        veri = {}
    if yanit.status_code != 200 or "error" in veri:
        hata = veri.get("error", {})
        raise RuntimeError(f"Instagram API hatası ({yanit.status_code}): {hata.get('message', yanit.text[:300])}")
    return veri


def hesap() -> dict:
    """Paylaşım yapılacak Instagram hesabının kimliğini ve kullanıcı adını bulur."""
    if _token().startswith("IG"):
        return _istek("GET", "me", fields="user_id,username")

    ig_id = os.getenv("IG_USER_ID", "").strip()
    if ig_id:
        v = _istek("GET", ig_id, fields="id,username")
        return {"user_id": v["id"], "username": v.get("username")}

    # Kimlik verilmediyse token'ın erişebildiği Instagram hesaplarını aramayı dene.
    for yol, alanlar in (("me/instagram_accounts", "id,username"),
                         ("me/accounts", "instagram_business_account{id,username}")):
        try:
            veri = _istek("GET", yol, fields=alanlar).get("data", [])
        except RuntimeError:
            continue
        for kayit in veri:
            ig = kayit.get("instagram_business_account", kayit)
            if ig.get("id"):
                return {"user_id": ig["id"], "username": ig.get("username")}
    raise RuntimeError(
        "Instagram hesap kimliği bulunamadı. Meta panelindeki hesap kimliğini (rakamlardan oluşan) "
        ".env dosyasına IG_USER_ID= satırı olarak ekleyin."
    )


def adresin_hazir_olmasini_bekle(url: str, en_fazla: int = 300) -> None:
    """GitHub Pages yeni dosyayı yayınlayana kadar bekler."""
    bitis = time.time() + en_fazla
    while time.time() < bitis:
        try:
            r = requests.head(url, timeout=30, allow_redirects=True)
            if r.status_code == 200:
                return
        except requests.RequestException:
            pass
        print("    Video adresi henüz hazır değil, bekleniyor...")
        time.sleep(15)
    raise RuntimeError(f"Video adresine ulaşılamadı: {url}")


def reels_paylas(video_url: str, aciklama: str) -> str:
    kullanici = hesap()
    ig_id = kullanici["user_id"]
    print(f"Hesap: @{kullanici.get('username')}")

    adresin_hazir_olmasini_bekle(video_url)

    print("1/3 Instagram'a video bildiriliyor...")
    kap = _istek("POST", f"{ig_id}/media", media_type="REELS", video_url=video_url,
                 caption=aciklama, share_to_feed="true")
    kap_id = kap["id"]

    print("2/3 Instagram videoyu işliyor...")
    for _ in range(20):  # en fazla ~10 dakika
        time.sleep(30)
        durum = _istek("GET", kap_id, fields="status_code,status").get("status_code")
        print(f"    Durum: {durum}")
        if durum == "FINISHED":
            break
        if durum in ("ERROR", "EXPIRED"):
            ayrinti = _istek("GET", kap_id, fields="status").get("status")
            raise RuntimeError(f"Instagram videoyu işleyemedi: {ayrinti}")
    else:
        raise RuntimeError("Instagram video işlemesi zaman aşımına uğradı.")

    print("3/3 Yayınlanıyor...")
    sonuc = _istek("POST", f"{ig_id}/media_publish", creation_id=kap_id)
    return sonuc["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Instagram Reels paylaşımı")
    ap.add_argument("--video-url")
    ap.add_argument("--aciklama", help="Açıklama metninin bulunduğu dosya")
    ap.add_argument("--kontrol", action="store_true", help="Yalnızca bağlantıyı kontrol et")
    args = ap.parse_args()

    if not os.getenv("IG_ACCESS_TOKEN", "").strip():
        print("Hata: IG_ACCESS_TOKEN tanımlı değil.")
        return 1

    if args.kontrol:
        k = hesap()
        print(f"Bağlantı çalışıyor. Hesap: @{k.get('username')} (kimlik: {k.get('user_id')})")
        return 0

    if not args.video_url or not args.aciklama:
        ap.error("--video-url ve --aciklama gerekli")
    with open(args.aciklama, encoding="utf-8") as f:
        aciklama = f.read().strip()
    medya_id = reels_paylas(args.video_url, aciklama)
    print(f"Paylaşıldı. Medya kimliği: {medya_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
