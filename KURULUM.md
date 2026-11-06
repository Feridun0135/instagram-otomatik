# Kurulum ve Çalıştırma (Windows)

## 1. Gerekli programlar

PowerShell'i açıp şu komutları çalıştırın:

```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
```

Kurulumdan sonra PowerShell'i kapatıp yeniden açın.

## 2. Python paketleri

Proje klasöründe:

```powershell
cd "$HOME\OneDrive\Desktop\instagram otomatik"
python -m pip install -r requirements.txt
```

## 3. Anahtarlar

1. `.env.example` dosyasının kopyasını `.env` adıyla oluşturun.
2. Gemini anahtarını https://aistudio.google.com/apikey adresinden alıp `GEMINI_API_KEY=` satırına yazın.
3. Stok video için Pexels (https://www.pexels.com/api/) veya Pixabay (https://pixabay.com/api/docs/) anahtarı alıp `.env` dosyasında ilgili satıra (`PEXELS_API_KEY=` ya da `PIXABAY_API_KEY=`) yazın.

## 4. Çalıştırma

```powershell
python calistir.py --deneme   # anahtarsız, örnek metinle deneme videosu
python calistir.py            # yapay zekâ ile günün videosu
```

Videolar `cikti\` klasörüne, her çalıştırma için tarihli bir alt klasöre kaydedilir.
Instagram'a paylaşım adımı henüz eklenmedi.
