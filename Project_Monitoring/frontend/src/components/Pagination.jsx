function Pagination({
  offset,
  total,
  pageSize,
  onPageChange,
  label,
  singularLabel = label,
}) {
  const totalPages = Math.ceil(total / pageSize);
  const currentPage = totalPages
    ? Math.min(Math.floor(offset / pageSize) + 1, totalPages)
    : 0;
  const firstItem = total ? offset + 1 : 0;
  const lastItem = Math.min(offset + pageSize, total);
  const countLabel = total === 1 ? singularLabel : label;

  return (
    <nav className="pagination" aria-label={`Pagination ${label}`}>
      <span className="pagination-summary">
        {firstItem}–{lastItem} sur {total} {countLabel}
      </span>

      {totalPages > 1 && (
        <div className="pagination-controls">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(0, offset - pageSize))}
            disabled={offset === 0}
          >
            Précédent
          </button>
          <span>
            Page {currentPage} sur {totalPages}
          </span>
          <button
            type="button"
            onClick={() => onPageChange(offset + pageSize)}
            disabled={offset + pageSize >= total}
          >
            Suivant
          </button>
        </div>
      )}
    </nav>
  );
}

export default Pagination;
