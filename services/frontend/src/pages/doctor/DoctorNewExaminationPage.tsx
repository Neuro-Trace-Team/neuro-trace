import { useState, type DragEvent, type FormEvent } from "react";
import Icon from "../../components/Icon";
import ButtonPrimary from "../../components/ButtonPrimary";
import ButtonSecondary from "../../components/ButtonSecondary";
import Checkbox from "../../components/Checkbox";
import InputSection from "../../components/InputSection";
import FormField from "../../components/FormField";
import PageTitle from "../../components/PageTitle";
import SectionTitle from "../../components/SectionTitle";
import Surface from "../../components/Surface";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import type { Examination } from "../../types/api.types";
import { useToast } from "../../context/useToast";
import GlassPane from "../../components/GlassPane";

const supportedExtensions = [".edf", ".bdf"];

function DoctorNewExaminationPage() {
  const [newPatient, setNewPatient] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [artifactIds, setArtifactIds] = useState<number[]>([]);
  const [nextArtifactId, setNextArtifactId] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { showToast } = useToast();

  const acceptFile = (candidate?: File) => {
    if (!candidate) return;
    const extension = candidate.name.slice(candidate.name.lastIndexOf(".")).toLowerCase();
    if (!supportedExtensions.includes(extension)) {
      showToast("Choose an EDF or BDF file.", "error");
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
    for (let index = 0; index < artifactIds.length; index += 1) {
      const artifactId = artifactIds[index];
      const digits = Array.from({ length: 9 }, (_, digitIndex) =>
        String(form.get(`artifact-${artifactId}-digit-${digitIndex}`) ?? "").trim(),
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
      const patientId = String(form.get("patientId") ?? "").trim();
      if (!newPatient && !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i.test(patientId)) {
        showToast("Enter a valid patient UUID.", "error");
        return;
      }
      const upload = new FormData();
      if (newPatient) upload.append("generate_patient", "true");
      else upload.append("patient_id", patientId);
      upload.append("events", JSON.stringify(artifactEvents));
      upload.append("file", file);
      const { data: examination } = await apiClient.post<Examination>("/examinations", upload);
      setFile(null);
      formElement.reset();
      setArtifactIds([]);
      setNextArtifactId(0);
      setNewPatient(false);

      showToast(`Examination ${examination.id} uploaded (${examination.status}). Preprocessing was requested.`, "success");
    } catch (submitError) {
      showToast(`${getApiErrorMessage(submitError, "Could not upload the examination.")} The examination may already have been saved. Check the examination list before retrying.`, "error");
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
            <div className="mt-7">
              <SectionTitle>Examination Artifacts</SectionTitle>
              <ButtonSecondary aria-label="Add artifact timestamp" className="mb-1 h-9 w-9 px-0" icon="plus" iconOnly onClick={() => {
                setArtifactIds((ids) => [...ids, nextArtifactId]);
                setNextArtifactId((id) => id + 1);
              }} type="button" />
              <div className="space-y-1.5">
                {artifactIds.map((artifactId, index) => (
                  <div className="flex items-center gap-1 text-[13px]" key={artifactId}>
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
                            name={`artifact-${artifactId}-digit-${digitIndex}`}
                            onChange={(event) => {
                              const input = event.currentTarget;
                              const digit = input.value.replace(/\D/g, "").slice(-1);
                              input.value = digit;
                              if (digit) {
                                input.form?.querySelector<HTMLInputElement>(
                                  `input[name="artifact-${artifactId}-digit-${digitIndex + 1}"]`,
                                )?.focus();
                              }
                            }}
                            onKeyDown={(event) => {
                              if (event.key === "Backspace" && !event.currentTarget.value) {
                                event.currentTarget.form?.querySelector<HTMLInputElement>(
                                  `input[name="artifact-${artifactId}-digit-${digitIndex - 1}"]`,
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
                    <ButtonSecondary
                      aria-label={`Remove artifact timestamp ${index + 1}`}
                      className="h-9 w-9 shrink-0 px-0"
                      icon="trash"
                      iconOnly
                      onClick={() => setArtifactIds((ids) => ids.filter((id) => id !== artifactId))}
                      type="button"
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div>
            <SectionTitle>EEG File Upload</SectionTitle>
            <GlassPane>
              <label
                className="
                flex min-h-[232px] cursor-pointer flex-col items-center 
                justify-center rounded-[8px] border border-[#d8dbdc] 
                px-4 text-center shadow-[0_2px_4px_rgba(0,0,0,0.22)] 
                transition hover:bg-white/25 hover:shadow-[0_4px_8px_rgba(0,0,0,0.22)]"
                onDragOver={(event) => event.preventDefault()}
                onDrop={handleDrop}
              >
                <Icon className="mb-3 h-8 w-8" name="upload" />
                <span className="text-[14px] font-semibold">{file?.name ?? "Drag and drop an EEG file here"}</span>
                <span className="my-3 rounded-md border border-white bg-white/80 px-3 py-1.5 text-[13px] font-semibold shadow-sm">Browse files</span>
                <input accept=".edf,.bdf" className="sr-only" onChange={(event) => acceptFile(event.target.files?.[0])} type="file" />
              </label>
            </GlassPane>

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
