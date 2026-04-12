# Szakdolgozat — Webalapú multiplex PCR görbe értékelő

Ez a repozitori a SE-EMK Egészségügyi Adattudomány MSc szakdolgozatához készült. A projekt célja egy webalapú szoftver fejlesztése, amely multiplex real-time PCR nyers fluoreszcens adataiból képes a minták kvalitatív (pozitív/negatív) és kvantitatív (Ct érték) kiértékelésére.

**Főbb jellemzők**
- Többcsatornás (multiplex) PCR futások feldolgozása
- Nyers fluoreszcens időbeli adatok beolvasása (EDS futási fájlformátum)
- Mintaazonosítók és target–festék hozzárendelés kezelése
- Minőségi döntés: pozitív / negatív meghatározása
- Kvantitatív eredmény: Ct (cycle threshold) számítása
- Eredmények exportálása mintázott táblázatként (mintázó azonosító + Ct)

Input
- EDS futási fájl: a PCR gép által exportált nyers fluoreszcencia-idősorok
- Mintaazonosítók: a futásban szereplő minták azonosítói
- Target–festék összerendelés: mely target mely fluoreszcens csatornához tartozik

Output
- Minden mintához tartozó kiértékelés, tartalmazva:
	- Kvalitatív eredmény (Pozitív / Negatív)
	- Ct érték (ha meghatározható)
	- Feldolgozás metaadatok (futás azonosító, dátum, csatorna)

Használati esetek
- Laborok és kutatócsoportok, akik multiplex PCR futásokat elemeznek
- Automatizált eredménygenerálás klinikai/diagnosztikai vizsgálatokhoz

Rövid műszaki áttekintés
- Betöltés: az EDS fájl parszolása csatornánkénti fluoreszcencia-idősorokra
- Előfeldolgozás: jel simítása, háttérlevonás, normalizálás
- Ct számítás: küszöbalapú (threshold crossing) és/vagy görbefit alapú módszerek
- Minősítés: szabályalapú logika és küszöbértékek alkalmazása multiplex kontextusban

Fejlesztés és futtatás
- A projekt webalapú felülettel rendelkezik (front-end / back-end felépítés — részletek a dolgozatban)
- Telepítés, futtatás és fejlesztési utasítások a dolgozat részletes dokumentációjában és a `docs/` mappában találhatók (ha elérhető)

Validálás és tesztelés
- A módszer validálása kontrollminták és korábbi futások összehasonlításával történik. Részletes eredmények és statisztikai értékelés a szakdolgozat mellékleteiben.

Licenc és kapcsolat
- Licenc: (add meg a kívánt licencet itt)
- Kapcsolat: (szerző neve, e-mail címe, intézmény)

Ha szeretnéd, átfogalmazom angolra, vagy hozzáadok részletes telepítési és futtatási utasításokat a `docs/` mappához.