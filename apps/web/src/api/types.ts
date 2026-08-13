export type Envelope<T> = {
  code: string;
  message: string;
  data: T;
};

export type WorkbenchSummary = {
  as_of: string;
  park_id: number | null;
  metrics: {
    open_todos: number;
    overdue_todos: number;
    due_soon_todos: number;
    unpaid_bills: number;
    expiring_contracts: number;
    expiring_within_days: number;
  };
  recent_todos: Array<{
    id: number;
    title: string;
    status: string;
    priority: string;
    item_type: string;
    due_at: string | null;
    source_type: string;
    source_id: string;
  }>;
};

export type PageResult<T> = {
  total: number;
  page: number;
  page_size: number;
  items: T[];
};
