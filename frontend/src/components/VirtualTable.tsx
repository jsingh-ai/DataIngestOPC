import { useRef, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

type Column<T> = {
  key: keyof T | string;
  header: ReactNode;
  width?: string;
  render: (item: T) => ReactNode;
};

export function VirtualTable<T extends { [key: string]: unknown }>({
  columns,
  rows,
  rowHeight = 44,
}: {
  columns: Column<T>[];
  rows: T[];
  rowHeight?: number;
}): JSX.Element {
  const parentRef = useRef<HTMLDivElement | null>(null);
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 8,
  });

  return (
    <div className="virtual-table">
      <div className="table-header" style={{ gridTemplateColumns: columns.map((c) => c.width ?? "1fr").join(" ") }}>
        {columns.map((column) => (
          <div key={String(column.key)}>{column.header}</div>
        ))}
      </div>
      <div ref={parentRef} className="table-body">
        <div style={{ height: rowVirtualizer.getTotalSize(), position: "relative" }}>
          {rowVirtualizer.getVirtualItems().map((virtualRow) => {
            const row = rows[virtualRow.index];
            return (
              <div
                key={virtualRow.key}
                className="table-row"
                style={{
                  height: rowHeight,
                  transform: `translateY(${virtualRow.start}px)`,
                  gridTemplateColumns: columns.map((c) => c.width ?? "1fr").join(" "),
                }}
              >
                {columns.map((column) => (
                  <div key={String(column.key)}>{column.render(row)}</div>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
