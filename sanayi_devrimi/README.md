# Sanayi Devrimi – Kısa Eğitim Videosu

`sanayi_devrimi.mp4`: Sanayi Devrimi'ni anlatan, Türkçe sesli ve altyazılı, yaklaşık 2 dakikalık (1280×720, 24 fps) animasyonlu bir video.

## Bölümler
1. Sanayi Devrimi (1760 – 1840)
2. Devrimden Önce: tarım toplumu ve el emeği
3. Neden İngiltere?: kömür, demir, sermaye, pazarlar, fikirler
4. Buhar Makinesi: James Watt, 1769
5. Fabrikalar ve Tekstil
6. Demiryolu Çağı: 1825 Stockton – Darlington
7. Toplumsal Etkiler: kentleşme, işçi sınıfı, işçi hakları
8. Dünyaya Yayılış
9. Mirası

## Yeniden üretmek için
```bash
sudo apt-get install -y ffmpeg espeak-ng mbrola-tr1   # mbrola-tr1 isteğe bağlı, daha doğal ses verir
pip install pillow numpy
python3 make_video.py
```
Sahneler `make_video.py` içinde Pillow ile kare kare çiziliyor. Anlatım espeak-ng (MBROLA Türkçe sesi) ile üretiliyor, fon müziği de script içinde sentezleniyor. Metni değiştirmek için `SCENES` listesini düzenlemeniz yeterli; sahne süreleri anlatımın uzunluğuna göre kendiliğinden ayarlanır.
