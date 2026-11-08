export function SkeletonRow() {
  return (
    <div className="flex gap-3 bg-white rounded-2xl p-3 border border-gray-100 shadow-sm animate-pulse">
      <div className="w-20 h-20 rounded-xl bg-gray-200 shrink-0" />
      <div className="flex-1 space-y-2 py-1">
        <div className="h-4 bg-gray-200 rounded w-2/3" />
        <div className="h-3 bg-gray-200 rounded w-1/3" />
        <div className="h-3 bg-gray-200 rounded w-1/2" />
      </div>
    </div>
  )
}
