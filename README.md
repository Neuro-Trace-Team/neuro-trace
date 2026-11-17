# NeuroTrace

Pain is subjective and can be difficult to assess. EEG recordings may provide additional information about how a person perceives pain. NeuroTrace is a proof of concept for a system that processes EEG data and uses AI/ML methods to predict a person's pain level.

The project is based on a public EEG dataset containing laser-evoked potentials and the corresponding subjective pain ratings. It demonstrates the full workflow: EEG data ingestion and preprocessing, pain prediction, and presentation of results in a web application. The system is intended as a foundation for a deployable EEG-based pain assessment solution; its predictions are not a substitute for clinical assessment.

## Modules

- **Web frontend** – manage patients and examinations, and view analysis results.
- **Backend API** – authentication, patient and examination data, and coordination between modules.
- **Preprocessing** – prepare EEG recordings and extract features.
- **ML service** – analyze the extracted features and store prediction results.
- **Infrastructure** – databases, message queue, and file storage.

For technical details, see the README files in the `services/` directories.

## Run with Docker Compose

Docker and Docker Compose are required. From the project root, create the environment file and start the application:

```bash
cp .env.example .env
docker compose up --build
```

The first run may take a few minutes while Docker downloads images and builds the application. Open the web app at [http://localhost:3000](http://localhost:3000). The API is available at [http://localhost:8080](http://localhost:8080).

Stop the application with `Ctrl+C`, then run:

```bash
docker compose down
```

Database and file data are stored in Docker volumes and remain available after the containers stop.

## Use the application

Sign in with an account configured for the local environment. Add a patient, create an examination, and upload an EEG file. NeuroTrace processes the recording and runs an analysis. Track the examination status in the list and open a completed examination to view its results.

## Module documentation

- [Backend](services/backend/README.md)
- [Frontend](services/frontend/README.md)
- [Preprocessing](services/preprocessing/README.md)
- [ML service](services/ml/README.md)
