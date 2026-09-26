"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/alert";
import {
  Dialog, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import {
  Factory, Plus, Search, Upload, Pencil, Ban, Trash2, Loader2,
  CheckCircle2, AlertTriangle, Info, Globe, BookOpen, X, Check, FileText, Download,
} from "lucide-react";
import {
  useManufacturers, useCreateManufacturer, useUpdateManufacturer,
  useManufacturerCodes, useCreateManufacturerCode, useUpdateManufacturerCode,
  useDeactivateManufacturerCode, useDeleteManufacturerCode,
  usePreviewImport, useCommitImport,
  useSpecBooks, useUploadSpecBook, useSpecBook, useSpecBookRows,
  useUpdateSpecBookRow, useRejectSpecBookRow, useApproveSpecBookRows,
} from "@/lib/hooks/use-manufacturers";
import {
  useNKBAReferenceDocuments, useUploadNKBAReferenceDocument,
  useDeleteNKBAReferenceDocument, useNKBAReferenceDownloadUrl,
} from "@/lib/hooks/use-nkba-reference";
import {
  ItemCategory, Manufacturer, ManufacturerCode, BulkImportPreview, BulkImportResult,
  SpecBook, SpecBookRow, NKBAReferenceDocument,
} from "@/lib/api/types";

const CATEGORIES: ItemCategory[] = [
  "CABINET", "PANEL", "FILLER", "MOLDING", "ACCESSORY",
  "ARCHITECTURAL_ANNOTATION", "APPLIANCE", "COMMERCIAL_CHARGE", "UNKNOWN",
];

const IMPORT_COLUMNS = "code, description, category, alias_group, is_current, source_version, effective_from, effective_to";

export function ManufacturerIntelligenceTab() {
  const { data: manufacturers, isLoading: loadingMfrs } = useManufacturers();
  const [selectedId, setSelectedId] = useState<string>("");
  const [showAddMfr, setShowAddMfr] = useState(false);
  const [showEditMfr, setShowEditMfr] = useState(false);
  const [showAddCode, setShowAddCode] = useState(false);
  const [editingCode, setEditingCode] = useState<ManufacturerCode | null>(null);
  const [showImport, setShowImport] = useState(false);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const list = React.useMemo(() => manufacturers || [], [manufacturers]);
  const selected = list.find((m) => m.id === selectedId) || null;

  React.useEffect(() => {
    if (!selectedId && list.length > 0) setSelectedId(list[0].id);
  }, [list, selectedId]);

  const isReadOnly = !!selected?.is_global;

  const { data: codes, isLoading: loadingCodes } = useManufacturerCodes(
    selectedId || null,
    { search: search || undefined, category: categoryFilter || undefined }
  );

  return (
    <div className="space-y-6">
      <NKBAReferenceLibrarySection />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#0EA5E9]">
              <Factory className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>Manufacturer & Cabinet Intelligence</CardTitle>
              <CardDescription>
                Configure manufacturer identities and their cabinet code dictionaries used by Cabinet Code Intelligence during extraction classification.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-sky-50/50 border border-sky-100 rounded-xl flex items-start gap-3">
            <Info className="h-5 w-5 text-[#0EA5E9] shrink-0 mt-0.5" />
            <p className="text-xs text-sky-950 leading-relaxed">
              When a project is linked to a manufacturer, extracted cabinet codes are verified against that manufacturer&apos;s dictionary first — codes that match are classified with high confidence; everything else falls back to CrossCheckPro&apos;s generic classifier. Projects without a manufacturer configured are unaffected.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-end gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F] block mb-1.5">
                Manufacturer
              </label>
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                disabled={loadingMfrs}
                className="w-full h-10 rounded-lg border border-[#DCE6F0] bg-white px-3 text-sm font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
              >
                {list.length === 0 && <option value="">No manufacturers configured</option>}
                {list.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}{m.is_global ? " (Global)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              {selected && !isReadOnly && (
                <Button variant="outline" onClick={() => setShowEditMfr(true)}>
                  <Pencil className="h-4 w-4 mr-1.5" /> Rename
                </Button>
              )}
              <Button onClick={() => setShowAddMfr(true)}>
                <Plus className="h-4 w-4 mr-1.5" /> Add Manufacturer
              </Button>
            </div>
          </div>

          {selected && (
            <div className="flex items-center gap-2 text-xs">
              {selected.is_global ? (
                <Badge variant="info"><Globe className="h-3 w-3" /> Global — shared, read-only</Badge>
              ) : (
                <Badge variant="secondary">Organization-specific</Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {selected && (
        <Card>
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <CardTitle className="text-base">Cabinet Code Dictionary</CardTitle>
                <CardDescription>{selected.name}&apos;s known SKUs, categories, and documented aliases.</CardDescription>
              </div>
              {!isReadOnly && (
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => setShowImport(true)}>
                    <Upload className="h-4 w-4 mr-1.5" /> Import CSV / Excel
                  </Button>
                  <Button onClick={() => setShowAddCode(true)}>
                    <Plus className="h-4 w-4 mr-1.5" /> Add Code
                  </Button>
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#58708F]" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search code or description..."
                  className="w-full h-10 pl-9 pr-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
                />
              </div>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="h-10 rounded-lg border border-[#DCE6F0] bg-white px-3 text-sm font-medium text-[#0F2747] focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
              >
                <option value="">All categories</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {loadingCodes ? (
              <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin text-[#0EA5E9]" /></div>
            ) : !codes || codes.length === 0 ? (
              <div className="text-center py-10 text-sm text-[#58708F]">
                No dictionary entries yet{search || categoryFilter ? " matching your filters" : ""}.
              </div>
            ) : (
              <div className="border border-[#DCE6F0] rounded-xl overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Alias Group</TableHead>
                      <TableHead>Current</TableHead>
                      <TableHead>Version</TableHead>
                      {!isReadOnly && <TableHead className="text-right">Actions</TableHead>}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {codes.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-mono font-semibold text-[#0F2747]">
                          {c.code}
                          {!c.is_primary_alias && <span className="ml-1.5 text-[10px] text-[#58708F] font-sans">(alias)</span>}
                        </TableCell>
                        <TableCell className="text-[#58708F]">{c.description || "—"}</TableCell>
                        <TableCell><Badge variant="outline">{c.category}</Badge></TableCell>
                        <TableCell className="text-[#58708F]">{c.alias_group || "—"}</TableCell>
                        <TableCell>
                          {c.is_current ? (
                            <Badge variant="success"><CheckCircle2 className="h-3 w-3" /> Active</Badge>
                          ) : (
                            <Badge variant="secondary">Inactive</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-[#58708F]">{c.source_version || "—"}</TableCell>
                        {!isReadOnly && (
                          <TableCell className="text-right">
                            <div className="flex justify-end gap-1">
                              <Button variant="ghost" size="icon" onClick={() => setEditingCode(c)} title="Edit">
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              {selectedId && <DeactivateButton manufacturerId={selectedId} code={c} />}
                              {selectedId && <DeleteButton manufacturerId={selectedId} code={c} />}
                            </div>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {selected && !isReadOnly && <SpecBooksSection manufacturerId={selected.id} />}

      {showAddMfr && <ManufacturerFormDialog onClose={() => setShowAddMfr(false)} onCreated={(id) => setSelectedId(id)} />}
      {showEditMfr && selected && <ManufacturerFormDialog manufacturer={selected} onClose={() => setShowEditMfr(false)} />}
      {showAddCode && selectedId && <CodeFormDialog manufacturerId={selectedId} onClose={() => setShowAddCode(false)} />}
      {editingCode && selectedId && (
        <CodeFormDialog manufacturerId={selectedId} code={editingCode} onClose={() => setEditingCode(null)} />
      )}
      {showImport && selectedId && <ImportDialog manufacturerId={selectedId} onClose={() => setShowImport(false)} />}
    </div>
  );
}

function DeactivateButton({ manufacturerId, code }: { manufacturerId: string; code: ManufacturerCode }) {
  const mutation = useDeactivateManufacturerCode(manufacturerId);
  if (!code.is_current) return null;
  return (
    <Button variant="ghost" size="icon" title="Deactivate" isLoading={mutation.isPending} onClick={() => mutation.mutate(code.id)}>
      <Ban className="h-3.5 w-3.5 text-amber-600" />
    </Button>
  );
}

function DeleteButton({ manufacturerId, code }: { manufacturerId: string; code: ManufacturerCode }) {
  const mutation = useDeleteManufacturerCode(manufacturerId);
  return (
    <Button
      variant="ghost"
      size="icon"
      title="Delete"
      isLoading={mutation.isPending}
      onClick={() => {
        if (window.confirm(`Delete dictionary entry "${code.code}"? This cannot be undone.`)) {
          mutation.mutate(code.id);
        }
      }}
    >
      <Trash2 className="h-3.5 w-3.5 text-rose-600" />
    </Button>
  );
}

function ManufacturerFormDialog({
  manufacturer, onClose, onCreated,
}: { manufacturer?: Manufacturer; onClose: () => void; onCreated?: (id: string) => void }) {
  const [name, setName] = useState(manufacturer?.name || "");
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreateManufacturer();
  const updateMutation = useUpdateManufacturer();
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Manufacturer name is required");
      return;
    }
    try {
      if (manufacturer) {
        await updateMutation.mutateAsync({ id: manufacturer.id, data: { name: name.trim() } });
      } else {
        const created = await createMutation.mutateAsync({ name: name.trim() });
        onCreated?.(created.id);
      }
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save manufacturer");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <form onSubmit={handleSubmit}>
        <DialogHeader>
          <DialogTitle>{manufacturer ? "Rename Manufacturer" : "Add Manufacturer"}</DialogTitle>
          <DialogDescription>
            {manufacturer ? "Update this manufacturer's display name." : "Create an organization-specific manufacturer to hold its own cabinet code dictionary."}
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive" className="mb-4">{error}</Alert>}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Name</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Yorktowne"
            className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={isPending}>Save</Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

function CodeFormDialog({
  manufacturerId, code, onClose,
}: { manufacturerId: string; code?: ManufacturerCode; onClose: () => void }) {
  const [form, setForm] = useState({
    code: code?.code || "",
    description: code?.description || "",
    category: code?.category || ("CABINET" as ItemCategory),
    alias_group: code?.alias_group || "",
    is_primary_alias: code?.is_primary_alias ?? true,
    is_current: code?.is_current ?? true,
    source_version: code?.source_version || "",
  });
  const [error, setError] = useState<string | null>(null);
  const createMutation = useCreateManufacturerCode(manufacturerId);
  const updateMutation = useUpdateManufacturerCode(manufacturerId);
  const isPending = createMutation.isPending || updateMutation.isPending;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!form.code.trim() && !code) {
      setError("Code is required");
      return;
    }
    try {
      if (code) {
        await updateMutation.mutateAsync({
          codeId: code.id,
          data: {
            description: form.description || null,
            category: form.category,
            alias_group: form.alias_group || null,
            is_primary_alias: form.is_primary_alias,
            is_current: form.is_current,
            source_version: form.source_version || null,
          },
        });
      } else {
        await createMutation.mutateAsync({
          code: form.code.trim(),
          description: form.description || null,
          category: form.category,
          alias_group: form.alias_group || null,
          is_primary_alias: form.is_primary_alias,
          is_current: form.is_current,
          source_version: form.source_version || null,
        });
      }
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save dictionary entry");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <DialogHeader>
          <DialogTitle>{code ? "Edit Dictionary Entry" : "Add Dictionary Entry"}</DialogTitle>
          <DialogDescription>
            {code ? "Raw code is preserved — only classification metadata can be edited." : "The raw code you enter is never altered by normalization."}
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive">{error}</Alert>}

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2 space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Code</label>
            <input
              disabled={!!code}
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
              placeholder="e.g. BT36B-2"
              className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white disabled:bg-slate-50 disabled:text-slate-500 text-sm font-mono focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            />
          </div>
          <div className="col-span-2 space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Description</label>
            <input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="e.g. Base w/ 2 Roll-Out Trays"
              className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Category</label>
            <select
              value={form.category}
              onChange={(e) => setForm((f) => ({ ...f, category: e.target.value as ItemCategory }))}
              className="w-full h-10 rounded-lg border border-[#DCE6F0] bg-white px-3 text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            >
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Source Version</label>
            <input
              value={form.source_version}
              onChange={(e) => setForm((f) => ({ ...f, source_version: e.target.value }))}
              placeholder="optional, e.g. 2026"
              className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Alias Group</label>
            <input
              value={form.alias_group}
              onChange={(e) => setForm((f) => ({ ...f, alias_group: e.target.value }))}
              placeholder="optional, e.g. BFHC12-GROUP"
              className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
            />
          </div>
          <div className="flex items-center gap-2 pt-6">
            <input
              type="checkbox"
              checked={form.is_primary_alias}
              onChange={(e) => setForm((f) => ({ ...f, is_primary_alias: e.target.checked }))}
              className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300"
            />
            <span className="text-xs text-[#58708F]">This is the primary spelling for its alias group</span>
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.is_current}
              onChange={(e) => setForm((f) => ({ ...f, is_current: e.target.checked }))}
              className="h-4 w-4 rounded text-[#0EA5E9] focus:ring-[#0EA5E9] border-slate-300"
            />
            <span className="text-xs text-[#58708F]">Current (used in classification lookups)</span>
          </div>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={isPending}>Save</Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

function ImportDialog({ manufacturerId, onClose }: { manufacturerId: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<BulkImportPreview | null>(null);
  const [result, setResult] = useState<BulkImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previewMutation = usePreviewImport(manufacturerId);
  const commitMutation = useCommitImport(manufacturerId);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] || null;
    setFile(f);
    setPreview(null);
    setResult(null);
    setError(null);
    if (f) {
      try {
        const p = await previewMutation.mutateAsync(f);
        setPreview(p);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to preview file");
      }
    }
  };

  const handleCommit = async () => {
    if (!file) return;
    setError(null);
    try {
      const r = await commitMutation.mutateAsync(file);
      setResult(r);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Import failed");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogHeader>
        <DialogTitle>Import CSV / Excel</DialogTitle>
        <DialogDescription>
          Supported columns: <span className="font-mono text-[11px]">{IMPORT_COLUMNS}</span>. Only <span className="font-mono text-[11px]">code</span> and <span className="font-mono text-[11px]">category</span> are required.
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4">
        {error && <Alert variant="destructive">{error}</Alert>}

        <input
          type="file"
          accept=".csv,.xlsx"
          onChange={handleFileChange}
          className="w-full text-sm text-[#58708F] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-sky-50 file:text-[#0EA5E9] hover:file:bg-sky-100"
        />

        {previewMutation.isPending && (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-[#0EA5E9]" /></div>
        )}

        {preview && !result && (
          <div className="rounded-xl border border-[#DCE6F0] p-4 space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-[#58708F]">Rows</span><span className="font-bold text-[#0F2747]">{preview.total_rows}</span></div>
            <div className="flex justify-between"><span className="text-[#58708F]">Valid</span><span className="font-bold text-emerald-600">{preview.valid}</span></div>
            <div className="flex justify-between"><span className="text-[#58708F]">Duplicates</span><span className="font-bold text-amber-600">{preview.duplicates}</span></div>
            <div className="flex justify-between"><span className="text-[#58708F]">Invalid</span><span className="font-bold text-rose-600">{preview.invalid}</span></div>
            {preview.errors.length > 0 && (
              <div className="pt-2 border-t border-[#DCE6F0] space-y-1 max-h-32 overflow-y-auto">
                {preview.errors.map((e, i) => (
                  <div key={i} className="text-[11px] text-rose-700 flex items-start gap-1">
                    <AlertTriangle className="h-3 w-3 shrink-0 mt-0.5" />
                    Row {e.row}{e.code ? ` (${e.code})` : ""}: {e.reason}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {result && (
          <Alert variant="success" title="Import Complete">
            Imported {result.imported} entries. Skipped {result.skipped_duplicates} duplicates and {result.skipped_invalid} invalid rows.
          </Alert>
        )}
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>{result ? "Close" : "Cancel"}</Button>
        {!result && (
          <Button
            type="button"
            disabled={!preview || preview.valid === 0}
            isLoading={commitMutation.isPending}
            onClick={handleCommit}
          >
            Import {preview ? `${preview.valid} Codes` : ""}
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
}

// ---- Specification Book: Upload -> Extract -> Review -> Approve ----------

const SPEC_BOOK_STATUS_BADGE: Record<SpecBook["status"], React.ReactNode> = {
  UPLOADED: <Badge variant="secondary">Uploaded</Badge>,
  EXTRACTING: <Badge variant="info"><Loader2 className="h-3 w-3 animate-spin" /> Extracting</Badge>,
  EXTRACTED: <Badge variant="success"><CheckCircle2 className="h-3 w-3" /> Ready for Review</Badge>,
  FAILED: <Badge variant="destructive"><AlertTriangle className="h-3 w-3" /> Failed</Badge>,
};

function SpecBooksSection({ manufacturerId }: { manufacturerId: string }) {
  const { data: books, isLoading } = useSpecBooks(manufacturerId);
  const [showUpload, setShowUpload] = useState(false);
  const [reviewBookId, setReviewBookId] = useState<string | null>(null);

  // Poll any book still extracting so status/badge updates without a manual refresh.
  const hasExtracting = (books || []).some((b) => b.status === "EXTRACTING");

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-[#0EA5E9]">
              <BookOpen className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base">Specification Books</CardTitle>
              <CardDescription>Upload a manufacturer catalog PDF to extract candidate codes for review.</CardDescription>
            </div>
          </div>
          <Button onClick={() => setShowUpload(true)}>
            <Upload className="h-4 w-4 mr-1.5" /> Upload Spec Book
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-6"><Loader2 className="h-5 w-5 animate-spin text-[#0EA5E9]" /></div>
        ) : !books || books.length === 0 ? (
          <div className="text-center py-8 text-sm text-[#58708F]">No specification books uploaded yet.</div>
        ) : (
          <div className="space-y-2">
            {books.map((book) => (
              <SpecBookRowSummary key={book.id} manufacturerId={manufacturerId} book={book} onReview={() => setReviewBookId(book.id)} poll={hasExtracting} />
            ))}
          </div>
        )}
      </CardContent>

      {showUpload && <UploadSpecBookDialog manufacturerId={manufacturerId} onClose={() => setShowUpload(false)} />}
      {reviewBookId && (
        <SpecBookReviewDialog manufacturerId={manufacturerId} bookId={reviewBookId} onClose={() => setReviewBookId(null)} />
      )}
    </Card>
  );
}

function SpecBookRowSummary({
  manufacturerId, book, onReview, poll,
}: { manufacturerId: string; book: SpecBook; onReview: () => void; poll: boolean }) {
  // Individually poll this book while it's extracting so its badge flips to
  // Ready/Failed without the user refreshing the page.
  const { data: live } = useSpecBook(manufacturerId, book.id, { refetchInterval: poll && book.status === "EXTRACTING" ? 2000 : false });
  const current = live || book;

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-[#DCE6F0] bg-white">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-[#0F2747] truncate">{current.original_filename}</div>
        <div className="text-xs text-[#58708F]">
          {current.source_version ? `Version ${current.source_version} · ` : ""}
          {new Date(current.created_at).toLocaleDateString()}
          {current.status === "FAILED" && current.error?.message ? ` · ${current.error.message}` : ""}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {SPEC_BOOK_STATUS_BADGE[current.status]}
        {current.status === "EXTRACTED" && (
          <Button size="sm" variant="outline" onClick={onReview}>Review</Button>
        )}
      </div>
    </div>
  );
}

function UploadSpecBookDialog({ manufacturerId, onClose }: { manufacturerId: string; onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [sourceVersion, setSourceVersion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const uploadMutation = useUploadSpecBook(manufacturerId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose a PDF file to upload");
      return;
    }
    try {
      await uploadMutation.mutateAsync({ file, sourceVersion: sourceVersion || undefined });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <DialogHeader>
          <DialogTitle>Upload Specification Book</DialogTitle>
          <DialogDescription>
            PDF catalogs are read with AI extraction; CSV/Excel catalogs are read deterministically by matching
            columns like Code/SKU, Description, and Category — no AI guessing needed since the data is already
            structured. Either way, extraction runs in the background and nothing is added to the dictionary
            until you review and approve it.
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Catalog File (PDF, CSV, or Excel)</label>
          <input
            type="file"
            accept=".pdf,.csv,.xlsx"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-[#58708F] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-sky-50 file:text-[#0EA5E9] hover:file:bg-sky-100"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Source Version (optional)</label>
          <input
            value={sourceVersion}
            onChange={(e) => setSourceVersion(e.target.value)}
            placeholder="e.g. 2026 Fall Catalog"
            className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={uploadMutation.isPending}>Upload & Extract</Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}

function SpecBookReviewDialog({ manufacturerId, bookId, onClose }: { manufacturerId: string; bookId: string; onClose: () => void }) {
  const { data: rows, isLoading } = useSpecBookRows(manufacturerId, bookId, "PENDING");
  const approveMutation = useApproveSpecBookRows(manufacturerId, bookId);
  const [approveResult, setApproveResult] = useState<{ approved: number; skipped_duplicates: number } | null>(null);

  const handleApproveAll = async () => {
    const result = await approveMutation.mutateAsync({ approve_all: true });
    setApproveResult(result);
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogHeader>
        <DialogTitle>Review Extracted Codes</DialogTitle>
        <DialogDescription>
          Correct or reject any misread rows, then approve to add them to the manufacturer dictionary. Nothing is added until approved.
        </DialogDescription>
      </DialogHeader>

      {approveResult ? (
        <Alert variant="success" title="Approved">
          Added {approveResult.approved} new dictionary entries
          {approveResult.skipped_duplicates > 0 ? ` (${approveResult.skipped_duplicates} already existed and were skipped)` : ""}.
        </Alert>
      ) : isLoading ? (
        <div className="flex justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-[#0EA5E9]" /></div>
      ) : !rows || rows.length === 0 ? (
        <div className="text-center py-8 text-sm text-[#58708F]">No pending rows left to review.</div>
      ) : (
        <div className="max-h-[50vh] overflow-y-auto overflow-x-auto border border-[#DCE6F0] rounded-xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Page</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <SpecBookRowEditRow key={row.id} manufacturerId={manufacturerId} bookId={bookId} row={row} />
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>{approveResult ? "Close" : "Cancel"}</Button>
        {!approveResult && (
          <Button type="button" disabled={!rows || rows.length === 0} isLoading={approveMutation.isPending} onClick={handleApproveAll}>
            Approve All ({rows?.length ?? 0})
          </Button>
        )}
      </DialogFooter>
    </Dialog>
  );
}

function SpecBookRowEditRow({
  manufacturerId, bookId, row,
}: { manufacturerId: string; bookId: string; row: SpecBookRow }) {
  const [editing, setEditing] = useState(false);
  const [description, setDescription] = useState(row.description || "");
  const [category, setCategory] = useState<ItemCategory>(row.category);
  const updateMutation = useUpdateSpecBookRow(manufacturerId, bookId);
  const rejectMutation = useRejectSpecBookRow(manufacturerId, bookId);

  const handleSave = async () => {
    await updateMutation.mutateAsync({ rowId: row.id, data: { description, category } });
    setEditing(false);
  };

  if (row.status === "REJECTED") return null;

  return (
    <TableRow>
      <TableCell className="font-mono font-semibold text-[#0F2747]">
        {row.raw_code}
        {row.confidence !== null && row.confidence !== undefined && row.confidence < 0.5 && (
          <span title="Low extraction confidence"><AlertTriangle className="inline h-3 w-3 ml-1 text-amber-500" /></span>
        )}
      </TableCell>
      <TableCell>
        {editing ? (
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full h-8 px-2 rounded border border-[#DCE6F0] text-sm"
          />
        ) : (
          <span className="text-[#58708F]">{row.description || "—"}</span>
        )}
      </TableCell>
      <TableCell>
        {editing ? (
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as ItemCategory)}
            className="h-8 px-2 rounded border border-[#DCE6F0] text-sm"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        ) : (
          <Badge variant={row.category === "UNKNOWN" ? "warning" : "outline"}>{row.category}</Badge>
        )}
      </TableCell>
      <TableCell className="text-[#58708F]">{row.page_number ?? "—"}</TableCell>
      <TableCell className="text-right">
        <div className="flex justify-end gap-1">
          {editing ? (
            <Button size="icon" variant="ghost" isLoading={updateMutation.isPending} onClick={handleSave} title="Save">
              <Check className="h-3.5 w-3.5 text-emerald-600" />
            </Button>
          ) : (
            <Button size="icon" variant="ghost" onClick={() => setEditing(true)} title="Edit">
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            size="icon" variant="ghost" isLoading={rejectMutation.isPending}
            onClick={() => rejectMutation.mutate(row.id)} title="Reject"
          >
            <X className="h-3.5 w-3.5 text-rose-600" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

// ---- NKBA Reference Library (global, storage-only, no extraction) --------

function NKBAReferenceLibrarySection() {
  const { data: docs, isLoading } = useNKBAReferenceDocuments();
  const [showUpload, setShowUpload] = useState(false);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base">NKBA Reference Library</CardTitle>
              <CardDescription>
                Store the generic NKBA nomenclature guideline for reference — not manufacturer-specific, and not used in cabinet classification.
              </CardDescription>
            </div>
          </div>
          <Button variant="outline" onClick={() => setShowUpload(true)}>
            <Upload className="h-4 w-4 mr-1.5" /> Upload NKBA PDF
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-[#0EA5E9]" /></div>
        ) : !docs || docs.length === 0 ? (
          <div className="text-center py-6 text-sm text-[#58708F]">No NKBA reference documents uploaded yet.</div>
        ) : (
          <div className="space-y-2">
            {docs.map((doc) => <NKBAReferenceDocRow key={doc.id} doc={doc} />)}
          </div>
        )}
      </CardContent>
      {showUpload && <UploadNKBAReferenceDialog onClose={() => setShowUpload(false)} />}
    </Card>
  );
}

function NKBAReferenceDocRow({ doc }: { doc: NKBAReferenceDocument }) {
  const downloadMutation = useNKBAReferenceDownloadUrl();
  const deleteMutation = useDeleteNKBAReferenceDocument();

  const handleDownload = async () => {
    const { url } = await downloadMutation.mutateAsync(doc.id);
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-[#DCE6F0] bg-white">
      <div className="min-w-0">
        <div className="text-sm font-semibold text-[#0F2747] truncate">{doc.label}</div>
        <div className="text-xs text-[#58708F] truncate">{doc.original_filename} · {new Date(doc.created_at).toLocaleDateString()}</div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Button size="icon" variant="ghost" isLoading={downloadMutation.isPending} onClick={handleDownload} title="Download">
          <Download className="h-3.5 w-3.5" />
        </Button>
        <Button
          size="icon" variant="ghost" isLoading={deleteMutation.isPending}
          onClick={() => {
            if (window.confirm(`Delete "${doc.label}"?`)) deleteMutation.mutate(doc.id);
          }}
          title="Delete"
        >
          <Trash2 className="h-3.5 w-3.5 text-rose-600" />
        </Button>
      </div>
    </div>
  );
}

function UploadNKBAReferenceDialog({ onClose }: { onClose: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const uploadMutation = useUploadNKBAReferenceDocument();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose a PDF file to upload");
      return;
    }
    if (!label.trim()) {
      setError("A label (e.g. 'NKBA 5th Edition') is required");
      return;
    }
    try {
      await uploadMutation.mutateAsync({ file, label: label.trim() });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <DialogHeader>
          <DialogTitle>Upload NKBA Reference Document</DialogTitle>
          <DialogDescription>
            Stored for reference only — visible to every organization, but never extracted from or used to
            classify cabinet codes.
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive">{error}</Alert>}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">Label</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. NKBA 5th Edition"
            className="w-full h-10 px-3 rounded-lg border border-[#DCE6F0] bg-white text-sm focus:border-[#0EA5E9] focus:outline-none focus:ring-1 focus:ring-[#0EA5E9]"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-xs font-semibold uppercase tracking-wider text-[#58708F]">PDF File</label>
          <input
            type="file"
            accept=".pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-[#58708F] file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-sky-50 file:text-[#0EA5E9] hover:file:bg-sky-100"
          />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
          <Button type="submit" isLoading={uploadMutation.isPending}>Upload</Button>
        </DialogFooter>
      </form>
    </Dialog>
  );
}
