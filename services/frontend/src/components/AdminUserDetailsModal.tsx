import { useEffect, useState, type FormEvent } from "react";
import { apiClient, getApiErrorMessage } from "../services/apiClient";
import { formatDate, mapApiUser } from "../services/api";
import type { ApiUser } from "../types/api.types";
import Modal from "./Modal";
import ButtonPrimary from "./ButtonPrimary";
import ButtonSecondary from "./ButtonSecondary";
import Checkbox from "./Checkbox";
import InputSection from "./InputSection";
import { useToast } from "../context/useToast";

type UserForm = {
  first_name: string;
  last_name: string;
  email: string;
  role: "ADMIN" | "DOCTOR";
  is_active: boolean;
};

export default function AdminUserDetailsModal({
  userId,
  onClose,
  onSaved,
}: {
  userId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [user, setUser] = useState<ApiUser | null>(null);
  const [form, setForm] = useState<UserForm | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    let active = true;
    apiClient
      .get<ApiUser>(`/users/${userId}`)
      .then(({ data }) => {
        if (!active) return;
        setUser(data);
        setForm({
          first_name: data.first_name,
          last_name: data.last_name,
          email: data.email,
          role: data.role.toUpperCase() === "ADMIN" ? "ADMIN" : "DOCTOR",
          is_active: data.is_active ?? true,
        });
      })
      .catch((loadError: unknown) => {
        if (active) setError(getApiErrorMessage(loadError, "Could not load user details."));
      });
    return () => {
      active = false;
    };
  }, [userId]);

  const updateForm = <K extends keyof UserForm>(key: K, value: UserForm[K]) => {
    setForm((current) => current ? { ...current, [key]: value } : current);
  };

  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form || !user) return;
    const changes: Partial<UserForm> = {};
    if (form.first_name !== user.first_name) changes.first_name = form.first_name;
    if (form.last_name !== user.last_name) changes.last_name = form.last_name;
    if (form.email !== user.email) changes.email = form.email;
    if (form.role !== user.role) changes.role = form.role;
    if (form.is_active !== user.is_active) changes.is_active = form.is_active;
    if (Object.keys(changes).length === 0) {
      setIsEditing(false);
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      const { data } = await apiClient.patch<ApiUser>(`/users/${userId}`, changes);
      setUser(data);
      setForm({
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email,
        role: data.role.toUpperCase() === "ADMIN" ? "ADMIN" : "DOCTOR",
        is_active: data.is_active ?? true,
      });
      setIsEditing(false);
      onSaved();
      showToast("User details updated successfully.", "success");
    } catch (saveError) {
      showToast(getApiErrorMessage(saveError, "Could not save user changes."), "error");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal
      className="max-w-[620px]"
      description="View account information or update the user's profile, role, and access."
      onClose={onClose}
      title="User details"
      footer={!isEditing && user ? (
        <>
          <ButtonSecondary onClick={onClose} type="button">Close</ButtonSecondary>
          <ButtonPrimary
            onClick={() => setIsEditing(true)}
            type="button"
          >
            Edit user
          </ButtonPrimary>
        </>
      ) : undefined}
    >
      {error && <p className="mb-4 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{error}</p>}
      {!user && !error && <p className="py-8 text-center text-sm text-[#52677b]" role="status">Loading user details...</p>}
      {user && form && (
        isEditing ? (
          <form className="space-y-4" onSubmit={save}>
            <div className="grid gap-4 sm:grid-cols-2">
              <InputSection label="First name" maxLength={100} minLength={1} name="first_name" onChange={(event) => updateForm("first_name", event.target.value)} required value={form.first_name} />
              <InputSection label="Last name" maxLength={100} minLength={1} name="last_name" onChange={(event) => updateForm("last_name", event.target.value)} required value={form.last_name} />
            </div>
            <InputSection label="Email" maxLength={255} minLength={3} name="email" onChange={(event) => updateForm("email", event.target.value)} required type="email" value={form.email} />
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Role
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => updateForm("role", event.target.value === "ADMIN" ? "ADMIN" : "DOCTOR")} value={form.role}>
                  <option value="DOCTOR">Doctor</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </label>
              <Checkbox checked={form.is_active} className="self-end pb-2 font-semibold" label="Account active" onChange={(checked) => updateForm("is_active", checked)} />
            </div>
            <div className="flex flex-wrap justify-between gap-2 border-t border-[#dce5e9] pt-4">
              <ButtonSecondary disabled={isSaving} onClick={() => {
                setForm({
                  first_name: user.first_name,
                  last_name: user.last_name,
                  email: user.email,
                  role: user.role.toUpperCase() === "ADMIN" ? "ADMIN" : "DOCTOR",
                  is_active: user.is_active ?? true,
                });
                setIsEditing(false);
                setError("");
              }} type="button">Cancel</ButtonSecondary>
              <ButtonPrimary disabled={isSaving} type="submit">
                {isSaving ? "Saving..." : "Save changes"}
              </ButtonPrimary>
            </div>
          </form>
        ) : (
          <dl className="divide-y divide-[#e1e8eb]">
            <Detail label="Name" value={`${user.first_name} ${user.last_name}`} />
            <Detail label="Email" value={user.email} />
            <Detail label="Role" value={mapApiUser(user).role === "admin" ? "Administrator" : "Doctor"} />
            <Detail label="Status" value={user.is_active ? "Active" : "Inactive"} />
            <Detail label="User ID" value={user.id} />
            <Detail label="Created" value={formatDate(user.created_at)} />
            <Detail label="Last updated" value={formatDate(user.updated_at)} />
          </dl>
        )
      )}
    </Modal>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[150px_minmax(0,1fr)] sm:gap-4">
      <dt className="text-xs font-bold uppercase tracking-wide text-[#52677b]">{label}</dt>
      <dd className="break-all text-sm text-[#102d58]">{value || "—"}</dd>
    </div>
  );
}
