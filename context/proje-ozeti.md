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

Sistem çalışır durumda (2026-11-06): GitHub Actions her gün videoyu üretip GitHub Pages'e koyuyor ve resmî Instagram API'si ile @feriduntalak hesabında Reels olarak paylaşıyor. İlk otomatik paylaşım 2026-11-06'da yapıldı. Instagram bağlantısı Meta uygulaması "Günlük makaralar" üzerinden kuruldu. Teknoloji ve içerik kararları için `kararlar.md` dosyasına bak.

## Önemli konumlar

- `calistir.py`: Günün videosunu üreten ana giriş dosyası.
- `paylas.py`: Videoyu resmî Instagram API'si ile Reels olarak paylaşır.
- `.github/workflows/gunluk-reels.yml`: Günlük GitHub Actions otomasyonu (çalışma saatleri burada).
- `uretici/`: İçerik (`icerik.py`), haber toplama (`haberler.py`), seslendirme, görsel ve video modülleri.
- `KURULUM.md`: Kurulum ve çalıştırma adımları.
- `cikti/`: Üretilen videolar (GitHub'a yüklenmez).
- `veri/gecmis.json`: Daha önce işlenen konular (tekrarı önlemek için).
- GitHub deposu: https://github.com/Feridun0135/instagram-otomatik (herkese açık; çalışmalar Actions sekmesinde).
