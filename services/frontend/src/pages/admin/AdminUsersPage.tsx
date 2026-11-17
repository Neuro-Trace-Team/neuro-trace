import { useCallback, useEffect, useRef, useState } from "react";
import AdminCreateUserModal, { type CreateUserInput } from "../../components/AdminCreateUserModal";
import AdminUserDetailsModal from "../../components/AdminUserDetailsModal";
import DataTable from "../../components/DataTable";
import ButtonPrimary from "../../components/ButtonPrimary";
import PageTitle from "../../components/PageTitle";
import Surface from "../../components/Surface";
import InputSection from "../../components/InputSection";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate, mapApiUser } from "../../services/api";
import type { ApiUser, PaginatedResponse } from "../../types/api.types";
import { useToast } from "../../context/useToast";

type UserRoleFilter = "all" | "ADMIN" | "DOCTOR";
type ActiveFilter = "all" | "active" | "inactive";
type SortField = "created_at" | "email" | "first_name" | "role";
type ExtraFilters = { id: string; email: string; first_name: string; last_name: string };
const emptyExtra: ExtraFilters = { id: "", email: "", first_name: "", last_name: "" };
type SortOrder = "asc" | "desc";

function AdminUsersPage() {
  const requestId = useRef(0);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [extra, setExtra] = useState(emptyExtra);
  const [draftExtra, setDraftExtra] = useState(emptyExtra);
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [roleFilter, setRoleFilter] = useState<UserRoleFilter>("all");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [draftRoleFilter, setDraftRoleFilter] = useState<UserRoleFilter>("all");
  const [draftActiveFilter, setDraftActiveFilter] = useState<ActiveFilter>("all");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showToast } = useToast();

  const loadUsers = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setIsLoading(true);
    try {
      const { data } = await apiClient.get<PaginatedResponse<ApiUser>>("/users", {
        params: { page, page_size: 20, sort_by: sortBy, sort_order: sortOrder,
          query: debouncedSearch || undefined, role: roleFilter === "all" ? undefined : roleFilter,
          is_active: activeFilter === "all" ? undefined : activeFilter === "active",
          ...Object.fromEntries(Object.entries(extra).filter(([, value]) => value.trim())),
        },
      });
      if (currentRequest !== requestId.current) return;
      setUsers(data.items);
      setTotal(data.total);
    } catch (loadError) {
      if (currentRequest === requestId.current) showToast(getApiErrorMessage(loadError, "Could not load users."), "error");
    } finally {
      if (currentRequest === requestId.current) setIsLoading(false);
    }
  }, [showToast, sortBy, sortOrder, page, debouncedSearch, roleFilter, activeFilter, extra]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim().toLowerCase()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    void Promise.resolve().then(loadUsers);
    return () => { requestId.current += 1; };
  }, [loadUsers]);

  const createUser = async (input: CreateUserInput) => {
    await apiClient.post<ApiUser>("/users", input);
    setIsCreateModalOpen(false);
    setIsLoading(true);
    await loadUsers();
  };

  const filteredUsers = users;
  const rows = filteredUsers.map((user) => [
    `${user.first_name} ${user.last_name}`,
    user.email,
    mapApiUser(user).role === "admin" ? "Admin" : "Doctor",
    formatDate(user.created_at),
  ]);
  const filtersActive =
    roleFilter !== "all" ||
    activeFilter !== "all" || Object.values(extra).some(Boolean);

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>User Management</PageTitle>
      <Surface className="p-3">
        <DataTable
          columns={["User", "Email", "Role", "Created"]}
          sortBy={sortBy}
          sortOrder={sortOrder}
          sortableColumns={{ User: "first_name", Email: "email", Role: "role", Created: "created_at" }}
          onSortChange={(nextSortBy, nextSortOrder) => {
            setIsLoading(true);
            setPage(1);
            setSortBy(nextSortBy as SortField);
            setSortOrder(nextSortOrder);
          }}
          itemLabel="user"
          itemLabelPlural="users"
          rows={rows}
          rowIds={filteredUsers.map((user) => user.id)}
          totalCount={total}
          currentPage={page}
          onPageChange={setPage}
          pageSize={20}
          showPagination
          searchPlaceholder="Search users"
          searchValue={search}
          onSearchChange={(nextSearch) => {
            setPage(1);
            setSearch(nextSearch);
          }}
          showFilters
          filterTitle="Filter users"
          filtersActive={filtersActive}
          onApplyFilters={() => {
            setPage(1);
            setExtra(draftExtra);
            setRoleFilter(draftRoleFilter);
            setActiveFilter(draftActiveFilter);
          }}
          onClearFilters={() => {
            setPage(1);
            setExtra(emptyExtra);
            setDraftExtra(emptyExtra);
            setDraftRoleFilter("all");
            setDraftActiveFilter("all");
            setRoleFilter("all");
            setActiveFilter("all");
          }}
          filterContent={(
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Role
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => setDraftRoleFilter(event.target.value as UserRoleFilter)} value={draftRoleFilter}>
                  <option value="all">All roles</option>
                  <option value="DOCTOR">Doctor</option>
                  <option value="ADMIN">Admin</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Account status
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => setDraftActiveFilter(event.target.value as ActiveFilter)} value={draftActiveFilter}>
                  <option value="all">All statuses</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              {([['id', 'User ID'], ['email', 'Email'], ['first_name', 'First name'], ['last_name', 'Last name']] as const).map(([key, label]) => (
                <InputSection key={key} label={label} name={`user-filter-${key}`} value={draftExtra[key]} onChange={(event) => setDraftExtra((current) => ({ ...current, [key]: event.target.value }))} />
              ))}
            </div>
          )}
          onRowClick={(_row, rowIndex) => setSelectedUserId(filteredUsers[rowIndex]?.id ?? null)}
          toolbarEnd={
            <ButtonPrimary className="ml-auto" icon="users" onClick={() => setIsCreateModalOpen(true)} type="button">
              Create an Account
            </ButtonPrimary>
          }
        />
        {isLoading && <p className="mt-3 text-sm text-[#52677b]">Loading users...</p>}
      </Surface>
      {isCreateModalOpen && (
        <AdminCreateUserModal
          onClose={() => setIsCreateModalOpen(false)}
          onCreate={createUser}
        />
      )}
      {selectedUserId && (
        <AdminUserDetailsModal
          userId={selectedUserId}
          onClose={() => setSelectedUserId(null)}
          onSaved={() => {
            setIsLoading(true);
            void loadUsers();
          }}
        />
      )}
    </div>
  );
}

export default AdminUsersPage;
