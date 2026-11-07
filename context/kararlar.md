# Proje Kararları

Bu dosya kesinleşmiş ve gelecekteki çalışmaları etkileyecek kararları kaydeder. Geçici fikirler veya henüz onaylanmamış seçenekler buraya yazılmaz.

| Tarih | Karar | Gerekçe | Durum | Etkilediği alanlar |
|---|---|---|---|---|
| 2026-11-05 | Programlama dili olarak Python kullanılacak | Otomasyon, video işleme ve API işleri için yaygın ve kolay | aktif | Kod yapısı |
| 2026-11-05 | Günlük çalıştırma GitHub Actions zamanlanmış görevleriyle yapılacak | Bilgisayar kapalıyken de çalışır | aktif | Zamanlama, dağıtım |
| 2026-11-05 | Paylaşım yalnızca resmî Instagram API'si ile yapılacak; resmî olmayan kütüphaneler kullanılmayacak | Hesabın kapatılma riskini önlemek | aktif | Paylaşım modülü, hesap türü |
| 2026-11-05 | Başlangıçta yalnızca ücretsiz araç ve hizmetler kullanılacak | Kullanıcının bütçe tercihi | aktif | Metin üretimi, seslendirme, görüntü kaynakları |
| 2026-11-06 | GitHub deposu herkese açık olacak; video GitHub Pages üzerinden herkese açık adresle Instagram API'ye verilecek. Anahtarlar GitHub gizli ayarlarında tutulacak | Instagram API videoyu herkese açık bir adresten alıyor; ücretsiz ve basit çözüm | aktif | Depo, yayın, paylaşım modülü |
| 2026-11-06 | Instagram API bağlantısı Meta'nın Birleşik giriş (Unified login) yöntemiyle, süresiz sistem kullanıcı erişim belirteciyle (SUAT) kurulacak | Yeni Meta uygulamalarında Instagram girişi yöntemi kaldırıldı; SUAT süresiz olduğu için yenileme gerekmez | aktif | Paylaşım modülü, Meta uygulaması |
| 2026-11-06 | Paylaşım saatleri güne göre değişir (TR): Pzt-Salı 18:47, Çarşamba 11:47, Perşembe 08:47, Cuma-Pazar 20:47 | Kullanıcı en çok izlenen saatlere göre paylaşım istedi; Buffer'ın 9,6 milyon gönderilik analizine dayanır. Hesap verisi oluşunca kendi istatistiklerine göre güncellenebilir | aktif | GitHub otomasyon zamanlaması |
| 2026-11-06 | İçerik türleri sırayla döner: yeni ürün analizi, ipucu, yeni ürün analizi, teknoloji bilgisi (günlerin yarısı ürün analizi) | Kullanıcı yalnızca bilgilendirme değil yeni ürün analizleri de istedi | aktif | İçerik üretimi (`uretici/icerik.py`) |
| 2026-11-06 | Ürün analizleri 7 teknoloji haber sitesinin RSS akışlarındaki son 4 günün haberlerinden seçilir; yalnızca haberdeki bilgiler kullanılır ve açıklamaya kaynak yazılır | Güncel ürünleri işlemek ve yanlış bilgiyi önlemek | aktif | `uretici/haberler.py`, içerik üretimi |
| 2026-11-06 | Açıklama: kanca cümlesi, kısa öz, harekete çağrı ve soru; en fazla 5 etiket | Kullanıcı kanca cümleli açıklama ve etiket istedi; Instagram 2026'da gönderi başına 5 etiket sınırı getirdi | aktif | Açıklama üretimi |
| 2026-11-06 | Video stili: yaklaşık 2,2 sn'lik hızlı çekimler ve geçişler, %15 hızlı seslendirme, kelime vurgulu altyazı, bilgi kartı animasyonları, ilerleme çubuğu | Kullanıcı daha akıcı video, hızlı konuşma ve bilgiler için animasyon istedi | aktif | `uretici/video.py`, seslendirme |
| 2026-11-06 | Stok videolar Pixabay'den alınır | Pexels API anahtarı alınamadı | aktif | `uretici/gorseller.py` |
| 2026-11-07 | Anlatıcı karakteri samimi abi; kapanış imzası "Takipte kal, yarın yine buradayım."; yapay zekâ kalıp ifadeleri yasak | Kullanıcı karakter olarak samimi abiyi seçti; içeriklerin daha doğal görünmesi isteniyor | aktif | İçerik istemi (`uretici/icerik.py`) |
| 2026-11-07 | Ürün analizlerinde ürünün gerçek görselleri haber sayfasından/RSS'ten indirilir ve stok videolarla dönüşümlü gösterilir; açıklamada görsel kaynağı belirtilir. Başka kanalların videoları (ör. YouTube) indirilmez | Kullanıcı tanıtılan ürünün gerçek görsellerinin kullanılmasını istedi; video indirme platform kurallarına ve telif hakkına aykırı | aktif | `uretici/haberler.py`, `uretici/video.py` |
| 2026-11-07 | Ürün analizlerinde özellikler anlatılırken "vitrin" düzeni: ürün görseli solda sabit, sağda "ÖNE ÇIKANLAR" başlığı altında oklarla sırayla gelen özellik listesi; her maddede pop sesi, görüntü geçişlerinde hafif whoosh sesi (efektler FFmpeg ile sentezlenir) | Kullanıcı daha emek verilmiş görünen, özelliklerin oklarla sırayla listelendiği bir video istedi | aktif | `uretici/video.py`, `calistir.py` |
| 2026-11-07 | Kanal objektif olacak: ürün analizlerinde 2 artı ve 2 eksi dengeli söylenir, ekranda ayrı başlıklarla listelenir: önce yeşil ARTILAR başlığı ve (+) maddeler, ardından eksiler gelmeden önce kırmızı EKSİLER başlığı ve (-) maddeler; eksiler uydurulmaz, yalnızca haberde geçen dezavantajlar veya dürüst belirsizlikler kullanılır; efsaneler doğruymuş gibi anlatılmaz | Kullanıcı yalnızca artıların değil eksilerin de söylendiği objektif bir teknoloji kanalı istedi | aktif | İçerik istemi, `uretici/video.py` |
| 2026-11-07 | Her videoda kısık arka plan müziği: içerik türüne göre üç ruh hali (ürün: tempolu modern, ipucu: lo-fi, bilgi: ambiyans); müzik her video için FFmpeg/numpy ile sentezlenir, konuşma sırasında otomatik kısılır. `muzik/` klasörüne konan kullanıcı müzikleri tercih edilir (lisans kullanıcının sorumluluğunda) | Kullanıcı rahatsız etmeyen, türe uygun kısık müzik istedi; hazır müzikleri herkese açık depoya koymak lisans sorunu yaratabilir | aktif | `uretici/muzik.py`, `uretici/video.py` |
| 2026-11-07 | Seslendirme kullanıcının kendi sesiyle (Chatterbox Multilingual, açık kaynak) yapılır; ses örneği şifreli olarak `veri/ses_ornegi.enc` dosyasında, şifre `.env` ve GitHub Secrets'ta (SES_SIFRESI); GitHub değişkeni SES_MOTORU=klon ile açılır, sorun olursa o gün hazır sese dönülür | Kullanıcı kendi sesini istedi ve ses testini beğendi; depo herkese açık olduğu için örnek şifrelenir | aktif | `uretici/klon_ses.py`, `ses_sifrele.py`, iş akışları |
| 2026-11-07 | Seslendirme yazı dilinde değil günlük konuşma dilinde yapılır (yapıcam, olucak, bi şey); ekrandaki altyazılar düzgün yazımla kalır | Kullanıcı dublaj/seslendirmedeki gibi doğal konuşma istedi | aktif | İçerik istemi (`seslendirme_metni`), `uretici/seslendirme.py` |

## Kullanım kuralları

- Yeni kararları tarih ve kısa gerekçeyle ekleyin.
- Bir karar değiştiğinde eski kaydı sessizce silmeyin; durumunu değiştirin ve yeni kararı ayrı kayıt olarak ekleyin.
- `Durum` alanında `aktif`, `değiştirildi`, `iptal edildi` veya `tamamlandı` gibi açık ifadeler kullanın.
- Yalnızca gelecekte tekrar bilinmesi gereken kararları kaydedin.

