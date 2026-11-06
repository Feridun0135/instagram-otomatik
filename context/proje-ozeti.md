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
  - Günlük teknoloji bilgileri
  - Ürün tanıtımları
  - Telefon veya bilgisayar kullanımını kolaylaştıran ipuçları

## Kapsam dışında kalanlar

<!-- Henüz belirlenmedi. -->

## Mevcut durum

Proje başlangıç aşamasında. Çalışma talimatları ve bağlam yapısı hazırlandı; video üretim kodunun ilk sürümü yazıldı (içerik metni, seslendirme, stok görüntü, video); Instagram'a paylaşım kodu ve günlük GitHub otomasyonu yazıldı; otomasyon henüz GitHub'a yüklenmedi. Yayınlanmış içerik yok. Instagram hesabı (@feriduntalak) açıldı ve profesyonel hesaba çevrildi; Meta uygulaması ("Günlük makaralar") üzerinden Instagram API bağlantısı kuruldu ve doğrulandı. Teknoloji kararları için `kararlar.md` dosyasına bak.

## Önemli konumlar

- `calistir.py`: Günün videosunu üreten ana giriş dosyası.
- `paylas.py`: Videoyu resmî Instagram API'si ile Reels olarak paylaşır.
- `github-otomasyonu/gunluk-reels.yml`: Günlük GitHub Actions otomasyonu (GitHub'da `.github/workflows/` altına konur).
- `uretici/`: İçerik, seslendirme, görsel ve video modülleri.
- `KURULUM.md`: Kurulum ve çalıştırma adımları.
- `cikti/`: Üretilen videolar (GitHub'a yüklenmez).
- `veri/gecmis.json`: Daha önce işlenen konular (tekrarı önlemek için).
