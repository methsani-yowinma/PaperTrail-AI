import { cn } from "@/lib/utils";

/**
 * Renders a stored passage, highlighting [start, end) when the offsets were verified
 * against the stored text by the backend. Nothing here is model-generated text.
 */
export function HighlightedPassage({
  text,
  start,
  end,
  className,
}: {
  text: string;
  start?: number | null;
  end?: number | null;
  className?: string;
}) {
  const valid = start != null && end != null && start >= 0 && end > start && end <= text.length;
  return (
    <p className={cn("prose-excerpt whitespace-pre-line", className)}>
      {valid ? (
        <>
          {text.slice(0, start)}
          <mark>{text.slice(start, end)}</mark>
          {text.slice(end)}
        </>
      ) : (
        text
      )}
    </p>
  );
}
