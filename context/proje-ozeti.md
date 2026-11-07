# Proje Özeti

Bu dosya projenin ne olduğunu, neden var olduğunu, kapsamını ve mevcut durumunu açıklar.

## Projenin adı

İnstagram İçerik Üretici

## Kısa tanım

Bir Instagram hesabı için her gün otomatik olarak videolu içerik üretip paylaşacak bir sistem (algoritma).

## Ana amaç

Hesabı düzenli içerikle büyütüp markalarla iş birliği yapılabilecek bir seviyeye getirmek. Takipçi hedefleri için `hedefler.md` dosyasına bak.

## Kapsama dahil olanlar

- Her gün 1 videolu içerik üretimi ve paylaşımı.
- İçerik dili Türkçedir.
- İçerik konuları:
  - Yeni çıkan / duyurulan teknoloji ürünlerinin analizi (teknoloji haber sitelerinden)
  - Telefon veya bilgisayar kullanımını kolaylaştıran ipuçları
  - Günlük teknoloji bilgileri

## Kapsam dışında kalanlar

<!-- Henüz belirlenmedi. -->

## Mevcut durum

Sistem çalışır durumda: GitHub Actions her gün videoyu üretip GitHub Pages'e koyuyor ve resmî Instagram API'si ile @feriduntalak hesabında Reels olarak paylaşıyor (ilk paylaşım 2026-11-06). 2026-11-07 itibarıyla videolar kullanıcının kendi sesiyle (konuşma dilinde), samimi abi karakteriyle, kısık arka plan müziğiyle üretiliyor; ürün analizlerinde gerçek ürün görselleri ve ayrı ARTILAR/EKSİLER listesi var. Teknoloji ve içerik kararları için `kararlar.md` dosyasına bak.

## Önemli konumlar

- `calistir.py`: Günün videosunu üreten ana giriş dosyası.
- `paylas.py`: Videoyu resmî Instagram API'si ile Reels olarak paylaşır.
- `uretici/`: İçerik (`icerik.py`), haber ve ürün görselleri (`haberler.py`), seslendirme (`seslendirme.py`, kendi ses: `klon_ses.py`), müzik (`muzik.py`), stok görüntü (`gorseller.py`) ve video (`video.py`) modülleri.
- `.github/workflows/gunluk-reels.yml`: Günlük otomasyon (paylaşım saatleri burada). `.github/workflows/ses-testi.yml`: Paylaşım yapmadan kendi sesle deneme seslendirmesi.
- `ses_sifrele.py`: Ses örneğini şifreleyip `veri/ses_ornegi.enc` olarak kaydeder. Şifresiz örnek `ses_ornegi/` klasöründe durur ve depoya yüklenmez.
- `KURULUM.md`: Kurulum ve çalıştırma adımları.
- `cikti/`: Üretilen videolar (GitHub'a yüklenmez).
- `veri/gecmis.json`: Daha önce işlenen konular (tekrarı önlemek için).
- GitHub deposu: https://github.com/Feridun0135/instagram-otomatik (herkese açık). Gizli ayarlar: GEMINI_API_KEY, PIXABAY_API_KEY, IG_ACCESS_TOKEN, IG_USER_ID, SES_SIFRESI; değişken: SES_MOTORU=klon.
