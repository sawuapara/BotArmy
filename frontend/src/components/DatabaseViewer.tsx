import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Database, Table, ChevronLeft, ChevronRight, ChevronDown, RefreshCw, ArrowUpDown, LayoutDashboard, Folder, FolderOpen, Lock } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface TableInfo {
  name: string;
  schema_name: string;
  row_count: number;
  full_name: string;
}

interface SchemaInfo {
  name: string;
  tables: TableInfo[];
}

interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  default: string | null;
  is_primary: boolean;
}

interface TableSchema {
  name: string;
  schema_name: string;
  columns: ColumnInfo[];
  row_count: number;
}

interface TableData {
  table: string;
  schema_name: string;
  columns: string[];
  rows: Record<string, any>[];
  total_count: number;
  limit: number;
  offset: number;
}

export function DatabaseViewer() {
  const [schemas, setSchemas] = useState<SchemaInfo[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null); // full_name: schema.table
  const [tableSchema, setTableSchema] = useState<TableSchema | null>(null);
  const [data, setData] = useState<TableData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [orderBy, setOrderBy] = useState<string | null>(null);
  const [orderDir, setOrderDir] = useState<'ASC' | 'DESC'>('DESC');
  const [expandedSchemas, setExpandedSchemas] = useState<Set<string>>(new Set(['public']));
  const pageSize = 50;

  // Fetch schemas on mount
  useEffect(() => {
    fetchSchemas();
  }, []);

  // Fetch data when table or pagination changes
  useEffect(() => {
    if (selectedTable) {
      fetchTableData(selectedTable);
    }
  }, [selectedTable, page, orderBy, orderDir]);

  async function fetchSchemas() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/database/schemas`);
      if (!res.ok) throw new Error('Failed to fetch schemas');
      const data = await res.json();
      setSchemas(data);
      // Expand all schemas by default
      setExpandedSchemas(new Set(data.map((s: SchemaInfo) => s.name)));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  async function fetchTableSchema(fullName: string) {
    try {
      const res = await fetch(`${API_BASE}/database/tables/${fullName}/schema`);
      if (!res.ok) throw new Error('Failed to fetch schema');
      const data = await res.json();
      setTableSchema(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    }
  }

  async function fetchTableData(fullName: string) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        limit: pageSize.toString(),
        offset: (page * pageSize).toString(),
      });
      if (orderBy) {
        params.set('order_by', orderBy);
        params.set('order_dir', orderDir);
      }
      const res = await fetch(`${API_BASE}/database/tables/${fullName}/data?${params}`);
      if (!res.ok) throw new Error('Failed to fetch data');
      const data = await res.json();
      setData(data);
      // Also fetch schema if not already loaded
      if (!tableSchema || `${tableSchema.schema_name}.${tableSchema.name}` !== fullName) {
        fetchTableSchema(fullName);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }

  function selectTable(fullName: string) {
    setSelectedTable(fullName);
    setPage(0);
    setOrderBy(null);
    setOrderDir('DESC');
    setTableSchema(null);
    setData(null);
  }

  function toggleSchema(schemaName: string) {
    setExpandedSchemas(prev => {
      const next = new Set(prev);
      if (next.has(schemaName)) {
        next.delete(schemaName);
      } else {
        next.add(schemaName);
      }
      return next;
    });
  }

  function handleSort(column: string) {
    if (orderBy === column) {
      setOrderDir(orderDir === 'ASC' ? 'DESC' : 'ASC');
    } else {
      setOrderBy(column);
      setOrderDir('DESC');
    }
    setPage(0);
  }

  const totalPages = data ? Math.ceil(data.total_count / pageSize) : 0;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-3">
              <Database className="w-6 h-6 text-blue-400" />
              <h1 className="text-xl font-semibold">Database Explorer</h1>
            </div>
            <nav className="flex items-center gap-2">
              <Link
                to="/"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-gray-700 hover:bg-gray-600 text-gray-300"
              >
                <LayoutDashboard className="w-4 h-4" />
                Dashboard
              </Link>
              <Link
                to="/database"
                className="px-3 py-1.5 rounded text-sm bg-blue-600 text-white"
              >
                Database
              </Link>
              <Link
                to="/vault"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm bg-gray-700 hover:bg-gray-600 text-gray-300"
              >
                <Lock className="w-4 h-4" />
                Vault
              </Link>
            </nav>
          </div>
          <button
            onClick={() => {
              fetchSchemas();
              if (selectedTable) fetchTableData(selectedTable);
            }}
            className="flex items-center gap-2 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar - Schema/Table List */}
        <aside className="w-64 bg-gray-800 border-r border-gray-700 min-h-[calc(100vh-73px)]">
          <div className="p-4">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">
              Schemas
            </h2>
            {error && !schemas.length && (
              <div className="text-red-400 text-sm p-2 bg-red-900/20 rounded">
                {error}
              </div>
            )}
            <div className="space-y-2">
              {schemas.map((schema) => (
                <div key={schema.name}>
                  {/* Schema header */}
                  <button
                    onClick={() => toggleSchema(schema.name)}
                    className="w-full flex items-center justify-between px-2 py-1.5 rounded text-left text-sm hover:bg-gray-700 text-gray-300"
                  >
                    <span className="flex items-center gap-2">
                      {expandedSchemas.has(schema.name) ? (
                        <FolderOpen className="w-4 h-4 text-yellow-500" />
                      ) : (
                        <Folder className="w-4 h-4 text-yellow-600" />
                      )}
                      <span className="font-medium">{schema.name}</span>
                    </span>
                    <ChevronDown
                      className={`w-4 h-4 transition-transform ${
                        expandedSchemas.has(schema.name) ? '' : '-rotate-90'
                      }`}
                    />
                  </button>
                  {/* Tables in schema */}
                  {expandedSchemas.has(schema.name) && (
                    <ul className="ml-4 mt-1 space-y-0.5">
                      {schema.tables.map((table) => (
                        <li key={table.full_name}>
                          <button
                            onClick={() => selectTable(table.full_name)}
                            className={`w-full flex items-center justify-between px-2 py-1.5 rounded text-left text-sm transition-colors ${
                              selectedTable === table.full_name
                                ? 'bg-blue-600 text-white'
                                : 'hover:bg-gray-700 text-gray-300'
                            }`}
                          >
                            <span className="flex items-center gap-2">
                              <Table className="w-3.5 h-3.5" />
                              {table.name}
                            </span>
                            <span className="text-xs opacity-60">{table.row_count}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        </aside>

        {/* Main Content - Table Data */}
        <main className="flex-1 p-6">
          {!selectedTable ? (
            <div className="flex flex-col items-center justify-center h-96 text-gray-500">
              <Database className="w-16 h-16 mb-4 opacity-50" />
              <p>Select a table to view its data</p>
            </div>
          ) : (
            <div>
              {/* Table Header */}
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold">{selectedTable}</h2>
                  {tableSchema && (
                    <p className="text-sm text-gray-400">
                      {tableSchema.columns.length} columns, {data?.total_count ?? tableSchema.row_count} rows
                    </p>
                  )}
                </div>

                {/* Pagination */}
                {data && totalPages > 1 && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(Math.max(0, page - 1))}
                      disabled={page === 0}
                      className="p-1 rounded hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="w-5 h-5" />
                    </button>
                    <span className="text-sm text-gray-400">
                      Page {page + 1} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                      disabled={page >= totalPages - 1}
                      className="p-1 rounded hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="w-5 h-5" />
                    </button>
                  </div>
                )}
              </div>

              {/* Schema Info */}
              {tableSchema && (
                <div className="mb-4 p-3 bg-gray-800 rounded-lg text-xs">
                  <div className="flex flex-wrap gap-2">
                    {tableSchema.columns.map((col) => (
                      <span
                        key={col.name}
                        className={`px-2 py-1 rounded ${
                          col.is_primary
                            ? 'bg-yellow-900/50 text-yellow-300 border border-yellow-700'
                            : 'bg-gray-700 text-gray-300'
                        }`}
                        title={`${col.type}${col.nullable ? ', nullable' : ''}${col.default ? `, default: ${col.default}` : ''}`}
                      >
                        {col.is_primary && '🔑 '}
                        {col.name}
                        <span className="ml-1 opacity-50">{col.type}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Data Table */}
              {loading ? (
                <div className="flex items-center justify-center h-64">
                  <RefreshCw className="w-8 h-8 animate-spin text-blue-400" />
                </div>
              ) : error ? (
                <div className="text-red-400 p-4 bg-red-900/20 rounded">
                  {error}
                </div>
              ) : data && data.rows.length > 0 ? (
                <div className="overflow-x-auto rounded-lg border border-gray-700">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800">
                      <tr>
                        {data.columns.map((col) => (
                          <th
                            key={col}
                            onClick={() => handleSort(col)}
                            className="px-4 py-3 text-left font-medium text-gray-300 cursor-pointer hover:bg-gray-700 select-none"
                          >
                            <span className="flex items-center gap-1">
                              {col}
                              {orderBy === col && (
                                <ArrowUpDown className="w-3 h-3 text-blue-400" />
                              )}
                            </span>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {data.rows.map((row, idx) => (
                        <tr key={idx} className="hover:bg-gray-800/50">
                          {data.columns.map((col) => (
                            <td key={col} className="px-4 py-2 text-gray-300">
                              {renderCell(row[col])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  No data in this table
                </div>
              )}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

function renderCell(value: any): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-gray-500 italic">null</span>;
  }
  if (typeof value === 'boolean') {
    return <span className={value ? 'text-green-400' : 'text-red-400'}>{value.toString()}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-gray-500">[]</span>;
    return (
      <span className="text-purple-300">
        [{value.map((v, i) => (
          <span key={i}>
            {i > 0 && ', '}
            {JSON.stringify(v)}
          </span>
        ))}]
      </span>
    );
  }
  if (typeof value === 'string') {
    // Check if it looks like a UUID
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)) {
      return <span className="font-mono text-xs text-cyan-400">{value.slice(0, 8)}...</span>;
    }
    // Check if it looks like an ISO date
    if (/^\d{4}-\d{2}-\d{2}T/.test(value)) {
      const date = new Date(value);
      return (
        <span className="text-orange-300" title={value}>
          {date.toLocaleDateString()} {date.toLocaleTimeString()}
        </span>
      );
    }
    // Truncate long strings
    if (value.length > 100) {
      return (
        <span title={value}>
          {value.slice(0, 100)}
          <span className="text-gray-500">...</span>
        </span>
      );
    }
  }
  return String(value);
}
