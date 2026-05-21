"use client";

import { useMemo, useState } from "react";

export function useLocalTableSelection<T extends { id: string }>(initialRows: T[]) {
  const [rows, setRows] = useState(initialRows);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const rowIds = useMemo(() => rows.map((row) => row.id), [rows]);
  const selectedCount = selectedIds.length;
  const allSelected = rowIds.length > 0 && selectedCount === rowIds.length;
  const partiallySelected = selectedCount > 0 && selectedCount < rowIds.length;

  function toggleAll(checked: boolean) {
    setSelectedIds(checked ? rowIds : []);
  }

  function toggleOne(id: string, checked: boolean) {
    setSelectedIds((current) => (checked ? [...current, id] : current.filter((selectedId) => selectedId !== id)));
  }

  function deleteSelected() {
    if (selectedIds.length === 0) {
      return;
    }

    setRows((current) => current.filter((row) => !selectedIds.includes(row.id)));
    setSelectedIds([]);
  }

  function clearSelection() {
    setSelectedIds([]);
  }

  function deleteOne(id: string) {
    setRows((current) => current.filter((row) => row.id !== id));
    setSelectedIds((current) => current.filter((selectedId) => selectedId !== id));
  }

  function addRow(row: T) {
    setRows((current) => [row, ...current]);
  }

  function updateRow(row: T) {
    setRows((current) => current.map((item) => (item.id === row.id ? row : item)));
  }

  return {
    addRow,
    allSelected,
    clearSelection,
    deleteOne,
    deleteSelected,
    partiallySelected,
    rows,
    selectedCount,
    selectedIds,
    setRows,
    toggleAll,
    toggleOne,
    updateRow,
  };
}
