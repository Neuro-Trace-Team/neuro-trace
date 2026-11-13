# Porównanie preprocessingu — 2026-11-12

Test dotyczy jednego nagrania: `/home/marek/EEG_Dataset/experiment_01/sub-001/task-26ByBiosemi_run-01/raw_eeg.bdf`.
Referencja: `/home/marek/Downloads/combined_features_sub-001-exp1.csv` (znaleziona nazwa bez literówki „combained”).

## Wykonanie

- 30 wartości `onset` z `events.csv` przeliczono z sekund na milisekundy (×1000), zachowując kolejność i pełną precyzję; zapis: `timestamps.json`, obiekt z listą `timestamps`.
- Zweryfikowano zgodność SHA-256 wszystkich plików Python serwisu w kontenerze z repozytorium.
- Uruchomiono dodatkową instancję niezmienionego API w kontenerze, port 18001, z osobną kolejką RabbitMQ `preprocessing.validation.20261112`.
- Wejście przesłano do rzeczywistego RustFS. Wywołano POST `/api/v1/examinations/8e24831d-893f-4a88-b756-4449f28e303b/preprocessing`. Odpowiedź: HTTP 202, końcowy status GET: `COMPLETED`.
- Porównywany `combined_features.csv` pobrano z RustFS, z klucza `preprocessing/8e24831d-893f-4a88-b756-4449f28e303b/combined_features.csv`, bucket `examinations`. Jego bajty są identyczne z lokalnym wynikiem zadania.
- Odebrano 17 wiadomości RabbitMQ; wszystkie zawierały identyfikator tego testu. Testową kolejkę po odebraniu wiadomości usunięto, dodatkową instancję API zatrzymano.
- Kontenery preprocessing, RustFS i RabbitMQ uruchomiono na potrzeby testu i pozostawiono uruchomione. Pliki wejściowe i wynik testu pozostają w RustFS pod unikalnym identyfikatorem testu.

## Zgodność struktury i zdarzeń

Oba CSV mają **17 wierszy × 207 kolumn**, identyczną kolejność kolumn i zdarzeń oraz identyczne położenie pustych komórek. Nie brakuje ani wierszy, ani kolumn. Timestampy, indeksy zdarzeń, identyfikatory klastrów i ich liczebności zgadzają się dokładnie. W obu plikach pierwszy wiersz obejmuje klaster 14 timestampów, a pozostałych 16 wierszy odpowiada pojedynczym timestampom.

Raport wykonania: 30 wejściowych zdarzeń, 17 zdarzeń analizy, 17 epok, 0 odrzuconych epok, pusta lista błędów. Raport zawiera ostrzeżenie o wysokiej amplitudzie w F8, T8, P7; nie jest to porównanie ostrzeżeń, ponieważ dostarczona referencja jest wyłącznie CSV.

## Niezgodności

Każda z poniższych różnic występuje we wszystkich 17 wierszach (łącznie 51 komórek):

| Kolumna | Referencja | Wynik serwisu |
| --- | --- | --- |
| experiment_id | experiment_01 | study |
| subject_id | sub-001 | subject |
| recording_id | task-26ByBiosemi_run-01 | run |

Dodatkowo **1525 komórek w 104 kolumnach liczbowych** różni się na bardzo odległych miejscach dziesiętnych. Największa różnica bezwzględna: **1.1368683772161603e-12**. Przykład: `event_index=0`, czas `7.893484933035714 s`, `early_absolute_spectral_power`: referencja `512.4943630040253`, serwis `512.4943630040265`.

Największa różnica względna, liczona jako `abs(a-b)/max(abs(a),abs(b))`: **3.943575128911456e-12**. Dotyczy `event_index=16`, czas `146.9482421875 s`, `sustained_spectral_power_db_change_mean_channels`: referencja `-0.0049304621935214385`, serwis `-0.004930462193540882`.

W ścisłym porównaniu wartości pliki nie są identyczne. Przy jawnie przyjętej tolerancji liczbowej `rel_tol=1e-9, abs_tol=1e-20` wszystkie wartości liczbowe są zgodne. Ta tolerancja służy wyłącznie opisowi porównania i nie stanowi kryterium walidacji klinicznej. Pozostałe **1943 komórki** są identyczne tekstowo.

Nie badano przyczyn różnic i nie zmieniano kodu serwisu.

## Pliki

- `timestamps.json`: przygotowane wejście dla serwisu.
- `combined_features.csv`: wynik serwisu pobrany z RustFS.
- `reference.csv`: kopia referencji.
- `metadata_differences.csv`: wszystkie 51 różnic identyfikatorów.
- `numeric_differences.csv`: wszystkie 1525 różnic liczbowych z wartościami i odchyleniami.
- `comparison_summary.json`: podsumowanie liczbowe.
- `preprocessing_report.json`: raport wykonania pipeline'u.
- `submission.json`, `status.json`: żądanie i status API.
- `compare.py`: powtórzenie porównania: `python3 reports/preprocessing-validation-20261112/compare.py`.
