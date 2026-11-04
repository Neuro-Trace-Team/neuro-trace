export function createRows(row: string[], count = 112): string[][] {
  return Array.from({ length: count }, () => [...row]);
}

export const examRows = createRows(["Hjw721Kd2J0", "01.01.2026", "BE9d7nB72na"]);
export const patientRows = createRows(["Hjw721Kd2J0", "12", "01.01.2026", "01.01.2026"]);
export const userRows = createRows(["Alice Smith", "alice.smith@neurotrace.com", "Doctor", "01.01.2026 13:09"]);
export const activityRows = createRows(["01.01.2026", "Log-in attempt", "Failed log-in attempt at an account with several unsuccessful attempts"]);
