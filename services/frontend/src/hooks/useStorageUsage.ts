import { useEffect, useState } from "react";
import { apiClient } from "../services/apiClient";
import type { StorageUsage } from "../types/api.types";

export function useStorageUsage() {
  const [storage, setStorage] = useState<StorageUsage | "loading" | "unavailable">("loading");

  useEffect(() => {
    let active = true;
    apiClient.get<StorageUsage>("/storage/usage")
      .then(({ data }) => { if (active) setStorage(data); })
      .catch(() => { if (active) setStorage("unavailable"); });
    return () => { active = false; };
  }, []);

  return storage;
}
