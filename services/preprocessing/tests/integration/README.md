# Lokalne testy integracyjne preprocessingu

Testy nie wymagają uruchomionych kontenerów, baz danych ani zmiennych
środowiskowych. Backend, RustFS i RabbitMQ są zastąpione atrapami, a testy
sprawdzają requesty, nagłówki, payloady, ścieżki obiektów i wiadomości JSON.

Uruchomienie:

```bash
cd services/preprocessing
source .venv/bin/activate
PYTHONPATH=src pytest -q tests/integration
```
