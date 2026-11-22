import { describe, expect, it } from "vitest";
import { formatBytes, formatExaminationDate, mapApiUser } from "../src/services/api";

describe("API presentation helpers", () => {
  it("maps API roles and names and rejects unsupported roles", () => {
    const user = { id: "1", email: "a@example.com", first_name: "Anna", last_name: "Nowak", role: "DOCTOR" };
    expect(mapApiUser(user)).toMatchObject({ id: "1", firstName: "Anna", lastName: "Nowak", role: "doctor" });
    expect(mapApiUser({ ...user, role: "ADMIN" }).role).toBe("admin");
    expect(() => mapApiUser({ ...user, role: "OTHER" })).toThrow("Unsupported user role");
  });
  it("formats storage sizes and handles missing or invalid dates", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1024)).toBe("1 KiB");
    expect(formatBytes(1048576)).toBe("1 MiB");
    expect(formatExaminationDate(null)).toBe("?");
    expect(formatExaminationDate("invalid")).toBe("invalid");
  });
});
