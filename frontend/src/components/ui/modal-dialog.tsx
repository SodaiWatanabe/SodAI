"use client";

import {
  forwardRef,
  type ComponentPropsWithoutRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from "react";

export type ModalDialogHandle = {
  close: (returnValue?: string) => void;
};

export type ModalDialogProps = Omit<
  ComponentPropsWithoutRef<"dialog">,
  "onCancel" | "onClick" | "onClose"
> & {
  dismissible?: boolean;
  initialFocus?: "auto" | "dialog";
  onClose?: () => void;
  onRequestClose?: () => void;
};

export const ModalDialog = forwardRef<ModalDialogHandle, ModalDialogProps>(
  function ModalDialog(
    {
      children,
      className = "",
      dismissible = true,
      initialFocus = "auto",
      onClose,
      onRequestClose,
      tabIndex,
      ...props
    },
    forwardedRef,
  ) {
    const dialogRef = useRef<HTMLDialogElement>(null);

    const close = useCallback((returnValue?: string) => {
      dialogRef.current?.close(returnValue);
    }, []);

    const requestClose = useCallback(() => {
      if (!dismissible) return;

      if (onRequestClose) {
        onRequestClose();
      } else {
        close();
      }
    }, [close, dismissible, onRequestClose]);

    useImperativeHandle(forwardedRef, () => ({ close }), [close]);

    useEffect(() => {
      const dialog = dialogRef.current;
      if (!dialog) return;

      if (!dialog.open) dialog.showModal();
      if (initialFocus === "dialog") {
        dialog.focus({ preventScroll: true });
      }
    }, [initialFocus]);

    return (
      <dialog
        {...props}
        ref={dialogRef}
        tabIndex={initialFocus === "dialog" ? -1 : tabIndex}
        className={`ui-modal m-auto rounded-[28px] border border-[var(--divider)] bg-[var(--surface)] p-0 text-[var(--text)] shadow-[0_28px_80px_var(--dialog-shadow)] outline-none ${className}`}
        onCancel={(event) => {
          event.preventDefault();
          requestClose();
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget) requestClose();
        }}
        onClose={onClose}
      >
        {children}
      </dialog>
    );
  },
);
