import { useState, type DragEvent, type FormEvent } from "react";
import Icon from "../../components/Icon";
import ButtonPrimary from "../../components/ButtonPrimary";
import ButtonSecondary from "../../components/ButtonSecondary";
import Checkbox from "../../components/Checkbox";
import InputSection from "../../components/InputSection";
import { FormField, PageTitle, SectionTitle, Surface } from "../../components/PageUI";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import type { Examination, Patient } from "../../types/api.types";
import { useToast } from "../../context/useToast";

const supportedExtensions = [".edf", ".bdf", ".set", ".fif", ".vhdr", ".eeg"];

function DoctorNewExaminationPage() {
  const [newPatient, setNewPatient] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [artifactCount, setArtifactCount] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const acceptFile = (candidate?: File) => {
    if (!candidate) return;
    const extension = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!supportedExtensions.includes(extension)) {
      showToast("Choose an EDF, BDF, SET, FIF, VHDR, or EEG file.", "error");
      return;
    }
    setFile(candidate);
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    acceptFile(event.dataTransfer.files[0]);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (!file) {
      showToast("Choose an EEG file to continue.", "error");
      return;
    }

    const form = new FormData(event.currentTarget);
    const artifactEvents: Array<{ timestamp: number; type: string }> = [];
    for (let index = 0; index < artifactCount; index += 1) {
      const digits = Array.from({ length: 9 }, (_, digitIndex) =>
        String(form.get(`artifact-${index}-digit-${digitIndex}`) ?? "").trim(),
      );
      if (digits.every((digit) => !digit)) continue;
      if (digits.some((digit) => !/^\d$/.test(digit))) {
        showToast(`Complete all nine digits for artifact ${index + 1}.`, "error");
        return;
      }

      const hours = Number(digits.slice(0, 2).join(""));
      const minutes = Number(digits.slice(2, 4).join(""));
      const seconds = Number(digits.slice(4, 6).join(""));
      const milliseconds = Number(digits.slice(6, 9).join(""));
      if (minutes > 59 || seconds > 59) {
        showToast(`Artifact ${index + 1} has an invalid time.`, "error");
        return;
      }
      artifactEvents.push({
        timestamp: hours * 3600 + minutes * 60 + seconds + milliseconds / 1000,
        type: "ARTIFACT",
      });
    }

    setIsSubmitting(true);
    try {
      const patientId = newPatient
        ? (await apiClient.post<Patient>("/patients")).data.id
        : String(form.get("patientId"));
      const upload = new FormData();
      upload.append("patient_id", patientId);
      upload.append("file", file);
      const { data: examination } = await apiClient.post<Examination>("/examinations", upload);
      setFile(null);
      formElement.reset();
      setArtifactCount(0);
      setNewPatient(false);

      if (artifactEvents.length) {
        try {
          await Promise.all(
            artifactEvents.map((artifact) =>
              apiClient.post(`/examinations/${examination.id}/events`, artifact),
            ),
          );
        } catch (eventError) {
          showToast(
            `Examination ${examination.id} was uploaded, but artifact timestamps could not all be saved: ${getApiErrorMessage(eventError, "request failed")}`,
            "error",
          );
          return;
        }
      }

      showToast(
        `Examination ${examination.id} uploaded (${examination.processing_status}). Preprocessing and model analysis are not started automatically by the current backend.`,
        "success",
      );
    } catch (submitError) {
      showToast(getApiErrorMessage(submitError, "Could not upload the examination."), "error");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Enter New Examination</PageTitle>
      <Surface className="p-4 sm:p-[14px]">
        <form className="grid gap-7 lg:grid-cols-2 lg:gap-10" onSubmit={submit}>
          <div>
            <SectionTitle>Patient Details</SectionTitle>
            <FormField disabled={newPatient} label="Patient ID" name="patientId" placeholder={newPatient ? "Generated for this examination" : "Patient UUID"} required={!newPatient} />
            <Checkbox checked={newPatient} className="mt-3" label="Create a new pseudonymized patient" onChange={setNewPatient} />
            {newPatient && (
              <p className="mt-2 text-xs text-[#52677b]">
                The backend generates a patient ID and does not store names or other direct identifiers.
              </p>
            )}
            <div className="mt-7">
              <SectionTitle>Examination Artifacts</SectionTitle>
              <p className="mb-1 text-[14px] font-semibold">Insert timestamps of artifact appearances</p>
              <ButtonSecondary aria-label="Add artifact timestamp" className="mb-1 h-9 w-9 px-0" icon="plus" iconOnly onClick={() => setArtifactCount((count) => count + 1)} type="button" />
              <div className="space-y-1.5">
                {Array.from({ length: artifactCount }, (_, index) => (
                  <div className="flex items-center gap-1 text-[13px]" key={index}>
                    {Array.from({ length: 9 }, (_, digitIndex) => {
                      const unit = digitIndex < 2 ? "H" : digitIndex < 4 ? "M" : digitIndex < 6 ? "S" : "MS";

                      // Określamy, czy po danej cyfrze powinien pojawić się dwukropek
                      // (po 2. cyfrze H, po 2. cyfrze M)
                      const showColonAfter = digitIndex === 1 || digitIndex === 3 || digitIndex === 5;

                      return (
                        <div key={digitIndex} className="flex items-center gap-1">
                          <InputSection
                            aria-label={`Artifact ${index + 1} ${unit} digit ${digitIndex + 1}`}
                            className="w-12"
                            inputClassName="h-9 px-1 text-center"
                            inputMode="numeric"
                            maxLength={1}
                            name={`artifact-${index}-digit-${digitIndex}`}
                            onChange={(event) => {
                              const input = event.currentTarget;
                              const digit = input.value.replace(/\D/g, "").slice(-1);
                              input.value = digit;
                              if (digit) {
                                input.form?.querySelector<HTMLInputElement>(
                                  `input[name="artifact-${index}-digit-${digitIndex + 1}"]`,
                                )?.focus();
                              }
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Backspace" && !event.currentTarget.value) {
                                event.currentTarget.form?.querySelector<HTMLInputElement>(
                                  `input[name="artifact-${index}-digit-${digitIndex - 1}"]`,
                                )?.focus();
                              }
                            }}
                            placeholder={unit}
                            type="text"
                          />
                          {showColonAfter && (
                            <span className="select-none px-0.5 font-bold text-[#52677b]">:</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div>
            <SectionTitle>EEG File Upload</SectionTitle>
            <label
              className="flex min-h-[232px] cursor-pointer flex-col items-center justify-center rounded-[8px] border border-[#d8dbdc] bg-[#dcdddd] px-4 text-center shadow-[0_2px_4px_rgba(0,0,0,0.22)] transition hover:bg-[#e5e7e7]"
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
            >
              <Icon className="mb-3 h-8 w-8" name="upload" />
              <span className="text-[14px] font-semibold">{file?.name ?? "Drag and drop an EEG file here"}</span>
              <span className="my-3 rounded-md border border-white bg-white/80 px-3 py-1.5 text-[13px] font-semibold shadow-sm">Browse files</span>
              <input accept=".edf,.bdf,.set,.fif,.vhdr,.eeg" className="sr-only" onChange={(event) => acceptFile(event.target.files?.[0])} type="file" />
            </label>
            <ButtonPrimary className="mt-3 w-full" disabled={isSubmitting} type="submit">
              {isSubmitting ? "Uploading..." : "Upload examination"}
            </ButtonPrimary>
          </div>
        </form>
      </Surface>
    </div>
  );
}

export default DoctorNewExaminationPage;
