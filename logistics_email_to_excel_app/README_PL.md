# 🚚 Email → Excel (Streamlit, z hasłem) — INSTRUKCJA PO POLSKU

**Co robi ta aplikacja?**
- Wgrywasz swój plik **Excel** (z kolumnami jak na Twoim screenie: *Country, City, Shipment mode, Weight Band, Origin Country, Origin City*, itd.).
- Wklejasz **treść maila** od agenta (może mieć różny format).
- Aplikacja **sama wyłuskuje** dane (skąd/dokąd, kg, wymiary, stawka/km, dystans, data, total).
- **Uzupełnia** też kolumny: *Country, City, Origin Country, Origin City, Shipment mode, Weight Band* (z maila lub z domyślnych wartości).
- **Dopisuje wiersze** do Excela i daje przycisk **Download updated Excel**.

## 1) Uruchomienie lokalne (najprościej)
1. Zainstaluj **Python** (python.org → Download, zaznacz „Add Python to PATH”).
2. Rozpakuj ZIP z projektem.
3. Otwórz terminal w folderze projektu i wpisz:
   ```
   pip install -r requirements.txt
   streamlit run app_main.py
   ```
4. Wejdź w przeglądarce na adres z terminala (np. `http://localhost:8501`).

### Hasło
- Lokalnie możesz pominąć hasło. Jeśli chcesz je włączyć:
  - Windows (PowerShell): `setx APP_PASSWORD "TwojeHaslo123"` (potem zamknij i otwórz terminal).
  - macOS/Linux: `export APP_PASSWORD="TwojeHaslo123"` i uruchom aplikację.

## 2) Uruchomienie online za darmo (Streamlit Cloud)
1. Wgraj **rozpakowane pliki** do publicznego repozytorium na **GitHub** (nie ZIP, tylko zawartość).
2. Na **streamlit.io** → **New app** → wskaż repo, **Main file**: `app_main.py` → **Deploy**.
3. W panelu aplikacji → **Settings → Secrets** dodaj:
   ```
   APP_PASSWORD = TwojeHaslo123
   ```
4. Wejdź w link aplikacji → podaj hasło → gotowe.

## 3) Jak używać (krok po kroku)
1. **Upload your Excel template (XLSX)** — wgraj swój Excel (z Twoimi kolumnami).
2. **Sheet name** — zostaw puste (weźmie pierwszy arkusz) lub wpisz nazwę.
3. **Paste email text here** — wklej treść maila. Wiele maili? Rozdziel je linią `---`.
4. (Opcjonalnie) w **Settings** zaznacz przeliczanie **Total = Rate × Distance**.
5. W **Routing & Defaults** ustaw **domyślne**: Country/City oraz Origin Country/City (gdy w mailu brakuje tych danych).
6. W **Shipment classification** możesz wymusić tryb **AIR/SEA**.
7. W **Weight bands** ustaw swoje przedziały (np. `0-500`, `501-1000`).
8. Podgląd wierszy pojawi się automatycznie; kliknij **Download updated Excel**.

## 4) Jak rozpoznajemy pola
- **Destination**: szukamy linii `Destination: Miasto, Kraj` (albo `To:` / `Delivery:`). Jeśli jest tylko miasto, kraj bierzemy z domyślnych ustawień.
- **Origin**: `Origin: Miasto, Kraj` (albo `From:` / `Pickup:`).
- **Weight (kg)**: rozumiemy kg i tony (`t` → przeliczane na kg).
- **Dimensions**: format `LxWxH mm/cm/m`.
- **Volume (m3)**, **Rate per km**, **Distance (km)**, **Date**, **Total** — typowe warianty.
- **Shipment mode**: wykryjemy z tekstu (AIR/SEA) lub wymusisz w ustawieniach.
- **Weight Band**: wybieramy pasmo, w które wpada `Weight (kg)`.

## 5) Dostosowania
- Jeśli Twoje nagłówki w Excelu są inne, w sekcji **Column mapping (optional)** zobaczysz sugerowane mapowania. Najprościej jest nazwać kolumny tak, jak w Twoim szablonie ekranu.
- Chcesz wbudować **na sztywno** konkretne nazwy kolumn? Daj je w odpowiedzi — dopiszę w kodzie na stałe.

Miłej pracy! 😊
