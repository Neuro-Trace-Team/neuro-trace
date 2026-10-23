import { useState, type DragEvent, type FormEvent } from "react";
import Icon from "../../components/Icon";
import { FormField, PageTitle, SectionTitle, SmallButton, Surface } from "../../components/PageUI";

function DoctorNewExaminationPage() {
  const [newPatient, setNewPatient] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [artifactCount, setArtifactCount] = useState(3);
  const [notice, setNotice] = useState("");

  const acceptFile = (candidate?: File) => {
    if (!candidate) return;
    if (!candidate.name.toLowerCase().endsWith(".edf")) {
      setNotice("Please choose an EDF file.");
      return;
    }
    setFile(candidate);
    setNotice("");
  };

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    acceptFile(event.dataTransfer.files[0]);
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNotice(file ? "Your examination is ready. The analysis service is not connected yet." : "Choose an EDF file to continue.");
  };

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>Enter New Examination</PageTitle>
      <Surface className="p-4 sm:p-[14px]">
        <form className="grid gap-7 lg:grid-cols-2 lg:gap-10" onSubmit={submit}>
          <div>
            <SectionTitle>Patient Details</SectionTitle>
            {!newPatient && <FormField label="Patient ID" name="patientId" placeholder="Patient ID" required />}
            <label className="mt-3 flex items-center gap-2 text-[14px] text-[#102d58]">
              <input checked={newPatient} className="h-4 w-4 accent-[#00abc1]" onChange={(event) => setNewPatient(event.target.checked)} type="checkbox" />
              Create new patient instead
            </label>
            {newPatient && (
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <FormField label="First name" name="firstName" placeholder="First name" required />
                <FormField label="Last name" name="lastName" placeholder="Last name" required />
              </div>
            )}
            <div className="mt-7">
              <SectionTitle>Examination Artifacts</SectionTitle>
              <p className="mb-1 text-[14px] font-semibold">Insert timestamps of artifact appearances</p>
              <SmallButton aria-label="Add artifact timestamp" className="mb-1 h-8 w-9 px-1" onClick={() => setArtifactCount((count) => count + 1)} type="button">
                <Icon className="h-4 w-4" name="plus" />
              </SmallButton>
              <div className="space-y-1.5">
                {Array.from({ length: artifactCount }, (_, index) => (
                  <div className="flex gap-1 text-[13px]" key={index}>
                    {["HH", "HH", "MM", "MM", "SS", "SS", "MS", "MS", "MS"].map((part, field) => (
                      <input
                        aria-label={`Artifact ${index + 1} ${part} ${field + 1}`}
                        className="h-8 min-w-0 flex-1 rounded-md border border-white bg-white/65 text-center text-[#57636a] outline-none focus:border-[#00a9c4]"
                        key={`${part}-${field}`}
                        maxLength={2}
                        inputMode="numeric"
                        placeholder={part}
                        type="text"
                      />
                    ))}
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
              <span className="text-[14px] font-semibold">{file?.name ?? "Drag and drop EDF file here"}</span>
              <span className="my-3 rounded-md border border-white bg-white/80 px-3 py-1.5 text-[13px] font-semibold shadow-sm">Browse files</span>
              <input accept=".edf,application/edf" className="sr-only" onChange={(event) => acceptFile(event.target.files?.[0])} type="file" />
            </label>
            <button className="mt-3 h-[42px] w-full rounded-full bg-gradient-to-r from-[#00bdc5] to-[#0071b4] px-3 text-[13px] font-bold text-white shadow-md transition hover:brightness-105 focus-visible:outline-2 focus-visible:outline-[#06234e]" type="submit">
              CONFIRM AND START ANALYSIS
            </button>
            {notice && <p aria-live="polite" className="mt-2 text-sm text-[#0b5566]" role="status">{notice}</p>}
          </div>
        </form>
      </Surface>
    </div>
  );
}

export default DoctorNewExaminationPage;
