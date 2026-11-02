import { useCallback, useEffect, useState } from "react";
import AdminCreateUserModal, { type CreateUserInput } from "../../components/AdminCreateUserModal";
import AdminUserDetailsModal from "../../components/AdminUserDetailsModal";
import DataTable from "../../components/DataTable";
import ButtonPrimary from "../../components/ButtonPrimary";
import { PageTitle, Surface } from "../../components/PageUI";
import { apiClient, getApiErrorMessage } from "../../services/apiClient";
import { formatDate, mapApiUser } from "../../services/api";
import type { ApiUser, PaginatedResponse } from "../../types/api.types";
import { useToast } from "../../context/useToast";

type UserRoleFilter = "all" | "ADMIN" | "DOCTOR";
type ActiveFilter = "all" | "active" | "inactive";
type SortField = "created_at" | "updated_at" | "email";
type SortOrder = "asc" | "desc";

function AdminUsersPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [users, setUsers] = useState<ApiUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [sortBy, setSortBy] = useState<SortField>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");
  const [draftSortBy, setDraftSortBy] = useState<SortField>("created_at");
  const [draftSortOrder, setDraftSortOrder] = useState<SortOrder>("desc");
  const [roleFilter, setRoleFilter] = useState<UserRoleFilter>("all");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("all");
  const [draftRoleFilter, setDraftRoleFilter] = useState<UserRoleFilter>("all");
  const [draftActiveFilter, setDraftActiveFilter] = useState<ActiveFilter>("all");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const { showToast } = useToast();

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data: firstPage } = await apiClient.get<PaginatedResponse<ApiUser>>("/users", {
        params: { page: 1, page_size: 100, sort_by: sortBy, sort_order: sortOrder },
      });
      const pageCount = Math.ceil(firstPage.total / firstPage.page_size);
      const usersFromAdditionalPages: ApiUser[] = [];

      for (let firstPageNumber = 2; firstPageNumber <= pageCount; firstPageNumber += 5) {
        const pageNumbers = Array.from(
          { length: Math.min(5, pageCount - firstPageNumber + 1) },
          (_, index) => firstPageNumber + index,
        );
        const pageResponses = await Promise.all(
          pageNumbers.map((page) =>
            apiClient.get<PaginatedResponse<ApiUser>>("/users", {
              params: { page, page_size: 100, sort_by: sortBy, sort_order: sortOrder },
            }),
          ),
        );
        usersFromAdditionalPages.push(...pageResponses.flatMap(({ data }) => data.items));
      }

      setUsers([...firstPage.items, ...usersFromAdditionalPages]);
    } catch (loadError) {
      showToast(getApiErrorMessage(loadError, "Could not load users."), "error");
    } finally {
      setIsLoading(false);
    }
  }, [showToast, sortBy, sortOrder]);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim().toLowerCase()), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    void Promise.resolve().then(loadUsers);
  }, [activeFilter, debouncedSearch, loadUsers, roleFilter]);

  const createUser = async (input: CreateUserInput) => {
    await apiClient.post<ApiUser>("/users", input);
    setIsCreateModalOpen(false);
    setIsLoading(true);
    await loadUsers();
  };

  const filteredUsers = users.filter((user) => {
    const matchesRole = roleFilter === "all" || user.role === roleFilter;
    const matchesActive = activeFilter === "all" || Boolean(user.is_active) === (activeFilter === "active");
    const matchesSearch = !debouncedSearch || `${user.first_name} ${user.last_name} ${user.email}`.toLowerCase().includes(debouncedSearch);
    return matchesRole && matchesActive && matchesSearch;
  });
  const rows = filteredUsers.map((user) => [
    `${user.first_name} ${user.last_name}`,
    user.email,
    mapApiUser(user).role === "admin" ? "Admin" : "Doctor",
    formatDate(user.created_at),
  ]);
  const filtersActive =
    sortBy !== "created_at" ||
    sortOrder !== "desc" ||
    roleFilter !== "all" ||
    activeFilter !== "all";

  return (
    <div className="mx-auto max-w-[1100px]">
      <PageTitle>User Management</PageTitle>
      <Surface className="p-3">
        <DataTable
          columns={["User", "Email", "Role", "Created"]}
          itemLabel="user"
          itemLabelPlural="users"
          rows={rows}
          totalCount={filteredUsers.length}
          pageSize={20}
          showPagination
          searchPlaceholder="Search users"
          searchValue={search}
          onSearchChange={(nextSearch) => {
            setSearch(nextSearch);
            setIsLoading(true);
          }}
          showFilters
          filterTitle="Filter and sort users"
          filtersActive={filtersActive}
          onApplyFilters={() => {
            setIsLoading(true);
            setSortBy(draftSortBy);
            setSortOrder(draftSortOrder);
            setRoleFilter(draftRoleFilter);
            setActiveFilter(draftActiveFilter);
          }}
          onClearFilters={() => {
            setDraftSortBy("created_at");
            setDraftSortOrder("desc");
            setDraftRoleFilter("all");
            setDraftActiveFilter("all");
            setIsLoading(true);
            setSortBy("created_at");
            setSortOrder("desc");
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
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Sort by
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => setDraftSortBy(event.target.value as SortField)} value={draftSortBy}>
                  <option value="created_at">Created date</option>
                  <option value="updated_at">Updated date</option>
                  <option value="email">Email</option>
                </select>
              </label>
              <label className="grid gap-1 text-sm font-semibold text-[#102d58]">
                Order
                <select className="h-10 rounded-md border border-[#d6dfe3] bg-white px-3 outline-none focus:border-[#009bb4]" onChange={(event) => setDraftSortOrder(event.target.value as SortOrder)} value={draftSortOrder}>
                  <option value="desc">Newest first / Z–A</option>
                  <option value="asc">Oldest first / A–Z</option>
                </select>
              </label>
              <p className="text-xs text-[#52677b] sm:col-span-2">
                Results are refreshed from the backend when search and filters change. Search and role/status filters apply across the loaded user records.
              </p>
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
