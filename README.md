# Szakdolgozat — Webalkalmazás fejlesztése PCR-eredmények automatizált kiértékelésére

Ez a repozitórium a SE-EMK Egészségügyi Adattudomány MSc szakdolgozatához készült. A szakdolgozat célja egy webalapú szoftver fejlesztése, amely multiplex real-time PCR nyers fluoreszcens adataiból képes a minták kvalitatív (pozitív/negatív) és kvantitatív (Ct érték) kiértékelésére.

**Főbb jellemzők**
- Többcsatornás (multiplex) PCR futások feldolgozása
- Nyers fluoreszcens időbeli adatok beolvasása (EDS futási fájlformátum)
- Mintaazonosítók és target–festék hozzárendelés kezelése
- Minőségi döntés: pozitív / negatív meghatározása
- Kvantitatív eredmény: Ct (cycle threshold) számítása
- Eredmények exportálása táblázatként 

Input
- EDS futási fájl: a PCR gép által exportált nyers fluoreszcencia-idősorok
- Mintaazonosítók: a futásban szereplő minták azonosítói
- PCR kit kiválasztása (festék-target összerendelés, a kontrollok, és minta értékelési szabályok )

Output
- Minden mintához tartozó kiértékelés, tartalmazva:
	- Kvalitatív eredmény (Pozitív / Negatív)
	- Ct érték (pozitív esetben)
	- exportálható eredmények (csv/xlsx/txt)
	

Használati esetek
- Laborok és kutatócsoportok, akik multiplex PCR futásokat elemeznek
- Automatizált eredménygenerálás klinikai/diagnosztikai vizsgálatokhoz

Rövid műszaki áttekintés
- Betöltés: az EDS fájl-ből  csatornánkénti/wellenkénti fluoreszcencia-idősorok kinyerése
- Előfeldolgozás: jel simítása, 
- Kvalitatív értékelés: első derivált átlaga alapján 1000 küszöbértékkel
- Ct számítás: második derivált maximumához tartozó ciklusérték


Futtatás
- Python verzió követelmény (pl. Python 3.14+)
- requirements.txt tartalmazza a futtatáshoz szükséges összes python könyvtárat és verzióját
- Tesztadat mappán található covid_02.eds futási fájllal és a fiktív mintaazonosítókat tartalmazó covid_02_sample_id.xlsx táblázattal az alkalmazás kipróbálható.
- https://szakdoga.fly.dev/ oldalról elérhető, de lokálisan is futtatható:

```bash
pip install -r requirements.txt
streamlit run frontend.py
```

Validálás és tesztelés
- A módszer validálása valós diagnosztikai minták vizsgálatából származó PCR reakciókkal történt.  Részletes eredmények és statisztikai értékelés a szakdolgozatban.

Kapcsolat

- Kapcsolat: Kovács Anett, anettkova@gmail.com
