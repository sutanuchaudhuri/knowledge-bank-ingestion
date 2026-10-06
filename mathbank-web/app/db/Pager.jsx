"use client";

import { Pager as KitPager } from "../_components/ui.jsx";

/** Prev/Next pager for the grid pages — uses a hasMore flag (limit+1 fetch trick) instead of a total count. */
export default function Pager(props) {
  return <KitPager {...props} />;
}
