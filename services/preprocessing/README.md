# EEG Pain Pipeline

Pipeline MNE/NumPy do preprocessingu EEG i ekstrakcji cech neurofizjologicznych. Jako dane EEG przyjmuje wyłącznie pliki BioSemi `.bdf`. Analiza jest wykonywana na 19 kanałach:

```text
Fp1 Fp2 F7 F3 Fz F4 F8 T7 C3 Cz C4 T8 P7 P3 Pz P4 P8 O1 O2
```

Pipeline nie interpoluje brakujących kanałów. Pomiar, którego kanałów nie można jednoznacznie zidentyfikować, zostaje odrzucony.

## Instalacja i uruchomienie

```bash
cd /home/marek/Projects/zpi-pipeline
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

Analiza całego zbioru:

```bash
python -m eeg_pipeline.cli \
  --input ~/EEG_Pain_Dataset \
  --output ~/EEG_Pain_Processed \
  --all
```

Jeden eksperyment lub uczestnik:

```bash
python -m eeg_pipeline.cli \
  --input ~/EEG_Pain_Dataset \
  --output ~/EEG_Pain_Processed \
  --experiment 1 \
  --subject sub-001
```

Analiza event-based używa konfigurowalnych okien `baseline=(-5.5,-0.5)`,
`early_response=(0,1)` i `sustained_response=(0.5,5.5)` s. Okna są liczone po
resamplingu, a wyjście zachowuje jeden wiersz na klaster zdarzeń. Okna poza
rejestracją lub nachodzące na kolejną stymulację są oznaczane jako nieważne/
zanieczyszczone, a nie cicho skracane.

## Struktura danych wejściowych

Każdy katalog pomiaru musi zawierać jeden plik `.bdf` oraz `events.csv`:

```text
EEG_Pain_Dataset/
├── experiment_01/
│   └── sub-001/
│       └── task-26ByBiosemi/
│           ├── sub-001_task-26ByBiosemi_eeg.bdf
│           └── events.csv
└── experiment_02/
```

`events.csv` musi zawierać kolumnę `onset`. Jej wartości są czasami zdarzeń w sekundach od początku rejestracji. Pozostałe kolumny są ignorowane. Kolejność wierszy wyznacza `event_index` w wynikach; puste onsety są pomijane, a niepoprawne lub ujemne wartości powodują błąd wczytywania pomiaru.

```csv
onset,event_type
7.8,stimulus
121.9,stimulus
```

Brak `events.csv` albo brak kolumny `onset` nie powoduje tworzenia zastępczych zdarzeń. `configuration.json` nie jest już źródłem zdarzeń ani metadanych wymaganych do analizy.

## Jak działa pipeline

Główne etapy znajdują się w następujących plikach:

1. `eeg_pipeline/data_loader.py` wyszukuje tylko `.bdf`, otwiera go przez MNE i pobiera z nagłówka BDF częstotliwość próbkowania, nazwy kanałów oraz typy kanałów. Czyta również onsety z `events.csv`. Dane z `*_channels.tsv` nie są używane; kanały muszą być jednoznacznie opisane w nagłówku BDF.
2. `eeg_pipeline/preprocessing.py` wybiera wymagane 19 kanałów, nakłada montage `standard_1020`, filtruje sygnał, stosuje referencję average, opcjonalnie wykonuje jawnie skonfigurowane ICA i resampluje do 256 Hz.
3. Ten sam moduł wycina jedną epokę dla każdego onsetu: od `onset + tmin` do `onset + tmax`. Epoki poza granicami rejestracji lub z artefaktami są odrzucane. Nie są generowane żadne fragmenty niezwiązane ze zdarzeniem.
4. `eeg_pipeline/spectral_features.py`, `entropy.py`, `connectivity.py`, `microstates.py` i `graph_features.py` obliczają odpowiednio cechy widmowe, entropię, connectivity dwPLI, mikrostany i metryki grafowe dla każdej zaakceptowanej epoki.
5. `eeg_pipeline/feature_export.py` zapisuje wyniki, a `feature_merge.py` tworzy tabelę połączoną.

Domyślne parametry preprocessingu to filtr pasmowy `0.5–45 Hz`, notch `50 Hz`, resampling do `256 Hz` i referencja average. Obliczane są m.in. moce pasm delta/theta/alpha/beta, PAF, theta/alpha ratio, gamma, permutation entropy, dwPLI, mikrostany i cechy grafowe.

## Dane wyjściowe

Format danych wyjściowych pozostaje bez zmian. Dla każdego pomiaru powstaje:

```text
EEG_Pain_Processed/experiment_01/sub-001/task-26ByBiosemi/
├── features.csv
├── channel_features.csv
├── connectivity.npz
├── connectivity_dwpli.csv
├── microstates.csv
├── network_metrics.csv
├── combined_features.csv
└── preprocessing_report.json
```

`features.csv` zawiera jeden wiersz na zaakceptowaną epokę i średnie cech po 19 kanałach. `channel_features.csv` zawiera cechy osobno dla każdego kanału. `connectivity.npz` przechowuje macierze connectivity, `microstates.csv` cechy mikrostanu, `network_metrics.csv` metryki sieci, a `combined_features.csv` połączone cechy do modelowania.

W istniejącym schemacie kolumn zachowane są m.in. `experiment_id`, `subject_id`, `recording_id`, `window_id`, `event_index`, `event_time_s`, `segment_start_s` i `segment_end_s`. Nazwa `window_id` pozostaje elementem formatu wyjściowego dla zgodności wstecznej, ale identyfikuje epokę event-based, a nie równe okno. `event_time_s` wskazuje onset zdarzenia.

`preprocessing_report.json` zawiera parametry, plik źródłowy, metadane odczytane przez MNE z BDF, liczbę zaakceptowanych i odrzuconych epok, przyczyny odrzuceń, ostrzeżenia oraz błędy.

## Ograniczenia

Losowe elementy klasteryzacji mają stałe ziarna. Brakujące lub niekompletne dane wymagane do preprocessingu powodują błąd, a kanały nie są uzupełniane. Connectivity może zawierać `NaN`, jeśli epoka ma zbyt mało danych. Typ zdarzenia z dodatkowych kolumn `events.csv` nie jest interpretowany i nie jest automatycznie mapowany na ocenę bólu.
