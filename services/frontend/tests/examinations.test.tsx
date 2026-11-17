import { afterEach, beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { apiClient } from "../src/services/apiClient";
import { ToastProvider } from "../src/context/ToastContext";
import DoctorNewExaminationPage from "../src/pages/doctor/DoctorNewExaminationPage";
import DoctorExaminationDetailsPage from "../src/pages/doctor/DoctorExaminationDetailsPage";

let api: MockAdapter;
beforeEach(() => { api = new MockAdapter(apiClient); });
afterEach(() => api.restore());
function newExam() {
  return render(<MemoryRouter initialEntries={["/new"]}><ToastProvider><Routes><Route path="/new" element={<DoctorNewExaminationPage />} /><Route path="/doctor/examinations/:id" element={<div>Uploaded examination</div>} /></Routes></ToastProvider></MemoryRouter>);
}
function details() {
  return render(<MemoryRouter initialEntries={["/doctor/examinations/exam-1"]}><Routes><Route path="/doctor/examinations/:id" element={<DoctorExaminationDetailsPage />} /></Routes></MemoryRouter>);
}
describe("examinations", () => {
  it("validates a patient UUID before uploading", async () => {
    const user = userEvent.setup();
    const view = newExam();
    await user.type(screen.getByPlaceholderText("Patient UUID"), "invalid");
    await user.upload(view.container.querySelector('input[type="file"]')!, new File(["eeg"], "recording.edf"));
    await user.click(screen.getByRole("button", { name: "Upload examination" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid patient UUID");
    expect(api.history.post).toHaveLength(0);
  });
  it("rejects invalid file types", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const view = newExam();
    await user.upload(view.container.querySelector('input[type="file"]')!, new File(["x"], "bad.txt"));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose an EDF or BDF file");
  });
  it("uploads a new patient and serializes artifact timestamps", async () => {
    api.onPost("/examinations").reply(200, { id: "exam-1", status: "uploaded" });
    const user = userEvent.setup();
    const view = newExam();
    await user.click(screen.getByLabelText("Create a new pseudonymized patient"));
    await user.click(screen.getByRole("button", { name: "Add artifact timestamp" }));
    const digits = view.container.querySelectorAll<HTMLInputElement>('input[name^="artifact-"]');
    "010203456".split("").forEach((digit, i) => fireEvent.change(digits[i], { target: { value: digit } }));
    await user.upload(view.container.querySelector('input[type="file"]')!, new File(["eeg"], "recording.edf"));
    await user.click(screen.getByRole("button", { name: "Upload examination" }));
    expect(await screen.findByText("Uploaded examination")).toBeInTheDocument();
    const body = api.history.post[0].data as FormData;
    expect(body.get("generate_patient")).toBe("true");
    expect(body.get("timestamps")).toBe('["01:02:03:456"]');
    expect((body.get("file") as File).name).toBe("recording.edf");
  });
  it("reports pending results and loads patient history", async () => {
    api.onGet("/examinations/exam-1").reply(200, { id: "exam-1", patient_id: "patient-1" });
    api.onGet("/examinations/exam-1/results").reply(409);
    api.onGet("/patients/patient-1/examinations").reply(200, { items: [{ id: "previous", examination_date: null }], total: 1, page: 1, page_size: 10 });
    details();
    expect(await screen.findByText("Analysis is being processed or is not ready yet.")).toBeInTheDocument();
    expect(await screen.findByText("previous")).toBeInTheDocument();
  });
  it("shows selected analysis and failure reason", async () => {
    api.onGet("/examinations/exam-1").reply(200, { id: "exam-1", patient_id: "patient-1" });
    api.onGet("/patients/patient-1/examinations").reply(200, { items: [], total: 0 });
    api.onGet("/examinations/exam-1/results").reply(200, { total_analyses_count: 2, analyses: [
      { analysis_id: 1, time_stamp: "00:01", is_valid: true, result: 5, confidence: 0.8 },
      { analysis_id: 2, time_stamp: "00:02", is_valid: false, result: null, confidence: null, invalid_reason: "Bad signal" },
    ] });
    const user = userEvent.setup();
    details();
    expect(await screen.findByLabelText("Pain level 5 out of 10")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /00:02/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Bad signal"));
  });
});
