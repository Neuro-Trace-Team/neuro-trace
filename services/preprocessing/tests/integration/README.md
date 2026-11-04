# Lokalne testy integracyjne preprocessingu

Testy nie wymagają uruchomionych kontenerów, baz danych ani zmiennych
środowiskowych. Backend, RustFS i RabbitMQ są zastąpione atrapami, a testy
sprawdzają requesty, nagłówki, payloady, ścieżki obiektów i wiadomości JSON.

Uruchomienie:

```bash
cd services/preprocessing
source .venv/bin/activate
python -m pytest -q tests/integration
```

Testy jednostkowe można uruchomić niezależnie:

```bash
python -m pytest -q tests --ignore=tests/integration
```

Cały zestaw: `PYTHONPATH=src python -m pytest -q`. Workflow CI uruchamia tę
samą komendę z `PYTHONPATH=src` ustawionym jako zmienną środowiskową.

Testy uploadu sprawdzają zapis niezmienionego CSV we wskazanym buckecie,
kolejność uploadu, publikacji i callbacku oraz obsługę błędów każdego etapu.
Testy jednostkowe adaptera storage sprawdzają też odrzucanie brakującego
pliku i nieprawidłowego bucketa przed połączeniem z S3.
