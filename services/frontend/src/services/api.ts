import type { ApiUser } from "../types/api.types";
import type { User } from "../types/user.types";

export function mapApiUser(user: ApiUser): User {
  const role = user.role.toLowerCase();
  if (role !== "admin" && role !== "doctor") {
    throw new Error(`Unsupported user role returned by the backend: ${user.role}`);
  }

  return {
    id: user.id,
    email: user.email,
    role,
    firstName: user.first_name,
    lastName: user.last_name,
    ...(user.created_at ? { createdAt: user.created_at } : {}),
  };
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function formatExaminationDate(value: string | null | undefined): string {
  if (!value) return "?";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit", year: "numeric" });
}
