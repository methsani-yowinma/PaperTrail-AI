"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

function Toaster(props: ToasterProps) {
  return (
    <Sonner
      position="bottom-right"
      closeButton
      toastOptions={{ classNames: { toast: "!rounded-xl !border-border !shadow-md", description: "!text-muted-foreground" } }}
      {...props}
    />
  );
}

export { Toaster };
